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
re-fetched. Outages that have gone quiet for 6 hours drop to a 6-hourly re-check:
ESB leaves planned works in the feed for weeks without touching them, and in the
first days of collection nine such entries accounted for 71% of all detail
fetches while producing not one change. Replayed over real data the back-off cuts
fetches by 58% and captures an identical change log.

This is safe because the *list* is still fetched in full every run, and any
change of outage type forces an immediate detail fetch however long that outage
has been dormant. Only a quiet outage's descriptive fields are ever delayed.

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

Docker is unnecessary here — the collector is standard library only, so it needs
nothing but Python 3.9+ and the system timezone data. Running it natively also
removes the bind-mount ownership problem entirely, since systemd's
`StateDirectory=` creates the data directory with the right owner every run.

Clone this repo anywhere, then run the installer from your checkout:

```bash
sudo sh scripts/install-native.sh
```

The installer checks the Python version and that `Europe/Dublin` resolves,
creates an `esb` service user, installs the code to `/opt/esb-outages`, the units
from `scripts/systemd/native/`, and an `esb` command to `/usr/local/bin`. It is
idempotent — re-run it after a `git pull` to deploy an update, and it re-arms the
timers so a changed schedule actually takes effect.

Then set `ESB_ALERT_WEBHOOK` in `/etc/esb-outages.env` and start it:

```bash
sudo esb test-alert && sudo esb check
```

```bash
sudo systemctl enable --now esb-outages.timer && systemctl list-timers esb-outages.timer
```

Polling is every 30 minutes. A timer beats cron for one reason: `Persistent=true`
runs a missed trigger as soon as the machine is back, and observed retention
after restoration has been as short as 112 minutes, so a window missed during
downtime is gone for good.

Docker variants of the units are in `scripts/systemd/docker/` if you prefer
that route.

### Day to day

Everything below is the `esb` command installed above, which runs the collector
as its service user with the right data directory. It needs `sudo` because the
environment file holding the webhook is root-only.

| Command | What it tells you |
| --- | --- |
| `sudo esb stats` | What has been collected, plus the recent runs and how many fetches the dormancy back-off avoided |
| `sudo esb check` | Whether the API key still works. Writes nothing |
| `sudo esb test-alert` | Whether a failure would actually reach you |
| `sudo esb rebuild` | Re-derive the database from the raw logs |
| `sudo esb compact` | Gzip previous months (skip this if backing up via git) |
| `systemctl list-timers` | When the collector and backup next run |
| `journalctl -u esb-outages.service -n 20` | What the last runs did |
| `sudo systemctl start esb-outages.service` | Run one poll right now |
| `sudo systemctl start esb-backup.service` | Push a backup right now |

Note that `journalctl` prints local time while the collector logs UTC, so a run
started at 20:30 IST appears as `19:30Z`. They are the same run.

To change the interval without editing the repo, `sudo systemctl edit
esb-outages.timer` and add — the empty first line is required, it clears the
inherited value rather than adding a second schedule:

```
[Timer]
OnCalendar=
OnCalendar=*:0/15
```

### Health checks worth doing occasionally

- `sudo esb stats` — the `detail fetches` line should show a rising proportion
  avoided as dormant planned works accumulate.
- `sudo esb test-alert` — after any change to the environment file or the units.
  Alerting has silently broken twice in this project's short life.
- `sudo esb rebuild` — proves the raw logs are still a sufficient source of
  truth. Outage and change counts must not move.

### Migrating from another host

Running both collectors for a while is safe and avoids a gap. Each writes its
own run IDs, and replay sorts runs by start time, so the logs merge cleanly.

Stop the local collector first, and **wait for any in-flight run to finish**.
Stopping the timer does not stop a service already running, and a poll takes
tens of seconds; merging underneath it will clobber whatever it was writing:

```bash
sudo systemctl stop esb-outages.timer && sudo systemctl stop esb-outages.service
```

Copy the other host's raw logs somewhere, then merge file by file:

```bash
for f in /path/to/other/raw/*.jsonl; do b=$(basename "$f"); cat "$f" /var/lib/esb-outages/raw/"$b" 2>/dev/null | sort -u > /tmp/"$b" && sudo mv /tmp/"$b" /var/lib/esb-outages/raw/"$b"; done
```

`sort -u` makes this idempotent: records are written with sorted keys, so
duplicates are byte-identical and collapse. Re-running the merge changes nothing.

Then rebuild and check the totals — outage and change counts should match the
larger source, with the run count being the sum of both:

```bash
sudo -u esb ESB_DATA_DIR=/var/lib/esb-outages python3 -m esb_outages rebuild && sudo -u esb ESB_DATA_DIR=/var/lib/esb-outages python3 -m esb_outages stats
```

### Back up the data directory

On a NAS this was somebody else's problem. On a Pi it is yours, and an SD card
failure would destroy a dataset that cannot be re-collected at any price.

Only `raw/` needs backing up. It is append-only, compresses well, and `esb.db`
rebuilds from it, so the raw logs alone are a complete backup.

`scripts/backup-to-git.sh` commits and pushes them to a git remote daily. It
needs **write** access, so this is the one part of the setup that requires
credentials.

Create a **private** repository for the data — separate from this code repo, and
private because it is scraped data whose redistribution terms are unclear.

Generate a deploy key on the collector host. A deploy key is scoped to a single
repository, unlike an account-wide token:

```bash
sudo ssh-keygen -t ed25519 -N "" -f /etc/esb-outages-deploy-key -C "esb-collector"
```

Add the **public** half (`/etc/esb-outages-deploy-key.pub`) to that repository on
GitHub under Settings → Deploy keys, with **Allow write access** ticked. Then let
the service user read the private half, and point the repo at the remote:

```bash
sudo chown esb:esb /etc/esb-outages-deploy-key && sudo chmod 600 /etc/esb-outages-deploy-key
```

```bash
cd /var/lib/esb-outages && sudo -u esb git init -b main && sudo -u esb git remote add origin git@github.com:<you>/esb-data.git
```

Verify the credential works before trusting the schedule:

```bash
sudo systemctl start esb-backup.service && journalctl -u esb-backup.service -n 20 --no-pager
```

Then enable it:

```bash
sudo cp scripts/backup-to-git.sh /usr/local/bin/esb-backup-to-git.sh && sudo chmod +x /usr/local/bin/esb-backup-to-git.sh && sudo cp scripts/systemd/esb-backup.* /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now esb-backup.timer
```

A failed push alerts through the same `ESB_ALERT_WEBHOOK`, because a backup that
silently stopped is the same failure mode as a collector that silently stopped.

Two caveats:

- **Do not run `compact` if you back up via git.** Git already compresses blobs
  and deltas append-only text well; replacing a `.jsonl` with a `.jsonl.gz`
  destroys that and churns the history for no gain.
- `esb.db` is excluded deliberately. It is a binary rewritten wholesale every
  run, so git cannot delta it, and it is derived data anyway.

Git alone is a single point of failure in the same way the SD card is. Pairing it
with a second copy on different hardware — the `rsync` below, run from the NAS —
is what makes the dataset genuinely safe:

```bash
rsync -av --delete pi@raspberrypi:/var/lib/esb-outages/raw/ /volume1/backups/esb-raw/
```

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
