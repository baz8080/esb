"""CLI entry point: python -m esb_outages <command>"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__, alert
from .client import EsbClient
from .poll import run_check, run_poll
from .store import Store

DEFAULT_DATA_DIR = os.environ.get("ESB_DATA_DIR", "/data")


def _human_bytes(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} GiB"


def cmd_stats(args) -> int:
    with Store(args.data_dir) as store:
        s = store.stats()
    print(f"outages tracked : {s['outages']}")
    print(f"  with detail   : {s['detailed']}")
    print(f"  finalised     : {s['final']}")
    print(f"  DST-ambiguous : {s['tz_ambiguous']}")
    for outage_type, n in s["by_type"]:
        print(f"    {outage_type or '(unknown)':<10} {n}")
    print(f"field changes   : {s['changes']}")
    print(f"runs recorded   : {s['runs']}")
    print(f"coverage        : {s['first_run'] or '-'} .. {s['last_run'] or '-'}")
    print(f"raw log size    : {_human_bytes(s['raw_bytes'])}")
    print(f"database size   : {_human_bytes(s['db_bytes'])}")

    fetched, skipped = s["total_fetched"], s["total_skipped"]
    if fetched or skipped:
        pct = skipped / (fetched + skipped) * 100
        print(
            f"\ndetail fetches  : {fetched} made, {skipped} skipped ({pct:.0f}% avoided)"
        )
    if s["recent_runs"]:
        print("\nrecent runs:")
        print(
            f"  {'started':<21}{'status':<9}{'listed':>7}"
            f"{'fetched':>9}{'cached':>8}{'errors':>8}"
        )
        for r in s["recent_runs"]:
            print(
                f"  {r['started_at_utc']:<21}{r['status'] or '':<9}"
                f"{r['n_listed'] if r['n_listed'] is not None else '-':>7}"
                f"{r['n_detail_fetched'] if r['n_detail_fetched'] is not None else '-':>9}"
                f"{r['n_detail_skipped'] if r['n_detail_skipped'] is not None else '-':>8}"
                f"{r['n_errors'] if r['n_errors'] is not None else '-':>8}"
            )
    return alert.EXIT_OK


def cmd_test_alert(args) -> int:
    """Fire a real alert through the real channel.

    Exists because an untested alarm is not an alarm, and the alternative way to
    test it - deliberately breaking the API key - stops collection while you do.
    """
    if not os.environ.get("ESB_ALERT_WEBHOOK"):
        print(
            "ESB_ALERT_WEBHOOK is not set, so failures would reach nobody.\n"
            "Set it in /etc/esb-outages.env, e.g. an ntfy.sh topic URL.",
            file=sys.stderr,
        )
        return 1
    message = alert.banner(
        "ESB POLLER: TEST ALERT",
        [
            "This is a test. Nothing is wrong.",
            "",
            "If you are reading this, a real failure would have reached you too.",
        ],
    )
    print(message)
    if not alert.notify(message):
        print("alert delivery FAILED - see the warning above", file=sys.stderr)
        return 1
    print("alert delivered")
    return alert.EXIT_OK


def cmd_rebuild(args) -> int:
    with Store(args.data_dir) as store:
        result = store.rebuild(verbose=True)
    if result["runs"] == 0 and result["observations"] == 0:
        print("nothing to replay: no raw logs found", file=sys.stderr)
    return alert.EXIT_OK


def cmd_compact(args) -> int:
    with Store(args.data_dir) as store:
        done = store.compact()
    print(f"compacted {len(done)} file(s): {', '.join(done) or 'none'}")
    return alert.EXIT_OK


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="esb_outages", description="Collect ESB Networks outage data."
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR, help="storage root (env: ESB_DATA_DIR)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_poll = sub.add_parser("poll", help="run one collection pass (the scheduled command)")
    p_poll.add_argument(
        "--delay-ms", type=int, default=None,
        help="pause between detail requests (env: ESB_POLL_DELAY_MS, default 1000)",
    )
    sub.add_parser("check", help="verify the API key and connectivity; writes nothing")
    sub.add_parser("test-alert", help="send a test alert through ESB_ALERT_WEBHOOK")
    sub.add_parser("rebuild", help="rebuild the database from the raw JSONL logs")
    sub.add_parser("stats", help="summarise what has been collected")
    sub.add_parser("compact", help="gzip raw logs from previous months")

    args = parser.parse_args(argv)

    if args.command == "poll":
        return run_poll(args.data_dir, delay_ms=args.delay_ms)
    if args.command == "check":
        return run_check(EsbClient())
    if args.command == "test-alert":
        return cmd_test_alert(args)
    if args.command == "rebuild":
        return cmd_rebuild(args)
    if args.command == "stats":
        return cmd_stats(args)
    if args.command == "compact":
        return cmd_compact(args)
    return alert.EXIT_OK  # pragma: no cover - argparse enforces a command


if __name__ == "__main__":
    sys.exit(main())
