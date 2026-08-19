"""The shared UI under esb_site/ui is a vendored copy of ../statusui/ui.

Edits belong upstream, then `scripts/sync-ui.sh`. Compared file by file when
the sibling checkout is present; skipped otherwise, like the data-dir tests.
"""

import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
VENDORED = HERE / "esb_site" / "ui"
UPSTREAM = HERE.parent / "statusui" / "ui"


class TestVendoredUi(unittest.TestCase):
    def test_matches_upstream(self):
        if not UPSTREAM.is_dir():
            self.skipTest(f"no sibling checkout at {UPSTREAM}")
        for src in sorted(UPSTREAM.iterdir()):
            if src.name.startswith((".", "__pycache__")):
                continue
            with self.subTest(file=src.name):
                copy = VENDORED / src.name
                self.assertTrue(copy.exists(), f"{src.name} not vendored; run scripts/sync-ui.sh")
                self.assertEqual(
                    copy.read_bytes(), src.read_bytes(),
                    f"{src.name} differs from ../statusui; run scripts/sync-ui.sh",
                )

    def test_site_script_redeclares_no_shared_global(self):
        import re

        decl = r"^(?:function|var)\s+(\w+)"
        shared = set(re.findall(decl, (VENDORED / "ui.js").read_text(), re.M))
        for page in ("site.html", "county.html"):
            text = (HERE / "esb_site" / page).read_text()
            # everything after the shared script is the site's own
            own = text.split("<!--UI-JS-->", 1)[1]
            mine = set(re.findall(decl, own, re.M))
            self.assertFalse(mine & shared, f"{page} redeclares {sorted(mine & shared)}")
