"""Turning the outage database into per-county, per-month statistics.

The unit of measurement here is the one Irish electricity is actually regulated
in: **Customer Minutes Lost** (CML), the minutes an average customer spends
without supply. ESB Networks reports it annually, the CRU sets an incentivised
target for it, and money changes hands over the gap. That gives this site
something the sibling water site never had - a scale it did not have to invent.

See notes/grading.md for the published figures the grade bands sit on, and
notes/site-methodology.md for what these numbers can and cannot mean.
"""

from __future__ import annotations

import csv
import math
import sqlite3
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

DATA_DIR = Path(__file__).parent / "data"
SA_POP_PATH = DATA_DIR / "sa_pop.csv"
SA_TOWNS_PATH = DATA_DIR / "sa_towns.csv"

# The first poll landed at 2026-07-31T21:02:11Z. ESB's API only ever shows
# current outages and purges them a few hours after restoration, so nothing
# before this instant exists anywhere and no amount of later work can recover
# it. Days before it are rendered as "no data", never as "no outages".
COLLECTION_START = datetime(2026, 7, 31, 21, 2, 11, tzinfo=UTC)

# The denominator for CML and CI. Both figures ESB publishes point at the same
# number: the Distribution System Statistics in DAPR 2024 give "c. 2.5 million
# customer meters", and the company page says "roughly 2.5 million customers
# connected" (https://www.esbnetworks.ie/about-us/company).
#
# This was 2.4 million, on a "almost 2.4 million domestic, commercial and
# industrial customers" attributed to the same report. That string does not
# appear anywhere in DAPR 2024 - the only customer count in it is the 2.5
# million above - so the lower figure was carrying a citation it did not have.
#
# It is a meter count rather than a headcount, and ESB does not publish the
# denominator it divides by, so this cannot be exact. It is the closest thing
# ESB states, which makes it the most defensible choice: every figure here that
# is compared against ESB's own has to be built the way ESB builds it.
NATIONAL_CUSTOMERS = 2_500_000

MINUTES_PER_YEAR = 365.0 * 24 * 60

# --- Published reference points ---------------------------------------------
# ESB Networks 2024, unplanned and excluding storm days, quoted verbatim from
# DAPR 2024: "these targets were set at 78.7 CML and 112.7 CI. Our performance
# against these unplanned outage targets stood at 117.47 CML and 137.86 CI for
# 2024" - CI per 100 customers, so 1.3786 per customer.
#
# Do not "correct" these against the 1.75 and 219 that appear in the same
# report's summary bullets. Those are the all-in figures - planned and unplanned
# together, storm days included - and pairing one of them with an unplanned
# number here would compare two different populations.
#
# DAPR 2024 was issued September 2025 and is the newest published; DAPR 2025 is
# due around September 2026. Reported on the page for comparison; see
# notes/grading.md for why they do not set the grade.
ESB_CRU_TARGET_CML = 78.7
ESB_NATIONAL_CML = 117.47
ESB_NATIONAL_CI = 1.38

# --- Grade bands ------------------------------------------------------------
# The grade is ESB Networks' own published service standard, from the Customer
# Charter the CRU approves: "our aim is to restore supply within less than
# 4 hours in 95% of cases". A county is measured on the share of its
# fault-interrupted customers who got supply back inside that window.
#
# This replaced a grade built on Customer Minutes Lost, for two reasons. It is
# an *absolute* standard, so a letter means "measured against what ESB promises"
# rather than "compared with the other counties", and a relative scale hands out
# an F for being three times the national average even when the national average
# is good. And because it is a proportion of customers rather than a count of
# them, the one known bias in this data - PowerCheck reports the customers on the
# affected section, which runs above the number ESB settles on - appears in the
# numerator and the denominator alike and cancels out.
CHARTER_TARGET_HOURS = 4.0
CHARTER_TARGET_SHARE = 95.0
# The charter's other number: past this, compensation is due, and it is the
# point at which an outage stops being an inconvenience.
CHARTER_COMPENSATION_HOURS = 24.0

GRADE_BANDS = (("A", 95.0), ("B", 90.0), ("C", 80.0), ("D", 70.0), ("E", 60.0))

# A month needs this many observed days, and this many faults, before its grade
# means anything: a county with three outages can swing two bands on one of them.
MIN_GRADED_DAYS = 5
MIN_GRADED_FAULTS = 5

