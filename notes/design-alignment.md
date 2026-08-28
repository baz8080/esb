# Aligning the design language with uisce

2026-08-26. The owner reviewed both home pages side by side and picked a winner
per element, so the two sites read as one product before the same language is
applied to lifts. What esb absorbed:

- **Banner** takes uisce's format: `**August 2026 so far:** 978 faults and
  1,122 planned outages` — the bold month-and-colon prefix, the long month
  name, and " so far" only while the viewed month is still collecting
  (`D.observed_iso` month == viewed month). The old trailing "in Aug 2026" and
  the all-bold single `<strong>` went with it.
- **National heading** takes uisce's format: "The national picture in August
  2026", filled per month, replacing the static "Nationally this month" which
  read wrong on every past month.
- **Footer**: "How the grade is worked out" and "The other figure: Customer
  Minutes Lost" merged into one disclosure, "How these numbers are worked out",
  and every disclosure was tightened for a lay reader — the measured detail
  (1,460-outage back-dating check, 8 revisions, the 30-minute poll mechanics)
  lives in `notes/grading.md`, not the page. The final line is now the shared
  format: "Source code · not affiliated with ESB Networks or the CRU."
- **The horizon left the footer** — an owner decision, reversing the earlier
  "the exact horizon stays in the footer" note. "Built twice daily … Data to
  Wed 26 Aug, 06:04 UTC." was removed; the age chip stays, and the exact
  horizon survives as the chip's hover `title` and, in full, in each county
  page's sub line (which is a cold-entry surface and keeps its no-JS text).
- **Search behaviour moved upstream** to statusui (`searchHits`/`bindSearch`);
  this page keeps only the markup, the index build and the pick handler. uisce
  gets the same box in place of its sort control.
- `site.css` shrank: `--row-cols`/`--stats-cols` (identical to base),
  `.stats .cml` and the mobile legend-order override all moved into (or were
  already in) statusui's base.css, because uisce wanted the same values.

esb's own layout was the reference for the county rows (chevron, two-line
percentage stat, right-aligned counts) and the county-page card
(legend → tall bar → tiles), so nothing changed here on those.

## The county page got a way in from the app — 2026-08-26

The app never linked to `c/<slug>.html`. The page linked into the app ("open the interactive view"), so it was a one-way trip, and the missing leg was the one that matters: a reader already looking at Cork had no way to reach Cork's durable address.

`renderCounty` now carries a link on its own line under the heading, above the month tabs — the placement lifts uses and uisce adopted at the same time. The rule that styles it, `.chead + .sub`, is promoted to statusui's `base.css`; this repo and lifts had been carrying it byte for byte and uisce is now a third consumer. The local copy went with the pin bump that followed.

Placed above the tabs rather than below despite the risk of reading as a tab modifier: the `margin-bottom: 16px` on `.sub` separates them, and matching the other two sites was worth more than the residual ambiguity.

**Wording: "Every month for County Cork on one page", not "permalink".** The label makes a promise, so it has to match what is actually on the other side. This view is one month at a time; the page — since it became an archive earlier the same day — is every month plus the outage history. Naming that difference gives a reader a reason to follow the link.

**uisce says the same sentence**, because its county page stands in the same relation to its county view: one month there, every month here. It briefly said "Every notice ever recorded in Co. Carlow" instead and that was wrong — its page caps the notice list at 60 and prints "older notices not shown here", so the label was contradicted by the page it landed on. Two categories, not three: esb and uisce name the months; lifts says "Permanent link to Athy station", because its page carries the same months and cases its view does and naming *that* for its content would promise something the reader is already looking at. Same placement on all three.

"Permalink" was rejected here for two reasons: it undersells a page that now has more than the view, and it is blogging-era vocabulary a general audience mostly does not hold. The county is in the link text because a screen reader lists links stripped of their context.

The overview row's `<a href>` already pointed at the page with the click suppressed, so a crawler and a "copy link address" always reached it; this closes the gap for a reader who has already drilled in.

Guarded by `tests/test_permalink_affordance.py`.

### The meta description had the same shape as the link

"Power cuts recorded in County Cork since 31 July 2026: 95 faults and 139 planned outages…" — the colon made the counts read as an inventory of the page, and the page lists `COUNTY_PAGE_CASES` of them. Not false the way uisce's link was, since it never claimed a listing, but a reader arriving from that snippet would expect 234 outages and find 150 plus "84 older outages not shown here".

Now: "County Cork: 95 faults and 139 planned power cuts since 31 July 2026. Month-by-month totals and the most recent outages, from ESB Networks' PowerCheck feed." The counts are stated as the county's record and what the page holds is named after them.

**Ordered so that truncation cannot make it false.** A snippet is cut by pixel width, not character count, and what survives is the front. Cut anywhere in the second sentence, this reads "County Cork: 95 faults and 139 planned power cuts since 31 July 2026" — still true. The old one truncated back into an inventory claim, which is the failure the reordering exists to prevent. 155–160 characters across all 26 counties, so the tail that goes is the source attribution, which is the right thing to lose.

Guarded by `tests/test_permalink_affordance.py::DescriptionCase`, including the truncation property and the length ceiling.

## The copy and consistency pass — 2026-08-27

Driven from uisce, whose live pages were read end to end; the findings that were not
uisce-specific were applied here the same day. The two sites' static pages are close enough
that most of them were the same finding twice.

### The county page lists every outage — `COUNTY_PAGE_CASES` is gone

The cap was 150, and the page carried "N older outages not shown here — open the interactive
view" underneath. A page whose whole purpose is to be the durable, indexable record of a
county should not be the one surface that holds a fraction of it. Both went; `county_page`
renders `cases` rather than a slice of it.

Measured on the August 2026 corpus, rebuilt from `../esb-data`: the largest county page
(Cork) goes **100.7 KB → 127.4 KB**, and the 26 pages together 1,767 KB → 1,825 KB. That is
well inside anything a static host cares about.

The original comment's objection stands and is worth writing down rather than deleting: *the
archive grows without bound and nothing now bounds the page.* The bound to reintroduce, if
one is needed, is a **byte budget rather than a count** — a count was always a proxy for
bytes and a poor one, since a row's width varies with the location string.

`desc` moved with it: "Month-by-month totals and every outage recorded". The record-then-
listing ordering stays for the reason design-alignment.md § the meta description already
gives — a snippet cut by width has to leave a true sentence behind — but the clause it is
protecting is now true rather than merely careful.

### One name per thing

- The area page's "Elsewhere" block dropped to two links: the county's whole record, and
  `County X's interactive view`. The directory link it gave up moved into the footer of
  `county.html` and `area.html`, where uisce's static pages already carried one and this
  site's did not.
