# 12. How often does ESB's estimate hold?
*~9 min read · PR #39 · 5 to 6 September 2026*

*Where we are:* every outage row has carried a phrase like "2 h later than ESB estimated" since
28 August (chapter 7b). This chapter is about adding those up, and about the first number on this
site that nobody else publishes at all.

## The question that opened this stretch

When your power goes out, the grid gives you two things: the fact that it knows, and a time it
expects to be back. The first is the outage. The second is the only part you can act on - whether
to wait, cook, drive somewhere, call someone. It is a promise made to one household about one
evening, made hundreds of times a day, and nobody publishes how often it is kept. ESB does not,
the regulator does not, and the charter's 4-hour aim (chapter 4b) is about something else: it
measures restoration against a fixed target, not against the time ESB itself named for this
outage.

The site had been quietly holding the ingredients for a year's worth of that question since its
first week. Every restored fault's row already compared the restore against the estimate. On the
corpus to 5 September, **1,079 of 1,129 restored faults carry an estimate**. All that was missing
was the addition.

## What changed

"Restored by ESB's first estimate" is now the share of faults, among those with a confirmed
restore and a published estimate, back no later than five minutes after the first restore time
ESB named. It sits beside "restored within 4 hours" everywhere that figure appears: a tile on the
national view and on each county view, and a column in the county page's month table. The footer's
method disclosure defines it in two sentences. In payload terms it is two integers per
county-month and per national month: `data.js` grows 0.6 KB and the initial load stands at
65.9 KB, against the 500 KB budget of chapter 5.

Every interesting decision in it is about *which* number counts, and each one was measured before
it was chosen.

### First word or last word

ESB revises. Of the 973 single-id faults, 192 had their estimate revised at least once - and
**156 of those revisions came after the previous time had already passed**. That is the finding
the whole figure turns on. A revision is not usually a better forecast issued in good time; it is
mostly the grid telling you, once the hour it named has gone by, that it will be a while yet.

Score against ESB's latest estimate and 74.4% of faults are back on time. Score against the first
time it named and 63.6% are. The gap, almost eleven points, is very nearly the 156.

> **Concept: scoring a promise against its first statement.** When the target of a measurement can
> itself be edited, the metric has to say which version counts, and "the latest one" is the choice
> that flatters. A deadline moved after it has passed is not a new promise; it is a report of a
> missed one, and a score that accepts it converts every miss into a hit at the moment it is
> acknowledged. The rule here is that a promise is scored against the first version the person
> acting on it could have seen - the time that was on the screen when they decided whether to wait
> up. The obvious middle course was measured too: "kept unless some estimate passed while the
> outage was still out" scores 67.3%, and was rejected because no tile label can state it. A
> figure whose rule cannot be said in a phrase will be read as whatever the reader assumes, which
> is the one thing the rule was supposed to prevent.

This is also the one place in the series where the invariant of chapter 1 pays out in a number.
The first estimate is not a field in the feed. ESB's detail body carries whatever the estimate is
*now*; the earlier value survives only because the collector wrote every response down before
reading it, and the database records every field that changed. `Outage.first_est` is read out of
that change log, per record, before the merge - the envelope timeline of chapter 4a carries no
estimates - and for a merged event it is the earliest any member named. A site that had parsed on
the way in, keeping only the current value, could not compute this figure at all, and could not
compute it retroactively for a corpus already collected.

### Per outage, not per customer

Customer-weighted, the same share reads 83.4% against 74.6% per outage. Large faults keep their
estimates more often, which is plausible - a big fault gets a crew and a plan - but weighting by
customers would report the big outages' record as everybody's. An estimate is one statement about
one outage, and that is how a household meets it: one time, on one screen, for one evening. Per
outage.

### A grace that only forgives lateness

The share allows five minutes, `ESTIMATE_GRACE`, and the ladder behind it was measured on the
last estimate: 73.3% at zero grace, 74.6% at five minutes, 78.9% at fifteen, 82.3% at thirty. Five
is not a compromise between those; it is the line the outage row already draws, since the row
prints no "later than ESB estimated" inside five minutes. The constant is defined once in the
model, the row's own tolerance now reads it, and the JavaScript mirror is asserted by the same
test that guards the grade's minimum.

The wording took a correction. The first cut said "within five minutes", which reads as a band
either side, and the site would then have been claiming a figure it does not measure: under a
two-sided band, where being back *early* also fails, the share is **3.7%**. Restoring early is
ordinary and good. The footer, the column title and the row now say "no later than five minutes
after".

> **Concept: a one-sided tolerance.** Any published figure with a tolerance has to say which
> direction the tolerance forgives, because the natural English for a tolerance - "within five
> minutes", "give or take an hour" - is symmetric, and most real tolerances are not. Here early is
> not a miss at all, so the grace hangs on one side only; said symmetrically the same rule would
> have described a completely different and nearly empty measurement. The test of the wording is
> not whether it is technically defensible but whether a reader who never sees the code would
> compute the same number from the sentence.

