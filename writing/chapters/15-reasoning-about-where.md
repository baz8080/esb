# 15. The hover that was read as a rule
*~7 min read · PR #44 · 7 September 2026*

*Where we are:* chapter 10 took apart the one sentence that explained a missing grade and found
three different gates under it. Four days later, eight counties showed a dash that nothing on a
phone could explain, and the reason turns out to be a sentence in chapter 10 itself.

## The question that opened this stretch

Reported from the site, on 7 September: Carlow, Cavan, Limerick, Longford "and some others" show
no grade for September, and the five-day gate opened on the 6th. So the fix from chapter 10 had
landed, the month was old enough, and the dashes were still there.

Nothing was broken. All eight counties are the fault gate, and they are genuinely small:

| County | Faults in September to the 7th |
|---|---:|
| Carlow | 1 |
| Longford | 1 |
| Offaly, Waterford, Westmeath | 2 |
| Limerick | 3 |
| Cavan, Tipperary | 4 |

Eight of 26 counties, every one of them under the five-fault minimum, and the site had computed
the correct sentence for each of them. Into a `title` attribute. Which is precisely the failure
chapter 10 was written about, three days after it was written about.

## What changed

### The sentence that caused it

Chapter 10 moved the day gate's explanation out of the hover and into the open, and left the other
two where they were. Its own account of that decision reads:

> The day-gate sentence is now printed in the open [...] and said **once** rather than in 26 chips,
> because that gate is national and the other two are not. Where a message is displayed follows
> from whose fact it is. The per-county fault case stays in the tooltip, since that row already
> shows its own fault count beside the dash.

Every clause of that is true, and the conclusion is still wrong. The argument is about **where** to
print a sentence: a national gate covers all 26 counties, so print it once above the list rather
than 26 times inside chips. That is a real constraint and it decides a layout question. It says
nothing whatever about whether a county-scoped reason should be reachable by a reader who cannot
hover, and the fault-gate case was left in the tooltip as though it had.

> **Concept: reasoning about where, read later as a rule about whether.** A decision not to do
> something arrives with a reason attached, and the reason is usually narrow: this particular
> placement would repeat itself 26 times. What survives into the next week is the outcome - "the
> county gates stay in the tooltip" - with the narrow reason quietly promoted into a principle
> nobody ever argued for. This is the failure mode the repository's dated notes exist to prevent,
> and the notes did their job: the argument was written down in full, which is how re-reading it
> four days later showed that it had never covered the case it was being used to justify. The
> general guard is to record *why* a thing was not done, in terms specific enough that a later
> reader can check whether the why still applies, rather than recording only that it was not done.

The gates are not equally in need of explanation - a county with one fault in a week is less
mysterious than a whole country of dashes - but none of them is self-evident from a dash, and a
dash with nothing beside it reads as a verdict rather than as an absence.

### The reason in the open, wherever the dash is

The reason is now printed wherever a reader can meet a missing letter, whichever gate withheld it:

- **On `c/<slug>.html`**, under the county's name, for any ungraded newest month. The page had
  been testing the day gate specifically; it now tests the reason itself, so all three gates
  reach it.
- **In the app's county view**, the same sentence, off the same source.
- **Under the month table**, for the *older* ungraded months. Every month is a row there, and
  July's dash - three hours of collection on the 31st - had no explanation anywhere on the page at
  all. The newest month is excluded because the chip above already carries it.
- **Above the county list**, as a count rather than a list of names: "8 counties are not graded in
  September 2026: too few faults to grade fairly". Only the app sees all 26 counties at once, and
  26 chips repeating one sentence is the thing the national line exists to avoid. It splits the
  count when both county gates apply, and stays quiet inside the day gate, whose own sentence is
  sitting beside it covering every county anyway.

The count deliberately does not say "8 of 26": a reader looking at a list of 26 rows can see the
denominator, and the shorter sentence is the one that gets read.

All of that is one new sentence. The counted line above the list is the only wording that has no
per-county twin to reuse; every other sentence comes from `render.ungraded_reason`, which chapter
10 built, mirrored once in `site.html`. Adding four placements without adding four wordings is the
whole reason the earlier chapter's helper was worth building.

The footer moved too, in both directions. It had documented two gates and now documents three. And
it had claimed "the page says which of the three it is", which the index does not do - its line
counts rather than names, and in a mixed month a given county's own reason is still in its chip.
The footer now points at a county's own page, which does.

### Worked example: a mirror test that could not fail

The interesting review finding is not in the render path at all.

Two renderers produce these sentences - Python for the static pages, JavaScript for the app - and
a test has guarded their agreement since chapter 10. It did so by restating the four wordings as
literals and checking both sides against them. That test catches a unilateral edit of `site.html`.
It does not catch the edit anyone would actually make: reword `ungraded_reason` and the two
assertions about it in the same commit, and the test stays green while the two halves of the site
disagree.

The test now reads each sentence **out of** `ungraded_reason`, splits off the parts the JavaScript
assembles for itself (the month label, and the day gate's date), and asserts the remainder appears
in `site.html` as a quoted JavaScript string literal. Quoted is load-bearing: as a bare substring,
" to grade fairly" was satisfied by the county list's own note, "too few faults to grade fairly.",
and the drift went unnoticed. And the whole thing was verified the only way such a test can be -
by mutating `site.html` and checking that the test fails now and did not before.

> **Concept: a test that restates what it guards.** A test written to keep two implementations in
> agreement must derive its expectation from one of them, not state it a third time. A third
> statement is a third place to edit, and the failure it produces is the wrong way round: it fires
> when someone changes one side carefully, and stays silent when someone changes both sides
> carelessly. This is the same family as chapter 7b's guard that shrank silently - a check that
> builds its own idea of what to check can always pass by checking less - and the remedy is the
> same: read the list from the source, then assert what must be in it.

## The one measurement in it

The under-table note prints one sentence per ungraded older month, which would become a run-on
paragraph for a county that collects them. Rather than engineering around a hypothetical, the rate
was measured: in August, the only whole month collected so far, **no county was under the
five-fault gate at all**, and the quietest, Longford, had 12 faults - 2.4 times the floor. The
gates that do fire are the two partial months at either end of collection, so the note is one
sentence, July's, and stays one sentence. The number is written into the note with instructions to
collapse the list if a genuinely quiet month ever turns up.

That is the same posture as the rest of the series and worth naming as it recurs: the question
"what if this gets long?" is answered with the distribution rather than with a mechanism.

## Where it left the site

Three gates, four sentences, five places a reader can meet one, and one wording source behind all
of them. A reader on a phone who sees a dash can now find out why without a pointing device,
whether the county is quiet, the month is young, or the month was never fully watched.

## Notes

- `notes/grading.md` "The other two gates were hover-only" (7 Sep 2026): the eight counties and
  their fault counts; the where-versus-whether argument; the four placements and what each one
  reads off; why the count is not "8 of 26"; the footer's two corrections; the mirror test's new
  shape and why quoting matters; August's measured floor clearance (Longford 12, 2.4x).
- PR #44, merged 7 September 2026, with its review commit ("Review follow-ups: a mirror test that
  can fail, and two overclaims").
- Chapter 10 for the three gates and `ungraded_reason`; chapter 7b for the guard that shrank
  silently; chapter 11 for the other two claims the footer was making ahead of the code.
