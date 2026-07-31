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
from datetime import datetime, timezone
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

    # ---- lifecycle -------------------------------------------------------

    def open(self) -> "Store":
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

    def __enter__(self) -> "Store":
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
        self, run_id: str, started_at: str, list_status: int, list_body
    ) -> None:
        """Record the list response verbatim, before any detail fetching starts."""
        self._append_raw(
            "runs",
            _month_of(started_at),
            {
                "run_id": run_id,
                "started_at": started_at,
                "list_status": list_status,
                "list_body": list_body,
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
        for path in self.raw_files(kind):
            with _open_maybe_gzip(path) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        yield json.loads(line)

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
                # Safety net: an outage we had marked immutable has changed state
                # (ESB re-opened it, or recycled the ID). Un-finalise so the next
                # step re-fetches its detail rather than trusting stale data.
                self.conn.execute(
                    "UPDATE outage SET outage_type = ?, last_seen_utc = ?, is_final = 0"
                    " WHERE outage_id = ?",
                    (list_type, observed_at, outage_id),
                )
            else:
                self.conn.execute(
                    "UPDATE outage SET last_seen_utc = ? WHERE outage_id = ?",
                    (observed_at, outage_id),
                )

    def ids_needing_detail(self, outage_ids: list[str]) -> list[str]:
        """Which of these outages still need a detail fetch this run."""
        if not outage_ids:
            return []
        placeholders = ",".join("?" * len(outage_ids))
        rows = self.conn.execute(
            f"SELECT outage_id FROM outage WHERE outage_id IN ({placeholders})"
            "  AND has_detail = 1 AND is_final = 1",
            outage_ids,
        ).fetchall()
        done = {r["outage_id"] for r in rows}
        return [oid for oid in outage_ids if oid not in done]

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

        seen_run_ids = set()
        for rec in self.iter_raw("runs"):
            run_id = rec["run_id"]
            seen_run_ids.add(run_id)
            body = rec.get("list_body")
            if isinstance(body, dict) and isinstance(body.get("outageMessage"), list):
                self.apply_list(rec["started_at"], body["outageMessage"])
            self.record_run(
                run_id=run_id,
                started_at_utc=rec["started_at"],
                status="rebuilt",
            )
            n_runs += 1
            for obs in observations.get(run_id, []):
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
        return {"runs": n_runs, "observations": n_obs}

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
