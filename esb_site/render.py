"""Emit the static site.

The payload split is the thing this file exists to get right. `data.js` carries
only what the front page needs - one row per county per month, with the day bars
packed into a string - while the individual outages live in a per-county shard
that is never fetched until a reader opens that county. Everything the reader
first downloads has to fit inside 500 KB and keep fitting for years, and the
only way to hold that line is to never put a per-outage record in `data.js`.
"""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import statusui

from . import model

BASE_URL = "https://baz8080.github.io/esb"
BUDGET_BYTES = 500 * 1024

TEMPLATES = Path(__file__).parent
SITE_HTML = TEMPLATES / "site.html"
COUNTY_HTML = TEMPLATES / "county.html"
AREAS_HTML = TEMPLATES / "areas.html"
AREA_HTML = TEMPLATES / "area.html"
SITE_CSS = TEMPLATES / "site.css"

# Neighbour links per area page: the reader's check of where else an outage
# may be filed, since the pin is the fault and not everyone it cut off. Five
# covers a plausible substation catchment without becoming a gazetteer.
NEARBY_AREAS = 5

# How far the data may lag the build before the page says so. Pushes land every
# six hours, so with the timer's jitter and one poll interval the newest data can
# legitimately be ~7h old; a single missed push shows 13h+.
STALE_AFTER = timedelta(hours=10)

slug = statusui.slug
month_label = statusui.month_label
_dumps = statusui.dumps
_stamp = statusui.stamp
_when = statusui.when
_hours = statusui.hours
_fmt_day = statusui.fmt_day


def _short(dt):
    """Timestamps are rendered, never computed on, so minutes are enough."""
    return dt.strftime("%Y-%m-%dT%H:%M") if dt else None


def _when_at(ts, ref):
    """A timestamp against the outage's start day: the clock time alone when it
    falls on the same day, the full day otherwise. Mirrored in site.html."""
    if ts[:10] == ref[:10]:
        return ts[11:16]
    return f"{_fmt_day(ts)}, {ts[11:16]}"


def _span_hm(hours, about=False):
    """A duration in hours and minutes, never a decimal a reader has to work
    out. `about` rounds to the nearest half hour - an unconfirmed end does not
    support minute precision - and owns its hedging words, so a caller cannot
    pair them wrongly. Mirrored in site.html (spanHM)."""
    minutes = statusui.half_up(hours * 60)
    if about:
        minutes = statusui.half_up(minutes / 30.0) * 30
        if not minutes:
            # An unconfirmed span this short is a lower bound; rounding it up
            # to 30 min would contradict the card's own timestamps.
            return "under 30 min"
    prefix = "about " if about else ""
    if minutes < 60:
        return f"{prefix}{minutes} min"
    if hours >= 48:
        return prefix + _hours(hours)
    h, m = divmod(minutes, 60)
    return prefix + f"{h} h" + (f" {m} min" if m else "")


def _approx(n):
    """Nearest 1,000 (nearest 100 under 10,000). The county figure is ESB's
    ~2.5m national meter count split by Census population share, which carries
    no more precision than this."""
    step = 1000 if n >= 10000 else 100
    return int(statusui.half_up(n / step)) * step


