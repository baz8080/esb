# How the A–F grade was derived

*Written 2026-08-17, against the first 16 days of collected data (1,457 outages).*

The sibling water site's grade needed months of iteration because it had no
external anchor: the thresholds were calibrated to its own distribution of
county-months, which makes them honest but circular. Electricity does not have
that problem. Irish distribution reliability is regulated, in public, in a
specific unit, against a specific target.

## The published prior art

ESB Networks reports two continuity measures every year, and the CRU attaches
money to both. From the Distribution Annual Performance Reports:

- **CI** — Customer Interruptions: interruptions longer than three minutes that
  an average customer experiences in a year.
- **CML** — Customer Minutes Lost: minutes an average customer spends without
  supply in a year.

Both are reported **excluding storm days**, so that utilities can be compared.

| Year | Unplanned CML | CRU target | Unplanned CI | CI target | Planned + unplanned CML |
|------|--------------:|-----------:|-------------:|----------:|------------------------:|
| 2022 | 103.34 | 82.9 | – | – | – |
| 2023 | 105.59 | 80.8 | 126.38 | 114.8 | 207 min |
| 2024 | 117.47 | 78.7 | 137.86 | 112.7 | 219 min |

Targets fall about 2.1% a year. ESB has missed them throughout PR5 and been
penalised roughly €37m for it. The network serves about 2.4 million connected
customers and has a 6:1 ratio of overhead to underground line, which is the
usual explanation offered for the gap. 2024 had a record 24 storm days.

