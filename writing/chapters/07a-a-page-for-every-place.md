# 7a. A page for every place
*~8 min read · PRs #21 to #24 · 27 to 28 August 2026*

*Where we are:* chapter 6b left the site reading like its siblings, with each county holding a
durable page. The next two days pushed a level deeper, to the town, and ran into the one thing
this feed cannot tell you: not when an outage happened, or how big it was, but *who* it hit.

## The question that opened this stretch

The water site grew area pages on 26 August: a page for every named town and parish, and a
directory listing all of them. The argument transferred directly. A county is not a place
anybody lives in, and a reader whose power went off in Newbridge wants Newbridge, not Kildare
averaged over 26 days.

The machinery transferred too, and cheaply, because it was already here and being thrown away.
Chapter 4b's Small Area lookup had been resolving every outage to a *settlement* since the
county work landed; the site simply discarded that half of the answer when it loaded outages
(PR #21, 27 Aug 2026). The Census lookups in `esb_site/data/` are byte-identical to the water
site's. So the build starts grouping merged events by area, and the site gains **384 area
pages** plus a 179 KB directory, with the initial load untouched at 56 KB against the 500 KB
budget.

What did not transfer was the meaning of a pin, and that is this chapter.

## What changed

### The pin is where the fault is, not who is off

> **Concept: attribution, and why this feed cannot do it.** The water site's notice names a
> supply area, so drawing a 500 m circle around its pin and counting the Census population
> inside is an approximation of something real. ESB publishes a point per outage, and that
> point is *the fault* - a pole, a substation, a length of feeder - not the households it cut
> off. A fault on a feeder outside town A can black out towns B and C and still be filed under
> A alone. Two visible consequences follow, and both had to be said rather than hidden: an area
> page can look quiet while the village next to it sat in the dark, and an outage listed on an
> area's page can report more customers than the area has people, because the count belongs to
> the whole event and not to the area it was filed under (`notes/area-pages.md`, 27 Aug 2026).

The tempting fix is to build a footprint: put a radius on each pin, spread its customers over
the Small Areas inside, and let towns B and C get their share. That would reopen a decision
chapter 4b settled with numbers, and it would import the water site's largest standing
assumption into a site that has never needed one. It was not considered.

The answer taken instead is wording plus navigation, which is a weaker claim honestly made
rather than a stronger claim invented. Every list heading says outages **pinned near** the
area. A one-line disclaimer states the filing rule and why a count can exceed the population.
And each area page carries a **Nearby areas** card listing the five nearest paged areas by
population-weighted centroid distance, deliberately crossing county lines - Balbriggan's
nearest neighbour is Stamullen, Co. Meath, five kilometres away and in another county (PR #21).
If a reader's power went off and their own area's page looks empty, the card is the route to
the page that probably has it.

What *did* transfer from the water site unchanged is worth listing, because it is a good
example of a design decision aging well in a second home: named settlements and city electoral
areas get pages while the "Around ..." Electoral Divisions and city remainder buckets get
directory rows only (904 of 3,717 area codes qualify); **no outage-count floor**, because a
permanent link that comes and goes is worse than a short one; paths keyed on the unique
county-and-name pair; uncapped lists, so a page promising "every one of them" is telling the
truth; and record-first meta descriptions, chapter 6b's truncation rule. Also transferred: **no
grade, no day bar and no CML at area level**. The grade bands are calibrated to county-months
and the day-cell buckets divide by a denominator that saturates against a village, so both
would produce confident nonsense at this scale. An area page reports counts and a history, and
declines to award a letter.

### The search box could not reach them (PR #22, 27 August)

The pages shipped, and the one control a reader would use to find them did not work: typing
"Newbridge" and clicking the hit landed you on County Kildare, to find Newbridge again
yourself. The cause was in the shared layer rather than in a routing choice here - the search
index returned a name and a county and threw the matched *name* away, so the click handler had
nothing to route on.

Fixing it produced the stretch's cleanest example of the family rule from chapter 6a working
in reverse. The water site has an in-app area *view* as well as its area pages, so the
symmetric answer was to build one here and point search at it. It was reconsidered, and
declined again: the two are the same content, an in-app view has no month tabs and no search
box inside it, and a page is indexable, shareable and middle-clickable where a fragment is none
of those. **A search hit is an entry point, not a drill-down.** So the two sites converge on
the *page*, with the same code in both, and this one needs no route to get there (PR #22,
27 Aug 2026; `notes/area-pages.md`). Convergence is the goal; identical navigation is not the
same thing as convergence.

Two smaller decisions in the same pull request are worth keeping. The index deliberately holds
ESB's own location strings beside the Census names - "Skerries Road" is not a settlement, and
neither is an "Around ..." Electoral Division - so those hits go to the county and are
annotated "· county" in the dropdown. A hit that quietly does something other than what it
says is worse than one that says what it will do. And no broken link is possible by
construction: the page builder and the index builder read the same list of outages, so a name
only carries a page's address when a page was written from the same events. A test asserts it
anyway, that being the one thing this index must never do.

#### Worked example: a rename that was load-bearing

The search index file is fetched lazily, on the first keystroke, which means a browser tab
opened *before* a deploy pairs its own already-inlined code with the *current* index file.
When the file's shape changed, the old code called a text operation on the new pair-shaped
entry and threw - before the dropdown's markup was assigned, leaving the box stuck on
"Searching..." until a reload. Reproduced against the live code. The fix was to rename the
variable the file assigns as well as changing its shape, so the old code sees nothing at all
and falls into its own error path: "Search is unavailable - try reloading", which is the box's
own state, and which tells the reader what to do (PR #22, from review). A stale tab is not an
edge case on a site people reach from search results and leave open.

### The cap came off (PR #23, 27 August)

Chapter 6b raised the county page's outage list from 40 to 150 and called it an archive. Two
days later, a read of the live pages end to end - driven from the water site, whose own pages
got the same treatment - found the obvious objection: a page whose entire purpose is to be the
durable, indexable record of a county should not be the one surface holding a fraction of it.
The cap is gone. `county_page` renders every case it has.

Rebuilt against the real corpus, the largest county page (Cork) goes from 100.7 KB to 127.4 KB
and the 26 together from 1,767 KB to 1,825 KB (PR #23, 27 Aug 2026). The old comment's
objection stands and was written into the notes rather than deleted: the archive grows without
bound, and nothing now bounds the page. If a bound is needed again it should be a **byte
budget, not a count** - a count was always a proxy for bytes, and a poor one, since a row's
width varies with the length of the location string. The page's description could then drop
its careful hedging and say "Month-by-month totals and every outage recorded", a sentence that
is now true rather than merely un-false. Chapter 6b's truncation-ordering rule still applies;
it just has an easier job.

The same pass fixed a bug both sites had been carrying in the same rule: `base.css` resets a
list's margin but not its padding, so removing the bullet markers left the 40-pixel gutter the
markers used to sit in. The water site had it in two places, which is what turned it up here.
And a "one name per thing" pass settled the vocabulary: the directory is "every area with an
outage", the app is "County X's interactive view", and heading counts read "· N outages"
instead of a bare number with nothing saying what it counts.

### Alphabetical (PR #24, 28 August)

One line, and a good illustration of who a page is for. The overview list was ordered worst
grade first, with ungraded counties sunk to the bottom by a sentinel value. That is the order
an analyst wants. A reader wants to find their own county, and for that the only useful order
is the alphabet. The stale "worst first" comment went with the sort (PR #24, 28 Aug 2026).
The water site had reached the same conclusion two days earlier; both county lists are now
alphabetical.

## Where it left the site

412 pages where there had been 27: an index, 26 county archives, 384 area pages and a
directory, with a search box that reaches the right one and a sitemap that lists them all.
Every claim about *who* an outage affected is hedged in the page's own words, with a
neighbouring-areas card as the honest substitute for a footprint model this feed cannot
support. And the initial load is still 56 KB, because none of it rides in the payload.

## Notes

- PR #21 (27 Aug 2026): 384 area pages, `areas.html` 179 KB, initial load 56 KB; `place()`
  returns county, code and town, `Outage.town_code`; 904 of 3,717 codes get pages; no grade,
  day bar or CML at area level; nearby-areas card (Balbriggan to Stamullen, 5 km); 208 tests;
  sitemap 27 to 412 URLs. `notes/area-pages.md` "The pin is where the fault is".
- PR #22 (27 Aug 2026): search hits become real links; the in-app area view reconsidered and
  declined; ESB location strings and "Around ..." EDs annotated "· county"; the index rename
  and the stale-tab failure; no-broken-link-by-construction test; 213 tests. Fourteen
  settlements sharing their county's name are excluded from the index by a pre-existing line,
  recorded as follow-up.
- PR #23 (27 Aug 2026): `COUNTY_PAGE_CASES` gone; Cork 100.7 to 127.4 KB, 26 pages 1,767 to
  1,825 KB; byte budget over count, recorded; "one name per thing"; the `ul.areas` 40-pixel
  padding bug; `TestTheCap` became `TestTheHistoryListing`.
- PR #24 (28 Aug 2026): alphabetical overview.
- The water site's equivalents: its series, chapter 16 and its own area-pages work of
  26 August; the 500 m footprint it rests on is its chapters 8a and 8b.