def build(outages, sa_index, now, until):
    """Assemble every value the templates need, and nothing they do not.

    `now` fixes only what is still in the future; `until` is where the collected
    data stops, and every measured window ends there.
    """
    months = model.month_list(model.COLLECTION_START, now)

    by_county = defaultdict(list)
    for o in outages:
        by_county[o.county].append(o)

    stats, national = {}, {}
    for county in sa_index.counties:
        rows = by_county.get(county, [])
        per_month = {}
        for ym in months:
            s = model.county_month(
                rows, county, sa_index.customers[county], ym, now, until
            )
            per_month[ym] = [
                s["cells"],
                s["grade"],
                None if s["within"] is None else round(s["within"], 1),
                # a month's row on a month's clock; `cml` is the annual rate
                round(s["cml_month"], 1),
                s["faults"],
                s["planned"],
                s["customers_hit"],
                s["over_compensation"],
            ]
        stats[county] = per_month

    for ym in months:
        lo, hi = model.observed_window(ym, until)
        live = [o for o in outages if o.start and o.end and o.end > lo and o.start < hi]
        faults = [o for o in live if not o.planned]
        # Same gate as county_month: an outage still out has no restoration to
        # judge, and its elapsed time would score as a fast one.
        judged = [o for o in faults if o.start >= lo and o.end <= hi and not o.ongoing]
        seen = sum(o.customers for o in judged)
        within = sum(
            o.customers
            for o in judged
            if o.minutes / 60.0 <= model.CHARTER_TARGET_HOURS
        )
        national[ym] = [
            round(model.national_cml(outages, until, ym, annualised=False), 1),
            len(faults),
            len(live) - len(faults),
            sum(o.customers for o in faults),
            round(sum(o.customer_minutes(lo, hi) for o in faults) / 60.0, 1),
            None if not seen else round(100.0 * within / seen, 1),
        ]

    # Names a reader might type, grouped by county so the county name is stored
    # once instead of beside every place in it. This is the only part of the
    # payload that grows with the number of distinct place names rather than
    # with time, which is why it is loaded on demand rather than up front.
    #
    # A Census settlement with a page is stored as `[name, slug]` so the hit can
    # link straight to it; ESB's own location strings, which name no area, stay
    # bare. Keyed on the name because `location` falls back to `town`, and the
    # slug is right for that name either way. Every page these address is
    # written from the same outages below, so a slug here always has a file.
    #
    # A name that is its county's enters only with a slug: paged, it is one of
    # the fourteen towns named for their county and its page is somewhere the
    # county row cannot go; bare, it is ESB writing "Sligo" for a fault
    # somewhere in the county, and would be a second row to the same view.
    paged = {}
    search = {}
    for o in outages:
        if model.area_has_page(o.town_code):
            paged.setdefault(o.county, {})[o.town] = slug(o.town)
        names = search.setdefault(o.county, set())
        names.update(n for n in (o.town, o.location) if n)
    search = {
        c: [
            [n, paged[c][n]] if n in paged.get(c, ()) else n
            for n in sorted(names)
            if n != c or n in paged.get(c, ())
        ]
        for c, names in sorted(search.items())
    }

    data = {
        "generated": _stamp(now),
        # What the build knows, as distinct from when it ran. Without this the
        # page dates itself by the clock and a reader cannot tell a quiet week
        # from a collector that stopped. Formatted for display here - it is
        # only ever shown, and the footer says "Data to {observed}".
        "observed": (
            f"{statusui.fmt_date(until.date().isoformat(), now.date())},"
            f" {until:%H:%M} UTC"
        ),
        # The same instant for freshness(), which dates the page against the
        # reader's clock rather than the build's. STALE_AFTER travels with it,
        # so a page served from cache can still go stale.
        "observed_iso": f"{until:%Y-%m-%dT%H:%M:00Z}",
        "stale_hours": round(STALE_AFTER.total_seconds() / 3600),
        # Two dates at most, and the same for every county, so they sit here
        # rather than on every month of every county's row.
        "partial": model.partial_days(until),
        "daygate": _daygate(months, until),
        # The three figures the CML explainer quotes about itself. They move
        # with every rebuild, and hard-coding them into the prose meant the
        # paragraph making the site's credibility argument quietly went wrong.
        "compare": {
            # the one annual figure left, for the paragraph that argues with
            # ESB's own yearly number; every other figure on the site is a month
            "cml": round(model.national_cml(outages, until), 1),
            "caidi": round(model.national_caidi(outages, until) or 0),
            "esb_caidi": round(model.ESB_NATIONAL_CML / model.ESB_NATIONAL_CI),
            "bias": round(
                (model.national_ci(outages, until) / model.ESB_NATIONAL_CI - 1) * 100
            ),
        },
        "start": model.COLLECTION_START.strftime("%-d %B %Y"),
        "months": months,
        "esb": {
            "national": model.ESB_NATIONAL_CML,
            "target": model.ESB_CRU_TARGET_CML,
            "hours": model.CHARTER_TARGET_HOURS,
            "share": model.CHARTER_TARGET_SHARE,
        },
        "counties": sa_index.counties,
        "customers": {c: _approx(sa_index.customers[c]) for c in sa_index.counties},
        "stats": stats,
        "national": national,
    }
    return data, by_county, months, search


