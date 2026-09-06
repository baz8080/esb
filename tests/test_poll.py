import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from esb_outages import alert
from esb_outages.client import ApiError, AuthError, TransientError
from esb_outages.poll import poll_lock, run_check, run_poll
from esb_outages.store import Store

from .helpers import FakeClient, detail, make_list, one_shot_server


class PollTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        # A shell that has sourced the Pi's env file would otherwise send every
        # fake poll's alarm and heartbeat to the real channels.
        self._env = unittest.mock.patch.dict(os.environ)
        self._env.start()
        os.environ.pop("ESB_ALERT_WEBHOOK", None)
        os.environ.pop("ESB_HEARTBEAT_URL", None)

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def poll(self, client):
        return run_poll(self.data_dir, client=client, delay_ms=0)

    def store(self):
        return Store(self.data_dir).open()

    def client_with(self, *kinds):
        details = {detail(k)["outageId"]: detail(k) for k in kinds}
        return FakeClient(list_body=make_list(*[detail(k) for k in kinds]), details=details)


class TestHappyPath(PollTestCase):
    def test_successful_run_exits_zero_and_stores_everything(self):
        client = self.client_with("fault", "planned", "restored")
        self.assertEqual(self.poll(client), alert.EXIT_OK)

        with self.store() as st:
            stats = st.stats()
        self.assertEqual(stats["outages"], 3)
        self.assertEqual(stats["detailed"], 3)
        self.assertEqual(stats["final"], 1)
        self.assertEqual(stats["runs"], 1)

    def test_second_run_skips_finalised_outages(self):
        # The efficiency guarantee: restored outages are never re-fetched.
        client = self.client_with("fault", "planned", "restored")
        self.poll(client)
        client.detail_calls.clear()
        self.poll(client)

        self.assertNotIn(detail("restored")["outageId"], client.detail_calls)
        self.assertEqual(len(client.detail_calls), 2)

    def test_raw_log_records_every_response(self):
        self.poll(self.client_with("fault", "restored"))
        with self.store() as st:
            runs = list(st.iter_raw("runs"))
            obs = list(st.iter_raw("observations"))
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["list_body"], make_list(detail("fault"), detail("restored")))
        self.assertEqual(len(obs), 2)