### Where it goes blank

Under five estimates the cell is blank and the tile a dash, `MIN_ESTIMATES`, which is the grade's
own floor for the grade's own reason (chapter 10: a denominator that is a sample). August's
smallest county sample was 10 and its largest 99; a September six days old ranged from 1 to 25, so
the floor is doing real work at a month's start. There is no day gate here - this is a plain share
of a sample rather than a judgement about a month, and a small-sample floor is the whole of what
it needs.

The population is the faults the grade judges: started and restored inside the observed window,
not ongoing, so the county tiles and the national row cannot end up counting different sets.

### Worked example: the row and the tile can disagree, and should

A row on a county page can read "28 min earlier than ESB estimated" for a fault the tile above it
counts as a miss. That looks like a bug and is the design.

The row compares against ESB's **last** word: the estimate carried by the record that ended the
event, which is the settled rule from chapter 4a, and for a live fault the "expected back by" has
to be the newest thing ESB has said or it would be telling a reader in the dark to plan around a
time already abandoned. The share holds ESB to its **first** word, because that is the promise the
household acted on. Both are correct answers to different questions: *is ESB's current statement
accurate?* and *was ESB's original statement kept?* The tile's label says "first estimate", so a
reader can tell which one they are looking at.

## Where it left the site

August, as the page now shows it: nationally **59.2% of 982 first estimates were kept**. Leitrim
at 33% of 27 and Meath at 46% of 35 sit at one end, Kilkenny at 75% of 20 and Waterford at 77% of
30 at the other. And the misses are long when they happen: against the last estimate, the median
miss is 55 minutes late and a tenth of them run more than four hours over.

So the answer to the chapter's title, for one Irish summer month: a little under three in five
faults are back by the time ESB first named, and when that time slips it typically slips by the
better part of an hour.

One thing was deliberately not done with it. The footer's credibility paragraph, which sets this
pipeline's CML, CI and CAIDI against ESB's published figures (chapter 4b), does not get an
all-time national estimate share. That paragraph exists to be checked against an external source,
and there is no external source: ESB publishes nothing to compare this with. The figure lives in
the tiles, month by month, on the clock everything else on the page runs on (chapter 7b).

## The water site, for once, in the stronger position

This is the first number in the series where the two sites swap chairs.

Everywhere else, this site has had the external anchor the water site lacked: a published charter,
published CML and CI, a national test suite holding the pipeline to ESB's own numbers. Here it has
none of that, and it is in exactly the position chapter 4b described the water site as being in -
publishing a measurement nobody else publishes, defensible only through its stated method and the
numbers behind each choice. That is why so much of this chapter is the rejected alternatives with
their measured shares: it is the water site's way of earning a number, applied on this bank.

The water site's own version of "which stated time counts" went the other way, and for a reason
that is about its feed rather than its taste. Its `start_date` is re-stamped in place by the feed,
so an earlier value simply ceases to exist unless it happened to be observed, and its notes
explicitly reject reconstructing a minimum from what was seen, because a backward re-stamp would
inflate every duration. Its scheduled ends are kept out of the published median entirely: pooling
them dragged the headline from 17.0 to 9.3 hours, and a figure that can be halved by including a
category is not one figure. So where that site could not trust a stated time and excluded it, this
site could reconstruct the original statement exactly and chose to score against it. Same problem,
opposite answers, and the difference is entirely in what each feed lets you keep.

## Notes

- `notes/design-alignment.md` "The site says how good ESB's estimates are" (5 Sep 2026): the
  choices table with every measured figure - first 63.6% vs last 74.4%, 192 revisions of which 156
  after the time had passed, the 67.3% middle rule; 74.6% per outage vs 83.4% customer-weighted;
  the grace ladder 73.3 / 74.6 / 78.9 / 82.3 and the 3.7% under a two-sided band; `MIN_ESTIMATES`
  and the August 10-to-99 and September 1-to-25 samples; the August national 59.2% of 982 with
  Leitrim, Meath, Kilkenny and Waterford; the 55-minute median miss; the rejected footer figure.
- `esb_site/model.py`: `ESTIMATE_GRACE`, `MIN_ESTIMATES = MIN_GRADED_FAULTS`, `Outage.first_est`
  taken per record from the change log and minimised across a merged event's members.
- PR #39, merged 6 September 2026, with the first-estimate correction in its review commit
  ("Hold the share to the first estimate ESB named, and say the grace is one-sided").
- Chapter 1 for the log that makes a superseded estimate recoverable; chapter 4a for the ender's
  estimate rule; chapter 7b for the row's own "later than ESB estimated"; chapter 10 for the
  small-sample floor. The water site's re-stamped starts and excluded scheduled ends: its series,
  chapter 6, and `notes/data-quality.md` there.
