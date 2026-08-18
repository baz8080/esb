"""Unit tests for the site's arithmetic, on synthetic outages.

These build a database the same way a real run does - through Store.apply_* -
so the timeline reconstruction is exercised against the change log the collector
actually writes rather than against a hand-made fixture.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from esb_outages.parse import normalize_detail
from esb_outages.store import Store
from esb_site import model

NOW = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def detail(outage_id, **over):
    """A detail body shaped exactly like ESB's, in Dublin local time."""
    body = {
        "outageId": outage_id,
        "outageType": "Fault",
        "point": {"c": "53.36858,-6.27098"},  # Glasnevin, Dublin
        "location": "Glasnevin",
        "plannerGroup": "Dublin Central",
        "numCustAffected": 100,
        "startTime": "10/08/2026 09:00",
        "estRestoreTime": "10/08/2026 13:00",
        "statusMessage": "",
        "restoreTime": "",
        "plannedOutageReason": "",
    }
    body.update(over)
    return body


class SiteModelCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.store = Store(self.dir).open()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self.store.close)

    def observe(self, body, at):
        """Apply one list+detail observation, as a poll run would."""
        item = {"i": body["outageId"], "t": body["outageType"], "p": body["point"]}
        self.store.apply_list(iso(at), [item])
        self.store.apply_detail(iso(at), normalize_detail(body))

    def load(self, now=NOW):
        self.store.conn.commit()
        index = model.SmallAreaIndex.load()
        outages, unplaced = model.load_outages(self.store.db_path, index, now)
        return outages, unplaced, index


class TestGrade(unittest.TestCase):
    def test_a_is_esbs_own_published_aim(self):
        """95% inside 4 hours, from the CRU-approved Customer Charter."""
        self.assertEqual(model.CHARTER_TARGET_SHARE, 95.0)
        self.assertEqual(model.CHARTER_TARGET_HOURS, 4.0)
        self.assertEqual(model.grade(95.0), "A")
        self.assertEqual(model.grade(94.9), "B")

    def test_bands(self):
        self.assertEqual(model.grade(100.0), "A")
        self.assertEqual(model.grade(90.0), "B")
        self.assertEqual(model.grade(89.9), "C")
        self.assertEqual(model.grade(80.0), "C")
        self.assertEqual(model.grade(79.9), "D")
        self.assertEqual(model.grade(70.0), "D")
        self.assertEqual(model.grade(69.9), "F")
        self.assertEqual(model.grade(0.0), "F")

    def test_nothing_to_judge_means_no_grade(self):
        self.assertIsNone(model.grade(None))


class TestDayBuckets(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(model.day_bucket(0.0, False), 0)
        self.assertEqual(model.day_bucket(0.049, False), 0)
        self.assertEqual(model.day_bucket(0.05, False), 1)
        self.assertEqual(model.day_bucket(0.29, False), 1)
        self.assertEqual(model.day_bucket(0.3, False), 2)
        self.assertEqual(model.day_bucket(0.99, False), 2)
        self.assertEqual(model.day_bucket(1.0, False), 3)
        self.assertEqual(model.day_bucket(2.99, False), 3)
        self.assertEqual(model.day_bucket(3.0, False), model.DAY_SEVERE)

    def test_planned_shows_only_when_faults_are_negligible(self):
        self.assertEqual(model.day_bucket(0.0, True), model.DAY_PLANNED)
        self.assertEqual(model.day_bucket(0.01, True), model.DAY_PLANNED)
        # A real fault outranks planned works; the day is not "maintenance".
        self.assertEqual(model.day_bucket(0.5, True), 2)


class TestPlacement(SiteModelCase):
    def test_coordinates_resolve_to_a_county_and_town(self):
        self.observe(detail("1"), datetime(2026, 8, 10, 10, tzinfo=timezone.utc))
        outages, unplaced, _ = self.load()
        self.assertEqual(unplaced, 0)
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0].county, "Dublin")

    def test_a_point_off_the_island_is_not_placed(self):
        self.observe(
            detail("1", point={"c": "48.85,2.35"}),  # Paris
            datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        )
        outages, unplaced, _ = self.load()
        self.assertEqual((len(outages), unplaced), (0, 1))

    def test_every_county_has_customers_apportioned(self):
        index = model.SmallAreaIndex.load()
        self.assertEqual(len(index.counties), 26)
        self.assertAlmostEqual(sum(index.customers.values()), model.NATIONAL_CUSTOMERS, places=3)


