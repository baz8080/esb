# 2. A collector in the hall
*~9 min read · pre-PR commits, 31 July – 3 August 2026 · and a measurement from 18 August*

*Where we are:* chapter 1 decided that the raw logs are the truth and the database is
disposable. This chapter is about the machine that writes those logs — how often it looks,
how it avoids wearing out its welcome, and how it announces its own death.

## The question that opened this stretch

The water site's collector is a GitHub Actions workflow: a cloud scheduler runs the pipeline
twice a day, and the series that documented it called the pattern "CI as a scheduled clerk".
That was the obvious thing to copy, and it would have been wrong here. The clerk this feed
needs makes 48 passes a day, forever, against a feed that purges restored outages within
hours — and a cloud cron is best-effort about minutes and, worse, is switched off entirely
after 60 days without a commit to its repository, a fact that would later bite this project's
*site* build (PR #1, 18 Aug 2026). A miss is not a delay here; it is data that never existed.
So the collector is a physical machine in my house: a Raspberry Pi, standard library only,
installed by copying files, running on a systemd timer.

The question of this stretch: what does it take for a machine nobody watches to be trusted
with an unrepeatable observation, every 30 minutes, for years?

## What changed

### Thirty minutes, decided by the data it had already missed

The timer first shipped hourly, with a comment suggesting 30 minutes would be better — which
is no use as a default when the analysis already pointed at 30. The first days of data
settled it: the median outage lasted 83 minutes and 37% lasted under an hour, so an hourly pass
caught only 58% of outages while they were still live — and ESB wipes the status message at
restoration, so whatever is missed live is gone permanently. The timer moved to 30 minutes
(commit "Poll every 30 minutes and re-arm timers on install", 3 Aug 2026).

The same commit fixed a quieter bug with a lesson in it: the installer re-ran `systemd`'s
reload after changing a timer, but a reload does not re-arm a timer that is already running,
so a changed schedule would silently not take effect until the next reboot. The installer
would have *looked* like it worked while changing nothing. It now restarts active timers.
systemd was chosen over plain cron for one property: `Persistent=true` runs a missed trigger
as soon as the machine is back, and with observed feed retention as short as 112 minutes, a
window missed during downtime is gone for good.

### Backing off without missing anything

By the third day the collector was being a bad citizen in a specific, measurable way. ESB
leaves planned works sitting in the feed for weeks without touching them, and the collector
was dutifully re-fetching each one's detail every pass. Analysed over the first 56 hours:
**nine stale entries accounted for 531 of 743 detail fetches — 71% — and produced zero
changes** (commit "Back off on dormant outages and stop logging coordinate noise",
3 Aug 2026).

The fix: an outage whose detail has not changed in 6 hours drops to a 6-hourly re-check. What
makes this safe is that the *list* is still fetched in full every run, and any change of an
outage's type forces an immediate detail fetch however long it has been dormant — so the
back-off can delay only a quiet outage's descriptive fields, never the news. And because
chapter 1's logs replay, the claim was tested rather than argued: re-running the real 56-hour
history with the back-off in place cut fetches by 58% (744 → 310) and produced a
**byte-identical change log**. The same commit stopped a second kind of noise at the source:
the list endpoint rounds coordinates to five decimals while the detail endpoint sends full
float precision, so `55.14151` → `55.14151191932` was being logged as the outage *moving* —
34 of the first 200 change rows. Coordinates are compared at five decimals (about 1.1 m),
which still catches real relocations, which run to tens or hundreds of metres.

### A machine that announces its own death

> **Concept: the exit code is the alerting stack.** A program tells its operating system how
> it finished with a single number: zero for success, anything else for failure. The
> collector leans on that instead of an email server or a monitoring service: every way a run
> can need a human gets its own number — 2 for "API key rejected, collection has stopped",
> 3 for "feed unreachable after retries", 4 for "the response shape changed", 6 for "cannot
> write the data directory" — and a non-zero exit also pushes one banner to a webhook
> (ntfy.sh, which needs no account: pick an unguessable topic name and subscribe to it on a
> phone). Just as important is what deliberately does *not* alert: a single outage's detail
> returning 404 (it was purged between the list call and the detail call — routine), or one
> or two isolated fetch failures. Neither loses data, because unfinalised outages stay listed
> and are retried next run. Alerting on recoverable blips only trains you to ignore the ones
> that matter.

The alert that matters most is exit 2. The feed's API key ships in the PowerCheck website's
own JavaScript — de-facto public, so it is committed to the repo and the tool works out of
the box — but ESB can rotate it at any time without notice, which would silently stop
collection dead. That is the single biggest risk to the whole project, and it is why the
README's health checklist includes `sudo esb test-alert`: in this project's short life,
alerting has silently broken twice.

Two supporting commits made the unattended machine legible. Per-run counters — how many
outages listed, fetched, skipped by the back-off — were only printed by `poll`, whose output
goes nowhere visible, so `stats` now shows the recent runs and the proportion of fetches the
back-off avoided; and those counters were being discarded by `rebuild`, so it now
reconstructs them from the logs, and a run that failed before its list call even writes a
record with a null body rather than vanishing from history (commit "Surface per-run counters
and stop losing them on rebuild", 3 Aug 2026). The same weekend, the Docker and Synology
paths were deleted outright: the collector had settled on one home, and an install path that
exists but is untested is documentation that lies (commit "Remove Docker and Synology
support", 3 Aug 2026).

### Should it be 15 minutes? Measured, and no

Two weeks later, with a real corpus to test against, the interval question was reopened
properly — in both directions at once, with one experiment: drop every second poll from the
real 16-day history, rebuild (chapter 1's replay again), and compare. What halving the rate
costs is what doubling it would roughly buy back (`notes/polling.md`, 18 Aug 2026):

| | 30 min | 60 min | change |
|---|---:|---:|---:|
| Events detected | 1,333 | 1,269 | −4.8% |
| Faults with a confirmed restore time | 573 | 288 | **−49.7%** |
| National CI (interruptions per customer) | 1.86 | 1.53 | −18.1% |
| % restored inside 4 hours | 88.4 | 86.1 | −2.7% |

The 30→60 step is brutal — half the confirmed restore times vanish — which is the argument
for never going coarser. But it is not automatically an argument for going finer, because the
curve flattens: at 30 minutes, 85% of fault events already carry a confirmed restore time. Of
the 15% that do not, 69 ended on a "last listed" guess — and for 66 of those, **the feed
never showed them as Restored at all**. ESB dropped them without ever publishing a restore
time. No poll rate fixes what is missing at source. The realistic headroom at 15 minutes is
about 5% of fault durations, against permanently doubling the growth of an archive that is
committed to git and can never be pruned — 178 MiB a year would become roughly 360. Verdict:
stay at 30.

> **Concept: the poll interval is a filter.** An outage shorter than the gap between two
> passes can begin and end unseen — it exists in the data only if ESB's own record survives
> long enough to be caught on its way out. The 96 outage ids visible at 30 minutes but lost
> at 60 had a median duration of 0.65 hours against 3.68 for all events: the interval is not
> a sampling rate, it is a *lower bound on the size of outage the site can know about*. The
> water site met the same shape of question — should it build more often, to catch
> short-lived notices? — and measured its way to the opposite resting place: past daily, its
> floor belonged to the utility's own bookkeeping, which closes cases a median of 75.7 hours
> after the crew finishes, so building faster bought freshness, not coverage. Same
> experiment, opposite bottleneck: there the utility's ledger was the filter, here the
> collector is. That is why this site polls 48 times a day from a hall and the water site
> builds twice a day from the cloud, and why neither number transfers to the other.

### Worked example: what the back-off saves

The dormancy arithmetic, with the real first-week numbers. Nine planned works sat in the feed
untouched. At 48 passes a day, fetching each one's detail every pass is 9 × 48 = 432 fetches
a day producing nothing — and measured over the first 56 hours they were 531 of 743 fetches,
or 71% of all the collector's detail traffic (commit of 3 Aug 2026). Under the back-off, a
quiet outage is checked 4 times a day instead of 48: those nine cost 36 fetches a day, a 92%
cut on the dormant set, and the replayed total fell 58% (744 → 310) with an identical change
log. Today the `stats` command reports the avoided proportion continuously — the number that
tells you the back-off is still working — and by 18 August the collector's whole footprint
was 45 list fetches and about 699 detail fetches a day (`notes/polling.md`).

## Where it left the site

Still no site — but by 3 August the collector had its final shape, and it has not needed a
collector-side change since: a 30-minute timer that survives reboots and catch-ups, a
back-off that provably loses nothing, an alerting scheme with tested wiring, logs pushing to
a git remote, and a standby procedure any laptop can run. The next fifteen days were silence:
the machine in the hall doing its job while the data accumulated toward being worth looking
at. The next chapter is what the data turned out to say — including the things the feed says
that the water site's feed never could.

## Notes

- Commit "Poll every 30 minutes and re-arm timers on install" (3 Aug 2026): 83-minute median,
  37% under an hour, 58% caught live hourly; the re-arm fix.
- Commit "Back off on dormant outages and stop logging coordinate noise" (3 Aug 2026): 9
  entries, 531/743 fetches, 58% cut (744 → 310), byte-identical replay; 34/200 coordinate-
  noise rows, 5-decimal (~1.1 m) comparison.
- Commit "Surface per-run counters and stop losing them on rebuild" (3 Aug 2026); commit
  "Remove Docker and Synology support" (3 Aug 2026).
- README: exit-code table, ntfy webhook, deliberate non-alerts, the API-key risk, "alerting
  has silently broken twice", `Persistent=true` and the 112-minute retention, standby
  collection.
- `notes/polling.md` (18 Aug 2026): the 30/60 table, 85% vs 47% confirmed, 66-of-69 missing
  at source, ~5% headroom, 178 → ~360 MiB/yr, the short-outage filter (0.65 h vs 3.68 h
  medians), 45 list / 699 detail fetches a day.
- The water site's cadence measurement: its series, chapter 7 (`closed_at` is a floor; the
  75.7-hour closure lag; twice-daily builds are for freshness).
