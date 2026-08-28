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
# listener, that alone.
MARKERS = ("<!--UI-JS-->", "<!--UI-JS-CAPTION-->")


class TestUiGlobals(unittest.TestCase):
    def test_site_script_redeclares_no_shared_global(self):
        shared = statusui.js_globals()
        self.assertIn("bindDayCaption", shared, "the bundle's second file is missing")
        page = "site.html"
        text = (HERE / "esb_site" / page).read_text()
        marker = next(m for m in MARKERS if m in text)
        # everything after the shared script is the site's own
        own = text.split(marker, 1)[1]
        mine = set(re.findall(r"^(?:function|var)\s+(\w+)", own, re.M))
        self.assertFalse(mine & shared, f"{page} redeclares {sorted(mine & shared)}")

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