class TestClassification(SiteModelCase):
    def test_restored_does_not_erase_that_it_was_a_fault(self):
        t = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        self.observe(detail("1"), t)
        self.observe(
            detail("1", outageType="Restored", restoreTime="10/08/2026 12:30"),
            t + timedelta(minutes=30),
        )
        outages, _, _ = self.load()
        self.assertFalse(outages[0].planned)
        self.assertEqual(outages[0].end_src, "restored")

    def test_planned_stays_planned_and_never_reports_a_restore(self):
        t = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        self.observe(detail("1", outageType="Planned"), t)
        outages, _, _ = self.load()
        self.assertTrue(outages[0].planned)
        self.assertNotEqual(outages[0].end_src, "restored")


class TestEndTime(SiteModelCase):
    def test_real_restore_time_wins(self):
        t = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        self.observe(
            detail("1", outageType="Restored", restoreTime="10/08/2026 11:45"), t
        )
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "restored")
        self.assertTrue(o.end_known)
        # 11:45 Dublin in August is 10:45 UTC.
        self.assertEqual(o.end, datetime(2026, 8, 10, 10, 45, tzinfo=timezone.utc))

    def test_estimate_is_used_when_it_precedes_the_last_sighting(self):
        # Seen at 09:30 and 14:00 UTC, estimated back at 13:00 Dublin = 12:00 UTC.
        self.observe(detail("1"), datetime(2026, 8, 10, 9, 30, tzinfo=timezone.utc))
        self.observe(detail("1"), datetime(2026, 8, 10, 14, 0, tzinfo=timezone.utc))
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "estimated")
        self.assertEqual(o.end, datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc))

    def test_last_sighting_wins_when_it_precedes_the_estimate(self):
        # Dropped out of the feed at 09:30 UTC, long before its 12:00 estimate.
        self.observe(detail("1"), datetime(2026, 8, 10, 9, 30, tzinfo=timezone.utc))
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "listed")
        self.assertEqual(o.end, datetime(2026, 8, 10, 9, 30, tzinfo=timezone.utc))

    def test_an_estimate_before_the_start_is_not_an_estimate(self):
        """Falling back rather than clamping: clamping made the outage zero-length."""
        self.observe(
            detail("1", startTime="10/08/2026 09:00", estRestoreTime="10/08/2026 08:00"),
            datetime(2026, 8, 10, 9, 30, tzinfo=timezone.utc),
        )
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "listed")
        self.assertGreaterEqual(o.end, o.start)
        self.assertEqual(o.minutes, 90.0)


class TestUpdates(SiteModelCase):
    def test_an_outage_that_never_changes_has_one_update(self):
        t = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        for i in range(5):
            self.observe(detail("1"), t + timedelta(minutes=30 * i))
        outages, _, _ = self.load()
        self.assertEqual(len(outages[0].updates), 1)

    def test_one_poll_cycle_is_one_update(self):
        """A list change and a detail change seconds apart are the same event.

        Without coalescing, every Fault -> Restored transition would read as two
        updates a few seconds apart, which inflated the count on a third of all
        outages.
        """
        t = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        self.observe(detail("1"), t)
        body = detail("1", outageType="Restored", restoreTime="10/08/2026 12:30")
        item = {"i": "1", "t": "Restored", "p": body["point"]}
        later = t + timedelta(minutes=30)
        self.store.apply_list(iso(later), [item])
        self.store.apply_detail(iso(later + timedelta(seconds=4)), normalize_detail(body))
        outages, _, _ = self.load()
        self.assertEqual(len(outages[0].updates), 2)

    def test_customer_count_changes_are_updates(self):
        t = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        for i, n in enumerate((100, 80, 40)):
            self.observe(detail("1", numCustAffected=n), t + timedelta(minutes=30 * i))
        outages, _, _ = self.load()
        self.assertEqual([u.customers for u in outages[0].updates], [100, 80, 40])

    def test_status_message_noise_is_not_an_update(self):
        """statusMessage has five distinct values and unstable whitespace."""
        t = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        self.observe(detail("1", statusMessage="We apologise."), t)
        self.observe(
            detail("1", statusMessage="We  apologise."), t + timedelta(minutes=30)
        )
        outages, _, _ = self.load()
        self.assertEqual(len(outages[0].updates), 1)

    def test_coordinate_refinement_is_not_an_update(self):
        t = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        self.observe(detail("1"), t)
        self.observe(
            detail("1", point={"c": "53.36861,-6.27101"}), t + timedelta(minutes=30)
        )
        outages, _, _ = self.load()
        self.assertEqual(len(outages[0].updates), 1)


