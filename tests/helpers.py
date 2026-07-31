"""Shared test helpers: fixture loading and a scriptable fake API client."""

from __future__ import annotations

import json
from pathlib import Path

from esb_outages.client import AuthError, NotFound, TransientError

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def detail(kind: str):
    return load(f"detail_{kind}")


def make_list(*details, extra=None):
    """Build a list response consistent with the given detail payloads."""
    items = [
        {"i": d["outageId"], "t": d["outageType"], "p": d["point"]} for d in details
    ]
    if extra:
        items.extend(extra)
    return {"outageMessage": items}


class FakeClient:
    """Stands in for EsbClient. Records calls so caching can be asserted."""

    masked_key = "fake...key"

    def __init__(self, list_body=None, details=None, list_error=None, detail_errors=None):
        self.list_body = list_body if list_body is not None else {"outageMessage": []}
        self.details = details or {}
        self.list_error = list_error
        self.detail_errors = detail_errors or {}
        self.list_calls = 0
        self.detail_calls: list[str] = []

    def get_outage_list(self):
        self.list_calls += 1
        if self.list_error:
            raise self.list_error
        return self.list_body

    def get_outage_detail(self, outage_id):
        self.detail_calls.append(outage_id)
        err = self.detail_errors.get(outage_id)
        if err:
            raise err
        if outage_id not in self.details:
            raise NotFound(f"404 for {outage_id}")
        return self.details[outage_id]


__all__ = [
    "FIXTURES", "load", "detail", "make_list", "FakeClient",
    "AuthError", "NotFound", "TransientError",
]
