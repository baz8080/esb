"""Unit tests for the site's arithmetic, on synthetic outages.

These build a database the same way a real run does - through Store.apply_* -
so the timeline reconstruction is exercised against the change log the collector
actually writes rather than against a hand-made fixture.
"""

from __future__ import annotations

import math
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from esb_outages.parse import normalize_detail
from esb_outages.store import Store
from esb_site import model, render

NOW = datetime(2026, 8, 20, 0, 0, 0, tzinfo=UTC)


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

    def poll(self, at, n_listed=0):
        """Record a run that reached the feed, which is what sets the horizon."""
        self.store.record_run(
            run_id=iso(at), started_at_utc=iso(at), status="ok", n_listed=n_listed
        )

    def load(self, now=NOW):
        self.store.conn.commit()
        index = model.SmallAreaIndex.load()
        outages, unplaced, until = model.load_outages(self.store.db_path, index, now)
        # Where the collected data stops, as distinct from the clock. Kept on
        # the case so the county-month tests can measure the same window the
        # site does.
        self.until = until
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
        self.observe(detail("1"), datetime(2026, 8, 10, 10, tzinfo=UTC))
        outages, unplaced, _ = self.load()
        self.assertEqual(unplaced, 0)
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0].county, "Dublin")

    def test_a_point_off_the_island_is_not_placed(self):
        self.observe(
            detail("1", point={"c": "48.85,2.35"}),  # Paris
            datetime(2026, 8, 10, 10, tzinfo=UTC),
        )
        outages, unplaced, _ = self.load()
        self.assertEqual((len(outages), unplaced), (0, 1))

    def test_every_county_has_customers_apportioned(self):
        index = model.SmallAreaIndex.load()
        self.assertEqual(len(index.counties), 26)
        self.assertAlmostEqual(sum(index.customers.values()), model.NATIONAL_CUSTOMERS, places=3)


class TestClassification(SiteModelCase):
    def test_restored_does_not_erase_that_it_was_a_fault(self):
        t = datetime(2026, 8, 10, 10, tzinfo=UTC)
        self.observe(detail("1"), t)
        self.observe(
            detail("1", outageType="Restored", restoreTime="10/08/2026 12:30"),
            t + timedelta(minutes=30),
        )
        outages, _, _ = self.load()
        self.assertFalse(outages[0].planned)
        self.assertEqual(outages[0].end_src, "restored")

    def test_planned_stays_planned_and_never_reports_a_restore(self):
        t = datetime(2026, 8, 10, 10, tzinfo=UTC)
        self.observe(detail("1", outageType="Planned"), t)
        outages, _, _ = self.load()
        self.assertTrue(outages[0].planned)
        self.assertNotEqual(outages[0].end_src, "restored")


class TestEndTime(SiteModelCase):
    def test_real_restore_time_wins(self):
        t = datetime(2026, 8, 10, 10, tzinfo=UTC)
        self.observe(
            detail("1", outageType="Restored", restoreTime="10/08/2026 11:45"), t
        )
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "restored")
        self.assertTrue(o.end_known)
        # 11:45 Dublin in August is 10:45 UTC.
        self.assertEqual(o.end, datetime(2026, 8, 10, 10, 45, tzinfo=UTC))

    def test_estimate_is_used_when_it_precedes_the_last_sighting(self):
        # Seen at 09:30 and 14:00 UTC, estimated back at 13:00 Dublin = 12:00 UTC.
        self.observe(detail("1"), datetime(2026, 8, 10, 9, 30, tzinfo=UTC))
        self.observe(detail("1"), datetime(2026, 8, 10, 14, 0, tzinfo=UTC))
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "estimated")
        self.assertEqual(o.end, datetime(2026, 8, 10, 12, 0, tzinfo=UTC))

    def test_last_sighting_wins_when_it_precedes_the_estimate(self):
        # Dropped out of the feed at 09:30 UTC, long before its 12:00 estimate.
        self.observe(detail("1"), datetime(2026, 8, 10, 9, 30, tzinfo=UTC))
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "listed")
        self.assertEqual(o.end, datetime(2026, 8, 10, 9, 30, tzinfo=UTC))

    def test_an_estimate_before_the_start_is_not_an_estimate(self):
        """Falling back rather than clamping: clamping made the outage zero-length."""
        self.observe(
            detail("1", startTime="10/08/2026 09:00", estRestoreTime="10/08/2026 08:00"),
            datetime(2026, 8, 10, 9, 30, tzinfo=UTC),
        )
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "listed")
        self.assertGreaterEqual(o.end, o.start)
        self.assertEqual(o.minutes, 90.0)


