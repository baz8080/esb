"""No page script may redeclare a global from statusui's ui.js.

The shared file is inlined ahead of each page's own script, so a redeclaration
silently shadows the shared helper on that page alone.
"""

import re
import unittest
from pathlib import Path

import statusui

HERE = Path(__file__).resolve().parent.parent


class TestUiGlobals(unittest.TestCase):
    def test_site_script_redeclares_no_shared_global(self):
        decl = r"^(?:function|var)\s+(\w+)"
        shared_js = (Path(statusui.__file__).parent / "ui.js").read_text()
        shared = set(re.findall(decl, shared_js, re.M))
        page = "site.html"
        text = (HERE / "esb_site" / page).read_text()
        # everything after the shared script is the site's own
        own = text.split("<!--UI-JS-->", 1)[1]
        mine = set(re.findall(decl, own, re.M))
        self.assertFalse(mine & shared, f"{page} redeclares {sorted(mine & shared)}")

    def test_the_county_page_ships_no_script_at_all(self):
        """It stopped needing any: no day bar to caption, no age to compute.

        Left in, the shared ui.js would be 15 KB of dead weight on every one of
        26 pages that are entered cold from a search result.
        """
        text = (HERE / "esb_site" / "county.html").read_text()
        self.assertNotIn("<!--UI-JS-->", text)
        # the analytics beacon is the one script tag left, and it is not ours
        self.assertEqual(text.count("<script"), 1)
        self.assertIn("cloudflareinsights", text)
