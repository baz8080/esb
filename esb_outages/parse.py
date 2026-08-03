"""Normalisation of ESB API payloads.

Every function here is pure and total: it never raises on odd input, it returns
what it could parse plus a flag. The raw strings are always preserved alongside
the parsed values in the database, so a bug in this module costs nothing that a
`rebuild` cannot fix.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ESB's timestamps carry no offset. They are Europe/Dublin wall-clock time:
# outage 2826455 reported restoreTime 31/07/2026 17:34 while the server clock
# read 17:26 UTC. Read as UTC that restoration would be in the future for an
# already-restored outage, so the field must be local (UTC+1 at the time).
DUBLIN = ZoneInfo("Europe/Dublin")

ESB_DATETIME_FORMAT = "%d/%m/%Y %H:%M"

# The full field set of a detail response, as observed live. Anything added or
# removed by ESB trips schema-drift detection and fails the run loudly, because
# a silently changed API is how a collector rots without anyone noticing.
DETAIL_FIELDS = frozenset(
    {
        "outageId",
        "outageType",
        "point",
        "location",
        "plannerGroup",
        "numCustAffected",
        "startTime",
        "estRestoreTime",
        "statusMessage",
        "restoreTime",
        "plannedOutageReason",
    }
)

LIST_ITEM_FIELDS = frozenset({"i", "t", "p"})


def parse_esb_datetime(value: str | None) -> tuple[str | None, bool]:
    """Parse 'dd/mm/yyyy HH:MM' Dublin local time into an ISO8601 UTC string.

    Returns (utc_iso_or_None, tz_ambiguous). The flag is set when the wall-clock
    time is ambiguous or impossible because of a DST transition:

    - Fall back (last Sunday of October): 01:00-01:59 happens twice. We take the
      first occurrence (fold=0), so the value may be an hour late.
    - Spring forward (last Sunday of March): 01:00-01:59 never happens. Python
      resolves it, but the result is a fiction.

    Either way the raw string is retained in the database, so a flagged row can
    be revisited rather than silently trusted.
    """
    if not value or not value.strip():
        return None, False
    try:
        naive = datetime.strptime(value.strip(), ESB_DATETIME_FORMAT)
    except ValueError:
        return None, False

    local = naive.replace(tzinfo=DUBLIN)

    ambiguous = local.utcoffset() != local.replace(fold=1).utcoffset()
    roundtrip = local.astimezone(timezone.utc).astimezone(DUBLIN)
    imaginary = roundtrip.replace(tzinfo=None) != naive

    utc = local.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ"), bool(ambiguous or imaginary)


# The list endpoint returns 5-decimal coordinates and the detail endpoint returns
# full float precision, so an unrounded comparison logs 55.14151 -> 55.14151191932
# as a change. That noise was 34 of the first 200 recorded changes. Five decimals
# is ~1.1m, matches the coarser of the two sources, and still catches the real
# thing this field is worth watching: ESB relocating a fault as crews narrow it
# down, which shows up as moves of tens to hundreds of metres.
COORD_PRECISION = 5


def parse_point(point) -> tuple[float | None, float | None, str | None]:
    """Pull (lat, lon) out of {"c": "52.39,-8.85"}, keeping the raw string.

    Coordinates are rounded; `raw` keeps the value exactly as sent, and the JSONL
    log keeps the whole response, so nothing is actually discarded.
    """
    if not isinstance(point, dict):
        return None, None, None
    raw = point.get("c")
    if not isinstance(raw, str) or "," not in raw:
        return None, None, raw if isinstance(raw, str) else None
    lat_s, _, lon_s = raw.partition(",")
    try:
        return (
            round(float(lat_s), COORD_PRECISION),
            round(float(lon_s), COORD_PRECISION),
            raw,
        )
    except ValueError:
        return None, None, raw


def check_detail_schema(body: dict) -> list[str]:
    """Return human-readable descriptions of any drift from the known shape."""
    keys = set(body)
    problems = []
    unexpected = sorted(keys - DETAIL_FIELDS)
    missing = sorted(DETAIL_FIELDS - keys)
    if unexpected:
        problems.append(f"unexpected field(s): {', '.join(unexpected)}")
    if missing:
        problems.append(f"missing field(s): {', '.join(missing)}")
    return problems


def check_list_schema(body: dict) -> list[str]:
    problems = []
    if "outageMessage" not in body:
        return ["response has no 'outageMessage' key"]
    items = body["outageMessage"]
    if not isinstance(items, list):
        return ["'outageMessage' is not a list"]
    seen_unexpected: set[str] = set()
    seen_missing: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            problems.append("list item is not an object")
            break
        seen_unexpected |= set(item) - LIST_ITEM_FIELDS
        seen_missing |= LIST_ITEM_FIELDS - set(item)
    if seen_unexpected:
        problems.append(f"unexpected list field(s): {', '.join(sorted(seen_unexpected))}")
    if seen_missing:
        problems.append(f"missing list field(s): {', '.join(sorted(seen_missing))}")
    return problems


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value):
    """Normalise ESB's empty-string sentinels to NULL, keeping real text."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def normalize_detail(body: dict) -> dict:
    """Turn a raw detail response into the column set stored in SQLite."""
    lat, lon, point_raw = parse_point(body.get("point"))

    start_utc, start_amb = parse_esb_datetime(body.get("startTime"))
    est_utc, est_amb = parse_esb_datetime(body.get("estRestoreTime"))
    restore_utc, restore_amb = parse_esb_datetime(body.get("restoreTime"))

    outage_type = _text(body.get("outageType"))
    restore_raw = _text(body.get("restoreTime"))

    return {
        "outage_id": str(body.get("outageId")),
        "outage_type": outage_type,
        "location": _text(body.get("location")),
        "planner_group": _text(body.get("plannerGroup")),
        "num_cust_affected": _int_or_none(body.get("numCustAffected")),
        "lat": lat,
        "lon": lon,
        "point_raw": point_raw,
        "start_time_raw": _text(body.get("startTime")),
        "start_time_utc": start_utc,
        "est_restore_time_raw": _text(body.get("estRestoreTime")),
        "est_restore_time_utc": est_utc,
        "restore_time_raw": restore_raw,
        "restore_time_utc": restore_utc,
        "status_message": _text(body.get("statusMessage")),
        "planned_outage_reason": _text(body.get("plannedOutageReason")),
        # An outage is only immutable once it is restored *and* carries the
        # actual restore time; "Restored" with an empty restoreTime is still
        # settling and must be re-fetched.
        "is_final": int(outage_type == "Restored" and restore_raw is not None),
        "tz_ambiguous": int(start_amb or est_amb or restore_amb),
    }