class TestUpdates(SiteModelCase):
    def test_an_outage_that_never_changes_has_one_update(self):
        t = datetime(2026, 8, 10, 10, tzinfo=UTC)
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
        t = datetime(2026, 8, 10, 10, tzinfo=UTC)
        self.observe(detail("1"), t)
        body = detail("1", outageType="Restored", restoreTime="10/08/2026 12:30")
        item = {"i": "1", "t": "Restored", "p": body["point"]}
        later = t + timedelta(minutes=30)
        self.store.apply_list(iso(later), [item])
        self.store.apply_detail(iso(later + timedelta(seconds=4)), normalize_detail(body))
        outages, _, _ = self.load()
        self.assertEqual(len(outages[0].updates), 2)

    def test_customer_count_changes_are_updates(self):
        t = datetime(2026, 8, 10, 10, tzinfo=UTC)
        for i, n in enumerate((100, 80, 40)):
            self.observe(detail("1", numCustAffected=n), t + timedelta(minutes=30 * i))
        outages, _, _ = self.load()
        self.assertEqual([u.customers for u in outages[0].updates], [100, 80, 40])

    def test_status_message_noise_is_not_an_update(self):
        """statusMessage has five distinct values and unstable whitespace."""
        t = datetime(2026, 8, 10, 10, tzinfo=UTC)
        self.observe(detail("1", statusMessage="We apologise."), t)
        self.observe(
            detail("1", statusMessage="We  apologise."), t + timedelta(minutes=30)
        )
        outages, _, _ = self.load()
        self.assertEqual(len(outages[0].updates), 1)

    def test_coordinate_refinement_is_not_an_update(self):
        t = datetime(2026, 8, 10, 10, tzinfo=UTC)
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
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)  # 10:00 Dublin
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
        lo = datetime(2026, 8, 1, tzinfo=UTC)
        self.assertAlmostEqual(o.customer_minutes(lo, NOW) / 60.0, 140.0, places=3)

    def test_nothing_accrues_outside_the_window(self):
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
        self.observe(detail("1"), t)
        outages, _, _ = self.load()
        o = outages[0]
        after = datetime(2026, 8, 11, tzinfo=UTC)
        self.assertEqual(o.customer_minutes(after, NOW), 0.0)


class TestEventMerging(SiteModelCase):
    """ESB opens a new outage id each time a fault's scope changes."""

    def split_fault(self):
        # One event: 900 customers off at 10:00 Dublin, restored in two stages.
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
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
        self.assertEqual(o.end, datetime(2026, 8, 10, 11, 0, tzinfo=UTC))
        self.assertEqual(o.end_src, "restored")
        self.assertEqual(o.minutes, 120.0)

    def test_customer_minutes_use_the_decaying_envelope(self):
        """900 off for an hour, then 400 for an hour: 1300 customer-hours."""
        self.split_fault()
        outages, _, _ = self.load()
        lo = datetime(2026, 8, 1, tzinfo=UTC)
        self.assertAlmostEqual(
            outages[0].customer_minutes(lo, NOW) / 60.0, 1300.0, places=3
        )

    def test_a_record_lingering_past_a_confirmed_restore_does_not_downgrade_it(self):
        """The feed leaves a Fault row up briefly after the last section is back."""
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
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
        self.assertEqual(outages[0].end, datetime(2026, 8, 10, 10, 0, tzinfo=UTC))

    def test_different_locations_are_not_merged(self):
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
        self.observe(detail("1", location="Glasnevin"), t)
        self.observe(detail("2", location="Santry"), t)
        outages, _, _ = self.load()
        self.assertEqual(len(outages), 2)

    def test_a_fault_and_a_planned_outage_are_never_merged(self):
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
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
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
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
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
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
            datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
        )
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.updates[0].kind, "Restored")
        self.assertEqual(o.minutes, 30.0)
        self.assertFalse(o.planned)


