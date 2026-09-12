# 3. The feed that knows when it happened
*~8 min read · the PR #1 branch · 17–18 August 2026*

*Where we are:* a Raspberry Pi has been logging every response from ESB's live outage feed
since 31 July. Sixteen days in, there is enough data to ask what the feed actually says - and
what it only appears to say.

## The question that opened this stretch

The water site's single deepest limitation is about time. Its feed never records when supply
was actually lost: the only start it publishes is the moment someone pressed publish, and the
feed even re-stamps that date in place, so every duration the water site prints is a *floor*
- "at least this long" - and its series spent a chapter renaming metrics to stop them
claiming more. Coming from that, the first question I put to sixteen days of ESB data was the
one that had hurt before: **when this feed says an outage started, does it mean the fault, or
the paperwork? And does the value hold still?**

The answer turned out to be the best fact in this repository, and most of this chapter hangs
off it.

## What changed

### The start time means the fault

Measured across 1,460 outage records (`notes/grading.md`, "Does startTime drift?",
18 Aug 2026):

- **It holds still.** ESB revised `startTime` 8 times out of 1,460 - 0.5% - and two of those
  were by a single minute. For comparison, the free-text status message changed 639 times and
  the outage type 534. Nothing about the start drifts as an incident develops.
- **It is back-dated, not publication-stamped.** Comparing each record's reported start
  against the moment our collector first saw it: the median fault appears in the feed 32
  minutes after its own stated start, and **not one record in the corpus - zero of 1,460 -
  appeared before its reported start.** A publication timestamp cannot behave like that; a
  fault clock can. Better still, our own 30-minute poll accounts for essentially the whole
  lag: for the 593 faults caught while still live, the median gap is 31 minutes - one poll
  interval - meaning ESB's own publication delay is close to zero at the median. There is a
  real tail (the 90th percentile is 147 minutes; some faults are published hours late), but a
  late *publication* delays when we learn of an outage without corrupting how long it is
  recorded as lasting.

