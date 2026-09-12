# 11. What the page already knew
*~11 min read · PRs #36 to #38 · 5 September 2026*

*Where we are:* chapter 10 fixed an explanation that was wrong. This chapter is about three
facts the site had already worked out, shipped to the browser, or promised in writing, and was
showing nobody.

## The question that opened this stretch

A day spent reading the published site rather than the code turned up three defects of the same
shape. In each one the hard part was already done: the value was computed, the flag was set, the
page for the missing link existed. What was missing was the last step, the one that puts the fact
in front of a reader, and in each case something plausible had stopped it: a guard written for a
version of the site that no longer existed, a sentence written for a tile that was never built,
and a field dropped on the way out.

None of them was a crash, a wrong number or a failing test. That is the point of the chapter: the
failures a test suite is worst at catching are the ones where the code does exactly what it says
and nobody has read what it says lately.

> **Concept: a claim in the prose is a claim in the code.** The footer of this site is prose, and
> prose has no test. When the page says "outages past 24 hours are counted separately on each
> county page", that is a factual assertion about the build, as much as any assertion in
> `tests/`, and it can go false in two directions: the code can change under it, or, as here, the
> sentence can be written ahead of a feature that is then declined. Nothing in the toolchain
> notices either. The only defence is to read the site's own prose against the site periodically,
> the way you would re-run a test - and when a sentence turns out to be wrong, the interesting
> question is which half to fix. Here the sentence was right about what mattered and the code was
> behind it, so the code moved.

## What changed

### A guard that outlived its reason

Fourteen Irish towns are named for their county: Carlow, Cavan, Donegal, Kildare, Kilkenny,
Leitrim, Longford, Louth, Monaghan, Roscommon, Sligo, Tipperary, Wexford and Wicklow. Twelve of
them have a page of their own on today's data (`notes/area-pages.md`, 3 Sep 2026), built by
chapter 7a's area pass, listed in the directory, and unreachable from the search box.

The reason was a single line, `name != o.county`, written in the site's first cut. Back then
every search hit went to a county view, so a row for Carlow town would have been the County
Carlow row printed twice, and the guard kept it out. Area pages ended that: `a/carlow/carlow.html`
exists and holds the town's own outages, so the row now has somewhere of its own to go. The guard
was right when it was written and had been wrong since the day the area pages landed, which is
the ordinary way a guard goes bad.

The interesting part is that the fix needed three places and two repositories. The water site had
the same symptom by a different route: its index already carried the town, but statusui's
`searchHits` deduplicated on `name|county`, the county hit ranks first, and the town lost the key
before it could render. That dedup now keys on `name|county|target` (statusui `eecdf2d`), so a
bare name that is also a county still collapses to one row - which is what the lifts site relies
on - while an entry pointing at a different destination is treated as the different destination it
is. Then this site's index admits a county-named settlement **when it is paged**, and only then:
ESB files a fault out in the countryside under the bare county name, and bare, that string would
be exactly the redundant second row the guard existed to prevent. A test holds it out.

What the two rows say was the question that had kept this closed. `notes/area-pages.md` had
declined it in August with a condition attached: "Reopen it only with an answer for what two rows
both labelled 'Sligo' would say." The answer is how people already say it out loud. The county row
is unchanged and still first; one row below it is the town, with `town` in the annotation slot
where every other area hit shows its county. "Sligo" and "Sligo town". Renaming the page itself was
rejected, because the CSO's name and the page's heading are "Sligo" and a query of "town" would
then match fourteen rows; annotating all 26 county rows "· county" was rejected as 26 changes for
14 cases. Cost: `search.js` goes from 37,398 to 37,666 bytes, and it is fetched on the first
keystroke, so the initial load does not move at all.

The two halves were safe to merge in either order, which is worth a sentence because it is not an
accident. Until this site's statusui pin moved past `eecdf2d`, the old dedup silently dropped the
new entries - exactly as it had been dropping the water site's. A change that is inert until its
dependency arrives can be shipped without a coordinated deploy, and the pin bump rode in the same
pull request here, so the rows went live with it.

