# 14. The storm it had never seen
*~12 min read · PRs #41 and #42 · 6 September 2026*

*Where we are:* chapter 2 put a Raspberry Pi in a hall and gave it an alerting scheme built out
of exit codes. Five calm weeks later, two of that scheme's assumptions got tested: that the
collector can report its own failures, and that a run can always finish its work.

## The question that opened this stretch

Both halves of this chapter come from the same question, asked of a machine that has so far only
ever had good days: **what does this thing do on its worst day?**

Nothing in the first five weeks stressed it. The largest outage list was 120 records, the longest
run took two minutes against a fifteen-minute limit, and every failure the collector had actually
had was one it noticed and reported. So there was no evidence of a problem, and no evidence of
safety either. Both of these fixes are written against simulations and arithmetic rather than
against an incident, which is the only way to get ahead of a failure whose first occurrence is
expensive.

## Part one: the alarm that cannot report its own death

Chapter 2's alerting is a list of things the collector notices about itself: a rejected API key, an
unreachable feed, a schema that drifted, detail fetches failing across the board, a data directory
it cannot write. Each gets its own exit code and one push to a webhook, and each is silent when the
failure is the recoverable kind, because alerting on blips trains you to ignore alerts.

Every one of those alarms is raised by the collector. So the failure that class of alarm cannot
report is the collector not running at all. A Pi that is off. A timer somebody disabled during
unrelated maintenance. An SD card that died. An uplink that went and stayed gone. None of them runs
the code that would send the webhook, and the project's own README records alerting having broken
silently twice already in a short life.

The only signal that existed was the stale banner on the site (chapter 9), which trips ten hours
after the last push and therefore up to sixteen hours after the last poll. That is a notice on a
public web page, aimed at readers, doing double duty as monitoring for the person who runs the
thing.

> **Concept: an alarm that fires on silence.** Any alarm a system raises about itself shares a
> single point of failure with the system: the process that would raise it. The complement is a
> dead man's switch - the system sends a periodic sign of life to somewhere else, and that
> somewhere else raises the alarm when the signs stop. It inverts the direction of evidence.
> Instead of "I will tell you when I am broken", which requires me to be running, it is "I will
> tell you I am alive, and my silence is the message", which requires nothing of me at all. The
> two are complements rather than alternatives: the self-raised alarm says *what* is wrong and
> is useless when the machine is gone; the heartbeat says only *something* is wrong and works
> precisely then.

So the collector now pings `ESB_HEARTBEAT_URL` after every run that reached the feed, and a
dead-man's monitor - healthchecks.io, whose free tier is enough - raises the alarm when the pings
stop. It is about ten lines of standard library and one GET, best effort like the webhook, and it
cannot change the exit code. It is explicitly not a second webhook: ntfy has no way to alert on
silence, which is a different kind of service entirely.

The interesting parts are the edges, and all of them are decisions about what silence should mean:

- **Sent for the runs that half-worked.** Schema drift and a partial run exit non-zero and already
  reach the webhook, but the list is on disk and collection is happening. Going silent as well
  would raise a second alarm for a collector that is running.
- **Not sent for a rejected key or an unreachable feed.** Those raise both alarms, which is right:
  collection has stopped, whatever the cause, and the two channels agreeing is information.
- **Nothing when a trigger finds the lock held**, because the run holding it will ping.
- **Period 30 minutes, grace 90.** The timer fires every 30 minutes with up to three minutes of
  jitter, and `Persistent=true` runs a missed trigger as soon as the machine is back, so one
  missed poll is ordinary and three in a row is not.
- **Rejected: pinging from the six-hourly backup script instead.** Too coarse to notice a stopped
  collector, and the backup can succeed with the collector dead, which is the exact case the
  heartbeat exists to catch.

### Worked example: the tests that would have proved the collector alive while it was dead

Review of the first cut found two faults, and the second is the best cautionary tale in the
chapter.

The poll tests' base class never cleared `ESB_ALERT_WEBHOOK` or `ESB_HEARTBEAT_URL` from the
environment. On any machine where a shell had sourced the Pi's own environment file, every fake
green poll in the test suite would have sent a real ping to the real monitor. The monitor would
have gone on saying the collector was healthy, fed by a test suite, which is exactly the
false-alive signal a dead man's switch exists to rule out. A monitoring channel that a test can
write to is not a monitoring channel, and the fix is one line in a `setUp` that clears both.

