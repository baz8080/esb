"""Failure signalling.

The primary alerting channel is the process exit code. Synology's Task Scheduler
option "Send run details only when the script terminates abnormally" emails the
captured output of any task that exits non-zero, which means correct exit codes
buy us alerting with no SMTP config, no secrets in the repo, and nothing extra to
keep running.

Because that email contains only what we printed, every fatal message has to
stand on its own: what broke, and what to do about it.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

EXIT_OK = 0
EXIT_AUTH = 2
EXIT_UNREACHABLE = 3
EXIT_SCHEMA_DRIFT = 4
EXIT_PARTIAL = 5
EXIT_STORAGE = 6

EXIT_MEANINGS = {
    EXIT_OK: "success",
    EXIT_AUTH: "API subscription key rejected",
    EXIT_UNREACHABLE: "ESB API unreachable",
    EXIT_SCHEMA_DRIFT: "API response shape changed",
    EXIT_PARTIAL: "too many detail fetches failed",
    EXIT_STORAGE: "data directory not writable",
}


BANNER_WIDTH = 78


def banner(title: str, lines: list[str]) -> str:
    # Fixed width: these end up in an email, and a long raw error message would
    # otherwise stretch the rule far past anything readable.
    bar = "!" * BANNER_WIDTH
    out = [bar, f"!!! {title}", bar, ""]
    out.extend(line for line in lines if line is not None)
    out.append("")
    return "\n".join(out)


def auth_banner(masked_key: str, detail: str = "") -> str:
    return banner(
        "ESB POLLER FATAL: API SUBSCRIPTION KEY REJECTED (HTTP 401)",
        [
            f"The key currently in use ({masked_key}) is no longer accepted.",
            "No outage data is being collected. ESB purges outages a few hours",
            "after restoration, so every hour this stays broken is data lost",
            "permanently.",
            "",
            "To fix:",
            "  1. Open https://powercheck.esbnetworks.ie in a browser.",
            "  2. Open developer tools -> Network, and reload the map.",
            "  3. Find a request to api.esb.ie and copy the value of the",
            "     'API-Subscription-Key' request header.",
            "  4. Set it on the Synology task, e.g.:",
            "       docker run --rm -e ESB_API_KEY=<newkey> ...",
            "  5. Run the task manually and confirm it exits 0.",
            "",
            f"Raw error: {detail}" if detail else "",
        ],
    )


def unreachable_banner(detail: str) -> str:
    return banner(
        "ESB POLLER: API UNREACHABLE",
        [
            "The outage list endpoint could not be reached after retries.",
            "If this clears on the next hourly run, no action is needed - a",
            "single miss is covered by the ~4h retention window. Repeated",
            "failures mean data is being lost.",
            "",
            f"Raw error: {detail}",
        ],
    )


def schema_banner(problems: list[str]) -> str:
    return banner(
        "ESB POLLER: API SCHEMA CHANGED",
        [
            "The API returned a shape this collector does not recognise:",
            *[f"  - {p}" for p in problems],
            "",
            "Raw responses were still written to the JSONL log verbatim, so no",
            "data has been lost. Update esb_outages/parse.py to handle the new",
            "shape, then run 'rebuild' to re-derive the database.",
        ],
    )


def storage_banner(data_dir, problem: str) -> str:
    return banner(
        "ESB POLLER: DATA DIRECTORY NOT WRITABLE",
        [
            f"{problem}",
            "",
            "Nothing was collected. The usual cause is a Docker bind mount: the",
            "host directory's ownership replaces the image's, and this container",
            "runs as uid 1000 rather than root.",
            "",
            "Fix on the NAS:",
            "  sudo chown -R 1000:1000 /volume1/docker/esb/data",
        ],
    )


def partial_banner(failed: int, attempted: int, errors: list[str]) -> str:
    return banner(
        "ESB POLLER: PARTIAL DATA LOSS",
        [
            f"{failed} of {attempted} detail fetches failed this run.",
            "Outages seen in the list but never fetched may be purged before",
            "the next run.",
            "",
            "Errors:",
            *[f"  - {e}" for e in errors[:10]],
        ],
    )


def notify(message: str) -> None:
    """Optional secondary channel, off unless ESB_ALERT_WEBHOOK is set.

    Best-effort by design: a webhook failure must never mask the underlying
    problem or change the exit code.
    """
    url = os.environ.get("ESB_ALERT_WEBHOOK")
    if not url:
        return
    try:
        if "ntfy" in url:
            data, headers = message.encode("utf-8"), {"Title": "ESB poller failure"}
        else:
            data = json.dumps({"content": message, "text": message}).encode("utf-8")
            headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=10).close()
    except Exception as exc:  # pragma: no cover - never let alerting break the run
        print(f"warning: alert webhook failed: {exc}", file=sys.stderr)


def fail(message: str, code: int) -> int:
    """Print a fatal banner to stderr, fire the optional webhook, return the code."""
    print(message, file=sys.stderr)
    notify(message)
    return code