class TestRepeatChains(SiteModelCase):
    """Same spot, failing again shortly after being restored."""

    def chain_of(self, *windows):
        t = datetime(2026, 8, 10, 6, 0, tzinfo=UTC)
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
        t = datetime(2026, 8, 10, 12, tzinfo=UTC)
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
        t = datetime(2026, 8, 10, 12, tzinfo=UTC)
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
            datetime(2026, 8, 10, 20, 2, tzinfo=UTC),  # 21:02 Dublin
        )
        outages, _, _ = self.load()
        o = outages[0]
        rows = model.timeline(o.start, o.end, o.end_src, o.segments)
        kinds = [r[0] for r in rows]
        self.assertEqual(kinds, ["began", "restored"])
        # 15:15 and 18:17 Dublin are 14:15 and 17:17 UTC.
        self.assertEqual(rows[0][1], datetime(2026, 8, 10, 14, 15, tzinfo=UTC))
        self.assertEqual(rows[-1][1], datetime(2026, 8, 10, 17, 17, tzinfo=UTC))
        self.assertEqual(rows[0][2], 31)

    def test_the_first_and_last_rows_are_always_the_reported_anchors(self):
        t = datetime(2026, 8, 10, 9, tzinfo=UTC)
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
        t = datetime(2026, 8, 10, 9, tzinfo=UTC)
        for i in range(8):
            self.observe(detail("1"), t + timedelta(minutes=30 * i))
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(len(model.timeline(o.start, o.end, o.end_src, o.segments)), 2)


class TestCountyMonth(SiteModelCase):
    def test_planned_works_are_kept_out_of_the_grade(self):
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
        self.observe(
            detail("1", outageType="Planned", numCustAffected=5000), t
        )
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-08", NOW, self.until
        )
        self.assertEqual(s["planned"], 1)
        self.assertEqual(s["faults"], 0)
        self.assertEqual(s["cml"], 0.0)
        self.assertEqual(s["customers_hit"], 0)

    def test_cells_cover_the_whole_month_and_mark_the_unobserved(self):
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-08", NOW, self.until
        )
        self.assertEqual(len(s["cells"]), 31)
        # NOW is the 20th, so the 21st onward is still to come.
        self.assertEqual(set(s["cells"][20:]), {str(model.DAY_FUTURE)})

    def test_days_before_collection_started_are_not_days_without_outages(self):
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-07", NOW, self.until
        )
        self.assertEqual(set(s["cells"][:30]), {str(model.DAY_NO_DATA)})

    def test_the_row_shows_the_month_and_not_the_year(self):
        """Every number on a month's row is that month's, CML included.

        `cml` is the same figure annualised - a year's clock - and the page has
        no room to say which of the two a reader is looking at, so the payload
        carries the month's own minutes per customer.
        """
        t = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
        self.observe(detail("1", numCustAffected=50000), t)
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-08", NOW, self.until
        )
        self.assertGreater(s["cml_month"], 0)
        self.assertGreater(s["cml"], s["cml_month"])
        row = render.build(outages, index, NOW, self.until)[0]["stats"]["Dublin"]
        self.assertEqual(row["2026-08"][3], round(s["cml_month"], 1))

    def test_a_month_too_short_to_judge_is_left_ungraded(self):
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-07", NOW, self.until
        )
        self.assertLess(s["observed_days"], model.MIN_GRADED_DAYS)
        self.assertIsNone(s["grade"])