The first fault is smaller and more ordinary: `sudo esb test-alert`, the command the README names
as proving both channels, could not prove the heartbeat, because the `esb` wrapper forwards an
allowlist of environment variables to the service user and the new one was not on the list. The
command would have reported the URL unset on the very Pi that had it set. Both the wrapper and the
service unit's comment now carry it.

One more, from CI rather than review: the 3.11 job lost the drifted-run heartbeat because the
one-shot test server gave up after half a second and the poll took longer than that on a loaded
runner. It now serves until the test shuts it down, which also dropped eleven server-backed tests
from 3.6 seconds to 0.6, because a test expecting no request no longer waits out a timeout.

## Part two: the storm

The second half is about the run itself. Detail fetches went out one at a time, a second apart,
and the service unit stopped a run at fifteen minutes: about 880 details. The largest list in five
calm weeks was 120, so the ceiling had never been approached, let alone tested.

Storm Éowyn, in January 2025, put 768,000 customers off. At this corpus's mean of about 260
customers per fault that is roughly 3,000 records, though ESB may well file storm damage more
coarsely. The estimate is an inference and is labelled as one in `notes/storms.md`; the threshold
it is compared against is not.

So the behaviour past the limit was simulated: a fake feed of 1,000 outages, a run cut off after
300 fetches.

| Run | Details fetched | Of those, never fetched before |
|---|---:|---:|
| 1 | 300 | 300 |
| 2 | 300 | 0 |
| 3 | 300 | 0 |
| 4 | 300 | 0 |

Four runs, 1,200 fetches, and 300 of the 1,000 outages had detail. Two independent faults produced
that.

`ids_needing_detail` walked ESB's list in ESB's order, and an outage first seen inside the last six
hours counted as "actively changing" and was re-fetched every run. In a storm the head of the list
is full of exactly those, so the head consumed the whole budget every time and the tail was never
reached at all. Meanwhile the kill itself - Python's default handling of SIGTERM - ended the process
mid-transaction, so SQLite rolled the run's work back, no run record was written, and the next run
began knowing nothing about what the last one had done.

And an outage with no detail is not delayed, it is lost: no start time, no location, no customer
count, so it never reaches the site, and ESB purges it a few hours after restoration (chapter 1).
The 112-minute retention that forced this project's whole design is also what makes a deferred
fetch permanent.

> **Concept: order the work by what a delay would destroy.** When there is more work than budget,
> the natural orders are all wrong: arrival order, the feed's order, or "new things first" each
> optimise for something other than loss. The right key is exposure - how much is unrecoverable if
> this item waits. A re-check of a live outage that waits loses at most one revision, and the
> outage is still in the feed next time. A restored outage whose detail was never captured is gone
> at the purge, taking the restore time with it and leaving that row ending on an estimate
> for good. So the ranking is: anything listed Restored that still needs a fetch, whether never
> captured or just flipped, then live outages never captured, then changed state, then active
> re-checks, then stale ones, keeping ESB's own order inside each rank. The first cut of this put
> every never-fetched outage ahead of the just-flipped ones, which in a sustained storm would have
> deferred the flipped ones every run until the purge took them - the same bug one level down.

Four changes went in together, because they are one fix:

- **The ranking above**, by exposure rather than by ESB's order.
- **Every detail is committed as it lands**, so a run killed outright still leaves the database
  knowing what it fetched. The raw log always had the truth; this is about the next run not
  repeating the last one.
- **The run stops itself** at `RUN_BUDGET_S`, 24 minutes, and records itself with status
  `cut_short` and exit 0. `esb stats` counts those, which is the operator's sign that a storm
  outran the budget.
- **Half a second between fetches** instead of one: the second was courtesy, not a limit ESB
  states. A 24-minute run now reaches about 2,800 details, inside the 30-minute interval with
  jitter to spare. The interval, the lock and the dormancy back-off are untouched.

A cut-short run sends its heartbeat and raises no webhook alarm, and that combination is the design
statement: a storm long enough to stop every run is a collector working flat out, not a stopped
one, and nothing is lost that the next run will not take first.

