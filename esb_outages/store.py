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
import hashlib
import io
import json
import os
import re
import shutil
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


_UTC_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")

# What a run's end record carries: everything a rebuild cannot derive from the
# list and the observations.
RUN_END_FIELDS = ("status", "exit_code", "n_detail_skipped", "n_errors", "error_summary")

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


def _fsync_dir(path: Path) -> None:
    """Make a rename in `path` durable before anything relies on it."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _month_of(iso_ts: str) -> str:
    return iso_ts[:7]


def _open_maybe_gzip(path: Path):
    # A line torn inside a multi-byte character (any fada) must stay one
    # malformed line, not a decode error that ends the whole read.
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


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
        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        with path.open("a+b") as fh:
            # A line torn by a power cut would swallow this one too, and a run's
            # start line is its only copy of the list.
            if fh.seek(0, os.SEEK_END):
                fh.seek(-1, os.SEEK_END)
                if fh.read(1) != b"\n":
                    line = "\n" + line
            fh.write(line.encode("utf-8"))
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
                # Says an end line follows, so a rebuild can tell a run that
                # died from one logged before end lines existed.
                "ends_logged": True,
            },
        )

    def finish_run(self, **fields) -> None:
        """Log how a run ended, then record it.

        The start line is written before the run knows how it will end, so
        without this a rebuild restored every cut-short, partial or drifted
        run as "ok". Only what a rebuild cannot derive is logged.
        """
        self._append_raw(
            "runs",
            _month_of(fields["finished_at_utc"]),
            {
                "event": "end",
                "run_id": fields["run_id"],
                "finished_at": fields["finished_at_utc"],
                **{k: fields.get(k) for k in RUN_END_FIELDS},
            },
        )
        self.record_run(**fields)

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
        # Every line carries its own timestamps and run id, so an identical one
        # is the same record read twice: from a `sort -u`-less merge, or a
        # compact that crashed before removing what it had archived.
        seen: set[bytes] = set()
        month = None
        for path in self.raw_files(kind):
            # Copies share a month file, so the set never needs to span one.
            if path.name.split(".", 1)[0] != month:
                month = path.name.split(".", 1)[0]
                seen.clear()
            with _open_maybe_gzip(path) as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    digest = hashlib.blake2b(line.encode("utf-8"), digest_size=16).digest()
                    if digest in seen:
                        continue
                    seen.add(digest)
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
            # Already on disk, so replay meets it too: skip it, or every
            # rebuild dies on the same line of a log nobody may edit.
            if not isinstance(item, dict):
                continue
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
        """Which of these outages still need a detail fetch this run, most
        urgent first.

        Beyond skipping finalised outages, this backs off on ones that have gone
        quiet. ESB leaves planned works in the feed for weeks without ever
        touching them - in the first days of collection, nine such entries
        accounted for 71% of all detail fetches and produced not one change.

        Backing off is safe because the *list* is still fetched in full every
        run, and apply_list clears last_detail_utc the moment an outage's type
        changes. So a state transition is still caught within one poll; all that
        is delayed is a quiet outage's descriptive fields.

        The order matters when a run cannot finish, and it is by what a purge
        would take. ESB purges an outage a few hours after restoration and not
        before, so anything listed Restored that still needs a fetch is on a
        clock, whether it was never captured or has just flipped; a live
        outage never captured stays listed while it is out; a re-check loses
        at most a revision. In ESB's list order a storm run cut short by the
        service timeout re-fetched the same head of the list every run and
        never reached the tail (notes/storms.md).
        """
        if not outage_ids:
            return []
        # ESB listing an id twice would fetch it twice, and the two identical
        # observation lines would read as one copy (iter_raw).
        outage_ids = list(dict.fromkeys(outage_ids))
        now = now or utc_now_iso()
        placeholders = ",".join("?" * len(outage_ids))
        rows = self.conn.execute(
            f"""SELECT o.outage_id, o.outage_type, o.has_detail, o.is_final,
                       o.last_detail_utc,
                       COALESCE(MAX(c.observed_at_utc), o.first_seen_utc) AS last_change
                FROM outage o
                LEFT JOIN outage_change c ON c.outage_id = o.outage_id
                WHERE o.outage_id IN ({placeholders})
                GROUP BY o.outage_id""",
            outage_ids,
        ).fetchall()
        state = {r["outage_id"]: r for r in rows}

        def urgency(outage_id: str) -> int | None:
            row = state.get(outage_id)
            if row is None:
                return 2
            # apply_list has already written the list's type, so this is
            # whether the purge clock is running
            restored = row["outage_type"] == "Restored"
            if not row["has_detail"]:
                return 0 if restored else 2
            # Cleared by apply_list on a type change: something happened. A
            # captured record that has flipped to Restored loses only its
            # restore time to a purge, like the settling ones below.
            if row["last_detail_utc"] is None:
                return 1 if restored else 3
            if row["is_final"]:
                return None
            if restored:
                # Captured, but with no restore time yet. Still on the purge
                # clock, behind the rank above: a purge here costs one field,
                # there the whole record.
                return 1
            if _hours_between(row["last_change"], now) < quiet_after_hours:
                return 4  # actively changing, keep watching closely
            if _hours_between(row["last_detail_utc"], now) >= recheck_hours:
                return 5
            return None

        ranked = [
            (rank, index, oid)
            for index, oid in enumerate(outage_ids)
            if (rank := urgency(oid)) is not None
        ]
        return [oid for _, _, oid in sorted(ranked)]

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
        run_records, ends = [], {}
        for rec in self.iter_raw("runs"):
            if rec.get("event") == "end":
                ends[rec.get("run_id")] = rec
            else:
                run_records.append(rec)

        # An end line whose start line was lost still says how the run went,
        # and its run id carries the start time: it replays as a run with no
        # list, so its observations keep their place.
        starts = {rec["run_id"] for rec in run_records}
        lost_starts = 0
        for run_id in ends:
            started = str(run_id).rsplit("-", 1)[0]
            if run_id not in starts and _UTC_STAMP.fullmatch(started):
                run_records.append({"run_id": run_id, "started_at": started})
                lost_starts += 1
        # A start line promising an end line that never came is a run that
        # died, unless it is the newest: a backup can snapshot the log mid-run.
        newest = max((rec["started_at"] for rec in run_records), default=None)

        # Observations whose run record never made it to disk (a crash between
        # the two writes, or a damaged line) replay at their own place in time.
        # Replayed after everything else, an old body rolled back newer state.
        run_ids = {rec["run_id"] for rec in run_records}
        orphans = [
            (min(o.get("observed_at") or "" for o in records), records)
            for run_id, records in observations.items()
            if run_id not in run_ids
        ]
        # On a tie the orphan goes first: its run started no later than it.
        timeline = sorted(
            [(rec["started_at"], 1, rec, None) for rec in run_records]
            + [(at, 0, None, records) for at, records in orphans],
            key=lambda event: event[:2],
        )

        for _, _, rec, orphaned in timeline:
            if orphaned is not None:
                for obs in orphaned:
                    n_obs += apply_observation(obs)
                continue
            run_id = rec["run_id"]
            body = rec.get("list_body")
            items = body.get("outageMessage") if isinstance(body, dict) else None
            if isinstance(items, list):
                self.apply_list(rec["started_at"], items)

            # Reconstruct the run counters rather than leaving them null: they
            # are all derivable from the raw log, and they are what tells you
            # whether the dormancy back-off is working.
            run_obs = observations.get(run_id, [])
            fetched = sum(
                1 for o in run_obs
                if o.get("http_status") == 200 and isinstance(o.get("body"), dict)
            )
            purged = sum(1 for o in run_obs if o.get("http_status") == 404)
            errors = sum(
                1 for o in run_obs if o.get("http_status") not in (200, 404)
            )
            # as poll counts them: object items only, and a list call that
            # answered 200 with an unusable body still reached the feed
            if isinstance(items, list):
                listed = sum(isinstance(item, dict) for item in items)
            else:
                listed = 0 if rec.get("list_status") == 200 else None
            # Runs logged before the end record existed take the start line's
            # status and derived counters, which is all a rebuild ever had.
            end = ends.get(run_id, {})
            self.record_run(
                run_id=run_id,
                started_at_utc=rec["started_at"],
                finished_at_utc=end.get("finished_at"),
                status=end.get("status") or (
                    ("in_progress" if rec["started_at"] == newest else "unfinished")
                    if rec.get("ends_logged") else rec.get("status", "ok")
                ),
                exit_code=end.get("exit_code"),
                n_listed=listed,
                n_detail_fetched=fetched if listed is not None else None,
                n_detail_skipped=end["n_detail_skipped"] if "n_detail_skipped" in end else (
                    listed - fetched - purged - errors if listed is not None else None
                ),
                n_errors=end["n_errors"] if "n_errors" in end else errors,
                error_summary=end.get("error_summary"),
            )
            n_runs += 1
            for obs in run_obs:
                n_obs += apply_observation(obs)

        self.conn.commit()
        if verbose:
            print(f"replayed {n_runs} runs and {n_obs} detail observations")
            if lost_starts:
                print(f"  {lost_starts} run(s) had lost their start line; "
                      "recorded from their end line", file=sys.stderr)
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
        cut_short = c.execute(
            "SELECT COUNT(*) n FROM run WHERE status = 'cut_short'"
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
            "cut_short": cut_short["n"] or 0,
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
                staged = Path(str(target) + ".tmp")
                with staged.open("wb") as out:
                    # A month written to after it was compacted - a Pi with no
                    # clock battery boots in the past until NTP syncs - keeps
                    # its archive and gains the late lines as a further gzip
                    # member, which every gzip reader concatenates.
                    if target.exists():
                        with target.open("rb") as archived:
                            shutil.copyfileobj(archived, out)
                    with path.open("rb") as src, gzip.GzipFile(fileobj=out, mode="wb") as dst:
                        if target.exists():
                            # the archive may end in a torn line; a blank one is skipped
                            dst.write(b"\n")
                        shutil.copyfileobj(src, dst)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(staged, target)
                _fsync_dir(self.raw_dir)
                # A crash before this unlink compacts the same lines again next
                # time; iter_raw drops the repeats.
                path.unlink()
                _fsync_dir(self.raw_dir)
                compacted.append(target.name)
        return sorted(compacted)