Sources: [DAPR 2024](https://media.esbnetworks.ie/media/docs/default-source/publications/distribution-annual-performance-report-2024.pdf),
[DAPR 2023](https://esbnetworksprdsastd01.blob.core.windows.net/media/docs/default-source/publications/distribution-annual-performance-report-2023-accessibled434eedca532460d959ccfba328306eb.pdf),
[CRU PR5 framework](https://cruie-live-96ca64acab2247eca8a850a7e54b-5b34f62.divio-media.com/documents/CRU20154-PR5-Regulatory-Framework-Incentives-and-Reporting-1.pdf),
[CEER Benchmarking Report 6.1](https://www.ceer.eu/wp-content/uploads/2024/04/C18-EQS-86-03_Benchmarking_Report_6.1.pdf).

## What this dataset measures against those numbers

Over the 16-day window, computed from the collected feed:

| Measure | This pipeline | ESB 2024 | Ratio |
|---|---:|---:|---:|
| Unplanned CML, annualised | 195.0 | 117.47 | **1.66×** |
| Unplanned CI, annualised | 2.21 | 1.38 | **1.60×** |
| Implied CAIDI (CML ÷ CI) | 88.2 min | 85.1 min | **1.04×** |

**The durations are right and the customer counts are not.** CAIDI cancels the
customer count and leaves only the clock, and it lands within three minutes of
ESB's own figure. CI and CML are both high by the same ~1.6×.

The explanation is in what `numCustAffected` is. PowerCheck reports the
customers on the affected section when a fault is logged; ESB settles on a
smaller number once crews have isolated it. The feed shows this happening
directly — outage 2831024 was published at 83 customers and finished at 19 — and
553 of 1,457 outages had their coordinates revised as the fault was narrowed
down. We take the count as reported at each moment; ESB reports what it
concludes afterwards.

### Why that forced a ratio-based grade

Applying ESB's absolute thresholds to a scale running 1.66× hot would have given
almost every county a D or an F for a bias that has nothing to do with the
county. So the bands are expressed as **ratios to the national figure measured
by this same pipeline**, and the CRU target is carried across as *its* published
ratio to what ESB actually delivered:

| Grade | Ratio to national | Derivation |
|-------|------------------:|------------|
| **A** | ≤ 0.67 | 78.7 / 117.47 — the CRU's 2024 target as a fraction of ESB's actual |
| **B** | ≤ 1.0 | at or better than the national average |
| **C** | ≤ 1.5 | |
| **D** | ≤ 3.0 | |
| **F** | > 3.0 | |

Numerator and denominator carry the same bias, so it cancels. What survives is
the comparison between counties, which is the thing a reader actually wants.

On August 2026 this gives A 9, B 7, C 2, D 7, F 1 — a real spread, with Wexford
the only F. `tests/test_site_national.py` holds the CI ratio inside 1.2–2.4 and
requires CML to stay off by the same factor CI is, so a drift in either is
caught rather than quietly absorbed into the letters.

## Settled, with the numbers

**Planned works are excluded from the grade.** The CRU's incentive excludes
them, they are notified in advance, and — decisively — not one of the 675
planned outages in the corpus ever reported a restore time. `Planned → Restored`
never occurs; planned works simply stop being listed. Their duration is an ESB
estimate that ESB never confirms.

**Storm days are not excluded**, because nothing in the feed identifies one. ESB
excludes them; this site cannot, so winter months will read worse than ESB's own
figures for a reason that is not ESB's fault. Said plainly in the page footer.

**The end of an outage without a restore time is the ESB estimate, not the last
sighting.** Measured against the 648 outages whose true restore time is known:

| Fallback | Bias | MAE | Total duration vs truth |
|---|---:|---:|---:|
| Last time it was still listed | +3.78 h | 3.78 h | **2.26×** |
| ESB's estimated restore time | +0.39 h | 1.31 h | **1.13×** |
| min(estimate, last listed) | +0.54 h | 1.41 h | **1.18×** |

ESB leaves restored outages sitting in the feed for hours, so the last sighting
overstates duration by 126%. The estimate is used when it falls between the
start and the last sighting; otherwise the last sighting is the tighter bound.
Outages carry which of the three their end came from, and the page says so.

**Customer-minutes are integrated over the reported count, not multiplied.** The
count is not constant — crews restore in sections. Multiplying the final count
by the whole duration understates; the first count overstates.

**Customers per county are apportioned from Census population**, because ESB
publishes no per-county customer count. This is the one real approximation in
the chain. Worth replacing with CSO household counts if a county ever looks
systematically wrong; the ratio-based grade makes the site fairly insensitive to
it, since an error would have to be county-specific to move a letter.

**Counties come from the nearest Census Small Area centroid.** The feed has no
county field, no Eircode — only `point.c`. This placed 1,457 of 1,457 outages
across all 26 counties with nothing left over. The water site's
radius-and-population footprint was deliberately not carried over: ESB publishes
a point per outage, not a service area, so spreading one pin over its neighbours
would invent coverage the data never claimed.

## Day cells

Coloured by magnitude, not by presence: 66% of county-days carried at least one
fault, so a bar that reddened for "an outage happened" would be a near-solid
wall. Thresholds are absolute fault minutes-lost per customer per day, fixed so
that a published day never changes colour afterwards.

| Bucket | min/customer/day | Share of the first month |
|---|---:|---:|
| Normal | < 0.05 | 44% |
| Minor | < 0.3 | 22% |
| Moderate | < 1.0 | 19% |
| Major | < 3.0 | 9% |
| Severe | ≥ 3.0 | 6% |

## The update disclosure

Counting only reader-visible fields — excluding `statusMessage`, which has five
distinct values and unstable whitespace that made it the most-changed field in
the corpus while carrying no news, and `point`, which moves as crews narrow a
fault down:

| Distinct states | Outages | Cumulative |
|---:|---:|---:|
| 1 | 863 | 59.2% |
| 2 | 471 | 91.6% |
| 3 | 93 | 97.9% |
| 4+ | 30 | 100% |

So every update is rendered inline up to three, and only the middle ones are
folded behind a disclosure at four or more. That fires on 2.1% of outages. The
threshold is this table, not a guess.

One subtlety worth keeping: a poll cycle records its list change and its detail
change seconds apart, so without coalescing them a plain `Fault → Restored`
transition read as two updates and inflated a third of all outages into the
disclosure. Changes within 15 minutes of each other are one update; polls are 30
minutes apart, so nothing real is merged.
