"""Failure signalling.

Failures are pushed to ESB_ALERT_WEBHOOK, and the exit code carries the same
information for whatever is running the collector. Since this project's whole
failure mode is stopping silently while ESB keeps purging data, an alert has to
stand on its own: what broke, and what to do about it. Nobody reading one of
these has the context of this repository in front of them.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

EXIT_OK = 0
EXIT_CRASH = 1
EXIT_AUTH = 2
EXIT_UNREACHABLE = 3
EXIT_SCHEMA_DRIFT = 4
EXIT_PARTIAL = 5
EXIT_STORAGE = 6

EXIT_MEANINGS = {
    EXIT_OK: "success",
    EXIT_CRASH: "collector crashed",
    EXIT_AUTH: "API subscription key rejected",
    EXIT_UNREACHABLE: "ESB API unreachable",
    EXIT_SCHEMA_DRIFT: "API response shape changed",
    EXIT_PARTIAL: "too many detail fetches failed",
    EXIT_STORAGE: "data directory not writable",
}


BANNER_WIDTH = 78

# Discord rejects a message over 2,000 characters outright; ntfy allows 4,096.
MAX_ALERT_CHARS = 1900
TRUNCATED = "\n[truncated; the full text is in the journal]"


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
            "  4. Set ESB_API_KEY to it in /etc/esb-outages.env",
            "  5. Confirm it works:  sudo esb check",
            "",
            f"Raw error: {detail}" if detail else "",
        ],
    )


def unreachable_banner(detail: str) -> str:
    return banner(
        "ESB POLLER: API UNREACHABLE",
        [
            "The outage list endpoint could not be reached after retries.",
            "If this clears on the next run, no action is needed - a",
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
            "Collection has stopped. Usual causes are a full disk, or the",
            "directory not being owned by the user the collector runs as.",
            "",
            "Check:",
            f"  df -h {data_dir}",
            f"  ls -ld {data_dir}",
            f"  sudo chown -R esb:esb {data_dir}",
        ],
    )


def crash_banner(exc: BaseException) -> str:
    return banner(
        "ESB POLLER: RUN CRASHED",
        [
            "The collector hit an error it has no handling for and stopped",
            "partway through the run. The traceback is in the journal:",
            "  journalctl -u esb-outages.service -n 50",
            "",
            "If the database is at fault, this re-derives it from the raw",
            "logs:  sudo esb rebuild",
            "If the rebuild fails the same way, or the next run crashes",
            "again, the code needs a fix; rebuild again once it has one.",
            "",
            f"Raw error: {type(exc).__name__}: {exc}",
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


def _deliver(what: str, url: str, data: bytes | None = None, headers=None) -> bool:
    """Best effort, in one place: a failure to report must never mask the
    problem being reported or change the exit code."""
    try:
        # Built in here: a URL missing its scheme raises from the constructor.
        request = urllib.request.Request(url, data=data, headers=headers or {})
        urllib.request.urlopen(request, timeout=10).close()
        return True
    except Exception as exc:
        print(f"warning: {what} failed: {_describe(exc)}", file=sys.stderr)
        return False


def _describe(exc: Exception) -> str:
    # Never str(exc): the URL is the secret (an ntfy topic, a ping id), and
    # urllib and http.client quote it, or its path, in their messages.
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, OSError):
        return f"{type(reason).__name__}: {reason.strerror or 'no detail'}"
    if isinstance(reason, ValueError):
        return f"{type(reason).__name__} (check the URL's form)"
    # A URLError's reason can be a bare string, which may quote the URL.
    return type(reason if isinstance(reason, Exception) else exc).__name__


def notify(message: str) -> bool:
    """Push to ESB_ALERT_WEBHOOK. Returns whether it was delivered."""
    url = os.environ.get("ESB_ALERT_WEBHOOK")
    if not url:
        return False
    if len(message) > MAX_ALERT_CHARS:
        message = message[: MAX_ALERT_CHARS - len(TRUNCATED)] + TRUNCATED
    if "ntfy" in url:
        data, headers = message.encode("utf-8"), {"Title": "ESB poller failure"}
    else:
        data = json.dumps({"content": message, "text": message}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
    return _deliver("alert webhook", url, data, headers)


def heartbeat() -> bool:
    """Ping ESB_HEARTBEAT_URL. Returns whether it was delivered.

    The webhook reports failures the collector can see. A Pi that is off, a
    disabled timer, a dead card or a lost uplink reports nothing, so a
    dead-man's monitor watches for this ping instead and alerts on silence.
    """
    url = os.environ.get("ESB_HEARTBEAT_URL")
    if not url:
        return False
    return _deliver("heartbeat ping", url)


def fail(message: str, code: int) -> int:
    """Print a fatal banner to stderr, fire the optional webhook, return the code."""
    print(message, file=sys.stderr)
    notify(message)
    return code
