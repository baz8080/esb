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

Fourteen settlements share their county's name — Carlow, Cavan, Donegal, Kildare, Kilkenny,
Leitrim, Longford, Louth, Monaghan, Roscommon, Sligo, Tipperary, Wexford, Wicklow. They are
excluded from the index by the pre-existing `name != o.county` line, so `a/sligo/sligo.html` is
built and listed in `areas.html` but is not reachable from the box; uisce arrives at the same
place by a different route, where statusui's `name|county` dedup lets the county hit win. Left
as it is: typing a county name almost always means the county, and the county view is the
richer answer. Reopen it only with an answer for what two rows both labelled "Sligo" would say.

`search.js` assigns `ESB_PLACES` rather than `ESB_SEARCH`, and the rename is load-bearing. The
file is fetched on the first keystroke, so a tab opened before a deploy pairs its own inlined
`ui.js` with the current file, and the cache-bust is a query string the server ignores rather
than a version it selects. The old `searchHits` calls `toLowerCase` on an entry, which throws on
the pair, before the dropdown's markup is assigned — leaving it stuck on "Searching…" until a
reload. Renaming with the shape means that reader gets "Search is unavailable - try reloading"
instead, which is the box's own state and tells them what to do. The same rename went into uisce.

No 404 is possible by construction rather than by check: `build` and `area_index` read
the same outage list, so a name only carries a slug when a page was written from the same
events. The test asserts it anyway, since that is the one thing this index must not do.

## The directory stopped being two-thirds unclickable — 2026-08-28

Owner read of `areas.html`. **876 of its 1,270 rows were plain text** — every
"Around ..." ED and every city remainder — because they have no page of their
own, and the footer explained that at the bottom of a very long page:

> *Around …* areas are countryside rather than places, so their history lives on
> the county page instead of a page of their own.

Contradictory as written (the directory does list them), and buried where only a
reader who had already scrolled past all 1,270 rows would find it. The owner's
question answers itself: if their history lives on the county page, link them to
the county page. `_area_items` takes `county_fallback`, and every row in the
directory is now a link — to `a/<county>/<area>.html` where there is a page, to
`c/<county>.html` where there is not.

This is the rule search already follows (§ Search reaches them): a name that
reaches no area page still carries its county's page in the href. The directory
was the one surface that stopped at the plain name. It does not change what gets
a page — `area_has_page` is untouched, and hundreds of near-identical "Around
..." pages is still scaled thin content.

**The county page's own copy of the list keeps them plain**, since there the
link would point at the page it is on. That is the whole of what
`county_fallback` decides.

No `title` attribute naming the destination: 876 of them is 39 KB of hover text
no phone can read (measured — the page went 208.6 → 246.5 KB with it). **One
line carries it instead, under the jump nav where the rows begin:** *"Around …
and Elsewhere in … areas have no page of their own — those links go to the
county page."* Both prefixes, because `area_has_page` excludes the city
remainders as well as the EDs: 874 of the 876 fallback rows are "Around …" and
the other two are Cork's and Galway's "Elsewhere in …" buckets. Same
sentence for every reader, once, at the moment there are links to click; the
header was the other candidate and lost because this is about what a click
does, not about what the page is. Guarded by
`tests/test_site_areas.py::test_the_directory_says_where_an_around_row_lands`,
which also holds it above the first section.

### The footer was three paragraphs and is now one line

- **The definition of an area** (CSO settlement / city LEA / ED countryside) went
  entirely. It is vocabulary for someone building the site, not for someone
  looking up their town, and the rows say "Around ..." in plain sight.
- **The attribution caveat moved to the top**, as `header .sub2`, where the
  index already carries its own caveat in that slot: *"Counts are outages pinned
  to the area nearest each fault ESB reported, not necessarily every outage that
  cut power there."* It is the one thing in the old paragraph a reader needed,
  and the bottom of a 1,270-row page is not where a caveat works.
- **"Areas with no outage at all are not listed: a page of them would say
  nothing"** — dropped on the owner's call. It answers a question nobody asks.

What is left is the shared `Source code · not affiliated` line, as on every
other page.

### Header and spacing

`Every Census 2022 area an ESB Networks outage has been recorded near. Pick one
for its full outage history.` named the CSO's product and buried the instruction
behind a subordinate clause. Now `Search for a place, or jump to a county —
every name links to where its outages are listed`, which is true of all 1,270
rows for the first time.

The gap between the search field and the jump nav measured **42px**: an empty
`#qcount` reserving 1.45em against layout shift, plus the nav's own 18px top
margin. The reserve is right — a count appearing under the field must not shove
the page down mid-search — but one line is enough, and the nav closes up behind
it: 1.2em and a 6px margin, **25px** measured.

## The area page's tail — 2026-08-28

### The attribution note lost a third of its words

It ran to 65 words across two sentences and said the same thing twice. Now 45:

> Outages are filed under the Census area nearest the fault ESB reported. A cut
> that hit Borris may be listed under a neighbouring area, and one listed here
> may reach far beyond it — which is why a row can count more customers than
> Borris has people.

All three facts survive — the rule, that it cuts both ways, and the customer
count that looks impossible without it. `test_it_says_the_pin_is_the_fault_not_the_footprint`
still holds the page to the rule being stated.

### "How to read this page" is gone

It explained that an outage shows a start and a restore, that an unconfirmed end
is marked as an estimate or a last sighting, and that there is no grade at this
level. The first two stopped being news the day the case row started explaining
itself (design-alignment.md § The outage row stopped reading like a database
row): "restored 07:07 (2 h 2 min)" and "no restore time published" need no
key. The third explains an absence — nothing on the page shows a grade, so
nobody is looking for one.

What was worth keeping was the way out to the method, and it is now a clause on
a line that was already there: *"Every area with an outage - the full directory.
Method and sources are on the main page."*

The county page's identical disclosure went the same way on the owner's call —
the two sentences were redundant there for exactly the same reason — and then
its grade paragraph followed. The grade *chip* stays; the four sentences under
it explaining the A–F bands, planned works and storm days did not, and the
county page's footer is now the same two lines as the area page's.

**What the county page loses with that paragraph:** the letter beside the
county name, and the Grade column in its table, are no longer explained
anywhere on the page — only through the "main page" link beside them. A `title`
on each chip would put it back for anyone hovering (~1.5 KB a page, unlike the
39 KB the directory's tooltips would have cost), but it reaches no phone, and
it was not asked for.

### The rule above the footer went with it

With two grey lines under it, the shared `footer { margin-top: 40px;
padding-top: 18px; border-top }` read as a horizontal rule stranded in
whitespace rather than the top of anything.

It was overridden in `area.html` alone for about an hour, until the county
page's footer shrank to the same two lines and `areas.html` turned out to have
been carrying its own copy of the 40px all along. Three copies of one rule is
what moving `.chead + .sub` upstream existed to end, so **the override is now
`site.css`** — `margin-top: 26px`, no border — and **the index opts back in at
the bottom of `site.html`**, restoring base.css's values. That is the one
footer on the site that is a block of prose (the grade, the method, what the
numbers cannot tell you), which is a block worth dividing; the three static
templates just end.

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
