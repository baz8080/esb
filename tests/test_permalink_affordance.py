"""The county view offers the page it has a permanent URL for.

The hash route is not a URL a reader can keep or a crawler can index, so
c/<slug>.html is the only durable address a county has - and until 2026-08-26
the app never mentioned it. The page linked into the app; the app did not link
back, which is the leg that matters for sharing.

Source-level rather than executed: this is a template string assembled at
runtime, and what needs guarding is that the link is still written at all.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

SITE_HTML = (Path(__file__).resolve().parent.parent / "esb_site" / "site.html").read_text()


class PermalinkAffordanceCase(unittest.TestCase):
    def test_the_county_view_links_to_the_county_page(self):
        self.assertIn("'<div class=\"sub\"><a href=\"c/' + slug(c) + '.html\">", SITE_HTML)

    def test_the_link_sits_under_the_heading_and_above_the_month_tabs(self):
        """Placement is the point, and it matches lifts and uisce."""
        head = SITE_HTML.index("'<span class=\"pop\">About ' + num(D.customers[c])")
        link = SITE_HTML.index("'<div class=\"sub\"><a href=\"c/' + slug(c) + '.html\">")
        tabs = SITE_HTML.index("'<div class=\"controls\"><div class=\"months\">'")
        self.assertLess(head, link)
        self.assertLess(link, tabs)

    def test_the_link_names_the_county_rather_than_calling_itself_a_permalink(self):
        """Named for the difference a reader gets - this view is one month, that
        page is all of them. Naming it for its content is only honest because
        the page carries more than the view; lifts' does not, and says
        "permanent link" instead."""
        self.assertIn("Every month for County ", SITE_HTML)
        self.assertIn(" on one page", SITE_HTML)
        self.assertNotIn("permanent link", SITE_HTML.lower())


class DescriptionCase(unittest.TestCase):
    """The meta description is read alone, in a search result, with the page it
    describes not yet open - so it has to survive being read as a promise."""

    def build(self, county="Dublin", n=None):
        from datetime import UTC, datetime

        from esb_site import model, render

        index = model.SmallAreaIndex.load()
        now = datetime(2026, 8, 31, tzinfo=UTC)
        data, _, months, _ = render.build([], index, now, now)
        n = 190 if n is None else n
        shard = {
            "2026-08": [
                [f"o{i}", "Somewhere", i % 2, 10, "2026-08-01T09:00",
                 "2026-08-01T11:00", "restored", "", [], [], None]
                for i in range(n)
            ]
        }
        page = render.county_page(county, data, shard, months, now, index.counties)
        return re.search(r'name="description" content="([^"]*)"', page).group(1)

    def test_the_counts_are_the_county_s_record_not_a_promise_of_a_listing(self):
        """The counts and the listing agree since the cap came off, but the
        order still matters: the record first, what the page holds after it."""
        desc = self.build()
        self.assertIn("County Dublin: ", desc)
        self.assertIn("Month-by-month totals and every outage recorded", desc)
        self.assertNotIn("recorded in County", desc)

    def test_it_stays_true_when_a_search_engine_truncates_it(self):
        """A snippet is cut by width, and what survives is the front. The clause
        naming what the page holds may be lost; the sentence before it may not
        become false when it is."""
        desc = self.build().replace("&#x27;", "'")
        head = desc.split(". ")[0]
        self.assertIn("since 31 July 2026", head)
        self.assertNotIn("every outage recorded", head)

    def test_it_fits_a_search_result(self):
        self.assertLessEqual(len(self.build().replace("&#x27;", "'")), 160)

    def test_one_fault_is_not_one_faults(self):
        self.assertIn("1 fault and 1 planned power cut ", self.build(n=2))


if __name__ == "__main__":
    unittest.main()
