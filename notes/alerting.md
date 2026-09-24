# Alerting: what the collector can say, and what only silence can

Decisions behind the collector's alarms. Dated 2026-09-06.

## The heartbeat - 2026-09-06

Every alarm the collector had was one it raised itself: a rejected key, an
unreachable feed, drifted schema, broad detail loss, an unwritable directory,
each pushed to `ESB_ALERT_WEBHOOK`. The README records alerting breaking
silently twice in the project's short life, and the failure that class of alarm
cannot report is the collector not running at all. A Pi that is off, a timer
someone disabled, a dead SD card, a lost uplink: none of them runs the code
that would send the webhook. The only signal was the stale banner on a page
nobody watches for that purpose, and it trips ten hours after the last push,
which is up to sixteen hours after the last poll.

So the collector now pings `ESB_HEARTBEAT_URL` after every run that reached
the feed, and a dead-man's monitor raises the alarm when the pings stop. The
collector sends nothing new to a human; it sends a sign of life to a machine
whose whole job is to notice its absence. Ten lines of standard library, one
GET, best effort like the webhook.

**Sent for every run that reached the feed, not only a clean one.** Schema
drift and a partial run exit non-zero and already reach the webhook, but the
list is on disk and collection is happening; going silent as well would raise a
second alarm for a collector that is running. A rejected key and an unreachable
feed send no ping, so those raise both alarms, which is right: collection has
stopped, whatever the cause. A trigger that finds the lock held sends nothing
either, because the run holding it will.

**Period 30 minutes, grace 90.** The timer fires every 30 minutes with up to
three minutes of jitter, and `Persistent=true` runs a missed trigger as soon as
the machine is back, so one missed poll is ordinary. Three in a row is not.

**Not a second webhook.** ntfy cannot alert on silence; that is a different
kind of service, and healthchecks.io's free tier is enough. The URL is the
secret, as the ntfy topic is, and lives in the same root-only file.

Rejected: pinging from `backup-to-git.sh` instead. A push every six hours is
too coarse to notice a stopped collector, and the backup can succeed with the
collector dead, which is the exact case a heartbeat exists to catch.

## A run that fails partway still says so - 2026-09-24

The only storage check was a probe before the run that creates an empty file,
which a full disk still allows: it needs an inode, not a data block. The first
real write then raised `ENOSPC` out of the run, and so did any error the code
had no handling for. Either way the run exited 1 with a traceback, sent no
webhook and no heartbeat, and the only alarm was the dead-man's monitor two
hours later, naming no cause.

`run_poll` now catches both. An `OSError`, or a SQLite error whose code is a
full disk, an I/O error, a file it cannot open or a read-only database, is the
storage alert, exit 6. Anything else, a column an older `esb.db` lacks or a
malformed file included, is a new "run crashed" alert, exit 1, with the
traceback in the journal: the storage banner's `df` and `chown` would send the
reader the wrong way.

The crash banner names `esb rebuild` for every crash, and says that a rebuild
which fails the same way, or a next run that crashes again, means the code
needs a fix: a bug in the poll's own path replays cleanly. Choosing from the
exception's type was wrong both ways: an older `esb.db` missing a column
raises `IndexError` from `sqlite3.Row`, which a rebuild fixes, and a code bug
can raise `sqlite3.ProgrammingError`, which it replays. Following the advice
blind costs nothing the raw logs cannot restore: a rebuild that fails leaves a
partial `esb.db`, and the next one that succeeds replaces it. Building into a
side file and renaming it in was tried and dropped: about 60 lines guarding a
disposable file, which four review rounds kept finding holes in.

Neither the storage alert nor the crash pings: the run stored nothing
reliable, so it joins the rejected key and the unreachable feed in raising
both alarms.
