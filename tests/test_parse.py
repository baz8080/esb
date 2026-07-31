import unittest

from esb_outages.parse import (
    check_detail_schema,
    check_list_schema,
    normalize_detail,
    parse_esb_datetime,
    parse_point,
)

from .helpers import detail, load


class TestDatetime(unittest.TestCase):
    def test_summer_time_is_utc_plus_one(self):
        # This is the observation that proved the API reports local time:
        # 13:41 IST == 12:41 UTC.
        self.assertEqual(
            parse_esb_datetime("31/07/2026 13:41"), ("2026-07-31T12:41:00Z", False)
        )

    def test_winter_time_is_utc(self):
        self.assertEqual(
            parse_esb_datetime("15/01/2026 12:00"), ("2026-01-15T12:00:00Z", False)
        )

    def test_day_month_order_is_not_month_day(self):
        # 03/04 must be 3 April, not 4 March - the single most damaging
        # misreading possible for this dataset.
        self.assertEqual(
            parse_esb_datetime("03/04/2026 09:00"), ("2026-04-03T08:00:00Z", False)
        )

    def test_dst_fall_back_is_flagged_ambiguous(self):
        # 25 Oct 2026: 02:00 IST -> 01:00 GMT, so 01:30 happens twice.
        utc, ambiguous = parse_esb_datetime("25/10/2026 01:30")
        self.assertTrue(ambiguous)
        self.assertEqual(utc, "2026-10-25T00:30:00Z")  # first occurrence (fold=0)

    def test_dst_spring_forward_is_flagged(self):
        # 29 Mar 2026: 01:00 GMT -> 02:00 IST, so 01:30 never occurs.
        _, ambiguous = parse_esb_datetime("29/03/2026 01:30")
        self.assertTrue(ambiguous)

    def test_times_either_side_of_a_transition_are_not_flagged(self):
        for value in ("25/10/2026 00:30", "25/10/2026 03:30", "29/03/2026 04:00"):
            with self.subTest(value=value):
                self.assertFalse(parse_esb_datetime(value)[1])

    def test_empty_and_malformed_yield_none(self):
        for value in ("", "   ", None, "not a date", "31/02/2026 10:00"):
            with self.subTest(value=value):
                self.assertEqual(parse_esb_datetime(value), (None, False))


class TestPoint(unittest.TestCase):
    def test_parses_lat_lon(self):
        lat, lon, raw = parse_point({"c": "52.399424975954,-8.854789413876"})
        self.assertAlmostEqual(lat, 52.399424975954)
        self.assertAlmostEqual(lon, -8.854789413876)
        self.assertEqual(raw, "52.399424975954,-8.854789413876")

    def test_tolerates_junk(self):
        self.assertEqual(parse_point(None), (None, None, None))
        self.assertEqual(parse_point({}), (None, None, None))
        self.assertEqual(parse_point({"c": "abc,def"}), (None, None, "abc,def"))


class TestSchemaChecks(unittest.TestCase):
    def test_real_fixtures_have_no_drift(self):
        for kind in ("restored", "planned", "fault"):
            with self.subTest(kind=kind):
                self.assertEqual(check_detail_schema(detail(kind)), [])
        self.assertEqual(check_list_schema(load("list_ok")), [])

    def test_detects_added_and_removed_fields(self):
        body = dict(detail("fault"))
        body["newThing"] = 1
        del body["location"]
        problems = check_detail_schema(body)
        self.assertTrue(any("newThing" in p for p in problems))
        self.assertTrue(any("location" in p for p in problems))

    def test_detects_missing_outage_message(self):
        self.assertEqual(
            check_list_schema({"somethingElse": []}),
            ["response has no 'outageMessage' key"],
        )

    def test_detects_changed_list_item_shape(self):
        problems = check_list_schema({"outageMessage": [{"i": "1", "t": "Fault"}]})
        self.assertTrue(any("missing list field" in p for p in problems))


class TestNormalize(unittest.TestCase):
    def test_restored_outage_is_final(self):
        n = normalize_detail(detail("restored"))
        self.assertEqual(n["outage_type"], "Restored")
        self.assertEqual(n["is_final"], 1)
        self.assertIsNotNone(n["restore_time_utc"])

    def test_active_outages_are_not_final(self):
        for kind in ("fault", "planned"):
            with self.subTest(kind=kind):
                self.assertEqual(normalize_detail(detail(kind))["is_final"], 0)

    def test_restored_without_restore_time_is_not_final(self):
        # Still settling: must be re-fetched rather than frozen.
        body = dict(detail("restored"))
        body["restoreTime"] = ""
        self.assertEqual(normalize_detail(body)["is_final"], 0)

    def test_empty_strings_become_null(self):
        n = normalize_detail(detail("restored"))
        self.assertIsNone(n["status_message"])
        self.assertIsNone(n["planned_outage_reason"])

    def test_planned_reason_is_kept(self):
        n = normalize_detail(detail("planned"))
        self.assertEqual(n["planned_outage_reason"], "CONNECT NEW CUSTOMERS")

    def test_raw_strings_are_always_preserved(self):
        n = normalize_detail(detail("fault"))
        self.assertEqual(n["start_time_raw"], detail("fault")["startTime"])

    def test_survives_a_completely_unexpected_payload(self):
        # Never raise: a parse failure must not cost us the run or the raw log.
        n = normalize_detail({"outageId": "1"})
        self.assertEqual(n["outage_id"], "1")
        self.assertIsNone(n["start_time_utc"])


if __name__ == "__main__":
    unittest.main()
