# 13. Where faults keep happening
*~8 min read · PR #40 · 6 September 2026*

*Where we are:* by chapter 12 the site publishes a grade, the regulator's units and a promise
score. Everything it shows is still either alphabetical or chronological. This chapter is about
the first thing on it that is ranked, and about giving the rows away.

## The question that opened this stretch

Westport has had 26 faults in five weeks. Killinick has had 23, Milltown 16. None of those
sentences could be got off the site: the area directory is alphabetical, the county history is
chronological, and a reader who suspected their own town was a bad spot had no way to find out
except by counting rows.

That is a strange gap in a site whose whole subject is where the grid is worst, and it existed
because ranking is the easiest thing in the world to do badly. A ranked list is an accusation:
these ten places are the bad ones. Publishing one means being sure the names in it are names of
places, that the counts behind them are the counts the rest of the page uses, and that the list
does not quietly rank an artefact of the feed.

## What changed

### A card that ranks, and links nowhere

The county page gains "Where faults keep happening": the ten of ESB's own location names with the
most faults across every month collected, two or more, each with its count and the largest number
of customers any single one of them took out.

The rows link nowhere, and that is the decision the card is really about. The obvious link is the
area page of chapter 7a, and it would be wrong: a location name is where ESB says the fault is,
not a place the Census recognises, and **222 of the 422 location names in the corpus have been
pinned to more than one Census area**. Westport's 26 faults sit in an area the site calls "Around
Killavally"; Wexford's 12 sit in "Around Whitechurch". A link would assert an identity between the
two names that the placement pipeline does not support, so the note under the heading says so
instead, in the same words the area pages use for the same problem.

> **Concept: a ranking is a claim about its labels.** Sorting is arithmetic and is never the hard
> part; the hard part is that a ranked list asserts that each row is a thing of the same kind, that
> the things are distinct from each other, and that the label names the thing. Chapter 7a's
> attribution box said the published point is the fault rather than the households behind it; this
> is its sibling one level up. ESB's location strings are its own operational account of where a
> fault is, which is exactly what a reader wants ranked, and exactly what cannot be turned into a
> hyperlink to a Census settlement. Ranking them is honest; linking them would not be. Where a
> label cannot carry the weight of a link, print the caveat rather than dropping the list.

Two of ESB's strings are not spots at all, and both had to be dealt with before the card could be
published. ESB files a fault out in the open countryside under the bare county name - "Wexford",
twelve faults spread over four different areas - and eleven records in the corpus carry no location
at all, which the page fills in for display with the Census area it was placed in. Ranked naively,
six county pages listed *themselves* as a top fault spot. The card now counts `Outage.esb_location`,
ESB's own string and empty where it gave none, and skips the county name, which is also how the
search box has read that string since chapter 11.

### Worked example: Monaghan's 74 outages and its 77 rows

The third correction is the one worth reading, because it is a two-lists-that-should-be-one bug of
the kind chapter 8 and chapter 11 both produced, and this time the number was visible on the page.

At the very first poll, 21:02 on 31 July 2026, ESB was still listing fourteen outages that it had
already restored. They are a real part of the log and they are not part of anything the site
measures: they overlap no observed window, so no day cell, no grade and no month table has ever
counted them, and the county page's outage list has never shown them. But they were in the
county's raw list, and the first cut of the card and the CSV built straight off that. Monaghan's
page therefore said 74 outages, its list showed 74, and its CSV had 77 rows.

Nothing about that is a rounding difference a reader could shrug off: an export that disagrees
with the page it hangs off is worse than no export, because the disagreement is discovered by the
one reader who cared enough to check. `render.build` now drops an outage restored before the first
poll at the point where the county lists are made, so the shard, the card and the CSV are three
views of one list by construction rather than by three matching filters.

### The CSV

The README has always said the point of the project is to study Irish outages over time. Until
this week the only way to do that was to clone `esb-data`, rebuild the database, and then
re-implement `merge_events` - which is to say, redo the one piece of the pipeline with the most
judgement in it (chapter 4a) and hope you redid it the same way.