if __name__ == "__main__":
    unittest.main()


class TestPlacementGrid(unittest.TestCase):
    """The grid is an index, not a model: it must agree with brute force."""

    def test_the_nearest_centroid_wins_west_of_greenwich(self):
        """Ireland is entirely at negative longitude.

        `int()` truncates towards zero and `math.floor()` does not, so building
        the bins with one and reading them with the other files every centroid
        one bin east of where it is looked up, and the ring search can then
        settle for a centroid across a county line.
        """
        index = model.SmallAreaIndex.load()
        rows = [
            (lat, lon, county, code, town)
            for cell in index._bins.values()
            for (lat, lon, county, code, town) in cell
        ]

        def nearest(lat, lon):
            return min(
                rows,
                key=lambda r: math.hypot(
                    (r[0] - lat) * 111.0,
                    (r[1] - lon) * 111.0 * math.cos(math.radians(lat)),
                ),
            )[2:]

        # Points either side of a county line, where a one-bin shift shows up.
        for lat, lon in [
            (53.38763, -6.46575),  # Macetown: Dublin, a shade off the Meath line
            (53.55878, -7.65083),
            (53.5254, -8.29095),
            (53.43591, -7.99234),
            (53.59973, -9.54275),
            (53.48538, -9.25047),
        ]:
            self.assertEqual(index.place(lat, lon), nearest(lat, lon), f"{lat},{lon}")


class TestCollectionHorizon(SiteModelCase):
    """`now` says what is in the future; the data says what is known."""

    def test_the_horizon_is_the_last_run_that_reached_the_feed(self):
        self.observe(detail("1"), datetime(2026, 8, 10, 9, tzinfo=UTC))
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC))
        self.load()
        self.assertEqual(self.until, datetime(2026, 8, 12, 6, tzinfo=UTC))

    def test_a_run_that_never_reached_the_feed_does_not_extend_it(self):
        """An auth failure or a dead connection observed nothing."""
        self.observe(detail("1"), datetime(2026, 8, 10, 9, tzinfo=UTC))
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC))
        self.store.record_run(
            run_id="dead",
            started_at_utc=iso(datetime(2026, 8, 15, 6, tzinfo=UTC)),
            status="unreachable",
        )
        self.load()
        self.assertEqual(self.until, datetime(2026, 8, 12, 6, tzinfo=UTC))

    def test_days_past_the_horizon_are_not_days_without_outages(self):
        """The failure this exists to stop: silence published as calm."""
        self.observe(detail("1"), datetime(2026, 8, 10, 9, tzinfo=UTC))
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC), n_listed=1)
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-08", NOW, self.until
        )
        # Collection stopped on the 12th and NOW is the 20th: the 13th to the
        # 19th are unwatched, and the 20th onward is still to come.
        self.assertEqual(set(s["cells"][12:19]), {str(model.DAY_NO_DATA)})
        self.assertEqual(set(s["cells"][19:]), {str(model.DAY_FUTURE)})

    def test_the_measured_window_stops_at_the_horizon(self):
        """Time the collector was down is not time this site watched."""
        self.observe(detail("1"), datetime(2026, 8, 10, 9, tzinfo=UTC))
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC), n_listed=1)
        outages, _, index = self.load()
        s = model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-08", NOW, self.until
        )
        self.assertAlmostEqual(s["observed_days"], 11.25, places=2)


