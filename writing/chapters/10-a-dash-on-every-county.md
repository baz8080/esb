# 10. A dash on every county
*~9 min read · PR #35 · 3 September 2026*

*Where we are:* chapter 8 got the new month to appear at all. This chapter is about what the
page said once it did, on the morning every county in Ireland showed no grade.

## The question that opened this stretch

September opened with a dash where each of the 26 letters should be, and a sentence under each
one saying "Too few faults this month to grade fairly".

Nothing was broken. Chapter 4b's grade needs five observed days as well as five faults, and on
2 September the month held 1.83 of them, so the day gate shut every county at once. The site
had simply never crossed a month boundary before: collection began on 31 July, August was its
only whole month, and July's three hours were too old for anyone to question (`notes/grading.md`,
3 Sep 2026).

What was wrong was the explanation. And the reason it was wrong is that chapter 4b's rule,
stated there as one sentence, is really three different facts.

## What changed

### Three gates, and none of them is the same fact

| Gate | Scope | What it measures |
|---|---|---|
| five observed days | **national** - the window function takes no county | calendar coverage of the month |
| five faults | the county's own | faults overlapping the window |
| nothing scoreable | the county's own | whether *any* fault could be judged at all |

> **Concept: a shared sentence for unrelated causes.** The chip said "too few faults" whatever
> had actually withheld the letter, so in September it sent a reader hunting for outages that
> were not the reason. The three gates are not variations on one idea: the first is about the
> *calendar* and is the same for all 26 counties, the second is about a county's own weather,
> and the third is about whether any fault it did have was scoreable. Crucially, **none of them
> counts "days on which a fault happened"**, which is exactly what the old wording invited a
> reader to imagine. A single message covering several causes is not a simplification; it is a
> claim that they are the same cause, and a reader who acts on it looks in the wrong place. The
> fix was one sentence per gate, and a helper that returns the gate rather than a boolean, so
> the letter and the explanation for its absence cannot drift apart.

The four sentences the page can now say, each naming its month: *too new* ("September 2026 is
too new to grade. Grades appear from 6 September"), *never watched enough* ("Only part of July
2026 was watched, so it is not graded" - July can never reach five days and the month is over,
so promising a date would be a lie), *too few faults*, and *nothing judged* ("No fault in
August 2026 was restored in the month it started, so there is nothing to grade").

### The explanation moved out of the hover

The reason had been living in a `title` attribute, which does not open on a touch screen, and
most visitors are on a phone checking their power. A page of dashes with no visible explanation
reads as a verdict on every county at once.

The day-gate sentence is now printed in the open - above the county list, under the heading on
the static county page, and in the app's county view - and said **once** rather than in 26
chips, because that gate is national and the other two are not. Where a message is displayed
follows from whose fact it is. The per-county fault case stays in the tooltip, since that row
already shows its own fault count beside the dash.

### Worked example: what five days is actually for

The gate itself was re-examined rather than assumed, by replaying August at every day-of-month
horizon with the gate removed and comparing against each county's settled letter:

| Horizon | Counties with a defined grade | Matching the settled letter |
|---|---:|---:|
| day 1 | 14/26 | 3/26 |
| day 3 | 25/26 | 6/26 |
| day 5 | 26/26 | 8/26 |
| day 10 | 26/26 | 12/26 |
| day 14 | 26/26 | 17/26 |

Read the two columns against each other and the gate's job becomes precise. Five days buys a
**defined** letter for every county; it does not buy a **stable** one, and nine counties were
still changing band after a fortnight. So the gate is a floor against the day-one reading -
where Wicklow showed an **F** that settled at A, and Dublin an **E** that settled at C, each
off one or two outages - and not a promise that the letter has converged. A gate long enough
to settle the letter would withhold half the month. It stays at five days, and the thing that
needed fixing was the wording (PR #35, 3 Sep 2026).

The cost is stated plainly in the note rather than buried: the day gate will shut every county
for the first five days of every month from now on, which is about 16% of the calendar, on the
view the app opens on.

### Why the water site needs no such gate

This is the sharpest version of the series' running contrast, and it is written into the
repository's own note rather than only into this account. All three sibling sites grade A to F.
The difference is what sits under the division.

> **Concept: a denominator that is time versus one that is a sample.** The water site divides
> by people multiplied by seconds, and the lift site by days observed. That is **time**, which
> accrues whether or not anything happens: the denominator is always full-size for the window
> being measured, so a two-day answer is a complete two-day fact and a quiet month is a
> legitimate 100%. This site divides by the customers a fault actually reached. That is a
> **sample**, and its size is whatever the weather delivered; with zero faults it is not 100%
> but undefined. A measure that only exists once enough has gone wrong needs a small-sample
> floor. The siblings' measures are at their most solid precisely when nothing has happened.

There is a second half to it, about what a single letter can carry. The water and lift sites
name their own denominator to the reader - "listed on 1 of 2 days watched" - so a short window
cannot mislead. A letter has no room to say "C, from one outage", which is why this site
withholds the letter rather than qualifying it.

## What went wrong, and was caught in review

The first attempt at this fix had a bug of exactly the kind it existed to remove. The helper
took a fault count and never read it, which made "too few faults" an unconditional catch-all
for any month past the day gate - the old mis-blaming, with the gates swapped. The tell is
that "nothing scoreable" is independent of the count: a county can have plenty of faults and
still have none that started inside the window, were restored inside it, and were not still
running at the horizon.

Reproduced with six live faults on 20 August, the chip read "Too few faults in August 2026" on
the same table row whose fault column read **6**. It was latent rather than live - replaying
the real corpus across every August horizon produces no occurrence - but it would have
surfaced in a storm, which is the worst possible moment for a page to contradict itself on
screen. It is covered by a regression test now.

## Where it left the site

A page that says why a letter is missing, in the reader's view rather than in a hover, with
one sentence per cause and each naming its month. The footer documents the five-day rule
alongside the five-fault one. The gate is unchanged and now has its measurements written down,
including the honest admission that five days is a floor and not a settling point. 236 tests,
an initial load of 63.3 KB against the 500 KB budget, and the national comparison against
ESB's published figures unmoved.

## Notes

- PR #35 (3 Sep 2026): the three gates and their scopes; `days_gate` returning the instant a
  month reaches five days; the four sentences; the day-gate sentence printed in the open;
  the August replay table (day 1/3/5/10/14: defined 14/25/26/26/26, matching 3/6/8/12/17 of
  26); Wicklow F to A and Dublin E to C at day 1; nine counties still moving after a
  fortnight; the review bug (six faults, `within` None, reproduced 20 Aug); 236 tests;
  63.3 KB initial load.
- `notes/grading.md` "The five-day gate had nobody to explain it" (3 Sep 2026), including
  "Why this site needs the gate and uisce and lifts do not" and "The gate is a floor, not a
  settling point"; September held 1.83 observed days on 2 September and reopens 6 September;
  the gate shuts about 16% of the calendar.
- Chapter 4b states the grade's thresholds and the ungraded rule as one sentence; this chapter
  is that sentence taken apart. Chapter 8 is the previous morning's month-boundary bug.
