"""One collection run.

Ordering here is deliberate: the list response is written to the raw log before
any detail fetching begins, so a crash, a NAS reboot, or an OOM kill halfway
through still leaves a durable record of which outages existed at that moment.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import time
import uuid
from pathlib import Path

from . import alert
from .client import ApiError, AuthError, EsbClient, NotFound, TransientError
from .parse import check_detail_schema, check_list_schema, normalize_detail
from .store import Store, utc_now_iso

DEFAULT_DELAY_MS = 1000

# A failed detail fetch is not lost data: the outage stays in the list for the
# whole retention window and is not marked final, so the next hourly run retries
# it - roughly four more chances before ESB purges it. Only a broad failure is
# worth an email, so both a proportion and an absolute floor must be exceeded.
PARTIAL_FAILURE_THRESHOLD = 0.25
PARTIAL_FAILURE_MIN = 3


@contextlib.contextmanager
def poll_lock(data_dir: Path):
    """Exclusive lock so two runs can never interleave writes.

    At one request per second a large storm could in principle push a run past
    the next hourly trigger. Overlapping runs would corrupt neither file
    irrecoverably, but they would duplicate work and confuse change history.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".poll.lock"
    handle = lock_path.open("w")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        handle.close()


def run_poll(data_dir, client: EsbClient | None = None, delay_ms: int | None = None) -> int:
    data_dir = Path(data_dir)
    client = client or EsbClient()
    if delay_ms is None:
        delay_ms = int(os.environ.get("ESB_POLL_DELAY_MS", DEFAULT_DELAY_MS))

    with poll_lock(data_dir) as acquired:
        if not acquired:
            print("another poll run holds the lock; skipping this trigger")
            return alert.EXIT_OK
        return _run(data_dir, client, delay_ms)


def _run(data_dir: Path, client: EsbClient, delay_ms: int) -> int:
    started_at = utc_now_iso()
    # Timestamps are only second-resolution, so they cannot identify a run on
    # their own; rebuild groups observations by run_id and needs it unique.
    run_id = f"{started_at}-{uuid.uuid4().hex[:8]}"

    with Store(data_dir) as store:
        # --- list ---------------------------------------------------------
        try:
            list_body = client.get_outage_list()
        except AuthError as exc:
            store.record_run(
                run_id=run_id, started_at_utc=started_at, finished_at_utc=utc_now_iso(),
                status="auth_error", exit_code=alert.EXIT_AUTH, n_errors=1,
                error_summary=str(exc),
            )
            return alert.fail(alert.auth_banner(client.masked_key, str(exc)), alert.EXIT_AUTH)
        except (TransientError, ApiError) as exc:
            store.record_run(
                run_id=run_id, started_at_utc=started_at, finished_at_utc=utc_now_iso(),
                status="unreachable", exit_code=alert.EXIT_UNREACHABLE, n_errors=1,
                error_summary=str(exc),
            )
            return alert.fail(alert.unreachable_banner(str(exc)), alert.EXIT_UNREACHABLE)

        # Durability point: the list is on disk before anything else happens.
        store.write_run_raw(run_id, started_at, 200, list_body)

        drift = check_list_schema(list_body)
        items = list_body.get("outageMessage") or []
        if not isinstance(items, list):
            items = []

        store.apply_list(started_at, items)
        listed_ids = [str(i.get("i")) for i in items if isinstance(i, dict)]
        todo = store.ids_needing_detail(listed_ids)
        skipped = len(listed_ids) - len(todo)

        # --- details ------------------------------------------------------
        fetched = 0
        purged = 0
        errors: list[str] = []
        for index, outage_id in enumerate(todo):
            if index:
                time.sleep(delay_ms / 1000.0)
            observed_at = utc_now_iso()
            try:
                body = client.get_outage_detail(outage_id)
            except NotFound:
                # Normal: purged between the list call and this one. The stub row
                # from apply_list keeps its ID and coordinates.
                store.write_observation_raw(run_id, observed_at, outage_id, 404, None)
                purged += 1
                continue
            except AuthError as exc:
                # The key died mid-run. Stop immediately rather than burning
                # through hundreds of guaranteed-failing requests.
                store.record_run(
                    run_id=run_id, started_at_utc=started_at,
                    finished_at_utc=utc_now_iso(), status="auth_error",
                    exit_code=alert.EXIT_AUTH, n_listed=len(listed_ids),
                    n_detail_fetched=fetched, n_detail_skipped=skipped,
                    n_errors=1, error_summary=str(exc),
                )
                return alert.fail(
                    alert.auth_banner(client.masked_key, str(exc)), alert.EXIT_AUTH
                )
            except (TransientError, ApiError) as exc:
                errors.append(f"{outage_id}: {exc}")
                continue

            store.write_observation_raw(run_id, observed_at, outage_id, 200, body)
            drift.extend(
                f"outage {outage_id}: {p}" for p in check_detail_schema(body)
            )
            store.apply_detail(observed_at, normalize_detail(body))
            fetched += 1

        # --- outcome ------------------------------------------------------
        attempted = len(todo) - purged
        failed = len(errors)
        partial = (
            attempted > 0
            and failed >= PARTIAL_FAILURE_MIN
            and failed / attempted > PARTIAL_FAILURE_THRESHOLD
        )

        if partial:
            status, code = "partial", alert.EXIT_PARTIAL
        elif drift:
            status, code = "schema_drift", alert.EXIT_SCHEMA_DRIFT
        else:
            status, code = "ok", alert.EXIT_OK

        store.record_run(
            run_id=run_id, started_at_utc=started_at, finished_at_utc=utc_now_iso(),
            status=status, exit_code=code, n_listed=len(listed_ids),
            n_detail_fetched=fetched, n_detail_skipped=skipped, n_errors=failed,
            error_summary="; ".join(errors[:10]) or None,
        )
        store.conn.commit()

        print(
            f"run {started_at}: {len(listed_ids)} listed, {fetched} fetched, "
            f"{skipped} cached, {purged} purged, {failed} failed"
        )

        if partial:
            return alert.fail(
                alert.partial_banner(failed, attempted, errors), alert.EXIT_PARTIAL
            )
        if drift:
            # Deduplicated: one changed field would otherwise report once per outage.
            unique = sorted({d.split(": ", 1)[-1] for d in drift})
            return alert.fail(alert.schema_banner(unique), alert.EXIT_SCHEMA_DRIFT)
        return alert.EXIT_OK


def run_check(client: EsbClient | None = None) -> int:
    """Validate connectivity and the API key without writing anything.

    Useful as a second, independent Synology task: if the collector's own emails
    ever stop arriving, this one failing separately still surfaces the problem.
    """
    client = client or EsbClient()
    try:
        body = client.get_outage_list()
    except AuthError as exc:
        return alert.fail(alert.auth_banner(client.masked_key, str(exc)), alert.EXIT_AUTH)
    except (TransientError, ApiError) as exc:
        return alert.fail(alert.unreachable_banner(str(exc)), alert.EXIT_UNREACHABLE)

    problems = check_list_schema(body)
    if problems:
        return alert.fail(alert.schema_banner(problems), alert.EXIT_SCHEMA_DRIFT)

    count = len(body.get("outageMessage") or [])
    print(f"ok: key {client.masked_key} accepted, {count} outages currently listed")
    return alert.EXIT_OK
