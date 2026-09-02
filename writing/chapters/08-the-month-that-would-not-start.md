# 8. The month that would not start
*~6 min read · PR #31 · 1 September 2026*

*Where we are:* the account had reached the end of August with the site reading and measuring
the way its author wanted (chapters 7a and 7b). Then the calendar turned over, and the site
did not.

## The question that opened this stretch

September arrived, and the month strip along the top of the page did not show it. That is the
kind of bug that looks cosmetic for about a minute.

## What changed

The site builds its list of months by walking from the first collection to the horizon. The
walk started at `start.replace(day=1)`, which does exactly what it says: it replaces the
**day**. It does not touch the time. And `COLLECTION_START` is not a date, it is the first
poll's exact instant, `2026-07-31T21:02:11Z` (chapter 1). So the cursor carried 21:02:11
through every step of the walk, and the loop's "is the cursor still inside the window?" test
compared a 21:02 timestamp against the horizon. A new month could therefore not appear until
the first evening of that month. The site builds at 05:40 and 12:40 UTC, both before nine in
the evening, so September could not exist on the site until the build on 2 September.

> **Concept: a date comparison that is secretly a time comparison.** Two values can look like
> dates, print like dates, and still be compared as instants. `replace(day=1)` on a timestamp
> gives you the first of the month *at whatever o'clock the original carried*, so "is this
> month within range?" quietly becomes "is 21:02 on the 1st within range?" - and for the
> twenty-one hours before that, the answer is no. The tell is that nothing is *wrong* in the
> output: the month is simply absent, which reads as "nothing has happened yet" rather than as
> a fault. That is chapter 5's lesson arriving from a new direction. There the collection
> horizon stopped the page claiming days nobody watched; here a stray clock time made the page
> omit a day that *was* watched. Both failures point the same way, which is the way that does
> not look like a failure: the site appearing calmer, quieter and emptier than the data it
> holds.

The strip was only the visible half, and this is where a cosmetic bug stops being cosmetic.
The same month list drives the per-county statistics, the national statistics, and the shard
builder, where an outage is filed only under a month whose observed window it overlaps. With
September missing from the list, a fault that started and ended on 1 September reached no
county shard and no month table: it was collected, stored in the raw logs, rebuilt into the
database, and then dropped on the floor at the last step. The app also opened on August with
none of its "so far" wording, because the month it should have opened on did not exist yet.

The fix is three lines and one deletion: walk `(year, month)` pairs rather than datetimes, so
no time of day survives into the comparison at all. Tuple comparison does the ordering, and
the wrap to January is arithmetic on the month number. The commit says plainly that this is
**the shape uisce already uses**, which is the third time in this account that the water site
turns out to have solved something first (chapters 6a, 6b) and the first time the borrowing is
a loop rather than a component.

### Worked example: twenty-one hours of September

Collection began at 21:02:11 on 31 July 2026. Walk the months as datetimes from there and the
cursor sits at 21:02:11 on the first of every month it visits. On 1 September the site's two
scheduled builds run at 05:40 and 12:40 UTC. Both are earlier in the day than 21:02:11, so at
both of them the test "is the September cursor at or before the horizon?" is false, and the
month list stops at August. The first build that could include September is the one at 05:40
on **2 September** - by which time any fault that began and ended on the 1st had already been
filed nowhere (PR #31, 1 Sep 2026).

The comment left on the fixed function is a good example of this repository's own rule about
comments, which chapter 7b watched being written down: it does not say what the loop does,
which the three lines below it say perfectly well. It says why the loop is not made of
datetimes, which is a fact about `COLLECTION_START` that nothing else in the file records.

## Where it left the site

Thirty-six new lines of tests pin the behaviour: the month list from collection to a September
date, the first build of September specifically, and the year boundary that the arithmetic has
to cross in four months' time. The site shows the current month from its first minute, and
the first day of a month is filed like every other day.

It is a fitting place for this account to pause. The series has spent twelve chapters on
measurement, honesty and what a page may claim, and the last thing it records is a
twenty-one-hour hole that made the site quietly emptier than the truth, found by looking at
the top of the page on the first morning of a month and thinking "that is odd".

## Notes

- PR #31 (1 Sep 2026), merged the same evening: `month_list` walked datetimes seeded with
  `start.replace(day=1)`, carrying `COLLECTION_START`'s 21:02:11 through the walk; builds at
  05:40 and 12:40 UTC, so a month appeared only from its second day. Consequences named in
  the pull request: the month strip, the per-county stats, the national stats, and
  `render.shard`'s month filing, plus the app opening on the previous month without its "so
  far" wording. Fix walks `(year, month)`; 36 lines of new tests in `tests/test_site_model.py`.
- `COLLECTION_START = datetime(2026, 7, 31, 21, 2, 11, tzinfo=UTC)` in `esb_site/model.py`;
  the same instant chapter 1 opens on.
- Chapter 5 carries the collection horizon, the other half of this failure mode; chapter 7b
  carries the comment rule this fix's comment obeys.