class TestCustomerMinutes(SiteModelCase):
    def test_the_count_is_integrated_not_multiplied(self):
        """100 customers for an hour then 40 for an hour is 140 customer-hours.

        Multiplying the final count by the whole duration would say 80, and the
        first count by the whole duration would say 200.
        """
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)  # 10:00 Dublin
        self.observe(detail("1", numCustAffected=100, startTime="10/08/2026 10:00"), t)
        self.observe(
            detail("1", numCustAffected=40, startTime="10/08/2026 10:00"),
            t + timedelta(hours=1),
        )
        self.observe(
            detail(
                "1",
                numCustAffected=40,
                startTime="10/08/2026 10:00",
                outageType="Restored",
                restoreTime="10/08/2026 12:00",
            ),
            t + timedelta(hours=2),
        )
        outages, _, _ = self.load()
        o = outages[0]
        lo = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.assertAlmostEqual(o.customer_minutes(lo, NOW) / 60.0, 140.0, places=3)

    def test_nothing_accrues_outside_the_window(self):
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        self.observe(detail("1"), t)
        outages, _, _ = self.load()
        o = outages[0]
        after = datetime(2026, 8, 11, tzinfo=timezone.utc)
        self.assertEqual(o.customer_minutes(after, NOW), 0.0)


class TestEventMerging(SiteModelCase):
    """ESB opens a new outage id each time a fault's scope changes."""

    def split_fault(self):
        # One event: 900 customers off at 10:00 Dublin, restored in two stages.
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        common = {"location": "Glasnevin", "startTime": "10/08/2026 10:00"}
        self.observe(detail("1", numCustAffected=900, **common), t)
        self.observe(
            detail(
                "1", numCustAffected=900, outageType="Restored",
                restoreTime="10/08/2026 11:00", **common,
            ),
            t + timedelta(hours=1),
        )
        self.observe(
            detail(
                "2", numCustAffected=400, outageType="Restored",
                restoreTime="10/08/2026 12:00", **common,
            ),
            t + timedelta(hours=2),
        )

    def test_ids_sharing_a_location_and_start_are_one_event(self):
        self.split_fault()
        outages, _, _ = self.load()
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0].ids, ["1", "2"])

    def test_customers_are_the_envelope_not_the_sum(self):
        """Adding the records counts the same customer once per record."""
        self.split_fault()
        outages, _, _ = self.load()
        self.assertEqual(outages[0].customers, 900)  # not 900 + 400

    def test_the_event_ends_when_its_last_section_returns(self):
        self.split_fault()
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end, datetime(2026, 8, 10, 11, 0, tzinfo=timezone.utc))
        self.assertEqual(o.end_src, "restored")
        self.assertEqual(o.minutes, 120.0)

    def test_customer_minutes_use_the_decaying_envelope(self):
        """900 off for an hour, then 400 for an hour: 1300 customer-hours."""
        self.split_fault()
        outages, _, _ = self.load()
        lo = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.assertAlmostEqual(
            outages[0].customer_minutes(lo, NOW) / 60.0, 1300.0, places=3
        )

    def test_a_record_lingering_past_a_confirmed_restore_does_not_downgrade_it(self):
        """The feed leaves a Fault row up briefly after the last section is back."""
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        common = {"location": "Glasnevin", "startTime": "10/08/2026 10:00"}
        self.observe(
            detail(
                "1", outageType="Restored", restoreTime="10/08/2026 11:00", **common
            ),
            t + timedelta(hours=1),
        )
        # A second id still showing as a fault five minutes later.
        self.observe(detail("2", **common), t + timedelta(hours=1, minutes=5))
        outages, _, _ = self.load()
        self.assertEqual(outages[0].end_src, "restored")
        self.assertEqual(outages[0].end, datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc))

    def test_different_locations_are_not_merged(self):
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        self.observe(detail("1", location="Glasnevin"), t)
        self.observe(detail("2", location="Santry"), t)
        outages, _, _ = self.load()
        self.assertEqual(len(outages), 2)

    def test_a_fault_and_a_planned_outage_are_never_merged(self):
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        self.observe(detail("1", outageType="Fault"), t)
        self.observe(detail("2", outageType="Planned"), t)
        outages, _, _ = self.load()
        self.assertEqual(len(outages), 2)

    def test_the_merged_timeline_reports_customers_still_off(self):
        """Not one line per restored section, which says nothing to a reader."""
        self.split_fault()
        outages, _, _ = self.load()
        o = outages[0]
        rows = model.timeline(o.start, o.end, o.end_src, o.segments)
        self.assertEqual(
            [(k, n) for k, _, n in rows],
            [("began", 900), ("update", 400), ("restored", None)],
        )


    def test_a_repeat_fault_is_not_a_split(self):
        """Supply restored, then lost again at the same spot minutes later.

        These share a location and sit a minute apart, exactly like the split
        records, but they are separate interruptions - the same customers lost
        supply twice - and ESB's own CI index counts each. Only overlap tells
        the two patterns apart, which is why the merge key is the start time
        rather than a tolerance around it. See notes/grading.md.
        """
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        self.observe(
            detail(
                "1", numCustAffected=150, startTime="10/08/2026 10:00",
                outageType="Restored", restoreTime="10/08/2026 11:00",
            ),
            t + timedelta(hours=2),
        )
        self.observe(
            detail(
                "2", numCustAffected=150, startTime="10/08/2026 11:01",
                outageType="Restored", restoreTime="10/08/2026 11:30",
            ),
            t + timedelta(hours=3),
        )
        outages, _, _ = self.load()
        self.assertEqual(len(outages), 2)
        self.assertEqual([o.minutes for o in outages], [60.0, 29.0])

    def test_sections_in_different_counties_stay_apart(self):
        """One fault straddling a county boundary is one row per county.

        Merging would hand one county's customers to its neighbour, and each
        county's page has to carry the customers actually in it.
        """
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        common = {"location": "Little Bray", "startTime": "10/08/2026 10:00"}
        self.observe(detail("1", point={"c": "53.20873,-6.12507"}, **common), t)
        self.observe(detail("2", point={"c": "53.22514,-6.13477"}, **common), t)
        outages, _, _ = self.load()
        self.assertEqual({o.county for o in outages}, {"Wicklow", "Dublin"})
        self.assertEqual(len(outages), 2)

    def test_an_outage_seen_only_after_it_ended(self):
        """6.4% of events are first seen already Restored: a short outage that
        began and ended between two polls. It still has a real duration."""
        self.observe(
            detail(
                "1", outageType="Restored", startTime="10/08/2026 10:00",
                restoreTime="10/08/2026 10:30",
            ),
            datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
        )
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.updates[0].kind, "Restored")
        self.assertEqual(o.minutes, 30.0)
        self.assertFalse(o.planned)


