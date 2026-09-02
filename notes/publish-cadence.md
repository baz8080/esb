# Publishing: what makes the page current, and what only looked like it did

Decisions behind the collector's push slots, the site build's trigger and the
staleness threshold. Dated 2026-09-02, with the run times that settled them. The
sibling `lifts` repo carries the same note, because the same pipeline broke the
same way in both.

## The banner blamed the wrong half - 2026-09-02

The page read `Updated 22 hours ago - collection has stopped` while `esb-data`
held data from nine hours earlier. Collection had not stopped. The build had.

The wording is gone - statusui's `freshness()` no longer takes a `note` - because
it was an inference the page is in no position to make: from the browser, a build
that stopped and a collector that stopped look identical. What survives is the
age and the red, which is what `notes/design-alignment.md` already said the
warning rather than the wording was carrying.

That left the real fault, which the wording had been papering over.

## The age on the page is the age of the data, not of the build

Worth stating because it is what makes the obvious fix wrong. `freshness()`
measures from the collection horizon against the reader's clock, so rebuilding
the site later cannot make the number smaller. Moving the build into the morning
does nothing for a reader at 09:00 if the build carries yesterday's noon data
either way. Only two things move the number: pushing more often, and building
promptly after a push the site has not yet seen.

## The cron was not running when it said it would - 2026-09-02

`pages.yml` asked for `40 5` and `40 12` UTC. What GitHub actually ran, over the
week to 2026-09-01, identical here and in `lifts`:

| Cron | Actual run start, UTC |
|---|---|
| `40 5` | 10:23, 10:38, 11:46, 11:48, 13:38, 16:46, 17:40 |
| `40 12` | 16:51, 16:53, 16:56, 19:13, 22:33, 22:36 |

Four to ten hours late, every day, and the morning slot never once landed in the
morning. Before 2026-08-26, with a single `40 5` cron, runs started 05:58-06:06Z:
18 to 26 minutes late, which is the normal jitter GitHub documents. Push- and
dispatch-triggered runs are unaffected - the 2026-09-01 merge built at 21:18Z,
seconds after the push. Only `schedule` events are throttled this way.

**Retiming the cron was rejected.** A four-to-ten-hour delay cannot be aimed at a
one-hour window; picking a better cron time only moves where the miss lands.

## The build is triggered by the data landing - 2026-09-02

`esb-data` now carries `.github/workflows/build-site.yml`, which on every push
calls this repo's `pages.yml` through its existing `workflow_dispatch`. The site
rebuilds within a minute of the data arriving, and the two crons stay on as the
fallback for a dispatch that never fires.

`workflow_dispatch` rather than `repository_dispatch`: `pages.yml` already
declares the trigger, so the site repo needed no new one, and the fine-grained
token needs only **Actions: write** instead of the **Contents: write** that
`repository_dispatch` requires. The token lives in `esb-data` as
`SITE_BUILD_TOKEN`; the Pi's own credential is an SSH deploy key and cannot call
the API, so firing the dispatch from `backup-to-git.sh` would have meant putting
a second, wider credential on the Pi.

The fallback crons are `0 7` and `0 14` UTC. Actions cron has no timezone and DST
shifts Dublin by exactly one hour, so for a one-hour local target window only the
hour boundaries land inside it in both seasons: 07:00Z is 07:00 local in winter
and 08:00 in summer, 14:00Z is 14:00 and 15:00.

## Six-hourly pushes, and a threshold that can trip - 2026-09-02

`esb-backup.timer` moved from `00,12` to `00,06,12,18` local. The site is only
ever as current as the last push, so this is what caps how old the page can look.
Worst case is ~7h: a 6-hour slot, up to 30 minutes of `RandomizedDelaySec`, and
up to one 30-minute poll interval between the last poll and the push. The old
twice-daily slots put that at ~13h, which is why the page could show half a day
even when everything was working.

This is a publishing decision, not a collection one: the 30-minute poll interval
that `notes/polling.md` settles is untouched, and no observation is gained or
lost by pushing more often.

`STALE_AFTER` went from 16h to 10h to match. 16h was sized for the twice-daily
gap; under a six-hourly cadence it would only fire after more than two
consecutive pushes were missed, which is not a warning. 10h clears the ~7h
legitimate maximum with room and flags a single missed push (13h+) within a few
hours of it happening.

**Two pushes a day shifted to 07:00 and 19:00 local was rejected.** It keeps the
commit volume, and the mean age across 08:00-22:00 works out at ~5.4h against
~6.4h for the midnight/noon phase, but the peak stays at ~12h. Six-hourly gets
the mean to ~3.2h and the peak to ~7h for two more commits a day against a
repository that exists to be appended to.
