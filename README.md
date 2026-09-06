# esb

Long-term collector for ESB Networks (Ireland) power outage data.

ESB's PowerCheck API only shows *current* outages and purges each event a few
hours after restoration. There is no historical archive and no way to backfill,
so the only way to study Irish outages over time is to snapshot the live API on a
schedule and keep the results. That is all this does.

It is designed to run unattended for years on a small always-on machine such as
a Raspberry Pi: standard library only, nothing to keep alive between runs, and
loud failure when something breaks.

## How it works

Every 30 minutes:

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
| `ESB_DATA_DIR` | `/var/lib/esb-outages` | Storage root |
| `ESB_API_KEY` | built-in public key | Override if ESB rotates it |
| `ESB_POLL_DELAY_MS` | `1000` | Pause between detail requests |
| `ESB_ALERT_WEBHOOK` | unset | Optional ntfy/Discord/Slack URL for failures |

### The API key

The key is de-facto public — it ships in the PowerCheck site's JavaScript — so it
is committed here and the tool works out of the box. It can be rotated by ESB at
any time without notice, which would silently stop collection. That is the single
biggest risk to this project, hence the alerting below.

## Alerting

Set `ESB_ALERT_WEBHOOK` in `/etc/esb-outages.env`. An [ntfy.sh](https://ntfy.sh)
topic needs no account — pick an unguessable name and subscribe to it in the app.
Discord and Slack incoming webhooks work too.

Prove it works, which takes seconds and does not interrupt collection:

```bash
sudo esb test-alert
```

The poller exits non-zero only when something needs a human, and pushes the same
banner it prints:

| Exit | Meaning |
| --- | --- |
| 0 | Success — silent |
| 2 | **API key rejected (HTTP 401)** — collection has stopped |
| 3 | ESB API unreachable after retries |
| 4 | API response shape changed (raw data still safe) |
| 5 | A broad failure of detail fetches |
| 6 | Data directory not writable |

Deliberately *not* alerts: a per-outage 404 (the outage was purged between the
list call and its detail call — routine), and one or two isolated fetch failures.
Neither loses data, because unfinalised outages stay listed for the retention
window and are retried on the next run. Alerting on recoverable blips only trains
you to ignore the ones that matter.

## Deploying on a Raspberry Pi (or any systemd host)

The collector needs nothing but Python 3.11+ and the system timezone data.
systemd's `StateDirectory=` creates the data directory with the right owner
before every run, so there is no ownership setup to get wrong.

Clone this repo anywhere, then run the installer from your checkout:

```bash
sudo sh scripts/install-native.sh
```

The installer checks the Python version and that `Europe/Dublin` resolves,
creates an `esb` service user, installs the code to `/opt/esb-outages`, the units
from `scripts/systemd/`, and an `esb` command to `/usr/local/bin`. It is
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
- Restore from the backup, which proves it is recoverable rather than merely
  present. Counts should match the live database:

  ```bash
  git clone <your data repo> /tmp/restore-test && cd /opt/esb-outages && python3 -m esb_outages --data-dir /tmp/restore-test rebuild && python3 -m esb_outages --data-dir /tmp/restore-test stats
  ```

- **After each DST transition** (last Sunday of October and March), check
  `sudo esb stats` for a non-zero `DST-ambiguous` count. Times in the repeated
  hour of the October fall-back are recorded with `fold=0` and flagged rather
  than silently trusted; the raw strings are kept, so flagged rows can be
  revisited. A count of zero across an October transition would suggest the
  flagging is not working, not that the problem does not exist.

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

### Collecting from a second machine (power cut, or the collector is down)

A power cut takes out the collector exactly when the data is most interesting.
`Persistent=true` fires a catch-up run at boot, and restored outages stay visible
for at least ~112 minutes, so a short outage costs only the live detail — status
messages and ETA revisions, which are unrecoverable — rather than the outages
themselves. A long one loses events entirely.

Any machine that can reach the API can stand in. The collector is standard
library only, so a checkout of this repo is the entire requirement — no install,
no config, no root:

```bash
cd /path/to/this/repo && while true; do python3 -m esb_outages --data-dir ~/esb-standby poll; sleep 1800; done
```

A laptop on a phone hotspot is plenty: each run transfers roughly 12KB, so a full
day of standby collection costs well under a megabyte.

Afterwards, copy `~/esb-standby/raw/` to the collector host and merge it exactly
as under [Migrating from another host](#migrating-from-another-host). Run IDs
carry a uuid so the two machines cannot collide, `sort -u` collapses any overlap
where both were briefly running, and replay sorts runs by start time so the
interleaving reconstructs correctly.

This needs no special support because of the property the whole design rests on:
the raw JSONL is the source of truth and the database is derived. Any pile of raw
logs, from any number of machines, rebuilds into one complete database.

## The site

`esb_site` builds a static status page from the collected data and publishes it
to <https://baz8080.github.io/esb> — outage days per county, drilling into
individual outages and the updates ESB issued for each.

```bash
python -m esb_site --data-dir /var/lib/esb-outages     # writes out/site/
```

It reads `esb.db`, so run `rebuild` first if the database is stale. Counties are
derived from Census Small Area centroids, because the feed has no county field.

Every county has a CSV of its outages at `c/<county>.csv`, linked from its
page's outage history: one row per merged event, oldest first, with the columns
named in `render.CSV_COLUMNS`. It is the site's own rows, so anyone studying the
data gets what the page counts without rebuilding the database or
re-implementing the merge.

Each county-month is graded A–F on ESB Networks' own published service standard,
from the CRU-approved Customer Charter: *"our aim is to restore supply within
less than 4 hours in 95% of cases"*. A county scores on the share of its
fault-interrupted customers back inside that window. Customer Minutes Lost, the
unit the CRU's incentive uses, is reported alongside but does not set the grade —
this data reproduces ESB's durations almost exactly while counting about a third
more affected customers, which a share cancels and a total does not.

`notes/grading.md` has the derivation, the published figures it rests on, and the
measurements behind every choice; `tests/test_site_national.py` holds the
pipeline to them.
