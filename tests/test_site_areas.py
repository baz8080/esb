"""The area pages: what gets one, what it says, and what still does not.

An area was reachable nowhere until 2026-08-27 - the assignment existed on
every outage and was thrown away after naming the search index. These pages
are the long tail the county pages cannot carry, and the interesting half is
the exclusions: the "Around ..." Electoral Divisions would be over a thousand
near-identical pages, which is the failure this surface has to avoid, so the
predicate is guarded rather than trusted.

The other thing guarded here is honesty about attribution. The pin an outage
is filed under is where ESB reported the fault, not everyone it cut power to,
and every area page has to say so and point at its neighbours.
"""

from __future__ import annotations

import csv
import re
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from esb_site import model, render
from esb_site.model import SA_TOWNS_PATH
from tests.test_site_model import SiteModelCase, detail

# Late enough that July, August and September are all in the month list.
SEPT = datetime(2026, 9, 20, 0, 0, 0, tzinfo=UTC)

# Where the fixture coordinates land, resolved by the real index: a city LEA,
# a settlement in the same county, and countryside that only an ED covers.
GLASNEVIN = {"c": "53.36858,-6.27098"}  # Dublin, "Cabra-Glasnevin"
SKERRIES = {"c": "53.5793,-6.1083"}  # Dublin, "Skerries"
RURAL_SLIGO = {"c": "54.1226,-8.1921"}  # Sligo, "Around Ballynashee"