class TestFailurePaths(PollTestCase):
    def test_rejected_key_exits_two(self):
        client = FakeClient(list_error=AuthError("401 rejected"))
        self.assertEqual(self.poll(client), alert.EXIT_AUTH)

    def test_unreachable_api_exits_three(self):
        client = FakeClient(list_error=TransientError("connection refused"))
        self.assertEqual(self.poll(client), alert.EXIT_UNREACHABLE)

    def test_failures_are_still_recorded_in_the_run_table(self):
        self.poll(FakeClient(list_error=AuthError("401 rejected")))
        with self.store() as st:
            row = st.conn.execute("SELECT * FROM run").fetchone()
        self.assertEqual(row["status"], "auth_error")
        self.assertEqual(row["exit_code"], alert.EXIT_AUTH)

    def test_schema_drift_exits_four(self):
        body = dict(detail("fault"))
        body["brandNewField"] = "surprise"
        client = FakeClient(
            list_body=make_list(detail("fault")), details={body["outageId"]: body}
        )
        self.assertEqual(self.poll(client), alert.EXIT_SCHEMA_DRIFT)

    def test_drifted_response_is_still_written_to_the_raw_log(self):
        # Exiting non-zero must not mean discarding data.
        body = dict(detail("fault"))
        body["brandNewField"] = "surprise"
        client = FakeClient(
            list_body=make_list(detail("fault")), details={body["outageId"]: body}
        )
        self.poll(client)
        with self.store() as st:
            obs = list(st.iter_raw("observations"))
        self.assertEqual(obs[0]["body"]["brandNewField"], "surprise")

    def test_purged_outage_is_normal_and_does_not_fail_the_run(self):
        # 404 between the list call and the detail call is expected behaviour.
        client = FakeClient(list_body=make_list(detail("fault")), details={})
        self.assertEqual(self.poll(client), alert.EXIT_OK)
        with self.store() as st:
            row = st.conn.execute("SELECT * FROM outage").fetchone()
            obs = list(st.iter_raw("observations"))
        # The stub survives with its coordinates from the list response.
        self.assertEqual(row["has_detail"], 0)
        self.assertIsNotNone(row["lat"])
        self.assertEqual(obs[0]["http_status"], 404)

    def synthetic_outages(self, n, failing=0):
        """n distinct live outages, the first `failing` of which error out."""
        template = detail("fault")
        bodies = [
            dict(template, outageId=str(9000000 + i), location=f"Place {i}")
            for i in range(n)
        ]
        return FakeClient(
            list_body=make_list(*bodies),
            details={b["outageId"]: b for b in bodies},
            detail_errors={
                b["outageId"]: TransientError("boom") for b in bodies[:failing]
            },
        )

    def test_broad_failure_exits_five(self):
        self.assertEqual(
            self.poll(self.synthetic_outages(10, failing=6)), alert.EXIT_PARTIAL
        )

    def test_isolated_failures_do_not_fail_the_run(self):
        # Not data loss: these outages stay listed and unfinalised, so the next
        # run retries them. Alerting here would just train us to ignore emails.
        self.assertEqual(
            self.poll(self.synthetic_outages(10, failing=2)), alert.EXIT_OK
        )

    def test_a_single_failure_on_a_tiny_run_does_not_fail_the_run(self):
        # 1 of 3 is 33%, over the ratio, but well under the absolute floor.
        self.assertEqual(
            self.poll(self.synthetic_outages(3, failing=1)), alert.EXIT_OK
        )

    def test_failed_outages_are_retried_on_the_next_run(self):
        failing = self.synthetic_outages(4, failing=2)
        self.poll(failing)
        healthy = self.synthetic_outages(4, failing=0)
        self.poll(healthy)
        # All four still needed fetching: none were finalised by the failed run.
        self.assertEqual(len(healthy.detail_calls), 4)
        with self.store() as st:
            self.assertEqual(st.stats()["detailed"], 4)

    def test_key_dying_mid_run_aborts_immediately(self):
        # No point burning hundreds of guaranteed-failing requests.
        kinds = ["fault", "planned", "restored"]
        details = {detail(k)["outageId"]: detail(k) for k in kinds}
        first_id = make_list(*[detail(k) for k in kinds])["outageMessage"][0]["i"]
        client = FakeClient(
            list_body=make_list(*[detail(k) for k in kinds]),
            details=details,
            detail_errors={first_id: AuthError("401 mid-run")},
        )
        self.assertEqual(self.poll(client), alert.EXIT_AUTH)
        self.assertEqual(len(client.detail_calls), 1)


class TestUnwritableDataDir(PollTestCase):
    @unittest.skipIf(os.geteuid() == 0, "root bypasses permission checks")
    def test_readonly_directory_exits_six_without_a_traceback(self):
        # The directory exists but the process cannot write to it: a full disk,
        # or an owner that does not match the user the collector runs as.
        target = self.data_dir / "readonly"
        target.mkdir()
        os.chmod(target, 0o500)
        try:
            client = self.client_with("fault")
            self.assertEqual(
                run_poll(target, client=client, delay_ms=0), alert.EXIT_STORAGE
            )
            # Fails before touching the network: nothing to report on.
            self.assertEqual(client.list_calls, 0)
        finally:
            os.chmod(target, 0o700)

    def test_leaves_no_probe_file_behind(self):
        self.poll(self.client_with("fault"))
        self.assertFalse((self.data_dir / ".write-test").exists())


class TestLocking(PollTestCase):
    def test_second_run_backs_off_while_first_holds_the_lock(self):
        with poll_lock(self.data_dir) as acquired:
            self.assertTrue(acquired)
            client = self.client_with("fault")
            # Exits 0: an overlapping trigger is not a failure worth emailing about.
            self.assertEqual(self.poll(client), alert.EXIT_OK)
            self.assertEqual(client.list_calls, 0)

    def test_lock_is_released_afterwards(self):
        with poll_lock(self.data_dir) as acquired:
            self.assertTrue(acquired)
        with poll_lock(self.data_dir) as acquired:
            self.assertTrue(acquired)