# --- Day cells --------------------------------------------------------------
# Fault minutes lost per customer, for one county on one day. Bucketing by
# magnitude rather than by presence is deliberate: 66% of county-days in the
# first month carried at least one fault, so a bar coloured for "an outage
# happened" would be a near-solid wall that told a reader nothing. These cuts
# are absolute and fixed, unlike the grade, so that a day's colour never changes
# under it once published. Over the first month they split the county-days
# 44/22/19/9/6, which is the shape a status bar wants: mostly calm, with real
# variation left visible.
DAY_BUCKETS = ((0.05, 0), (0.3, 1), (1.0, 2), (3.0, 3))
DAY_SEVERE = 4
DAY_PLANNED = 5  # planned works, and no fault worth colouring
DAY_NO_DATA = 8  # outside the window the collector actually covered
DAY_FUTURE = 9

# Fields whose changes a reader would recognise as an update to their outage.
# `status_message` is excluded on purpose: it has only five distinct values in
# the whole corpus and its whitespace is unstable, which makes it the single
# most-"changed" field while carrying no news. `point` is excluded for the same
# kind of reason - coordinates get refined as crews narrow a fault down, which
# is real work but not an update anyone is waiting for.
READER_FIELDS = (
    "outage_type",
    "num_cust_affected",
    "start_time_utc",
    "est_restore_time_utc",
    "restore_time_utc",
    "location",
)

# At or below this many distinct reader-visible states, every update is shown
# inline. 97.9% of outages in the first month sat here, so the disclosure below
# is a genuine exception rather than a default that hides the story.
INLINE_UPDATES = 3

# Changes closer together than this came from the same 30-minute poll cycle.
COALESCE_WINDOW = timedelta(minutes=15)
# One poll cycle plus the timer's jitter, used to decide whether two records
# ending at different times ended at the same moment as far as we can tell.
POLL_INTERVAL = timedelta(minutes=35)

# A fault returning to the same spot within this long of being restored is a
# repeat, not a coincidence. Fifteen minutes is where the observed gaps cluster:
# of 63 sequential same-location pairs, the median gap is 15 minutes and a
# quarter are under 5. Tycor failed four times in 90 minutes, each leg starting
# within a minute of the last restoration.
REPEAT_WINDOW = timedelta(minutes=15)
REPEAT_RADIUS_KM = 1.0


def parse_utc(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def month_bounds(ym):
    year, month = int(ym[:4]), int(ym[5:7])
    lo = datetime(year, month, 1, tzinfo=UTC)
    hi = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=UTC)
    return lo, hi


def month_list(start, end):
    """Every month from start's to end's, inclusive.

    Walked as (year, month) rather than as datetimes: COLLECTION_START is the
    first poll's exact instant, and a cursor carrying its 21:02 clock time hid
    each new month until its first evening.
    """
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = year + (month == 12), month % 12 + 1
    return months


def km(lat1, lon1, lat2, lon2):
    """The one statement of the 111-km-per-degree arithmetic, so placement,
    repeat chains and the nearby-areas card cannot disagree about "near"."""
    return math.hypot(
        (lat1 - lat2) * 111.0,
        (lon1 - lon2) * 111.0 * math.cos(math.radians(lat1)),
    )


