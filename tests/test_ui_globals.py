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
        for page in ("site.html", "county.html"):
            text = (HERE / "esb_site" / page).read_text()
            # everything after the shared script is the site's own
            own = text.split("<!--UI-JS-->", 1)[1]
            mine = set(re.findall(decl, own, re.M))
            self.assertFalse(mine & shared, f"{page} redeclares {sorted(mine & shared)}")
