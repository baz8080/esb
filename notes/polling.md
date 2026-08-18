# Should the poll interval be 15 minutes?

*Measured 2026-08-18. Answer: no material gain at 30 minutes; revisit only if
short outages become the point of the site.*

The experiment: take the real 16-day corpus, drop every second poll to simulate
a 60-minute cadence, rebuild, and compare. Halving the rate shows what finer
polling would have to give back.

| | 30 min | 60 min | change |
|---|---:|---:|---:|
| Events detected | 1,333 | 1,269 | **−4.8%** |
| First seen already restored | 85 | 72 | −15.3% |
| Faults with a **confirmed** restore time | 573 | 288 | **−49.7%** |
| Faults ending on a "last listed" guess | 69 | 70 | +1.4% |
| National CI (ESB 1.38) | 1.86 | 1.53 | −18.1% |
| National CML (ESB 117.5) | 171.6 | 163.7 | −4.6% |
| % back inside 4 hours | 88.4 | 86.1 | −2.7% |
| Events hitting the update disclosure | 36 | 24 | −33.3% |

The 30→60 step is costly, which is the argument for *not* going coarser. It is
not automatically an argument for going finer, because the curve flattens:

**At 30 minutes, 85% of fault events already carry a confirmed restore time**
(it was 47% at 60 minutes). The remaining 15% splits into:

- **36 events (5%) ending on ESB's estimate** — the only group a finer poll
  could convert to a measured duration.
- **69 events (10%) ending on a "last listed" guess** — and for **66 of those
  the list endpoint never showed them as `Restored` at all**. ESB dropped them
  without ever publishing a restore time. No poll rate fixes that; it is missing
  at source.

So the realistic headroom is about 5% of fault durations, plus some improvement
in event detection.

## What finer polling would actually buy

Detection of **short** outages, specifically. The 96 ids visible at 30 minutes
but lost at 60 had a median duration of **0.65 h against 3.68 h for all events**,
and 64% of them were under an hour (against 13% overall). The poll interval is
essentially a filter on how short an outage can be and still be seen.

That matters more than it used to, because the site now surfaces repeat-fault
chains, and **8 of 32 chain legs are shorter than a single 30-minute poll** — the
shortest is 9 minutes. Those legs survive today only because ESB's own
`startTime` and `restoreTime` are carried in the record whenever the record is
seen at all; the poll rate decides whether the record is seen, not how well it
is timed.

Worth noting for the CI bias: under-detection of short outages *suppresses* our
interruption count, so the real overcount from `numCustAffected` is larger than
the 1.35× measured, not smaller.

## Cost

| | 30 min | 15 min (projected) |
|---|---:|---:|
| List fetches | 45/day | 89/day |
| Detail fetches | 699/day | ~1,400/day |
| Raw log growth | 178 MiB/year | ~360 MiB/year |

Detail fetches scale with polls rather than being capped by the dormancy
back-off: the 60→30 step took them from 345/day to 699/day, a factor of 2.02.

The log growth is the real cost. The raw JSONL is the source of truth, is
committed to git daily, and can never be pruned — so the rate is permanent, and
the git history carries it too.

## Verdict

Doubling a permanent archive to convert 5% of durations from estimated to
measured is a poor trade. Stay at 30 minutes.

Revisit if either changes: short outages become something the site reports on
directly (the repeat chains are the current candidate), or ESB starts publishing
restore times for the outages it currently drops silently, which would raise the
ceiling that makes 30 minutes good enough today.
