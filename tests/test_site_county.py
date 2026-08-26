"""What a county page publishes, on synthetic outages.

The county page is the site's indexable surface: a reader arriving from a search
result is handed this and nothing else, and unlike the app it has to say
everything without a payload. These guard what it carries.

Built through the same Store the collector writes, so the page is exercised
against the pipeline rather than against a hand-made shard - except where a
hand-made one is the clearer statement of the rule, which is the cap.
"""

from __future__ import annotations

import re
import unittest
from datetime import UTC, datetime

import statusui

from esb_site import model, render
from tests.test_site_model import SiteModelCase, detail

# Late enough that July, August and September are all in the month list, and
# past the horizon a September poll sets.
SEPT = datetime(2026, 9, 20, 0, 0, 0, tzinfo=UTC)


class CountyPageCase(SiteModelCase):
    """Renders Dublin, which is where `detail()`'s coordinates land."""

    def render_county(self, now=SEPT, county="Dublin"):
        outages, _, index = self.load(now)
        data, by_county, months, _ = render.build(outages, index, now, self.until)
        by_month = render.shard(by_county.get(county, []), months, self.until)
        self.months = months
        return render.county_page(
            county, data, by_month, months, self.until, index.counties
        )

    def text_of(self, page):
        """The page as a reader with no stylesheet would read it."""
        body = re.sub(r"<(script|style).*?</\1>", "", page, flags=re.S)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()


class TestTheSubjectIsACounty(CountyPageCase):
    def test_the_title_names_the_county_and_never_a_month(self):
        """The whole reason the page grew past one month. A title carrying
        "August 2026" made the URL's subject change under it every time the
        month rolled over, which is the one thing a permalink must not do."""
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 1, 0, 0, tzinfo=UTC), n_listed=1)
        page = self.render_county()
        title = re.search(r"<title>([^<]*)</title>", page).group(1)
        self.assertEqual(title, "Power outages in County Dublin")
        for name in statusui.MONTH_NAMES:
            self.assertNotIn(name, title)

    def test_the_description_counts_the_whole_archive(self):
        """A search snippet that describes one month describes the wrong thing."""
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.observe(
            detail("2", outageType="Planned", startTime="02/09/2026 09:00",
                   estRestoreTime="02/09/2026 17:00"),
            datetime(2026, 9, 2, 10, 0, tzinfo=UTC),
        )
        self.poll(datetime(2026, 9, 3, 0, 0, tzinfo=UTC), n_listed=2)
        desc = re.search(r'name="description" content="([^"]*)"', self.render_county())
        self.assertIn("1 fault and 1 planned power cut", desc.group(1))
        self.assertIn("since", desc.group(1))


class TestTheMonthBoundary(CountyPageCase):
    def test_an_outage_spanning_two_months_is_listed_once(self):
        """A shard files an outage under every month it overlaps - that is what
        keeps the app's row count matching its tiles. Flattening one for the
        page without folding those back would print the same fault twice."""
        self.observe(
            detail("1", startTime="31/08/2026 22:00", estRestoreTime="01/09/2026 02:00",
                   restoreTime="01/09/2026 02:00"),
            datetime(2026, 9, 1, 3, 0, tzinfo=UTC),
        )
        self.poll(datetime(2026, 9, 2, 0, 0, tzinfo=UTC), n_listed=1)
        outages, _, index = self.load(SEPT)
        data, by_county, months, _ = render.build(outages, index, SEPT, self.until)
        by_month = render.shard(by_county.get("Dublin", []), months, self.until)

        listings = sum(len(v) for v in by_month.values())
        self.assertEqual(listings, 2, "the fixture must actually straddle the boundary")

        page = render.county_page(
            "Dublin", data, by_month, months, self.until, index.counties
        )
        self.assertEqual(page.count('<div class="case" id="o1"'), 1)

    def test_cases_are_ordered_by_when_they_began(self):
        """Newest first across the whole archive, not month block by month block:
        a boundary spanner is filed under the later month but began in the
        earlier one, and it belongs where its start puts it."""
        self.observe(
            detail("old", startTime="31/08/2026 22:00", estRestoreTime="01/09/2026 02:00",
                   restoreTime="01/09/2026 02:00", location="Spanner"),
            datetime(2026, 9, 1, 3, 0, tzinfo=UTC),
        )
        self.observe(
            detail("new", startTime="05/09/2026 09:00", estRestoreTime="05/09/2026 11:00",
                   restoreTime="05/09/2026 11:00", location="Later"),
            datetime(2026, 9, 5, 12, 0, tzinfo=UTC),
        )
        self.poll(datetime(2026, 9, 6, 0, 0, tzinfo=UTC), n_listed=2)
        page = self.render_county()
        self.assertLess(page.index("Later"), page.index("Spanner"))


