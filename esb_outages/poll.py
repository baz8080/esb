"""One collection run.

Ordering here is deliberate: the list response is written to the raw log before
any detail fetching begins, so a crash, a NAS reboot, or an OOM kill halfway
through still leaves a durable record of which outages existed at that moment.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import signal
import time
import uuid
from pathlib import Path

from . import alert
from .client import ApiError, AuthError, EsbClient, NotFound, TransientError
from .parse import check_detail_schema, check_list_schema, normalize_detail
from .store import Store, utc_now_iso

# Half a second is courtesy, not a limit ESB states.
DEFAULT_DELAY_MS = 500

# A run stops itself here, about 2,800 details at the pace above, and records
# what it left. systemd's TimeoutStartSec sits a minute beyond as a backstop,
# because a run systemd has to stop is a failed unit whatever it exits with.
RUN_BUDGET_S = 24 * 60

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


def check_writable(data_dir: Path) -> str | None:
    """Return a human explanation if the data directory is unusable, else None.

    Checked explicitly so a full disk or a wrong owner surfaces as a legible
    alert naming the directory, rather than as a bare PermissionError traceback.
    """
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"cannot create {data_dir}: {exc}"
    probe = data_dir / ".write-test"
    try:
        probe.touch()
        probe.unlink()
    except OSError as exc:
        return f"cannot write inside {data_dir}: {exc}"
    return None


def run_poll(
    data_dir,
    client: EsbClient | None = None,
    delay_ms: int | None = None,
    budget_s: float = RUN_BUDGET_S,
) -> int:
    data_dir = Path(data_dir)
    client = client or EsbClient()
    if delay_ms is None:
        delay_ms = int(os.environ.get("ESB_POLL_DELAY_MS", DEFAULT_DELAY_MS))

    problem = check_writable(data_dir)
    if problem:
        return alert.fail(alert.storage_banner(data_dir, problem), alert.EXIT_STORAGE)

    with poll_lock(data_dir) as acquired:
        if not acquired:
            print("another poll run holds the lock; skipping this trigger")
            return alert.EXIT_OK
        code = _run(data_dir, client, delay_ms, budget_s)
    # Sent for every run that reached the feed, not only a clean one: schema
    # drift and partial detail loss still leave the list on disk, and the
    # webhook already carries them. Silence means collection has stopped.
    if code not in (alert.EXIT_AUTH, alert.EXIT_UNREACHABLE):
        alert.heartbeat()
    return code


@contextlib.contextmanager
def _stop_on_sigterm():
    """Yield a list that gains an entry when SIGTERM arrives.

    The backstop behind RUN_BUDGET_S: systemd sends it if a run outlives
    TimeoutStartSec anyway. Left to Python's default the process dies
    mid-transaction, with no run record, no heartbeat, and the database
    forgetting what was fetched. Handled, the loop stops and the run closes
    itself out.
    """
    stop: list[int] = []
    try:
        previous = signal.signal(signal.SIGTERM, lambda signum, frame: stop.append(signum))
    except ValueError:  # not the main thread; nothing to catch there
        yield stop
        return
    try:
        yield stop
    finally:
        signal.signal(signal.SIGTERM, previous)


def _run(data_dir: Path, client: EsbClient, delay_ms: int, budget_s: float) -> int:
    with _stop_on_sigterm() as stop, Store(data_dir) as store:
        return _collect(store, client, delay_ms, stop, budget_s)


def _collect(store: Store, client: EsbClient, delay_ms: int, stop: list, budget_s: float) -> int:
    started_at = utc_now_iso()
    deadline = time.monotonic() + budget_s
    # Timestamps are only second-resolution, so they cannot identify a run on
    # their own; rebuild groups observations by run_id and needs it unique.
    run_id = f"{started_at}-{uuid.uuid4().hex[:8]}"

    # --- list -------------------------------------------------------------
    try:
        list_body = client.get_outage_list()
    except AuthError as exc:
        store.write_run_raw(run_id, started_at, 401, None, status="auth_error")
        store.record_run(
            run_id=run_id, started_at_utc=started_at, finished_at_utc=utc_now_iso(),
            status="auth_error", exit_code=alert.EXIT_AUTH, n_errors=1,
            error_summary=str(exc),
        )
        return alert.fail(alert.auth_banner(client.masked_key, str(exc)), alert.EXIT_AUTH)
    except (TransientError, ApiError) as exc:
        store.write_run_raw(run_id, started_at, 0, None, status="unreachable")
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
    store.conn.commit()
    listed_ids = [str(i.get("i")) for i in items if isinstance(i, dict)]
    todo = store.ids_needing_detail(listed_ids, now=started_at)
    skipped = len(listed_ids) - len(todo)

    # --- details ----------------------------------------------------------
    fetched = 0
    purged = 0
    done = 0
    errors: list[str] = []
    for index, outage_id in enumerate(todo):
        if index:
            time.sleep(delay_ms / 1000.0)
        # Checked after the sleep: a SIGTERM that lands during it resumes the
        # sleep, and must not start one more fetch. The first fetch always
        # runs, so a tiny budget still makes progress.
        if stop or (index and time.monotonic() >= deadline):
            break
        done += 1
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
            # Logged with status 0 so a rebuild can still account for the
            # attempt rather than showing a run that quietly fetched less.
            store.write_observation_raw(run_id, observed_at, outage_id, 0, None)
            errors.append(f"{outage_id}: {exc}")
            continue

        store.write_observation_raw(run_id, observed_at, outage_id, 200, body)
        drift.extend(
            f"outage {outage_id}: {p}" for p in check_detail_schema(body)
        )
        store.apply_detail(observed_at, normalize_detail(body))
        # Committed per detail so a run killed outright still leaves the
        # database knowing what it fetched; the next run then carries on
        # rather than starting the same list over.
        store.conn.commit()
        fetched += 1

    # --- outcome ----------------------------------------------------------
    attempted = done - purged
    failed = len(errors)
    left = len(todo) - done
    partial = (
        attempted > 0
        and failed >= PARTIAL_FAILURE_MIN
        and failed / attempted > PARTIAL_FAILURE_THRESHOLD
    )

    if partial:
        status, code = "partial", alert.EXIT_PARTIAL
    elif drift:
        status, code = "schema_drift", alert.EXIT_SCHEMA_DRIFT
    elif left:
        # Told to stop with work undone. Not an alarm: the list is on disk,
        # what was fetched is committed, and the next run takes the rest first.
        status, code = "cut_short", alert.EXIT_OK
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
        + (f", cut short with {left} left for the next run" if left else "")
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

    Safe to run at any time, including while a poll is in progress, since it
    takes no lock and touches no files.
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