class TestRepeatChains(SiteModelCase):
    """Same spot, failing again shortly after being restored."""

    def chain_of(self, *windows):
        t = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)
        for i, (start, end) in enumerate(windows):
            self.observe(
                detail(
                    str(i), numCustAffected=150, startTime=start,
                    outageType="Restored", restoreTime=end,
                ),
                t + timedelta(hours=6 + i),
            )
        return self.load()[0]

    def test_consecutive_faults_are_tagged_in_order(self):
        outages = self.chain_of(
            ("10/08/2026 10:00", "10/08/2026 11:00"),
            ("10/08/2026 11:01", "10/08/2026 11:20"),
            ("10/08/2026 11:25", "10/08/2026 11:40"),
        )
        self.assertEqual(len(outages), 3)
        self.assertEqual([o.chain for o in outages], [(1, 3), (2, 3), (3, 3)])

    def test_a_gap_longer_than_the_window_breaks_the_chain(self):
        outages = self.chain_of(
            ("10/08/2026 10:00", "10/08/2026 11:00"),
            ("10/08/2026 11:30", "10/08/2026 11:40"),  # 30 minutes later
        )
        self.assertEqual([o.chain for o in outages], [(), ()])

    def test_an_isolated_fault_is_not_a_chain(self):
        outages = self.chain_of(("10/08/2026 10:00", "10/08/2026 11:00"))
        self.assertEqual(outages[0].chain, ())

    def test_planned_works_are_never_chained(self):
        t = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
        self.observe(
            detail("1", outageType="Planned", startTime="10/08/2026 10:00",
                   estRestoreTime="10/08/2026 11:00"), t)
        self.observe(
            detail("2", outageType="Planned", startTime="10/08/2026 11:01",
                   estRestoreTime="10/08/2026 12:00"), t)
        outages, _, _ = self.load()
        self.assertTrue(all(o.chain == () for o in outages))

    def test_the_same_town_far_apart_is_not_a_chain(self):
        """Two faults in one big town are not the same spot failing twice."""
        t = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
        self.observe(
            detail("1", startTime="10/08/2026 10:00", outageType="Restored",
                   restoreTime="10/08/2026 11:00"), t)
        self.observe(
            detail("2", point={"c": "53.40858,-6.27098"},  # ~4.5 km north
                   startTime="10/08/2026 11:01", outageType="Restored",
                   restoreTime="10/08/2026 11:20"), t)
        outages, _, _ = self.load()
        self.assertTrue(all(o.chain == () for o in outages))


