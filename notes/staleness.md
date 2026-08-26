# The stale banner threshold, and the push cadence it hangs off

2026-08-26

## What happened

On the evening of 2026-08-25 the live site said "collection has stopped" while
the collector was running normally. The merge of PR #12 triggered a Pages
rebuild at 23:15Z, six minutes before the collector's nightly push landed at
23:21Z, so the build saw data whose horizon was 2026-08-24 23:03Z — 24.2 hours
old, just over the then 24-hour `STALE_AFTER`. The banner then sat on the live
site until the next rebuild the following morning. The lifts site tripped the
same way the same evening; the same statusui rollout had merged to its main.

The lesson is general: the site rebuilds on every push to main, not just on
its crons, so a rebuild can land at *any* point in the push cycle, and the
threshold must sit above the longest gap between pushes — not at it.

## The cadence

The backup timer (`scripts/systemd/esb-backup.timer`) fires at local midnight
and noon with up to 30 minutes of randomized delay. The second slot was added
after the incident above, following uisce (whose numbers are in its
`notes/data-quality.md`): it exists for publication latency only. With one
push a day the published page ran 6.5 to 30 hours behind the feed depending on
when you looked; a noon push, picked up by a 12:40Z site cron, roughly halves
that. It does nothing for data quality — the raw logs capture every poll
either way, and `startTime`/restore times come from ESB's body, not from when
we push — so the poll interval decision in `notes/polling.md` is untouched.

The site's crons (`40 5 * * *` and `40 12 * * *`) sit after each slot's
worst-case push: local midnight and noon land at 23:00/11:00 UTC in summer and
00:00/12:00 UTC in winter, plus the half-hour jitter.

## The threshold arithmetic

- Consecutive pushes are nominally 12 hours apart; jitter stretches that to
  12.5, and the October clock change to 13.5. The horizon inside a push trails
  it by up to another half-poll, so a build racing the next push can see data
  legitimately ~14 hours old.
- If the collector dies, the first build that *can* know is the next cron
  after a missed slot. A missed noon push shows ~14–15 hours of lag at the
  12:40Z build — indistinguishable from the legitimate maximum, so a single
  missed slot is deliberately not flagged. A missed midnight push shows
  17.2–20 hours at the morning cron, and a fully dead collector only grows
  from there.

So any threshold in (14, 17.2) hours separates "unlucky build timing" from
"the midnight push did not come". `STALE_AFTER` is 16 hours. A dead collector
is flagged by the first morning build after it stops, the same detection
latency the old daily cadence had.

## Rejected

- **24 hours (the original).** Under the daily cadence it was *below* the
  push interval itself, so any rebuild in the window between (previous
  horizon + 24h) and the next push published a false alarm — measured at
  24.2h on 2026-08-25, with a six-minute miss.
- **28 hours with the daily cadence.** Correct for one push a day (legit max
  ~25.5h, real miss 30h+ by the morning build) and briefly adopted, but the
  twice-daily cadence dominates it: same false-alarm immunity, half the
  reader-facing lag, and a real failure flagged up to 13 hours sooner.
- **Only rebuilding after the data push.** The push-to-main trigger exists so
  a merged fix reaches the site the same day; dropping it delays every fix,
  and the race would survive anyway in the minutes between a cron's data
  checkout and a late push.
- **Re-fetching the data mid-build if it looks old.** Adds a moving part to
  the workflow to save at most one cycle of banner, and the checkout can
  still race the push by seconds.
- **Flagging a single missed slot.** Would need a threshold inside the
  (14, 14.2) sliver — no margin. The noon slot is a latency optimization;
  its failure mode is caught six hours later by the midnight arithmetic.

Deploying the cadence: the timer file only takes effect on the Pi after
`scripts/install-native.sh` runs there (it restarts a live timer on a schedule
change). Until then the extra 12:40Z site cron rebuilds the same data —
harmless. The lifts site carries the same 24-hour constant in its own
`render.py` and the same daily timer, and needs the same treatment; it is
per-site code, not statusui.