class TestOngoingOutages(SiteModelCase):
    """An outage still out has no restoration to judge it on."""

    def judged(self, outages, index):
        return model.county_month(
            outages, "Dublin", index.customers["Dublin"], "2026-08", NOW, self.until
        )

    def test_an_outage_still_listed_at_the_last_poll_is_not_judged(self):
        # Out for 30 minutes and still going when collection stopped. Scoring
        # that as a restoration inside 4 hours is how a live fault flatters the
        # grade on every build.
        t = datetime(2026, 8, 10, 9, 30, tzinfo=UTC)
        self.observe(detail("1", startTime="10/08/2026 10:00"), t)
        self.poll(t, n_listed=1)
        outages, _, index = self.load()
        self.assertTrue(outages[0].ongoing)
        s = self.judged(outages, index)
        self.assertEqual(s["faults"], 1)
        self.assertIsNone(s["within"])

    def test_a_restored_outage_is_judged_however_recent(self):
        t = datetime(2026, 8, 10, 9, 30, tzinfo=UTC)
        self.observe(
            detail("1", outageType="Restored", restoreTime="10/08/2026 10:20"), t
        )
        self.poll(t, n_listed=1)
        outages, _, index = self.load()
        self.assertFalse(outages[0].ongoing)
        self.assertEqual(self.judged(outages, index)["within"], 100.0)

    def test_one_stopped_being_listed_before_the_horizon_is_judged(self):
        """Gone from the feed is an ending, even without a restore time."""
        self.observe(detail("1"), datetime(2026, 8, 10, 9, 30, tzinfo=UTC))
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC), n_listed=0)
        outages, _, index = self.load()
        self.assertFalse(outages[0].ongoing)
        self.assertIsNotNone(self.judged(outages, index)["within"])

    def test_a_long_live_outage_still_counts_against_compensation(self):
        """Past 24 hours is true of an outage that has not ended yet."""
        self.observe(
            detail("1", startTime="09/08/2026 08:00"),
            datetime(2026, 8, 10, 9, 30, tzinfo=UTC),
        )
        self.poll(datetime(2026, 8, 10, 9, 30, tzinfo=UTC), n_listed=1)
        outages, _, index = self.load()
        self.assertTrue(outages[0].ongoing)
        self.assertEqual(self.judged(outages, index)["over_compensation"], 1)


class TestShardMonths(SiteModelCase):
    """The list under a month and the tiles above it count the same outages."""

    def test_an_outage_crossing_midnight_on_the_last_is_listed_in_both(self):
        # 00:00 Dublin on 1 August is 23:00 UTC on 31 July, so this one is
        # counted in both months. Filed by its start month alone it went
        # missing from August's list while August's fault tile still counted
        # it, and a reader could count the rows and come up one short.
        self.observe(
            detail("1", startTime="01/08/2026 00:00"),
            datetime(2026, 7, 31, 23, 30, tzinfo=UTC),
        )
        self.observe(
            detail(
                "1",
                startTime="01/08/2026 00:00",
                outageType="Restored",
                restoreTime="01/08/2026 12:00",
            ),
            datetime(2026, 8, 1, 11, 30, tzinfo=UTC),
        )
        self.poll(datetime(2026, 8, 1, 11, 30, tzinfo=UTC), n_listed=1)
        outages, _, index = self.load()
        months = ["2026-07", "2026-08"]

        by_month = render.shard(outages, months, self.until)
        self.assertEqual(len(by_month["2026-07"]), 1)
        self.assertEqual(len(by_month["2026-08"]), 1)

        for ym in months:
            counted = model.county_month(
                outages, "Dublin", index.customers["Dublin"], ym, NOW, self.until
            )["faults"]
            self.assertEqual(counted, len(by_month[ym]), ym)

    def test_a_month_the_outage_never_touches_does_not_list_it(self):
        self.observe(detail("1"), datetime(2026, 8, 10, 9, tzinfo=UTC))
        self.poll(datetime(2026, 8, 10, 9, tzinfo=UTC), n_listed=1)
        outages, _, _ = self.load()
        by_month = render.shard(outages, ["2026-07", "2026-08"], self.until)
        self.assertEqual(by_month["2026-07"], [])
        self.assertEqual(len(by_month["2026-08"]), 1)


