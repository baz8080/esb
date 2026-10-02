"""Long static lists skip layout until they are near the screen.

Source-level, like test_first_paint: what needs guarding is that the rule is
written where it applies and that the markup it counts on is still there. The
measurements are in notes/design-alignment.md (2026-10-02).
"""

from __future__ import annotations

import re
import unittest

from tests.test_site_areas import AreaSiteCase
from tests.test_site_css import _stylesheet

# `nth-of-type` counts divs, so the first ten cases are the first ten only
# while nothing else in their card is a div.
CARD_THEN_CASES = (
    r'<div class="card"><h2>(?:(?!</?div).)*?</h2>'
    r'<p class="note">(?:(?!</?div).)*?</p><div class="case" id='
)


def skipping_rules(css):
    return [
        (prelude.strip(), body)
        for prelude, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
        if "content-visibility" in body
    ]


class SkippedRowsCase(AreaSiteCase):
    def test_a_case_is_skipped_only_past_the_first_ten(self):
        rules = skipping_rules(_stylesheet(self.page("c/dublin.html")))
        self.assertTrue(rules)
        for prelude, body in rules:
            self.assertIn(".case[id]:nth-of-type(n+11)", prelude)
            self.assertIn("content-visibility: auto", body)

    def test_a_skipped_case_has_an_estimate_and_a_clip_margin_for_its_focus_rings(self):
        css = _stylesheet(self.page("c/dublin.html"))
        (_, body), *_ = skipping_rules(css)
        self.assertRegex(body, r"contain-intrinsic-size:\s*auto calc\(")
        self.assertIn("overflow-clip-margin: 6px", body)

    def test_the_shapes_a_case_can_take_have_their_own_estimates(self):
        css = _stylesheet(self.page("c/dublin.html"))
        self.assertIn(":has(> .repeat)", css)
        self.assertIn(":has(> .tl)", css)

    def test_the_cases_are_the_only_divs_after_their_card_heading(self):
        for rel in ("c/dublin.html", "a/dublin/skerries.html"):
            with self.subTest(page=rel):
                self.assertRegex(self.page(rel), re.compile(CARD_THEN_CASES, re.S))

    def test_the_directory_skips_a_county_until_it_is_near(self):
        page = self.page("areas.html")
        sections = [rule for rule in skipping_rules(_stylesheet(page)) if rule[0] == "section"]
        self.assertEqual(len(sections), 1)
        _, body = sections[0]
        self.assertIn("content-visibility: auto", body)
        self.assertIn("overflow-clip-margin: 6px", body)
        self.assertIn("var(--n)", body)

    def test_each_section_says_how_many_rows_its_estimate_is_for(self):
        page = self.page("areas.html")
        sections = r'<section id="c-[^"]+"[^>]* style="--n:(\d+)">(.*?)</section>'
        found = re.findall(sections, page, re.S)
        self.assertGreaterEqual(len(found), 2)
        for n, body in found:
            self.assertEqual(int(n), body.count("<li"))

    def test_a_search_draws_every_section_because_a_drawn_one_keeps_its_height(self):
        page = self.page("areas.html")
        self.assertIn(".searching section { content-visibility: visible; }", page)
        self.assertIn('document.body.classList.toggle("searching", !!s);', page)

    def test_nothing_skips_where_the_clip_margin_is_not_honoured(self):
        gate = "@supports (overflow-clip-margin: 6px)"
        for rel in ("areas.html", "c/dublin.html"):
            css = _stylesheet(self.page(rel))
            for m in re.finditer("content-visibility: auto", css):
                opened = css.rfind(gate, 0, m.start())
                self.assertNotEqual(opened, -1, rel)
                between = css[opened:m.start()]
                self.assertGreater(between.count("{") - between.count("}"), 1, rel)


if __name__ == "__main__":
    unittest.main()
