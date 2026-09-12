import copy
import os
import signal
import sqlite3
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from esb_outages import alert
from esb_outages.client import ApiError, AuthError, TransientError
from esb_outages.poll import poll_lock, run_check, run_poll
from esb_outages.store import Store

from .helpers import FakeClient, detail, local_server, make_list, stop_server


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
        # No point burning hundreds of guaranteed-failing requests. The key
        # dies on the fault's fetch; the restored outage ranks ahead of it, so
        # what is asserted is that nothing follows the failure.
        kinds = ["fault", "planned", "restored"]
        details = {detail(k)["outageId"]: detail(k) for k in kinds}
        dying = detail("fault")["outageId"]
        client = FakeClient(
            list_body=make_list(*[detail(k) for k in kinds]),
            details=details,
            detail_errors={dying: AuthError("401 mid-run")},
        )
        self.assertEqual(self.poll(client), alert.EXIT_AUTH)
        self.assertEqual(client.detail_calls[-1], dying)
        self.assertEqual(len(client.detail_calls), 2)


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


def storm(n=30):
    """n fault bodies with distinct ids, shaped like ESB's."""
    base = detail("fault")
    bodies = []
    for i in range(n):
        b = copy.deepcopy(base)
        b["outageId"] = str(3000000 + i)
        bodies.append(b)
    return bodies


def storm_client(bodies, budget):
    """A feed that sends the process SIGTERM during the last fetch in `budget`,
    as systemd would; the collector's handler is what must catch it, and the
    next fetch must never start."""

    class StormClient(FakeClient):
        def get_outage_detail(inner, outage_id):
            if len(inner.detail_calls) == budget - 1:
                os.kill(os.getpid(), signal.SIGTERM)
            return super().get_outage_detail(outage_id)

    return StormClient(
        list_body=make_list(*bodies), details={b["outageId"]: b for b in bodies}
    )


class TestStorm(PollTestCase):
    """A storm lists more than one run can fetch. Simulated on 30 outages with
    a run stopped after ten, as the service timeout stops a real one."""

    N, BUDGET = 30, 10

    def ranked(self, listed, fetched=()):
        """ids_needing_detail over `listed` bodies after `fetched` have detail."""
        from esb_outages.parse import normalize_detail

        with self.store() as st:
            st.apply_list("2026-09-06T10:00:00Z", make_list(*listed)["outageMessage"])
            for b in fetched:
                st.apply_detail("2026-09-06T10:00:01Z", normalize_detail(b))
            return st.ids_needing_detail(
                [b["outageId"] for b in listed], now="2026-09-06T10:30:00Z"
            )

    def test_never_fetched_outages_go_before_rechecks(self):
        a, b = storm(2)
        self.assertEqual(self.ranked([a, b], fetched=[a]), [b["outageId"], a["outageId"]])

    def test_the_purge_clock_outranks_a_live_outage_never_seen(self):
        """ESB purges a few hours after restoration and not before: a live
        outage never fetched keeps its place in the feed while it is out, one
        listed Restored does not, whether never captured or just flipped."""
        live_new, restored_new, flipped = storm(3)
        restored_new["outageType"] = "Restored"
        self.ranked([flipped], fetched=[flipped])
        flipped_now = dict(flipped, outageType="Restored")
        order = self.ranked([live_new, restored_new, flipped_now])
        self.assertEqual(
            order, [restored_new["outageId"], flipped["outageId"], live_new["outageId"]]
        )

    def test_a_run_cut_short_records_itself_and_the_next_run_carries_on(self):
        bodies = storm(self.N)
        fetched = []
        for _ in range(3):
            c = storm_client(bodies, self.BUDGET)
            self.assertEqual(self.poll(c), alert.EXIT_OK)
            fetched.append(set(c.detail_calls))
        # each run fetched only outages no earlier run had, and three runs
        # covered the whole list
        self.assertEqual([len(f) for f in fetched], [self.BUDGET] * 3)
        self.assertEqual(len(set().union(*fetched)), self.N)
        with self.store() as st:
            statuses = [r["status"] for r in st.conn.execute(
                "SELECT status FROM run ORDER BY started_at_utc, run_id")]
            have = st.conn.execute(
                "SELECT COUNT(*) FROM outage WHERE has_detail = 1").fetchone()[0]
        # every run still had re-checks queued behind the new ones when the
        # stop landed, and every outage was captured by the third
        self.assertEqual(statuses, ["cut_short"] * 3)
        self.assertEqual(have, self.N)

    def test_the_stop_is_not_an_alarm(self):
        received = []
        url, server, thread = local_server(received)
        try:
            with unittest.mock.patch.dict(os.environ, {"ESB_ALERT_WEBHOOK": url}):
                self.assertEqual(self.poll(storm_client(storm(), self.BUDGET)), alert.EXIT_OK)
        finally:
            stop_server(server, thread)
        self.assertEqual(received, [])

    def test_a_run_stops_itself_at_its_budget(self):
        """The service timeout is a backstop and a failed unit; the run's own
        clock is what normally ends a storm run. A budget of nothing still
        fetches once, so progress is never zero."""
        bodies = storm(6)
        c = FakeClient(list_body=make_list(*bodies), details={b["outageId"]: b for b in bodies})
        self.assertEqual(run_poll(self.data_dir, client=c, delay_ms=0, budget_s=0), alert.EXIT_OK)
        self.assertEqual(len(c.detail_calls), 1)
        with self.store() as st:
            row = st.conn.execute("SELECT status, n_detail_fetched FROM run").fetchone()
        self.assertEqual((row["status"], row["n_detail_fetched"]), ("cut_short", 1))

    def test_each_detail_is_committed_as_it_lands(self):
        """A run killed outright, with no handler to close it out, must still
        leave the database knowing what it fetched. Checked from a second
        connection during the run, which sees only committed rows."""
        bodies = storm(6)
        db = self.data_dir / "esb.db"
        seen = []

        class Peeking(FakeClient):
            def get_outage_detail(inner, outage_id):
                other = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                seen.append(other.execute(
                    "SELECT COUNT(*) FROM outage WHERE has_detail = 1").fetchone()[0])
                other.close()
                return super().get_outage_detail(outage_id)

        self.poll(Peeking(list_body=make_list(*bodies),
                          details={b["outageId"]: b for b in bodies}))
        self.assertEqual(seen, list(range(6)))

    def test_the_handler_is_gone_after_the_run(self):
        self.poll(self.client_with("fault"))
        self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_DFL)


class TestWebhookAlerting(unittest.TestCase):
    """The webhook is the alerting channel; failures must reach it."""

    def setUp(self):
        self.received = []
        self.url, self.server, self.thread = local_server(self.received)

    def tearDown(self):
        stop_server(self.server, self.thread)

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
        self.url, self.server, self.thread = local_server(self.pings)
        os.environ["ESB_HEARTBEAT_URL"] = self.url

    def tearDown(self):
        stop_server(self.server, self.thread)
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

    def test_a_run_cut_short_still_pings(self):
        # a storm that outruns every run must not read as a stopped collector
        self.assertEqual(self.poll(storm_client(storm(), TestStorm.BUDGET)), alert.EXIT_OK)
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
