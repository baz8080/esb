# Outline - 10 posts plus intro and closing, chronological

Each entry: PRs/commits · thesis · concepts boxed · worked example · the uisce contrast the
chapter must state. The repo's history is small enough to read directly - 98 commits, 20 PRs,
three `notes/` files - so there is no `sources/` extraction; `figures.md` is the registry.

The series' standing mandate, on top of the uisce series' rules: **every fork from the water
site is stated as (their approach, our approach, the data fact that forced it).**

---

## Ch 0 - Ask the grid the same question · intro

The water site's question grew a sibling; the feed purges within hours, so collection had to
precede design. First-month answer: 88.4% against ESB's 95% aim. AI process named once.

## Ch 1 - Write it down before you read it · pre-PR commits · 31 Jul to 1 Aug

**Thesis.** Raw JSONL verbatim-before-parse; DB disposable; rebuild replays the live code
path. **Concepts.** Source of truth vs derived index · idempotent merge (sorted keys +
`sort -u`). **Example.** Outage 2826455, the 17:34/17:26 timezone proof. **Contrast.**
uisce's archive *is* its DB (upsert; a rewrite costs the archive); its feed is slow, this one
purges - sightings vs ledger. Mermaid pipeline diagram.

## Ch 2 - A collector in the hall · commits to 3 Aug + notes/polling.md (18 Aug)

**Thesis.** A Pi, not CI: 48 passes/day against a purging feed. 30-min interval decided by
data (83-min median, 58% caught live hourly); dormancy back-off (58% fetch cut, byte-identical
replay); exit-code alerting; 15-min polling measured and declined. **Concepts.** Exit code as
the alerting stack · the poll interval is a filter. **Example.** The dormancy arithmetic.
**Contrast.** uisce's "CI as a scheduled clerk"; its cadence floor is the utility's 75.7-h
closure lag, ours is the collector - same experiment, opposite bottleneck.

## Ch 3 - The feed that knows when it happened · PR #1 branch · 17–18 Aug

**Thesis.** `startTime` is back-dated and immutable (8/1,460; 0 records pre-date their start)
- durations measure the outage, not the notice. Structured fields still need interpreting
(restoreTime `""`; Restored overwrites type; planned never restore). Ends bounded: estimate
vs last sighting (1.13× vs 2.26× on 648 known ends). Timelines anchored on ESB's clock.
**Concept.** A back-dated start. **Example.** Roosky (15:15 / 18:17 / first seen 21:02).
**Contrast.** The central one of the series: uisce's floors vs our measured durations; their
extraction problem (prose → rules/LLM) vs our selection problem (three candidate ends).

## Ch 4a - One fault, five records · PR #1 branch · 17–18 Aug

**Thesis.** No event key in the feed; merge on identical (location, start); 1,457 ids → 1,333
events; chains (Tycor ×4 in 90 min) are separate interruptions, tagged never merged;
tolerance relaxation measured and rejected. **Concepts.** Envelope, not a sum · a chain is
not a split. **Example.** Bealistown's five records. SVG `envelope-not-sum.svg`.
**Contrast.** uisce's feed *gives* identity (`reference_num`, the 18-night event); ours
withholds it - same governing sentence, opposite operations.

## Ch 4b - Grade them on their own promise · PR #1 branch · 17–18 Aug

**Thesis.** Electricity is regulated in public: grade = ESB's own 4-h/95% charter aim.
Relative CML grade retracted (Wexford F→C). `numCustAffected` bias 1.3× cancels in a share;
CAIDI 92.2 vs 85.1 validates timing; denominator corrected to 2.5M (false citation); Census
as bit part (nearest centroid; `int()` vs `floor` bug). **Concepts.** Absolute vs relative
scale · a bias that cancels in a share. **Example.** The denominator correction. **Contrast.**
uisce had no published standard to grade against and led with Census population; we have both
a charter and per-outage counts, so Census does placement only; their radius footprint
deliberately not carried over.

## Ch 5 - What the page may claim · PR #1 · 18 Aug

**Thesis.** 500 KB enforced budget, shards, day cells by magnitude (66% of days had a fault),
update disclosure from the measured distribution; the collection horizon replaces `now`
(green ghost days; CML −9%; ongoing outages unjudged - 15/16 replayed days had one open;
peak defined before it matters; short days say so). **Concepts.** The collection horizon ·
magnitude, not presence (in prose). **Example.** Monaghan's 15-over-14. SVG `horizon.svg`.
**Contrast.** uisce's data-clock/build-clock box arrived via build gaps; ours via a separate
collector - same invariant.

## Ch 6a - The third site of the family · PRs #2–#11 · 19–21 Aug

**Thesis.** The statusui story from the receiving end: hand-porting dropped uisce's contrast
pass here; vendored on the 19th, drifted by the 20th, pinned in `uv.lock` by the 21st; the
Pi's empty-`dependencies` contract shapes the adoption; first rollout deletes the status dot.
**Concept.** Empty dependency list as a deployment contract (+ u14's boxes restated in a
line). **Example.** The drift measurement. **Contrast.** Explicit twin of uisce ch 14 - same
days, other bank.

## Ch 6b - Reading like one product · PRs #12–#20 · 25–26 Aug

**Thesis.** Plain-reader pass (fmtDay promoted - esb was the second user); the 25 Aug false
"collection has stopped" and the 16-h threshold arithmetic; freshness against the reader's
clock; the owner's element-by-element alignment (banner/heading from uisce, county rows/card
from esb); county pages become archives with promise-keeping links and truncation-safe
descriptions; the applies-tests. **Concepts.** A threshold sized to a cadence · ordered so
truncation cannot make it false. **Example.** The staleness arithmetic; the link-wording
triple. **Contrast.** Explicit twin of uisce ch 16.


## Ch 7a - A page for every place · PRs #21 to #24 · 27 to 28 Aug

**Thesis.** Area pages transfer from uisce almost free (the Small Area lookup already resolved
settlements and the site was discarding it): 384 pages + a 179 KB directory, initial load
still 56 KB. What does *not* transfer is attribution - ESB's point is the fault, not who is
off - so wording ("pinned near"), a disclaimer, and a nearest-neighbours card instead of a
footprint. Search hits become real links; the in-app area view reconsidered and declined
again. County page cap removed entirely. Overview goes alphabetical. **Concept.** Attribution,
and why this feed cannot do it. **Example.** The lazily-fetched index rename and the stale
tab. **Contrast.** uisce's 500 m circle is an approximation of something real; here the same
move would invent one.

## Ch 7b - The units a reader thinks in · PRs #25 to #29 · 28 to 30 Aug

**Thesis.** One question asked of every figure: is this in a unit the reader already holds?
Annualised CML beside a month's figures → `cml_month` (12.8); customer-years → customer-hours
(473,067, decomposed three ways and shown to be plausible); outage rows become sentences with
the span inside the phrase (five shapes, shares measured; restore vs estimate, 69% early);
county page loses card, age line and all JS (1,840 → 1,349 KB); the globals guard stops
parsing a file that had halved; the no-em-dash rule written down (and applied to this series);
the scale grows an E at 60%. **Concepts.** A guard that shrinks silently (+ the units rule in
prose). **Example.** Is half a million customer-hours plausible? **Contrast.** uisce had to
*fit* a new band against its distribution; anchored bands mean arithmetic sets the cut.

## Ch 8 - Closing

What the site can/cannot say (including the attribution limit and what an area page adds); the
full side-by-side table, the series' deliverable, now 15 rows; the settled-decisions table in
plain language; "collect first, interpret later, keep the bytes"; glossary (15 boxes + 3
borrowed).
