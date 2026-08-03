import tempfile
import unittest
from pathlib import Path

from esb_outages.parse import normalize_detail
from esb_outages.store import Store

from .helpers import detail, make_list


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.store = Store(self.data_dir).open()

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def row(self, outage_id):
        return self.store.conn.execute(
            "SELECT * FROM outage WHERE outage_id = ?", (outage_id,)
        ).fetchone()

    def changes(self, outage_id=None):
        if outage_id:
            return self.store.conn.execute(
                "SELECT * FROM outage_change WHERE outage_id = ? ORDER BY id",
                (outage_id,),
            ).fetchall()
        return self.store.conn.execute(
            "SELECT * FROM outage_change ORDER BY id"
        ).fetchall()


class TestApplyList(StoreTestCase):
    def test_creates_stub_with_coordinates(self):
        # The stub is the only record we keep if the outage is purged before its
        # detail call succeeds, so the list's own coordinates matter.
        self.store.apply_list("2026-07-31T10:00:00Z", make_list(detail("fault"))["outageMessage"])
        row = self.row(detail("fault")["outageId"])
        self.assertEqual(row["outage_type"], "Fault")
        self.assertIsNotNone(row["lat"])
        self.assertEqual(row["has_detail"], 0)
        self.assertEqual(row["first_seen_utc"], "2026-07-31T10:00:00Z")

    def test_repeat_sighting_advances_last_seen_only(self):
        items = make_list(detail("fault"))["outageMessage"]
        self.store.apply_list("2026-07-31T10:00:00Z", items)
        self.store.apply_list("2026-07-31T11:00:00Z", items)
        row = self.row(detail("fault")["outageId"])
        self.assertEqual(row["first_seen_utc"], "2026-07-31T10:00:00Z")
        self.assertEqual(row["last_seen_utc"], "2026-07-31T11:00:00Z")
        self.assertEqual(self.changes(), [])

    def test_type_change_in_list_is_recorded(self):
        fault = detail("fault")
        self.store.apply_list("2026-07-31T10:00:00Z", make_list(fault)["outageMessage"])
        restored = dict(fault, outageType="Restored")
        self.store.apply_list("2026-07-31T11:00:00Z", make_list(restored)["outageMessage"])
        rows = self.changes(fault["outageId"])
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["field"], rows[0]["old_value"], rows[0]["new_value"]),
                         ("outage_type", "Fault", "Restored"))

    def test_type_change_unfinalises_a_frozen_outage(self):
        # Safety net for an outage that re-opens, or an ID that ESB recycles.
        restored = detail("restored")
        self.store.apply_list("2026-07-31T10:00:00Z", make_list(restored)["outageMessage"])
        self.store.apply_detail("2026-07-31T10:00:01Z", normalize_detail(restored))
        self.assertEqual(self.row(restored["outageId"])["is_final"], 1)

        refaulted = dict(restored, outageType="Fault")
        self.store.apply_list("2026-07-31T11:00:00Z", make_list(refaulted)["outageMessage"])
        self.assertEqual(self.row(restored["outageId"])["is_final"], 0)


class TestIdsNeedingDetail(StoreTestCase):
    def test_skips_only_finalised_outages(self):
        restored, fault = detail("restored"), detail("fault")
        items = make_list(restored, fault)["outageMessage"]
        self.store.apply_list("2026-07-31T10:00:00Z", items)
        ids = [restored["outageId"], fault["outageId"]]

        self.assertEqual(set(self.store.ids_needing_detail(ids)), set(ids))

        self.store.apply_detail("2026-07-31T10:00:01Z", normalize_detail(restored))
        self.store.apply_detail("2026-07-31T10:00:02Z", normalize_detail(fault))
        # Restored is immutable; the ongoing fault still needs watching.
        self.assertEqual(self.store.ids_needing_detail(ids), [fault["outageId"]])

    def test_handles_empty_input(self):
        self.assertEqual(self.store.ids_needing_detail([]), [])