class TestWebhookAlerting(unittest.TestCase):
    """The webhook is the alerting channel; failures must reach it."""

    def setUp(self):
        self.received = []
        self.url, self.server, self.thread = one_shot_server(self.received)

    def tearDown(self):
        self.thread.join(1)
        self.server.server_close()

    def test_failure_is_pushed_to_the_webhook(self):
        with unittest.mock.patch.dict(os.environ, {"ESB_ALERT_WEBHOOK": self.url}):
            alert.fail(alert.auth_banner("abc...xyz"), alert.EXIT_AUTH)
        self.assertEqual(len(self.received), 1)
        self.assertIn("SUBSCRIPTION KEY REJECTED", self.received[0][1])

    def test_notify_reports_delivery(self):
        with unittest.mock.patch.dict(os.environ, {"ESB_ALERT_WEBHOOK": self.url}):
            self.assertTrue(alert.notify("hello"))

    def test_notify_is_a_no_op_when_unconfigured(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(alert.notify("hello"))

    def test_unreachable_webhook_does_not_raise(self):
        # Alerting must never be able to break the run it is reporting on.
        with unittest.mock.patch.dict(
            os.environ, {"ESB_ALERT_WEBHOOK": "http://127.0.0.1:9/dead"}
        ):
            self.assertFalse(alert.notify("hello"))


class TestHeartbeat(PollTestCase):
    """The ping a dead-man's monitor waits for: sent whenever a run reached
    the feed, and never when it did not. The ping is synchronous, so what
    the server saw is final the moment poll() returns."""

    def setUp(self):
        super().setUp()
        self.pings = []
        self.url, self.server, self.thread = one_shot_server(self.pings, method="GET")
        os.environ["ESB_HEARTBEAT_URL"] = self.url

    def tearDown(self):
        self.thread.join(1)
        self.server.server_close()
        super().tearDown()

    def paths(self):
        return [path for path, _ in self.pings]

    def test_a_clean_run_pings(self):
        self.assertEqual(self.poll(self.client_with("fault")), alert.EXIT_OK)
        self.assertEqual(self.paths(), ["/hook"])

    def test_a_drifted_run_still_pings(self):
        # the list is on disk and the webhook carries the drift; silence would
        # raise a second alarm for a collector that is running
        body = dict(detail("fault"))
        body["brandNewField"] = "surprise"
        client = FakeClient(
            list_body=make_list(detail("fault")), details={body["outageId"]: body}
        )
        self.assertEqual(self.poll(client), alert.EXIT_SCHEMA_DRIFT)
        self.assertEqual(self.paths(), ["/hook"])

    def test_a_rejected_key_does_not_ping(self):
        self.poll(FakeClient(list_error=AuthError("401 rejected")))
        self.assertEqual(self.paths(), [])

    def test_an_unreachable_feed_does_not_ping(self):
        self.poll(FakeClient(list_error=TransientError("connection refused")))
        self.assertEqual(self.paths(), [])

    def test_a_skipped_trigger_does_not_ping(self):
        with poll_lock(self.data_dir) as acquired:
            self.assertTrue(acquired)
            self.poll(self.client_with("fault"))
        self.assertEqual(self.paths(), [])

    def test_unconfigured_is_a_no_op(self):
        del os.environ["ESB_HEARTBEAT_URL"]
        self.assertFalse(alert.heartbeat())
        self.assertEqual(self.poll(self.client_with("fault")), alert.EXIT_OK)
        self.assertEqual(self.paths(), [])

    def test_a_dead_monitor_does_not_change_the_exit_code(self):
        os.environ["ESB_HEARTBEAT_URL"] = "http://127.0.0.1:9/dead"
        self.assertFalse(alert.heartbeat())
        self.assertEqual(self.poll(self.client_with("fault")), alert.EXIT_OK)


class TestCheck(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(run_check(FakeClient(list_body=make_list(detail("fault")))), alert.EXIT_OK)

    def test_bad_key(self):
        self.assertEqual(run_check(FakeClient(list_error=AuthError("401"))), alert.EXIT_AUTH)

    def test_unreachable(self):
        self.assertEqual(
            run_check(FakeClient(list_error=ApiError("418 teapot"))), alert.EXIT_UNREACHABLE
        )

    def test_drift(self):
        self.assertEqual(
            run_check(FakeClient(list_body={"nope": []})), alert.EXIT_SCHEMA_DRIFT
        )


if __name__ == "__main__":
    unittest.main()
