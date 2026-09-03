# 6b. Reading like one product
*~10 min read · PRs #12–#20 · 25–26 August 2026*

*Where we are:* the three sites share a design layer (chapter 6a). Two days at the end of
August made this one speak plainly, admit its data's age honestly, and give every county a
durable page - in step with the water site doing the same, with the two sites trading wins.

## The question that opened this stretch

The water series calls its version of this stretch "stop sounding like the author", and the
diagnosis transfers verbatim: read cold, the pages still carried the builder's vocabulary -
ISO dates, "4.2 h est.", a footer stamped with build times - where a reader wanted "Sat 1
Aug" and "off about 4 h". But this site's stretch had a second thread the water site's did
not: its data comes from a machine in a hall, pushed on a schedule, built on another
schedule - and on 25 August the seams between those schedules produced a public false alarm.
So the questions were: what does this page sound like to a neighbour, and what may it claim
about its own freshness?

## What changed

### Speak to the reader (PR #12, 25 August)

The plain-reader pass, following the same conventions the water site adopted in its PR #54.
Dates became "Sat 1 Aug" - the day-of-week is how people remember outages. Outage cards now
carry both ends where both exist: "restored 14:32 · ESB's estimate was 15:00", which quietly
shows the reader how good the estimates are; "4.2 h est." became "off 3 h 46 min", or "off
about 4 h" with half-hour rounding when the end is unconfirmed - chapter 3's end-source
labels, finally in words. Planned works read "scheduled until 15:00" rather than "not
confirmed", since planned works never confirm (chapter 3). One vocabulary - "restored" -
replaced a drift across "back in 4h" / "back inside" / "back within". The national tile
stopped saying "17215 days" and now says "47 years of customer time off supply". And the
county heading now reads "About 32,000 homes and businesses · estimated from Census 2022":
the previous exact pro-rata figure was false precision, because ESB's "customer" is a meter
count apportioned by population share (chapter 4b), and the rounding is the honesty.

The date formatter itself is the detail with the family story in it. The water site wrote
`fmtDay` for its own pass; this pass was the *second* site wanting it; and the water series'
concept box "promoted on the second user" is about exactly this moment - the helper moved
into statusui (Python and JavaScript mirrors, parity-tested), both sites deleted their
copies, and a guard test fails any page script that redeclares a shared name. This site was
the second user that triggered the promotion.

### The morning the site cried wolf (PR #13, 26 August)

On 25 August the live site displayed "collection has stopped" while the Pi was running
normally. The post-mortem: the site rebuilds on every push to its repository, not only on
its schedule, and one such rebuild landed six minutes *before* the collector's nightly push
- so it built against data 24.2 hours old, just over the then-24-hour staleness threshold.
The threshold was measuring the wrong thing: it sat *at* the longest legitimate gap between
pushes instead of above it.

