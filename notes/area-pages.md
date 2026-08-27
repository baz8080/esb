# The area pages — 2026-08-27

uisce grew `areas.html` and 739 per-area pages on 2026-08-26; this is the same surface for
esb, and the note records what transferred, what deliberately did not, and the one problem
that is esb's own. The build that closed this: **384 area pages** (7.6 MB raw), `areas.html`
at 179 KB standalone, initial load unchanged at 56 KB.

## The assignment already existed

`esb_site/data/sa_towns.csv` and `sa_pop.csv` are byte-identical to uisce's, and
`SmallAreaIndex.place()` has resolved every outage to a settlement since the county work —
the name was used as a display fallback and to feed `search.js`, and the code was thrown
away in `load()`. Shipping this was a render pass, not a model: `place()` now returns
`(county, code, town)`, `Outage` carries `town_code`, and `render.area_index` groups
**merged events** by `(county, code)`. Never raw ids — two ESB records sharing a location
and start are one row here exactly as they are everywhere else, and a page with six rows is
the one scale a reader would actually count them at
(`tests/test_site_areas.py::test_the_list_is_uncapped_and_the_ids_are_merged`).

## The pin is where the fault is — said, not hidden

The semantic gap against uisce: a water notice names a supply area, but ESB publishes a
point per outage, and that point is the fault, not everyone it cut power to. A fault on a
feeder outside town A that blacks out towns B and C is filed under A only, so an area page
can truthfully say little while the village sat in the dark — and an outage listed here can
count more customers than the area has people, because the count is the whole event's.

Rebuilding attribution as a radius footprint would reopen a settled decision
("Nearest-centroid placement, not the water site's radius footprint", grading.md) and was
not considered. The accepted answer is wording plus navigation, on the owner's framing:
this site is an archive rather than a live status service, and people have a reasonable
idea of where their local substation is, so a reader can absorb "check next door too" in a
way an is-my-power-out reader could not.

- Every list heading says **"pinned near"**, never "in".
- A one-line disclaimer above the list states the filing rule and why the customer count
  can exceed the population.
- A **Nearby areas** card lists the `NEARBY_AREAS = 5` nearest areas that have a page, by
  distance between population-weighted centroids, deliberately crossing county lines — a
  border reader's nearest neighbour is often in the next county (Balbriggan's nearest is
  Stamullen, Co. Meath, at 5 km). This is the disclaimer made actionable, and it interlinks
  the pages for crawlers as a side effect. Only page-having areas qualify: a link must have
  somewhere to go.

## What transferred from uisce unchanged

- **`area_has_page`**: named CSO settlements and city LEAs get a page; the 2,808
  `Around …` Electoral Divisions and the five city `-rest` buckets get an index row and no
  page (scaled thin content, and nobody searches "Around Ballynashee"). esb drops its
  unplaced outages before this point, so uisce's unplaced bucket has no counterpart.
- **No outage-count floor**: a permalink that comes and goes is worse than a short one.
- **Paths** keyed on `(county, name)` — a code is not a filename (EDs carry colons and
  slashes) — and slugged with `statusui.slug`, unique over all 3,717 areas (asserted).
- **Uncapped lists** on area pages against the county page's 150: an area accrues a
  handful of events where a county accrues hundreds, and the meta description's "every one
  of them" is only true uncapped.
- **Meta descriptions** state the record first and what the page holds last, so pixel
  truncation cannot make them false.
- The `ul.areas` row markup and CSS, shared between the directory, the county pages'
  "Areas with an outage" card and the nearby card so counts cannot drift between them.

## What deliberately did not transfer

**No grade, no day bar, no CML at area level.** The charter within% is technically
denominator-free, but `MIN_GRADED_FAULTS = 5` per month leaves nearly every area-month
ungraded, and the day-bar buckets divide by a customer denominator that saturates against a
village — the same reasoning uisce recorded when it kept letters and bars at county level.
An area page is a record, not a report card; the county page one link up carries the
judged numbers.

**No app area view.** The app has one hash route (`#county/<name>`) and gains none here;
ED rows on the directory are plain text rather than app links (uisce's EDs link into its
area view, which esb does not have). The app links the directory from its footer, and the
directory is standalone so the first paint carries none of it. Worth revisiting only if the
directory's unlinked majority — the countryside rows — turns out to be what readers want.

## Search reaches them — 2026-08-27

The pages shipped and the one control a reader uses could not reach them: typing
"Newbridge" and clicking the hit landed you on County Kildare, to find Newbridge again
yourself. That was statusui's index shape rather than a routing choice — `searchHits`
returned `[name, county]` and the matched name was discarded — so `pick: go` was the
only thing the callback was given.

`search.js` now stores a Census settlement that has a page as `[name, slug]`, and every
hit is a real link: an area to `a/<county>/<slug>.html`, a county to `c/<county>.html`
with the click kept in the app, the way the county rows already work. The slug is
shipped rather than derived because `ui.js`'s `slug` is not `statusui.slug` and leaves a
fada as a dash; it is trusted for the county half only, which the shard URLs already do.

**The "No app area view" decision above was reconsidered here, for convergence with
uisce, and stands.** uisce has an `#area` view as well as its pages, so the symmetric
answer was to build esb one and route search at it. It earns almost nothing over the
page: the two are the same content, uisce's view has no month tabs and no search box in
it, pushState does not get a drill-down counted in analytics, and the page is indexable,
shareable and middle-clickable where a fragment is none of those. A search hit is an
entry point, not a drill-down, and entry points should be real URLs. So the two sites
converge **on the page**, with the same code in both, and esb needs no route to do it.

Not every name in the index can reach an area, and the dropdown says so. The index holds
ESB's own `location` strings beside the Census names — "Skerries Road" is not a
settlement, and neither is an "Around ..." ED — so those hits go to the county and carry
a "· county" annotation. A hit that quietly does something else is worse than one that
says what it will do.

No 404 is possible by construction rather than by check: `build` and `area_index` read
the same outage list, so a name only carries a slug when a page was written from the same
events. The test asserts it anyway, since that is the one thing this index must not do.

## Residue to watch

- Merge requires an *identical* location string: a fault ESB re-publishes under a varied
  string is two rows, invisible at county scale and glaring on a page with six. Nothing new
  here, but this surface is where it would first show.
- County-boundary splits (deliberate, grading.md) put one physical fault on two counties'
  area pages, once each with its own count.
- uisce's 739 pages cost 15 MB raw, mostly inlined CSS; esb's 384 cost 7.6 MB. The
  size report prints both new lines every build. Re-decide the inlining past a thousand
  pages, as uisce's note already says.
- The `ul.areas` rules are now wanted identically by two sites, which by statusui's own
  rule makes them base.css material; promotion (and moving `_area_items` upstream with
  them) is the follow-up, kept out of this change so the surface could ship against the
  pinned statusui.
