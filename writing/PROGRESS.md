# Progress ledger

Read this first each session. Statuses: `todo` → `drafted` → `reviewed` (continuity pass by a
later session) → `final`.

- **Session 0 (27 Aug 2026)** drafted chapters 0 to 6b and the closing, and built `figures.md`.
- **Session 1 (31 Aug 2026)** merged `main` (PRs #21 to #29), swept every file to the repo's
  new no-em-dash rule, added chapters 7a and 7b, renumbered the closing 7 → 8, and corrected
  what those days moved: the grade scale grew an E, the county-page cap came off, and the
  commit, PR and test counts.
- **Session 2 (2 Sep 2026)** merged `main` again for PR #31, added chapter 8 and renumbered
  the closing 8 → 9. Found by a scheduled check on the open pull request rather than by a
  request, which is the intended way this ledger stays true while the PR is open.

A later session should do the continuity/review pass and check every `figures.md` "lifted" row
it quotes against its stated source.

| Ch | Title | PRs | Status | Words |
|---|---|---|---|---|
| 00 | Ask the grid the same question (intro) | - | drafted | 1,571 |
| 01 | Write it down before you read it | pre-PR | drafted | 1,757 |
| 02 | A collector in the hall | pre-PR + polling.md | drafted | 2,031 |
| 03 | The feed that knows when it happened | #1 branch | drafted | 1,964 |
| 04a | One fault, five records | #1 branch | drafted | 1,658 |
| 04b | Grade them on their own promise | #1 branch | drafted | 2,199 |
| 05 | What the page may claim | #1 | drafted | 2,045 |
| 06a | The third site of the family | #2 to #11 | drafted | 1,551 |
| 06b | Reading like one product | #12 to #20 | drafted | 2,386 |
| 07a | A page for every place | #21 to #24 | drafted | 1,953 |
| 07b | The units a reader thinks in | #25 to #29 | drafted | 2,670 |
| 08 | The month that would not start | #31 | drafted | 1,033 |
| 09 | Closing: two feeds, two sites, one discipline | - | drafted | 2,819 |

Total ~25,600 words, two SVGs (`envelope-not-sum.svg`, `horizon.svg`), one mermaid flow
(ch 1). Companion series: uisce PR #43 (`writing/` on its `writing-series` branch); its
chapters 14 and 16 narrate 19 to 26 August from the water site's side, and chapters here cite
uisce chapters by number, not by URL, so links survive that PR's merge.

## Chapter summaries (3 lines each)

- **00** The water site's question grows a power sibling; the purging feed (112-min
  retention) forces collect-first-design-later. First-month answer: 88.4% vs the 95% aim,
  9 A counties, 1 outage past 24 h. AI process named once (95 of 144 commits co-authored).
- **01** The invariant: verbatim log before parse, DB disposable, rebuild replays the live
  path. Boxes: source of truth vs derived index; idempotent merge (sorted keys + `sort -u`).
  Example: outage 2826455 timezone proof. Contrast: uisce's upsert archive; sightings vs
  ledger. Mermaid pipeline.
