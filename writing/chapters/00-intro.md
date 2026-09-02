# 0. Ask the grid the same question
*~6 min read · an introduction to the series*

## The question

For most of the summer of 2026 I was building a status site for Irish water outages, and
writing down what I learned as I went. That project began with a question about my own town -
*are other areas having as many outages as I am?* - and by August it had an answer. Somewhere
along the way the question grew a sibling. The water goes off in Leixlip often enough to
notice; the electricity, it seemed to me, almost never. But "it seemed to me" is exactly the
kind of claim the water site was built to replace with a number. Ireland's electricity
distribution network is run by ESB Networks, and ESB publishes every live outage on a public
map called PowerCheck. So: how good is the grid, really - county by county, against a standard
a reader can check?

There was a catch, and the catch shaped everything in this repository. PowerCheck shows only
what is happening *now*. Each outage is purged from the feed a few hours after restoration -
the shortest retention observed is 112 minutes - and there is no archive and no way to
backfill (README; commit "Add ESB Networks outage collector", 31 Jul 2026). The water site's
feed left notices up for days or weeks, so a build twice a day caught nearly everything. This
feed forgets by morning. Whatever questions I would eventually ask of the data, the data had
to be caught first, live, every half hour, by a machine that never sleeps.

So on 31 July 2026, at 21:02, a Raspberry Pi in my house made its first collection pass. The
site came eighteen days later, once there was a month of data worth showing. And the answer to
the question, for the first month, is: **genuinely good, but short of ESB's own aim.**
Nationally, 88.4% of fault-interrupted customers had supply back within four hours, against
the 95% ESB's Customer Charter aims for; nine counties met the aim outright and three failed
badly enough for an F (`notes/grading.md`, 17 Aug 2026). Nearly every Irish fault is cleared
the same day. One outage in the whole month crossed the 24-hour mark at which ESB's charter
pays compensation.

## What this series is

The water site's series ran to eighteen chapters because it had to invent almost everything:
how a map pin becomes a number of people, how a model reads an end time out of prose, what a
fair grade even is. This series is shorter, because this project inherited that summer's
lessons - and its particular job is to be honest about which lessons *transferred* and
which did not. Roughly half of the interesting decisions in this repository are the same
decision as the water site's; the other half are the opposite decision, and every one of those
traces to a property of the feed, not to a change of taste. The feed tells the truth about
when an outage started, so durations here mean something they could not mean there. The feed
counts the affected customers itself, so the Census plays a bit part here instead of the lead.
The feed forgets, so the archive lives in raw logs on my own hardware instead of in a database
built by a cloud scheduler. Each chapter states the water site's approach in a sentence, then
this site's, then the fact about the data that forced the fork.

The conventions are the water series' conventions. Every hard idea gets a **concept box** at
the point it first matters. Every concept gets a **worked example** with a real place and real
numbers, and the arithmetic shown - the running examples are Bealistown, a townland whose one
fault arrived as five records, and Tycor in Waterford, which lost power four times in ninety
minutes. Every number carries its source and date, and every chapter ends with notes saying
where the figures came from. Each chapter opens with two lines of *where we are*, so it can be
read alone.

## The shape of the story

| | | |
|---|---|---|
| **1** | *Write it down before you read it* | The one invariant everything rests on: the raw logs are the truth and the database is disposable - the opposite of the water site's design, and why. |
| **2** | *A collector in the hall* | A Raspberry Pi, a 30-minute timer, an alerting scheme for a machine nobody watches, and the measurement that kept the interval at 30. |
| **3** | *The feed that knows when it happened* | ESB back-dates its start times and never lies about them - the single thing the water site's feed could not give - and the three ways an outage ends. |
| **4a** | *One fault, five records* | ESB opens a new record each time a fault's scope changes; folding families of ids back into events, and the repeat faults that must *not* be folded. |
| **4b** | *Grade them on their own promise* | Why Customer Minutes Lost was demoted, what a share cancels that a total cannot, and a letter grade pinned to ESB's own published aim. |
| **5** | *What the page may claim* | A 500 KB budget, day cells coloured by magnitude, and the collection horizon - the day the site stopped mistaking an absent collector for a calm network. |
| **6a** | *The third site of the family* | The shared design layer, told from the side that received it: vendored on a Tuesday, drifting by Wednesday, pinned by the weekend. |
| **6b** | *Reading like one product* | The plain-reader pass, a staleness threshold sized to a push schedule, and the county pages becoming a durable archive. |
| **7a** | *A page for every place* | A page for every named town, and the honest answer to the one thing this feed cannot tell you: who an outage actually hit. |
| **7b** | *The units a reader thinks in* | Figures put on the month's own clock, outage rows written as sentences, a guard that would have passed by checking less, and the letter E. |
| **8** | *The month that would not start* | A stray clock time inside a date, and twenty-one hours of September that reached no page. |
| **9** | *Closing* | What the site can and cannot say, the two sites side by side in one table, and a glossary. |

## How it was built, said once

Like the water site, this project was written with an AI assistant - Claude, in Anthropic's
Claude Code - from the first commit. Most of the repository's 144 commits carry a
`Co-Authored-By` trailer naming the model that wrote them: Opus 5 for the collector and the
first site, Fable 5 for the later passes - and Fable 5 also drafted this series from the
repository's own history under my direction, as it did the water series. I chose what to
build and what to reject, and I read every diff. The wrong turns recounted here - the relative
grade that handed out an F for ordinary service, the lookup grid that filed every centroid one
bin to the east, the customer denominator resting on a citation that did not exist - are wrong
turns I approved. Nothing about the findings depends on who typed them: every one is a
measurement against a public feed, a public census and ESB's own published reports, and the
notes and tests that back them are in the repository.

## What the site is, in one paragraph

A Raspberry Pi fetches ESB's live outage list every 30 minutes and writes every response,
verbatim, to an append-only log before anything reads it; a SQLite database is derived from
the log and can always be thrown away and rebuilt. Records that are one physical fault are
merged into events; each event's timeline is anchored on ESB's own start and restore times;
each event is placed in a county by the nearest Census Small Area centroid, because the feed
carries no county. A county-month is graded A to F on the share of its fault-interrupted
customers restored within four hours - ESB's own charter aim of 95% is the A - and Customer
Minutes Lost, the regulator's unit, is shown beside the grade with its caveat stated. The
result is published as static pages at `baz8080.github.io/esb`, rebuilt twice a day after the
Pi pushes its logs, with a banner that admits the data's age. Storm days are not excluded,
because nothing in the feed identifies one, and the page says so.

## A note on the numbers

Figures are quoted as they were measured at the time, with the date and the pull request,
commit or note they came from. Some moved as the corpus grew or the method sharpened - the
interruption-count bias was 1.60× before the merge, 1.35× after it, 1.33× after the
denominator was corrected - and where that happened the chapter says so rather than quietly
using the newest figure. The whole first month is 26 days of data collected by one small
computer; the numbers will keep moving, and the winter, which is where Irish outage statistics
are made, has not happened to this site yet.