class TestTimeline(SiteModelCase):
    """The story of the outage, anchored on the times ESB reports."""

    def test_an_outage_seen_only_after_it_ended_still_reads_correctly(self):
        """The bug this fixes: a 3-hour outage rendered as one late event.

        Roosky began 15:15 and was restored 18:17, but was first seen at 21:02.
        Rendering the observation log directly showed a single 21:02 row.
        """
        self.observe(
            detail(
                "1", numCustAffected=31, outageType="Restored",
                startTime="10/08/2026 15:15", restoreTime="10/08/2026 18:17",
            ),
            datetime(2026, 8, 10, 20, 2, tzinfo=timezone.utc),  # 21:02 Dublin
        )
        outages, _, _ = self.load()
        o = outages[0]
        rows = model.timeline(o.start, o.end, o.end_src, o.segments)
        kinds = [r[0] for r in rows]
        self.assertEqual(kinds, ["began", "restored"])
        # 15:15 and 18:17 Dublin are 14:15 and 17:17 UTC.
        self.assertEqual(rows[0][1], datetime(2026, 8, 10, 14, 15, tzinfo=timezone.utc))
        self.assertEqual(rows[-1][1], datetime(2026, 8, 10, 17, 17, tzinfo=timezone.utc))
        self.assertEqual(rows[0][2], 31)

    def test_the_first_and_last_rows_are_always_the_reported_anchors(self):
        t = datetime(2026, 8, 10, 9, tzinfo=timezone.utc)
        self.observe(detail("1"), t)
        outages, _, _ = self.load()
        o = outages[0]
        rows = model.timeline(o.start, o.end, o.end_src, o.segments)
        self.assertEqual(rows[0][0], "began")
        self.assertEqual(rows[0][1], o.start)
        self.assertEqual(rows[-1][0], o.end_src)
        self.assertEqual(rows[-1][1], o.end)

    def test_an_unchanged_count_adds_no_rows(self):
        """Polling the same figure eight times is not eight updates."""
        t = datetime(2026, 8, 10, 9, tzinfo=timezone.utc)
        for i in range(8):
            self.observe(detail("1"), t + timedelta(minutes=30 * i))
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(len(model.timeline(o.start, o.end, o.end_src, o.segments)), 2)


class TestCountyMonth(SiteModelCase):
    def test_planned_works_are_kept_out_of_the_grade(self):
        t = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
        self.observe(
            detail("1", outageType="Planned", numCustAffected=5000), t
        )
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-08", NOW, 100.0
        )
        self.assertEqual(s["planned"], 1)
        self.assertEqual(s["faults"], 0)
        self.assertEqual(s["cml"], 0.0)
        self.assertEqual(s["customers_hit"], 0)

    def test_cells_cover_the_whole_month_and_mark_the_unobserved(self):
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-08", NOW, 100.0
        )
        self.assertEqual(len(s["cells"]), 31)
        # NOW is the 20th, so the 21st onward is still to come.
        self.assertEqual(set(s["cells"][20:]), {str(model.DAY_FUTURE)})

    def test_days_before_collection_started_are_not_days_without_outages(self):
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-07", NOW, 100.0
        )
        self.assertEqual(set(s["cells"][:30]), {str(model.DAY_NO_DATA)})

    def test_a_month_too_short_to_judge_is_left_ungraded(self):
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-07", NOW, 100.0
        )
        self.assertLess(s["observed_days"], model.MIN_GRADED_DAYS)
        self.assertIsNone(s["grade"])


if __name__ == "__main__":
    unittest.main()
