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
SITE_CSS = TEMPLATES / "site.css"
SITE_JS = TEMPLATES / "site.js"

# How many outages a server-rendered county page carries. The page exists so
# that a county has a real URL for a search engine and a reader arriving cold;
# the full month lives in the shard the app loads.
COUNTY_PAGE_CASES = 40

# How far the data may lag the build before the page says so. Pushes land at
# local midnight and noon, so with jitter and DST a build can legitimately see
# ~14h-old data, while a dead collector shows 17h+ by the next morning cron.
STALE_AFTER = timedelta(hours=16)

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
                round(s["cml"], 1),
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
            round(model.national_cml(outages, until, ym), 1),
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
    search = {}
    for o in outages:
        names = search.setdefault(o.county, set())
        for name in (o.town, o.location):
            if name and name != o.county:
                names.add(name)
    search = {c: sorted(names) for c, names in sorted(search.items())}

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
        # The same instant in a form Date.parse handles across engines, so the
        # banner can say "17 hours ago" rather than ask a reader to do timezone
        # arithmetic, and so the age is measured against the reader's clock
        # instead of being frozen at the build's. STALE_AFTER travels with it
        # for the same reason: a page served from cache has to be able to go
        # stale on its own.
        "observed_iso": f"{until:%Y-%m-%dT%H:%M:00Z}",
        "stale_hours": round(STALE_AFTER.total_seconds() / 3600),
        # Two dates at most, and the same for every county, so they sit here
        # rather than on every month of every county's row.
        "partial": model.partial_days(until),
        # The three figures the CML explainer quotes about itself. They move
        # with every rebuild, and hard-coding them into the prose meant the
        # paragraph making the site's credibility argument quietly went wrong.
        "compare": {
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
        o.reason.title() if o.reason else "",
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


def _end_bits(k):
    """How the outage ended, per the source of the end time. Only a "restored"
    end is something ESB confirmed; the wording keeps that visible, and the
    estimate is shown beside the actual rather than silently replaced by it."""
    if k[6] == "restored":
        bits = [f"restored {_when_at(k[5], k[4])}"]
        if k[10]:
            # Dated against the end, not the start: the reader has just been
            # handed the restore's day, so that is the day a bare clock time
            # reads as.
            bits.append(f"ESB's estimate was {_when_at(k[10], k[5])}")
        return bits
    if k[6] == "estimated":
        # Planned works never report a restore, so "not confirmed" would tag
        # every one of them; the estimate is simply the scheduled end.
        if k[2]:
            return [f"scheduled until {_when_at(k[5], k[4])}"]
        return [f"ESB estimated restore by {_when_at(k[5], k[4])}, not confirmed"]
    if k[2]:
        # Most planned works leave the feed without reaching their estimate;
        # "seen out" would put fault vocabulary on scheduled work.
        return [f"last listed at {_when_at(k[5], k[4])}"]
    return [f"last seen out at {_when_at(k[5], k[4])}"]


def _case_html(k):
    planned = k[2]
    chain = k[8]
    bits = [f"{k[3]:,} customer" + ("" if k[3] == 1 else "s")]
    if k[4]:
        bits.append(f"began {_fmt_day(k[4])}, {k[4][11:16]}")
    span = ""
    if k[4] and k[5]:
        hours = (
            datetime.fromisoformat(k[5]) - datetime.fromisoformat(k[4])
        ).total_seconds() / 3600.0
        # A planned record's span is its schedule when it has one and unknown
        # when it left the feed early; "off" would claim an observed outage
        # duration the footer says this data cannot know.
        if planned:
            if k[6] == "estimated":
                span = f"scheduled {_span_hm(hours)}"
        else:
            span = "off " + _span_hm(hours, about=k[6] != "restored")
        bits.extend(_end_bits(k))
    if planned and k[7]:
        bits.append(html.escape(k[7].lower()))
    return "".join(
        [
            # Anchored on the ESB outage id, so a single outage can be linked to.
            f'<div class="case" id="o{html.escape(k[0])}"><div class="top">',
            f'<span class="where">{html.escape(k[1])}</span>',
            f'<span class="tag {"tag-p" if planned else "tag-f"}">'
            f'{"Planned" if planned else "Fault"}</span>',
            f'<span class="when">{span}</span></div>',
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


DAY_LABELS = {
    "0": "no significant fault",
    "1": "minor fault disruption",
    "2": "moderate fault disruption",
    "3": "major fault disruption",
    "4": "severe fault disruption",
    "5": "planned works only",
    "8": "no data collected for this day",
    "9": "still to come",
}

# What each day-cell colour means. The swatches take their colours from the
# same site.css rules that colour the cells, so the two cannot drift.
# Mirrored in site.html (legendHtml).
LEGEND_ITEMS = (
    ("b0", "no significant fault"),
    ("b1", "minor"),
    ("b2", "moderate"),
    ("b3", "major"),
    ("b4", "severe"),
    ("b5", "planned works"),
    ("b8", "no data"),
)


def _legend_html():
    spans = "".join(
        f'<span><i class="{cls}"></i>{label}</span>' for cls, label in LEGEND_ITEMS
    )
    return f'<div class="legend">{spans}</div>'


def _day_cells(cells, ym, partial):
    # nothing to qualify on a day with no data or no colour yet
    return statusui.day_cells(cells, ym, partial, DAY_LABELS, qualify=lambda ch: ch not in "89")


def county_page(county, data, cases, ym, all_counties):
    m = data["stats"][county][ym]
    grade = m[1]
    label = month_label(ym)
    title = f"Power outages in County {county} - {label}"
    desc = (
        f"{m[4]} faults and {m[5]} planned power outages recorded in County {county} "
        f"during {label}, from ESB Networks' PowerCheck feed."
    )
    tiles = [
        ("–" if m[2] is None else f"{m[2]:g}%", "restored within 4 hours"),
        (m[4], "faults"),
        (m[5], "planned outages"),
        (f"{m[6]:,}", "customers hit by faults"),
    ]
    shown = cases[:COUNTY_PAGE_CASES]
    body = [
        '<a class="back" href="../index.html">← All counties</a>',
        f'<div class="chead"><span class="gradechip g-{grade or "none"}">{grade or "–"}</span>',
        f"<h1>County {html.escape(county)}</h1></div>",
        f'<div class="sub">{label} · About {data["customers"][county]:,} homes '
        "and businesses · estimated from Census 2022<br>"
        # This page is entered cold from a search result, so it has to carry the
        # same caveat the app does: the day bar ends where the data does. The
        # age is filled in by the page, against the reader's clock; the exact
        # horizon stays beside it for anyone who wants the digits.
        f'<span id="stamp" data-observed="{data["observed_iso"]}"'
        f' data-stale-hours="{data["stale_hours"]}"></span>'
        f'Data to {html.escape(data["observed"])}</div>',
        f'<div class="card">{_legend_html()}<div class="bar tall">'
        f'{_day_cells(m[0], ym, data["partial"])}</div>'
        '<div class="daycap"></div><div class="tiles">',
        "".join(
            f'<div class="tile"><div class="v">{v}</div><div class="k">{k}</div></div>'
            for v, k in tiles
        ),
        "</div>",
        "</div>",
    ]
    if shown:
        body.append(f'<div class="card"><h2>Outages in {label}</h2>')
        body.append("".join(_case_html(k) for k in shown))
        if len(cases) > len(shown):
            body.append(
                f'<p class="empty" style="padding-top:12px">'
                f"{len(cases) - len(shown)} more not shown here - "
                f'<a href="../index.html#county/{county}">open the full month</a>.</p>'
            )
        body.append("</div>")
    else:
        body.append(
            f'<div class="card"><p class="empty">No outages were recorded in '
            f"{html.escape(county)} during {label}.</p></div>"
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


def _page(template, markers):
    """A template with the shared UI and this site's own CSS and JS inlined, then its markers."""
    markers = dict(
        markers,
        **{
            "SITE-CSS": SITE_CSS.read_text(encoding="utf-8"),
            "SITE-JS": SITE_JS.read_text(encoding="utf-8"),
        },
    )
    return statusui.assemble(template.read_text(encoding="utf-8"), markers)


def write(site_dir, outages, sa_index, now, until):
    site_dir = Path(site_dir)
    (site_dir / "c").mkdir(parents=True, exist_ok=True)
    (site_dir / "h").mkdir(parents=True, exist_ok=True)

    data, by_county, months, search = build(outages, sa_index, now, until)
    latest = months[-1]

    (site_dir / "index.html").write_text(
        _page(SITE_HTML, {"CANONICAL": f"{BASE_URL}/"}), encoding="utf-8"
    )
    (site_dir / "data.js").write_text(
        "window.ESB_DATA = " + _dumps(data) + ";\n", encoding="utf-8"
    )
    (site_dir / "search.js").write_text(
        "window.ESB_SEARCH = " + _dumps(search) + ";\n", encoding="utf-8"
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
            county_page(county, data, by_month.get(latest, []), latest, sa_index.counties),
            encoding="utf-8",
        )

    lastmod = now.strftime("%Y-%m-%d")
    paths = [""] + [f"c/{slug(c)}.html" for c in sa_index.counties]
    (site_dir / "sitemap.xml").write_text(
        statusui.sitemap(BASE_URL, paths, lastmod), encoding="utf-8"
    )
    (site_dir / "robots.txt").write_text(statusui.robots(BASE_URL), encoding="utf-8")
    return data


def size_report(site_dir):
    """What a reader downloads before they touch anything; printed on every build."""
    return statusui.size_report(
        site_dir, BUDGET_BYTES, "c", "county pages", extra=[("search.js", "on first keystroke")]
    )
