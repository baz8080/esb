"""The county view offers the page it has a permanent URL for.

The hash route is not a URL a reader can keep or a crawler can index, so
c/<slug>.html is the only durable address a county has - and until 2026-08-26
the app never mentioned it. The page linked into the app; the app did not link
back, which is the leg that matters for sharing.

Source-level rather than executed: this is a template string assembled at
runtime, and what needs guarding is that the link is still written at all.
"""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
