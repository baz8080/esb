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
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import model

BASE_URL = "https://baz8080.github.io/esb"

TEMPLATES = Path(__file__).parent
SITE_HTML = TEMPLATES / "site.html"
COUNTY_HTML = TEMPLATES / "county.html"

CANONICAL = "<!--CANONICAL-->"
TITLE, DESC, BODY = "<!--TITLE-->", "<!--DESC-->", "<!--BODY-->"

# How many outages a server-rendered county page carries. The page exists so
# that a county has a real URL for a search engine and a reader arriving cold;
# the full month lives in the shard the app loads.
COUNTY_PAGE_CASES = 40

# How an outage's end is described, per the source the end time came from. The
# distinction matters to a reader: only the first is something ESB confirmed.
END_LABEL = {
    "restored": "restored {when}",
    "estimated": "due back {when}",
    "listed": "last seen out at {when}",
}

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def slug(county):
    return "".join(c if c.isalnum() else "-" for c in county.lower()).strip("-")


def month_label(ym):
    return f"{MONTH_NAMES[int(ym[5:7]) - 1]} {ym[:4]}"


def _dumps(obj):
    # Default separators spend a byte on every comma and colon in the payload.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _stamp(dt):
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _short(dt):
    """Timestamps are rendered, never computed on, so minutes are enough."""
    return dt.strftime("%Y-%m-%dT%H:%M") if dt else None


def build(outages, sa_index, now):
    """Assemble every value the templates need, and nothing they do not."""
    months = model.month_list(model.COLLECTION_START, now)
    national_rate = model.national_cml(outages, now)

    by_county = defaultdict(list)
    for o in outages:
        by_county[o.county].append(o)

    stats, national = {}, {}
    for county in sa_index.counties:
        rows = by_county.get(county, [])
        per_month = {}
        for ym in months:
            s = model.county_month(
                rows, county, sa_index.customers[county], ym, now, national_rate
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
        lo, hi = model.observed_window(ym, now)
        live = [o for o in outages if o.start and o.end and o.end > lo and o.start < hi]
        faults = [o for o in live if not o.planned]
        judged = [o for o in faults if o.start >= lo and o.end <= hi]
        seen = sum(o.customers for o in judged)
        within = sum(
            o.customers
            for o in judged
            if o.minutes / 60.0 <= model.CHARTER_TARGET_HOURS
        )
        national[ym] = [
            round(model.national_cml(outages, now, ym), 1),
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
    return data, by_county, months, national_rate, search


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
        [
            [_short(u.at), u.kind, u.customers, _short_raw(u.est_restore), _short_raw(u.restore)]
            for u in o.updates
        ],
    ]


def _short_raw(value):
    """Timeline values arrive from the change log as text, already UTC ISO."""
    return value[:16] if value else None


def shard(county, outages, months):
    """Every outage in one county, grouped by the month it started in."""
    by_month = defaultdict(list)
    for o in sorted(outages, key=lambda o: o.start, reverse=True):
        ym = f"{o.start.year:04d}-{o.start.month:02d}"
        if ym in months:
            by_month[ym].append(case_record(o))
    return by_month


def _case_html(k):
    planned = k[2]
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
            _updates_html(k[8]),
            "</div>",
        ]
    )


def _update_line(u, key):
    bits = []
    if u[1]:
        bits.append(f"<b>{html.escape(u[1])}</b>")
    if u[2] is not None:
        bits.append(f"{u[2]:,} customers")
    if u[4]:
        bits.append(f"restored {_when(u[4])}")
    elif u[3]:
        bits.append(f"estimated {_when(u[3])}")
    cls = ' class="key"' if key else ""
    return f"<li{cls}><time>{_when(u[0])}</time>{' · '.join(bits)}</li>"


def _updates_html(ups):
    if not ups:
        return ""
    label = '<div class="tll">What ESB reported, and when we saw it</div>'
    if len(ups) <= model.INLINE_UPDATES:
        rows = "".join(
            _update_line(u, i in (0, len(ups) - 1)) for i, u in enumerate(ups)
        )
        return f'{label}<ul class="tl">{rows}</ul>'
    mid = ups[1:-1]
    inner = "".join(_update_line(u, False) for u in mid)
    return (
        label
        + '<ul class="tl">'
        + _update_line(ups[0], True)
        + f"<li><details><summary>{len(mid)} further update"
        + ("" if len(mid) == 1 else "s")
        + f"</summary><ul>{inner}</ul></details></li>"
        + _update_line(ups[-1], True)
        + "</ul>"
    )


