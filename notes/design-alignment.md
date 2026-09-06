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

## The county page became an archive and nothing else — 2026-08-28

Owner read of `c/<slug>.html`. Two things on it belonged to a different page.

### The header's age line is gone

`Updated 11 hours ago · Data to 27 Aug, 23:02 UTC` sat under the county name.
It was the last survivor of the horizon's retreat (2026-08-26: out of the
footer, kept here because a county page is entered cold from a search result).
It is out of the header now too, and with it the `#stamp` span, its
`data-observed`/`data-stale-hours` attributes and the `freshness()` call.

**The cost, stated plainly: a county page no longer warns that collection has
stopped.** What is left is static and still true — the month table's newest row
carries `to 27 Aug` under its own name, so a record that stops advancing shows
as a month table that stops advancing. The index keeps the live banner. If the
warning is wanted back here, it is a `freshness()` call and the 15 KB of script
that went with it.

### The newest month's card is gone

The page opened with a card for the latest month alone: heading, legend, day
bar, four tiles. Two objections, and the second is the fatal one.

- **Wrong scale.** One month's day-by-day detail on the page whose whole reason
  for existing is *every* month. The interactive view is where a month is the
  unit; this page is the record.
- **It was a duplicate.** Every figure in those four tiles — restored within
  4 hours, faults, planned, customers hit — is the first row of the
  month-by-month table immediately below it. The page led with a copy of its
  own next section, and the section that matters was pushed below the fold.

`c/cork.html` now opens: back link, grade chip and county name, the customer
count, then **Month by month**. 127.4 KB → 106.3 KB.

The grade chip stays on the owner's call, but it is still the newest month's
letter and the card that used to name that month is gone — so its hover title
names it: *"Grade B in August 2026: 90% or more restored within 4 hours"*.
Without that a bare "B" reads as the county's standing for all time, which is
the one thing an archive page must not imply.

### The county page ships no JavaScript at all

With no day bar to caption and no age to compute, `bindDayCaption()` and the
stamp script were the page's only behaviour, and statusui's `ui.js` was inlined
for them alone. Both `<script>` blocks are gone: **county pages 1,840 KB →
1,349 KB across 26 files**, a 15 KB saving per page on pages that are, by
design, entered cold from a search result. The only `<script>` left is the
analytics beacon, which is not ours.

`render._legend_html`, `render._day_cells`, `DAY_LABELS` and `LEGEND_ITEMS`
went with the card — nothing else rendered a bar from Python. The app keeps its
own copies (`legendHtml`, `dayCells` in `ui.js`), which is where day bars now
live exclusively. Guarded by
`tests/test_ui_globals.py::test_the_county_page_ships_no_script_at_all`.

### Already done, on this branch

Two items in the same review were fixed earlier and are visible only after a
rebuild: the month table's `CML` column became **Minutes lost** carrying the
month's own figure (3451f8f), and the case rows got the sentence treatment
(73be525) — the static county page renders through the same `_case_html` as
every other page, so it was never a separate fix.

## The county table carries the 24-hour count the footer promised - 2026-09-05

The footer has said since 2026-08-28 that outages past the charter's 24-hour
compensation mark "are counted separately on each county page". They were not.
`county_month` computed `over_compensation`, `render.build` packed it as the
eighth field of every county-month row in `data.js`, and neither the app nor the
county page read it. The sentence was written for a count the tiles decision
above then declined to show (§ The tiles say what they mean: replacing the
customer-hours tile with it "was raised and declined by the owner"), and nobody
went back to the footer.

**It is now a column in the county page's month table**, `Over 24 h`, between
Faults and Planned, with the charter named in the heading's hover the way
"Minutes lost" carries its own definition. Read off the same payload row as the
rest of the table, so the app and the page cannot disagree about a month. The
count is the one `grading.md` settled: a fault still out past the mark counts,
because the time it has already run is a lower bound.

On the corpus to 5 September: 6 faults over 24 hours across 1,387, 3 of them
with a confirmed restore. A column that is 0 on nearly every row is legible in a
table, which is where a rare count belongs.

Rejected:

- **A fifth tile in the app's county view.** Twenty-five counties would carry a
  tile reading 0 most months, and a tile exists to be read. The national tile
  was declined on the same day for the same reason, and that decision stands.
- **Dropping the footer sentence instead.** The count is the most useful
  independent fact the payload already held, and the sentence was right about
  where it belongs: the county page is the archive, and the 24-hour mark is an
  archive fact.
- **A bare "24 h" heading.** Beside "Restored in 4h" and "Faults" it reads as a
  duration; "Over 24 h" plus the hover reads as a count of faults.

## An outage still out says so - 2026-09-05