def merge(intervals):
    """Union overlapping [start, end) pairs. Lifted from the uisce generator."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def grade(share_within_target):
    """A-F from the share of fault-interrupted customers back inside 4 hours.

    Graded off the raw share, never the rounded one the page prints: a county
    sitting a thousandth under a cut should keep the letter its arithmetic
    earned rather than lose it to one decimal place of display.
    """
    if share_within_target is None:
        return None
    for letter, floor in GRADE_BANDS:
        if share_within_target >= floor:
            return letter
    return "F"


def day_bucket(fault_minutes_per_customer, has_planned):
    if fault_minutes_per_customer > 0:
        for ceiling, code in DAY_BUCKETS:
            if fault_minutes_per_customer < ceiling:
                # A day whose faults were too small to colour still shows its
                # planned works rather than reading as untouched.
                return DAY_PLANNED if code == 0 and has_planned else code
        return DAY_SEVERE
    return DAY_PLANNED if has_planned else 0


class SmallAreaIndex:
    """Census Small Area centroids, grid-hashed, for point -> area lookups.

    Ported from the uisce site generator, with the radius-and-footprint logic
    dropped. ESB publishes a point per outage rather than a service area, so the
    nearest centroid is the honest answer and the extra machinery would only
    spread one pin over neighbours it was never claimed to affect. In the first
    month this placed 1,457 of 1,457 outages across all 26 counties.
    """

    BIN = 0.01  # degrees, about 1.1 km of latitude

    def __init__(self, rows):
        self._bins = defaultdict(list)
        self._cache = {}
        self.county_pop = defaultdict(int)
        self.town_pop = defaultdict(int)
        sums = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0])
        for lat, lon, county, code, town, pop in rows:
            # math.floor, not int: Irish longitudes are negative and int()
            # truncates towards zero, so int() here against the floor() in
            # `place` files every centroid one bin east of where it is sought.
            self._bins[
                (math.floor(lat / self.BIN), math.floor(lon / self.BIN))
            ].append((lat, lon, county, code, town))
            self.county_pop[county] += pop
            self.town_pop[code] += pop
            s = sums[code]
            s[0] += lat * pop
            s[1] += lon * pop
            s[2] += lat
            s[3] += lon
            s[4] += 1
        # Pop-weighted: "near" means near an area's people. A zero-pop code
        # (none in the shipped CSV) falls back to the plain mean, not a crash.
        self.centroids = {}
        for code, (wlat, wlon, plat, plon, n) in sums.items():
            pop = self.town_pop[code]
            self.centroids[code] = (
                (wlat / pop, wlon / pop) if pop else (plat / n, plon / n)
            )
        self.counties = sorted(self.county_pop)
        national = sum(self.county_pop.values())
        # ESB publishes no per-county customer count, so customers are
        # apportioned by Census population share. It is the one real
        # approximation in the chain, and it is a good one: the national CML it
        # produces lands within 1.3% of ESB's own published figure.
        self.customers = {
            c: NATIONAL_CUSTOMERS * p / national for c, p in self.county_pop.items()
        }

    @classmethod
    def load(cls, pop_path=SA_POP_PATH, towns_path=SA_TOWNS_PATH):
        places = {}
        with open(towns_path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                places[r["guid"]] = (r["town_county"], r["town_code"], r["town_name"])
        rows = []
        with open(pop_path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                place = places.get(r["guid"])
                if place:
                    rows.append(
                        (float(r["lat"]), float(r["lon"]), *place, int(r["pop"]))
                    )
        return cls(rows)

    def place(self, lat, lon):
        """Nearest Small Area's (county, area code, town), or None if implausibly far."""
        key = (round(lat, 4), round(lon, 4))
        if key in self._cache:
            return self._cache[key]
        by, bx = math.floor(lat / self.BIN), math.floor(lon / self.BIN)
        km_per_bin = self.BIN * 111.0 * math.cos(math.radians(lat))
        best, best_d = None, float("inf")
        for ring in range(0, 40):
            for dy in range(-ring, ring + 1):
                for dx in range(-ring, ring + 1):
                    if max(abs(dy), abs(dx)) != ring:
                        continue  # only the cells this ring adds
                    for slat, slon, county, code, town in self._bins.get(
                        (by + dy, bx + dx), ()
                    ):
                        d = km(lat, lon, slat, slon)
                        if d < best_d:
                            best, best_d = (county, code, town), d
            # Every bin within `ring` of the target has now been read, so any
            # centroid still unseen is at least that many bins away. Once the
            # best hit is closer than that floor, no further ring can beat it -
            # stopping at the first hit instead would sometimes pick a centroid
            # in the wrong county.
            if best is not None and best_d <= ring * km_per_bin:
                break
        # Anything this far from an inhabited Small Area is off the island -
        # a coordinate typo, or Northern Ireland, which ESB Networks does not
        # serve and this site does not cover.
        result = best if best_d <= 25.0 else None
        self._cache[key] = result
        return result


def area_has_page(code):
    """Whether an area names a place a reader could search for.

    uisce's rule: "Around ..." EDs and city "-rest" remainders are buckets,
    not places, and near-identical pages for them is scaled thin content.
    Deliberately no outage-count floor - a permalink that comes and goes is
    worse than a short one. Rationale and numbers in notes/area-pages.md.
    """
    return not code.startswith("ed:") and not code.endswith("-rest")


class Update(NamedTuple):
    at: datetime
    kind: str  # "Fault" | "Planned" | "Restored"
    customers: int | None
    start: str | None
    est_restore: str | None
    restore: str | None
    location: str | None


def timeline(start, end, end_src, segments):
    """The outage's own story, anchored on the times ESB reports.

    The observation log this is built from is our polling chronology, not the
    outage's: an outage that began at 15:15 and was restored at 18:17 can first
    be seen at 21:02, and rendering that log directly made a three-hour outage
    read as a single event at nine at night. ESB's own `startTime` and
    `restoreTime` are exact and always present, so they anchor the timeline and
    the observations only fill in what happened between them - the customer
    count falling as crews work, which is the one thing no ESB field records.

    The middle rows come from the customer-count segments rather than the raw
    observations, because for an outage assembled from several ESB records the
    segment boundaries are ESB's own restore times and the observations are only
    when we happened to look.

    Returns (kind, when, customers) rows, where kind is "began", "update", or
    one of the end sources.
    """
    rows = [("began", start, segments[0][2] if segments else None)]
    seen = rows[0][2]
    for seg_start, _, customers in segments[1:]:
        if start < seg_start < end and customers != seen:
            rows.append(("update", seg_start, customers))
            seen = customers
    rows.append((end_src, end, None))
    return rows


