# Working in this repository

Two things live here: `esb_outages`, a collector that snapshots ESB Networks'
PowerCheck API every 30 minutes, and `esb_site`, a static site generator that
turns the result into https://baz8080.github.io/esb. **Both run on the standard
library alone** — `pyproject.toml` declares no runtime dependencies and exists
only for ruff and the dev tooling, because the collector is installed on a
Raspberry Pi by copying files. Keep it that way.

```bash
uv run python -m esb_outages --data-dir <dir> poll      # one collection pass
uv run python -m esb_outages --data-dir <dir> rebuild   # replay JSONL into esb.db
uv run python -m esb_outages --data-dir <dir> stats
uv run python -m esb_site --data-dir <dir>              # build out/site/
uv run --group dev ruff check
uv run python -m unittest discover -s tests -t .
```

Plain `python3` works for all of these too; uv only pins the interpreter, to the
3.14 in `.python-version`. That pin is the dev and CI interpreter, not the floor:
`requires-python` says **3.11**, because that is what Raspberry Pi OS bookworm
ships and the collector has to run there. `scripts/install-native.sh` gates on
the same number, and ruff takes its target from it, so the linter will not
suggest syntax the Pi cannot run. One floor covers both halves — 3.11 already
allows everything the site uses, so splitting the two is not worth a second
config.

The collected data is a separate repository, `baz8080/esb-data`, normally
checked out at `../esb-data`. Set `ESB_DATA_DIR` to it, or pass `--data-dir`.
The site tests in `tests/test_site_national.py` skip without it, so run them
with it set before shipping anything that touches the numbers.

## The UI is shared — change it upstream

