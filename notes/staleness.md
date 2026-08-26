# The stale banner threshold

2026-08-26

## What happened

On the evening of 2026-08-25 the live site said "collection has stopped" while
the collector was running normally. The merge of PR #12 triggered a Pages
rebuild at 23:15Z, six minutes before the collector's nightly push landed at
23:21Z, so the build saw data whose horizon was 2026-08-24 23:03Z — 24.2 hours
old, just over the 24-hour `STALE_AFTER`. The banner then sat on the live site
until the next rebuild the following morning. The lifts site tripped the same
way the same evening; the same statusui rollout had merged to its main.

## The timing arithmetic

- The collector pushes once a day at a fixed Europe/Dublin time with up to 30
  minutes of jitter, so consecutive pushes are 23.5–24.5 hours apart, and
  25.5 hours across the October DST change.
- The site rebuilds on the 05:40Z cron *and* on every push to main. A rebuild
  can therefore run at any time of day, and one that runs late in the push
  cycle sees data legitimately up to ~24.5 hours old (25.5 on the DST night).
- If the collector genuinely misses a push, the first build to notice is the
  next 05:40Z cron run, by which point the lag is at least ~30 hours (the
  ~6.5-hour morning handover plus the missed 24-hour cycle).

So any threshold in (25.5, 30) hours separates the two cases exactly.
`STALE_AFTER` is 28 hours, the middle of that window. Detection latency for a
real failure is unchanged from 24 hours: either way, the first build past the
threshold is the same morning cron run, at ~30.5 hours of lag.

## Rejected

- **Keeping 24 hours.** It is under the push cadence itself, so any rebuild in
  the window between (previous horizon + 24h) and the next push publishes a
  false alarm — measured at 24.2h on 2026-08-25, with a six-minute miss.
- **Only rebuilding after the data push.** The push-to-main trigger exists so
  a merged fix reaches the site the same day; dropping it delays every fix by
  up to a day, and the race would survive anyway in the minutes between the
  cron's data checkout and a late push.
- **Re-fetching the data mid-build if it looks old.** Adds a moving part to
  the workflow to save at most one evening of banner, and the checkout can
  still race the push by seconds.

The lifts and uisce sites carry the same constant in their own `render.py` and
need the same change; it is per-site code, not statusui.
