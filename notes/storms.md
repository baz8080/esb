# Storms: what a run can fetch, and what happens past that

Dated 2026-09-06. The collector had never seen a storm; this note is what a
simulation said it would have done, and what changed so it will not.

## The failure, measured on a simulation

Detail fetches ran one at a time, a second apart, and the service unit stopped
a run at fifteen minutes: about 880 details. The largest list in five calm weeks
was 120, and the longest run took two minutes, so nothing had tested the limit.
A storm might. Storm Éowyn in January 2025 put 768,000 customers off; at this
corpus's mean of about 260 customers per fault that is roughly 3,000 records,
though ESB may file storm damage more coarsely. The estimate is an inference,
the threshold is not.

What happened past the limit was simulated with a fake feed of 1,000 outages
and a run cut off after 300 fetches:

| Run | Fetched | Never fetched before |
|---|---:|---:|
| 1 | 300 | 300 |
| 2 | 300 | 0 |
| 3 | 300 | 0 |
| 4 | 300 | 0 |

After four runs 300 of the 1,000 had detail and no run row existed for any of
them. `ids_needing_detail` walked the list in ESB's order, and an outage first
seen inside the last six hours counted as "actively changing" and was fetched
again every run, so the head of the list took the whole budget and the tail was
never reached. An outage with no detail has no start time, no location and no
customer count: it never reaches the site, and ESB purges it a few hours after
restoration, so the loss is permanent. The kill itself, Python's default
handling of SIGTERM, ended the process mid-transaction: SQLite rolled the run's
work back, no run record was written, and no heartbeat was sent.

## What changed

Four things, one PR, because they are one fix.

- **Never-fetched outages go first.** `ids_needing_detail` now ranks its work:
  never captured, then changed state, then active re-checks, then stale ones,
  keeping ESB's order inside each rank. A re-check loses at most a revision; a
  first fetch missed is the record. The same simulation now covers the whole
  list in as many runs as it takes, each fetching only what no earlier run had
  (`tests/test_poll.py::TestStorm`).
- **Every detail is committed as it lands.** A run killed outright, with no
  chance to close itself out, still leaves the database knowing what it
  fetched, so the ranking has something to rank against. The raw log already
  carried the truth; this is about the next run not repeating the last one.
- **SIGTERM stops the loop instead of the process.** The run records itself
  with status `cut_short` and exit 0, and `run_poll` sends the heartbeat as for
  any run that reached the feed. A storm long enough to stop every run is a
  collector working flat out, not a stopped one, and must not raise the
  dead-man's alarm. It raises no webhook alarm either: nothing is lost that
  the next run will not take first. `esb stats` counts cut-short runs, which is
  the operator's sign that a storm outran the budget.
- **Half a second between fetches, and 25 minutes before the stop.** The
  second was courtesy, not a limit ESB states. At 500 ms a 25-minute run
  reaches about 3,000 details, inside the 30-minute interval with jitter to
  spare. The interval, the lock and the dormancy back-off are untouched: the
  lock is released by the kernel when a process dies, and the back-off is what
  keeps a calm day cheap.

The same 1,000-outage simulation, with a hard kill after 300 fetches that
bypasses the handler entirely, now reads:

| Run | Fetched | Never fetched before |
|---|---:|---:|
| 1 | 300 | 300 |
| 2 | 300 | 300 |
| 3 | 300 | 300 |
| 4 | 300 | 100 |

All 1,000 have detail after four runs. That is the ordering and the per-detail
commits alone; the handler adds the run record and the heartbeat on top.

The raw run record still says `ok` for a cut-short run, since it is written
before the details start and the log is append-only; a rebuild shows the run's
fewer observations rather than its status. Not worth a second raw record.
