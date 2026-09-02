# 9. Closing: two feeds, two sites, one discipline
*~12 min read · with the side-by-side table and a glossary*

*Where we are:* the end of the account, on 2 September 2026, with the repository at pull
request #31 - 144 commits, 225 tests, and a month and a day of continuously collected data.

## The question, answered as far as it can be

*How good is the grid, really?* For the first month: genuinely good, and short of its own
aim. Nationally, 88.4% of fault-interrupted customers had supply back within four hours,
against the 95% ESB's charter aims for; nine counties met the aim, and exactly one outage in
the whole corpus ran past the 24-hour compensation mark (`notes/grading.md`, 17 Aug 2026;
graded on the five-band scale of chapter 4b, before chapter 7b added an E). And the average
interrupted customer was back in about an hour and a half - this pipeline's CAIDI of 92.2
minutes sits within 8% of ESB's own published 85.1 (chapter 4b), which is the strongest
external check either of these sibling sites has ever had. In the 29 August rebuild, on the
six-band scale, the 26 graded county-months read A 8, B 6, C 9, D 1, E 1, F 1.

The honest answer carries its dates, though. This is a month of high summer, collected by
one small computer that itself missed whatever fell between its half-hour glances. Storm
days - which ESB excludes from its published figures and this site cannot - have not
happened yet; winter is where Irish outage statistics are made. The letters will get worse
before they get representative, for a reason the footer states and the operator does not
control.

## What the site can say

- **How many outages there were, where, and how big** - since 31 July 2026, as events rather
  than record-keeping artefacts, with peaks and customer-minutes read off an envelope
  (chapter 4a).
- **How long each one lasted, meaning the outage itself.** ESB's start times are back-dated
  to the fault and effectively immutable - zero of 1,460 records ever appeared before their
  own start - so durations measure the outage, not the paperwork (chapter 3). This is the
  claim the water site could not make, and it is the foundation of everything graded here.
- **Whether the operator met its own promise**, county by county, month by month - the grade
  is ESB's published 4-hour/95% charter aim, and a share of customers cancels the one bias
  this feed is known to carry (chapter 4b).
- **The regulator's own units beside the grade** - CML, CI, CAIDI - with the pipeline held
  to ESB's published national figures by a test that runs on every build (chapter 4b).
- **How much of any day was disrupted, and how much of any day was watched** - day cells
  colour by magnitude, end at the horizon, and part-observed days say so (chapter 5).
- **Whether the page itself is current**, against the reader's own clock, with a threshold
  derived from the push arithmetic rather than hope (chapter 6b).
- **What has happened near a named town**, on its own page, for every settlement the Census
  names and every outage the archive holds, uncapped (chapter 7a).

## What it cannot say, and says so

- **Anything about a storm on ESB's terms.** Nothing in the feed marks a storm day, so they
  stay in, and winter months here will read worse than ESB's storm-excluded figures through
  no fault of ESB's (chapter 4b).
- **Anything about outages shorter than its glance.** The 30-minute poll is a filter: a
  fault that begins and ends inside one gap exists here only if ESB's record outlived it.
  The known blind spot is sized - the ids lost at coarser polling had a median duration of
  39 minutes - and 8 of 32 repeat-chain legs are shorter than one poll (chapter 2).
- **A trustworthy count of interrupted customers.** `numCustAffected` runs about 1.3× the
  figure ESB settles on. The grade is built so the bias cancels; the CML shown beside it
  inherits the bias and says so (chapter 4b).
- **Exactly when 15% of faults ended.** Where ESB never publishes a restore time, the end
  is bounded - the estimate or the last sighting, whichever is tighter, labelled on the page
  - and measured against known ends the chosen bound overstates totals by 18% where the
  naive one overstated by 126% (chapter 3).
- **Which section of a county an outage hit.** Placement is the nearest Census centroid to
  a point ESB publishes; the site deliberately does not invent a service area around it
  (chapter 4b).
- **Who an outage actually cut off.** ESB's point is the fault, not the households behind
  it, so an area page lists what was *pinned near* the area and can look quiet while the next
  village sat in the dark. The page says so, and points at its neighbours, rather than
  modelling a footprint (chapter 7a).

## The two sites, side by side

The series' promised deliverable: every consequential fork between this site and the water
site, each traceable to a property of the feed it serves.