def case_record(o):
    """One outage, as compact as it can be while staying readable in the file."""
    return [
        o.id,
        o.location,
        1 if o.planned else 0,
        o.customers,
        _short(o.start),
        _short(o.end),
        o.end_src,
        model.reason_label(o.reason),
        list(o.chain),
        [
            [kind, _short(when), customers]
            for kind, when, customers in model.timeline(
                o.start, o.end, o.end_src, o.segments
            )
        ],
        # Only a confirmed restore renders the estimate, and only when the two
        # differ; anything else is payload the page can never show.
        _short(o.est) if o.end_src == "restored" and o.est != o.end else None,
    ]


def shard(outages, months, until):
    """Every outage in one county, grouped by month.

    An outage is listed under every month it overlaps, which is exactly the set
    of months `county_month` counts it in. Filing it by its start month instead
    left one that ran past midnight on the 31st counted in the later month's
    tiles and missing from that month's list, so a reader could count the rows
    and come up one short of the headline.
    """
    windows = [(ym,) + model.observed_window(ym, until) for ym in months]
    by_month = defaultdict(list)
    for o in sorted(outages, key=lambda o: o.start, reverse=True):
        record = None
        for ym, lo, hi in windows:
            if o.end > lo and o.start < hi:
                record = case_record(o) if record is None else record
                by_month[ym].append(record)
    return by_month


def _vs_estimate(end, est):
    """Restored earlier or later than ESB said, when the gap is worth saying.

    69% of restored faults beat the estimate and 25% miss it, which is worth
    more than the estimate's clock time. Inside five minutes it is noise.
    """
    delta = (
        datetime.fromisoformat(end) - datetime.fromisoformat(est)
    ).total_seconds() / 60.0
    if abs(delta) < 5:
        return ""
    return (
        f"{_span_hm(abs(delta) / 60.0)} "
        f"{'later' if delta > 0 else 'earlier'} than ESB estimated"
    )


def _end_bits(k, hours):
    """How the outage ended and how long it ran, as one phrase per shape.

    Only a "restored" end is something ESB confirmed; the rest name the missing
    record rather than hedging. Mirrored in site.html (endBits).
    """
    planned, src = k[2], k[6]
    if src == "restored":
        bits = [f"restored {_when_at(k[5], k[4])} ({_span_hm(hours)})"]
        if k[10]:
            bits.append(_vs_estimate(k[5], k[10]))
        return [b for b in bits if b]
    if src == "estimated":
        # Planned works never report a restore, so their estimate is simply
        # the schedule and needs no caveat; a fault's is a guess nobody stood
        # over, and the caveat says which guess.
        if planned:
            return [f"scheduled until {_when_at(k[5], k[4])} ({_span_hm(hours)})"]
        return [
            f"expected back by {_when_at(k[5], k[4])} ({_span_hm(hours, about=True)})",
            "no restore time published",
        ]
    # Delisted: state the span that was measured - time off, or time on ESB's
    # list - rather than the sighting's clock time, which told a reader nothing.
    if planned:
        return [f"listed for {_span_hm(hours, about=True)}", "no end time published"]
    return [f"off for {_span_hm(hours, about=True)}", "no restore time published"]


def _case_html(k):
    planned = k[2]
    chain = k[8]
    bits = [f"{k[3]:,} customer" + ("" if k[3] == 1 else "s") + " affected"]
    if k[4]:
        bits.append(f"began {_fmt_day(k[4])}, {k[4][11:16]}")
    if k[4] and k[5]:
        hours = (
            datetime.fromisoformat(k[5]) - datetime.fromisoformat(k[4])
        ).total_seconds() / 3600.0
        bits.extend(_end_bits(k, hours))
    # in the chip rather than trailing the timings: it is the row's most human
    # fact and it was in its least-read position
    tag = "Planned" if planned else "Fault"
    if planned and k[7]:
        tag += f" · {k[7]}"
    return "".join(
        [
            # Anchored on the ESB outage id, so a single outage can be linked to.
            f'<div class="case" id="o{html.escape(k[0])}"><div class="top">',
            f'<span class="where">{html.escape(k[1])}</span>',
            f'<span class="tag {"tag-p" if planned else "tag-f"}">'
            f"{html.escape(tag)}</span></div>",
            f'<div class="sum">{" · ".join(bits)}</div>',
            _chain_html(chain),
            _updates_html(k[9], planned),
            "</div>",
        ]
    )


