"""The index holds back what its script has not filled yet.

Source-level, like test_permalink_affordance: what needs guarding is that the
marker, the attributes and the calls are still written. Without any one of them
the page paints an empty skeleton above a footer, and the render pushes the
footer down (CLS 0.41 on a phone, 0.20 at 1366px, measured 2026-10-02).
"""

from __future__ import annotations

import unittest
from html.parser import HTMLParser
from pathlib import Path

import statusui

from esb_site import render

SITE_HTML = (Path(__file__).resolve().parent.parent / "esb_site" / "site.html").read_text()

# The banner is left out on purpose: it is the first thing drawn, and its
# "Loading…" is what a reader sees while the rest is held back.
HELD_BACK = {"footer", "#basis", "#legend", "#list", "#natHeading", "#tiles", ".controls"}


class WaitingElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-wait" not in a:
            return
        if tag == "footer":
            self.found.add("footer")
        elif a.get("id"):
            self.found.add("#" + a["id"])
        else:
            self.found.add("." + a["class"].split()[0])


def function_body(name):
    start = SITE_HTML.index(f"function {name}(")
    return SITE_HTML[start : SITE_HTML.index("\n}\n", start)]


class FirstPaintCase(unittest.TestCase):
    def test_the_marker_is_in_the_head(self):
        head = SITE_HTML[SITE_HTML.index("<head>") : SITE_HTML.index("</head>")]
        self.assertIn(statusui.UI_WAIT, head)

    def test_the_built_page_carries_the_script_in_place_of_the_marker(self):
        page = render._page(render.SITE_HTML, {"CANONICAL": "x"})
        self.assertNotIn(statusui.UI_WAIT, page)
        self.assertEqual(page.count(statusui.WAIT_HEAD), 1)

    def test_what_the_first_render_fills_is_held_back_and_the_banner_is_not(self):
        parser = WaitingElements()
        parser.feed(SITE_HTML)
        self.assertEqual(parser.found, HELD_BACK)

    def test_render_releases_the_footer_before_it_measures_the_month_strip(self):
        """A [data-wait] strip measures zero, so revealMonthTab would not scroll it."""
        body = function_body("render")
        self.assertIn("pending(county && HSTATE[curCounty] ===", body)
        self.assertLess(body.index("pending("), body.index("revealMonthTab("))

    def test_a_page_with_no_data_releases_what_it_holds(self):
        boot = function_body("boot")
        failed = boot[boot.index("if (!D)") : boot.index("return;")]
        self.assertRegex(failed, r"pending\(false\)")


if __name__ == "__main__":
    unittest.main()