def label_repeats(events):
    """Mark faults that struck the same spot again shortly after being restored.

    These are not the same event recorded twice - they are separate
    interruptions, and ESB's own CI index counts each one - so they stay as
    separate rows. But a reader looking at three consecutive rows for Boghall
    Road has no way to see that it is one spot failing repeatedly, which is the
    most interesting thing about it. Each leg is tagged with its position in the
    chain so the page can say so.
    """
    by_place = defaultdict(list)
    for o in events:
        if not o.planned:
            by_place[(o.county, o.location)].append(o)

    chains = {}
    for group in by_place.values():
        group.sort(key=lambda o: o.start)
        run = [group[0]]
        for prev, cur in zip(group, group[1:], strict=False):
            gap = (cur.start - prev.end).total_seconds()
            if 0 <= gap <= REPEAT_WINDOW.total_seconds() and _near(prev, cur):
                run.append(cur)
            else:
                _tag(run, chains)
                run = [cur]
        _tag(run, chains)

    if not chains:
        return events
    return [o._replace(chain=chains.get(o.id, ())) for o in events]


def _near(a, b):
    if None in (a.lat, a.lon, b.lat, b.lon):
        return True
    return km(a.lat, a.lon, b.lat, b.lon) <= REPEAT_RADIUS_KM


def _tag(run, chains):
    if len(run) < 2:
        return
    for i, o in enumerate(run):
        chains[o.id] = (i + 1, len(run))


def merge_events(outages):
    """Fold the several IDs ESB issues for one outage back into one event.

    ESB's system opens a new outage record each time a fault's scope changes, so
    a single event arrives as a family of IDs sharing a location and a start
    time. Bealistown on 14 August was five: a Fault at 2,427 customers and four
    Restored records at 1,118, 2,078, 1,547 and 880 as the sections came back.
    Left alone they read as five separate outages on the page, and their
    customer counts sum to 5,623 for an event that never took out more than
    2,427 - which was inflating every count on the site.

    Members are matched on an identical location string and an identical start
    time. Requiring the coordinates to be close as well was tried and changed
    almost nothing (two extra pairs in the first month), so the simpler rule
    stands. 1,457 IDs collapse to 1,321 events.
    """
    groups = defaultdict(list)
    for o in outages:
        groups[(o.county, o.location, o.start, o.planned)].append(o)
    return sorted(
        (_merge_group(members) for members in groups.values()),
        key=lambda o: o.start,
    )


def _merge_group(members):
    if len(members) == 1:
        return members[0]
    lead = max(members, key=lambda o: o.customers)
    start = lead.start
    confirmed = [o.end for o in members if o.end_src == "restored"]
    others = [o.end for o in members if o.end_src != "restored"]
    if confirmed and (not others or max(others) <= max(confirmed) + POLL_INTERVAL):
        # Every section has a confirmed restore time, and nothing outlasts them
        # by more than a poll cycle. A record lingering a minute past the last
        # restoration is the feed catching up, not the outage continuing, and
        # taking the latest end regardless would downgrade a confirmed end to a
        # guess over that minute.
        ender = max(
            (o for o in members if o.end_src == "restored"), key=lambda o: o.end
        )
    else:
        ender = max(members, key=lambda o: o.end)
    end, end_src = ender.end, ender.end_src
    # The ender decides whether the event is over, for the same reason it
    # decides when: a sibling lingering a minute past a confirmed restore is
    # the feed catching up. any() over the members made such an event both
    # "restored" and "still out", and kept it out of the grade for one build.
    ongoing = ender.ongoing
    # ESB revises its estimate as sections come back, so the estimate the event
    # ended on is the one carried by the record that ended it. Taking max()
    # over the group instead can resurrect a stale figure from a sibling that
    # closed early, after ESB had already revised it down.
    est = ender.est
    if ongoing and est is None:
        # That risk is about records that closed. A live event's reader wants
        # the latest time ESB has named for any part of it, and "no estimate
        # published" would be false while a sibling carries one.
        est = max((o.est for o in members if o.est), default=None)

    # Customers off at any instant is the envelope over the members, not their
    # sum: each record describes part of the same event, and adding them counts
    # the same customer once per record. The envelope decays as sections return,
    # which is the shape the underlying restoration actually has.
    bounds = sorted({b for o in members for seg in o.segments for b in seg[:2]})
    segments = []
    for a, b in zip(bounds, bounds[1:], strict=False):
        n = max(
            (c for o in members for (s, e, c) in o.segments if s <= a and e >= b),
            default=0,
        )
        if n and (not segments or segments[-1][2] != n):
            segments.append((a, b, n))
        elif n:
            segments[-1] = (segments[-1][0], b, n)

    segments = segments or lead.segments
    return lead._replace(
        ids=sorted((i for o in members for i in o.ids), key=int),
        start=start,
        end=end,
        end_src=end_src,
        restored=all(o.restored for o in members),
        ongoing=ongoing,
        est=est,
        customers=max(c for _, _, c in segments),
        updates=_envelope_updates(members, segments, end, end_src, lead.planned),
        segments=segments,
    )


