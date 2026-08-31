# 6a. The third site of the family
*~7 min read · PRs #2–#11 · 19–21 August 2026*

*Where we are:* the site went live on 18 August. Within a day it stopped being a standalone
page and became the third member of a family - and the family got a shared wardrobe.

## The question that opened this stretch

By August there were three of these status sites: the water site, this one, and a third for
lift faults at train stations - same author, same construction, and deliberately made to look
alike, so that a reader who has learned one can read the others. The water series' chapter 14
tells what happened next from its side of the fence; this chapter is the *receiving* end of
the same three days, and the two views disagree in an instructive way about who was ahead.

Because from here, the motivating failure was local: **the water site's contrast pass of 18
August - darker tokens, dark lettering on the B and D grade chips - never reached this
site.** Every UI fix was being ported across three repositories by hand, "not always
successfully", which is a phrase that describes a wish rather than a mechanism
(`notes/grading.md`, 19 Aug 2026). This site launched with day-old cosmetic debt it did not
know it had.

## What changed

### First, receive a fix (PR #2, 19 August)

The first pull request after launch was this site applying a change the water site had
worked out the same morning (its PR #44): the little caption strip that reads out a hovered
day cell sat *beside* each county row, so the row's hover highlight stopped a line above the
caption. Moved inside the row's own grid, the hover band, click target and keyboard-focus
ring cover it by construction, and the per-day browser tooltips - which repeated the readout
after a delay and never fired on a phone - went. One fix, hand-ported, a day apart, in each
repository: the problem stated as a workflow.

### Then, share the wardrobe (PR #3, 19 August)

The same day, the shared part of the page - colour tokens, base rules, the row, bar, card
and footer components, the small JavaScript helpers - moved into a fourth repository,
`statusui`, and this site took its copy from there, vendored under `esb_site/ui/` and inlined
into every page at build by `statusui.assemble()`. (The water series boxed both ideas at this
point; one line each here. *Assembled at build:* every page stays a single self-contained
file - the build inlines the shared CSS and JS, so a reader still costs one request.
*Vendor or pin:* a vendored copy is files copied in, current only as of the last sync; a
pinned dependency is a recorded pointer to an exact upstream commit.)

What stayed behind is this site's identity: `site.css` keeps the bar colour buckets, the two
layout widths and the repeat-fault tag, and the domain widgets stay in the templates. The
build's own duplicates - a local `slug`, `month_label`, day-cell packer, sitemap writer -
were deleted for the shared ones. And the immediately visible change was the point of the
exercise: this site's pages picked up the water site's contrast-checked tokens, the ones the
hand-porting had dropped - while the data files, shards and search index stayed
byte-identical to a build from `main`, which is the verification that only the wardrobe
changed (PR #3, 19 Aug 2026).

### Meanwhile, in the hall (PRs #4–#5, 19 August)

The same day, a reminder that this site has a hardware department the others do not: the
Pi's nightly backup failed with a non-fast-forward push, because a commit had been pushed to
the data repository from another machine and the Pi never fetched it - and the rejection sat
undiscovered in the systemd journal. The backup script now fetches and merges before pushing,
so divergence self-heals; and the follow-up gave the merge a committer identity, found when
the *next* failure was git refusing to commit as nobody (PRs #4–#5, 19 Aug 2026). Two
one-line fixes, each found by a real failure, each an argument for chapter 2's alerting
posture: the failure modes of an unattended machine are discovered one at a time, in
production, forever.

### The iPhone findings arrive downstream (PRs #8–#9, 20 August)

Next morning the water site's owner-with-a-phone review pass landed upstream in `statusui`,
and this site synced it in: the month-tab strip scrolls in one row instead of wrapping
toward three, day captions stop popping in on touch, the phone column spaces its own
children. Receiving it surfaced the one integration duty a consumer has: the scrolling strip
can leave the *selected* tab off-screen, so this site's `render()` now reveals it after each
render - and a second pass the same day bound the reveal to rotation, after measuring that
turning a phone from 851 px to 375 px left the selected tab entirely out of view (PR #9,
20 Aug 2026, measured on the shared component). The family dynamic in miniature: the upstream
fix is shared, the call sites are each site's own.

### One day of vendoring was enough (PR #10, 20 August)

The vendored mechanism then failed in exactly the way the water series records: a shared fix
cost a sync-test-commit-PR cycle in each of three repositories, and the sites *still*
drifted - when measured, this site and the lift site were synced to statusui `f248ac3` while
the water site's main sat five commits behind, with nothing failing to say so, because the
byte-compare drift test only fires against the checkout you happen to have beside the repo
(`notes/grading.md`, 20 Aug 2026). So `statusui` became a real package, and this site
declares it as a git dependency pinned to an exact commit in `uv.lock`; the vendored tree,
the sync script and the byte-compare went; upstream's `rollout.sh` now bumps the pin in all
three sites, runs each site's tests and opens the three pull requests in one command.

> **Concept: an empty dependency list as a deployment contract.** This repository's
> `pyproject.toml` declares **no runtime dependencies at all**, and that emptiness is
> load-bearing: the collector deploys to the Raspberry Pi by copying files onto whatever
> Python the Pi's operating system ships, with no installer, no lock file, no network. So
> when the *site* half grew a real dependency (statusui), it could not go in `dependencies`
> - it went into a separate dependency *group*, used only when building the site, with the
> default-groups configuration keeping a plain `uv run` working for developers. The pin
> updates the site's wardrobe without the Pi ever hearing about it. The water site has no such
> constraint - its pipeline always runs where packages install freely - which is why its
> version of this change was simpler. Here the family's shared layer had to be adopted
> *around* the hall machine's contract, and the contract is written at the top of the repo's
> instructions so nobody helpfully adds a dependency and breaks a Pi three counties away.

### The first real rollout (PR #11, 21 August)

The proof of the machinery came the next morning: the banner's coloured status dot - which
broke the banner text onto a second line on phones and added nothing to a sentence that
already states the numbers - was deleted once, upstream, and `rollout.sh` opened the three
pull requests. This site's share of the change: a pin bump and the removal of its own dot
markup. The water series reports the same PR from its side; +2/−4 lines there. That is what
the whole stretch was for: a design decision made once, landing everywhere, with no site able
to quietly fall behind.

## Where it left the site

Pinned to statusui `61b642c`, tests at 152, pages assembled at build from a shared layer plus
a small local stylesheet (41 lines today - the bar buckets, the layout widths, the
repeat-fault tag; measured 27 Aug 2026), and the three sites incapable of drifting silently. The wardrobe
was now shared; the *language* - what the pages actually say to a reader - still differed
site by site, and closing that gap is the next chapter.

## Notes

- PR #2 (19 Aug 2026): caption strip into the row grid, tooltips removed, touch behaviour;
  "same change as uisce #44".
- PR #3 (19 Aug 2026): statusui vendored, `assemble()`, what stayed local, deleted local
  helpers, byte-identical data files, +4 KB index; `notes/grading.md` "The design layer is
  shared…" (19 Aug): the missed contrast pass, "not always successfully".
- PRs #4–#5 (19 Aug 2026): backup fetch-and-merge; committer identity for the merge commit.
- PRs #8–#9 (20 Aug 2026): statusui `374b358` sync (month strip, touch captions, spacing,
  rounding); `revealMonthTab` on render, then on rotate (851→375 px measurement). PR #7
  (20 Aug): CI cache pruning, housekeeping.
- PR #10 (20 Aug 2026) and `notes/grading.md` "The vendored copy became a pinned dependency"
  (20 Aug): the drift (`f248ac3` vs five commits), the uv git pin, `rollout.sh`, the empty
  `dependencies` contract, `--with-editable` for trying unpushed upstream changes.
- PR #11 (21 Aug 2026): the status dot, first rollout.
- The other bank of the same days: the water series, chapter 14 (its PRs #44–#49), including
  the "assembled at build" and "vendor or pin" concept boxes restated above.