def _chain_html(chain):
    """A repeat fault is a separate interruption, but the reader wants the run."""
    if not chain:
        return ""
    return (
        f'<div class="repeat">Repeat fault - outage {chain[0]} of {chain[1]} '
        f"at this location in quick succession</div>"
    )


ROW_LABEL = {
    "began": "Outage began",
    "restored": "Supply restored",
    "estimated": "Estimated restore, from ESB",
    "listed": "Last seen still out",
}

# Planned works get their own end-row words, matching the summary line: their
# "estimate" is a schedule, and their listing is not an observed outage.
PLANNED_ROW_LABEL = {"estimated": "Scheduled end", "listed": "Last listed"}


def _update_line(row, key, planned=False):
    kind, when, customers = row
    bits = []
    label = (PLANNED_ROW_LABEL.get(kind) if planned else None) or ROW_LABEL.get(kind)
    if label:
        bits.append(f"<b>{label}</b>")
    if customers is not None:
        bits.append(
            f"{customers:,} customers"
            + (" still off" if kind == "update" else "")
        )
    cls = ' class="key"' if key else ""
    return f"<li{cls}><time>{_when(when)}</time>{' · '.join(bits)}</li>"


def _updates_html(rows, planned=False):
    # Two rows are the reported start and end, which the summary line above
    # already states; repeating them as a timeline is noise on the 93% of
    # outages whose customer count never changed. The timeline earns its place
    # only when there is something between the anchors.
    if len(rows) <= 2:
        return ""
    if len(rows) <= model.INLINE_UPDATES:
        body = "".join(
            _update_line(r, i in (0, len(rows) - 1), planned)
            for i, r in enumerate(rows)
        )
        return f'<ul class="tl">{body}</ul>'
    mid = rows[1:-1]
    inner = "".join(_update_line(r, False, planned) for r in mid)
    return (
        '<ul class="tl">'
        + _update_line(rows[0], True, planned)
        + f"<li><details><summary>{len(mid)} further update"
        + ("" if len(mid) == 1 else "s")
        + f"</summary><ul>{inner}</ul></details></li>"
        + _update_line(rows[-1], True, planned)
        + "</ul>"
    )


GRADES = {
    "A": "meets ESB's aim of 95% restored within 4 hours",
    "B": "90% or more restored within 4 hours",
    "C": "80% or more restored within 4 hours",
    "D": "70% or more restored within 4 hours",
    "E": "60% or more restored within 4 hours",
    "F": "fewer than 60% restored within 4 hours",
}


def _daygate(months, until):
    """Months the five-day gate still holds shut, against the date each opens.

    Absent means graded on days; "" means a month that can never reach five.
    """
    gates = ((ym, model.days_gate(ym, until)) for ym in months)
    return {
        ym: "" if when >= model.month_bounds(ym)[1] else f"{when:%-d %B}"
        for ym, when in gates
        if when is not None
    }


def ungraded_reason(ym, faults, until):
    """Why a county-month carries no letter. Call only for an ungraded one.

    Three gates withhold it and naming the wrong one sends a reader after
    outages that are not the reason. Mirrored in site.html (ungradedReason).
    """
    when = model.days_gate(ym, until)
    if when is not None:
        # past the month's end: it can never reach five days, so promise no date
        if when >= model.month_bounds(ym)[1]:
            return f"Only part of {month_label(ym)} was watched, so it is not graded"
        return f"{month_label(ym)} is too new to grade. Grades appear from {when:%-d %B}"
    if faults < model.MIN_GRADED_FAULTS:
        return f"Too few faults in {month_label(ym)} to grade fairly"
    # Past both gates, nothing was judged: every fault still out at the horizon,
    # or begun before the month. Blaming the count here would contradict the
    # Faults column beside it.
    return (
        f"No fault in {month_label(ym)} was restored in the month it started, "
        "so there is nothing to grade"
    )


def _grade_chip(grade, month=None, reason=None):
    """The letter, with the band it stands for on hover.

    The county page's footer used to spell the bands out. `month` names the
    month the letter is for: on the heading the card that used to scope it is
    gone, so a bare "F" would read as the county's standing for all time.
    Mirrored in site.html (GRADES, gradeChip).
    """
    when = f" in {month}" if month else ""
    title = (
        f"Grade {grade}{when}: {GRADES[grade]}"
        if grade
        # bare, never the faults wording: guessing at a gate is what went wrong
        else reason or f"Not graded{when or ' this month'}"
    )
    return (
        f'<span class="gradechip g-{grade or "none"}" title="{html.escape(title)}">'
        f'{grade or "–"}</span>'
    )