def _envelope_updates(members, segments, end, end_src, planned):
    """One timeline for the whole event, in customers still off.

    Concatenating the members' own updates produces a run of near-identical
    lines - Bealistown gave four "Restored" entries in the same minute, one per
    section - which tells a reader nothing about what was happening. Reporting
    the envelope instead says the thing they want: how many customers were still
    without supply at each point, falling as sections came back.
    """
    times = []
    for at in sorted({u.at for o in members for u in o.updates}):
        if times and at - times[-1] <= COALESCE_WINDOW:
            times[-1] = at
        else:
            times.append(at)

    kind = "Planned" if planned else "Fault"
    updates = []
    for at in times:
        off = max((c for s, e, c in segments if s <= at < e), default=0)
        u = Update(
            at=at,
            kind=kind if off else "Restored",
            customers=off or None,
            start=None,
            est_restore=None,
            restore=(
                end.strftime("%Y-%m-%dT%H:%M:%SZ")
                if not off and end_src == "restored"
                else None
            ),
            location=None,
        )
        if not updates or u[1:] != updates[-1][1:]:
            updates.append(u)
    return updates


class Outage(NamedTuple):
    id: str
    ids: list  # every ESB outage id folded into this event
    county: str
    town: str
    # the town's stable census key, which the per-area pages group on
    town_code: str
    location: str
    planned: bool
    customers: int  # peak reported, which is what an interruption count wants
    start: datetime | None
    end: datetime | None
    # Where the end time came from, because the three are not equally trustworthy:
    # "restored" is ESB's own restoreTime, "estimated" its published restore
    # estimate, "listed" the last time the outage was still in the feed.
    end_src: str
    restored: bool
    # Still listed when the collector last looked, so the time it has been out
    # is a floor rather than a length and there is nothing to judge it against.
    ongoing: bool
    reason: str
    lat: float
    lon: float
    # (position, length) when this outage is one leg of a repeat chain - the
    # same spot failing again shortly after being restored.
    chain: tuple
    updates: list
    segments: list  # (start, end, customers), the count as it changed over time
    # ESB's published restore estimate, kept alongside the end rather than
    # collapsed into it: the pages show the estimate and the actual restore.
    est: datetime | None = None

    @property
    def end_known(self):
        return self.end_src == "restored"

    @property
    def minutes(self):
        if not self.start or not self.end or self.end <= self.start:
            return 0.0
        return (self.end - self.start).total_seconds() / 60.0

    def customer_minutes(self, lo, hi):
        """Customer-minutes accrued inside [lo, hi).

        Integrated over the reported customer count rather than multiplying one
        count by the whole duration, because the count is not constant: crews
        restore an outage in sections and ESB revises the figure down as they
        go, so a single outage can start at 83 customers and finish at 19.
        """
        total = 0.0
        for seg_start, seg_end, customers in self.segments:
            start, end = max(seg_start, lo), min(seg_end, hi)
            if end > start:
                total += customers * (end - start).total_seconds() / 60.0
        return total


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _timelines(conn):
    """Reconstruct each outage's reader-visible states from the change log.

    The `outage` table holds only the latest state, so the history is recovered
    by rolling each tracked field back through `outage_change.old_value` to get
    the state at first sighting, then replaying the changes forward. The change
    log stores everything as text; that is fine, because these values are only
    ever rendered.
    """
    changes = defaultdict(list)
    for row in conn.execute(
        "SELECT outage_id, observed_at_utc, field, old_value, new_value"
        " FROM outage_change WHERE field IN ({})"
        " ORDER BY outage_id, observed_at_utc, id".format(
            ",".join("?" * len(READER_FIELDS))
        ),
        READER_FIELDS,
    ):
        changes[row["outage_id"]].append(row)
    return changes


