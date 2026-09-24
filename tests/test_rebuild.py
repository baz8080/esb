"""The integrity guarantee: SQLite is disposable, the raw log is not.

If these tests pass, a parsing bug found months from now can be fixed and the
entire history re-derived. If they ever fail, the project has silently become
dependent on state that only exists inside a database file.
"""

import json
import tempfile
import unittest
from pathlib import Path

from esb_outages.poll import run_poll
from esb_outages.store import Store

from .helpers import FakeClient, detail, make_list


class TestRebuild(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def poll(self, client):
        return run_poll(self.data_dir, client=client, delay_ms=0)

    def run_a_realistic_history(self):
        """Three runs covering the interesting transitions."""
        fault, planned, restored = detail("fault"), detail("planned"), detail("restored")

        # Run 1: a live fault and a planned outage.
        self.poll(FakeClient(
            list_body=make_list(fault, planned),
            details={fault["outageId"]: fault, planned["outageId"]: planned},
        ))

        # Run 2: the fault's estimate slips, and a new outage appears that is
        # purged before we can fetch its detail.
        revised = dict(fault, estRestoreTime="31/07/2026 23:45",
                       statusMessage="Crews are on site.")
        self.poll(FakeClient(
            list_body=make_list(revised, planned, restored,
                                extra=[{"i": "9999999", "t": "Fault",
                                        "p": {"c": "53.0,-7.0"}}]),
            details={revised["outageId"]: revised, planned["outageId"]: planned,
                     restored["outageId"]: restored},
        ))

        # Run 3: the fault is restored and becomes immutable.
        done = dict(revised, outageType="Restored", restoreTime="31/07/2026 23:30")
        self.poll(FakeClient(
            list_body=make_list(done, planned, restored),
            details={done["outageId"]: done, planned["outageId"]: planned,
                     restored["outageId"]: restored},
        ))

    def test_rebuild_reproduces_the_database_exactly(self):
        self.run_a_realistic_history()

        with Store(self.data_dir) as st:
            before = st.snapshot()
            self.assertTrue(before, "history should not be empty")

        with Store(self.data_dir) as st:
            st.rebuild()
            after = st.snapshot()

        self.assertEqual(before, after)

    def test_rebuild_is_idempotent(self):
        self.run_a_realistic_history()
        with Store(self.data_dir) as st:
            st.rebuild()
            once = st.snapshot()
            st.rebuild()
            twice = st.snapshot()
        self.assertEqual(once, twice)

    def test_rebuild_from_a_deleted_database(self):
        self.run_a_realistic_history()
        with Store(self.data_dir) as st:
            before = st.snapshot()

        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(self.data_dir / "esb.db") + suffix)
            if candidate.exists():
                candidate.unlink()

        with Store(self.data_dir) as st:
            st.rebuild()
            self.assertEqual(st.snapshot(), before)

    def test_change_history_survives_the_round_trip(self):
        self.run_a_realistic_history()
        with Store(self.data_dir) as st:
            fields_before = [
                r["field"] for r in st.conn.execute(
                    "SELECT field FROM outage_change ORDER BY id"
                )
            ]
            st.rebuild()
            fields_after = [
                r["field"] for r in st.conn.execute(
                    "SELECT field FROM outage_change ORDER BY id"
                )
            ]
        self.assertIn("est_restore_time_utc", fields_before)
        self.assertEqual(fields_before, fields_after)

    def test_merged_logs_from_two_hosts_replay_in_time_order(self):
        """Migration case: concatenated logs must replay chronologically.

        Two collectors running in parallel produce interleaved runs. Appending
        one host's log to the other's puts them out of order on disk, so replay
        has to sort rather than trust file order.
        """
        fault = detail("fault")
        raw = self.data_dir / "raw"

        def write(run_id, started_at, outage_type):
            body = dict(fault, outageType=outage_type)
            with (raw / "runs-2026-07.jsonl").open("a") as fh:
                fh.write(json.dumps({
                    "run_id": run_id, "started_at": started_at,
                    "list_status": 200, "list_body": make_list(body),
                }, sort_keys=True) + "\n")
            with (raw / "observations-2026-07.jsonl").open("a") as fh:
                fh.write(json.dumps({
                    "run_id": run_id, "observed_at": started_at,
                    "outage_id": body["outageId"], "http_status": 200, "body": body,
                }, sort_keys=True) + "\n")

        raw.mkdir(parents=True, exist_ok=True)
        # Host A's runs appended first, then host B's - interleaved in time.
        write("2026-07-31T10:00:00Z-aaaa", "2026-07-31T10:00:00Z", "Fault")
        write("2026-07-31T12:00:00Z-aaaa", "2026-07-31T12:00:00Z", "Restored")
        write("2026-07-31T11:00:00Z-bbbb", "2026-07-31T11:00:00Z", "Fault")

        with Store(self.data_dir) as st:
            st.rebuild()
            row = st.conn.execute("SELECT * FROM outage").fetchone()
            # The 12:00 run is last in time, so its state must win despite the
            # 11:00 record sitting after it in the file.
            self.assertEqual(row["outage_type"], "Restored")
            self.assertEqual(row["first_seen_utc"], "2026-07-31T10:00:00Z")
            self.assertEqual(row["last_seen_utc"], "2026-07-31T12:00:00Z")

    def test_a_truncated_final_line_does_not_destroy_the_history(self):
        """A power cut mid-append, or a backup snapshotting mid-write.

        Losing the last observation is acceptable. Losing everything before it,
        because one line will not parse, is not.
        """
        self.run_a_realistic_history()
        with Store(self.data_dir) as st:
            before = st.snapshot()

        obs_file = self.data_dir / "raw" / "observations-2026-07.jsonl"
        with obs_file.open("a") as fh:
            fh.write('{"run_id": "x", "observed_at": "2026-07-31T23:59:5')

        with Store(self.data_dir) as st:
            result = st.rebuild()
            self.assertEqual(result["malformed"], 1)
            self.assertEqual(st.snapshot(), before)

    def test_run_counters_survive_a_rebuild(self):
        """They are derivable from the raw log, so a rebuild must restore them.

        Without this, `stats` after a rebuild cannot show whether the dormancy
        back-off is working - the counters it reads are all null.
        """
        self.run_a_realistic_history()
        with Store(self.data_dir) as st:
            before = [
                dict(r) for r in st.conn.execute(
                    "SELECT run_id, n_listed, n_detail_fetched, n_detail_skipped"
                    " FROM run ORDER BY started_at_utc"
                )
            ]
            st.rebuild()
            after = [
                dict(r) for r in st.conn.execute(
                    "SELECT run_id, n_listed, n_detail_fetched, n_detail_skipped"
                    " FROM run ORDER BY started_at_utc"
                )
            ]
        self.assertEqual(before, after)
        self.assertTrue(all(r["n_listed"] for r in after))

    def test_a_failed_run_is_not_lost_by_a_rebuild(self):
        from esb_outages.client import AuthError
        from esb_outages.poll import run_poll
        from tests.helpers import FakeClient

        self.poll(FakeClient(list_body=make_list(detail("fault")),
                             details={detail("fault")["outageId"]: detail("fault")}))
        run_poll(self.data_dir, client=FakeClient(list_error=AuthError("401")), delay_ms=0)

        with Store(self.data_dir) as st:
            st.rebuild()
            statuses = [r[0] for r in st.conn.execute("SELECT status FROM run")]
        self.assertIn("auth_error", statuses)

    def test_every_run_column_survives_a_rebuild(self):
        """How a run ended is not derivable from its list and observations, so
        the log carries it; without that a storm's cut-short runs came back ok."""
        from esb_outages.client import AuthError, TransientError

        self.run_a_realistic_history()
        many = [dict(detail("fault"), outageId=str(3000000 + i)) for i in range(4)]
        by_id = {d["outageId"]: d for d in many}
        run_poll(self.data_dir, client=FakeClient(list_body=make_list(*many),
                 details=by_id), delay_ms=0, budget_s=0)
        more = [dict(detail("fault"), outageId=str(4000000 + i)) for i in range(4)]
        self.poll(FakeClient(
            list_body=make_list(*more),
            details={d["outageId"]: d for d in more},
            detail_errors={d["outageId"]: TransientError("503") for d in more[:3]},
        ))
        last = dict(detail("fault"), outageId="5000000")
        self.poll(FakeClient(list_body=make_list(last), details={},
                             detail_errors={"5000000": AuthError("401")}))
        self.poll(FakeClient(list_error=AuthError("401")))

        def runs(st):
            return [tuple(r) for r in st.conn.execute(
                "SELECT * FROM run ORDER BY started_at_utc, run_id")]

        with Store(self.data_dir) as st:
            before = runs(st)
            st.rebuild()
            after = runs(st)
        statuses = {r[3] for r in before}
        self.assertTrue({"cut_short", "partial", "auth_error"} <= statuses, statuses)
        self.assertEqual(before, after)

    def test_rebuild_and_compact_wait_for_a_running_poll(self):
        from esb_outages.__main__ import main
        from esb_outages.poll import poll_lock

        self.run_a_realistic_history()
        db = self.data_dir / "esb.db"
        inode = db.stat().st_ino
        with poll_lock(self.data_dir) as held:
            self.assertTrue(held)
            for command in ("rebuild", "compact"):
                self.assertEqual(main(["--data-dir", str(self.data_dir), command]), 1)
        self.assertEqual(db.stat().st_ino, inode)

    def test_a_malformed_response_neither_kills_the_run_nor_the_rebuild(self):
        from esb_outages import alert

        fault = detail("fault")
        listed = make_list(fault)
        listed["outageMessage"].insert(0, "not an object")
        code = self.poll(FakeClient(list_body=listed, details={fault["outageId"]: None}))
        self.assertEqual(code, alert.EXIT_SCHEMA_DRIFT)
        self.assertEqual(self.poll(FakeClient(list_body=[])), alert.EXIT_SCHEMA_DRIFT)
        with Store(self.data_dir) as st:
            before = st.snapshot()
            st.rebuild()
            self.assertEqual(st.snapshot(), before)
            self.assertEqual(
                [r[0] for r in st.conn.execute("SELECT outage_id FROM outage")],
                [fault["outageId"]],
            )

    def test_rebuild_on_empty_data_dir_is_harmless(self):
        with Store(self.data_dir) as st:
            self.assertEqual(
                st.rebuild(), {"runs": 0, "observations": 0, "malformed": 0}
            )
            self.assertEqual(st.snapshot(), [])

    def test_rebuild_reads_compacted_logs(self):
        self.run_a_realistic_history()
        with Store(self.data_dir) as st:
            before = st.snapshot()
        # Force every log into the compacted state, then rebuild from gzip only.
        import gzip
        for path in list((self.data_dir / "raw").glob("*.jsonl")):
            with path.open("rb") as src, gzip.open(str(path) + ".gz", "wb") as dst:
                dst.write(src.read())
            path.unlink()
        with Store(self.data_dir) as st:
            st.rebuild()
            self.assertEqual(st.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