- **02** The Pi vs CI; 30-min interval (83-min median, 58% caught live hourly); dormancy
  back-off (9 entries = 71% of fetches; −58%, byte-identical replay); exit-code alerting +
  ntfy; 15-min polling declined (~5% headroom vs doubling a permanent archive). Boxes: exit
  code as alerting stack; the poll interval is a filter (uisce's 75.7-h contrast).
- **03** `startTime` back-dated + immutable (8/1,460; 0 pre-listed; median lag = one poll)
  - durations measure the outage, the claim uisce could not make. Traps: restoreTime `""`,
  Restored overwrites type, 675 planned never restore. Ends bounded (2.26×/1.13×/1.18× on
  648). Roosky timeline example; 85 restored-only events. Box: a back-dated start.
- **04a** No event key in feed → merge on exact (location, start): 1,457 → 1,333, CI 1.60×
  → 1.35×. Bealistown example + envelope SVG. Chains (Tycor ×4) kept separate, tagged;
  tolerance table rejected; 9 county-straddles deliberate. Boxes: envelope not sum; a chain
  is not a split. Contrast: uisce's `reference_num` - identity given vs inferred.
- **04b** Charter grade (4-h/95% = A) replaces relative CML grade (Wexford F→C). Bias 1.3×
  cancels in a share; CAIDI 92.2 vs 85.1 validates timing; denominator 2.4M→2.5M (false
  citation, −4.2%); 1.75 trap; Census as bit part (nearest centroid, `int()`/`floor` bug,
  Macetown). Boxes: absolute vs relative; bias cancels in a share. Forward ref to 7b's E.
- **05** Payload budget (34→41 KB vs 500 KB, test-enforced); day cells by magnitude (66% of
  days had a fault; bucket table); update disclosure from measured distribution (2.7%);
  the horizon (ghost days 17–18 Aug; CML −9%; ongoing unjudged - 15/16 replayed days;
  peak defined early; short days say so; Monaghan 15/14). Box: the collection horizon +
  horizon SVG.
- **06a** statusui from the receiving end: hand-porting dropped uisce's contrast pass here;
  PR #2 receives the caption fix; PR #3 vendors; PRs #8–#9 sync the iPhone pass (tab reveal
  on render + rotate); PR #10 pins in `uv.lock` after the five-commit drift; PR #11 first
  rollout (dot). Box: empty `dependencies` as the Pi's deployment contract. Pi backup
  interlude (PRs #4–#5).
- **06b** PR #12 plain-reader pass (fmtDay promoted - esb the second user); PR #13 the
  24.2-h false alarm → twice-daily pushes, 16-h threshold (14 h legit max vs 17+ h failure);
  PR #15 reader-clock freshness, "Independent"; PR #16 the 3.11 floor; PR #18 element-by-
  element alignment (banner/heading from uisce; county rows/card from esb); PR #19 county
  archive (cap 150, removed the next day in 7a) + promise-keeping link + truncation-safe
  description; PR #20 applies-tests. Boxes: threshold sized to a cadence; ordered so
  truncation cannot make it false.
- **07a** PR #21 area pages (384 + directory; the lookup was already resolving settlements
  and being discarded); attribution is the non-transferable part - the pin is the fault, so
  "pinned near", a disclaimer and a nearest-neighbours card instead of a footprint; PR #22
  search hits become real links, in-app area view declined again (both sites converge on the
  page), the stale-tab rename; PR #23 the cap comes off (Cork 100.7→127.4 KB), byte budget
  over count, `ul.areas` padding; PR #24 alphabetical. Box: attribution.
- **07b** PR #25 the units pass: annualised CML → `cml_month` 12.8, customer-years →
  customer-hours 473,067 (decomposed three ways: 311,321 × 1.52 h; 11.4 min each; 1.36× ESB),
  outage rows as sentences (five shapes; restore vs estimate 69% early), planned reason in
  the site not the DB, county page loses card/age/JS (1,840→1,349 KB); PR #26 the guard that
  would have passed by checking less; PR #27 the no-em-dash rule (and why a user-level rule
  never reached a web session); PR #29 the E band at 60% (Sligo 68.0 / Longford 59.3; no A-D
  letter moves). Box: a guard that shrinks silently.
- **08** PR #31: `month_list` walked datetimes seeded with `replace(day=1)`, so
  COLLECTION_START's 21:02:11 rode the cursor and September could not appear until its second
  day; not cosmetic, because the same list drives per-county and national stats and shard
  month-filing, so a fault on the 1st was filed nowhere. Fixed by walking (year, month), the
  shape uisce already uses. Box: a date comparison that is secretly a time comparison, tied
  back to ch 5 (both failures make the site look calmer than its data).
- **09** Question answered with dates (both scales); can-say / cannot-say lists incl.
  attribution; the 16-row side-by-side table + the identical column; settled-decisions table
  (22 rows) in plain language; "collect first, interpret later, keep the bytes"; glossary of
  16 own + 3 borrowed boxes.

## Open threads

- Review pass not yet done (all chapters `drafted`); check cross-references to uisce
  chapters still hold if PR #43 renumbers anything.
- The two SVGs are functional, unpolished - an optional later pass, as in the uisce series.
- When DAPR 2025 lands (~Sep 2026), ch 4b's constants section gains a sequel; note exists in
  `notes/grading.md` "When to refresh".
- A root README pointer to `writing/` is deliberately left for the publish decision, as the
  water series did.
- Anything landing after PR #31 needs a new chapter or an extension to an existing one; the
  repo moves roughly a pull request a day, so check `git log origin/main` before assuming the
  account is current. A chapter is owed when a merged change *contradicts* what a chapter says
  (the E band did, the county-page cap did); a passing mention suffices when it merely adds.
