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

- **What a purge would take goes first.** `ids_needing_detail` now ranks its
  work by exposure, keeping ESB's order inside each rank: anything listed
  Restored that still needs a fetch, whether never captured or just flipped,
  because ESB purges a few hours after restoration and not before; then live
  outages never captured, which keep their place in the feed while they are
  out; then changed state, active re-checks, stale ones. A re-check loses at
  most a revision; a restore time missed leaves the row ending on an estimate
  for good. The first cut ranked every never-fetched outage ahead of the
  flipped ones, which in a sustained storm would defer the flipped ones every
  run until the purge took them. The same simulation now covers the whole
  list in as many runs as it takes, each fetching only what no earlier run had
  (`tests/test_poll.py::TestStorm`).
- **Every detail is committed as it lands.** A run killed outright, with no
  chance to close itself out, still leaves the database knowing what it
  fetched, so the ranking has something to rank against. The raw log already
  carried the truth; this is about the next run not repeating the last one.
- **The run stops itself, and SIGTERM stops the loop instead of the process.**
  A run ends its fetching at `RUN_BUDGET_S`, 24 minutes (22 since
  2026-09-24, below), records itself with
  status `cut_short` and exit 0, and `run_poll` sends the heartbeat as for any
  run that reached the feed. A storm long enough to stop every run is a
  collector working flat out, not a stopped one, and must not raise the
  dead-man's alarm. It raises no webhook alarm either: nothing is lost that
  the next run will not take first. `esb stats` counts cut-short runs, which is
  the operator's sign that a storm outran the budget. The service unit's
  `TimeoutStartSec` sits a minute beyond as a backstop, and the first cut
  relied on it alone: a unit systemd has to stop is a failed unit whatever
  the process exits with, so the "not an alarm" design needed the run's own
  clock. The SIGTERM handler stays for the backstop, and the stop is checked
  after the inter-fetch sleep, since a signal landing during the sleep
  resumes it and must not start one more fetch.
- **Half a second between fetches.** The second was courtesy, not a limit ESB
  states. At 500 ms a 24-minute run reaches about 2,800 details, inside the
  30-minute interval with jitter to spare. The interval, the lock and the
  dormancy back-off are untouched: the lock is released by the kernel when a
  process dies, and the back-off is what keeps a calm day cheap.

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
fewer observations rather than its status, and counts the unfetched tail as
skipped, so `esb stats` on a rebuilt database overstates the back-off's "%
avoided" across storm runs. Known and accepted: a second raw record kind for
the run's end would change the log's shape for a number nobody grades on.

### The run's end is logged after all (2026-09-24)

The paragraph above accepted the gap; a retroactive review of the collector
raised it again and the owner reversed it. The gap was wider than the "%
avoided" figure: every non-`ok` outcome a run decides after its list line
(`cut_short`, `partial`, `schema_drift`, a key rejected mid-run) came back from
a rebuild as `ok`, with no finish time, exit code or error summary. On the
corpus to 24 September the raw runs said `ok` 2,470 times and nothing else, so
`esb stats` on the rebuilt database reads "runs cut short: 0" whatever
happened in a storm.

`Store.finish_run` now appends a second line for every run, `"event": "end"`,
before writing the run row, carrying only what cannot be derived:
`finished_at`, `status`, `exit_code`, `n_detail_skipped`, `n_errors` and
`error_summary`. `rebuild` prefers it when present. Older runs have none and
replay as before, from the start line's status and derived counters. The line
is written with sorted keys like every other, so `sort -u` merges still hold,
and it goes in the month file of its own timestamp, so a run crossing midnight
on the last day ends in the next month's file.

Two edges follow from having two lines per run. A start line now carries
`"ends_logged": true`, and one with that flag but no end line is a run that
died before closing itself out (an uncaught exception, a full disk, a kill
the SIGTERM handler never saw): a rebuild records it as `unfinished`, where
the live database has no row for it at all, rather than as a clean `ok`. The
newest such run reads `in_progress` instead, because the six-hourly backup
commits `raw/` without the poll lock and often catches a run mid-flight. (The
backup takes the poll lock since 2026-09-24, so a new snapshot no longer does;
the label stays for the ones already pushed.)
The flag, not the date of the first end line, is what decides: a merged log
from a host still on the old code, or a Pi that booted with a wrong clock,
would otherwise relabel every older-style run after it. An end line whose
start line was lost replays as a run with no list, started at the time its
run id carries, so its observations keep their place. Two copies of
the same line, from a merge without `sort -u` or a `compact` that crashed
before removing what it had archived, are read once.

## The budget leaves room for the last fetch - 2026-09-24

`RUN_BUDGET_S` was 24 minutes against a `TimeoutStartSec` of 25, but the
budget is checked only between fetches. After it come the slowest fetch, the
webhook for a partial or drifted run, and the heartbeat. Each request can
time out on connect to two addresses (IPv4 and IPv6) and then on the read, so
one fetch attempt can take three 15-second timeouts, three attempts plus about
five seconds of backoff come to 140 seconds, and the webhook and the ping add
30 each: 200 seconds past the budget. That is a storm with a degraded API,
exactly when runs reach the budget, and systemd would fail the unit and kill
the heartbeat mid-send.

The budget is now 22 minutes and the backstop 26: 1,520 seconds at worst,
inside 1,560. The backstop cannot grow further, because the timer's three
minutes of jitter plus the backstop must end before the next trigger, 30
minutes on. A poll also waits up to two minutes for the lock while the backup
commits, and the budget counts from the start, so that wait comes out of it
rather than pushing the end later. 22 minutes is about 2,550 details at 500 ms.
`TestTheBackstop` recomputes all of this from the client's, the alert's and
the poll's constants and the two unit files.