The tokens, base CSS, row/bar/card components and the JS helpers that uisce, esb and lifts
all use come from [`../statusui`](https://github.com/baz8080/statusui), a **uv git dependency
pinned in `uv.lock`** (the `site` dependency group — `dependencies` stays empty for the Pi
collector) and inlined into every page at build by `statusui.assemble()`. Edit it there,
push, then `../statusui/rollout.sh` bumps the pin in all three sites and opens the PRs. This
site's own rules are `esb_site/site.css`; the shared/per-site rule is in statusui's
CLAUDE.md.

## The invariant

**The raw JSONL logs are the source of truth. The database is disposable.**
Nothing is parsed before it is written to the log, and `rebuild` replays the
logs through the same code path a live run uses. If a parse is wrong, fix it and
rebuild; never edit the logs. `json.dumps(..., sort_keys=True)` in
`store.py:_append_raw` is load-bearing — it is what lets two machines' logs be
merged with `sort -u`.

## Data-shape traps

Every one of these has already cost someone an hour:

- **There is no county field**, no Eircode, no address. Only `point.c`, a
  `"lat,lon"` *string*, and `plannerGroup`, which is an ESB depot and not a
  county. County is derived by nearest Census Small Area centroid.
- **`restoreTime` is `""`, never null**, and is only ever set once an outage
  flips to `Restored` — 10,542 of 11,199 detail bodies have it empty.
- **`Restored` overwrites the original `outageType`.** The only record that
  something was a fault is the earliest non-`Restored` type it was seen with.
- **Planned outages never restore.** `Planned → Restored` does not occur; they
  stop being listed. Not one of 675 in the first month reported a restore time.
- **Timestamps in the body are `dd/mm/yyyy HH:MM` Europe/Dublin with no offset**;
  everything at the top level of a record is ISO UTC with a `Z`.
- **Run records may lack `status`** (86 early ones do), and an observation's
  `body` is `null` when `http_status` is 404.
- **`numCustAffected` is not constant** over an outage's life, and runs about
  1.3× the count ESB finally reports even after merging. See `notes/grading.md`.
- **One real outage is several ESB ids.** A new record is opened each time a
  fault's scope changes, sharing the location and start time of its siblings.
  `model.merge_events` folds them back; never count raw ids.

## Settled — don't re-litigate without reading the note

| Decision | Where |
|---|---|
| The grade is ESB's own 4-hour/95% charter aim, not Customer Minutes Lost | `notes/grading.md` § The grade |
| Why CML was rejected as the basis (scale bias, and a relative scale mislabels a good network) | `notes/grading.md` § Why not Customer Minutes Lost |
| One ESB event is one row: ids sharing a location and start time are merged | `notes/grading.md` § Settled |
| Planned works are excluded from the grade | `notes/grading.md` § Settled |
| The county page lists **every** outage; `COUNTY_PAGE_CASES` is gone (largest page 100.7 → 127.4 KB). A count was always a proxy for bytes — if a bound is needed again, make it a byte budget | `notes/design-alignment.md` § The copy and consistency pass (2026-08-27) |
| One name per thing: the directory is "every area with an outage", the app is "County X's interactive view", heading counts read `· N outages` (row counts stay bare) | `notes/design-alignment.md` § One name per thing (2026-08-27) |
| `base.css` resets margin, not padding, so a bare `<ul>` keeps the UA's 40px indent — `ul.areas` resets its own | `notes/design-alignment.md` § `ul.areas` was indented 40px (2026-08-27) |
| Every figure beside a month is on that month's clock: the CML tile and the county month table show `cml_month`, not the annualised rate, and say "customer minutes lost" / "Minutes lost". The annualised rate survives only in the footer paragraph that names ESB's yearly 117.47 (`compare.cml`) | `notes/design-alignment.md` § The tiles say what they mean (2026-08-28) |
| The national tiles carry no jargon — no "CML", "annualised" or "unplanned" — and the customer-time total is always in **customer-hours**: rolled into days or years, a unit named after a calendar span collides with a page organised by months, whether or not a given reader misreads it | `notes/design-alignment.md` § The tiles say what they mean (2026-08-28) |
| `c/<slug>.html` is an archive: no single-month card (its tiles duplicated the table's first row), and **no JavaScript** — 1,840 → 1,349 KB across 26 pages. Day bars are the app's alone | `notes/design-alignment.md` § The county page became an archive (2026-08-28) |
| The outage row explains itself: no floating `span.when`, the span inside the phrase it measures, "no restore time published" instead of "not confirmed", a restore compared against ESB's estimate rather than printed beside it, and the planned reason in the tag as a label (`Planned · line diversion`) | `notes/design-alignment.md` § The outage row stopped reading like a database row (2026-08-28) |
| ESB's six planned reasons are labelled in `model.PLANNED_REASONS`, in the site and **not** as a column in `esb.db` — the database is disposable, the collector captures rather than interprets, and an unmapped reason must still render. 15% carry no reason and nothing in the record distinguishes them | `notes/design-alignment.md` § The reason moved into the tag |
| The footer explains the grade, not the pipeline: the build cadence and the merge/repeat rule are out of it. The merge rule lives in `notes/grading.md`, not on the page | `notes/design-alignment.md` § What the footer stopped saying (2026-08-28) |
| Storm days are *not* excluded, and the page says so | `notes/grading.md` § Settled |
| Ending an outage on ESB's estimate rather than its last sighting | `notes/grading.md` § Settled (measured: 1.18× vs 2.26×) |
| Customer-minutes integrated over the count, not multiplied | `notes/grading.md` § Settled |
| Nearest-centroid placement, not the water site's radius footprint | `notes/grading.md` § Settled |
| Day cells coloured by magnitude, not by presence | `notes/grading.md` § Day cells |
| Updates inline to 3, disclosure at 4+ | `notes/grading.md` § The update disclosure |
| Coalescing changes within 15 minutes into one update | `notes/grading.md` § The update disclosure |
| Repeat faults stay separate rows but are tagged as a chain | `notes/grading.md` § Repeat faults are not splits |
| Poll interval stays at 30 min; 15 min was measured and is marginal | `notes/polling.md` |
| `startTime` is immutable and back-dated, so durations measure the outage | `notes/grading.md` § Does startTime drift |
| Every measured window ends at the collection horizon, not at the build clock | `notes/grading.md` § What the clock knows |
| An outage still listed at the last poll is not judged on the charter | `notes/grading.md` § An outage still listed |
| Peak customers means the most off while the outage was live | `notes/grading.md` § The peak is the highest count |
| Part-observed days keep their colour and say so in the tooltip | `notes/grading.md` § Short days say so |
| 2.5M customer denominator, and which DAPR figures are comparable | `notes/grading.md` § The customer denominator |
| The Pi pushes twice daily (midnight and noon local) and the site builds after each slot; the stale banner trips at 16h — above the widest legitimate push gap (~14h), below a missed midnight push (17h+) | `STALE_AFTER` in `esb_site/render.py` |
| The banner states the data's *age* ("Updated 17 hours ago"), not its timestamp. A healthy overnight gap is a big number, so the warning, not the wording, carries it | `freshness()` in statusui's `ui.js` |
| The exact horizon left the footer (owner call, 2026-08-26) and then the county page's header (2026-08-28); it survives only as the age chip's hover title on the index. A county page's currency signal is the month table's `to 27 Aug` caveat | `notes/design-alignment.md` § The county page became an archive |
| Banner, national heading and footer formats are aligned with uisce; the merged "How these numbers are worked out" disclosure and the "Source code · not affiliated" line are the shared shape | `notes/design-alignment.md` |
| The app's county view links to `c/<slug>.html` from its own line under the heading; the wording names the difference (one month here, every month there) rather than calling itself a permalink, and uisce says the same sentence because its page stands in the same relation to its view | `notes/design-alignment.md` § The county page got a way in from the app |
| The county page's meta description states the county's record, then names what the page holds, in that order — the page caps its list, and a snippet truncated mid-sentence must not read as an inventory | `notes/design-alignment.md` § The meta description had the same shape as the link |
| The design layer is shared with uisce and lifts via `../statusui`, a uv git dependency pinned in `uv.lock` — edit upstream, then `../statusui/rollout.sh` bumps all three sites. Vendored copies were tried first and drifted within a day. `esb_site/site.css` is this site's own | `notes/grading.md` § The vendored copy became a pinned dependency; statusui's README |
| Named areas get pages at `a/<county>/<area>.html` plus the `areas.html` directory, counting merged events, with no grade, day bar or CML at that level and no outage-count floor; "Around …" EDs and city `-rest` buckets get rows, not pages | `notes/area-pages.md` |
| The area page has no "How to read this page" disclosure (the case row explains itself now) and no rule above its two-line footer — overridden in `area.html` alone, since every other footer carries paragraphs | `notes/area-pages.md` § The area page's tail (2026-08-28) |
| Every row in `areas.html` is a link: to the area's page where it has one, to `c/<county>.html` where it does not (876 of 1,270 rows). The county page's own copy leaves them plain — there it would link at itself | `notes/area-pages.md` § The directory stopped being two-thirds unclickable |
| A search hit is an entry point, so it is a real link: an area hit goes to `a/<county>/<area>.html`, a county hit carries `c/<county>.html` in its `href` but keeps the click in the app. ESB location strings and "Around …" EDs reach no area and say "· county". The app area view was reconsidered for convergence with uisce and still declined — both sites converge on the page | `notes/area-pages.md` § Search reaches them |
| The pin is where the fault is, not who is off — area pages say "pinned near", carry the attribution disclaimer, and list the 5 nearest paged areas (pop-weighted centroids, crossing county lines) instead of pretending the attribution is exact | `notes/area-pages.md` § The pin is where the fault is |

Decisions go in `notes/`, dated, with the rejected alternatives and their
numbers. Add a row here when one closes something off — this file carries
pointers only, never the rationale, or it becomes the thing it exists to fix.

## Comments

Comments earn their place or they go. Say **why**, not what — never a paraphrase
of the line below, a heading for an obviously-named block, or an explanation of a
standard flag. What does earn a comment: a reason the obvious approach was
rejected, a dependency nothing else records, a constraint from outside the code.

One line where one will do. If the reasoning needs a paragraph it belongs in the
commit message, the PR, or `notes/` — not above the line.

## Before changing anything the site publishes

`tests/test_site_national.py` compares this pipeline against ESB's own published
CML, CI and CAIDI. It is the reason the grades are defensible. If it fails,
something moved in the model or in the feed — find out which before adjusting a
threshold to make it pass.

The 500 KB initial-load budget is enforced by `PayloadCase` and printed by every
build. It holds only because individual outages live in per-county shards and
never in `data.js`; keep them there.
