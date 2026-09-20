# 16. Closing: two feeds, two sites, one discipline
*~20 min read · with the side-by-side table and a glossary*

*Where we are:* the end of the account, on 7 September 2026, with the repository at pull
request #44 - 178 commits, 285 tests, and five and a half weeks of continuously collected
data.

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
- **Why a letter is missing**, when one is, in the reader's own view, naming which of the three
  gates withheld it, and reachable without a pointing device (chapters 10 and 15).
- **Which outages are still out right now**, said in those words, with whatever ESB has published
  about when they will be back (chapter 11).
- **How often ESB's own restore estimate holds** - 59.2% of 982 first estimates kept in August -
  which is a question nobody else publishes an answer to (chapter 12).
- **Where faults keep happening**, ranked, county by county, in ESB's own names for the places
  (chapter 13).
- **Its own rows, to anyone who wants them**: a CSV per county of merged events with the ends,
  both estimates and the integrated customer-minutes, so the page's arithmetic can be checked
  rather than reproduced (chapter 13).

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
- **Where exactly a named fault spot is.** ESB's location strings are its own account of where a
  fault is, and 222 of the 422 in the corpus have been pinned to more than one Census area, so
  the ranked spots are printed with their counts and link nowhere (chapter 13).
- **Whether its estimate score is right**, by anybody else's figure. The grade has ESB's published
  CML, CI and CAIDI to be checked against; the promise score has nothing at all, which is the
  position the water site is in for almost everything it publishes (chapter 12).

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
| Staleness trips at | 24 hours, sized to its build schedule | 10 hours, sized to six-hourly pushes (16 while the pushes were twice daily) |
| A new grade band | Fitted against its own distribution | Set by arithmetic, then checked for a band nobody can reach |
| A thin month | Graded anyway: the denominator is time, so a short window is a complete short fact | Ungraded behind three gates: the denominator is a sample of what the weather delivered, and is undefined at zero faults |
| The smallest published place | A town, with the people in a 500 m circle around each pin | A town, with the outages *pinned near* it and a card pointing at its neighbours |
| An outage in progress | The default state: a notice is open until it is lifted, and the *end* is the hard part | Carried as a flag all the way to the row, because the ends are structured and the liveness was the thing dropped |
| The operator's own promise | Stated times are re-stamped in place and scheduled ends are kept out of the headline; there is no promise left to score | Scored: 59.2% of first estimates kept, recoverable only because every field change was written down |
| The feed's own place string | 3,866 values; discarded entirely, geography rebuilt on Census settlements | 422 values; ranked as ESB's own account of where faults are, and never turned into a link |
| What it hands a reader who wants the data | The inference JSONL, committed on every build: the step nobody can reproduce from the feed | A CSV per county of the site's own merged rows, beside a public archive of the raw bytes |
| Watching the collector | A hosted runner records a failed run, in a system the author does not operate | A dead man's switch: the Pi pings an outside monitor, and silence is the alarm |
| A day the feed is too big to fetch | The notices linger, so the collector catches up tomorrow | The unfetched tail is lost at the purge, so a run has a budget and fetches first what a purge would take |

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
| Publish on a schedule, and trust the schedule | Scheduled runs landed 4 to 10 hours late every day for a week and the morning slot never ran in the morning; build on the data landing instead, and keep the crons only as a fallback (chapter 9). |
| Retime the late cron | A 4-to-10-hour delay cannot be aimed at a one-hour window; a better time only moves where the miss lands (chapter 9). |
| Let the banner name a cause | From a browser a stalled build and a stalled collector are indistinguishable; publish the age and the warning, not the diagnosis (chapter 9). |
| Explain three different gates with one sentence | "Too few faults" sent readers hunting for outages that were not the reason; one sentence per gate, each naming its month (chapter 10). |
| Put the explanation in a hover | A `title` does not open on a touch screen, and the readers are on phones checking their power; a national gate is stated once, in the open (chapter 10). |
| Raise the five-day gate until the letter settles | Measured: five days buys a defined letter, and nine counties were still moving band after a fortnight. A gate that waited for stability would withhold half the month (chapter 10). |
| Show the 24-hour count as a tile | 6 faults in 1,387: a tile reading 0 in most counties most months is furniture, where a table column is a legible rarity (chapter 11). |
| Score restorations against ESB's latest estimate | 156 of 192 revisions came after the previous time had already passed; scoring against the latest converts a miss into a hit at the moment it is admitted (chapter 12). |
| Weight the estimate score by customers | 83.4% against 74.6%: large faults keep their estimates more often, and weighting reports the big outages' record as everyone's (chapter 12). |
| Say the estimate is kept "within five minutes" | It reads as a band either side, and under a band - where being early also fails - the figure is 3.7% (chapter 12). |
| Link the ranked fault spots to area pages | 222 of the 422 location names have been pinned to more than one Census area; the ranking is honest, the link would not be (chapter 13). |
| Rank ESB's bare county name as a fault spot | It is ESB's string for a fault out in the country, and six county pages listed themselves as a top spot (chapter 13). |
| Build the card and the CSV from a county's raw list | Fourteen outages ESB had already restored at the first poll reached the export and not the page: Monaghan said 74 outages and shipped 77 rows (chapter 13). |
| Fetch a storm's details in the feed's own order | The head of the list consumes the budget every run and the tail is never reached; order by what a purge would destroy instead (chapter 14). |
| Let systemd's timeout enforce the run budget | A unit systemd has to stop is a failed unit whatever the process exits with, so every busy run would read as a broken collector (chapter 14). |
| Ping the heartbeat from the six-hourly backup | Too coarse to notice a stopped collector, and the backup can succeed with the collector dead, which is the case the heartbeat exists to catch (chapter 14). |
| Leave a county's own ungraded reason in a hover | The argument for printing the national gate once decided *where* a sentence goes and was read as a rule about *whether* (chapter 15). |
| Guard two renderers by restating their shared wording | A third statement of the sentence fires when one side is edited carefully and stays silent when both are edited carelessly; read one side, assert the other (chapter 15). |

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
- **A schedule you asked for is not a schedule you have** - a cron line is a request, and the
  evidence for when a job runs is its recorded start times; an argument resting on "this runs
  at T" is only as good as that log (9).