Which is also why the first cut's approach was wrong in a way worth naming. It enforced the budget
with systemd's start timeout alone - let the unit run until systemd stops it. But a unit systemd has
to stop is a *failed* unit in the journal, whatever exit code the process manages on the way out, so
every busy run would have been recorded as a failed collector. A process that has a rule about when
to stop has to enforce that rule itself; a supervisor's timeout is a backstop, and it now sits a
minute beyond the run's own budget with the SIGTERM handler kept for it. (The stop is checked after
the inter-fetch sleep, since a signal landing during the sleep resumes it and must not be allowed
to start one more fetch.)

The same simulation, with a hard kill after 300 fetches that bypasses the handler entirely:

| Run | Details fetched | Of those, never fetched before |
|---|---:|---:|
| 1 | 300 | 300 |
| 2 | 300 | 300 |
| 3 | 300 | 300 |
| 4 | 300 | 100 |

All 1,000 have detail after four runs, and that is the ordering and the per-detail commits alone,
before the handler adds the run record and the heartbeat on top.

## What is still open

Two things, both written down rather than quietly carried.

The raw run record still says `ok` for a cut-short run, because it is written before the details
start and the log is append-only (chapter 1: the logs are never edited). A rebuild therefore counts
the unfetched tail as skipped, so `esb stats` on a rebuilt database will overstate the back-off's
"% avoided" across storm runs. Accepted: a second raw record kind would change the shape of the
log for a number nobody grades on.

And there is a third gap in the alarm scheme, open as issue #43 at the time of writing. A 200
response with an empty outage list passes every check: the key is accepted, the shape is right,
there is nothing to fetch, the run records `ok`, and the heartbeat pings happily. If ESB ever
changed what the endpoint returns behind a still-valid key, collection would stop and nothing would
say so. In 1,644 runs the list has never been below two outages, so the proposed rule is six
consecutive empty runs - three hours - raising the webhook once. Deliberately not a heartbeat
change: the collector is running and reaching the feed, so a dead man's switch should keep hearing
from it.

## The water site has none of these problems, and the reason is the same one

Chapter 2 set the two collectors against each other: a cloud scheduler twice a day there, a Pi
every 30 minutes here, with the same measurement reaching opposite conclusions because the water
notices linger and the ESB records purge. Both halves of this chapter are that same fact, arriving
later and harder.

The water site's collector runs in a hosted CI service, so a failed run is recorded by a system its
author does not operate, and the specific failures this chapter is about - a dead card, a lost
uplink, a timer somebody disabled - are somebody else's to have. That site has a blind spot of its
own shape, a schedule the platform quietly stops running, but it does not have to build the
machinery to detect a machine that is simply gone. This one runs on hardware in a hall, where every
observation about its own health is made by the thing whose health is in question, so it has to buy
its watchdog separately.

And a storm is only an emergency here because of the purge. If the water site's collector could
fetch only a third of its feed one day, the rest would still be there tomorrow: its notices stay
listed for days or weeks, and the archive would simply catch up. Here the tail of an unfinished run
is not deferred work, it is a hole in the record that no later run can fill. The clock that made
this project write everything down before parsing it is the same clock that makes an unfinished run
a data loss rather than a delay.

## Notes

- `notes/alerting.md` "The heartbeat" (6 Sep 2026): what the self-raised alarms cannot report; the
  banner's 10 hours after the last push and up to 16 after the last poll; which runs ping and which
  do not; period 30 / grace 90 and the jitter and `Persistent=true` behind them; ntfy cannot alert
  on silence; the rejected backup-script ping.
- `notes/storms.md` (6 Sep 2026): the pre-change limits (one second apart, 15-minute unit timeout,
  ~880 details) against the calm-week maximum of 120; Storm Éowyn's 768,000 customers and the
  ~3,000-record inference; both simulation tables; the exposure ranking with its first-cut error;
  `RUN_BUDGET_S` 24 minutes, `cut_short`, the 25-minute backstop, 500 ms and ~2,800 details; the
  accepted rebuild residue.
- README § The heartbeat and § Alerting; `scripts/esb-wrapper.sh` (the forwarded variable);
  `tests/test_poll.py::TestStorm`. PRs #41 and #42, both merged 6 September 2026. Issue #43, open,
  for the empty-list alarm, with its 1,644-run measurement.
- Chapter 1 for the purge and the append-only log, chapter 2 for the exit-code scheme and the
  dormancy back-off, chapter 9 for the stale banner's threshold.
