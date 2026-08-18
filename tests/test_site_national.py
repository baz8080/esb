"""Cross-checks against ESB Networks' own published figures, on the real corpus.

This is the most valuable file in the site's test suite. Everything else checks
that the arithmetic does what it was told; this checks that what it was told
bears any relation to reality, by comparing the numbers this pipeline derives
against the ones ESB reports to the regulator.

It needs the collected data, which lives in a separate repository. Locally,
point ESB_DATA_DIR at a checkout of it and run `esb_outages rebuild` first; CI
checks it out and always runs these.
"""

from __future__ import annotations

import calendar
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from esb_site import model, render

DATA_DIR = Path(os.environ.get("ESB_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "esb.db"

# Published by ESB Networks for 2024, unplanned and excluding storm days.
ESB_CI = model.ESB_NATIONAL_CI
ESB_CAIDI = model.ESB_NATIONAL_CML / ESB_CI  # 85 minutes per interrupted customer


@unittest.skipUnless(
    DB_PATH.exists(),
    f"no database at {DB_PATH}; set ESB_DATA_DIR and run `esb_outages rebuild`",
)
class NationalCase(unittest.TestCase):
    """Loaded once: replaying the corpus for each test would dominate the run."""

    @classmethod
    def setUpClass(cls):
        cls.index = model.SmallAreaIndex.load()
        # The clock is pinned so the assertions do not drift as the corpus grows
        # past them; it moves forward when the reference window is widened.
        cls.now = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)
        cls.outages, cls.unplaced = model.load_outages(DB_PATH, cls.index, cls.now)
        cls.lo, cls.hi = model.COLLECTION_START, cls.now
        cls.faults = [o for o in cls.outages if not o.planned]
        # Only outages that began inside the window can be counted as
        # interruptions, or the rate is inflated by ones already under way.
        cls.started = [o for o in cls.faults if o.start >= cls.lo]

    @property
    def years(self):
        return (self.hi - self.lo).total_seconds() / (365 * 86400)

    def national_cml(self):
        return model.national_cml(self.outages, self.now)

    def national_ci(self):
        return sum(o.customers for o in self.started) / model.NATIONAL_CUSTOMERS / self.years

    def test_every_outage_is_placed_in_a_county(self):
        self.assertEqual(self.unplaced, 0)
        self.assertEqual(len({o.county for o in self.outages}), 26)

    def test_duration_per_interrupted_customer_matches_esb(self):
        """The strongest evidence that the timing model is right.

        CAIDI is CML divided by CI, so it cancels the customer-count bias
        entirely and leaves only the clock. Landing within a few minutes of
        ESB's own figure is what licenses this site to talk about durations.
        """
        customer_minutes = sum(o.customer_minutes(self.lo, self.hi) for o in self.faults)
        caidi = customer_minutes / sum(o.customers for o in self.started)
        self.assertAlmostEqual(caidi, ESB_CAIDI, delta=25.0, msg=f"CAIDI {caidi:.1f} min")

    def test_the_customer_count_bias_is_where_we_left_it(self):
        """PowerCheck reports more interrupted customers than ESB settles on.

        Nothing here can fix that - it is the feed's own figure - but the grade
        is built as a ratio precisely so the bias cancels, and that reasoning
        only holds while the bias stays roughly constant. If this test fails,
        re-read notes/grading.md before touching the bands: either the feed
        changed, or the window stopped being representative.
        """
        ratio = self.national_ci() / ESB_CI
        self.assertGreater(ratio, 1.2, f"CI ratio {ratio:.2f}")
        self.assertLess(ratio, 2.4, f"CI ratio {ratio:.2f}")

    def test_national_cml_tracks_the_bias_and_nothing_else(self):
        """CML should be off by the same factor CI is, and no more.

        If CML drifts away from CI's ratio, the durations have moved - which is
        a real finding, not a rounding error.
        """
        cml_ratio = self.national_cml() / model.ESB_NATIONAL_CML
        ci_ratio = self.national_ci() / ESB_CI
        self.assertAlmostEqual(cml_ratio, ci_ratio, delta=0.35,
                               msg=f"CML {cml_ratio:.2f}x vs CI {ci_ratio:.2f}x")

    def test_grades_are_spread_across_the_bands(self):
        """A scale on which every county scores the same is not a scale."""
        national = self.national_cml()
        grades = {
            model.county_month(
                self.outages, c, self.index.customers[c], "2026-08", self.now, national
            )["grade"]
            for c in self.index.counties
        }
        self.assertGreaterEqual(len(grades - {None}), 4, f"grades seen: {sorted(grades - {None})}")

    def test_the_disclosure_stays_the_exception(self):
        """The whole design rests on most outages being short enough to show."""
        inline = sum(1 for o in self.outages if len(o.updates) <= model.INLINE_UPDATES)
        self.assertGreater(inline / len(self.outages), 0.90)


@unittest.skipUnless(DB_PATH.exists(), f"no database at {DB_PATH}")
class PayloadCase(unittest.TestCase):
    """The 500 KB budget, enforced rather than hoped for."""

    BUDGET = 500 * 1024

    @classmethod
    def setUpClass(cls):
        index = model.SmallAreaIndex.load()
        now = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)
        outages, _ = model.load_outages(DB_PATH, index, now)
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls._tmp.name)
        cls.data = render.write(cls.dir, outages, index, now)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_initial_load_is_inside_the_budget(self):
        total, report = render.size_report(self.dir)
        self.assertLess(total, self.BUDGET, f"\n{report}")

    def test_the_payload_carries_no_per_outage_records(self):
        """The budget holds only because individual outages live in the shards.

        A failure here means something started copying cases into data.js, which
        is the one change that would put the front page on a path to breaking
        the budget as the archive grows.
        """
        self.assertEqual(
            set(self.data),
            {
                "generated", "start", "months", "esb",
                "counties", "customers", "stats", "national",
            },
        )

    def test_every_county_has_a_page_and_a_shard(self):
        for county in self.data["counties"]:
            s = render.slug(county)
            self.assertTrue((self.dir / "c" / f"{s}.html").exists(), county)
            # Written even for a county with nothing in it, so the loader never
            # has to tell a 404 apart from a quiet county.
            self.assertTrue((self.dir / "h" / f"{s}.js").exists(), county)

    def test_day_cells_are_one_character_per_day(self):
        for county, months in self.data["stats"].items():
            for ym, row in months.items():
                days = calendar.monthrange(int(ym[:4]), int(ym[5:7]))[1]
                self.assertEqual(len(row[0]), days, f"{county} {ym}")
                self.assertTrue(set(row[0]) <= set("01234589"), f"{county} {ym}: {row[0]}")


if __name__ == "__main__":
    unittest.main()