`Outage.ongoing` has decided since 2026-08-18 whether a fault is judged on the
charter (grading.md § An outage still listed), and `case_record` dropped it. A
fault still out at the horizon rendered as "off for about 2 h · no restore time
published", the same words as one that had quietly left the feed, and its
estimate was thrown away with it: `case_record` shipped `est` only beside a
confirmed restore. So the one row a reader most wants to read, the live one,
was the row that told them least.

The record carries a twelfth field, `ongoing`, and ships the estimate whenever
that is set. `_end_bits` and its mirror `endBits` take the flag before any
other shape, and the row says what is known:

| Shape | Fault | Planned |
|---|---|---|
| no estimate | still out when last checked · no estimate published | still listed when last checked · no end time published |
| estimate ahead | still out when last checked · expected back by 07:30 | scheduled until Wed 9 Sep, 17:00 (7 days) · still listed when last checked |
| estimate passed | still out when last checked · past ESB's estimate of 00:15 | the same schedule wording; a listing is not an observed outage |

The three faults ongoing at the 5 September horizon happened to be one of each:
Kilkee with no estimate, Kilcock expected back at 07:30, and Carrigaline five
hours past its 00:15 estimate. Templeogue's planned works had read "listed for
about 3 days · no end time published" while ESB had them scheduled to the 9th
all along.

**No span for a live fault.** "Off for about 2 h so far" was the first draft.
The end of an ongoing outage is the collection horizon, and where the model
ended it on a passed estimate (`end_src == "estimated"`) the span would stop at
the estimate rather than at the last sighting, understating by up to the
distance between them. The row already says when it began; the age of the data
is on the banner and in the month table's "to 5 Sep". Planned works keep their
span because theirs measures the schedule, which is the one duration ESB
actually states.

**"When last checked", not the horizon's clock time.** The exact horizon left
the county page on 2026-08-28 and this does not bring it back; the phrase names
the fact without a timestamp the page has decided not to carry.

### What review of the first cut found

Three shapes the single-id tests did not reach, all fixed at the source rather
than in the wording:

- **A merged event with a restored ender and a sibling still listed** was
  `ongoing` by `any()` over its members, so the row said "still out when last
  checked · past ESB's estimate of 01:52" for an outage ESB confirmed restored
  at 01:52, and the event sat out of the grade for one build. Seven groups in
  the corpus hit this shape at the build after their restore. `_merge_group`
  already treats a sibling lingering a poll cycle past a confirmed restore as
  the feed catching up; `ongoing` now follows the ender, as `end` always did.
- **"No estimate published" when the ender had none and a sibling did.** The
  ender is the record listed latest, not the one ESB put a time on; seven
  unrestored groups had that shape. A live event now borrows the latest
  estimate over its members when its ender carries none. The settled rule that
  the ender's estimate wins (grading.md, stale figures resurrected by `max()`)
  is about records that closed and is untouched.
- **"Expected back by" was judged against the row's end**, which for a listed
  outage is the last sighting, up to a poll cycle before the horizon. An
  estimate in that gap has passed by the data's own clock. The comparison is
  now against the horizon, which the app has as `D.observed_iso` and the static
  pages take from the same payload field; `_case_html` takes it as an argument
  rather than defaulting, so a caller cannot fall back to the sighting by
  accident.

Rejected: a tag label ("Fault · still out"), the way a planned reason rides in
the tag. The tag names what the outage is and the summary line says what
happened to it, and a live fault is a state of the second kind.

Residue: 167 of the 179 delisted faults carried an estimate that lay *after*
their last sighting - ESB dropped them before the time it had named - and that
estimate is still not shipped for them. A row for one says "off for about 4 h ·
no restore time published"; whether it should also say what ESB had expected is
a separate question with a separate shape.

## The site says how good ESB's estimates are - 2026-09-05

Every outage row has said "2 h later than ESB estimated" since 2026-08-28, and
nothing added those up. The estimate is the one number a customer actually
plans around, and nobody publishes how often it holds. On the corpus to
5 September, 1,079 of 1,129 restored faults carried one.

**The figure is "restored by ESB's first estimate"**: the share of faults,
among those with a confirmed restore and an estimate, back no later than five
minutes after the first restore time ESB named. It sits beside "restored within
4 hours" everywhere that appears: a tile on the national view and the county
view, and a column in the county page's month table. The footer's method
disclosure defines it in two sentences.

Choices, with the numbers behind them:

