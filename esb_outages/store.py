"""Storage: append-only JSONL as the source of truth, SQLite as an index.

The split matters. Every API response is written to JSONL verbatim, before any
parsing, and never rewritten. SQLite holds the normalised view and is entirely
disposable: `rebuild` deletes it and replays the logs. That means a parsing bug
discovered in month six can be fixed retroactively across all data ever
collected, which is the whole reason this project can afford to start collecting
before anyone knows what questions they want to ask.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1

# Fields compared on every observation to build the change history. This is what
# makes the dataset interesting later: it captures how ESB's restoration
# estimates drift during an incident, not just where they landed.
TRACKED_FIELDS = (
    "outage_type",
    "location",
    "planner_group",
    "num_cust_affected",
    "lat",
    "lon",
    "start_time_utc",
    "est_restore_time_utc",
    "restore_time_utc",
    "status_message",
    "planned_outage_reason",
)

DETAIL_COLUMNS = (
    "outage_type",
    "location",
    "planner_group",
    "num_cust_affected",
    "lat",
    "lon",
    "point_raw",
    "start_time_raw",
    "start_time_utc",
    "est_restore_time_raw",
    "est_restore_time_utc",
    "restore_time_raw",
    "restore_time_utc",
    "status_message",
    "planned_outage_reason",
    "is_final",
    "tz_ambiguous",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS outage (
    outage_id             TEXT PRIMARY KEY,
    outage_type           TEXT,
    location              TEXT,
    planner_group         TEXT,
    num_cust_affected     INTEGER,
    lat                   REAL,
    lon                   REAL,
    point_raw             TEXT,
    start_time_raw        TEXT,
    start_time_utc        TEXT,
    est_restore_time_raw  TEXT,
    est_restore_time_utc  TEXT,
    restore_time_raw      TEXT,
    restore_time_utc      TEXT,
    status_message        TEXT,
    planned_outage_reason TEXT,
    first_seen_utc        TEXT NOT NULL,
    last_seen_utc         TEXT NOT NULL,
    last_detail_utc       TEXT,
    has_detail            INTEGER NOT NULL DEFAULT 0,
    is_final              INTEGER NOT NULL DEFAULT 0,
    tz_ambiguous          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS outage_change (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    outage_id       TEXT NOT NULL,
    observed_at_utc TEXT NOT NULL,
    source          TEXT NOT NULL,
    field           TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT
);

CREATE TABLE IF NOT EXISTS run (
    run_id           TEXT PRIMARY KEY,
    started_at_utc   TEXT NOT NULL,
    finished_at_utc  TEXT,
    status           TEXT,
    exit_code        INTEGER,
    n_listed         INTEGER,
    n_detail_fetched INTEGER,
    n_detail_skipped INTEGER,
    n_errors         INTEGER,
    error_summary    TEXT
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE INDEX IF NOT EXISTS idx_outage_final ON outage(is_final);
CREATE INDEX IF NOT EXISTS idx_outage_start ON outage(start_time_utc);
CREATE INDEX IF NOT EXISTS idx_outage_last_seen ON outage(last_seen_utc);
CREATE INDEX IF NOT EXISTS idx_change_outage ON outage_change(outage_id);
CREATE INDEX IF NOT EXISTS idx_change_time ON outage_change(observed_at_utc);
"""


# How long an outage must go unchanged before it is treated as dormant, and how
# often to re-check it once it is. Expressed in hours rather than run counts so
# the behaviour does not shift if the poll interval changes.
QUIET_AFTER_HOURS = 6.0
STALE_RECHECK_HOURS = 6.0


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hours_between(earlier: str | None, later: str) -> float:
    """Hours from `earlier` to `later`; infinite if `earlier` is unknown."""
    if not earlier:
        return float("inf")
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        delta = datetime.strptime(later, fmt) - datetime.strptime(earlier, fmt)
    except ValueError:
        return float("inf")
    return delta.total_seconds() / 3600.0


