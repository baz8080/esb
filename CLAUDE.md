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
3.14 in `.python-version`. The collector itself still has to run on the Pi's
Python, which `scripts/install-native.sh` gates at 3.9 — `requires-python` says
so, and ruff takes its target from it, so the linter will not suggest syntax the
Pi cannot run.

The collected data is a separate repository, `baz8080/esb-data`, normally
checked out at `../esb-data`. Set `ESB_DATA_DIR` to it, or pass `--data-dir`.
The site tests in `tests/test_site_national.py` skip without it, so run them
with it set before shipping anything that touches the numbers.

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

Decisions go in `notes/`, dated, with the rejected alternatives and their
numbers. Add a row here when one closes something off — this file carries
pointers only, never the rationale, or it becomes the thing it exists to fix.

## Before changing anything the site publishes

`tests/test_site_national.py` compares this pipeline against ESB's own published
CML, CI and CAIDI. It is the reason the grades are defensible. If it fails,
something moved in the model or in the feed — find out which before adjusting a
threshold to make it pass.

The 500 KB initial-load budget is enforced by `PayloadCase` and printed by every
build. It holds only because individual outages live in per-county shards and
never in `data.js`; keep them there.
