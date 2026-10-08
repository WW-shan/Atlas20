"""Long-running worker process for queued backtest runs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import errno
import logging
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
from typing import Any

from prometheus_client import start_http_server
from sqlmodel import Session

from atlas20.api._time import utc_now
from atlas20.api.repositories import RunsRepo, get_engine
from atlas20.api.settings import Settings, get_settings
from atlas20.api.worker.queue import WorkerQueue
from atlas20.api.worker.recovery import StaleRunMonitor, stale_threshold_seconds

logger = logging.getLogger(__name__)
_shutdown_requested = threading.Event()
# Cap on the retry delay after a failed poll. Kept under the 30s staleness
# window of the docker healthcheck that reads the poll-tick gauge.
MAX_POLL_BACKOFF_SECONDS = 15.0
_metrics_server_started = False
_metrics_server_lock = threading.Lock()


def start_metrics_server(port: int) -> None:
    """Expose this worker process's Prometheus registry on the given port.

    Prometheus counters are per-process memory; without a dedicated worker
    scrape target every increment recorded by the worker (backtest lifecycle,
    report generation) would be invisible to the API process's /metrics
    endpoint. Idempotent: only binds on the first call per process so unit
    tests that import this module repeatedly do not collide on the port.
    """
    global _metrics_server_started
    with _metrics_server_lock:
        if _metrics_server_started:
            return
        try:
            multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
            if multiproc_dir:
                from prometheus_client import CollectorRegistry, multiprocess

                registry = CollectorRegistry()
                multi_process_collector: Any = multiprocess.MultiProcessCollector
                multi_process_collector(registry)
                start_http_server(port, registry=registry)
            else:
                start_http_server(port)
            _metrics_server_started = True
            logger.info("worker prometheus /metrics listening on port %d (multiproc=%s)", port, bool(multiproc_dir))
        except OSError as exc:
            addr_in_use_codes = {errno.EADDRINUSE}
            win_code = getattr(errno, "WSAEADDRINUSE", None)
            if win_code is not None:
                addr_in_use_codes.add(win_code)
            if exc.errno not in addr_in_use_codes:
                raise
            _metrics_server_started = True
            multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
            if multiproc_dir:
                logger.info(
                    "worker prometheus /metrics port %d already bound; this worker's "
                    "counters will be aggregated by the bound process via "
                    "PROMETHEUS_MULTIPROC_DIR=%s",
                    port,
                    multiproc_dir,
                )
            else:
                logger.warning(
                    "worker prometheus /metrics port %d already bound and "
                    "PROMETHEUS_MULTIPROC_DIR is not configured; this worker's "
                    "counter increments will be DROPPED (not visible in any /metrics "
                    "scrape). Set PROMETHEUS_MULTIPROC_DIR to enable cross-worker "
                    "aggregation.",
                    port,
                )


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    engine = get_engine(settings or get_settings())
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def setup_signal_handlers() -> None:
    def request_shutdown(signum: int, frame: object | None) -> None:
        del signum, frame
        _shutdown_requested.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)


def _terminate_process(proc: subprocess.Popen[bytes], grace_seconds: float) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def make_worker_id() -> str:
    """Name this worker process uniquely: host, PID and a random suffix.

    A PID alone does not identify a worker: every containerised worker is PID 1.
    """
    return f"{socket.gethostname()}:{os.getpid()}:{secrets.token_hex(4)}"


def _mark_cancelled(run_id: str, settings: Settings) -> None:
    with session_scope(settings) as session:
        RunsRepo(session).mark_cancelled(run_id, error="cancelled by user")


def _mark_failed(run_id: str, settings: Settings, error: str) -> None:
    with session_scope(settings) as session:
        RunsRepo(session).update_metrics_from_completion(
            run_id,
            status="failed",
            error=error[:1000],
            heartbeat_at=None,
            worker_pid=None,
        )


def _heartbeat_loop(
    run_id: str,
    proc: subprocess.Popen[bytes],
    settings: Settings,
    stop_event: threading.Event,
    cancelled_event: threading.Event,
    heartbeat_interval_seconds: float,
) -> None:
    from atlas20.api._metrics import record_worker_poll_tick

    while not stop_event.wait(heartbeat_interval_seconds):
        # Refresh the worker liveness gauge here too: the main poll loop is
        # blocked inside _execute_run while this run is in flight, so without
        # an in-flight stamp the gauge would age past the docker healthcheck
        # threshold during long backtests and the worker would be falsely
        # killed.
        record_worker_poll_tick()
        should_cancel = False
        try:
            with session_scope(settings) as session:
                repo = RunsRepo(session)
                run = repo.get(run_id)
                if run is None or run.status != "running":
                    return
                if run.requested_cancel:
                    should_cancel = True
                else:
                    repo.update(run_id, heartbeat_at=utc_now())
        except Exception as exc:
            logger.warning("heartbeat tick failed: %s", exc)
            continue

        if should_cancel:
            cancelled_event.set()
            _terminate_process(proc, settings.worker_cancel_grace_seconds)
            _mark_cancelled(run_id, settings)
            return


def start_heartbeat_thread(
    run_id: str,
    proc: subprocess.Popen[bytes],
    settings: Settings,
    *,
    heartbeat_interval_seconds: float | None = None,
) -> tuple[threading.Event, threading.Event, threading.Thread]:
    stop_event = threading.Event()
    cancelled_event = threading.Event()
    interval = heartbeat_interval_seconds if heartbeat_interval_seconds is not None else settings.worker_heartbeat_interval_seconds
    thread = threading.Thread(
        target=_heartbeat_loop,
        args=(run_id, proc, settings, stop_event, cancelled_event, interval),
        name=f"atlas20-heartbeat-{run_id}",
        daemon=True,
    )
    thread.start()
    return stop_event, cancelled_event, thread


def _decode_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def _subprocess_error(stdout: bytes | str | None, stderr: bytes | str | None) -> str:
    message = _decode_output(stderr).strip() or _decode_output(stdout).strip()
    return message[-1000:] if message else "subprocess failed"


def _execute_run(run_id: str, settings: Settings, *, heartbeat_interval_seconds: float | None = None) -> None:
    with session_scope(settings) as session:
        repo = RunsRepo(session)
        run = repo.get(run_id)
        if run is None:
            return
        if run.requested_cancel:
            repo.mark_cancelled(run_id, error="cancelled before execution")
            return

    proc: subprocess.Popen[bytes] = subprocess.Popen(
        [sys.executable, "-m", "atlas20.api.worker.run_one", run_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )
    interval = heartbeat_interval_seconds if heartbeat_interval_seconds is not None else settings.worker_heartbeat_interval_seconds
    try:
        stop_event, cancelled_event, thread = start_heartbeat_thread(
            run_id,
            proc,
            settings,
            heartbeat_interval_seconds=interval,
        )
    except BaseException:
        # Without a heartbeat thread nobody can cancel or supervise the run.
        _terminate_process(proc, settings.worker_cancel_grace_seconds)
        raise
    try:
        try:
            stdout, stderr = proc.communicate(timeout=settings.run_timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            if not cancelled_event.is_set():
                _mark_failed(run_id, settings, "timeout")
            return

        if cancelled_event.is_set():
            _mark_cancelled(run_id, settings)
        elif proc.returncode != 0:
            _mark_failed(run_id, settings, _subprocess_error(stdout, stderr))
    finally:
        stop_event.set()
        thread.join(timeout=interval + 1)


def _recover_orphaned_runs(settings: Settings, monitor: StaleRunMonitor, worker_id: str) -> int:
    try:
        with session_scope(settings) as session:
            recovered = monitor.recover(session)
    except Exception as exc:
        logger.warning("stale run recovery failed: %s", exc)
        return 0
    if recovered:
        logger.info("Worker %s recovered %d orphaned running run(s)", worker_id, recovered)
    return recovered


def _recovery_loop(
    settings: Settings,
    monitor: StaleRunMonitor,
    stop_event: threading.Event,
    interval_seconds: float,
    worker_id: str,
) -> None:
    while True:
        _recover_orphaned_runs(settings, monitor, worker_id)
        if stop_event.wait(interval_seconds):
            return


def start_recovery_thread(
    settings: Settings,
    monitor: StaleRunMonitor,
    stop_event: threading.Event,
    *,
    worker_id: str | None = None,
    interval_seconds: float | None = None,
) -> threading.Thread:
    """Fail runs orphaned by any dead worker, on a cadence of its own.

    It runs beside the poll loop because that loop blocks for a whole backtest,
    and orphans (whose cancel requests nobody acts on) must not wait for it.
    """
    interval = interval_seconds if interval_seconds is not None else settings.worker_heartbeat_interval_seconds
    thread = threading.Thread(
        target=_recovery_loop,
        args=(settings, monitor, stop_event, interval, worker_id or make_worker_id()),
        name="atlas20-stale-run-recovery",
        daemon=True,
    )
    thread.start()
    return thread


def main() -> None:
    settings = get_settings()
    setup_signal_handlers()
    from atlas20.api.install_check import warn_if_shadow_install

    warn_if_shadow_install()
    start_metrics_server(settings.worker_metrics_port)
    worker_id = make_worker_id()
    logger.info("Worker %s starting", worker_id)
    monitor = StaleRunMonitor(stale_threshold_seconds(settings.worker_heartbeat_interval_seconds))
    recovery_thread = start_recovery_thread(settings, monitor, _shutdown_requested, worker_id=worker_id)

    failures = 0
    while not _shutdown_requested.is_set():
        try:
            worked = _poll_once(settings, worker_id)
        except Exception:
            # A locked or briefly unreachable database must not kill the
            # worker; queued runs would otherwise wait for a manual restart.
            failures += 1
            delay = _poll_backoff_seconds(settings, failures)
            logger.exception("worker poll failed (%d in a row); retrying in %.1fs", failures, delay)
            _shutdown_requested.wait(delay)
            continue
        failures = 0
        if not worked:
            _shutdown_requested.wait(settings.worker_poll_interval_seconds)
    recovery_thread.join(timeout=settings.worker_heartbeat_interval_seconds + 1)


def _poll_once(settings: Settings, worker_id: str) -> bool:
    """Claim and execute one queued run; return False when the queue was empty."""
    from atlas20.api._metrics import record_worker_poll_tick

    run_id: str | None = None
    try:
        with session_scope(settings) as session:
            claimed = WorkerQueue(session).claim_one(worker_id=worker_id)
            if claimed is not None:
                run_id = claimed.run_id
    finally:
        # The loop is alive even when the claim failed; the healthcheck gauge
        # tracks liveness, not database health.
        record_worker_poll_tick()
    if run_id is None:
        return False
    try:
        _execute_run(run_id, settings)
    except Exception as exc:
        _mark_failed_best_effort(run_id, settings, f"worker error: {exc}")
        raise
    return True


def _mark_failed_best_effort(run_id: str, settings: Settings, error: str) -> None:
    try:
        _mark_failed(run_id, settings, error)
    except Exception:
        # Stale-heartbeat recovery fails the run later if this write cannot land.
        logger.exception("could not mark run %s failed", run_id)


def _poll_backoff_seconds(settings: Settings, failures: int) -> float:
    base = max(settings.worker_poll_interval_seconds, 0.01)
    return float(min(MAX_POLL_BACKOFF_SECONDS, base * 2 ** min(failures - 1, 16)))


if __name__ == "__main__":
    main()