def _county_cases(by_month, months):
    """Every outage in one county, newest first, once each.

    A shard files an outage under every month it overlaps, so flattening one
    without this would list a fault that ran past midnight on the 31st twice.
    """
    seen, cases = set(), []
    for ym in reversed(months):
        for k in by_month.get(ym, []):
            if k[0] not in seen:
                seen.add(k[0])
                cases.append(k)
    # by start rather than by the month it was filed under, so the boundary
    # spanners sit where a reader looking for them expects
    cases.sort(key=lambda k: k[4] or "", reverse=True)
    return cases


def _month_watched(ym, until):
    """"from 31 Jul" - the part of a month the collector actually saw.

    The same reason `partial_days` exists, one level up: the first and last
    months are short, and a row of zeros for three hours of July reads as a
    quiet month rather than an absent collector.
    """
    lo, hi = model.month_bounds(ym)
    olo, ohi = model.observed_window(ym, until)
    bits = []
    if olo > lo:
        bits.append(f"from {olo:%-d %b}")
    if ohi < hi:
        bits.append(f"to {ohi:%-d %b}")
    return " ".join(bits)


def _reason_for(m, ym, until):
    """The ungraded sentence for a payload row, or None where it has a letter."""
    return None if m[1] else ungraded_reason(ym, m[4], until)


def _county_months_html(county, data, months, until):
    """One row per month, newest first.

    Read straight off the payload the app charts, so the page and the county
    view cannot come to disagree about a month.
    """
    rows = []
    for ym in reversed(months):
        m = data["stats"][county][ym]
        watched = _month_watched(ym, until)
        rows.append(
            f'<tr><th scope="row">{month_label(ym)}'
            + (f'<span class="part">{watched}</span>' if watched else "")
            + "</th>"
            f"<td>{_grade_chip(m[1], reason=_reason_for(m, ym, until))}</td>"
            f'<td>{"–" if m[2] is None else f"{m[2]:g}%"}</td>'
            f"<td>{m[4]:,}</td><td>{m[5]:,}</td><td>{m[6]:,}</td>"
            f"<td>{m[3]:,.1f}</td></tr>"
        )
    return (
        '<div class="card"><h2>Month by month</h2><div class="scroll">'
        '<table class="mtable"><thead><tr>'
        '<th scope="col">Month</th><th scope="col">Grade</th>'
        '<th scope="col">Restored in 4h</th>'
        '<th scope="col">Faults</th><th scope="col">Planned</th>'
        '<th scope="col">Customers hit</th>'
        '<th scope="col" title="Customer Minutes Lost: minutes off supply for '
        'the average customer that month, faults only">Minutes lost</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>'
    )