def _build_updates(row, rows_changes):
    initial = {f: None if row[f] is None else str(row[f]) for f in READER_FIELDS}
    # Walk backwards so the earliest change for each field wins the rollback.
    for ch in reversed(rows_changes):
        initial[ch["field"]] = ch["old_value"]

    def snapshot(at, state):
        return Update(
            at=at,
            kind=state["outage_type"] or "",
            customers=_int(state["num_cust_affected"]),
            start=state["start_time_utc"],
            est_restore=state["est_restore_time_utc"],
            restore=state["restore_time_utc"],
            location=state["location"],
        )

    state = dict(initial)
    updates = [snapshot(parse_utc(row["first_seen_utc"]), state)]
    for ch in rows_changes:
        state[ch["field"]] = ch["new_value"]
        at = parse_utc(ch["observed_at_utc"])
        # One poll cycle is one update. The list response and the detail fetch
        # inside a single run land seconds apart and record their changes
        # separately, so a plain Fault -> Restored transition would otherwise
        # read as two updates a few seconds apart. Polls are 30 minutes apart,
        # so anything closer together than COALESCE_MINUTES came from one run.
        if updates and (at - updates[-1].at) <= COALESCE_WINDOW:
            updates[-1] = snapshot(max(at, updates[-1].at), state)
        else:
            updates.append(snapshot(at, state))
    # Collapse any consecutive states the rollback left identical (a field can
    # change and change back within one observation).
    deduped = [updates[0]]
    for u in updates[1:]:
        if u[1:] != deduped[-1][1:]:
            deduped.append(u)
    return deduped


def observed_until(conn):
    """The last instant the collector is known to have looked at the feed.

    Taken from the run log rather than from the outages, because a poll that
    listed nothing still observed that nothing was happening, and taken from
    runs that reached the API - `n_listed` is null when a run died on auth or
    could not connect, and a run that saw nothing saw nothing.

    This is deliberately not `now`. The build clock keeps moving whether or not
    the Raspberry Pi is still collecting, and a site that treats "no data" as
    "no outages" publishes a clean bill of health for days nobody watched.
    Falls back to the last sighting, and then to None for a caller to resolve.
    """
    row = conn.execute(
        "SELECT MAX(started_at_utc) AS t FROM run WHERE n_listed IS NOT NULL"
    ).fetchone()
    if row and row["t"]:
        return parse_utc(row["t"])
    row = conn.execute("SELECT MAX(last_seen_utc) AS t FROM outage").fetchone()
    return parse_utc(row["t"]) if row and row["t"] else None


