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

# How many outages a server-rendered county page carries. The page exists so
# that a county has a real URL for a search engine and a reader arriving cold;
# the full month lives in the shard the app loads.
COUNTY_PAGE_CASES = 40

# How far the data may lag the build before the page says so. The collector
# pushes daily and the site rebuilds daily, so a gap under this is the normal
# handover; past it, something has stopped and the reader should be told rather
# than left reading the day bars as a quiet week.
STALE_AFTER = timedelta(hours=24)

# How an outage's end is described, per the source the end time came from. The
# distinction matters to a reader: only the first is something ESB confirmed.
END_LABEL = {
    "restored": "restored {when}",
    "estimated": "due back {when}",
    "listed": "last seen out at {when}",
}

slug = statusui.slug
month_label = statusui.month_label
_dumps = statusui.dumps
_stamp = statusui.stamp
_when = statusui.when
_hours = statusui.hours


def _short(dt):
    """Timestamps are rendered, never computed on, so minutes are enough."""
    return dt.strftime("%Y-%m-%dT%H:%M") if dt else None


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
        # from a collector that stopped.
        "observed": _stamp(until),
        "stale": now - until > STALE_AFTER,
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
        "customers": {c: round(sa_index.customers[c]) for c in sa_index.counties},
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


def _case_html(k):
    planned = k[2]
    chain = k[8]
    bits = [f"{k[3]:,} customer" + ("" if k[3] == 1 else "s"), f"began {_when(k[4])}"]
    span = ""
    if k[4] and k[5]:
        hours = (
            datetime.fromisoformat(k[5]) - datetime.fromisoformat(k[4])
        ).total_seconds() / 3600.0
        span = _hours(hours) + ("" if k[6] == "restored" else " est.")
        bits.append(END_LABEL[k[6]].format(when=_when(k[5])))
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
            _updates_html(k[9]),
            "</div>",
        ]
    )


def _chain_html(chain):
    """A repeat fault is a separate interruption, but the reader wants the run."""
    if not chain:
        return ""
    return (
        f'<div class="repeat">Repeat fault — outage {chain[0]} of {chain[1]} '
        f"at this location in quick succession</div>"
    )


ROW_LABEL = {
    "began": "Outage began",
    "restored": "Supply restored",
    "estimated": "Due back, on ESB's estimate",
    "listed": "Last seen still out",
}


def _update_line(row, key):
    kind, when, customers = row
    bits = []
    if kind in ROW_LABEL:
        bits.append(f"<b>{ROW_LABEL[kind]}</b>")
    if customers is not None:
        bits.append(
            f"{customers:,} customers"
            + (" still off" if kind == "update" else "")
        )
    cls = ' class="key"' if key else ""
    return f"<li{cls}><time>{_when(when)}</time>{' · '.join(bits)}</li>"


def _updates_html(rows):
    # Two rows are the reported start and end, which the summary line above
    # already states; repeating them as a timeline is noise on the 93% of
    # outages whose customer count never changed. The timeline earns its place
    # only when there is something between the anchors.
    if len(rows) <= 2:
        return ""
    if len(rows) <= model.INLINE_UPDATES:
        body = "".join(
            _update_line(r, i in (0, len(rows) - 1)) for i, r in enumerate(rows)
        )
        return f'<ul class="tl">{body}</ul>'
    mid = rows[1:-1]
    inner = "".join(_update_line(r, False) for r in mid)
    return (
        '<ul class="tl">'
        + _update_line(rows[0], True)
        + f"<li><details><summary>{len(mid)} further update"
        + ("" if len(mid) == 1 else "s")
        + f"</summary><ul>{inner}</ul></details></li>"
        + _update_line(rows[-1], True)
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


def _day_cells(cells, ym, partial):
    # nothing to qualify on a day with no data or no colour yet
    return statusui.day_cells(cells, ym, partial, DAY_LABELS, qualify=lambda ch: ch not in "89")


def county_page(county, data, cases, ym, all_counties):
    m = data["stats"][county][ym]
    grade = m[1]
    label = month_label(ym)
    title = f"Power outages in County {county} — {label}"
    desc = (
        f"{m[4]} faults and {m[5]} planned power outages recorded in County {county} "
        f"during {label}, from ESB Networks' PowerCheck feed."
    )
    tiles = [
        ("–" if m[2] is None else f"{m[2]:g}%", "back within 4 hours"),
        (m[4], "faults"),
        (m[5], "planned outages"),
        (f"{m[6]:,}", "customers hit by faults"),
    ]
    shown = cases[:COUNTY_PAGE_CASES]
    body = [
        '<a class="back" href="../index.html">← All counties</a>',
        f'<div class="chead"><span class="gradechip g-{grade or "none"}">{grade or "–"}</span>',
        f"<h1>County {html.escape(county)}</h1></div>",
        f'<div class="sub">{label} · {data["customers"][county]:,} customers '
        "(estimated from Census population)<br>"
        # This page is entered cold from a search result, so it has to carry the
        # same caveat the app does: the day bar ends where the data does.
        f'Data to {html.escape(data["observed"])}'
        + (
            ' · <span class="stale">collection has stopped</span>'
            if data["stale"]
            else ""
        )
        + "</div>",
        f'<div class="card"><div class="bar tall">'
        f'{_day_cells(m[0], ym, data["partial"])}</div>'
        '<div class="daycap"></div><div class="tiles">',
        "".join(
            f'<div class="tile"><div class="v">{v}</div><div class="k">{k}</div></div>'
            for v, k in tiles
        ),
        "</div></div>",
    ]
    if shown:
        body.append(f'<div class="card"><h2>Outages in {label}</h2>')
        body.append("".join(_case_html(k) for k in shown))
        if len(cases) > len(shown):
            body.append(
                f'<p class="empty" style="padding-top:12px">'
                f"{len(cases) - len(shown)} more not shown here — "
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
    """A template with the shared UI and this site's stylesheet inlined, then its markers."""
    markers = dict(markers, **{"SITE-CSS": SITE_CSS.read_text(encoding="utf-8")})
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