def county_page(county, data, by_month, months, until, all_counties, areas=()):
    """The whole body of c/<slug>.html.

    Every month, not only the latest. The URL names a county, so what it
    publishes has to be that county's record; carrying one month made the page's
    subject - and its title - change under the same URL every time the month
    rolled over.
    """
    newest = data["stats"][county][months[-1]]
    grade = newest[1]
    reason = _reason_for(newest, months[-1], until)
    cases = _county_cases(by_month, months)
    faults = sum(1 for k in cases if not k[2])
    planned = len(cases) - faults
    title = f"Power outages in County {county}"
    # The counts and the listing now agree, but the order still matters: the
    # record first, what the page holds after it, so a snippet cut by width
    # leaves a true sentence behind.
    desc = (
        f"County {county}: {faults:,} fault{'' if faults == 1 else 's'} and "
        f"{planned:,} planned power cut{'' if planned == 1 else 's'} since "
        f"{data['start']}. Month-by-month totals and every outage recorded, "
        f"from ESB Networks' PowerCheck feed."
    )
    body = [
        '<a class="back" href="../index.html">← All counties</a>',
        f'<div class="chead">{_grade_chip(grade, month_label(months[-1]), reason)}',
        f"<h1>County {html.escape(county)}</h1></div>",
        f'<div class="sub">About {data["customers"][county]:,} homes '
        "and businesses · estimated from Census 2022</div>",
    ]
    # A `title` does not open on a touch screen and a bare dash reads as a
    # verdict, so the day gate - alone among the three - is said in the open.
    if grade is None and model.days_gate(months[-1], until) is not None:
        body.append(f'<div class="ungraded">{html.escape(reason)}.</div>')
    # Straight to the months: the newest month's card duplicated the table's
    # first row (notes/design-alignment.md § The county page became an archive).
    body.append(_county_months_html(county, data, months, until))
    if cases:
        body.append(
            f'<div class="card"><h2>Outage history <span class="n">'
            f'· {len(cases):,} outage{"" if len(cases) == 1 else "s"}</span></h2>'
        )
        body.append("".join(_case_html(k) for k in cases))
        body.append("</div>")
    else:
        body.append(
            f'<div class="card"><p class="empty">No outages have been recorded in '
            f"{html.escape(county)} since {data['start']}.</p></div>"
        )
    if areas:
        body.append(
            f'<div class="card"><h2>Areas with an outage <span class="n">'
            f'· {len(areas):,} area{"" if len(areas) == 1 else "s"}</span></h2>'
            f'<ul class="areas">{_area_items(county, areas, "../")}</ul></div>'
        )
    body.append('<div class="card"><h2>Every county</h2><p class="nav">')
    body.append(
        " ".join(
            f'<a href="{slug(c)}.html">{html.escape(c)}</a>'
            for c in all_counties
            if c != county
        )
    )
    body.append("</p></div>")

    return _page(
        COUNTY_HTML,
        {
            "TITLE": html.escape(title),
            "DESC": html.escape(desc),
            "CANONICAL": f"{BASE_URL}/c/{slug(county)}.html",
            "BODY": "".join(body),
        },
    )


def area_path(county, name):
    """`a/<county>/<area>.html`. Name, not code - a code is not a filename -
    and under the county because names repeat across counties; (county, name)
    is unique over the whole CSO file, asserted in the tests."""
    return f"a/{slug(county)}/{slug(name)}.html"


def area_index(outages, sa_index):
    """[(county, [(code, name, pop, events), ...]), ...], A-Z, events newest
    first. Grouped on the census assignment, never ESB's location string,
    which fragments (uisce measured 3,866 distinct values in its feed's)."""
    by_area = defaultdict(list)
    for o in outages:
        by_area[(o.county, o.town_code)].append(o)
    by_county = defaultdict(list)
    for (county, code), events in by_area.items():
        # id breaking ties so a rebuild is reproducible
        events.sort(key=lambda o: (o.start, o.id), reverse=True)
        by_county[county].append(
            (code, events[0].town, sa_index.town_pop[code], events)
        )
    return [
        (county, sorted(areas, key=lambda a: (a[1], a[0])))
        for county, areas in sorted(by_county.items())
    ]


def _area_items(county, areas, prefix="", county_fallback=False):
    """The <li> rows for one county's areas, shared by areas.html and c/*.html
    so the two cannot disagree about a count; `prefix` hops up from c/.

    `county_fallback` sends a row with no page of its own to the county's
    record, which is where those outages are listed - 876 of the directory's
    1,270 rows. The county page passes it off: there it would link at itself.
    """
    items = []
    for code, name, pop, events in areas:
        n = len(events)
        if model.area_has_page(code):
            where = f'<a href="{prefix}{area_path(county, name)}">{html.escape(name)}</a>'
        elif county_fallback:
            where = f'<a href="{prefix}c/{slug(county)}.html">{html.escape(name)}</a>'
        else:
            where = html.escape(name)
        # units on every row, not a column heading that scrolls away
        items.append(
            f"<li>{where}"
            '<span class="fill"></span>'
            f'<span class="n">{n} outage{"" if n == 1 else "s"}</span>'
            f'<span class="p">{pop:,} people</span></li>'
        )
    return "".join(items)