- **A shared sentence for unrelated causes** - one message covering several causes is not a
  simplification but a claim that they are the same cause, and it sends the reader to look in
  the wrong place (10).
- **A denominator that is time versus one that is a sample** - time accrues whether or not
  anything happens, so a short window is a complete fact; a sample sized by events is
  undefined when there are none, and needs a small-sample floor (10).
- **A claim in the prose is a claim in the code** - a sentence in the footer asserts something
  about the build and nothing in the toolchain checks it; read the site's own prose against the
  site (11).
- **Absent state renders as the default state** - a fact the renderer never receives does not
  come out blank, it comes out as whatever the code prints anyway, so the page reads calm rather
  than uncertain (11).
- **Scoring a promise against its first statement** - when the target can be edited, "the latest
  version" converts a miss into a hit at the moment it is admitted (12).
- **A one-sided tolerance** - the natural English for a tolerance is symmetric and most real
  tolerances are not; say which direction is forgiven or the reader computes a different
  number (12).
- **A ranking is a claim about its labels** - sorting is the easy part; the list asserts that each
  row names a distinct thing of one kind, which is why these rows carry counts and no links (13).
- **Publish the rows the page counts** - raw bytes make a project reproducible, the site's own
  derived rows make it checkable, and the interesting claims live between the two (13).
- **An alarm that fires on silence** - every self-raised alarm shares a point of failure with the
  thing it watches; a dead man's switch inverts the evidence and works precisely when the machine
  is gone (14).
- **Order the work by what a delay would destroy** - with less budget than work, arrival order and
  novelty both optimise for the wrong thing; rank by what is unrecoverable if it waits (14).
- **Reasoning about where, read later as a rule about whether** - a narrow reason for not doing
  something is remembered as a principle, which is why the reason gets written down and not just
  the outcome (15).
- **A test that restates what it guards** - a third statement of a shared wording fires on a
  careful one-sided edit and stays silent on a careless two-sided one; derive the expectation from
  one side (15).
