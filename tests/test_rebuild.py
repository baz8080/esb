"""The integrity guarantee: SQLite is disposable, the raw log is not.

If these tests pass, a parsing bug found months from now can be fixed and the
entire history re-derived. If they ever fail, the project has silently become
dependent on state that only exists inside a database file.
"""

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

    def test_rebuild_on_empty_data_dir_is_harmless(self):
        with Store(self.data_dir) as st:
            self.assertEqual(st.rebuild(), {"runs": 0, "observations": 0})
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
