# esb

Long-term collector for ESB Networks (Ireland) power outage data.

ESB's PowerCheck API only shows *current* outages and purges each event a few
hours after restoration. There is no historical archive and no way to backfill,
so the only way to study Irish outages over time is to snapshot the live API on a
schedule and keep the results. That is all this does.

It is designed to run unattended for years on a Synology NAS: standard library
only, no services to keep alive, and loud failure when something breaks.

## How it works

Every hour:

1. Fetch the outage list (~20 outages on a calm day, far more during a storm).
2. Write that response to an append-only JSONL log, verbatim, before anything else.
3. Fetch the detail for each outage that is new or still changing, one second apart.
4. Fold everything into a SQLite database, recording every field that changed.

Restored outages are immutable once they carry a restore time, so they are never
re-fetched. A typical run makes only a handful of detail calls.

### Storage

```
data/
  raw/
    runs-2026-07.jsonl          # one line per run, with the list response verbatim
    observations-2026-07.jsonl  # one line per detail fetch, body verbatim
  esb.db                        # derived SQLite index
```

**The JSONL logs are the source of truth. The database is disposable.** Nothing
is ever parsed before it is written to the log, and `rebuild` replays the logs
through the exact same code path a live run uses. That means a parsing bug found
in month six can be fixed and the entire history re-derived — which is what makes
it safe to start collecting now, before knowing what questions the data will be
asked.

`esb.db` holds three tables:

- `outage` — one row per outage. Every timestamp is stored twice: `*_raw` exactly
  as ESB sent it, and `*_utc` normalised. Plus `first_seen_utc` / `last_seen_utc`
  (our own sightings, useful for measuring ESB's real purge behaviour).
- `outage_change` — every observed field change. This is the interesting table:
  it captures how a restoration estimate moved during an incident, not just where
  it ended up.
- `run` — per-run outcome and counts.

### Timestamps

ESB reports `dd/mm/yyyy HH:MM` in **Europe/Dublin local time** with no offset.
(Confirmed live: outage 2826455 reported a restore time of 17:34 while the server
clock read 17:26 UTC — as UTC that restoration would be in the future for an
already-restored outage.)

Values are converted to UTC on the way into the database. Times that fall in a
DST transition — ambiguous on the October fall-back, impossible on the March
spring-forward — are flagged with `tz_ambiguous = 1` rather than silently
trusted, and the raw string is always kept.

## Usage

```bash
python -m esb_outages --data-dir ./data poll
```

| Command | Purpose |
| --- | --- |
| `poll` | One collection pass. This is the scheduled command. |
| `check` | Verify the API key and connectivity. Writes nothing. |
| `rebuild` | Drop the database and replay it from the raw logs. |
| `stats` | Summarise what has been collected. |
| `compact` | Gzip raw logs from previous months. |

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ESB_DATA_DIR` | `/data` | Storage root |
| `ESB_API_KEY` | built-in public key | Override if ESB rotates it |
| `ESB_POLL_DELAY_MS` | `1000` | Pause between detail requests |
| `ESB_ALERT_WEBHOOK` | unset | Optional ntfy/Discord/Slack URL for failures |

### The API key

The key is de-facto public — it ships in the PowerCheck site's JavaScript — so it
is committed here and the tool works out of the box. It can be rotated by ESB at
any time without notice, which would silently stop collection. That is the single
biggest risk to this project, hence the alerting below.

## Alerting

The process exit code *is* the alerting mechanism. Synology's Task Scheduler
emails a task's output only when it exits non-zero, so no SMTP config, no
secrets, and nothing extra to keep running.

| Exit | Meaning |
| --- | --- |
| 0 | Success — no email |
| 2 | **API key rejected (HTTP 401)** — collection has stopped |
| 3 | ESB API unreachable after retries |
| 4 | API response shape changed (raw data still safe) |
| 5 | A broad failure of detail fetches |

Deliberately *not* alerts: a per-outage 404 (the outage was purged between the
list call and its detail call — routine), and one or two isolated fetch failures.
Neither loses data, because unfinalised outages stay listed for the retention
window and are retried on the next run. Alerting on recoverable blips only trains
you to ignore the emails that matter.

Set `ESB_ALERT_WEBHOOK` for a second, independent channel if you want push
notifications as well.

## Deploying on a Synology NAS

Build the image on the NAS over SSH:

```bash
git clone <this repo> /volume1/docker/esb/src && cd /volume1/docker/esb/src && docker build -t esb-outages:latest .
```

Confirm it works before scheduling anything:

```bash
docker run --rm esb-outages:latest check
```

Then create the scheduled task: **Control Panel → Task Scheduler → Create →
Scheduled Task → User-defined script**, user **root**, schedule daily repeating
every hour, with the contents of [`scripts/synology-task.sh`](scripts/synology-task.sh)
as the script.

On the **Notification** tab, tick both *Send run details by email* and *Send run
details only when the script terminates abnormally*. This needs Control Panel →
Notification → Email to be configured first.

### Verify the alerting actually works

An untested alarm is not an alarm. Run this by hand with a deliberately broken
key and confirm an email arrives:

```bash
docker run --rm -e ESB_API_KEY=definitely-not-valid esb-outages:latest check
```

That should print the recovery instructions and exit 2.

## Development

```bash
python -m unittest discover -s tests -t .
```

Tests use the standard library only and run against real API responses captured
in `tests/fixtures/`. The most important one is the rebuild round-trip in
`tests/test_rebuild.py`: it polls a synthetic history, snapshots the database,
replays it from the raw logs, and asserts the result is identical. If that ever
fails, the raw log has stopped being a sufficient source of truth.

To run the suite inside the built image (this is what catches a missing `tzdata`):

```bash
docker run --rm --entrypoint python esb-outages:latest -m unittest discover -s tests -t .
```

## Not included

No analysis, dashboards, or mapping. The dataset needs months of accumulation
before any of that is worth building.
