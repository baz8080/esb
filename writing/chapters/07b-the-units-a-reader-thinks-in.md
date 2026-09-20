# 7b. The units a reader thinks in
*~12 min read · PRs #25 to #29 · 28 to 30 August 2026*

*Where we are:* the site now has a page for every county and every named area (chapter 7a).
The last three days this account covers are about what the numbers on those pages *say*: the
clock they are on, the units they are in, the sentences they are wrapped in, and one letter
that was missing from the alphabet.

## The question that opened this stretch

An owner read of the live site, surface by surface, produced twelve commits in one pull
request and a run of smaller ones after it. The through-line is a single question asked of
every figure on the page: **is this in a unit the reader is already holding?** Chapter 6b's
pass had fixed the *words*. This one found that several of the numbers were still in the
builder's units - a rate where the page was talking about a month, a calendar span where the
page was organised by months, a database row where the reader wanted a sentence.

## What changed

### Every figure beside a month is on that month's clock (PR #25, 28 August)

The national tile read `154` Customer Minutes Lost, and it was an *annualised rate*: a month's
customer-minutes scaled up to a year over the observed window. It sat among a heading, a day
bar, county rows and counts that were all one month. The reader had no way to know that one
of the five numbers in front of them had been multiplied by twelve.

It now shows the month's own figure - **12.8 minutes lost per customer** - and the county
page's month table moved with it, its column headed "Minutes lost" rather than CML. The
annualised rate is not lost: it survives in the one paragraph on the site that talks in years,
the disclosure that argues with ESB's published 117.47 for 2024, where a yearly rate is the
only thing that could go (PR #25, 28 Aug 2026; `notes/design-alignment.md`).

The same reasoning retired a unit. The customer-time total had read "54 years of customer time
off supply" - chapter 6b's own improvement on "17215 days", and still wrong, for a reason that
is not about whether a given reader misreads it. **A unit named after a calendar span collides
with a page organised by months.** The word *years* printed beside three figures that were all
one month's is a collision whatever the arithmetic. The tile is in customer-hours now, and
stays there.

#### Worked example: is half a million customer-hours plausible?

The tile then read **473,067 customer-hours off supply** for 1 to 27 August, which looks
enormous, and a figure that looks enormous either has an error behind it or an explanation.
It has an explanation, and it decomposes three ways (`notes/grading.md`, 28 Aug 2026):

- **As the product it is.** 311,321 customers interrupted × 1.52 hours mean time off =
  473,067. That mean is 91 minutes, which is CAIDI - the one index the customer-count bias
  divides out of (chapter 4b), and the figure the national test holds against ESB's own 85.
  The duration half of the multiplication is the best-evidenced number on the site.
- **Per customer.** 473,067 hours ÷ 2.5M meters = **11.4 minutes each**, which is exactly what
  the minutes-lost tile beside it now says. The two tiles are the same fact in two units, and a
  reader can check one against the other by eye - which they could not do while one of them was
  annualised. The unit fix made the page self-checking.
- **Against ESB's published figures.** 117.47 CML × 2.5M = 4,894,583 customer-hours a year, or
  348,655 over a 26-day window. This site says 473,067: **1.36×**, while the interrupted-customer
  count is **1.27×** what ESB's published interruption index implies over the same window.
  Durations agree, headcount does not, which is the documented feed bias of chapter 4b plus
  ESB excluding storm days where this site excludes nothing. Nothing new is wrong.

And it is not one bad day: 1,051 faults, median event 135 customer-hours against a mean of
450, the top ten events 15.8% of the total and the top fifty 43.5%. The largest single
contributor, Whitehall in Dublin on 23 August, is 2.4% of the month. A long tail of ordinary
faults is the shape this total should have, and the note says what to suspect if it ever stops
having it: a merge failure or a duration blowing out, not a bad month.

### The outage row stopped reading like a database row (PR #25)

The rows themselves were still records rather than sentences. A floating duration sat at the
end of each line, detached from the timestamp it measured, and was blank on the 40% of rows
that are planned works quietly delisted. "Last seen out at 08:31" printed the clock time of a
*sighting* and left the reader to subtract. "Not confirmed" was ambiguous exactly where it
could least afford to be, since it could mean the estimate or the outage, and meant neither:
it meant ESB published no restore time.

One phrase per shape now, with the span inside the phrase it measures, and the shapes are not
evenly weighted (measured 28 Aug 2026):

| shape | share | reads |
|---|---:|---|
| planned, delisted | 39.7% | `listed for about 7 h · no end time published` |
| fault, restored | 36.6% | `restored 07:07 (2 h 2 min) · 2 h 8 min earlier than ESB estimated` |
| planned, scheduled end | 15.0% | `scheduled until 15:00 (4 h 34 min)` |
| fault, delisted | 6.0% | `off for under 30 min · no restore time published` |
| fault, estimate only | 2.7% | `expected back by 04:15 (about 1 h) · no restore time published` |

The second row is chapter 3's end-source labelling growing up into a comparison a reader can
use: a restore is now stated *against* ESB's estimate rather than printed beside it. **69% of
restored faults beat the estimate, by a median of 58 minutes; 25% miss it, by a median of 54
minutes**, and inside five minutes the clause is dropped as noise. The site has been carrying
the evidence for that since chapter 3 measured its end-time fallbacks; this is the first pass
that puts it in front of the person reading about their own outage.

One decision here belongs to chapter 1's invariant rather than to design. ESB's planned works
carry a reason, and the reason now appears in the row's tag as a label - `Planned · line
diversion` - through a closed set of six with a lower-cased fallback. It lives **in the site,
not as a column in the database**: the database is disposable, the collector captures rather
than interprets, and an unmapped seventh reason has to keep rendering rather than break a
build. Where interpretation lives is a question this repository answers the same way every
time.

### The county page became an archive and nothing else (PR #25)

Three things left the county page, and the third is the interesting one. Its newest month's
card went, because its four tiles were a copy of the first row of the table directly below it,
so the page opened by repeating its own next section. Its age line went, which is stated
plainly rather than hidden: **a county page no longer warns that collection has stopped.**
What is left on it is static and still true - the month table's newest row says "to 27 Aug" -
and the index keeps the live banner chapter 6b built.

With no day bar to caption and no age to compute, the page had no behaviour left at all, so
the shared JavaScript is no longer inlined into it: **county pages went from 1,840 KB to
1,349 KB across 26 files**, about 15 KB saved on each page, on pages that are by design
entered cold from a search result (`notes/design-alignment.md`, 28 Aug 2026). Day bars are the
app's alone now. It is a pleasing shape for chapter 6a's shared layer to end up in: the
cheapest page is the one that stopped needing any of it.

### A guard that would have passed by seeing less (PR #26, 28 August)

Upstream, the shared layer split its day-caption listener into a file of its own, so a static
page can inline one small listener instead of the fifteen kilobytes of application it never
calls. That made the main shared file about half its former size - and this repository's guard
against a page redeclaring a shared name worked by *reading that file* and collecting the names
in it.

> **Concept: a guard that shrinks silently.** The test asked "does any page script redeclare a
> name the shared layer already defines?", and built the list of names by parsing the shared
> file. After the upstream split, that file no longer contained the caption listener's name.
> The guard would have kept passing - **by checking fewer things**. Nothing anywhere would have
> gone red: not the suite, not CI, not the rollout, because a guard reading a shorter list
> passes more easily, not less. This is the failure mode that makes tests-of-tests worth
> writing: the guard now *asks the shared package* for its list of names rather than parsing a
> file, and asserts that the caption listener is in what it got, so a bundle that arrives
> reshaped fails instead of quietly covering less. Chapter 6b's applies-tests were the same
> lesson about a stylesheet rule; this is it about a name (PR #26, 28 Aug 2026).

### A rule that binds this series (PR #27, 29 August)

One paragraph of documentation, no code, and it is in this account because it applies to this
account. The repository's instructions now say: **no em dashes** - not in the site's prose, the
code comments, the notes, commit messages, pull request bodies, or the replies in a working
session. The house dash is a spaced hyphen.

The interesting part is why it was missing. The rule had existed for months, in a personal
configuration file on one machine, and a session started in a browser gets a fresh container
that clones the repository and nothing else. So a rule kept outside the repository reached
none of the sessions that actually ran here, and got broken accordingly. A convention that
lives anywhere but in the repository is a convention that only applies when its author is in
the room.

It is stated, not enforced. The sibling lift site got a checker in its lint job because its
files were already clean; this repository carried **199 em dashes and 21 en dashes across 11
files** on the day the rule landed, most of them in settled notes, and a checker would have
failed on day one with no way to green it but a re-punctuation nobody asked for. So the rule
binds new prose and says to fix the rest only on lines already being edited. This series was
drafted the day before it landed, and was re-punctuated wholesale to meet it, which is what
"binds new prose" means when the prose has not been published yet.

### The scale grew an E (PR #29, 29 to 30 August)

The grade in chapter 4b ran A, B, C, D, F. Skipping E is an American convention and ESB is not
American, so the letter was added. It splits the old F band and moves nothing else: A stays on
ESB's own 95% aim and every cut down to 70 sits where it did, so **no county-month graded A to
D changes letter**.

The cut is **60%**, continuing the ten-point step the scale already uses below B. Measured over
the 26 graded county-months in a rebuild of the current data, the old F band held exactly two:
Sligo at 68.0% and Longford at 59.3%. A cut at 60 puts one in each, which is the outcome that
makes the split worth having; 55 and 50 were rejected for emptying F outright, and 65 gives the
same split as 60 while breaking the step for no gain (`notes/grading.md`, 29 Aug 2026).

The contrast with the water site is the whole reason this was a small change here. That site's
letters are calibrated against its own dataset, so adding a band there meant *fitting* one, and
its distribution had to be re-checked. These bands are anchored to a published standard, so the
arithmetic sets the cut and the distribution only has to be checked for the failure mode of a
band nobody can reach. Graded county-months in the 29 August rebuild: **A 8, B 6, C 9, D 1,
E 1, F 1**.

Two things travelled with it. A test already held the page's grade wording and the app's grade
wording together *by wording*, but not *by letter* - so a band could be added with nothing
behind its chip's hover title, and the test now checks every band the model grades has an
explanation. And the pin bump that brought the sixth chip also brought a contrast decision from
upstream: the B and D chips moved to white lettering, because dark ink on them had been chosen
on one accessibility standard and a newer perceptual one rates it far worse (B measured 38.6
against 69.2 for white). C is now the only chip taking dark ink. The old note about the water
site's contrast pass never reaching this site is left alone, being dated history about the
vendored era rather than a claim about today's chips.

## Where it left the site

As of 30 August 2026: every figure on a month's page is on that month's clock, in units named
after things a reader holds; outage rows that read as sentences and compare a restoration to
the promise it was measured against; county pages that are pure archive, 27% lighter and
JavaScript-free; a name guard that cannot shrink; a punctuation rule that reaches the sessions
that need it; and a six-letter scale whose new band was set by arithmetic rather than by
fitting. 221 tests, and an initial load of 60.0 KB against the 500 KB budget.

## Notes

- PR #25 (28 Aug 2026): CML tile to `cml_month` (12.8 per customer), month table "Minutes
  lost", annualised rate kept only in the ESB-comparison disclosure; customer-hours (473,067);
  outage-row shapes table and shares; restore compared against estimate (69% early, median 58
  min; 25% late, median 54 min; 5-minute noise floor); `model.PLANNED_REASONS` in the site not
  the database; county page loses its card, age line and all JavaScript (1,840 to 1,349 KB);
  219 tests. `notes/design-alignment.md` "The tiles say what they mean", "The outage row
  stopped reading like a database row", "The county page became an archive".
- `notes/grading.md` "Is half a million customer-hours in a month plausible?" (28 Aug 2026):
  311,321 × 1.52 h; 11.4 min per customer; 1.36× vs ESB's implied 348,655, headcount 1.27×;
  1,051 faults, median 135 / mean 450 customer-hours, top 10 = 15.8%, top 50 = 43.5%,
  Whitehall 23 Aug = 2.4%.
- PR #26 (28 Aug 2026): the guard asks the shared package for its globals rather than parsing
  a file, and asserts the caption listener is among them; verified by injecting a
  redeclaration; 219 tests.
- PR #27 (29 Aug 2026): the punctuation rule; 199 em dashes and 21 en dashes across 11 files;
  why a user-level rule never reaches a browser session; stated not enforced.
- PR #29 (29 to 30 Aug 2026) and `notes/grading.md` "The scale grew an E": the 60% cut, Sligo
  68.0% and Longford 59.3%, 55/50/65 rejected; no A-to-D letter moves; distribution A 8, B 6,
  C 9, D 1, E 1, F 1; the wording-by-letter test; upstream chip contrast (B at 38.6 vs 69.2);
  221 tests, 60.0 KB initial load. The August 2026 per-band table in the note keeps its
  original row, marked as measured on the five-band scale.