class TestSegmentWindow(SiteModelCase):
    """The peak is the highest count reported while the outage was live."""

    def test_a_count_revised_after_the_restore_is_not_the_peak(self):
        # Restored at 11:00 Dublin, then left sitting in the feed for another
        # two polls with the count revised upward - which happens because ESB
        # does not drop restored outages straight away. Those observations
        # describe an outage that was already over.
        self.observe(detail("1"), datetime(2026, 8, 10, 9, 30, tzinfo=UTC))
        for at, n in [
            (datetime(2026, 8, 10, 10, 30, tzinfo=UTC), 250),
            (datetime(2026, 8, 10, 11, 30, tzinfo=UTC), 300),
        ]:
            self.observe(
                detail(
                    "1",
                    outageType="Restored",
                    restoreTime="10/08/2026 11:00",
                    numCustAffected=n,
                ),
                at,
            )
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end, datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        # Every segment lies inside the outage, and none of them is inverted.
        for seg_start, seg_end, _ in o.segments:
            self.assertLess(seg_start, seg_end)
            self.assertGreaterEqual(seg_start, o.start)
            self.assertLessEqual(seg_end, o.end)
        self.assertEqual(o.customers, 100)


class TestPartialDays(SiteModelCase):
    """A day watched for six hours is not a quiet day."""

    def test_the_first_and_last_days_of_collection_are_short(self):
        self.observe(detail("1"), datetime(2026, 8, 10, 9, tzinfo=UTC))
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC), n_listed=1)
        self.load()
        self.assertEqual(
            model.partial_days(self.until),
            [model.COLLECTION_START.date().isoformat(), "2026-08-12"],
        )

    def test_a_horizon_on_the_stroke_of_midnight_leaves_a_whole_day(self):
        """[lo, hi) - a window ending at 00:00 covers the previous day fully."""
        until = datetime(2026, 8, 13, 0, 0, tzinfo=UTC)
        self.assertEqual(model.partial_days(until)[-1], "2026-08-12")


class TestEstimatePlumbing(SiteModelCase):
    """ESB's restore estimate reaches the page beside the actual restore."""

    def test_the_estimate_survives_beside_a_confirmed_restore(self):
        self.observe(
            detail("1", restoreTime="10/08/2026 11:00"),
            datetime(2026, 8, 10, 11, 30, tzinfo=UTC),
        )
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC))
        outages, _, _ = self.load()
        o = outages[0]
        self.assertEqual(o.end_src, "restored")
        # estRestoreTime 13:00 Dublin is 12:00 UTC in August.
        self.assertEqual(o.est, datetime(2026, 8, 10, 12, 0, tzinfo=UTC))
        self.assertEqual(render.case_record(o)[10], "2026-08-10T12:00")

    def test_a_merged_event_keeps_the_estimate_of_the_record_that_ended_it(self):
        # A sibling that closed early still carries ESB's old 18:00 estimate;
        # the record that ended the event had it revised down to 12:00. max()
        # over the group would resurrect the stale 18:00.
        at = datetime(2026, 8, 10, 11, 45, tzinfo=UTC)
        self.observe(
            detail(
                "1",
                restoreTime="10/08/2026 11:00",
                estRestoreTime="10/08/2026 18:00",
            ),
            at,
        )
        self.observe(
            detail(
                "2",
                restoreTime="10/08/2026 11:30",
                estRestoreTime="10/08/2026 12:00",
            ),
            at,
        )
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC))
        outages, _, _ = self.load()
        self.assertEqual(len(outages), 1)
        self.assertEqual(
            outages[0].end, datetime(2026, 8, 10, 10, 30, tzinfo=UTC)
        )
        self.assertEqual(
            outages[0].est, datetime(2026, 8, 10, 11, 0, tzinfo=UTC)
        )

    def test_an_estimate_the_page_cannot_show_is_not_serialized(self):
        # Matching the restore exactly would render "restored 12:00 · ESB's
        # estimate was 12:00"; an unconfirmed end never renders the estimate
        # at all. Neither belongs in the shard.
        self.observe(
            detail("1", restoreTime="10/08/2026 13:00"),
            datetime(2026, 8, 10, 12, 30, tzinfo=UTC),
        )
        self.observe(detail("2", location="Marino"),
                     datetime(2026, 8, 10, 11, 30, tzinfo=UTC))
        self.poll(datetime(2026, 8, 12, 6, tzinfo=UTC))
        outages, _, _ = self.load()
        by_loc = {o.location: o for o in outages}
        self.assertEqual(by_loc["Glasnevin"].est, by_loc["Glasnevin"].end)
        self.assertIsNone(render.case_record(by_loc["Glasnevin"])[10])
        self.assertNotEqual(by_loc["Marino"].end_src, "restored")
        self.assertIsNone(render.case_record(by_loc["Marino"])[10])


