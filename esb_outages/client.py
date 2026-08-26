"""HTTP client for the ESB PowerCheck API.

Stdlib only, deliberately: this job has to keep running unattended for years and
every dependency is a future breakage. The error taxonomy here drives the process
exit code and the alert that gets pushed, so the distinctions it draws are the
ones a human will be woken by.
"""

from __future__ import annotations

import gzip
import json
import os
import random
import time
import urllib.error
import urllib.request

BASE_URL = "https://api.esb.ie/esbn/powercheck/v1.0"

# The key is de-facto public: it ships in the JavaScript of the PowerCheck site
# and is visible in any browser's network tab. It is embedded here so the tool
# works out of the box, and so that the alerting path fires loudly if ESB ever
# rotates it. Override with ESB_API_KEY.
DEFAULT_API_KEY = "f713e48af3a746bbb1b110ab69113960"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/26.5.2 Safari/605.1.15"
)

DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 3


class EsbError(Exception):
    """Base for all API errors."""


class AuthError(EsbError):
    """HTTP 401 - the subscription key was rejected or missing.

    Never retried: a rejected key will not start working on the next attempt.
    """


class NotFound(EsbError):
    """HTTP 404 - outage ID unknown.

    Routine, not exceptional: an outage can be purged in the seconds between the
    list call and its detail call.
    """


class TransientError(EsbError):
    """Network failure, timeout, or 5xx. Retried with backoff."""


class ApiError(EsbError):
    """Any other unexpected HTTP status."""


def _decode(raw: bytes, headers) -> str:
    """Decode a response body.

    The API gzips every response and ignores Accept-Encoding entirely (identity,
    gzip, and omitting the header all come back gzipped), so this checks the
    actual Content-Encoding rather than trusting what we asked for.
    """
    encoding = (headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding:
        raw = gzip.decompress(raw)
    return raw.decode("utf-8")


class EsbClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        sleep=time.sleep,
    ):
        self.api_key = api_key or os.environ.get("ESB_API_KEY") or DEFAULT_API_KEY
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self._sleep = sleep

    @property
    def masked_key(self) -> str:
        k = self.api_key
        if len(k) <= 10:
            return "***"
        return f"{k[:6]}...{k[-4:]}"

    def _request(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "User-Agent": USER_AGENT,
                "API-Subscription-Key": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return _decode(resp.read(), resp.headers)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = _decode(exc.read(), exc.headers)
            except Exception:  # pragma: no cover - body is best-effort context
                pass
            if exc.code == 401:
                raise AuthError(f"401 rejected key {self.masked_key}: {body}") from exc
            if exc.code == 404:
                raise NotFound(f"404 for {url}") from exc
            if exc.code >= 500:
                raise TransientError(f"{exc.code} from {url}: {body}") from exc
            raise ApiError(f"{exc.code} from {url}: {body}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransientError(f"network failure for {url}: {exc}") from exc

    def get_json(self, path: str) -> dict:
        """GET a path, retrying transient failures with exponential backoff."""
        url = f"{self.base_url}{path}"
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                return json.loads(self._request(url))
            except TransientError as exc:
                last = exc
                if attempt < self.retries - 1:
                    # Jitter so a NAS rebooting mid-incident doesn't sync up with
                    # any other client retrying against the same endpoint.
                    self._sleep(2**attempt + random.random())
            except json.JSONDecodeError as exc:
                raise ApiError(f"malformed JSON from {url}: {exc}") from exc
        raise last  # type: ignore[misc]

    def get_outage_list(self) -> dict:
        return self.get_json("/outages")

    def get_outage_detail(self, outage_id: str) -> dict:
        return self.get_json(f"/outages/{outage_id}/")