| Choice | Taken | Measured |
|---|---|---|
| First estimate or last | **first**, `Outage.first_est` | 63.6% against the first, 74.4% against the last. 192 of the 973 single-id faults had their estimate revised, and 156 of those revisions came after the previous time had already passed: a revision is mostly ESB pushing back a time it missed, and scoring against it credits the miss. "Kept unless some estimate passed while still out" was measured too, at 67.3%, and rejected as a rule nobody could state in a tile's label |
| Per outage or per customer | **per outage** | 74.6% per outage against 83.4% customer-weighted, on the last estimate: large faults keep their estimates more often, and weighting by customers would report the big outages' record as everyone's. An estimate is one statement about one outage, and that is how a customer meets it |
| Grace | **five minutes**, `ESTIMATE_GRACE`, one-sided | 73.3% at zero, 74.6% at five, 78.9% at fifteen, 82.3% at thirty, on the last estimate. Five is the line the row already draws: it prints no "later than ESB estimated" inside it, so the share cannot count that a miss. Early is always kept; the wording says "no later than five minutes after" because "within five minutes" read as a band, and under a band the figure would be 3.7%. Defined once in the model; the JS mirror is asserted by the same test that guards `MIN_FAULTS` |
| Floor | **five estimates**, `MIN_ESTIMATES = MIN_GRADED_FAULTS` | August's smallest county sample was 10 and its largest 99; a September six days old ranged 1 to 25. Under five the cell is blank and the tile a dash, as the grade does. No day gate: this is a plain share of a sample, and the floor is the whole of what a small sample needs |
| Population | the faults the grade judges | started and restored in the observed window and not ongoing; the same list feeds `county_month` and the national row, so the two tiles cannot count different sets |

**The row and the share use different estimates, on purpose.** The row's
"28 min earlier than ESB estimated" compares against ESB's last word, the
estimate carried by the record that ended the event (grading.md § One ESB event
is one row), and the ongoing row's "expected back by" must be the latest. The
share holds ESB to its first word, because that is the promise a customer acted
on. A row can therefore read "earlier than ESB estimated" for a fault the share
counts as a miss; the tile's label says "first" so a reader can tell which
question each answers. For a merged event the first estimate is the earliest
any member named; the envelope timeline carries no estimates, so it is taken
per record before the merge.

August, as the page shows it: nationally 59.2% of 982 first estimates were
kept, Leitrim 33% of 27 and Meath 46% of 35 at one end, Kilkenny 75% of 20 and
Waterford 77% of 30 at the other. Misses are long when they happen: against the
last estimate, a median of 55 minutes late and a tenth over four hours.

Rejected: an all-time national figure in the footer beside the CML comparison.
That paragraph argues the site's credibility against ESB's published numbers,
and ESB publishes nothing to compare an estimate share with. The tiles carry it
month by month, which is the clock everything else on the page runs on.

## The county page ranks its fault spots, and hands out its rows - 2026-09-06

Two additions to `c/<slug>.html`, both static and neither on the initial load.

### Where faults keep happening

Nothing on the site ranked anything: the directory is alphabetical, the history
is chronological. Westport has 26 faults in five weeks, Killinick 23, Milltown
16, and a reader had to count rows to find that out. The card lists the ten
locations with the most faults over every month, two faults or more, each with
its count and the most customers any one of them took out.

**The rows are ESB's own location names and link nowhere.** The obvious link
is the area page, and it would be wrong: a location name is where ESB says the
fault is, and 222 of the 422 names in the corpus have been pinned to more than
one Census area. Westport's 26 faults sit in "Around Killavally"; Wexford's 12
in "Around Whitechurch". The note under the heading says so, in the same words
the area pages use for the same problem.

Measured on the corpus to 5 September: 308 of 422 locations have two or more
faults, every county has at least two such spots, the median county has nine
and Dublin 51. Ten rows cover 83% of Mayo's faults and 32% of Dublin's, which
is the range a fixed cap has to live with; a count is a proxy for bytes and
this is 10 rows, so no byte budget was needed.

Rejected: a repeat-chain count per row. The top eight spots hold one chain
between them; chains are a within-the-hour phenomenon (grading.md § Repeat
faults are not splits) and a spot is a within-the-month one.

### The CSV

The README has always said the point is to study Irish outages over time, and
the only way to do it was to clone `esb-data`, rebuild, and re-implement
`merge_events`. Each county page now links `c/<slug>.csv`: one row per merged
event, oldest first, the columns in `render.CSV_COLUMNS`. Every id folded into
an event is in `esb_ids`, the end carries its source, both estimates ride
along, and `customer_minutes` is the integrated figure the page uses, so a
reader gets what the page counts rather than raw records.

Per county rather than one national file, because the link sits on the county
page and that is the unit a reader arrives at; 534 KB in 26 files, listed in
the size report as "on request" and outside the budget. Written for every
county, an empty one included, so the link cannot 404. Not in the sitemap: a
CSV is not a page.