def load_outages(db_path, sa_index, now):
    """Read every outage that can be placed and timed, newest state first.

    Returns the outages, the count that could not be placed, and the instant the
    collected data reaches - every window in this module ends at that horizon
    rather than at `now`, which is only ever used to decide what is in the
    future.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        until = observed_until(conn) or now
        changes = _timelines(conn)
        outages, unplaced = [], 0
        for row in conn.execute(
            "SELECT * FROM outage WHERE has_detail = 1 AND lat IS NOT NULL"
            " AND start_time_utc IS NOT NULL ORDER BY start_time_utc"
        ):
            place = sa_index.place(row["lat"], row["lon"])
            if place is None:
                unplaced += 1
                continue
            county, town_code, town = place
            updates = _build_updates(row, changes.get(row["outage_id"], []))

            # `Restored` overwrites whatever the outage was, so the earliest
            # non-Restored type is the only record of what it started as.
            # Planned -> Restored never occurs in the data; planned works simply
            # stop being listed.
            kinds = [u.kind for u in updates if u.kind and u.kind != "Restored"]
            planned = (kinds[0] if kinds else row["outage_type"]) == "Planned"

            start = parse_utc(row["start_time_utc"])
            restore = parse_utc(row["restore_time_utc"])
            est = parse_utc(row["est_restore_time_utc"])
            last_seen = parse_utc(row["last_seen_utc"]) or until
            if restore:
                end, end_src = restore, "restored"
            elif est and start < est <= last_seen:
                # No restore time, so the outage either vanished from the feed
                # or is still running. ESB's own estimated restore time is by
                # far the best stand-in: measured against the 648 outages whose
                # true restore time we do know, it lands a median 0.7h late and
                # overstates total time by 18%, where falling back to the last
                # time the row was listed overstates it by 126% - ESB leaves
                # restored outages sitting in the feed for hours.
                end, end_src = est, "estimated"
            else:
                # No usable estimate: either there is none, or it lands before
                # the outage started (which makes it nonsense rather than an
                # estimate), or the outage stopped being listed before reaching
                # it, which makes leaving the feed the tighter of the two bounds.
                end, end_src = max(start, last_seen), "listed"
            if end_src != "restored":
                # Nothing can be *inferred* past the last poll, whatever the
                # clock says. A restoreTime is ESB's own statement and stands
                # even when it lands after the sighting that carried it.
                end = min(end, until)
            # An outage still listed when the collector last looked has not
            # ended yet: the time it has been out so far is a lower bound, and
            # scoring it as a restoration would count every fresh fault as a
            # fast one.
            ongoing = not restore and last_seen >= until - POLL_INTERVAL

            # The reported customer count as it changed over the outage's life,
            # so customer-minutes can be integrated rather than approximated.
            counts = [(u.at, u.customers) for u in updates if u.customers is not None]
            segments = []
            if counts:
                # Before the first observation we only have the first count.
                segments.append((start, counts[0][0], counts[0][1]))
                for i, (at, n) in enumerate(counts):
                    segments.append((at, counts[i + 1][0] if i + 1 < len(counts) else end, n))
            else:
                segments.append((start, end, row["num_cust_affected"] or 0))
            # Clamped first, then tested. A segment can be non-empty in the
            # raw observations and empty once cut to the outage's own window -
            # an observation recorded after ESB's restore time, most often,
            # because restored outages sit in the feed for hours. Testing the
            # uncut bounds kept those, inverted, and `customers` below maxes
            # over them: the peak is the highest count reported while the
            # outage was live, not the highest ever attached to its id.
            segments = [
                (max(s, start), min(e, end), n)
                for s, e, n in segments
                if min(e, end) > max(s, start)
            ]

            outages.append(
                Outage(
                    id=row["outage_id"],
                    ids=[row["outage_id"]],
                    county=county,
                    town=town,
                    town_code=town_code,
                    location=row["location"] or town,
                    planned=planned,
                    customers=max([n for _, _, n in segments] or [0]),
                    start=start,
                    end=end,
                    end_src=end_src,
                    # The same sanity rule as the end selection: an estimate
                    # before the outage started is nonsense, not an estimate.
                    est=est if est and start < est else None,
                    restored=bool(row["is_final"]),
                    ongoing=ongoing,
                    reason=row["planned_outage_reason"] or "",
                    lat=row["lat"],
                    lon=row["lon"],
                    chain=(),
                    updates=updates,
                    segments=segments,
                )
            )
        return label_repeats(merge_events(outages)), unplaced, until
    finally:
        conn.close()


def partial_days(until):
    """The days at either end of collection that were watched for only part of.

    The first day and the last are hours long rather than 24, so their cells are
    built from less time than the days beside them - and because the buckets
    count disruption accumulated over a day, a short day reads calmer than it
    was. The colour still says what was seen; these dates let the page say the
    day was short.
    """
    days = {COLLECTION_START.date(), (until - timedelta(microseconds=1)).date()}
    return sorted(d.isoformat() for d in days)


def observed_window(ym, until):
    """The part of month `ym` this site actually watched.

    Ends at the collection horizon, not at the clock: time the collector was
    down is time this site did not watch, and dividing by it would report a
    quiet network rather than an absent one.
    """
    lo, hi = month_bounds(ym)
    return max(lo, COLLECTION_START), min(hi, until)


def days_gate(ym, until):
    """When month `ym` reaches MIN_GRADED_DAYS, or None once it has.

    The instant can fall past the end of the month, so a caller about to
    promise a reader a date has to check it against `month_bounds` first.
    Takes no county: every county shares one answer.
    """
    lo, hi = observed_window(ym, until)
    if hi - lo >= timedelta(days=MIN_GRADED_DAYS):
        return None
    return lo + timedelta(days=MIN_GRADED_DAYS)


def county_month(outages, county, customers, ym, now, until):
    """Statistics for one county in one month.

    `outages` is the county's full list; filtering here rather than at the call
    site keeps the arithmetic and the selection in one place. `now` decides only
    what is still in the future; everything measured ends at `until`.
    """
    lo, hi = observed_window(ym, until)
    observed_minutes = max((hi - lo).total_seconds() / 60.0, 1.0)
    observed_days = observed_minutes / 1440.0
    month_lo, month_hi = month_bounds(ym)

    fault_cm = planned_cm = 0.0
    faults = planned = 0
    customers_hit = 0
    # The charter measure counts only outages that both started and finished
    # inside the observed window: one that began earlier was judged already, and
    # one still running has no restoration to judge. The window test alone
    # cannot catch the second - a live outage ends at the horizon, and so does
    # the window - so `ongoing` carries it.
    judged = judged_within = 0
    over_compensation = 0
    per_day_fault = defaultdict(float)
    per_day_planned = set()

    for o in outages:
        if o.county != county or not o.start or not o.end:
            continue
        if o.end <= lo or o.start >= hi:
            continue
        cm = o.customer_minutes(lo, hi)
        if o.planned:
            planned += 1
            planned_cm += cm
        else:
            faults += 1
            fault_cm += cm
            customers_hit += o.customers
            if o.start >= lo and o.end <= hi:
                hours = o.minutes / 60.0
                # Past 24 hours is true of an outage still out there: the clock
                # it has already run is a lower bound, so this one still counts.
                if hours > CHARTER_COMPENSATION_HOURS:
                    over_compensation += 1
                if not o.ongoing:
                    judged += o.customers
                    if hours <= CHARTER_TARGET_HOURS:
                        judged_within += o.customers

        # Split the outage across the days it spans, so a fault running past
        # midnight colours both days in proportion to the time it took from each.
        for seg_start, seg_end, seg_customers in o.segments:
            cur, stop = max(seg_start, lo), min(seg_end, hi)
            while cur < stop:
                nxt = (cur + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                seg = min(stop, nxt)
                if o.planned:
                    per_day_planned.add(cur.date())
                else:
                    per_day_fault[cur.date()] += (
                        seg_customers * (seg - cur).total_seconds() / 60.0
                    )
                cur = seg

    cml = fault_cm / customers
    annualised = cml * MINUTES_PER_YEAR / observed_minutes
    days_in_month = (month_hi - month_lo).days
    cells = []
    for d in range(1, days_in_month + 1):
        day = date(month_lo.year, month_lo.month, d)
        day_lo = datetime(day.year, day.month, day.day, tzinfo=UTC)
        if day_lo >= now:
            cells.append(DAY_FUTURE)
        elif day_lo + timedelta(days=1) <= COLLECTION_START or day_lo >= until:
            # Either side of the collected window is "no data". A day the
            # collector never reached is not a day without outages, and
            # colouring it would publish an all-clear nobody checked.
            cells.append(DAY_NO_DATA)
        else:
            cells.append(
                day_bucket(per_day_fault.get(day, 0.0) / customers, day in per_day_planned)
            )

    within = 100.0 * judged_within / judged if judged else None
    # Through `days_gate` so the letter and the sentence explaining its
    # absence cannot disagree.
    gradeable = (
        within is not None
        and days_gate(ym, until) is None
        and faults >= MIN_GRADED_FAULTS
    )
    return {
        "cells": "".join(str(c) for c in cells),
        "within": within,
        "cml": annualised,
        "cml_month": cml,
        "grade": grade(within) if gradeable else None,
        "faults": faults,
        "planned": planned,
        "customers_hit": customers_hit,
        "over_compensation": over_compensation,
        "fault_hours": fault_cm / 60.0,
        "planned_hours": planned_cm / 60.0,
        "observed_days": observed_days,
    }


# ESB publishes one of six, in block capitals. Labelled in the site and not in
# esb.db, which is disposable: notes/design-alignment.md § The reason moved into
# the tag.
PLANNED_REASONS = {
    "CONNECT NEW CUSTOMERS": "new connections",
    "DIVERT AN OVERHEAD LINE": "line diversion",
    "IMPROVE QUALITY OF SUPPLY": "supply quality",
    "IMPROVE THE NETWORK": "network improvement",
    "SUPPORT FIBER ROLLOUT": "fibre rollout",
    "UPGRADE THE NETWORK": "network upgrade",
}


def reason_label(reason):
    """ESB's shouted reason in a couple of readable words, or nothing at all.

    15% carry no reason, and the only other free text on the record is the
    apology every planned outage carries, so there is nothing to infer.
    """
    reason = (reason or "").strip()
    return PLANNED_REASONS.get(reason.upper(), reason.lower())


def national_ci(outages, until):
    """Fault interruptions per customer per year, ESB's other regulated index.

    Counts only faults that began inside the window: one already under way when
    collection started was an interruption somebody else's window should carry.
    """
    lo, hi = COLLECTION_START, until
    years = max((hi - lo).total_seconds(), 1.0) / (365 * 86400)
    started = sum(
        o.customers for o in outages if not o.planned and o.start and o.start >= lo
    )
    return started / NATIONAL_CUSTOMERS / years


def national_caidi(outages, until):
    """Minutes off supply per interrupted customer: CML over CI.

    The customer count divides out, which makes this the one index of the three
    that is not touched by the feed reporting more customers than ESB settles
    on. It is therefore the figure that says whether the timing model is right,
    and the page quotes it for exactly that reason.
    """
    lo, hi = COLLECTION_START, until
    faults = [o for o in outages if not o.planned]
    interrupted = sum(o.customers for o in faults if o.start and o.start >= lo)
    if not interrupted:
        return None
    return sum(o.customer_minutes(lo, hi) for o in faults) / interrupted


def national_cml(outages, until, ym=None, annualised=True):
    """Unplanned CML across the whole network.

    Annualised, this is the number that anchors the site's credibility: it is
    directly comparable to the figure ESB Networks publishes each year, and the
    test suite holds it to that comparison. `annualised=False` returns the
    window's own minutes per customer, which is what a surface showing one
    month has to print - a yearly rate beside a month's counts is a second
    clock on the same line, and nothing on the page says which is which.
    """
    if ym:
        lo, hi = observed_window(ym, until)
    else:
        lo, hi = COLLECTION_START, until
    total = sum(o.customer_minutes(lo, hi) for o in outages if not o.planned)
    cml = total / NATIONAL_CUSTOMERS
    if not annualised:
        return cml
    minutes = max((hi - lo).total_seconds() / 60.0, 1.0)
    return cml * MINUTES_PER_YEAR / minutes
