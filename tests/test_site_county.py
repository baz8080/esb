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

    def test_a_grade_chip_carries_its_band(self):
        """The footer used to spell the bands out. It does not any more, so the
        chip has to, and the two copies of the wording - here and in the app's
        JS - have to agree."""
        # this fixture county is ungraded every month, which is the chip the
        # page can show; the lettered ones come off the helper
        self.assertIn("Too few faults in September 2026 to grade fairly", self.page)
        self.assertIn('title="Grade A: meets ESB', render._grade_chip("A"))
        # the heading chip is one month's letter and the card that named that
        # month is gone, so the title has to name it
        self.assertIn("Grade A in August 2026:", render._grade_chip("A", "August 2026"))
        self.assertRegex(
            self.page, r'<div class="chead"><span[^>]*title="Too few faults in \w+ 2026'
        )
        app = render.SITE_HTML.read_text()
        for grade, band in render.GRADES.items():
            self.assertIn(band, app, f"site.html has drifted from GRADES[{grade}]")

    def test_every_band_the_model_grades_has_wording(self):
        """The wording is what a chip's title says, so a band with none is a
        letter a reader meets with no way to find out what it means."""
        self.assertEqual(
            list(render.GRADES), [letter for letter, _ in model.GRADE_BANDS] + ["F"]
        )

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


class TestAnUngradedMonthSaysWhy(CountyPageCase):
    """Two gates leave a month ungraded and they are not the same fact. The
    chip blamed faults for both, so the first five days of every month told 26
    counties' readers to go looking for outages that were not the reason."""

    def test_a_month_under_five_days_old_names_the_date_it_is_graded_from(self):
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 2, 20, 0, tzinfo=UTC), n_listed=1)
        page = self.render_county(now=datetime(2026, 9, 2, 20, 0, tzinfo=UTC))
        self.assertIn("September 2026 is too new to grade", page)
        self.assertIn("Grades appear from 6 September", page)
        self.assertNotIn("Too few faults in September", page)

    def test_the_reason_is_on_the_page_not_only_in_a_hover(self):
        """`title` does not exist on a touch screen, and the dash it explains is
        the first thing on the page. The five-day gate is national, so one
        sentence under the chip covers every county."""
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 2, 20, 0, tzinfo=UTC), n_listed=1)
        page = self.render_county(now=datetime(2026, 9, 2, 20, 0, tzinfo=UTC))
        self.assertIn(
            '<div class="ungraded">September 2026 is too new to grade.', page
        )
        self.assertIn("September 2026 is too new to grade", self.text_of(page))

    def test_a_month_that_can_never_reach_five_days_promises_no_date(self):
        """Collection opened at 21:02 on 31 July, so July holds three hours and
        the month is over. "Grades appear from 5 August" would be a lie."""
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 10, 0, 0, tzinfo=UTC), n_listed=1)
        page = self.render_county()
        self.assertIn("Only part of July 2026 was watched, so it is not graded", page)
        self.assertNotIn("Grades appear from 5 August", page)

    def test_a_watched_month_still_blames_its_faults(self):
        """The wording that was already right stays right: past five days, the
        county's own fault count is the gate."""
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        self.poll(datetime(2026, 9, 10, 0, 0, tzinfo=UTC), n_listed=1)
        page = self.render_county()
        self.assertIn("Too few faults in September 2026 to grade fairly", page)
        # and no bare line under the chip: nothing here a hover cannot carry
        self.assertNotIn('<div class="ungraded">', page)


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


class TestTheHistoryListing(unittest.TestCase):
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

    def test_a_long_county_is_listed_in_full(self):
        """The cap came off on 2026-08-27: this page presents itself as the
        county's whole record, and a "167 older outages not shown here" line
        underneath said otherwise."""
        page = self.page_for(167)
        self.assertEqual(page.count('<div class="case"'), 167)
        self.assertNotIn("not shown here", page)
        self.assertIn("Outage history", page)
        self.assertIn("· 167 outages", page)


if __name__ == "__main__":
    unittest.main()
