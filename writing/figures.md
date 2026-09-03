# Figures registry

Every number quoted in a chapter gets a row here. *Source* is a PR number, a commit subject,
a `notes/` section heading, a README section, or "measured" (a read-only check run by the
writing session). Chapters quote from here rather than re-deriving. Figures are quoted as
measured on their stated date; where the corpus moved between measurements (the CI ratio, the
CML), the chapter quotes one snapshot and names it.

## Verified against the working tree: 27 Aug (S0), 31 Aug (S1), 2 Sep (S2), 3 Sep (S3)

| Figure | Value | How | Verified |
|---|---|---|---|
| Commits on `main` | 152 (144 at S2, 138 at S1, 98 at S0) | `git log --oneline \| wc -l` | Y (3 Sep) |
| Commits with a `Co-Authored-By` trailer | 95 (64 Claude Opus 5, 26 Claude Fable 5, 5 unversioned) | `git log --format='%b' \| grep -o 'Co-Authored-By: [^<]*' \| sort \| uniq -c` | Y (2 Sep) |
| Merged pull requests | numbered to #34 (#28 unused) | GitHub, `baz8080/esb` | Y (3 Sep) |
| Test count | 225 (`Ran 225 tests`; 16 skipped without `../esb-data`) | `uv run python -m unittest discover -s tests -t .` | Y (2 Sep) |
| `STALE_AFTER` | 10 hours (16 until PR #32) | `esb_site/render.py:40` | Y (3 Sep) |
| `sort_keys=True` in the raw append | present | `esb_outages/store.py:201` | Y |
| `notes/` files | grading · polling · design-alignment · area-pages (27 Aug) · publish-cadence (2 Sep) | `ls notes/` | Y (3 Sep) |
| Em dashes in `writing/` after the sweep | 0 (339 before it) | `grep` for U+2014 across `writing/`; house rule in CLAUDE.md § Punctuation | Y (31 Aug) |

## Lifted figures by chapter (source + date measured; not re-run)

### Ch 0 (intro)
| Figure | Value | Source |
|---|---|---|
| First collection pass | 21:02, 31 Jul 2026 | PR #19 body (26 Aug 2026); commit dates |
| National charter share, first month | 88.4% vs the 95% aim | `notes/grading.md` "The grade", 17 Aug 2026 |
| County grades, August 2026 | A 9 · B 6 · C 4 · D 4 · F 3 | same |
| Outages past the 24-h compensation mark | 1 | same |
| Observed feed retention, shortest | 112 minutes | README, "Deploying on a Raspberry Pi" |

### Ch 1
| Figure | Value | Source |
|---|---|---|
| The timezone proof | outage 2826455: restore 17:34 vs server clock 17:26 UTC | README, "Timestamps" |
| Standby transfer per run | ~12 KB | README, "Collecting from a second machine" |
| Storage/tables/raw+utc columns | `runs-*.jsonl`, `observations-*.jsonl`, `esb.db`; `outage` / `outage_change` / `run` | README, "Storage" |

### Ch 2
| Figure | Value | Source |
|---|---|---|
| Median outage duration, first days | 83 min; 37% under an hour; hourly caught 58% live | commit "Poll every 30 minutes and re-arm timers on install", 3 Aug 2026 |
| Dormant planned works | 9 entries = 531 of 743 detail fetches (71%), 56-h window, zero changes | commit "Back off on dormant outages…", 3 Aug 2026 |
| Back-off replay | −58% fetches (744 → 310), byte-identical change log | same |
| Coordinate noise | 34 of first 200 change rows; 5 dp ≈ 1.1 m | same |
| 30 vs 60 min table | events 1,333/1,269 (−4.8%); confirmed restores 573/288 (−49.7%); CI 1.86/1.53; 4-h share 88.4/86.1 | `notes/polling.md`, 18 Aug 2026 |
| Confirmed-restore share | 85% at 30 min, 47% at 60 | same |
| Missing at source | 66 of 69 "last listed" faults never appeared Restored | same |
| Realistic 15-min headroom | ~5% of fault durations | same |
| Log growth | 178 MiB/yr at 30 min, ~360 projected at 15 | same |
| Short-outage filter | lost ids: median 0.65 h vs 3.68 h all events; 64% < 1 h vs 13% | same |
| Chain legs under one poll | 8 of 32; shortest 9 min | same |
| Daily footprint | 45 list + 699 detail fetches | same |
| Alerting silently broken | twice | README, "Health checks" |

### Ch 3
| Figure | Value | Source |
|---|---|---|
| `startTime` revisions | 8 of 1,460 (0.5%); 2 × 1 min; range −82 to +363 min | `notes/grading.md` "Does startTime drift?", 18 Aug 2026 |
| Field-change comparison | statusMessage 639, outageType 534 | same |
| Start → first-sighting lag | faults p25 21 / median 32 / p90 147 min; planned 12/21/34; 0 negative | same |
| Live-caught faults | 593; median lag 31 min | same |
| Empty `restoreTime` | 10,542 of 11,199 detail bodies | CLAUDE.md, "Data-shape traps" |
| Planned works never restore | 0 of 675 | `notes/grading.md` "Settled" |
| End-fallback table (648 known ends) | last-listed +3.78 h, 2.26×; estimate +0.39 h, MAE 1.31 h, 1.13×; min() +0.54 h, 1.18× | `notes/grading.md` "Settled", 17 Aug 2026 |
| Roosky | began 15:15, restored 18:17, first seen 21:02 | commit "Anchor each outage's timeline…", 18 Aug 2026 |
| Timeline suppressed | 93% of outages' counts never changed | same |
| Restored-only events | 85 of 1,333 (6.4%); median 30 min vs 2.2 h; first seen +32 min | `notes/grading.md` "Outages we only ever see restored", 17 Aug 2026 |

### Ch 4a
| Figure | Value | Source |
|---|---|---|
| Bealistown, 14 Aug | Fault 2,427c; Restored 1,118 + 2,078 + 1,547 + 880 = 5,623; peak 5,623 | `notes/grading.md` "Settled", 17 Aug 2026 |
| The merge | 1,457 ids → 1,333 events; CI 1.60× → 1.35×; CML 195 → 172 | same (the 17 Aug commit's same-day corpus read 1.60× → 1.32×) |
| Coordinates-close variant | +2 merged pairs in the month | same |
| Chains | Tycor ×4 in 90 min; Boghall Road ×3; Creagh ×2 at 1,027c; 15 chains, 32 events, 5 identical-count | `notes/grading.md` "Repeat faults are not splits" |
| Chain tag rule | next start ≤ 15 min after restoration, ≤ 1 km; 36 tagged events | commit "Tag repeat faults…", 18 Aug 2026 |
| Tolerance table | 1,333 / 1,281 / 1,239 / 1,164 events; CI 1.35 / 1.33 / 1.32 / 1.30×; CML 171.6 / 169.1 / 164.2 / 162.4 | `notes/grading.md` "The merge rule was not relaxed" |
| Boundary straddles | 9 events, 1–10 km apart (Little Bray) | `notes/grading.md` "Splits across a county boundary" |

### Ch 4b
| Figure | Value | Source |
|---|---|---|
| The charter aim | restore < 4 h in 95% of cases; compensation at 24 h + each 12 h; storms exempt | Customer Charter via `notes/grading.md`, 17 Aug 2026 |
| PR5 / DAPR 2024 | unplanned CML 117.47 vs target 78.7; CI 137.86 vs 112.7 per 100; ~€50m per index; ~€37m penalties; targets −2.1%/yr; 24 storm days | DAPR 2024 / CRU PR5 via `notes/grading.md` |
| CEER context | unplanned SAIDI 9–290 min across Europe | CEER 6.1 via `notes/grading.md` |
| Grade thresholds | A ≥ 95 (the aim), B ≥ 90, C ≥ 80, D ≥ 70; ungraded < 5 faults or < 5 observed days | `notes/grading.md` "The grade" |
| Wexford | F → C under the charter grade | commit "Grade on ESB's own 4-hour standard…", 17 Aug 2026 |
| CAIDI | 92.2 vs ESB 85.1 (1.08×) | `notes/grading.md` "The customer denominator", 18 Aug 2026 |
| Customer-count bias | CI 1.33× after correction (1.38× before); ~1.3× in prose | same; "Why not CML" |
| Denominator correction | 2.4M (citation absent) → 2.5M meters; CML 176.1 → 169.0; CI 1.91 → 1.83; −4.2% | commit "Use ESB's own 2.5 million customer count…", 18 Aug 2026 |
| The 1.75 trap | 1.75 interruptions / 219 min are all-in figures | `notes/grading.md` "The 1.75 trap" |
| Small Areas | 18,919 centroids; 1,457/1,457 placed, 26 counties | commit "Vendor the Census Small Area reference data", 18 Aug 2026 |
| Grid bug | `int()` vs `floor`; 12 wrong Small Areas, 1 wrong county (Macetown); 3,000-point check, 11 → 0 disagreements | commit "Fix the placement grid…", 18 Aug 2026 |

### Ch 5
| Figure | Value | Source |
|---|---|---|
| Initial load | 34 KB at first build; 41 KB at PR #1; budget 500 KB, test-enforced | commit "Add a static status site…" / PR #1, 18 Aug 2026 |
| Day-cell rationale | 66% of county-days carried ≥ 1 fault | `notes/grading.md` "Day cells", 17 Aug 2026 |
| Bucket table | Normal < 0.05 (44%) · Minor < 0.3 (22%) · Moderate < 1.0 (19%) · Major < 3.0 (9%) · Severe ≥ 3.0 (6%) min/cust/day | same |
| Update states | 1: 779 (58.4%) · ≤2: 90.4% · ≤3: 97.3% · 4+: 36 (2.7%); coalesce 15 min | `notes/grading.md` "The update disclosure" |
| Ghost days | 17–18 Aug green for 26 counties vs horizon 16 Aug 23:00 | `notes/grading.md` "What the clock knows", 18 Aug 2026 |
| CML annualisation | 161.7 vs 176.1 (−9% from 36 h absence) | same |
| Ongoing replay | 15 of 16 Aug days had ≥ 1 fault open at 05:40; 25 on the 4th | `notes/grading.md` "An outage still listed" |
| Peak definition | 17 events with an inverted late segment; none a maximum | `notes/grading.md` "The peak is the highest count" |
| Monaghan | 15 faults claimed over a list of 14 | commit "Fix the placement grid…", 18 Aug 2026 |

### Ch 6a
| Figure | Value | Source |
|---|---|---|
| The missed pass | uisce's 18 Aug contrast pass never reached esb | `notes/grading.md` "The design layer is shared", 19 Aug 2026 |
| Vendoring cost | data files byte-identical; index +4 KB, county pages +12 KB | PR #3, 19 Aug 2026 |
| The drift | esb + lifts at statusui `f248ac3`, uisce five UI commits behind | `notes/grading.md` "The vendored copy became a pinned dependency", 20 Aug 2026 |
| Rotate bug | strip fits at 851 px (tab at x 352–439), 341 px strip at 375 px still scrolled to 0 | PR #9, 20 Aug 2026 |
| First rollout | dot deleted upstream; uisce's diff +2/−4 | PR #11, 21 Aug 2026; uisce ch 14 |
| Tests at the pin | 152 | PR #3 / PR #9 |

### Ch 6b
| Figure | Value | Source |
|---|---|---|
| National tile | "17215 days" → "47 years of customer time off supply" | PR #12, 25 Aug 2026 |
| County figure | "About 32,000 homes and businesses · estimated from Census 2022" | same |
| The false alarm | build 6 min before the push → 24.2 h vs the 24-h threshold, 25 Aug | PR #13, 26 Aug 2026 |
| Threshold arithmetic | pushes 12 h nominal / 12.5 jitter / 13.5 DST; legit max ~14 h; missed midnight 17.2–20 h; `STALE_AFTER` 16 h | same |
| Python floor | 3.9 → 3.11 (Pi bookworm ships 3.11.2); 97 ruff findings, all mechanical; CI matrix 3.11 + 3.14 | PR #16, 26 Aug 2026 |
| Banner example | "**August 2026 so far:** 978 faults and 1,122 planned outages" | `notes/design-alignment.md`, 26 Aug 2026 |
| County archive | cap 40 → 150; busiest county 234 outages/month; +3.2 KB gzipped (13.1 → 16.3) for 3.7× indexable text; no-JS text ~5k → 18.3k chars | PR #19, 26 Aug 2026 |
| July window | 3 hours ("from 31 Jul") | same |
| Meta description | 155–160 chars across 26 counties; truncation-safe ordering | PR #19 / `notes/design-alignment.md` |
| Applies-tests | 4 guards, mutation-verified; 189 tests | PR #20, 26 Aug 2026 |

### Ch 7a
| Figure | Value | Source |
|---|---|---|
| Area pages | 384 at `a/<county>/<area>.html`; `areas.html` 179 KB; initial load 56 KB | PR #21, 27 Aug 2026 |
| Codes that get a page | 904 of 3,717 | same (`model.area_has_page`, guarded against the CSV) |
| Nearby-areas card | 5 nearest by population-weighted centroid, crossing counties (Balbriggan to Stamullen, Co. Meath, 5 km) | same |
| Site size | sitemap 27 to 412 URLs; 208 tests | same |
| Search | 213 tests; 14 settlements sharing their county's name excluded from the index (follow-up) | PR #22, 27 Aug 2026 |
| County page cap removed | Cork 100.7 to 127.4 KB; 26 pages 1,767 to 1,825 KB | PR #23, 27 Aug 2026 |
| Directory rows that were plain text | 876 of 1,270 | PR #25 / `notes/area-pages.md` |

### Ch 7b
| Figure | Value | Source |
|---|---|---|
| CML tile | annualised 154 to `cml_month` 12.8 minutes per customer | PR #25, 28 Aug 2026 |
| Customer-time tile | 473,067 customer-hours (1 to 27 Aug) | same |
| The plausibility decomposition | 311,321 customers × 1.52 h mean (91 min = CAIDI); 11.4 min per customer; ESB's implied 348,655 over the window, so 1.36×, headcount 1.27× | `notes/grading.md` "Is half a million customer-hours in a month plausible?", 28 Aug 2026 |
| Concentration | 1,051 faults; median event 135 customer-hours, mean 450; top 10 = 15.8%, top 50 = 43.5%; Whitehall 23 Aug = 2.4% | same |
| Outage-row shapes | planned delisted 39.7% · fault restored 36.6% · planned scheduled 15.0% · fault delisted 6.0% · fault estimate-only 2.7% | `notes/design-alignment.md` "The outage row stopped reading like a database row", 28 Aug 2026 |
| Restore vs estimate | 69% early (median 58 min), 25% late (median 54 min), 5-minute noise floor | same |
| Planned reasons | closed set of 6 in `model.PLANNED_REASONS`; 15% carry none | same |
| County pages without JavaScript | 1,840 to 1,349 KB across 26 files (~15 KB each) | `notes/design-alignment.md` "The county page became an archive" |
| The punctuation rule | 199 em dashes and 21 en dashes across 11 files at the time it landed | PR #27, 29 Aug 2026 |
| The E band | cut at 60%; old F band held Sligo 68.0% and Longford 59.3%; 55/50/65 rejected | `notes/grading.md` "The scale grew an E", 29 Aug 2026 |
| Grade distribution, 29 Aug rebuild | A 8, B 6, C 9, D 1, E 1, F 1 (26 graded county-months) | same |
| Chip contrast upstream | B measured Lc 38.6 on dark ink against 69.2 on white | PR #29 / statusui #11 |
| At the end of the stretch | 221 tests; initial load 60.0 KB against the 500 KB budget | PR #29, 30 Aug 2026 |

### Ch 10 (closing)
Aggregates of the above; no new figures except the CAIDI restatement (92.2 vs 85.1, ch 4b),
the 0.65 h median of coarse-poll-lost ids restated as 39 minutes (ch 2), and the six-band
distribution restated from ch 7b. The August 2026 five-band split (A 9 · B 6 · C 4 · D 4 ·
F 3) is kept where it is quoted and marked as pre-E, as `notes/grading.md` does.
