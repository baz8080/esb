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
