# 4b. Grade them on their own promise
*~9 min read · the PR #1 branch and its follow-up commits · 17–18 August 2026*

*Where we are:* 1,333 events with defensible starts, bounded ends and honest customer counts
(chapters 3–4a). Now the number a reader actually sees: what should a county's letter grade
*mean*?

## The question that opened this stretch

The water site had to invent its grade from nothing, because Irish water is measured in
public by nobody: Uisce Éireann publishes no service target a household can check, and the
British regulator's figure is constructed so differently it cannot be borrowed. So that site
built availability out of Census person-hours and drew its own A–F thresholds — defensible,
but self-referential by necessity.

Electricity is different, and the difference is an opportunity. Irish distribution
reliability is regulated *in public*. ESB Networks' Customer Charter, approved by the CRU,
states an aim anyone can read: **"our aim is to restore supply within less than 4 hours in
95% of cases."** The CRU's PR5 price review measures ESB on two indices — CI, interruptions
per customer per year, and CML, Customer Minutes Lost per customer per year — with roughly
€50m riding on each, and ESB's own Distribution Annual Performance Report publishes the
results: for 2024, 117.47 CML against a target of 78.7, and 137.86 interruptions per 100
customers against 112.7 (`notes/grading.md`, 17 Aug 2026). A site grading Irish electricity
does not have to invent a standard. The operator published one, and the question of this
stretch became: can the grade be pinned to it honestly?

## What changed

### The first grade was wrong, and Wexford proved it