- Heading counts read `· N outages` / `· N areas`. The static pages printed a bare `<span
  class="n">150</span>`, which is a number with nothing saying what it counts; the directory's
  own section headings were already in the target format. Row counts inside `ul.areas` keep
  their bare `N outages` — a row with a dotted leader is not a heading.

### `ul.areas` was indented 40px by the user agent

`base.css` resets `margin` and not `padding`, so `list-style: none` removes the marker and
leaves the gutter it sat in. The rule takes its own padding back now. uisce had the same bug
in the same rule plus in `ul.notices`, which is what turned it up. This does not change the
promotion follow-up in `notes/area-pages.md` — it makes the two copies agree again, which is
the precondition for promoting them.

### Not changed here

The footers already read `Source code · not affiliated with ESB Networks or the CRU.` on
every page, and the app is already called "the interactive view" rather than a map. uisce
moved to this site's wording on both counts, not the other way round.

## The tiles say what they mean — 2026-08-28

Owner read of the national tiles, in a reader's voice. Two of the four were
written for someone who already knows the domain.

### `154 CML` / `annualised, unplanned`

Three pieces of jargon in five words. **CML** is expanded exactly once on the
page, in a footer disclosure most readers never open, so on the tile it is four
letters that mean nothing. **Unplanned** is redundant: CML is a fault index by
construction — planned works are excluded everywhere on this site, and the tile
sits beside another that says "customers hit by faults". **Annualised** is the
word a reader has no way to decode.

The first pass kept the annualisation and said it in plain words — "customer
minutes lost a year" — because dropping it made the tile false: 154 is a
month's rate stretched to twelve months, and under a heading reading "The
national picture in August 2026" a bare "customer minutes lost" claims the
average customer lost 154 minutes *in August*, about twelve times the truth.

That fix was wrong at a level the wording could not reach, and the owner named
it: **why is a yearly figure sitting among monthly ones at all?** The other
three tiles, the day bar, the counts, the county rows and every month row on
`c/<slug>.html` are a month. One tile on a year's clock is a second clock on the
same surface, and no label short enough for a 150px tile can carry that without
"monthly"/"annually" headings the owner ruled out.