def _when(ts):
    if not ts:
        return ""
    dt = datetime.fromisoformat(ts)
    return f"{dt.day} {MONTH_NAMES[dt.month - 1][:3]}, {dt:%H:%M}"


def _hours(h):
    if h < 1:
        return f"{round(h * 60)} min"
    if h < 48:
        return f"{h:.1f} h" if h < 10 else f"{round(h)} h"
    return f"{round(h / 24)} days"


DAY_LABELS = {
    "0": "no significant fault",
    "1": "minor fault disruption",
    "2": "moderate fault disruption",
    "3": "major fault disruption",
    "4": "severe fault disruption",
    "5": "planned works only",
    "8": "before this site started collecting",
    "9": "still to come",
}


def _day_cells(cells, ym):
    return "".join(
        f'<i class="b{ch}" title="{ym}-{i + 1:02d}: {DAY_LABELS[ch]}"></i>'
        for i, ch in enumerate(cells)
    )


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
        "(estimated from Census population)</div>",
        f'<div class="card"><div class="bar">{_day_cells(m[0], ym)}</div><div class="tiles">',
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

    page = COUNTY_HTML.read_text(encoding="utf-8")
    return (
        page.replace(TITLE, html.escape(title))
        .replace(DESC, html.escape(desc))
        .replace(CANONICAL, f"{BASE_URL}/c/{slug(county)}.html")
        .replace(BODY, "".join(body))
    )


def _sitemap(paths, lastmod):
    urls = "".join(
        f"<url><loc>{BASE_URL}/{p}</loc><lastmod>{lastmod}</lastmod></url>" for p in paths
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )


def write(site_dir, outages, sa_index, now):
    site_dir = Path(site_dir)
    (site_dir / "c").mkdir(parents=True, exist_ok=True)
    (site_dir / "h").mkdir(parents=True, exist_ok=True)

    data, by_county, months, national_rate, search = build(outages, sa_index, now)
    latest = months[-1]

    (site_dir / "index.html").write_text(
        SITE_HTML.read_text(encoding="utf-8").replace(CANONICAL, f"{BASE_URL}/"),
        encoding="utf-8",
    )
    (site_dir / "data.js").write_text(
        "window.ESB_DATA = " + _dumps(data) + ";\n", encoding="utf-8"
    )
    (site_dir / "search.js").write_text(
        "window.ESB_SEARCH = " + _dumps(search) + ";\n", encoding="utf-8"
    )

    for county in sa_index.counties:
        by_month = shard(county, by_county.get(county, []), months)
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
    (site_dir / "sitemap.xml").write_text(_sitemap(paths, lastmod), encoding="utf-8")
    (site_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8"
    )
    return data


def size_report(site_dir):
    """What a reader downloads before they touch anything.

    Printed on every build: the payload is the constraint this site keeps having
    to defend, and a regression belongs in the build log rather than in the
    field.
    """
    site_dir = Path(site_dir)
    initial = {p: (site_dir / p).stat().st_size for p in ("index.html", "data.js")}
    shards = sorted((site_dir / "h").glob("*.js"), key=lambda p: -p.stat().st_size)
    pages = list((site_dir / "c").glob("*.html"))
    lines = [
        f"  {'index.html':<16}{initial['index.html'] / 1024:8.1f} KB",
        f"  {'data.js':<16}{initial['data.js'] / 1024:8.1f} KB",
        f"  {'initial load':<16}{sum(initial.values()) / 1024:8.1f} KB"
        f"   (budget 500.0 KB)",
        f"  {'search.js':<16}{(site_dir / 'search.js').stat().st_size / 1024:8.1f} KB"
        f"   (on first keystroke)",
        f"  {'county pages':<16}{sum(p.stat().st_size for p in pages) / 1024:8.1f} KB"
        f"   ({len(pages)} files)",
        f"  {'shards':<16}{sum(p.stat().st_size for p in shards) / 1024:8.1f} KB"
        f"   ({len(shards)} files, largest {shards[0].name} at"
        f" {shards[0].stat().st_size / 1024:.1f} KB)",
    ]
    return sum(initial.values()), "\n".join(lines)
