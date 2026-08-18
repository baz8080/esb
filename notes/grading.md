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

## Does `startTime` drift?

*Measured 2026-08-18. It does not, and it is back-dated to the fault, not the notice.*

**It is effectively immutable.** Across 1,460 outages ESB revised `startTime`
**8 times** (0.5%) — two of them by a single minute, the rest between −82 and
+363. For comparison, `statusMessage` changed 639 times and `outageType` 534.
Nothing about the start drifts as an outage develops.

**It is back-dated, not set to publication time.** Comparing the reported start
against our first sighting of the record:

| Lag, reported start → first sighting | Faults | Planned |
|---|---:|---:|
| p25 | 21 min | 12 min |
| median | 32 min | 21 min |
| p90 | 147 min | 34 min |
| Negative (listed before its own start) | **0** | **0** |

Our own 30-minute poll accounts for most of the median: for the 593 faults we
caught live the median lag is 31 minutes, one poll interval, so ESB's own
publication lag is close to zero at the median. Not one outage in the corpus
appeared in the feed before its reported start, so the field is never
forward-dated.

This is the single most important thing about the data, and it is what the
sibling water site could not claim. **Durations here measure the outage, not the
notice.** The long tail (p90 of 147 minutes for faults) is real — some faults
are published hours after they began — but it delays when we *learn* of an
outage rather than corrupting how long it is recorded as lasting.

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

## What the clock knows and what the data knows (2026-08-18)

Two windows were being conflated: the build clock, and how far the collected
data actually reaches. `now` was used for both, which is harmless only while the
collector is keeping up.

**Every measured window now ends at the collection horizon** — the last run in
the log that reached the feed (`n_listed IS NOT NULL`; a run that died on auth
or could not connect observed nothing). `now` survives in exactly one place: to
decide which days are still in the future.

Two things were wrong, both in the same direction — they made an absent
collector look like a calm network.

- **Days past the horizon were coloured.** A day nobody polled rendered as "no
  significant fault", in green, with a build timestamp beside it that looked
  fresh. On the corpus as checked out, 17 and 18 August were published as quiet
  for all 26 counties against a last observation of 16 August 23:00. They are
  now `DAY_NO_DATA`, and the page prints the horizon next to the build time,
  flagged past 24 hours.
- **CML was divided by wall-clock time.** Annualising over a window that
  included the gap understated the rate: on that same corpus, 161.7 against a
  corrected 176.1 CML/yr, a 9% understatement from 36 hours of absence.

### An outage still listed is not a fast restoration

The charter share was meant to skip outages still running — "no restoration time
to judge" — but the test that was supposed to do it, `o.end <= hi`, could not:
an unfinished outage ends at the horizon and so does the window, so it always
passed and was scored on how long it had been out *so far*.

A fault half an hour old counted as restored inside four hours. Replaying the
corpus at 05:40 (the Pages build time) on each of 16 August days, **15 of the 16
had at least one fault open** — 25 on the 4th — so this flattered the grade on
essentially every build. `Outage.ongoing` now carries it: still listed within a
poll cycle of the horizon, and no restore time.

Rejected: excluding every outage without a confirmed `restoreTime`. That would
also drop the ones that simply stopped being listed, which is the ordinary way a
fault ends here, and it contradicts ending an outage on ESB's estimate above.
The question is whether the outage was *over*, not whether ESB said so.

Kept deliberately: an ongoing outage past 24 hours still counts against the
compensation threshold. The time it has already run is a lower bound, so "this
has been out more than a day" is true whatever happens next.

### The peak is the highest count while the outage was live

The customer count is clipped to the outage's own window before empty segments
are dropped, not after. ESB leaves restored outages sitting in the feed for
hours, and those late observations sometimes carry a revised count; testing the
uncut bounds kept them as inverted segments, and `customers` maxes over the lot.

So `customers` means *the most customers reported off at any moment the outage
was running*, and a figure attached to the id after ESB called it restored does
not raise it. On the corpus as it stands no event's peak came from one of these
— 17 events carried an inverted segment and none of them was the maximum — so
this changes no published number today. It is a definition, fixed before a
revision upward makes it a number.

### Short days say so

The first day of collection and the last are watched for hours, not 24. Their
cells are built from less time than the days beside them, and because the
buckets count disruption accumulated across a day, a short day reads calmer than
it was — 31 July 2026 is under three hours and renders green.

Rejected: greying them out. The trailing short day is the most recent day the
site has, which is the one a reader most wants to see. Also rejected: pro-rating
the day's minutes up to 24 hours, which invents precision a 30-minute poll does
not have and would make a single fault in a two-hour window look like a
catastrophe.

Kept: the colour is what was actually seen, and the day's tooltip says "only
part of this day was recorded". Two dates for the whole site, so they sit at the
top of the payload rather than on every county's row.

## The customer denominator, and which ESB figures to compare with (2026-08-18)

CML and CI are both *per customer*, so the denominator sets the scale of every
national figure this site prints.

It was 2.4 million, cited to a "almost 2.4 million domestic, commercial and
industrial customers" said to be on the Key Statistics page of DAPR 2024. That
string is not in DAPR 2024. The only customer count in the report is in the
Distribution System Statistics — **"c. 2.5 million customer meters"** — and the
company page agrees: *"roughly 2.5 million customers connected"*
([about-us/company](https://www.esbnetworks.ie/about-us/company)). So the lower
figure was carrying a citation it did not have, and it is now 2.5 million.

It moves everything down by 4.2%:

| | Before | After | ESB 2024 | Ratio now |
|---|---:|---:|---:|---:|
| CML | 176.1 | **169.0** | 117.47 | 1.44× |
| CI | 1.91 | **1.83** | 1.38 | 1.33× |
| CAIDI | 92.2 | 92.2 | 85.1 | 1.08× |

CAIDI does not move, and cannot: the customer count divides out of it. That is
worth keeping in view — it is the one index that says whether the *timing* is
right, and no choice of denominator can flatter it.

This is a meter count, not a headcount, and ESB does not publish the denominator
it divides by, so the match cannot be exact. It is the closest figure ESB
states, which is the whole standard being applied: anything compared against
ESB's own numbers has to be built the way ESB builds it.

### The 1.75 trap

DAPR 2024's summary bullets say the average customer had *"an outage or Customer
Interruption exceeding three minutes approximately 1.75 times"* and was without
power *"for 219 minutes"*. Neither belongs beside the constants in `model.py`.
Those are the all-in figures — planned and unplanned together, storm days
included. The unplanned, storm-excluded pair this site compares against is in
the performance section, quoted exactly:

> In 2024, these targets were set at 78.7 CML and 112.7 CI. Our performance
> against these unplanned outage targets stood at 117.47 CML and 137.86 CI for
> 2024.

CI there is per 100 customers, hence 1.3786. 1.75 against a CML of 117.47 would
be comparing two different populations, and it would silently drag the measured
bias down by a fifth.

### When to refresh

DAPR 2024 was issued **September 2025** and is the newest published as of August
2026. DAPR 2025 is due around September 2026: when it lands, update
`ESB_CRU_TARGET_CML`, `ESB_NATIONAL_CML` and `ESB_NATIONAL_CI` together, take
them from the unplanned-target paragraph rather than the summary bullets, and
re-check the customer count in the same edition.
