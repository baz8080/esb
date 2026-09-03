# 9. The cron that never ran in the morning
*~9 min read · PRs #32 to #34 · 2 September 2026*

*Where we are:* chapter 6b sized a staleness warning against a publishing schedule, and was
proud of the arithmetic. This chapter is what happened when someone checked whether the
schedule was real.

## The question that opened this stretch

The page said `Updated 22 hours ago - collection has stopped`, and the collector had not
stopped. The data repository held data from nine hours earlier. So the banner was wrong twice
over: wrong about the age, and wrong about the cause.

Chapter 6b's threshold was not the bug. The bug was that the sentence beside it named a
culprit the page could not possibly identify.

## What changed

### The banner stopped naming a cause (PR #32, 2 September)

The wording is gone. `freshness()` no longer takes the site-specific note chapter 6b had
carefully parameterised, because **from a browser, a build that stopped and a collector that
stopped look identical**: both leave the page holding old data, and nothing the page can see
tells them apart. Saying "collection has stopped" was an inference the page was in no position
to make. What survives is the age and the red, which is what chapter 6b's own decision had
already concluded was doing the work - the warning, not the wording (`notes/publish-cadence.md`,
2 Sep 2026). A follow-up pull request dropped the now-ignored argument from the call site once
the shared layer's pin caught up, deliberately in that order: dropping it first would have
rendered a dangling separator against the old pin (PRs #33 and #34).

That removed the excuse, and left the real fault underneath it.

### The cron had not been running when it said it did

Chapter 6b's arithmetic assumed the site rebuilt at 05:40 and 12:40 UTC, because that is what
the workflow asks for. Someone finally checked the actual run times over the week to
1 September:

| Cron asked for | What actually ran, UTC |
|---|---|
| `40 5` | 10:23, 10:38, 11:46, 11:48, 13:38, 16:46, 17:40 |
| `40 12` | 16:51, 16:53, 16:56, 19:13, 22:33, 22:36 |

**Four to ten hours late, every day, and the morning slot never once landed in the morning.**
This is not the ordinary jitter: before 26 August, with a single `40 5` cron, runs started
between 05:58 and 06:06Z, which is the 18 to 26 minutes GitHub documents. Only *scheduled*
events are throttled this way; push- and dispatch-triggered runs are unaffected, and the merge
on 1 September built seconds after its push.

> **Concept: a schedule you asked for is not a schedule you have.** Chapter 6b derived a
> staleness threshold from a publishing cadence, and every number in that derivation was taken
> from the configuration rather than from the log of what ran. The configuration is a request.
> On a shared build service a scheduled job is best-effort, and here the effort was four to
> ten hours short, consistently, for a week. The general form: when an argument rests on "this
> runs at time T", the evidence for T is the recorded start times, not the line that asks for
> it. This is the same discipline the rest of this account applies to the *data* - chapter 5's
> horizon exists because `now` was standing in for something it could not know - turned on the
> project's own infrastructure for the first time.

**Retiming the cron was rejected**, and the reasoning is worth keeping: a four-to-ten-hour
delay cannot be aimed at a one-hour window, so a better cron time only moves where the miss
lands.

### The fix is to stop scheduling and start reacting

The insight that makes the obvious fix wrong is one the series has met before, from chapter
6b: the age on the page is the age of the *data*, measured from the collection horizon against
the reader's clock. Rebuilding later cannot make that number smaller. Moving the build into
the morning does nothing for a reader at nine o'clock if the build carries yesterday's noon
data either way. Only two things move it: pushing more often, and building promptly after a
push the site has not yet seen.

So the data repository now dispatches the site build on every push, and the site rebuilds
within a minute of the data landing. The crons stay on as a fallback for a dispatch that never
fires, moved to `0 7` and `0 14` UTC - and the choice of the hour boundary is itself a small
piece of reasoning worth recording: Actions cron has no timezone, and Irish daylight saving
shifts Dublin by exactly one hour, so for a one-hour local window only the hour boundaries
land inside it in both seasons (07:00Z is 07:00 local in winter and 08:00 in summer).

### Chapter 6b's threshold, resized

The collector's push slots moved from twice a day to every six hours - `00,06,12,18` local -
and this is what actually caps how old the page can look, because the site is only ever as
current as the last push.

#### Worked example: the same arithmetic, one cadence later

Chapter 6b's calculation, redone against the new schedule. A six-hour slot, plus up to 30
minutes of deliberate jitter, plus up to one 30-minute poll interval between the last poll and
the push, gives a legitimate worst case of about **7 hours** - against about 13 under the old
twice-daily slots, which is why the page could show half a day old while everything was
working. `STALE_AFTER` therefore goes from 16 hours to **10**: 16 was sized for the
twice-daily gap and under a six-hourly cadence would fire only after more than two consecutive
pushes were missed, which is not a warning. Ten clears the ~7-hour legitimate maximum with room
and flags a single missed push (13h+) within a few hours (`notes/publish-cadence.md`).

The concept from chapter 6b survives intact - a staleness threshold is sized to a cadence -
and this is what it looks like when the cadence changes underneath it: the same three
quantities, re-derived, with the numbers moving together. What the chapter got wrong was not
the method but one of its inputs.

An alternative was measured and rejected, which is the house style: two pushes a day shifted
to 07:00 and 19:00 local keeps the commit volume and improves the *mean* age across waking
hours (~5.4h against ~6.4h), but leaves the peak at ~12h. Six-hourly gets the mean to ~3.2h and
the peak to ~7h, for two more commits a day against a repository whose entire purpose is being
appended to.

### An ordering constraint on the Pi

One deployment detail belongs to chapter 1's contract, and shows what it costs to have a
hardware department. The threshold and the push schedule have to move together, and the Pi is
not deployed by the same mechanism as the site. Merging the 10-hour threshold while the Pi was
still pushing twice daily would have shown the red banner for roughly the last three hours of
every 12-hour window, every day - precisely the false alarm the change exists to end. The
pull request says so at the top: re-run the installer on the Pi first. Measured live during
implementation, the lag was already 10.2 hours at 09:12Z, over the new threshold and under the
old one.

The installer copies only the collector and the scripts, and the sole file in that set the
branch touches is the timer, so the deployment changes exactly one thing on the Pi and no
collector code differs from `main`. That precision is what makes it safe to say "deploy this
half first".

## Where it left the site

The page is now current within about seven hours at worst rather than thirteen, usually within
minutes of a push, and its warning names an age rather than a cause. The change is
deliberately a *publishing* change and not a collection one: the 30-minute poll interval
chapter 2 settled is untouched, and no observation is gained or lost by pushing more often.
Four repositories moved together for it - the site, the data, the shared layer and the lift
site, which had broken the same way and carries the same note.

## Notes

- PR #32 (2 Sep 2026): the 22-hours-ago banner over 9-hour-old data; the cron run-time table
  (4 to 10 hours late; 05:58-06:06Z before 26 Aug); retiming rejected; dispatch-on-push with
  crons at `0 7` / `0 14` UTC as fallback and the DST hour-boundary reasoning; pushes
  `00,06,12,18`; ~7h legitimate max vs ~13h; `STALE_AFTER` 16h to 10h; the 07:00/19:00
  alternative (mean ~5.4h vs ~3.2h, peak ~12h vs ~7h); the install-first ordering and the
  10.2h lag measured at 09:12Z; 225 tests against the real corpus.
- PRs #33 and #34 (2 Sep): the statusui pin bump carrying the reworded banner, then dropping
  the argument `freshness()` no longer takes.
- `notes/publish-cadence.md` (2 Sep 2026), carried identically by the lift site; the CLAUDE.md
  settled rows for the cadence and the banner were rewritten with it.
- Chapter 6b holds the superseded arithmetic (twice-daily pushes, builds at 05:40 and 12:40
  UTC, `STALE_AFTER` 16h) and the concept this chapter re-applies; chapter 8's worked example
  uses the old build times, which were the live ones on the day that bug bit.