### A footer that promised a column

Since 28 August the site's footer had said that faults running past the charter's 24-hour
compensation mark are counted separately on each county page. They were not. `county_month`
computed the count, `render.build` packed it as the eighth field of every county-month row in
`data.js`, every browser that loaded the app downloaded it, and nothing read it. The sentence had
been written for a national tile that the owner then declined on the same day, for a good reason -
a tile exists to be read, and this one would read 0 in most months - and nobody went back to the
footer (`notes/design-alignment.md`, 5 Sep 2026).

It is now a column, `Over 24 h`, in the county page's month table, between Faults and Planned,
with the charter named in the heading's hover the way "Minutes lost" carries its own definition.
It reads the same payload row as the rest of the table, so the app and the static page cannot
disagree about a month. And a table is the right home for it precisely because of the number that
made it a bad tile: on the corpus to 5 September there are **6 faults over 24 hours in 1,387**,
three of them with a confirmed restore. A column that is 0 on nearly every row is legible; a tile
that is 0 on nearly every county is furniture.

No new bytes on the initial load, because the payload had been carrying the field all along.

### The row that told the reader least

The third one is the largest, and it is about the row a reader is most likely to have opened the
site to read: the outage that is still out.

`Outage.ongoing` has decided since 18 August whether a fault is judged on the charter at all
(chapter 5: an outage still listed at the last poll is not scored). `case_record`, which turns an
event into the twelve numbers a row is rendered from, did not carry it. So a fault that was still
out at the horizon rendered as "off for about 2 h · no restore time published" - the identical
words to a fault that had quietly left the feed without ESB ever publishing a time. And because
the record shipped the estimate only beside a confirmed restore, the live row also threw away the
one number a reader in the dark actually wants: when ESB expects to be back.

> **Concept: absent state renders as the default state.** The renderer had no flag for "this is
> still happening", so a live fault fell through to the shape written for a finished one, and the
> output was not blank or broken but a confident sentence about a completed outage. This is the
> same failure mode as chapter 8's month that would not start and chapter 5's `now`: when a fact
> is missing rather than wrong, the page does not look uncertain, it looks calm. Anything that can
> be *in progress* needs that state carried all the way to the surface, because the fallback is
> never "we don't know" - the fallback is whatever the code happens to print.

The record gains a twelfth field, `ongoing`, and ships the estimate whenever it is set. `_end_bits`
and its JavaScript mirror `endBits` take the flag before any other shape, so a live row says what
is known and nothing else:

| What ESB has said | The fault row now reads |
|---|---|
| nothing | still out when last checked · no estimate published |
| a time still ahead | still out when last checked · expected back by 07:30 |
| a time already gone | still out when last checked · past ESB's estimate of 00:15 |

The three faults live at the 5 September horizon happened to be one of each: Kilkee with no
estimate, Kilcock expected back at 07:30, and Carrigaline five hours past its 00:15. Planned works
keep their schedule wording, because a listing is not an observed outage, and gain "still listed
when last checked"; Templeogue's had been reading "listed for about 3 days · no end time
published" while ESB had it scheduled to the 9th the whole time.

A live fault gets **no span**. "Off for about 2 h so far" was the first draft and was dropped: the
end of an ongoing outage is the collection horizon, and where the model has already ended it on a
passed estimate the span would stop at the estimate rather than at the last sighting, understating
by the distance between them. The row already says when it began, and the data's age is on the
banner. For the same reason the phrase is "when last checked" rather than a clock time: the exact
horizon left the county page on 28 August (chapter 7b) and this does not quietly bring it back.

### Worked example: the row that contradicted itself

Review of the first cut found three shapes the single-id tests could not reach, and the sharpest
is a merged event - chapter 4a's several-records-one-fault - where the members disagree.