class TestDormancyBackoff(StoreTestCase):
    """ESB leaves planned works in the feed for weeks without touching them."""

    def setUp(self):
        super().setUp()
        self.planned = detail("planned")
        self.oid = self.planned["outageId"]
        self.store.apply_list("2026-07-01T00:00:00Z", make_list(self.planned)["outageMessage"])
        self.store.apply_detail("2026-07-01T00:00:00Z", normalize_detail(self.planned))

    def needed(self, now):
        return self.store.ids_needing_detail([self.oid], now=now)

    def test_recently_changed_outage_is_always_fetched(self):
        self.assertEqual(self.needed("2026-07-01T03:00:00Z"), [self.oid])

    def test_dormant_outage_is_skipped(self):
        # Quiet for 8h and checked 8h ago... but recheck is due, so it fetches.
        # At 7h quiet with a 7h-old check it is also due; use a case where the
        # last check is recent to prove the skip.
        self.store.conn.execute(
            "UPDATE outage SET last_detail_utc = ? WHERE outage_id = ?",
            ("2026-07-01T20:00:00Z", self.oid),
        )
        self.assertEqual(self.needed("2026-07-01T22:00:00Z"), [])

    def test_dormant_outage_is_rechecked_periodically(self):
        self.store.conn.execute(
            "UPDATE outage SET last_detail_utc = ? WHERE outage_id = ?",
            ("2026-07-01T00:00:00Z", self.oid),
        )
        self.assertEqual(self.needed("2026-07-01T07:00:00Z"), [self.oid])

    def test_a_type_change_defeats_the_backoff_immediately(self):
        # The safety property: however long an outage has been dormant, a state
        # transition seen in the list forces a detail fetch on that same run.
        self.store.conn.execute(
            "UPDATE outage SET last_detail_utc = ? WHERE outage_id = ?",
            ("2026-07-05T00:00:00Z", self.oid),
        )
        self.assertEqual(self.needed("2026-07-05T01:00:00Z"), [])

        faulted = dict(self.planned, outageType="Fault")
        self.store.apply_list("2026-07-05T01:00:00Z", make_list(faulted)["outageMessage"])
        self.assertEqual(self.needed("2026-07-05T01:00:00Z"), [self.oid])

    def test_finalised_outages_stay_skipped(self):
        restored = detail("restored")
        self.store.apply_list("2026-07-01T00:00:00Z", make_list(restored)["outageMessage"])
        self.store.apply_detail("2026-07-01T00:00:00Z", normalize_detail(restored))
        self.assertEqual(
            self.store.ids_needing_detail([restored["outageId"]], now="2026-08-01T00:00:00Z"),
            [],
        )


class TestApplyDetail(StoreTestCase):
    def test_filling_a_stub_is_not_recorded_as_change(self):
        fault = detail("fault")
        self.store.apply_list("2026-07-31T10:00:00Z", make_list(fault)["outageMessage"])
        self.store.apply_detail("2026-07-31T10:00:01Z", normalize_detail(fault))
        self.assertEqual(self.changes(), [])
        self.assertEqual(self.row(fault["outageId"])["has_detail"], 1)

    def test_estimate_revision_is_recorded(self):
        # The headline use of the change log: watching ESB's ETA move.
        fault = detail("fault")
        self.store.apply_list("2026-07-31T10:00:00Z", make_list(fault)["outageMessage"])
        self.store.apply_detail("2026-07-31T10:00:01Z", normalize_detail(fault))

        revised = dict(fault, estRestoreTime="31/07/2026 22:00")
        self.store.apply_detail("2026-07-31T11:00:00Z", normalize_detail(revised))

        rows = self.changes(fault["outageId"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["field"], "est_restore_time_utc")
        self.assertEqual(rows[0]["new_value"], "2026-07-31T21:00:00Z")
        self.assertEqual(rows[0]["source"], "detail")

    def test_detail_without_prior_list_still_stores(self):
        fault = detail("fault")
        self.store.apply_detail("2026-07-31T10:00:00Z", normalize_detail(fault))
        row = self.row(fault["outageId"])
        self.assertEqual(row["has_detail"], 1)
        self.assertEqual(row["first_seen_utc"], "2026-07-31T10:00:00Z")

    def test_unchanged_repeat_records_nothing(self):
        fault = detail("fault")
        self.store.apply_detail("2026-07-31T10:00:00Z", normalize_detail(fault))
        self.store.apply_detail("2026-07-31T11:00:00Z", normalize_detail(fault))
        self.assertEqual(self.changes(), [])


class TestRawLogAndCompaction(StoreTestCase):
    def test_raw_files_are_split_by_month(self):
        self.store.write_run_raw("r1", "2026-07-31T10:00:00Z", 200, {"outageMessage": []})
        self.store.write_run_raw("r2", "2026-08-01T10:00:00Z", 200, {"outageMessage": []})
        names = {p.name for p in self.store.raw_files("runs")}
        self.assertEqual(names, {"runs-2026-07.jsonl", "runs-2026-08.jsonl"})

    def test_compact_gzips_old_months_and_keeps_current(self):
        from esb_outages.store import utc_now_iso

        current_month = utc_now_iso()[:7]
        self.store.write_run_raw("old", "2020-01-15T10:00:00Z", 200, {"outageMessage": []})
        self.store.write_run_raw("now", utc_now_iso(), 200, {"outageMessage": []})

        compacted = self.store.compact()
        self.assertEqual(compacted, ["runs-2020-01.jsonl.gz"])
        remaining = {p.name for p in self.store.raw_files("runs")}
        self.assertIn(f"runs-{current_month}.jsonl", remaining)
        self.assertIn("runs-2020-01.jsonl.gz", remaining)

    def test_gzipped_logs_are_still_readable(self):
        self.store.write_run_raw("old", "2020-01-15T10:00:00Z", 200, {"outageMessage": []})
        self.store.compact()
        records = list(self.store.iter_raw("runs"))
        self.assertEqual([r["run_id"] for r in records], ["old"])


if __name__ == "__main__":
    unittest.main()
