# How the A–F grade was derived

*Written 2026-08-17, against the first 16 days of collected data.*

## The published prior art

Irish distribution reliability is regulated in public, and three separate
published documents bear on how a county should be scored.

**1. ESB Networks' Customer Charter**, approved by the CRU, under the Restore
Supply Guarantee:

> our aim is to restore supply within less than 4 hours in 95% of cases

The same guarantee pays compensation if a customer is *without power for 24
hours* after ESB was made aware, and a further payment for each additional 12
hours. It exempts "exceptional cases such as storms".
([Customer Charter](https://esbnetworksprdsastd01.blob.core.windows.net/media/docs/default-source/publications/customer-charter.pdf))

**2. The CRU's PR5 incentive**, which measures ESB Networks on two indices and
attaches roughly €50m to each:

- **CI** — interruptions longer than three minutes per customer per year.
- **CML** — Customer Minutes Lost per customer per year.

| Year | Unplanned CML | CRU target | Unplanned CI | CI target | Planned + unplanned CML |
|------|--------------:|-----------:|-------------:|----------:|------------------------:|
| 2022 | 103.34 | 82.9 | – | – | – |
| 2023 | 105.59 | 80.8 | 126.38 | 114.8 | 207 min |
| 2024 | 117.47 | 78.7 | 137.86 | 112.7 | 219 min |

Targets fall ~2.1% a year; ESB has missed them throughout PR5 and been penalised
about €37m. Both indices **exclude storm days**:

> To benchmark our outage performance against other utilities storm days (the
> effects of severe weather) are removed for unplanned CI and CML reporting.

2024 had a record 24 storm days.
([DAPR 2024](https://media.esbnetworks.ie/media/docs/default-source/publications/distribution-annual-performance-report-2024.pdf),
[DAPR 2023](https://esbnetworksprdsastd01.blob.core.windows.net/media/docs/default-source/publications/distribution-annual-performance-report-2023-accessibled434eedca532460d959ccfba328306eb.pdf),
[CRU PR5 framework](https://cruie-live-96ca64acab2247eca8a850a7e54b-5b34f62.divio-media.com/documents/CRU20154-PR5-Regulatory-Framework-Incentives-and-Reporting-1.pdf))

**3. CEER's European benchmarking**, for context: unplanned SAIDI excluding
exceptional events ranged 9–290 minutes across Europe, with definitional
differences between countries (Ireland excludes extra-high voltage; Germany
counts only low and medium).
([Benchmarking Report 6.1](https://www.ceer.eu/wp-content/uploads/2024/04/C18-EQS-86-03_Benchmarking_Report_6.1.pdf))

## The grade: ESB's own 4-hour standard

**A county is scored on the share of its fault-interrupted customers who had
supply back within 4 hours.** A ≥ 95% (ESB's published aim), B ≥ 90%, C ≥ 80%,
D ≥ 70%, F below. A county-month with fewer than five faults, or fewer than five
observed days, is left ungraded.

Nationally in the first month: **88.4%**, against the 95% aim. One outage in the
whole corpus passed the 24-hour compensation mark.

| | A | B | C | D | F |
|---|---:|---:|---:|---:|---:|
| Counties, August 2026 | 9 | 6 | 4 | 4 | 3 |

### Why not Customer Minutes Lost

CML was the original basis and was replaced, for two reasons.

**It could not be put on ESB's scale.** This pipeline reproduces ESB's *duration*
per interrupted customer almost exactly — an implied CAIDI of 88 minutes against
ESB's 85 — but counts about a third more interrupted customers. The cause is what
`numCustAffected` is: PowerCheck reports the customers on the affected section
when a fault is logged, and ESB settles on a smaller number once crews have
isolated it. The feed shows this happening directly, with counts falling through
an outage's life. A share of customers has that bias in the numerator and the
denominator alike and cancels it; a total of them does not.

**A relative scale mislabels a good network.** Grading each county against the
national average handed out an F for being three times the average even though
the average is good and nearly every fault is cleared the same day — a letter
that read as failure while describing ordinary service. An absolute standard
that ESB itself published says something a reader can check.

CML is still computed and shown beside the grade, with the caveat stated on the
page, because it is the regulator's unit and worth reporting.

## Settled, with the numbers

**One ESB event is one row.** ESB opens a new outage record each time a fault's
scope changes, so a single event arrives as a family of IDs sharing a location
and start time. Bealistown on 14 August was five: a Fault at 2,427 customers and
four Restored records at 1,118, 2,078, 1,547 and 880 as sections came back.
Their counts sum to 5,623 for an event that peaked at 5,623 — but only because
one record already carried the whole figure; adding them counts the same
customers repeatedly. Records are merged on an identical location *and* start
time, folding **1,457 IDs into 1,333 events**, which cut national CI from 1.60×
ESB's figure to 1.35× and CML from 195 to 172.

Requiring the coordinates to be close as well was tried and merged two extra
pairs in the whole month, so the simpler rule stands. Merged events report
customers as an **envelope** — the maximum still off at each instant, decaying as
sections return — rather than a sum, and their timeline reports customers still
off rather than one line per restored section.

**Planned works are excluded.** The CRU's incentive excludes them, they are
notified in advance, and not one of the 675 planned outages in the corpus ever
reported a restore time. `Planned → Restored` never occurs; planned works simply
stop being listed, so their duration is an ESB estimate ESB never confirms.

**Storm days are not excluded**, because nothing in the feed identifies one. Both
the CRU indices and the charter guarantee exempt storms; this site cannot, so
winter months will read worse than ESB's own figures for a reason that is not
ESB's fault. Said plainly in the page footer.

**The end of an outage without a restore time is the ESB estimate, not the last
sighting.** Measured against the 648 outages whose true restore time is known:

| Fallback | Bias | MAE | Total duration vs truth |
|---|---:|---:|---:|
| Last time it was still listed | +3.78 h | 3.78 h | **2.26×** |
| ESB's estimated restore time | +0.39 h | 1.31 h | **1.13×** |
| min(estimate, last listed) | +0.54 h | 1.41 h | **1.18×** |

ESB leaves restored outages in the feed for hours, so the last sighting
overstates duration by 126%. The estimate is used when it falls between the start
and the last sighting; otherwise the last sighting is the tighter bound. An
estimate landing *before* the start is discarded rather than clamped, because
clamping produced zero-length outages. Every outage carries which of the three
its end came from, and the page says so rather than presenting an estimate as a
measurement.

**Customer-minutes are integrated over the reported count, not multiplied**, since
crews restore in sections and the count decays.

**Customers per county are apportioned from Census population**, because ESB
publishes no per-county count. This is the one real approximation left in the
chain, and the grade is insensitive to it — a share of customers does not touch
the county denominator at all. It only affects the CML figure shown alongside.

**Counties come from the nearest Census Small Area centroid.** The feed has no
county field, no Eircode — only `point.c`. This placed 1,457 of 1,457 outages
across all 26 counties. The water site's radius-and-population footprint was
deliberately not carried over: ESB publishes a point per outage, not a service
area.

## Outages we only ever see restored

*Investigated 2026-08-17, after the split-outage merge landed.*

85 of 1,333 events (6.4%) have `Restored` as their first observed state: we never
saw them live. All 85 are faults — planned works never restore — and they are
short, a median of 30 minutes against 2.2 hours overall. We first see them a
median of 32 minutes after they were restored, which is one poll interval. They
are the outages that begin and end inside a 30-minute gap between polls, which is
a property of the collection rate and not of the data.

Classified by whether they have a neighbouring event at the same location within
2 km and six hours:

| | Count |
|---|---:|
| No neighbour — a short outage caught only on its way out | 61 |
| Neighbour is **sequential**: a repeat fault | 11 |
| Neighbour **overlaps**: possibly a split we are missing | 13 |
| Present at the very first poll (collection-start backlog) | 5 |

### Repeat faults are not splits, and must not be merged

The neighbours are mostly the same fault happening *again*, not the same fault
recorded twice. The second outage starts nought to one minute after the first was
restored, at identical coordinates, often with an identical customer count:

```
Tycor (Waterford), 11 Aug   09:31-10:28 (369c) -> 10:29-10:39 (253c)
                            -> 10:40-10:49 (295c) -> 10:50-11:03 (369c)
Boghall Road (Wicklow)      02:17-04:01 (150c) -> 04:02-04:12 (150c) -> 04:13-04:26 (150c)
Creagh (Galway)             03:46-04:27 (1027c) -> 04:28-... (1027c)
```

15 such chains cover 32 events; 5 of them hit an identical customer count on
every leg. These are genuinely separate interruptions — the same customers lost
supply two, three, four times — and ESB's own CI index counts each one. Merging
them would understate how often supply failed.

### The merge rule was not relaxed

Because both patterns share a location and sit minutes apart, a start-time
tolerance alone cannot tell them apart; only *overlap* can. Merging same-location
records that overlap in time and start within a tolerance was measured:

| Rule | Events | CI vs ESB | CML |
|---|---:|---:|---:|
| Exact (location, start) — **current** | 1,333 | 1.35× | 171.6 |
| + overlapping, starts within 5 min | 1,281 | 1.33× | 169.1 |
| + overlapping, starts within 15 min | 1,239 | 1.32× | 164.2 |
| + overlapping, starts within 60 min | 1,164 | 1.30× | 162.4 |

The remaining bias barely moves — three points of a gap that is documented and
understood — while each step folds together more events that may be distinct.
Rejected: the exact rule already captures the split pattern it was built for
(1.60× to 1.35×), and the rest is not worth the false merges.

### Splits across a county boundary are deliberate

Nine events share a location name and start time but sit 1–10 km apart in
different counties — one fault whose sections straddle a boundary, such as
"Little Bray" appearing in both Wicklow and Dublin. County is part of the merge
key, so these stay separate. That is intended: each county's page should carry
the customers actually in that county, and merging would attribute one county's
outage to its neighbour. The cost is that a handful of physical incidents are
counted once per county at national level.

## Day cells

Coloured by magnitude, not presence: 66% of county-days carried at least one
fault, so a bar that reddened for "an outage happened" would be a near-solid
wall. Thresholds are absolute fault minutes-lost per customer per day, fixed so a
published day never changes colour afterwards. The bar answers *how much*
disruption; the grade answers *how fast supply came back*.

| Bucket | min/customer/day | Share of the first month |
|---|---:|---:|
| Normal | < 0.05 | 44% |
| Minor | < 0.3 | 22% |
| Moderate | < 1.0 | 19% |
| Major | < 3.0 | 9% |
| Severe | ≥ 3.0 | 6% |

## The update disclosure

Counting only reader-visible fields — excluding `statusMessage`, which has five
distinct values and unstable whitespace that made it the most-changed field while
carrying no news, and `point`, which moves as crews narrow a fault down:

| Distinct states | Events | Cumulative |
|---:|---:|---:|
| 1 | 779 | 58.4% |
| 2 | 426 | 90.4% |
| 3 | 92 | 97.3% |
| 4+ | 36 | 100% |

So every update is rendered inline up to three, and only the middle ones are
folded behind a disclosure at four or more. That fires on 2.7% of events. The
threshold is this table, not a guess.

One subtlety worth keeping: a poll cycle records its list change and its detail
change seconds apart, so without coalescing them a plain `Fault → Restored`
transition read as two updates and inflated a third of all outages into the
disclosure. Changes within 15 minutes of each other are one update; polls are 30
minutes apart, so nothing real is merged.
