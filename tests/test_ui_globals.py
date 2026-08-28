"""No page script may redeclare a global from statusui's shared bundle.

The bundle is inlined ahead of each page's own script, so a redeclaration
silently shadows the shared helper on that page alone.

The names come from `statusui.js_globals()`, never from reading `ui.js`: the
bundle is two files since the caption listener moved to `caption.js`, and a
test that reads one of them passes by seeing fewer names - a guard failing
open, silently, exactly when it stops covering something.
"""

import re
import unittest
from pathlib import Path

import statusui

HERE = Path(__file__).resolve().parent.parent

# A page takes the whole bundle or, if all it calls is the day-cell caption
# listener, that alone. From statusui, not spelled out here: a marker it
# renamed would leave this test looking for a string no page carries, and
# passing because it found nothing to check.
MARKERS = (statusui.UI_JS, statusui.UI_JS_CAPTION)


def declares(script, name):
    """Does this script declare `name` at the top level?

    Asked per name rather than by listing what the script declares, because
    listing misses the second name in `var a = 1, esc = 2;` - a form this
    site's own script uses - and a guard that misses a name fails open.

    Column zero only, which is what top level means in these files: a
    declaration inside a function body is scoped to it and shadows nothing.
    The `=` in the second branch is what makes a name a declaration rather
    than a mention: a shared helper passed by reference reads as `, esc]`.
    """
    n = re.escape(name)
    return bool(
        re.search(rf"^(?:async\s+)?(?:function|var|let|const|class)\s+{n}\b", script, re.M)
        or re.search(rf"^(?:var|let|const)\b[^\n]*,\s*{n}\s*=", script, re.M)
    )


def unreadable_declarations(script):
    """Top-level declarations this guard cannot read, so it can say so.

    It reads a line at a time, which covers every form these pages use - a
    multi-line object literal still declares its one name on the first line.
    What it cannot follow is a declarator list continued onto the next line,
    or a destructuring pattern. Neither appears in any of the three sites
    today; the point is that the day one does, this stops rather than quietly
    missing whatever the second name was.
    """
    for line in re.findall(r"^(?:var|let|const)\b[^\n]*", script, re.M):
        # A trailing comma inside an open bracket is a literal continuing, not
        # a second name: `var CELL = { 0: "nothing listed",` is one declaration.
        open_brackets = sum(line.count(c) for c in "{[(") - sum(line.count(c) for c in "}])")
        if (line.rstrip().endswith(",") and open_brackets <= 0) or re.match(
            r"^(?:var|let|const)\s*[\[{]", line
        ):
            yield line.strip()


class TestUiGlobals(unittest.TestCase):
    def test_site_script_redeclares_no_shared_global(self):
        shared = statusui.js_globals()
        self.assertIn("bindDayCaption", shared, "the bundle's second file is missing")
        page = "site.html"
        text = (HERE / "esb_site" / page).read_text()
        marker = next(m for m in MARKERS if m in text)
        # everything after the shared script is the site's own
        own = text.split(marker, 1)[1]
        self.assertEqual(list(unreadable_declarations(own)), [], f"{page}: see the docstring")
        clashes = sorted(name for name in shared if declares(own, name))
        self.assertFalse(clashes, f"{page} redeclares {clashes}")

    def test_the_county_page_ships_no_script_at_all(self):
        """It stopped needing any: no day bar to caption, no age to compute.

        Left in, the shared ui.js would be 15 KB of dead weight on every one of
        26 pages that are entered cold from a search result.
        """
        text = (HERE / "esb_site" / "county.html").read_text()
        for marker in MARKERS:
            self.assertNotIn(marker, text)
        # the analytics beacon is the one script tag left, and it is not ours
        self.assertEqual(text.count("<script"), 1)
        self.assertIn("cloudflareinsights", text)