| | The water site (uisce) | This site (esb) |
|---|---|---|
| The feed | Notices on a public map, listed for days or weeks | Live outages, purged within hours of restoration (112 min observed) |
| The collector | A cloud scheduler, twice a day | A Raspberry Pi in a hall, every 30 minutes |
| The archive | The database itself, built by upsert; rewriting it costs the archive | Verbatim append-only logs; the database is disposable and rebuilt at will |
| The start of an outage | Publication time, re-stamped in place by the feed; every duration a floor | ESB's own start, back-dated to the fault, immutable (8 revisions in 1,460); durations measure the outage |
| The end of an outage | In prose; read by rules, then a local language model; observed vs scheduled kept apart | In structured fields; confirmed vs estimate vs last sighting, bounded and labelled |
| What is one event | Pins sharing the feed's reference number | Records merged on identical location and start time; repeat chains deliberately kept apart |
| Who was affected | Census population within a 500 m assumption - the feed says nothing | ESB's own customer count - biased 1.3×, enveloped, never summed. *Where* they were is the open question, since the pin is the fault |
| The Census's job | The lead: population, settlements, a three-tier drill-down | A bit part: county placement and a denominator split |
| The grade | Availability from person-hours, on the site's own fixed thresholds | The share restored inside 4 hours, on ESB's published 95% aim |
| External validation | None exists to compare against | National CML, CI and CAIDI held to ESB's published figures in CI |
| The named caveat | The 500 m radius is an assumption, stated | Storm days are in, stated |
| Staleness trips at | 24 hours, sized to its build schedule | 16 hours, sized to the push arithmetic |
| A new grade band | Fitted against its own distribution | Set by arithmetic, then checked for a band nobody can reach |
| The smallest published place | A town, with the people in a 500 m circle around each pin | A town, with the outages *pinned near* it and a card pointing at its neighbours |

And the identical column, which is the deeper finding: both sites keep decisions in dated
notes with the rejected alternatives and their numbers; both publish single-file pages
assembled at build from the same pinned design layer; both colour their bars by magnitude
and make them answer one question; both label every estimate as an estimate; both end every
measured window at the data's own edge rather than the clock's; and both close with the same
footer sentence, "Source code · not affiliated" - which is the two projects' whole posture
in four words.

## What was learned, in the form the repository keeps it

The repo's root instructions carry a settled-decisions table so that no future session,
human or otherwise, re-litigates a closed question without reading the evidence that closed
it - the convention inherited unchanged from the water site. In plain language:

| The tempting idea | Why it was closed, and where |
|---|---|
| Grade counties against the national average | An F for three times an average that is itself good; ordinary service read as failure (chapter 4b). |
| Base the grade on Customer Minutes Lost | The feed's customer counts run 1.3× high; a share cancels the bias, a total cannot (chapter 4b). |
| Count ESB's outage ids | One fault arrives as several records; 1,457 ids are 1,333 events (chapter 4a). |
| Merge same-place faults minutes apart | Chains are separate interruptions; only overlap separates a chain from a split, and a tolerance folds up to 169 real events for three points of bias (chapter 4a). |
| End an outage at its last sighting | ESB leaves restored outages listed for hours; totals inflate 2.26× against known ends (chapter 3). |
| Poll every 15 minutes | ~5% of durations gained, against permanently doubling an archive that can never be pruned (chapter 2). |
| Poll hourly | Only 58% of outages caught live, and what is missed live is gone (chapter 2). |
| Exclude every outage lacking a confirmed restore time | Quietly leaving the feed is the *ordinary* way a fault ends; bound it instead (chapters 3, 5). |
| Trust `now` | An absent collector reads as a calm network; windows end at the horizon (chapter 5). |
| Grey out or pro-rate part-observed days | The trailing short day is the one readers want, and pro-rating invents precision a 30-minute poll lacks (chapter 5). |
| Alert on recoverable blips | It trains you to ignore the alerts that matter (chapter 2). |
| Keep a vendored copy of the shared design layer | Three copies drifted within a day, silently; one pinned upstream (chapter 6a). |
| Put the staleness threshold at the longest legitimate gap | It fired on an unlucky build six minutes early; above the gap, below the failure (chapter 6b). |
| Use DAPR's headline 1.75 interruptions / 219 minutes | All-in figures beside storm-excluded constants; the comparable pair is quoted verbatim in the code (chapter 4b). |
| Model a footprint so area pages can say who was cut off | It would import the water site's one big assumption into a site that has never needed one; the pages say "pinned near" and point at neighbours instead (chapter 7a). |
| Grade an area, or give it a day bar | The bands are calibrated to county-months and the day buckets saturate against a village; counts and a history, no letter (chapter 7a). |
| Cap the county page's outage list | A count was always a proxy for bytes, and a durable record should not be the one surface holding a fraction of itself; if a bound returns it should be a byte budget (chapter 7a). |
| Build an in-app area view to match the water site's | Same content as the page, and a page is indexable, shareable and linkable where a fragment is none of those; the two sites converge on the page (chapter 7a). |
| Print an annualised rate beside a month's figures | One of five numbers silently multiplied by twelve; every figure beside a month is on that month's clock (chapter 7b). |
| Report customer time in days or years | A unit named after a calendar span collides with a page organised by months, however the arithmetic goes; customer-hours (chapter 7b). |
| Build the shared-name guard by parsing the shared file | A guard reading a shorter list passes by checking less, silently; ask the package instead, and assert what must be in the answer (chapter 7b). |
| Keep a house rule in a personal config file | It never reaches a session that clones only the repository, so it applied only when its author was in the room (chapter 7b). |
| Seed a month walk with `replace(day=1)` on a timestamp | It replaces the day and keeps the clock time, so a month could not appear until its first evening, and the 1st reached no shard or table (chapter 8). |