def _areas_index_html(index):
    """The directory's body: a jump nav and one section per county."""
    nav = " · ".join(
        f'<a href="#c-{slug(c)}">{html.escape(c)}</a>' for c, _ in index
    )
    sections = []
    for county, areas in index:
        # data-county is the bare name for the search: matching the heading
        # would make "page" select every county in the country
        sections.append(
            f'<section id="c-{slug(county)}" data-county="{html.escape(county)}">'
            f"<h2>County {html.escape(county)} <span>· {len(areas)} "
            f'area{"" if len(areas) == 1 else "s"} · '
            f'<a href="c/{slug(county)}.html">county page</a></span></h2>'
            f'<ul class="areas">{_area_items(county, areas, county_fallback=True)}'
            "</ul></section>"
        )
    # Once, where the rows start: a fallback row looks like every other and
    # lands somewhere else. "Around ..." is 874 of the 876; the other two are
    # the city remainders, which the wording has to cover as well.
    note = (
        '<p class="note"><em>Around&nbsp;…</em> and <em>Elsewhere&nbsp;in&nbsp;…</em> '
        "areas have no page of their own — those links go to the county page.</p>"
    )
    return f"<nav>{nav}</nav>\n{note}\n{''.join(sections)}"


def _km_label(d):
    if d < 1.0:
        return "under 1 km"
    return f"{statusui.half_up(d)} km"


def nearby_areas(index, sa_index):
    """{code: [(km, county, name), ...]} - each page's NEARBY_AREAS nearest
    pages: the attribution disclaimer made actionable. County lines are
    deliberately not a fence, and only paged areas qualify - a link must
    have somewhere to go."""
    pages = [
        (county, code, name)
        for county, areas in index
        for code, name, _pop, _events in areas
        if model.area_has_page(code)
    ]
    out = {}
    for _county, code, _name in pages:
        centre = sa_index.centroids[code]
        out[code] = sorted(
            (model.km(*centre, *sa_index.centroids[other]), oc, oname)
            for oc, other, oname in pages
            if other != code
        )[:NEARBY_AREAS]
    return out


def area_page(county, name, pop, events, nearby, data):
    """The whole body of a/<county>/<area>.html.

    Uncapped, unlike the county page's list - an area accrues a handful of
    outages, and the description promises every one. No grade, day bar or
    CML: both are calibrated to county-scale denominators (notes/area-pages.md).
    """
    cases = [case_record(o) for o in events]
    faults = sum(1 for o in events if not o.planned)
    planned = len(events) - faults
    near = "".join(
        f'<li><a href="../{slug(c)}/{slug(n)}.html">{html.escape(n)}</a>'
        '<span class="fill"></span>'
        f'<span class="n">{_km_label(d)}</span>'
        f'<span class="p">{"" if c == county else f"County {html.escape(c)}"}</span></li>'
        for d, c, n in nearby
    )
    body = [
        f'<a class="back" href="../../c/{slug(county)}.html">'
        f"← County {html.escape(county)}</a>",
        f"<div class=\"chead\"><h1>{html.escape(name)}</h1></div>",
        f'<div class="sub">{pop:,} people · Census 2022 · '
        f"County&nbsp;{html.escape(county)}</div>",
        f'<div class="card"><h2>Every outage pinned near {html.escape(name)} '
        f'<span class="n">· {len(cases):,} outage'
        f'{"" if len(cases) == 1 else "s"}</span></h2>',
        # the one thing this page must not overclaim
        '<p class="note">Outages are filed under the Census area nearest the '
        f"fault ESB reported. A cut that hit {html.escape(name)} may be listed "
        "under a neighbouring area, and one listed here may reach far beyond "
        f"it - which is why a row can count more customers than "
        f"{html.escape(name)} has people.</p>",
        "".join(_case_html(k) for k in cases),
        "</div>",
    ]
    if near:
        body.append(
            '<div class="card"><h2>Nearby areas</h2>'
            '<p class="note">The nearest areas with a page of their own - an '
            "outage close to the boundary may be filed under one of these.</p>"
            f'<ul class="areas">{near}</ul></div>'
        )
    body.append(
        '<div class="card"><h2>Elsewhere</h2><p class="nav">'
        f'<a href="../../c/{slug(county)}.html">County {html.escape(county)}’s '
        "whole record</a> "
        f'<a href="../../index.html#county/{county}">County&nbsp;'
        f"{html.escape(county)}’s interactive view</a></p></div>"
    )
    # the record first, what the page holds last - truncation must not turn
    # the snippet into an inventory claim (the county pages' rule)
    desc = (
        f"{name}, County {county}: {faults:,} fault{'' if faults == 1 else 's'} and "
        f"{planned:,} planned power cut{'' if planned == 1 else 's'} pinned nearby "
        f"since {data['start']}. Every one of them, newest first, from ESB "
        f"Networks' PowerCheck feed."
    )
    return _page(
        AREA_HTML,
        {
            "TITLE": html.escape(f"Power outages near {name}, County {county}"),
            "DESC": html.escape(desc),
            "CANONICAL": f"{BASE_URL}/{area_path(county, name)}",
            "BODY": "".join(body),
        },
    )


