"""The shared drill-down sub line, asserted to apply rather than to exist.

`.chead + .sub` styles the line under a county heading — here, the customer
count and the data stamp on every `c/<slug>.html`. It lives in statusui's
base.css and reaches this repo only through the pin in `uv.lock`.

This repo carried a byte-identical copy in its own site.css until 2026-08-26,
and when the rule moved upstream that copy had to be kept back for one commit,
because `uv.lock` can only track statusui's `main`. Dropping both at once would
have left the line unstyled on the deployed site with every test still green:
nothing asserted a rule *applied*, only that files said what they said.

Three things make a rule apply, and a build can check all three without a
browser: the page renders an element for it to match, the rule is in the
stylesheet that page inlines, and nothing in the cascade beats it. base.css also
carries `header .sub`, which sets the same two properties, so the third is a
real question rather than a formality.
"""

from __future__ import annotations

import re
import unittest
from datetime import UTC, datetime
from pathlib import Path

import statusui

from esb_site import model, render

SHARED = {"color": "var(--muted)", "font-size": "12.5px", "margin-bottom": "16px"}


def _county_page():
    index = model.SmallAreaIndex.load()
    now = datetime(2026, 8, 31, tzinfo=UTC)
    data, _, months, _ = render.build([], index, now, now)
    return render.county_page("Dublin", data, {}, months, now, index.counties)


def _stylesheet(page):
    """What the page inlines: assemble() puts base.css and site.css in a <style>
    block, so this is the whole stylesheet a browser would apply."""
    css = "\n".join(re.findall(r"<style>(.*?)</style>", page, re.S))
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _specificity(sel):
    return (
        len(re.findall(r"#[\w-]+", sel)),
        len(re.findall(r"\.[\w-]+|\[[^\]]*\]|:(?!:)[\w-]+", sel)),
        len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", sel)),
    )


def _winner(css, prop):
    """The value the cascade leaves standing on a `.sub`, or None if nothing
    sets it.

    Only a selector's subject is read; an ancestor or sibling part is assumed to
    match, which can only make this stricter than the browser. A rule inside an
    @media block is counted as competing whatever its condition, for the same
    reason — neither file puts a `.sub` rule in one today.
    """
    rules = []
    for order, (prelude, body) in enumerate(re.findall(r"([^{}]+)\{([^{}]*)\}", css)):
        decls = re.findall(rf"(?:^|;)\s*{re.escape(prop)}\s*:\s*([^;]+)", body)
        if not decls:
            continue
        for sel in (s.strip() for s in prelude.split(",")):
            if re.split(r"[\s>+~]+", sel)[-1] == ".sub":
                rules.append((_specificity(sel), order, decls[-1].strip()))
    return max(rules)[2] if rules else None


class SharedSubLineCase(unittest.TestCase):
    def test_the_page_renders_an_element_the_rule_can_match(self):
        """A rule with nothing to match is a rule that does not apply. The
        lookahead keeps the closing tag the `.chead`'s own, so a nested div
        could not fake the adjacency."""
        page = _county_page()
        self.assertRegex(
            page, r'<div class="chead">(?:(?!</?div).)*</div>\s*<div class="sub"'
        )

    def test_the_shared_values_win_on_that_page(self):
        css = _stylesheet(_county_page())
        for prop, expected in SHARED.items():
            with self.subTest(prop=prop):
                self.assertEqual(
                    _winner(css, prop),
                    expected,
                    f"{prop} on the county page's sub line is not the shared value;"
                    " the rule from statusui either never arrived or lost the cascade",
                )

    def test_the_rule_is_upstream_and_has_not_been_copied_back(self):
        """Three byte-identical copies across three repos is what moving it to
        statusui existed to end."""
        self.assertIn(".chead + .sub", statusui.base_css())
        self.assertNotIn(".chead + .sub", Path(render.SITE_CSS).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