If the water series' summary lesson was *measure before you build, and write down what you
rejected*, this series adds the corollary that made this repository cheap to build: **collect
first, interpret later, and keep the bytes.** Nearly every decision above was made or
re-made *retroactively* - replayed against logs recorded before the question existed. The
merge rule, the poll-interval verdict, the end-time bounds, the back-off's safety proof, the
grade itself: all of them are reinterpretations of an archive that never had to be asked
twice, because the first commit promised never to parse before writing.

## Glossary

Each entry is a concept box from this series compressed to a line, with its chapter; three
are the water series' boxes, borrowed and marked (→ u14, u16).

- **Source of truth vs derived index** - append-only bytes that are never edited, versus a
  database that can always be deleted and replayed from them (1).
- **Idempotent merge** - records serialised with sorted keys are byte-identical wherever
  written, so `sort -u` merges any machines' logs perfectly, any number of times (1).
- **The exit code is the alerting stack** - every failure that needs a human gets its own
  exit status and one webhook push; recoverable blips deliberately stay silent (2).
- **The poll interval is a filter** - an outage shorter than the gap between polls exists in
  the data only if the feed's record outlives it; the interval bounds what can be seen (2).
- **A back-dated start** - a start time filled in retroactively to the fault, not stamped at
  publication; the property that lets durations mean the outage (3).
- **An envelope, not a sum** - overlapping records of one event are read along their top
  edge: the peak is the highest point, customer-minutes the area under it (4a).
- **A chain is not a split** - concurrent records are one event to merge; sequential faults
  at the same spot are separate interruptions to keep, and only overlap tells them apart (4a).
- **Absolute standard vs relative scale** - a letter pinned to a stated, published quantity
  means the same thing every month; a relative letter always fails someone (4b).
- **A bias that cancels in a share** - an inflation riding both numerator and denominator
  divides out; the same inflation in any total does not (4b).
- **The collection horizon** - the last moment a run reached the feed; every measured window
  ends there, and `now` decides only the future (5).
- **Assembled at build** (→ u14) - single-file pages with the shared layer inlined by the
  build, so sharing costs the reader nothing.
- **Vendor or pin** (→ u14) - copied-in files go stale silently; a pinned commit is
  recorded, reproducible and bumped deliberately.
- **An empty dependency list as a deployment contract** - the collector installs by file
  copy onto the Pi's own Python, so runtime dependencies stay at zero and the site's
  dependency lives in a group the Pi never sees (6a).
- **Promoted on the second user** (→ u16) - a helper moves upstream the moment a second site
  wants it, and a redeclaration guard makes the move mandatory rather than aspirational (6b).
- **A threshold sized to a cadence** - staleness is alarming only relative to the longest
  *legitimate* gap, which is arithmetic: above it, below the first real failure (6b).
- **Ordered so truncation cannot make it false** - text cut by machinery you do not control
  must be true under every prefix; put the always-true clause first (6b).
- **Attribution, and why this feed cannot do it** - the published point is the fault, not the
  households behind it, so an area page says what was pinned near it and names its
  neighbours rather than inventing a footprint (7a).
- **A guard that shrinks silently** - a check that builds its own list of things to check can
  pass by finding fewer of them; ask the source for the list, and assert what must be in it
  (7b).
- **A date comparison that is secretly a time comparison** - values that look and print like
  dates can still be compared as instants, and the symptom is absence rather than error: the
  page reads as quiet instead of as broken (8).