def _month_of(iso_ts: str) -> str:
    return iso_ts[:7]


def _open_maybe_gzip(path: Path):
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8")
    return path.open("r", encoding="utf-8")


class Store:
    def __init__(self, data_dir: str | os.PathLike):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.db_path = self.data_dir / "esb.db"
        self._conn: sqlite3.Connection | None = None
        self.malformed_lines: list[str] = []

    # ---- lifecycle -------------------------------------------------------

    def open(self) -> Store:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        # WAL survives an abrupt NAS power cut far better than the default.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._conn.commit()
        return self

    def close(self) -> None:
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Store:
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store is not open")
        return self._conn

    # ---- raw append-only log --------------------------------------------

    def _append_raw(self, kind: str, month: str, record: dict) -> None:
        path = self.raw_dir / f"{kind}-{month}.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            # The point of this file is to survive the NAS losing power mid-run.
            os.fsync(fh.fileno())

    def write_run_raw(
        self,
        run_id: str,
        started_at: str,
        list_status: int,
        list_body,
        status: str = "ok",
    ) -> None:
        """Record the list response verbatim, before any detail fetching starts.

        Also written for runs that failed outright, with a null body, so that a
        rebuilt database still shows the failure rather than a silent gap.
        """
        self._append_raw(
            "runs",
            _month_of(started_at),
            {
                "run_id": run_id,
                "started_at": started_at,
                "list_status": list_status,
                "list_body": list_body,
                "status": status,
            },
        )

    def write_observation_raw(
        self, run_id: str, observed_at: str, outage_id: str, http_status: int, body
    ) -> None:
        self._append_raw(
            "observations",
            _month_of(observed_at),
            {
                "run_id": run_id,
                "observed_at": observed_at,
                "outage_id": outage_id,
                "http_status": http_status,
                "body": body,
            },
        )

    def raw_files(self, kind: str) -> list[Path]:
        found = list(self.raw_dir.glob(f"{kind}-*.jsonl")) + list(
            self.raw_dir.glob(f"{kind}-*.jsonl.gz")
        )
        return sorted(found, key=lambda p: p.name)

    def iter_raw(self, kind: str):
        """Yield records from the raw log, skipping any line that will not parse.

        A single damaged line must never cost the whole history. The last line of
        a file can be truncated by a power cut mid-write, or captured mid-append
        by a backup, and neither is a reason to refuse to read the other 99.99%.
        Skips are counted and reported rather than passing silently.
        """
        for path in self.raw_files(kind):
            with _open_maybe_gzip(path) as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        self.malformed_lines.append(f"{path.name}:{lineno}: {exc}")

    # ---- applying observations ------------------------------------------

    def _record_change(
        self, outage_id: str, observed_at: str, source: str, field: str, old, new
    ) -> None:
        self.conn.execute(
            "INSERT INTO outage_change"
            " (outage_id, observed_at_utc, source, field, old_value, new_value)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                outage_id,
                observed_at,
                source,
                field,
                None if old is None else str(old),
                None if new is None else str(new),
            ),
        )

    def apply_list(self, observed_at: str, items: list[dict]) -> None:
        """Fold one list response into the database.

        Creates a stub row for outages never seen before, carrying the list's own
        coordinates. That stub is the only record we will ever have if the outage
        is purged before its detail call succeeds, so it is worth keeping even
        though the detail response duplicates the location.
        """
        from .parse import parse_point

        for item in items:
            outage_id = str(item.get("i"))
            list_type = item.get("t")
            lat, lon, point_raw = parse_point(item.get("p"))

            row = self.conn.execute(
                "SELECT outage_type, is_final FROM outage WHERE outage_id = ?",
                (outage_id,),
            ).fetchone()

            if row is None:
                self.conn.execute(
                    "INSERT INTO outage"
                    " (outage_id, outage_type, lat, lon, point_raw,"
                    "  first_seen_utc, last_seen_utc)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (outage_id, list_type, lat, lon, point_raw, observed_at, observed_at),
                )
                continue

            if list_type != row["outage_type"]:
                self._record_change(
                    outage_id, observed_at, "list", "outage_type",
                    row["outage_type"], list_type,
                )
                # The outage changed state, so whatever we hold is stale. Clearing
                # last_detail_utc forces a re-fetch on this run, which is what
                # makes the dormancy back-off in ids_needing_detail safe: a
                # transition is always picked up immediately, however long the
                # outage had been quiet. is_final goes too, in case ESB re-opened
                # an outage or recycled the ID.
                self.conn.execute(
                    "UPDATE outage SET outage_type = ?, last_seen_utc = ?,"
                    " is_final = 0, last_detail_utc = NULL WHERE outage_id = ?",
                    (list_type, observed_at, outage_id),
                )
            else:
                self.conn.execute(
                    "UPDATE outage SET last_seen_utc = ? WHERE outage_id = ?",
                    (observed_at, outage_id),
                )

    def ids_needing_detail(
        self,
        outage_ids: list[str],
        now: str | None = None,
        quiet_after_hours: float = QUIET_AFTER_HOURS,
        recheck_hours: float = STALE_RECHECK_HOURS,
    ) -> list[str]:
        """Which of these outages still need a detail fetch this run.

        Beyond skipping finalised outages, this backs off on ones that have gone
        quiet. ESB leaves planned works in the feed for weeks without ever
        touching them - in the first days of collection, nine such entries
        accounted for 71% of all detail fetches and produced not one change.

        Backing off is safe because the *list* is still fetched in full every
        run, and apply_list clears last_detail_utc the moment an outage's type
        changes. So a state transition is still caught within one poll; all that
        is delayed is a quiet outage's descriptive fields.
        """
        if not outage_ids:
            return []
        now = now or utc_now_iso()
        placeholders = ",".join("?" * len(outage_ids))
        rows = self.conn.execute(
            f"""SELECT o.outage_id, o.has_detail, o.is_final, o.last_detail_utc,
                       COALESCE(MAX(c.observed_at_utc), o.first_seen_utc) AS last_change
                FROM outage o
                LEFT JOIN outage_change c ON c.outage_id = o.outage_id
                WHERE o.outage_id IN ({placeholders})
                GROUP BY o.outage_id""",
            outage_ids,
        ).fetchall()
        state = {r["outage_id"]: r for r in rows}

        def needed(outage_id: str) -> bool:
            row = state.get(outage_id)
            if row is None or not row["has_detail"]:
                return True
            # Cleared by apply_list on a type change: something happened.
            if row["last_detail_utc"] is None:
                return True
            if row["is_final"]:
                return False
            if _hours_between(row["last_change"], now) < quiet_after_hours:
                return True  # actively changing, keep watching closely
            return _hours_between(row["last_detail_utc"], now) >= recheck_hours

        return [oid for oid in outage_ids if needed(oid)]

    def apply_detail(self, observed_at: str, normalized: dict) -> int:
        """Fold one detail response in, returning the number of changed fields."""
        outage_id = normalized["outage_id"]
        row = self.conn.execute(
            "SELECT * FROM outage WHERE outage_id = ?", (outage_id,)
        ).fetchone()

        changes = 0
        if row is None:
            # Detail arrived without the outage ever appearing in a list we
            # stored. Unusual but harmless; treat now as first sighting.
            columns = ", ".join(DETAIL_COLUMNS)
            marks = ", ".join("?" * len(DETAIL_COLUMNS))
            self.conn.execute(
                f"INSERT INTO outage (outage_id, {columns}, first_seen_utc,"
                f" last_seen_utc, last_detail_utc, has_detail)"
                f" VALUES (?, {marks}, ?, ?, ?, 1)",
                (
                    outage_id,
                    *[normalized[c] for c in DETAIL_COLUMNS],
                    observed_at,
                    observed_at,
                    observed_at,
                ),
            )
            return 0

        for field in TRACKED_FIELDS:
            old, new = row[field], normalized[field]
            if old != new:
                # A stub row created from a list response has NULLs everywhere;
                # filling them in for the first time is not a real "change".
                if not (row["has_detail"] == 0 and old is None):
                    self._record_change(
                        outage_id, observed_at, "detail", field, old, new
                    )
                    changes += 1

        assignments = ", ".join(f"{c} = ?" for c in DETAIL_COLUMNS)
        self.conn.execute(
            f"UPDATE outage SET {assignments}, last_seen_utc = ?,"
            f" last_detail_utc = ?, has_detail = 1 WHERE outage_id = ?",
            (
                *[normalized[c] for c in DETAIL_COLUMNS],
                observed_at,
                observed_at,
                outage_id,
            ),
        )
        return changes

    # ---- runs ------------------------------------------------------------

    def record_run(self, **fields) -> None:
        keys = list(fields)
        columns = ", ".join(keys)
        marks = ", ".join("?" * len(keys))
        self.conn.execute(
            f"INSERT OR REPLACE INTO run ({columns}) VALUES ({marks})",
            [fields[k] for k in keys],
        )

    # ---- rebuild ---------------------------------------------------------

    def rebuild(self, verbose: bool = False) -> dict:
        """Drop the database and replay it from the raw logs.

        Uses exactly the same apply_* methods as a live poll, so a successful
        rebuild is proof that the raw log is a sufficient source of truth.
        """
        from .parse import normalize_detail

        self.close()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(self.db_path) + suffix)
            if candidate.exists():
                candidate.unlink()
        self.open()

        # Replay follows the log's causal structure - each run's list, then the
        # detail fetches that run triggered - rather than sorting on timestamps.
        # Timestamps are only second-resolution, so several records can share
        # one, and sorting by them would silently reorder history.  Append order
        # within each file is the true order, and files sort chronologically by
        # their YYYY-MM name.
        observations: dict[str, list] = {}
        for rec in self.iter_raw("observations"):
            observations.setdefault(rec.get("run_id"), []).append(rec)

        n_runs = n_obs = 0

        def apply_observation(rec) -> int:
            if rec.get("http_status") == 200 and isinstance(rec.get("body"), dict):
                self.apply_detail(rec["observed_at"], normalize_detail(rec["body"]))
                return 1
            return 0

        # Sorted by start time, stably, so file order still breaks ties within a
        # second. For a single collector this is identical to file order; it
        # matters when logs from two hosts are concatenated during a migration,
        # where interleaved runs would otherwise replay out of order and skew
        # first_seen / last_seen.
        run_records = sorted(self.iter_raw("runs"), key=lambda r: r["started_at"])

        seen_run_ids = set()
        for rec in run_records:
            run_id = rec["run_id"]
            seen_run_ids.add(run_id)
            body = rec.get("list_body")
            items = body.get("outageMessage") if isinstance(body, dict) else None
            if isinstance(items, list):
                self.apply_list(rec["started_at"], items)

            # Reconstruct the run counters rather than leaving them null: they
            # are all derivable from the raw log, and they are what tells you
            # whether the dormancy back-off is working.
            run_obs = observations.get(run_id, [])
            fetched = sum(1 for o in run_obs if o.get("http_status") == 200)
            purged = sum(1 for o in run_obs if o.get("http_status") == 404)
            errors = sum(
                1 for o in run_obs if o.get("http_status") not in (200, 404)
            )
            listed = len(items) if isinstance(items, list) else None
            self.record_run(
                run_id=run_id,
                started_at_utc=rec["started_at"],
                status=rec.get("status", "ok"),
                n_listed=listed,
                n_detail_fetched=fetched,
                n_detail_skipped=(
                    listed - fetched - purged - errors if listed is not None else None
                ),
                n_errors=errors,
            )
            n_runs += 1
            for obs in run_obs:
                n_obs += apply_observation(obs)

        # Observations whose run record never made it to disk (a crash between
        # the two writes). Rare, but they are still real data.
        for run_id, records in observations.items():
            if run_id not in seen_run_ids:
                for obs in records:
                    n_obs += apply_observation(obs)

        self.conn.commit()
        if verbose:
            print(f"replayed {n_runs} runs and {n_obs} detail observations")
            for problem in self.malformed_lines:
                print(f"  skipped unreadable line {problem}", file=sys.stderr)
        return {
            "runs": n_runs,
            "observations": n_obs,
            "malformed": len(self.malformed_lines),
        }

    # ---- reporting -------------------------------------------------------

    def snapshot(self) -> list[tuple]:
        """Full ordered dump of derived state, for round-trip comparison."""
        outages = self.conn.execute(
            "SELECT * FROM outage ORDER BY outage_id"
        ).fetchall()
        changes = self.conn.execute(
            "SELECT outage_id, observed_at_utc, source, field, old_value, new_value"
            " FROM outage_change ORDER BY outage_id, observed_at_utc, field"
        ).fetchall()
        return [tuple(r) for r in outages] + [tuple(r) for r in changes]

    def stats(self) -> dict:
        c = self.conn
        row = c.execute(
            "SELECT COUNT(*) n, SUM(is_final) final, SUM(has_detail) detailed,"
            " SUM(tz_ambiguous) ambiguous, MIN(first_seen_utc) first,"
            " MAX(last_seen_utc) last FROM outage"
        ).fetchone()
        by_type = c.execute(
            "SELECT outage_type, COUNT(*) n FROM outage GROUP BY outage_type"
            " ORDER BY n DESC"
        ).fetchall()
        runs = c.execute(
            "SELECT COUNT(*) n, MIN(started_at_utc) first, MAX(started_at_utc) last"
            " FROM run"
        ).fetchone()
        changes = c.execute("SELECT COUNT(*) n FROM outage_change").fetchone()
        raw_bytes = sum(
            p.stat().st_size
            for kind in ("runs", "observations")
            for p in self.raw_files(kind)
        )
        recent = c.execute(
            "SELECT started_at_utc, status, n_listed, n_detail_fetched,"
            " n_detail_skipped, n_errors FROM run"
            " WHERE n_listed IS NOT NULL ORDER BY started_at_utc DESC LIMIT 6"
        ).fetchall()
        # Fetch efficiency over the recent window: the number to watch after a
        # change to the poll interval or the dormancy back-off.
        window = c.execute(
            "SELECT SUM(n_detail_fetched) f, SUM(n_detail_skipped) s FROM run"
            " WHERE status = 'ok' AND n_listed IS NOT NULL"
        ).fetchone()
        return {
            "outages": row["n"] or 0,
            "final": row["final"] or 0,
            "detailed": row["detailed"] or 0,
            "tz_ambiguous": row["ambiguous"] or 0,
            "first_seen": row["first"],
            "last_seen": row["last"],
            "by_type": [(r["outage_type"], r["n"]) for r in by_type],
            "runs": runs["n"] or 0,
            "first_run": runs["first"],
            "last_run": runs["last"],
            "changes": changes["n"] or 0,
            "raw_bytes": raw_bytes,
            "db_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            "recent_runs": [dict(r) for r in recent],
            "total_fetched": window["f"] or 0,
            "total_skipped": window["s"] or 0,
        }

    def compact(self) -> list[str]:
        """Gzip raw logs from previous months. The current month stays writable."""
        current = _month_of(utc_now_iso())
        compacted = []
        for kind in ("runs", "observations"):
            for path in self.raw_dir.glob(f"{kind}-*.jsonl"):
                month = path.stem.split("-", 1)[1]
                if month >= current:
                    continue
                target = Path(str(path) + ".gz")
                with path.open("rb") as src, gzip.open(target, "wb") as dst:
                    dst.write(src.read())
                path.unlink()
                compacted.append(target.name)
        return sorted(compacted)