> **Concept: a staleness threshold is sized to a cadence.** "The data is N hours old" is
> only alarming relative to how old it is *allowed* to be, and that allowance is arithmetic,
> not taste. Under the new schedule the Pi pushes twice a day, midnight and noon, each with
> up to 30 minutes of deliberate jitter; the site rebuilds after each slot. Consecutive
> pushes are nominally 12 hours apart, stretched to 12.5 by jitter and 13.5 across a
> daylight-saving change, and the horizon inside a push trails it by up to another
> half-poll: a build racing the next push can therefore legitimately see data about **14
> hours** old. A collector that has actually died is first noticed by the morning build at
> **17+ hours**. The threshold went to **16 hours** - above everything innocent, below the
> first guilty reading. (Every quantity in that arithmetic moves in chapter 9, including one
> that turned out never to have been true: the builds were not running when the workflow said
> they were. The *method* survives the correction; the threshold is 10 hours now.) The water
> site's equivalent threshold is 24 hours, sized against
> *its* build schedule; when the freshness logic later moved into the shared layer, the
> threshold and the warning sentence were exactly the two things left per-site, because they
> are the two things the arithmetic makes site-specific (PR #13, 26 Aug 2026).

The noon push, worth noting, is purely for publication latency - it halves how far the page
lags the feed. Data quality does not depend on it at all: the raw logs capture every poll
either way (chapter 1's invariant, again). And the false alarm itself was the horizon
machinery *working* - chapter 5 built the site to notice absence; this stretch taught it the
difference between absence and bedtime.

### Say how old, to the reader's clock (PRs #14–#15, 26 August)

The banner then changed what it says about freshness. It had shown a UTC build timestamp -
asking the reader to do timezone arithmetic - while its right-hand slot repeated a statistic
the tiles below already carried. It now answers the one question a reader brings to a status
page: "Updated 3 hours ago", turning red past the threshold with "… - collection has
stopped". Two design points, both in the honest direction. The age is computed against the
**reader's clock**, not frozen at build time, so a page served from cache goes stale by
itself; the build-time `stale` boolean left the payload entirely, replaced by the horizon
and the threshold, evaluated live. And the age *wording* deliberately does not soften
overnight gaps: a healthy midnight-to-morning reading is a big number, and it is the red
warning, not the phrasing, that distinguishes "asleep" from "dead". The exact horizon
timestamp moved out of the headline into the footer and the county pages' sub-line - kept,
demoted. The word "Unofficial" became "Independent" in the same pass, because "unofficial"
read as a disclaimer about the *numbers* rather than about affiliation. The freshness
arithmetic itself is statusui's `freshness()` - the water site had the arithmetic first,
this site's need made it shared, same pattern as `fmtDay` (PR #15, 26 Aug 2026).

A quieter pair of PRs the same day belongs to the Pi's contract: the Python floor moved from
3.9 to **3.11** - the version Raspberry Pi OS bookworm actually ships - with ruff re-linting
the whole tree against the new floor (97 findings, all mechanical) and CI growing a
3.11/3.14 matrix so the floor is *checked* rather than declared, since a 3.12-only stdlib
call would otherwise lint clean and fail on the Pi at deploy time (PR #16, 26 Aug 2026;
PR #17 made a root-user test skip explicit).

### The alignment pass: each site keeps what it got right (PRs #18–#19, 26 August)

Then the owner reviewed the water and power home pages side by side and picked a winner per
element - the pass `notes/design-alignment.md` records, and the reason this chapter can
fairly describe the family as *converging* rather than one site copying the other.

What this site absorbed from the water site: the banner's shape ("**August 2026 so far:**
978 faults and 1,122 planned outages" - bold month prefix, "so far" only while the viewed
month is still collecting); the month-aware national heading ("The national picture in
August 2026", replacing a static "Nationally this month" that read wrong on every past
tab); a basis line that names the month when a past tab is viewed; the merged footer
disclosure ("How these numbers are worked out") and the shared closing line ("Source code ·
not affiliated with ESB Networks or the CRU"). The local search code was deleted for the
shared `bindSearch` - which also fixed two latent bugs the local copy had.

What the water site absorbed from this one: the county rows themselves - chevron, two-line
percentage stat, right-aligned counts - and the county-page card order (legend, tall bar,
tiles), which had been this site's layout all along. On those elements this repository's
diff for the pass is empty, which is its own kind of win.

### Worked example: a link that must keep its promise (PR #19, 26 August)

The county pages then became what a permanent URL claims to be. `c/cork.html` had carried
only the latest month, capped at 40 outages, with a title that said so - the subject of a
durable address changed under it monthly. It is now the county's archive: every observed
month, a month-by-month table read from the same payload the app charts (so the two cannot
disagree), the outage list running newest-first across the whole record, cap raised to 150.
(The cap comes off entirely the following day, in chapter 7a, for the reason this paragraph
is already circling.)
Measured cost: the busiest county held 234 outages in a month, and the raise cost the
largest page 3.2 KB gzipped (13.1 → 16.3 KB) for 3.7× the indexable text.

Two correctness points had to be got right, both echoes of earlier chapters. The shards file
an outage under every month it overlaps (chapter 5's Monaghan lesson), so flattening them
for one list would double-count anything crossing a month boundary - folded back, ordered by
start. And July 2026 is three hours long here (collection began 21:02 on the 31st), so the
table would have read "July 2026: 0 faults" - an absent collector masquerading as a quiet
month, chapter 5's oldest enemy - and each short month now says which part was watched
("from 31 Jul").

Then the wording. The app now links to the page - the missing leg, since the page already
linked to the app - labelled "**Every month for County Cork on one page**", not "permalink":
the label names exactly the difference a reader gains by following it (the view is one
month; the page is all of them). The water site says the same sentence, because its county
page stands in the same relation to its county view - and it had briefly said "Every notice
ever recorded", which its own 60-notice cap contradicted, so the label was corrected to the
promise the page keeps. The lift site says "Permanent link to Athy station" instead, because
its page carries the same content as its view, and naming the content would promise the
reader what they are already looking at. Three sites, same placement, two wordings, each
matching what is on the other side of its own link (`notes/design-alignment.md`,
26 Aug 2026).

> **Concept: ordered so truncation cannot make it false.** The county page's search-result
> description had the same flaw as the water site's link, one layer down: "Power cuts
> recorded in County Cork since 31 July 2026: 95 faults and 139 planned outages…" - the
> colon makes the counts read as an inventory of the page, and the page caps its list. A
> search snippet is cut by pixel width, and what survives is the front. So the sentence was
> reordered - "County Cork: 95 faults and 139 planned power cuts since 31 July 2026.
> Month-by-month totals and the most recent outages…" - such that a cut *anywhere* leaves a
> true statement: the county's record first, the page's contents named after. A test guards
> the ordering, the truncation property and the 155–160-character ceiling across all 26
> counties. The general rule outlives the example: text that will be cut by machinery you do
> not control should be true under every prefix.

The stretch closed with a guard for the sharing mechanism itself: one styling rule this
repository had carried locally moved upstream, and PR #20 added tests that the rule
*applies* - the page renders an element it matches, the assembled stylesheet contains it,
nothing in the cascade beats it, and no local copy has crept back - because the move had
briefly created a state where the rule could vanish from the deployed site with every test
green. Each guard was verified by manufacturing the failure it exists for (PR #20,
26 Aug 2026; 189 tests).

## Where it left the site

As of 26 August 2026: a banner that answers "is this current?" against the reader's own
clock, with a threshold derived from push arithmetic rather than optimism; prose a neighbour
can read, with every estimate labelled; county pages that are durable archives with links
and descriptions that keep their promises; and a design language genuinely converged with
its siblings - assembled from a shared layer neither site can drift from, with each site
keeping the elements it got right first. The repository stands at 98 commits, 20 pull
requests and 189 tests, twenty-six days after its first poll.

## Notes

- PR #12 (25 Aug 2026): friendly dates, both restore times, "off about 4 h", one vocabulary,
  "47 years", "About 32,000 homes and businesses", legend placement, footer disclosure,
  em-dashes; `fmtDay` promoted (statusui `2076735`) - the water series' "promoted on the
  second user" box, from the second user's side.
- PR #13 (26 Aug 2026): the 24.2-hour false alarm of 25 Aug; twice-daily pushes ±30 min;
  builds 05:40/12:40 UTC; the 14 h / 16 h / 17+ h arithmetic; `STALE_AFTER` in
  `esb_site/render.py`.
- PR #15 (26 Aug 2026): "Updated N hours ago" via statusui's `freshness()`; reader-clock
  staleness; `stale` out of the payload; "Independent"; horizon demoted to footer and county
  sub-lines. PR #14: footer trim. PR #16: the 3.11 floor, 97 findings, the CI matrix;
  PR #17: root skip.
- PR #18 (26 Aug 2026) and `notes/design-alignment.md` (26 Aug): the element-by-element
  owner review; banner/heading/basis-line/footer from uisce; county rows and card from esb;
  shared `bindSearch`; the horizon leaving the footer as an owner call.
- PR #19 (26 Aug 2026): the county archive (40 → 150; 234; 3.2 KB / 3.7×; the month-fold;
  "from 31 Jul"); the link wording triple (esb/uisce name the months, lifts names the
  station); the meta-description reordering and its tests.
- PR #20 (26 Aug 2026): the applies-tests for `.chead + .sub`, mutation-verified; 189 tests.
- The other bank: the water series, chapter 16 - its PRs #54–#61, including the `freshness()`
  equivalence check and its own halves of the alignment.
