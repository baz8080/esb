import gzip
import http.client
import unittest
from unittest import mock

from esb_outages.client import ApiError, EsbClient, TransientError


class _Response:
    def __init__(self, read, encoding="gzip"):
        self._read = read
        self.headers = {"Content-Encoding": encoding}

    def read(self):
        return self._read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _raise(exc):
    def read():
        raise exc
    return read


class TestFailuresStayInTheTaxonomy(unittest.TestCase):
    """Anything else escapes the run: no run record, no heartbeat, a traceback."""

    def request(self, response):
        client = EsbClient(retries=1, sleep=lambda s: None)
        with mock.patch("urllib.request.urlopen", return_value=response):
            return client.get_json("/outages")

    def test_a_body_cut_off_mid_read_is_transient(self):
        with self.assertRaises(TransientError):
            self.request(_Response(_raise(http.client.IncompleteRead(b"{"))))

    def test_a_truncated_gzip_body_is_transient(self):
        cut = gzip.compress(b'{"outageMessage": []}')[:-8]
        with self.assertRaises(TransientError):
            self.request(_Response(lambda: cut))

    def test_a_body_that_is_not_utf8_is_an_api_error(self):
        with self.assertRaises(ApiError):
            self.request(_Response(lambda: b"\xff\xfe", encoding=""))


if __name__ == "__main__":
    unittest.main()