Each county page now links `c/<slug>.csv`: one row per merged event, oldest first, the columns
declared in `render.CSV_COLUMNS`. Every ESB id folded into the event is in `esb_ids`. The end
carries its source, so a reader can see whether it was confirmed, estimated or a last sighting
(chapter 3). Both estimates ride along, first and last, which is chapter 12's whole distinction.
`customer_minutes` is the integrated figure off the envelope, not a multiplication. The repeat
chain position is there, and the raw latitude and longitude.

> **Concept: publish the rows the page counts.** There are two honest things a data project can
> hand out: the raw bytes it collected, and the rows it actually published from. This project has
> always done the first - the logs are a public repository - and the first is not enough, because
> every interesting claim on the site lives in the transformations between the two, and those are
> exactly where an independent re-implementation diverges. An export of the site's own rows makes
> the site checkable rather than merely reproducible: a reader can sum the column and compare it
> with the tile above the link. It also makes the project falsifiable in the only way that matters
> for a one-person pipeline, which is that somebody else can find the mistake.

The small decisions: per county rather than one national file, because the link sits on a county
page and the county is the unit a reader arrives at; written for every county, an empty one
included, so the link cannot 404; 534 KB across 26 files, listed in the build's size report as "on
request" and deliberately outside the 500 KB initial-load budget, since nothing fetches a CSV until
a reader asks for it; and not in the sitemap, because a CSV is not a page.

One idea was rejected: a repeat-chain count per row. The top eight spots hold one chain between
them, and the reason is that the two things are about different time scales - a chain is a
within-the-hour phenomenon (chapter 4a), a spot is a within-the-month one - so the column would
have been noise in nearly every row.

## Where it left the site

Ten rows cover 83% of Mayo's faults and 32% of Dublin's, which is the range a fixed cap has to
live with. 308 of the 422 location names have two or more faults; every county has at least two
such spots, the median county has nine, and Dublin has 51. No byte budget was needed for a card
that is ten rows.

## What the water site did with the same problem

The water site met the feed's own place names first and reached the opposite conclusion, for a
reason that is in the numbers rather than in the design. Its `location` string has **3,866 distinct
values**, fragments badly and carries no population, so that site threw it out of its geography
entirely and rebuilt on CSO settlements (chapter 7a). ESB's equivalent is 422 names across five
weeks, tidy enough to rank and still too ambiguous to link. Same finding about the same kind of
field - the operator's own place string is not a place - with the consequence landing in a
different spot on each site, because 422 names you can print and 3,866 you cannot.

On handing out the rows, the water site's version is its inferred end times: a JSONL of what the
rules and the model extracted, committed to the repository on every build, so the one step nobody
can reproduce from the feed alone is published as data. The two exports are the same instinct
pointed at each site's own risky step. There, the risk is an extraction from prose. Here, it is
the merge.

## Notes

- `notes/design-alignment.md` "The county page ranks its fault spots, and hands out its rows"
  (6 Sep 2026): Westport 26, Killinick 23, Milltown 16; 222 of 422 names pinned to more than one
  Census area; the bare county name and the eleven empty locations; the fourteen pre-first-poll
  restorations and Monaghan's 74 against 77; 308 of 422 with two or more faults, median county 9,
  Dublin 51, ten rows covering 83% of Mayo and 32% of Dublin; the rejected chain column; the CSV's
  reasoning, 534 KB in 26 files, kept out of the sitemap.
- `esb_site/render.py`: `CSV_COLUMNS`, and the drop of pre-first-poll restorations where the county
  lists are made. PR #40, merged 6 September 2026.
- Chapter 3 for the end sources, chapter 4a for the merge and the envelope, chapter 5 for the
  observed window and the 500 KB budget, chapter 7a for attribution and the area pages, chapter 12
  for the two estimates. The water site's 3,866 location values: its series, chapter 8a;
  its committed inference JSONL: chapter 15 there.