> **Concept: a start that is back-dated.** When a fault trips a line at 15:15 and a
> technician logs it at 15:40, a feed can publish two different "starts": the moment of
> logging (what the water site's feed does) or the moment of the fault, filled in
> retroactively (what ESB's does). The difference decides what a duration *is*. Publication
> minus restoration measures the paperwork; fault minus restoration measures the outage. The
> water series had to conclude "every figure is a floor on the true length" and say so on its
> page. This site gets to say the stronger thing - durations here measure the outage, not the
> notice - but only because the claim was checked three ways: the field barely ever changes,
> no record predates it, and the residual lag matches our own polling arithmetic. The
> sibling sites' pages look alike; underneath, they are measuring two different clocks, and
> each one's footer says which.

### The fields that structured data uses to lie

The good news about `startTime` made the rest of the feed's habits stand out, because every
other field needs interpreting, and each of these cost real debugging time before it made it
into the repo's list of traps (CLAUDE.md, "Data-shape traps"):

- **`restoreTime` is `""`, never null**, and is only ever filled in once an outage flips to
  `Restored` - 10,542 of 11,199 collected detail bodies have it empty. An empty string that
  means "not yet" is one comparison bug away from meaning "midnight, 1970".
- **`Restored` overwrites the outage's type.** Once an outage is restored, the feed no longer
  says whether it *was* a fault or planned works - the only surviving evidence is the
  earliest non-`Restored` type the collector saw it with. A site built from snapshots of the
  current state alone could not grade anything; this is chapter 1's verbatim log paying out
  again.
- **Planned outages never restore.** `Planned → Restored` does not occur in the corpus: not
  one of the 675 planned works ever reported a restore time. They simply stop being listed,
  so every planned duration is an ESB estimate that ESB never confirms - one reason chapter
  4b excludes them from the grade.

The water site's equivalent problems were prose: its end times were buried in sentences like
"works are now complete", and it needed a local language model, then a rule engine, to read
them out. This feed's fields are machine-readable, and that is genuinely better - but the
lesson of this stretch is that *structured* is not the same as *true*. Here the work moved
from extraction to interpretation: the values parse trivially, and the meaning still had to
be established against the corpus, field by field.

### Three ways an outage ends

So when does an outage end? For 85% of faults, ESB eventually publishes a confirmed
`restoreTime` and the question answers itself (chapter 2 measured that share against the poll
rate). For the rest there are two candidates: ESB's *estimated* restore time, published while
the outage runs, and the last moment the collector saw the outage listed. Both are wrong in
knowable directions - the estimate is a plan, and the last sighting is late, because ESB
leaves restored outages sitting in the feed for hours.

Rather than pick by argument, the choice was measured against the 648 outages whose true
restore time is known (`notes/grading.md`, 17 Aug 2026):

| Fallback for a missing end | Bias | Total duration vs truth |
|---|---:|---:|
| Last time it was still listed | +3.78 h | **2.26×** |
| ESB's estimated restore time | +0.39 h | **1.13×** |
| min(estimate, last listed) - chosen | +0.54 h | **1.18×** |

The last sighting more than doubles total duration - a +126% error from ESB's leisurely
housekeeping. The estimate is used when it falls between the start and the last sighting;
otherwise the last sighting is the tighter bound. One edge was decided by a failure: an
estimate landing *before* the outage's start is discarded rather than clamped, because
clamping produced zero-length outages. And every outage carries a label saying which of the
three sources its end came from, surfaced on the page - "restored 14:32" and "off about 4 h"
are different claims, and the reader gets told which one they are reading. The water site
ended in the same posture by a different road: its plans (scheduled ends) accrue time but are
excluded from its published median, and its page labels estimates as estimates. Neither feed
hands over a clean end; both sites settled on *bound it, label it, and never present a plan
as a measurement*.

### The timeline is the outage's, not ours

One more habit had to be unlearned before the site could render an outage honestly. The
first draft showed each outage's timeline as the *observation log* - when our collector saw
what - which is the natural thing to build from the data structure and the wrong thing to
show a reader.

#### Worked example: Roosky

A fault at Roosky began at 15:15 and was restored at 18:17 - ESB's own times, both in the
record. But collection started at 21:02 that evening (it was 31 July, the collector's first
pass), so the observation log contains exactly one sighting: 21:02, already restored. Drawn
from observations, the page showed a single misleading row - an "event" at 21:02, hours after
everything had happened (commit "Anchor each outage's timeline on ESB's own start and restore
times", 18 Aug 2026). Anchored instead on the feed's own fields, the timeline opens with
"Outage began, 15:15" and closes with "restored, 18:17", each labelled for its source, and
our own sighting times appear nowhere - they record when we noticed, not what happened. The
rows in between, for outages that have them, come from the customer-count segments (chapter
4a), and any observation falling outside the outage's own window is dropped. The same commit
also stopped showing the timeline at all for the 93% of outages whose customer count never
changed: for those it repeated the summary line word for word, so it earned its place on
nobody's screen.

This is the mirror image of a water-site lesson. Over there, "observation time versus event
time" meant the *archive* could only know when a build first saw a case close - a floor,
because its feed publishes no end of its own. Here the feed publishes both anchors, so
observation time could be demoted to what it really is: bookkeeping about the collector,
useful for measuring ESB's purge behaviour and nothing else.

### The outages we only ever meet leaving

Finally, the corpus contains events the collector never saw alive: 85 of 1,333 (6.4%) whose
first observed state is already `Restored`. They are all faults - planned works never restore
- and they are short: median 30 minutes, against 2.2 hours for the corpus. We first see them
a median of 32 minutes after restoration: one poll interval. In other words, they are the
outages that begin and end inside the gap between two passes, caught only because ESB's
records outlive the outage by a little - a property of the collection rate, not of the
network (`notes/grading.md`, 17 Aug 2026). They keep their full, correct durations, because
`startTime` and `restoreTime` travel in the record whenever the record is seen at all: the
poll rate decides whether an outage is *seen*, not how well it is *timed*. That neat
separation - detection is ours, timing is ESB's - is exactly what the water site never got to
have, and it is what made chapter 2's "stay at 30 minutes" verdict cheap. A finer poll there
would buy better numbers; here it mostly buys more rows.

## Where it left the site

Nothing published yet - but the semantics were now settled enough to build on: durations that
measure the outage, ends that are bounded and labelled rather than guessed, timelines told in
the outage's own clock, and a corpus whose blind spot (sub-30-minute faults) is known and
sized. What was *not* yet settled was identity - what counts as one outage at all. The feed's
answer turns out to be "several records", and unpicking that is the next chapter.

## Notes

- `notes/grading.md` "Does `startTime` drift?" (measured 18 Aug 2026): 8 revisions in 1,460
  (2 × 1 min, rest −82 to +363 min); 639 statusMessage / 534 outageType changes; lag table
  p25 21/12, median 32/21, p90 147/34 (faults/planned), 0 negative; 593 live-caught faults,
  median 31 min.
- `notes/grading.md` "Settled, with the numbers" (17 Aug 2026): the 648-outage fallback
  table (2.26× / 1.13× / 1.18×), discard-not-clamp, end-source labels; 675 planned works,
  none restored.
- `notes/grading.md` "Outages we only ever see restored" (17 Aug 2026): 85 of 1,333, all
  faults, medians 30 min / 2.2 h, first seen +32 min.
- CLAUDE.md "Data-shape traps": `restoreTime` `""` (10,542 of 11,199 empty); `Restored`
  overwrites `outageType`.
- Commit "Anchor each outage's timeline on ESB's own start and restore times" (18 Aug 2026):
  Roosky (began 15:15, restored 18:17, first seen 21:02); timeline only when something
  happened (93% never changed count).
- The water site's contrasting facts: its series, chapter 6 (start = publication; every
  duration a floor; observed vs scheduled ends) and chapter 7 (observation time vs event
  time; `closed_at` is a floor).