So the tile shows **the month's own minutes per customer**: `12.8` / `customer
minutes lost`. Same measure, same window as everything beside it. `national_cml`
takes `annualised=False` for it, and `county_month` already computed both —
`c/<slug>.html`'s month table moved to `cml_month` in the same change, and its
column is headed "Minutes lost" rather than "CML" for the same reason as the
tile.

**The annualised rate did not disappear; it moved to the one place it can be
read.** The "How these numbers are worked out" disclosure is where the page
argues about ESB's published 117.47 for 2024, so it now carries this site's own
whole-corpus rate as `cmp-cml`, alongside the CI bias and CAIDI figures already
filled from the build: *"the comparable figure is this site's rate across
everything collected, about N a year."* A year's number in a paragraph about a
year, and nowhere else.

Dropping the tile outright — the owner's other option — was rejected because
what it measures is the site's whole subject: minutes off supply for the average
customer. It was the annualisation that made it unreadable, not the measure.

Guarded twice: `tests/test_site_model.py::TestCountyMonth` holds the payload row
to `cml_month` and asserts the annualised figure is the larger, different number
it is; `tests/test_site_national.py` derives `compare["cml"]` independently, as
it already did for CAIDI and the bias.

### `54 years` / `of customer time off supply`

The question it drew was "54 years since when?" — and the tile is one month.
This is customer-time, customers multiplied by the hours they were off, so the
first pass put the "customer" into the unit: `54` / `customer-years off
supply`, with a `customerTime` helper rolling hours up into days and then years
so the number stayed small.

**That was still wrong, and not subtly: the word "years" was printed on the
tile.** Under a heading reading "The national picture in August 2026", beside
three figures that are all August's, one tile said *years*. A reader does not
have to misread anything to be stopped by that — the year is on the page, in
plain sight, and the label is 12.5px under a 24px number with no room to say
what it is doing there. "Not annual, it is a product unit" is a true answer and
a useless one: it explains the tile instead of fixing it.

The quantity was never annual: 311,321 customers off supply for their various
spells during August add up to 473,067 customer-hours, which *is* 54
customer-years, all of it accrued inside August. A product unit has no upper
bound in calendar terms — 2.5M customers off for one hour is 285 customer-years
in an hour — which is exactly why naming it after a calendar span is the wrong
choice on a page organised by calendar months.

So the unit is now always **customer-hours**: `473,067` / `customer-hours off
supply`. Hours are the one time unit that cannot collide with the calendar —
nobody reads 473,067 hours as a span of the month — and "customer-hours" is
the standard industry form of exactly this quantity. `customerTime` is gone
with its two rollup branches; the tile is `num(Math.round(n[4]))`, which is
also the whole of what the payload already carried.

The number is large, which was the original objection to printing hours
("17215 days reads as nonsense") — but that objection was about *days*, a unit
a reader will try to place in a 31-day month. A big number in an unambiguous
unit beats a small one in an ambiguous unit, and `num()` gives it thousands
separators; 7 characters at 24px fits the 150px column.

The month is left to the heading directly above the tiles, as it is for the
other three: "this month" on one tile would be wrong the moment a reader picks
an earlier month tab.

**This tile and the CML tile are the same quantity** — customer-hours ÷ 2.5M
customers, in different units — which the annualisation used to disguise. Both
stay: one is the national total, the other is what it meant for the average
customer, and per-capita beside total is a pair a reader can use. Replacing
this one with something independent (faults past the 24-hour compensation mark
is the obvious candidate) was raised and declined by the owner.

## What the footer stopped saying — 2026-08-28

Two passages went, on the same read.

**"The site is built twice daily from snapshots of ESB Networks' public
PowerCheck feed, which keeps no history of its own."** The build cadence is
already answered where a reader would ask it — the banner says how old the data
is and warns when it goes stale. The sentence it was attached to is the page's
statement of what the grade means, and this was operational trivia sitting at
the end of it. The sentence "Planned works are excluded" went with it from that
disclosure; the next one along still says it, with the reason attached.

**"ESB opens a new record each time a fault's scope changes, so records sharing
a location and start time are folded into one outage here. A fault that returns
to the same spot is a separate interruption and stays a separate row, tagged as
a repeat."** True, load-bearing, and not footer material: it explains the shape
of ESB's feed to a reader who came to find out whether the power is back. It is
already written down where it belongs — `notes/grading.md` § One ESB event is
one row and § Repeat faults are not splits, with the counts and the rejected
merge rules. The "Repeat fault - outage 2 of 3 at this location in quick
succession" tag on the row explains itself in place.

## The outage row stopped reading like a database row — 2026-08-28

Owner read of `c/<slug>.html`: *"it's like reading a database row"*, with
`span.when` — the right-aligned duration — named as the worst of it. Sometimes
present, sometimes not, never adding clarity. Two options were put: build a card
display, or make the row explain itself. The row is already a card; what it
lacked was English, so the second.

### `span.when` is gone

It carried "off 3 h 46 min", "scheduled 4 h 34 min", or nothing at all — a
number floating at the end of a line, disconnected from the timestamp it
measured, and blank on 40% of rows (planned works that left the feed early).
The span now sits inside the phrase that names the end it belongs to:
`scheduled until 15:00 (4 h 34 min)`. `.case .when` stays in statusui's
`base.css` for the other two sites; this one no longer emits it.

### One phrase per shape, and the shapes are not evenly weighted

Measured on 2,336 merged events:

| shape | share | reads |
|---|---:|---|
| planned, delisted | 39.7% | `listed for about 7 h · no end time published` |
| fault, restored | 36.6% | `restored 07:07 (2 h 2 min) · 2 h 8 min earlier than ESB estimated` |
| planned, scheduled end | 15.0% | `scheduled until 15:00 (4 h 34 min)` |
| fault, delisted | 6.0% | `off for under 30 min · no restore time published` |
| fault, estimate only | 2.7% | `expected back by 04:15 (about 1 h) · no restore time published` |

**"last seen out at 08:31" and "last listed at 15:00" are gone.** Both printed
the clock time of a *sighting*, leaving the reader to subtract it from the start
time to get the thing they wanted. The sighting's clock time was never the
interesting half: what the data measured is a span, so the span is what it says
— "off for" a fault, "listed for" scheduled works, since time on ESB's list is
not a claim about time off supply.

**"not confirmed" is gone.** It was ambiguous exactly where it needed not to be:
unconfirmed *estimate*, or unresolved *outage*? It meant neither — it meant ESB
published no restore time. That is what the row says now.

**A restore is compared to the estimate, not printed beside it.** "ESB's
estimate was 15:00" made the reader do the arithmetic. 69% of restored faults
beat the estimate (median 58 min early) and 25% miss it (median 54 min late), so
how it landed is the most interesting fact available: `2 h 8 min earlier than
ESB estimated`. Inside five minutes either way (5% of them) the clause is
dropped as noise.

`N customers` became `N customers affected`, which is what the number means.

### The reason moved into the tag, with a label

`Tullow [Planned] … · divert an overhead line` put the row's most human fact in
its least-read position, in ESB's own shouted phrasing. Now
`Tullow [Planned · line diversion]`.

ESB publishes a closed set of six reasons, all in block capitals, mapped in
`model.PLANNED_REASONS`:

| feed | shown | events |
|---|---|---:|
| IMPROVE QUALITY OF SUPPLY | supply quality | 518 |
| UPGRADE THE NETWORK | network upgrade | 262 |
| CONNECT NEW CUSTOMERS | new connections | 204 |
| IMPROVE THE NETWORK | network improvement | 66 |
| DIVERT AN OVERHEAD LINE | line diversion | 51 |
| SUPPORT FIBER ROLLOUT | fibre rollout | 1 |

An unmapped seventh falls back to its own text lower-cased, so a new reason
renders as itself instead of vanishing until someone notices.

**Why the site and not a column in `esb.db`.** The database is disposable and
rebuilt from the logs; a label baked into it needs a rebuild to change, which is
the wrong cost for a copy decision. The collector is also the half that has to
keep running on a Raspberry Pi on the standard library, and its job is capture,
not interpretation — nothing is parsed before it is written. A dict in
`esb_site/model.py` is testable, changeable in a commit, and degrades to the raw
text when the feed surprises it.

### The 177 planned events with no reason: there is nothing to glean

15% of planned records carry an empty `plannedOutageReason`. The only other free
text on the record is `statusMessage`, and it is the same apology on 1,313 of
the 1,322 planned records — *"we are carrying out essential improvement /
maintenance works in your area"* — so it distinguishes nothing. `plannerGroup`
is a depot, not a purpose. Those rows say `Planned` and stop; inferring
"maintenance" from boilerplate every planned outage carries would be inventing a
distinction the feed does not draw.

Guarded by `tests/test_site_model.py::TestCaseCopy`, one test per shape.
