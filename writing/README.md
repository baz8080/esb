# The esb series - brief and style guide

A chapter-by-chapter account of how this repo grew from a script polling ESB Networks'
PowerCheck feed on a Raspberry Pi into a status site graded on ESB's own published service
standard. It is the companion to the water site's series
([uisce PR #43](https://github.com/baz8080/uisce/pull/43)): the same author, the same kind of
site, built second - and where the same problem got a different answer here, saying *why* is
this series' particular job.

Nothing in `writing/` is imported by the package. It is prose and diagrams only.

## Who it is for

The same reader as the uisce series: an intelligent professional who is not a programmer. They
can follow arithmetic when it is shown, and a table when it has real place names in it. They
will not tolerate a term used before it is explained, and they will notice a number that
appears without a sentence saying what it means. The chapters assume the reader *may* have read
the water series but must not require it: every comparison states the water site's approach in
a sentence before contrasting it.

## Voice

- First person, "I". The AI-assisted process is named once, in the intro, and not re-litigated
  chapter by chapter.
- Candid. The wrong turns - the grade that handed out an F for ordinary service, the grid that
  filed every centroid one bin east, the denominator carrying a citation it did not have - are
  the story, not embarrassments to skim past. Tell what was believed, what was measured, what
  changed.
- Chronological within a chapter. The reader should feel the order the problems arrived in.
- Plain. Prefer "the log" to "append-only JSONL", "customers" to "customer meters" once the
  meter caveat is made. Introduce a technical term once, in a concept box, then use it freely.
- **Every difference from the water site is called out where it bites**, in a consistent shape:
  what uisce does, what this site does, and the property of the *data* that forced the split.
  The differences are never taste; each one traces to a fact about the feed.

## Rules

Identical to the uisce series' rules; restated so this file stands alone.

1. **Every number carries a source and a date.** In text: "(PR #13, 26 Aug 2026)" or
   "(measured 27 Aug 2026)". Every number quoted also gets a row in `figures.md`.
2. **No figure without a sentence saying what it means.**
3. **One concept box per hard idea**, at the point the idea first matters, ≤ 200 words, in a
   blockquote starting `> **Concept: <name>**`. Where the water series already boxed the idea,
   link back and restate in one line rather than re-explaining.
4. **At least one worked example per hard concept**, using a real place and real numbers, with
   the arithmetic shown. Bealistown and Tycor are the running examples wherever they fit.
5. **Diagrams earn their place.** Mermaid fences for flows; small hand-written SVG in
   `diagrams/` for anything spatial or temporal. ≤ 40 lines, no polish.
6. **Length: target ~1,500–2,000 words, hard ceiling 3,000.** This series is deliberately
   shorter than uisce's - the repo is a month old, not eight weeks - so do not pad a light
   chapter. Each post carries a "~N min read" line (≈ 230 words/min).
7. **Standalone.** Each chapter opens with a two-line *Where we are* so it works as a single
   blog post.
8. **Vocabulary is fixed** (below); do not drift between synonyms.
9. **Missing number → `[verify: what]`** and move on; collected in the final pass.
10. **No em dashes**, per this repo's own rule (CLAUDE.md § Punctuation, 29 Aug 2026): the
    house dash is a spaced hyphen, and en dashes survive only in numeric ranges. The rule
    binds new prose, and every word here is new prose. The uisce series is written the other
    way; that is the one house-style difference between the two, and it is deliberate.

## Fixed vocabulary

| Use | Not | Meaning |
|---|---|---|
| **the feed** | the API (except in code contexts) | ESB Networks' PowerCheck service, list and detail |
| **record** | entry, id (alone) | one PowerCheck outage id as the feed publishes it |
| **event** | incident, outage-group | all records sharing a location and start time, merged to one row |
| **fault / planned** | unplanned, works | the two outage types; only faults are graded |
| **run** | poll (as a noun), pass | one scheduled collection pass, every 30 minutes |
| **observation** | detail, fetch (as a noun) | one detail fetch of one record within a run |
| **the log** | the archive, the JSONL | the raw append-only files; the source of truth |
| **the horizon** | last update, cutoff | the last moment a run actually reached the feed |
| **customers** | homes, meters (after the caveat) | ESB's count of affected connections; a meter count |
| **peak customers** | affected, total | the most customers off at any instant the event was live |
| **chain** | cluster, repeat group | consecutive faults at one spot, tagged, never merged |
| **charter share** | restore rate, SLA | % of fault-interrupted customers back inside 4 hours |
| **CML / CI / CAIDI** | - | the regulator's units: minutes lost, interruptions, minutes per interruption |
| **grade** | score, rating | the A to F letter, county-month only |
| **the water site** | uisce (except as the repo name) | the sibling site this series compares against |

## Chapter template

Same as the uisce series:

```markdown
# NN. Title
*~N min read · PRs #a–#b · dates*

*Where we are:* two lines placing this chapter in the series.

## The question that opened this stretch

## What changed
(narrative, chronological within the chapter)

> **Concept: <name>** - plain-English box, ≤ 200 words.

### Worked example: <place>
(real numbers, arithmetic shown, source + date)

## What went wrong / what got retracted   ← when applicable

## Where it left the site
(the numbers as of the chapter's last PR)

## Notes
PRs, commit subjects, `notes/` sections and code functions used; each figure's source.
```

## Working method

Session 0 (27 August 2026) drafted chapters 0 to 6b and the closing in one pass, from the
repository's own history - the commit messages, the pull request bodies, the `notes/` files
and the README - with the water series' chapters 14 and 16 open beside it, since they narrate
the same days from the other bank.

Session 1 (31 August 2026) merged `main`, swept the series to the new punctuation rule, added
chapters 7a and 7b for pull requests #21 to #29, renumbered the closing to 8, and corrected
the figures those days moved (the grade scale, the county-page cap, the commit and test
counts). Figures are registered in `figures.md` as quoted; the few re-run against the working
tree say so, with the date. `PROGRESS.md` is the ledger for any later session.