The original grade was relative: each county's Customer Minutes Lost against the national
average. It handed out an F for being three times the average — even though the average is
*good*, and nearly every Irish fault is cleared the same day. A letter that reads as failure
was describing ordinary service. When the grade moved to ESB's own standard, Wexford went
from F to C, which matched both the charter arithmetic and lived experience (commit "Grade on
ESB's own 4-hour standard…", 17 Aug 2026).

> **Concept: an absolute standard versus a relative scale.** A relative scale — "worst
> counties get the F" — always fails someone, by construction, even in a country where the
> service is fine; and it silently moves under the reader, because this month's F threshold
> depends on everyone else's month. An absolute standard fixes the meaning of each letter to
> a stated quantity — here, the share of fault-interrupted customers restored within four
> hours, with A at ESB's own published 95% aim, then B at 90%, C at 80%, D at 70% — so a
> letter means the same thing in every county and every month, and a reader can check the
> claim against the charter it came from. The water site reached the same conclusion by its
> own road (fixed thresholds, comparable month to month); what this site adds is that the
> anchor is not mine. If a county gets an A, it met the operator's own promise; if the
> country gets a B, the operator missed it. Nationally, the first month: **88.4%**, against
> the 95% aim. A county-month with fewer than five faults or five observed days goes
> ungraded rather than pretending a sample that thin means something.

For August 2026, the 26 counties split A 9 · B 6 · C 4 · D 4 · F 3 (`notes/grading.md`,
17 Aug 2026). One outage in the whole corpus crossed the 24-hour mark at which the charter
pays compensation.

### Why not Customer Minutes Lost — measured, not preferred

CML was not dropped because a relative scale misused it. It was dropped because this data
*cannot reproduce CML on ESB's scale*, and the reason is a bias worth understanding, because
choosing a metric that cancels it is the chapter's real move.

`numCustAffected` — the feed's customer count — is the number of customers on the affected
network section *when the fault is logged*. As crews isolate the fault, ESB settles on a
smaller figure, and the feed shows this happening: counts fall through an outage's life
(chapter 4a's envelopes are built from exactly those falling counts). The result, measured
against ESB's published 2024 figures: this pipeline reproduces ESB's *durations* almost
exactly — CAIDI, the average minutes per interruption, comes out at 92.2 against ESB's 85.1,
a ratio of 1.08 — while counting about a third more interrupted customers (CI at 1.33×
after the denominator correction below). Multiply an honest duration by an inflated
count and CML inherits the inflation: 169 against ESB's 117 (`notes/grading.md`,
"The customer denominator", 18 Aug 2026).

> **Concept: a bias that cancels in a share.** Suppose every event's customer count runs
> about 1.3× the true figure, because the feed reports the section rather than the settled
> number. Any *total* built from the counts — total customer-minutes, total interruptions —
> runs 1.3× high, and no amount of care downstream repairs it. But a *share* puts the same
> inflated counts on the top and the bottom of the fraction: customers-restored-inside-4-hours
> ÷ customers-interrupted. As an illustration (toy numbers, not data): two faults of 1,000
> customers each, one restored in 3 hours and one in 6, give a charter share of 50%; inflate
> both counts to 1,300 and the share is 1,300 ÷ 2,600 — still 50%. The inflation rides both
> rails and drops out. That is why the grade is a share of customers and not a sum of their
> minutes, and it is the same kind of reasoning the water site used when it kept its grade
> off metrics its feed could not support — each site graded on the thing its own data could
> defend, which is precisely why the two grades are *not* the same metric.

CML is still computed and shown beside the grade — it is the regulator's unit and worth
reporting — with the caveat stated on the page. And a guard keeps the whole claim honest:
`tests/test_site_national.py` compares the pipeline's national CML, CI and CAIDI against
ESB's published figures on every run, so if the model or the feed drifts, the build says so
before the site does.

### Two exclusions, one refusal

**Planned works are excluded from the grade.** The CRU's own incentive excludes them, they
are notified in advance, and chapter 3 measured the clincher: not one of 675 planned outages
ever reported a restore time, so their durations are estimates ESB never confirms — no basis
for judging a restoration promise.

**Storm days are not excluded, and the page says so.** Both the charter guarantee and the
CRU indices exempt storms — ESB removes storm days from its published unplanned CML and CI,
and 2024 had a record 24 of them. Nothing in this feed identifies a storm day, so this site
cannot make the same exclusion, and winter months here will read worse than ESB's own figures
*for a reason that is not ESB's fault*. Rather than approximate an exclusion the data cannot
support, the site keeps storm days in and states the difference in the footer. It is the same
posture the water site takes with its 500-metre assumption: when a limitation cannot be
removed, publish it.

### The Census plays a bit part here, not the lead

Both sites need the Census, and the contrast in *how much* they need it is the cleanest
illustration of the two feeds' differences. The water site's feed reports no affected count
at all, so Census population is its whole measure of exposure — a 500 m circle of Small Areas
around each pin decides how many people a notice touches, and everything downstream rests on
that assumption. ESB's feed reports the affected customers itself (biased, but usably — see
above), so the Census does exactly two small jobs here: **placement** — the feed has no
county field, no Eircode, no address, only a `"lat,lon"` string, so an outage's county is the
county of the nearest Census Small Area centroid (18,919 of them; in the first month this
placed 1,457 of 1,457 records across all 26 counties with nothing left over) — and
**apportionment**, splitting ESB's national 2.5 million customers across counties by
population share, which touches only the per-county CML shown beside the grade, never the
grade itself. The water site's radius-and-population footprint was deliberately not carried
over: ESB publishes a point per outage, not a service area, and inventing a service area
would import the very assumption this feed makes unnecessary (`notes/grading.md`; commit
"Vendor the Census Small Area reference data", 18 Aug 2026 — the two Census files are lifted
directly from the water site's repository).

Placement promptly supplied the branch's best bug. The centroid lookup builds a
degree-sized grid of Small Areas, and the grid was built with `int()` but read with
`math.floor()`. For positive numbers they agree; Irish longitudes are *negative*, and `int()`
truncates towards zero — so every centroid was filed one bin east of where the lookup
searched. Twelve outages landed in the wrong Small Area and one, the Macetown fault, in the
wrong county entirely. Against a brute-force nearest-neighbour check over 3,000 sampled
points, the fixed grid now agrees exactly, where eleven had disagreed (commit "Fix the
placement grid…", 18 Aug 2026). The water site's geography chapters carry a sibling story —
its polygon method under-counted a village fourfold before its centroid approach — and the
shared moral: check spatial code against brute force, because it fails silently and
plausibly.

### Worked example: the denominator that carried a false citation

Every per-customer figure divides by the number of ESB customers, and that constant was
2.4 million, cited to a sentence on DAPR 2024's Key Statistics page — "almost 2.4 million
domestic, commercial and industrial customers". Checking the citation for this stretch's
footer found that **the sentence is not in the report**. The only customer count DAPR 2024
actually contains is "c. 2.5 million customer meters", and ESB's own company page agrees —
"roughly 2.5 million customers connected". The constant was corrected, and everything divided
by it moved down 4.2%: CML 176.1 → 169.0, CI 1.91 → 1.83, so the measured customer-count bias
fell from 1.38× to 1.33× (commit "Use ESB's own 2.5 million customer count as the
denominator", 18 Aug 2026). CAIDI did not move and cannot: minutes-per-interruption divides
total minutes by total interruptions, and the customer count cancels out of the ratio — which
is exactly why CAIDI is the one index that says whether the *timing* model is right,
independent of every counting dispute. At 92.2 against ESB's 85.1, it says the timing is
close.

The same check pinned down a trap for future maintainers: DAPR 2024's summary bullets say the
average customer was interrupted "approximately 1.75 times" and lost "219 minutes" — all-in
figures, planned and unplanned together, storms included — which do not belong beside
constants taken from the unplanned, storm-excluded target paragraph. The comparable pair is
quoted verbatim in the code comment so the next reader does not "fix" 1.38 to 1.75 and
silently drag the measured bias down by a fifth.

## Where it left the site

A letter a reader can check against a document ESB published; the regulator's unit beside it
with its caveat; a national test suite holding the pipeline to ESB's own figures; and the two
honest admissions — storms are in, and the interruption count runs a documented third high —
stated on the page rather than buried. What the page did *not* yet do honestly was know its
own limits in time: what happens when the collector goes quiet, and what a half-finished day
should look like. That is chapter 5.

## Notes

- `notes/grading.md` "The published prior art" (17 Aug 2026): the Customer Charter 4-hour/95%
  aim and 24-hour compensation; PR5 CML/CI targets and outcomes (2024: 117.47 vs 78.7;
  137.86 vs 112.7 per 100 customers; ~€37m penalties; 24 storm days); CEER range 9–290
  SAIDI minutes.
- `notes/grading.md` "The grade" and "Why not Customer Minutes Lost" (17 Aug 2026): A–F
  thresholds, ungraded floor, national 88.4%, county split 9/6/4/4/3; the section-count bias;
  relative-scale mislabelling. Commit of 17 Aug: Wexford F → C.
- `notes/grading.md` "Settled, with the numbers": planned works excluded (675, none
  restored); storm days kept, stated; Census apportionment touches CML only;
  nearest-centroid placement, 1,457/1,457, footprint rejected.
- Commit "Fix the placement grid, and measure against the data rather than the clock"
  (18 Aug 2026): `int()` vs `math.floor()`, 12 wrong Small Areas, Macetown, 3,000-point
  brute-force check (11 → 0 disagreements).
- `notes/grading.md` "The customer denominator" and "The 1.75 trap" (18 Aug 2026): 2.4M's
  missing citation; 2.5M meters; CML 176.1 → 169.0, CI 1.91 → 1.83, CAIDI 92.2 (1.08×);
  refresh instructions for DAPR 2025.
- The toy share arithmetic is illustrative, not data. The water site's contrasting geography
  and grade: its series, chapters 5a and 8a–8b.
