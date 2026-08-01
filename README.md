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
| `test-alert` | Send a test alert through `ESB_ALERT_WEBHOOK`. |
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

Set `ESB_ALERT_WEBHOOK` in `scripts/synology-task.sh`. An [ntfy.sh](https://ntfy.sh)
topic needs no account — pick an unguessable name and subscribe to it in the app.
Discord and Slack incoming webhooks work too.

> **Do not rely on DSM's "Send run details by email".** It is a documented dead
> end: the Control Panel test email arrives, but per-task notifications silently
> never send. This was found the hard way during deployment. Leave the
> checkboxes ticked if you like — they cost nothing — but treat the webhook as
> the real channel.

Prove it works, which takes seconds and does not interrupt collection:

```bash
docker run --rm -e ESB_ALERT_WEBHOOK="$ESB_ALERT_WEBHOOK" esb-outages:latest test-alert
```

The process exit code drives all of this: the poller exits non-zero only when
something needs a human, and pushes the same banner it prints.

| Exit | Meaning |
| --- | --- |
| 0 | Success — no email |
| 2 | **API key rejected (HTTP 401)** — collection has stopped |
| 3 | ESB API unreachable after retries |
| 4 | API response shape changed (raw data still safe) |
| 5 | A broad failure of detail fetches |
| 6 | Data directory not writable |

Deliberately *not* alerts: a per-outage 404 (the outage was purged between the
list call and its detail call — routine), and one or two isolated fetch failures.
Neither loses data, because unfinalised outages stay listed for the retention
window and are retried on the next run. Alerting on recoverable blips only trains
you to ignore the emails that matter.

Set `ESB_ALERT_WEBHOOK` for a second, independent channel if you want push
notifications as well.

## Deploying on a Synology NAS

Get the source onto the NAS and build it. If DSM has `git` (it is not present on
a stock install, but the Git Server package provides it), clone or pull into
`/volume1/docker/esb`. Otherwise rsync from a machine that has the repo:

```bash
rsync -av --exclude data --exclude .git ./ <user>@<nas>:/volume1/docker/esb/
```

```bash
sudo /usr/local/bin/docker build -t esb-outages:latest /volume1/docker/esb
```

The collected data lives in `data/` inside that directory. Keep the `--exclude
data` above, and never add `--delete` to the rsync, or a deploy would take the
history with it.

Confirm it works before scheduling anything:

```bash
docker run --rm esb-outages:latest check
```

The container runs as uid 1000 rather than root, and a bind mount takes its
ownership from the host directory. Create the data directory with matching
ownership before the first run, or the poller exits 6:

```bash
sudo mkdir -p /volume1/docker/esb/data && sudo chown -R 1000:1000 /volume1/docker/esb/data
```

`scripts/synology-task.sh` does this on every run, so the scheduled task is
self-healing; it only needs doing by hand for one-off `docker run` commands.

Then create the scheduled task: **Control Panel → Task Scheduler → Create →
Scheduled Task → User-defined script**, user **root**, schedule daily repeating
every hour, with the contents of [`scripts/synology-task.sh`](scripts/synology-task.sh)
as the script.

On the **Notification** tab, tick both *Send run details by email* and *Send run
details only when the script terminates abnormally*. This needs Control Panel →
Notification → Email to be configured first.

### Verify the alerting actually works

An untested alarm is not an alarm, and this project's whole failure mode is
silent death. Confirm a notification actually reaches your phone:

```bash
sudo bash /volume1/docker/esb/scripts/synology-task.sh
```

with `ESB_API_KEY="broken"` temporarily set in that script. Expect exit 2, the
recovery banner, and a push notification. Then remove the line and run once more
to confirm a healthy run stays silent.

## Deploying on a Raspberry Pi (or any systemd host)

The image builds natively on ARM — `python:3.12-slim` has arm64 and armv7
variants — so build it on the Pi itself and nothing else changes.

```bash
sudo usermod -aG docker $USER && newgrp docker
```

```bash
docker build -t esb-outages:latest /home/pi/esb
```

Put the webhook (and the API key, if it ever needs overriding) in
`/etc/esb-outages.env`, readable only by root:

```bash
sudo install -m 600 /dev/null /etc/esb-outages.env && echo 'ESB_ALERT_WEBHOOK=https://ntfy.sh/your-topic' | sudo tee /etc/esb-outages.env
```

Then install the units from `scripts/systemd/`:

```bash
sudo cp scripts/systemd/esb-outages.* /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now esb-outages.timer
```

A systemd timer is preferred over cron for one reason: `Persistent=true` runs a
missed trigger as soon as the machine is back. Since ESB purges outages a few
hours after restoration, a window missed during downtime is gone for good.

Check on it with `systemctl list-timers esb-outages.timer` and
`journalctl -u esb-outages.service -n 50`.

### Migrating existing data

Stop the old collector first, so you are not running two that diverge:

```bash
rsync -av nastacha@nasty:/volume1/docker/esb/data/ pi@raspberrypi:/var/lib/esb-outages/
```

Then verify the history survived the move — this rebuilds the database from the
raw logs and is the strongest check available that nothing was truncated:

```bash
docker run --rm -v /var/lib/esb-outages:/data esb-outages:latest rebuild && docker run --rm -v /var/lib/esb-outages:/data esb-outages:latest stats
```

If you do end up running both hosts for a while, the datasets can be merged:
concatenate the matching `raw/*.jsonl` files and run `rebuild`. Replay sorts runs
by start time, so interleaved logs from two collectors reconstruct correctly.

### Back up the data directory

On a NAS this was somebody else's problem. On a Pi it is yours, and an SD card
failure would destroy a dataset that cannot be re-collected at any price. Copy
`raw/` somewhere else on a schedule — it is append-only and compresses well, and
`esb.db` can always be rebuilt from it, so the raw logs alone are enough.

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