class TestCaseCopy(unittest.TestCase):
    """The outage card's summary line, in the words the page shows.

    Records are hand-made in case_record's shape:
    [id, location, planned, customers, start, end, endSrc, reason, chain,
    updates, est].
    """

    @staticmethod
    def record(**over):
        k = [
            "1", "Glasnevin", 0, 17,
            "2026-08-24T10:46", "2026-08-24T14:32", "restored",
            "", [], [], "2026-08-24T15:00",
        ]
        fields = {
            "planned": 2, "customers": 3, "start": 4, "end": 5,
            "end_src": 6, "reason": 7, "est": 10,
        }
        for name, value in over.items():
            k[fields[name]] = value
        return k

    def test_a_confirmed_restore_says_how_long_and_how_it_landed(self):
        html = render._case_html(self.record())
        self.assertIn(
            "17 customers affected · began Mon 24 Aug, 10:46 · "
            "restored 14:32 (3 h 46 min) · 28 min earlier than ESB estimated",
            html,
        )
        # The floating right-hand span is gone; the duration belongs to the
        # phrase that names the end it measures.
        self.assertNotIn('class="when"', html)

    def test_a_restore_past_the_estimate_says_later(self):
        html = render._case_html(self.record(est="2026-08-24T13:00"))
        self.assertIn("restored 14:32 (3 h 46 min) · 1 h 32 min later than ESB estimated", html)

    def test_an_estimate_all_but_met_is_not_worth_a_clause(self):
        # Inside five minutes either way, "3 min earlier" is noise dressed as
        # a finding. 5% of restored faults land there.
        html = render._case_html(self.record(est="2026-08-24T14:35"))
        self.assertIn("restored 14:32 (3 h 46 min)", html)
        self.assertNotIn("than ESB estimated", html)

    def test_an_end_on_a_later_day_names_the_day(self):
        html = render._case_html(self.record(end="2026-08-25T01:10", est=None))
        self.assertIn("restored Tue 25 Aug, 01:10", html)

    def test_an_unconfirmed_fault_end_says_what_is_missing(self):
        # "not confirmed" left a reader guessing whether the estimate or the
        # outage was the unconfirmed thing. Name the missing record instead.
        html = render._case_html(
            self.record(end="2026-08-24T15:00", end_src="estimated", est=None)
        )
        self.assertIn(
            "expected back by 15:00 (about 4 h) · no restore time published", html
        )
        self.assertNotIn("not confirmed", html)

    def test_a_last_sighting_reads_as_a_span_not_a_timestamp(self):
        # "last seen out at 14:32" made a reader work out the duration from
        # two clock times on the same line. State the span; the sighting's
        # own clock time was never the interesting half.
        html = render._case_html(
            self.record(end="2026-08-24T14:32", end_src="listed", est=None)
        )
        self.assertIn("off for about 4 h · no restore time published", html)
        self.assertNotIn("last seen out", html)

    def test_a_very_short_unconfirmed_span_reads_as_a_bound(self):
        # A listed end 5 minutes after the start is a lower bound; "about
        # 30 min" would contradict the timestamps on the same card.
        html = render._case_html(
            self.record(end="2026-08-24T10:51", end_src="listed", est=None)
        )
        self.assertIn("off for under 30 min", html)

    def test_a_planned_outage_wears_its_reason_in_the_tag(self):
        html = render._case_html(
            self.record(planned=1, end_src="listed", est=None,
                        reason="new connections")
        )
        self.assertIn('<span class="tag tag-p">Planned · new connections</span>', html)

    def test_a_planned_outage_with_no_reason_just_says_planned(self):
        # 15% of them, and nothing in the record distinguishes one: the status
        # message is the same apology on every planned outage ESB publishes.
        html = render._case_html(self.record(planned=1, end_src="listed", est=None))
        self.assertIn('<span class="tag tag-p">Planned</span>', html)

    def test_planned_works_delisted_early_are_not_seen_out(self):
        # 928 of 1,318 planned events end as "listed". The fault vocabulary
        # does not belong on scheduled work, and what was measured is time on
        # ESB's list, not time off supply.
        html = render._case_html(
            self.record(planned=1, end_src="listed", est=None)
        )
        self.assertIn("listed for about 4 h · no end time published", html)
        self.assertNotIn("seen out", html)
        self.assertNotIn("off for", html)

    def test_planned_works_read_as_a_schedule_not_a_failed_promise(self):
        html = render._case_html(
            self.record(planned=1, end="2026-08-24T15:00", end_src="estimated",
                        est=None)
        )
        self.assertIn("scheduled until 15:00 (4 h 14 min)", html)
        self.assertNotIn("not confirmed", html)

    def test_esbs_shouted_reasons_come_out_readable(self):
        self.assertEqual(model.reason_label("IMPROVE QUALITY OF SUPPLY"), "supply quality")
        self.assertEqual(model.reason_label("DIVERT AN OVERHEAD LINE"), "line diversion")
        self.assertEqual(model.reason_label(""), "")
        # A seventh reason ESB starts publishing renders as itself rather than
        # vanishing until someone notices.
        self.assertEqual(model.reason_label("REPLACE A POLE"), "replace a pole")

    def test_planned_timeline_rows_match_the_schedule_wording(self):
        rows = [
            ["began", "2026-08-24T10:46", 40],
            ["update", "2026-08-24T12:00", 12],
            ["estimated", "2026-08-24T15:00", None],
        ]
        html = render._updates_html(rows, planned=True)
        self.assertIn("<b>Scheduled end</b>", html)
        self.assertNotIn("Estimated restore", html)
        rows[-1][0] = "listed"
        self.assertIn("<b>Last listed</b>", render._updates_html(rows, planned=True))
        # Fault timelines keep the fault wording.
        self.assertIn("<b>Last seen still out</b>", render._updates_html(rows))

    def test_span_hm_never_shows_a_decimal(self):
        self.assertEqual(render._span_hm(0.5), "30 min")
        self.assertEqual(render._span_hm(3 + 46 / 60), "3 h 46 min")
        self.assertEqual(render._span_hm(4.0), "4 h")
        self.assertEqual(render._span_hm(4.24, about=True), "about 4 h")
        self.assertEqual(render._span_hm(0.1, about=True), "under 30 min")
        self.assertEqual(render._span_hm(0.4, about=True), "about 30 min")
        self.assertEqual(render._span_hm(72), "3 days")

    def test_customer_figures_round_to_their_real_precision(self):
        self.assertEqual(render._approx(32069), 32000)
        self.assertEqual(render._approx(9432), 9400)
        self.assertEqual(render._approx(151678), 152000)
