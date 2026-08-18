"""CLI entry point: python -m esb_site"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import model, render

DEFAULT_DATA_DIR = os.environ.get("ESB_DATA_DIR", "data")
DEFAULT_OUT = "out/site"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="esb_site", description="Build the static ESB outage status site."
    )
    parser.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR, help="collector storage root (env: ESB_DATA_DIR)"
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"output directory ({DEFAULT_OUT})")
    parser.add_argument(
        "--now",
        default=None,
        help="override the build clock, as an ISO UTC timestamp (for reproducible builds)",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.data_dir) / "esb.db"
    if not db_path.exists():
        print(
            f"no database at {db_path}\n"
            f"run: python -m esb_outages --data-dir {args.data_dir} rebuild",
            file=sys.stderr,
        )
        return 1

    now = (
        datetime.fromisoformat(args.now).replace(tzinfo=timezone.utc)
        if args.now
        else datetime.now(timezone.utc)
    )

    sa_index = model.SmallAreaIndex.load()
    outages, unplaced = model.load_outages(db_path, sa_index, now)
    if not outages:
        print("no placeable outages in the database", file=sys.stderr)
        return 1

    render.write(args.out, outages, sa_index, now)

    national = model.national_cml(outages, now)
    print(f"built {args.out} from {len(outages)} outages across {len(sa_index.counties)} counties")
    if unplaced:
        print(f"  {unplaced} outage(s) had coordinates too far from any Small Area to place")
    print(
        f"  national unplanned rate {national:.1f} CML/yr"
        f"  (ESB published {model.ESB_NATIONAL_CML} for 2024)"
    )
    total, report = render.size_report(args.out)
    print(report)
    if total > 500 * 1024:
        print("  WARNING: initial load is over the 500 KB budget", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
