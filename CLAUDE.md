# Working in this repository

Two things live here: `esb_outages`, a collector that snapshots ESB Networks'
PowerCheck API every 30 minutes, and `esb_site`, a static site generator that
turns the result into https://baz8080.github.io/esb. Standard library only, both
of them — there is no `pyproject.toml`, no virtualenv, and nothing to install.

```bash
python -m esb_outages --data-dir <dir> poll      # one collection pass
python -m esb_outages --data-dir <dir> rebuild   # replay the JSONL into esb.db
python -m esb_outages --data-dir <dir> stats
python -m esb_site --data-dir <dir>              # build out/site/
python -m unittest discover -s tests -t .
```

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
  1.6× the count ESB finally reports. See `notes/grading.md`.

## Settled — don't re-litigate without reading the note

| Decision | Where |
|---|---|
| A–F bands are ratios to the national figure, not ESB's absolute minutes | `notes/grading.md` § Why that forced a ratio-based grade |
| Planned works are excluded from the grade | `notes/grading.md` § Settled |
| Storm days are *not* excluded, and the page says so | `notes/grading.md` § Settled |
| Ending an outage on ESB's estimate rather than its last sighting | `notes/grading.md` § Settled (measured: 1.18× vs 2.26×) |
| Customer-minutes integrated over the count, not multiplied | `notes/grading.md` § Settled |
| Nearest-centroid placement, not the water site's radius footprint | `notes/grading.md` § Settled |
| Day cells coloured by magnitude, not by presence | `notes/grading.md` § Day cells |
| Updates inline to 3, disclosure at 4+ | `notes/grading.md` § The update disclosure |
| Coalescing changes within 15 minutes into one update | `notes/grading.md` § The update disclosure |

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