class TestWhichAreasGetOne(unittest.TestCase):
    def test_a_named_place_gets_a_page(self):
        for code in ("19848", "01626", "02341-Cabra-Glasnevin", "04345"):
            self.assertTrue(model.area_has_page(code), code)

    def test_a_bucket_that_is_not_a_place_does_not(self):
        for code in (
            "ed:Carlow:Agha",
            "ed:Cavan:Dunmakeever/Benbrack/Derrynananta",
            "02341-rest",
            "17364-rest",
        ):
            self.assertFalse(model.area_has_page(code), code)

    def test_the_split_over_the_real_csv_is_where_we_left_it(self):
        """The numbers the decision to exclude the EDs was made on. If the CSO
        file changes shape these move, and the choice deserves re-making rather
        than inheriting."""
        codes = {}
        with open(SA_TOWNS_PATH, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                codes.setdefault(r["town_code"], (r["town_name"], r["town_county"]))
        self.assertEqual(len(codes), 3717)
        self.assertEqual(sum(1 for c in codes if model.area_has_page(c)), 904)
        self.assertEqual(sum(1 for c in codes if c.startswith("ed:")), 2808)
        # every ED is "Around somewhere", which is why none of them is a page
        self.assertTrue(
            all(
                n.startswith("Around ")
                for c, (n, _) in codes.items()
                if c.startswith("ed:")
            )
        )

    def test_the_path_is_unique_over_every_area_in_the_file(self):
        """A code is not a filename, so the path is keyed on county and name;
        name alone repeats across counties."""
        codes = {}
        with open(SA_TOWNS_PATH, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                codes.setdefault(r["town_code"], (r["town_name"], r["town_county"]))
        paths = [
            render.area_path(county, name)
            for code, (name, county) in codes.items()
            if model.area_has_page(code)
        ]
        self.assertEqual(len(set(paths)), 904)
        self.assertTrue(all(p.startswith("a/") and p.endswith(".html") for p in paths))

    def test_the_slug_folds_a_fada_rather_than_dropping_it(self):
        self.assertEqual(
            render.area_path("Dublin", "Dún Laoghaire"), "a/dublin/dun-laoghaire.html"
        )


class TestKmLabel(unittest.TestCase):
    def test_it_never_claims_zero_kilometres(self):
        self.assertEqual(render._km_label(0.3), "under 1 km")
        self.assertEqual(render._km_label(4.4), "4 km")


class TestTheDirectoryHeading(unittest.TestCase):
    def test_one_area_is_not_one_areas(self):
        """A from-scratch dataset can leave a county with a single area, and
        the rows two lines down already do the n == 1 dance."""
        one = [("19848", "Testtown", 100, [object()])]
        two = one + [("01626", "Othertown", 200, [object()])]
        self.assertIn("· 1 area ·", render._areas_index_html([("Carlow", one)]))
        self.assertIn("· 2 areas ·", render._areas_index_html([("Carlow", two)]))


class TestCentroids(unittest.TestCase):
    def test_an_uninhabited_area_falls_back_to_the_plain_mean(self):
        """The shipped CSV has no zero-population code, but a regenerated CSO
        extract carrying one must degrade to an unweighted centroid rather
        than crash every esb_site command."""
        index = model.SmallAreaIndex(
            [
                (53.0, -8.0, "Clare", "z1", "Ghosttown", 0),
                (53.2, -8.2, "Clare", "z1", "Ghosttown", 0),
                (52.0, -9.0, "Clare", "z2", "Realtown", 100),
            ]
        )
        lat, lon = index.centroids["z1"]
        self.assertAlmostEqual(lat, 53.1)
        self.assertAlmostEqual(lon, -8.1)
        self.assertEqual(index.centroids["z2"], (52.0, -9.0))


class AreaSiteCase(SiteModelCase):
    """One whole-site build per test: the assertions are about files agreeing
    with each other, which a single page render cannot show."""

    def setUp(self):
        super().setUp()
        self.observe(detail("1"), datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
        # Two ESB ids sharing a location and start: one event, and the row
        # count on the directory has to say so.
        for oid in ("2", "22"):
            self.observe(
                detail(
                    oid,
                    point=SKERRIES,
                    location="Skerries Road",
                    startTime="11/08/2026 09:00",
                    estRestoreTime="11/08/2026 12:00",
                    restoreTime="11/08/2026 11:00",
                ),
                datetime(2026, 8, 11, 10, 0, tzinfo=UTC),
            )
        self.observe(
            detail(
                "3",
                point=RURAL_SLIGO,
                location="Ballynashee",
                startTime="12/08/2026 09:00",
                estRestoreTime="12/08/2026 12:00",
                restoreTime="12/08/2026 11:00",
            ),
            datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
        )
        self.poll(datetime(2026, 9, 1, 0, 0, tzinfo=UTC), n_listed=1)
        outages, _, index = self.load(SEPT)
        self._out = tempfile.TemporaryDirectory()
        self.addCleanup(self._out.cleanup)
        self.out = Path(self._out.name)
        render.write(self.out, outages, index, SEPT, self.until)

    def page(self, rel):
        return (self.out / rel).read_text()

    def text_of(self, page):
        body = re.sub(r"<(script|style).*?</\1>", "", page, flags=re.S)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()


class TestThePage(AreaSiteCase):
    def test_it_is_written_at_its_path_with_a_canonical(self):
        page = self.page("a/dublin/skerries.html")
        self.assertIn(
            f'<link rel="canonical" href="{render.BASE_URL}/a/dublin/skerries.html">',
            page,
        )

    def test_it_needs_no_javascript_to_say_anything(self):
        """The same bar the county pages meet: it must not pull the payload,
        and must carry text rather than a shell."""
        page = self.page("a/dublin/skerries.html")
        self.assertNotIn("data.js", page)
        self.assertNotIn("ESB_DATA", page)
        self.assertNotIn("ESB_CASES", page)
        self.assertGreater(len(self.text_of(page)), 400)

    def test_it_says_the_pin_is_the_fault_not_the_footprint(self):
        """The one thing this page must not overclaim. ESB publishes a point
        per outage - where the fault is, not who is off - so the page states
        the attribution rule instead of pretending it is exact."""
        page = self.page("a/dublin/skerries.html")
        self.assertIn("nearest the fault ESB reported", page)
        self.assertIn("pinned near", page)
        self.assertNotIn("outages in Skerries", page)

    def test_the_list_is_uncapped_and_the_ids_are_merged(self):
        """Two ESB ids sharing a location and start are one event everywhere
        else on the site; a page this small showing them twice would be the
        multi-id bug reintroduced at the one scale a reader would count."""
        page = self.page("a/dublin/skerries.html")
        self.assertEqual(page.count('<div class="case"'), 1)
        self.assertNotIn("not shown here", page)

    def test_it_points_at_its_nearest_neighbours_with_distances(self):
        """The disclaimer made actionable: the reader's one-click check of
        where else their outage may have been filed."""
        page = self.page("a/dublin/skerries.html")
        self.assertIn('href="../dublin/cabra-glasnevin.html"', page)
        self.assertRegex(page, r'<span class="n">\d+ km</span>')

    def test_the_description_is_the_record_first(self):
        """Cut by pixel width, what survives is the front - so the counts and
        the window come first and the inventory claim last, the county pages'
        rule. "Every one of them" is true only while the list is uncapped."""
        desc = re.search(
            r'name="description" content="([^"]*)"', self.page("a/dublin/skerries.html")
        ).group(1)
        head = desc.split(". ")[0]
        self.assertIn("pinned nearby since 31 July 2026", head)
        self.assertIn("Every one of them", desc)
        self.assertNotIn("Every one", head)

    def test_one_fault_is_not_one_faults(self):
        desc = re.search(
            r'name="description" content="([^"]*)"', self.page("a/dublin/skerries.html")
        ).group(1)
        self.assertIn("1 fault and 0 planned power cuts", desc)


class TestTheRestOfTheSite(AreaSiteCase):
    def test_the_directory_lists_and_links_an_area_with_a_page(self):
        page = self.page("areas.html")
        self.assertIn('href="a/dublin/skerries.html"', page)
        self.assertIn("1 outage<", page)

    def test_an_ed_gets_a_row_but_no_page_and_no_link(self):
        """The countryside is real and the directory says so; a link would
        need somewhere to go, and there is deliberately nowhere - hundreds of
        near-identical "Around ..." pages is scaled thin content."""
        self.assertFalse((self.out / "a" / "sligo").exists())
        page = self.page("areas.html")
        self.assertIn("<li>Around Ballynashee", page)
        self.assertNotRegex(page, r"<a[^>]*>Around Ballynashee")

    def test_the_county_page_carries_the_same_rows_one_directory_up(self):
        page = self.page("c/dublin.html")
        self.assertIn("Areas with an outage", page)
        self.assertIn('href="../a/dublin/skerries.html"', page)

    def test_the_app_footer_links_the_directory(self):
        self.assertIn('href="areas.html"', self.page("index.html"))

    def test_the_sitemap_carries_the_area_surface(self):
        sitemap = self.page("sitemap.xml")
        self.assertIn(f"{render.BASE_URL}/areas.html", sitemap)
        self.assertIn(f"{render.BASE_URL}/a/dublin/skerries.html", sitemap)
        self.assertNotIn("ballynashee", sitemap)

    def test_every_area_link_on_the_directory_resolves(self):
        """The build's own link check: a row pointing at a page that was never
        written is a 404 nobody would notice until a reader hit it."""
        for href in re.findall(r'href="(a/[^"]+)"', self.page("areas.html")):
            self.assertTrue((self.out / href).exists(), href)


if __name__ == "__main__":
    unittest.main()