class TestTheMonthTable(CountyPageCase):
    def setUp(self):
        super().setUp()
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 10, 0, 0, tzinfo=UTC), n_listed=1)
        self.page = self.render_county()

    def test_every_month_gets_a_row_newest_first(self):
        rows = re.findall(r'<th scope="row">([A-Z][a-z]+ \d{4})', self.page)
        self.assertEqual(rows, [render.month_label(ym) for ym in reversed(self.months)])

    def test_a_month_watched_end_to_end_carries_no_caveat(self):
        """August is whole here, so a note on it would be noise."""
        august = re.search(r'<th scope="row">August 2026(.*?)</th>', self.page).group(1)
        self.assertEqual(august, "")

    def test_a_part_watched_month_says_which_part(self):
        """Collection began on 31 July and the horizon stops mid-September, so
        those two rows are built from less time than the months beside them. A
        row of zeros for three hours of July reads as a quiet month otherwise."""
        july = re.search(r'<th scope="row">July 2026(.*?)</th>', self.page).group(1)
        self.assertIn("from 31 Jul", july)
        sept = re.search(r'<th scope="row">September 2026(.*?)</th>', self.page).group(1)
        self.assertIn("to 10 Sep", sept)


class TestThePageStandsAlone(CountyPageCase):
    def test_it_pulls_neither_the_payload_nor_a_shard(self):
        """The point of the page. It carries its own text; a crawler or a reader
        on a dead connection gets the county, not a shell for a script to fill."""
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 1, 0, 0, tzinfo=UTC), n_listed=1)
        page = self.render_county()
        self.assertNotIn("data.js", page)
        self.assertNotIn("ESB_DATA", page)
        self.assertNotIn("ESB_CASES", page)
        self.assertGreater(len(self.text_of(page)), 600)

    def test_no_template_marker_survives(self):
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 1, 0, 0, tzinfo=UTC), n_listed=1)
        self.assertNotRegex(self.render_county(), r"<!--(TITLE|DESC|CANONICAL|BODY)-->")

    def test_the_canonical_is_self_referential(self):
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 1, 0, 0, tzinfo=UTC), n_listed=1)
        self.assertIn(
            f'<link rel="canonical" href="{render.BASE_URL}/c/dublin.html">',
            self.render_county(),
        )


class TestTheCap(unittest.TestCase):
    """A hand-made shard: the rule under test is a count, and building a
    thousand outages through the store would say nothing extra about it."""

    def shard_of(self, n):
        return {
            "2026-08": [
                [
                    f"o{i}", "Somewhere", 0, 10,
                    f"2026-08-{1 + i % 28:02d}T09:00", f"2026-08-{1 + i % 28:02d}T11:00",
                    "restored", "", [], [], None,
                ]
                for i in range(n)
            ]
        }

    def page_for(self, n):
        index = model.SmallAreaIndex.load()
        now = datetime(2026, 8, 31, tzinfo=UTC)
        data, _, months, _ = render.build([], index, now, now)
        return render.county_page(
            "Dublin", data, self.shard_of(n), months, now, index.counties
        )

    def test_a_short_county_shows_everything_and_says_nothing_about_more(self):
        page = self.page_for(3)
        self.assertEqual(page.count('<div class="case"'), 3)
        self.assertNotIn("older outages not shown", page)

    def test_a_long_county_stops_at_the_cap_and_says_what_it_held_back(self):
        """Unbounded, the busiest county's page would grow with the archive for
        as long as the site runs."""
        over = render.COUNTY_PAGE_CASES + 17
        page = self.page_for(over)
        self.assertEqual(page.count('<div class="case"'), render.COUNTY_PAGE_CASES)
        self.assertIn("17 older outages not shown here", page)
        self.assertIn("Outage history", page)
        self.assertIn(f"{over:,}", page)


if __name__ == "__main__":
    unittest.main()