def _page(template, markers):
    """A template with the shared UI and this site's stylesheet inlined, then its markers."""
    markers = dict(markers, **{"SITE-CSS": SITE_CSS.read_text(encoding="utf-8")})
    return statusui.assemble(template.read_text(encoding="utf-8"), markers)


def write(site_dir, outages, sa_index, now, until):
    site_dir = Path(site_dir)
    (site_dir / "c").mkdir(parents=True, exist_ok=True)
    (site_dir / "h").mkdir(parents=True, exist_ok=True)

    data, by_county, months, search = build(outages, sa_index, now, until)
    index = area_index(outages, sa_index)
    county_areas = dict(index)
    nearby = nearby_areas(index, sa_index)

    (site_dir / "index.html").write_text(
        _page(SITE_HTML, {"CANONICAL": f"{BASE_URL}/"}), encoding="utf-8"
    )
    (site_dir / "data.js").write_text(
        "window.ESB_DATA = " + _dumps(data) + ";\n", encoding="utf-8"
    )
    # ESB_PLACES, not ESB_SEARCH: search.js is fetched lazily, so a tab opened
    # before a deploy pairs its own inlined ui.js with the current file. The
    # entries carry a slug now, and the old searchHits calls toLowerCase on
    # them - renaming with the shape means that reader gets the box's own
    # "unavailable, try reloading" instead of a dropdown stuck on "Searching".
    (site_dir / "search.js").write_text(
        "window.ESB_PLACES = " + _dumps(search) + ";\n", encoding="utf-8"
    )
    (site_dir / "areas.html").write_text(
        _page(
            AREAS_HTML,
            {"AREAS": _areas_index_html(index), "CANONICAL": f"{BASE_URL}/areas.html"},
        ),
        encoding="utf-8",
    )

    for county in sa_index.counties:
        by_month = shard(by_county.get(county, []), months, until)
        # A shard is written for every county, including one with nothing in it,
        # so the loader never has to tell a 404 apart from a quiet county.
        (site_dir / "h" / f"{slug(county)}.js").write_text(
            f"(window.ESB_CASES=window.ESB_CASES||{{}})[{_dumps(county)}] = "
            + _dumps(by_month)
            + ";\n",
            encoding="utf-8",
        )
        (site_dir / "c" / f"{slug(county)}.html").write_text(
            county_page(
                county, data, by_month, months, until, sa_index.counties,
                county_areas.get(county, ()),
            ),
            encoding="utf-8",
        )

    area_paths = []
    for county, areas in index:
        for code, name, pop, events in areas:
            if not model.area_has_page(code):
                continue
            rel = area_path(county, name)
            path = site_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                area_page(county, name, pop, events, nearby[code], data),
                encoding="utf-8",
            )
            area_paths.append(rel)

    lastmod = now.strftime("%Y-%m-%d")
    paths = (
        [""]
        + [f"c/{slug(c)}.html" for c in sa_index.counties]
        + ["areas.html"]
        + area_paths
    )
    (site_dir / "sitemap.xml").write_text(
        statusui.sitemap(BASE_URL, paths, lastmod), encoding="utf-8"
    )
    (site_dir / "robots.txt").write_text(statusui.robots(BASE_URL), encoding="utf-8")
    return data


def size_report(site_dir):
    """What a reader downloads before they touch anything; printed on every build."""
    total, report = statusui.size_report(
        site_dir, BUDGET_BYTES, "c", "county pages", extra=[("search.js", "on first keystroke")]
    )
    # outside the initial load but printed: a crawl surface going quietly
    # empty is invisible from the field
    site_dir = Path(site_dir)
    pages = list((site_dir / "a").glob("*/*.html"))
    report += (
        f"\n  {'areas.html':<16}"
        f"{(site_dir / 'areas.html').stat().st_size / 1024:8.1f} KB   (standalone)"
        f"\n  {'area pages':<16}"
        f"{sum(p.stat().st_size for p in pages) / 1024:8.1f} KB"
        f"   ({len(pages)} files)"
    )
    return total, report