ESB confirms the ender restored at 01:52. A sibling record of the same fault is still listed at
the next poll, because the feed takes a cycle to catch up. `ongoing` was computed with `any()`
over the members, so one lingering sibling made the whole event live, and the row read:

> still out when last checked · past ESB's estimate of 01:52

For an outage ESB had confirmed restored at 01:52. The row managed to be wrong twice in one line,
and the event also sat out of the grade for one build. Seven groups in the corpus hit that shape
at the build after their restore. `_merge_group` already treats a sibling lingering a poll cycle
past a confirmed restore as the feed catching up, so `ongoing` now follows the ender, exactly as
`end` always has.

The other two are worth a line each. "No estimate published" was being asserted from the ender's
estimate alone, but the ender is the record ESB listed latest, not the one it put a time on: a
live event now borrows the latest estimate across its members when its own ender carries none
(seven unrestored groups had that shape). And "expected back by" was being judged against the
row's end, which for a listed outage is the *last sighting*, up to a poll cycle before the horizon.
An estimate falling in that gap has already passed by the data's own clock. The comparison now runs
against the horizon, and `_case_html` takes it as an argument rather than defaulting to anything,
so a caller cannot fall back to the sighting by accident. Both renderers, Python and JavaScript,
were then checked against each other under node across all fourteen row shapes.

## What got left undone, on purpose

167 of the 179 delisted faults carry an estimate that lies *after* their last sighting: ESB dropped
them from the feed before the time it had named. Those rows still say "off for about 4 h · no
restore time published" and do not mention what ESB had expected. Whether they should is a
different question with a different shape - it is a claim about a fault nobody confirmed ended -
and it is written down as residue rather than guessed at.

## The water site's version of the same day

Two of the three have a clean counterpart across the river, and the third does not, which is
itself the contrast.

The search guard is one bug with two symptoms and three fixes, and it is the clearest thing the
shared design layer has produced since chapter 6a: a dedup rule living upstream was quietly eating
a row on both sites for different reasons, and one key change fixed both.

The live row has no counterpart, because the water site's problem is the mirror image. There, a
notice stays listed until it is lifted, so "still going" is the default state and needs no flag;
what that site cannot see is the *end* - its `closed_at` is a floor, because short-lived cases are
never observed open at all. Here the ends are structured and reliable (chapter 3) and it was the
liveness that got dropped on the way to the page. Each feed hides the half the other one hands
over.

The 24-hour column has no counterpart at all, for the reason chapter 4b opened with: the charter's
compensation mark is a number ESB published and a water customer has nothing equivalent to be
counted against.

## Where it left the site

Twelve town pages that had existed for a week became findable; a promise the footer had been
making for eight days became true; and the live outage row, which had been the least informative
row on the site, became the most specific one. Not one of the three was found by a test, and none
of them could have been: every one was the code doing exactly what it said.

## Notes

- `notes/area-pages.md` "The county-named towns reach the box" (3 Sep 2026): issue #28; the
  `name != o.county` guard from `ca7638d`; fourteen county-named towns, twelve paged; statusui
  `eecdf2d`'s `name|county|target` dedup; the three rejected alternatives; `search.js`
  37,398 → 37,666 bytes, initial load unmoved at 63.9 KB.
- `notes/design-alignment.md` "The county table carries the 24-hour count the footer promised"
  (5 Sep 2026): `over_compensation` computed and shipped since 28 Aug and read by nothing; the
  `Over 24 h` column; 6 of 1,387 faults, 3 confirmed; the declined tile.
- `notes/design-alignment.md` "An outage still out says so" (5 Sep 2026): the twelfth field; the
  row-shape table; Kilkee, Kilcock, Carrigaline, Templeogue; why no span; the three review
  findings with their corpus counts (seven groups each for the first two); the 167-of-179 residue.
- PRs #36, #37 and #38, all merged 5 September 2026. Chapter 5 for the horizon, chapter 4a for
  merged events, chapter 7a for the area pages the search box could not reach.
