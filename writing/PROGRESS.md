# Progress ledger

Read this first each session. Statuses: `todo` → `drafted` → `reviewed` (continuity pass by a
later session) → `final`. The whole series was drafted in one session on 27 Aug 2026 (Session
0), which also registered the figures; a later session should do the continuity/review pass
and check every `figures.md` "lifted" row it quotes against its stated source.

| Ch | Title | PRs | Status | Words |
|---|---|---|---|---|
| 00 | Ask the grid the same question (intro) | — | drafted | 1,454 |
| 01 | Write it down before you read it | pre-PR | drafted | 1,719 |
| 02 | A collector in the hall | pre-PR + polling.md | drafted | 2,002 |
| 03 | The feed that knows when it happened | #1 branch | drafted | 1,932 |
| 04a | One fault, five records | #1 branch | drafted | 1,630 |
| 04b | Grade them on their own promise | #1 branch | drafted | 2,120 |
| 05 | What the page may claim | #1 | drafted | 1,994 |
| 06a | The third site of the family | #2–#11 | drafted | 1,511 |
| 06b | Reading like one product | #12–#20 | drafted | 2,327 |
| 07 | Closing: two feeds, two sites, one discipline | — | drafted | 2,129 |

Total ~18,800 words, two SVGs (`envelope-not-sum.svg`, `horizon.svg`), one mermaid flow
(ch 1). Companion series: uisce PR #43 (`writing/` on its `writing-series` branch); its
chapters 14 and 16 narrate the same 19–26 Aug days from the water site's side, and chapters
here cite uisce chapters by number, not by URL, so links survive that PR's merge.

## Chapter summaries (3 lines each)

- **00** The water site's question grows a power sibling; the purging feed (112-min
  retention) forces collect-first-design-later. First-month answer: 88.4% vs the 95% aim,
  9 A counties, 1 outage past 24 h. AI process named once (60/98 commits co-authored).
- **01** The invariant: verbatim log before parse, DB disposable, rebuild replays the live
  path. Boxes: source of truth vs derived index; idempotent merge (sorted keys + `sort -u`).
  Example: outage 2826455 timezone proof. Contrast: uisce's upsert archive; sightings vs
  ledger. Mermaid pipeline.
- **02** The Pi vs CI; 30-min interval (83-min median, 58% caught live hourly); dormancy
  back-off (9 entries = 71% of fetches; −58%, byte-identical replay); exit-code alerting +
  ntfy; 15-min polling declined (~5% headroom vs doubling a permanent archive). Boxes: exit
  code as alerting stack; the poll interval is a filter (uisce's 75.7-h contrast).
- **03** `startTime` back-dated + immutable (8/1,460; 0 pre-listed; median lag = one poll)
  — durations measure the outage, the claim uisce could not make. Traps: restoreTime `""`,
  Restored overwrites type, 675 planned never restore. Ends bounded (2.26×/1.13×/1.18× on
  648). Roosky timeline example; 85 restored-only events. Box: a back-dated start.
- **04a** No event key in feed → merge on exact (location, start): 1,457 → 1,333, CI 1.60×
  → 1.35×. Bealistown example + envelope SVG. Chains (Tycor ×4) kept separate, tagged;
  tolerance table rejected; 9 county-straddles deliberate. Boxes: envelope not sum; a chain
  is not a split. Contrast: uisce's `reference_num` — identity given vs inferred.
- **04b** Charter grade (4-h/95% = A) replaces relative CML grade (Wexford F→C). Bias 1.3×
  cancels in a share; CAIDI 92.2 vs 85.1 validates timing; denominator 2.4M→2.5M (false
  citation, −4.2%); 1.75 trap; Census as bit part (nearest centroid, `int()`/`floor` bug,
  Macetown). Boxes: absolute vs relative; bias cancels in a share.
- **05** Payload budget (34→41 KB vs 500 KB, test-enforced); day cells by magnitude (66% of
  days had a fault; bucket table); update disclosure from measured distribution (2.7%);
  the horizon (ghost days 17–18 Aug; CML −9%; ongoing unjudged — 15/16 replayed days;
  peak defined early; short days say so; Monaghan 15/14). Box: the collection horizon +
  horizon SVG.
- **06a** statusui from the receiving end: hand-porting dropped uisce's contrast pass here;
  PR #2 receives the caption fix; PR #3 vendors; PRs #8–#9 sync the iPhone pass (tab reveal
  on render + rotate); PR #10 pins in `uv.lock` after the five-commit drift; PR #11 first
  rollout (dot). Box: empty `dependencies` as the Pi's deployment contract. Pi backup
  interlude (PRs #4–#5).
- **06b** PR #12 plain-reader pass (fmtDay promoted — esb the second user); PR #13 the
  24.2-h false alarm → twice-daily pushes, 16-h threshold (14 h legit max vs 17+ h failure);
  PR #15 reader-clock freshness, "Independent"; PR #16 the 3.11 floor; PR #18 element-by-
  element alignment (banner/heading from uisce; county rows/card from esb); PR #19 county
  archive + promise-keeping link + truncation-safe description; PR #20 applies-tests. Boxes:
  threshold sized to a cadence; ordered so truncation cannot make it false.
- **07** Question answered with dates; can-say / cannot-say lists; the 12-row side-by-side
  table + the identical column; settled-decisions table in plain language; "collect first,
  interpret later, keep the bytes"; glossary of 13 own + 3 borrowed boxes.

## Open threads

- Review pass not yet done (all chapters `drafted`); check cross-references to uisce
  chapters still hold if PR #43 renumbers anything.
- The two SVGs are functional, unpolished — an optional later pass, as in the uisce series.
- When DAPR 2025 lands (~Sep 2026), ch 4b's constants section gains a sequel; note exists in
  `notes/grading.md` "When to refresh".
- A root README pointer to `writing/` is deliberately left for the publish decision, as the
  water series did.
