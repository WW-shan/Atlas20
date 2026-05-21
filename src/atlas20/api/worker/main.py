"""Long-running worker process for queued backtest runs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import errno
import logging
import os
import signal
import subprocess
import sys
import threading

from prometheus_client import start_http_server
from sqlmodel import Session

from atlas20.api._time import utc_now
from atlas20.api.repositories import RunsRepo, get_engine
from atlas20.api.settings import Settings, get_settings
from atlas20.api.worker.queue import WorkerQueue
from atlas20.api.worker.recovery import recover_runs_owned_by_pid

logger = logging.getLogger(__name__)
_shutdown_requested = threading.Event()
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
                multiprocess.MultiProcessCollector(registry)
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
    def request_shutdown(signum, frame):
        del signum, frame
        _shutdown_requested.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)


def _terminate_process(proc: subprocess.Popen, grace_seconds: float) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _mark_cancelled(run_id: str, settings: Settings) -> None:
    with session_scope(settings) as session:
        RunsRepo(session).update(
            run_id,
            status="cancelled",
            error="cancelled by user",
            heartbeat_at=None,
            worker_pid=None,
        )


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
    proc: subprocess.Popen,
    settings: Settings,
    stop_event: threading.Event,
    cancelled_event: threading.Event,
    heartbeat_interval_seconds: float,
) -> None:
    while not stop_event.wait(heartbeat_interval_seconds):
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
    proc: subprocess.Popen,
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
            repo.update(
                run_id,
                status="cancelled",
                error="cancelled before execution",
                heartbeat_at=None,
                worker_pid=None,
            )
            return

    proc = subprocess.Popen(
        [sys.executable, "-m", "atlas20.api.worker.run_one", run_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )
    interval = heartbeat_interval_seconds if heartbeat_interval_seconds is not None else settings.worker_heartbeat_interval_seconds
    stop_event, cancelled_event, thread = start_heartbeat_thread(
        run_id,
        proc,
        settings,
        heartbeat_interval_seconds=interval,
    )
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


def _recover_on_startup(settings: Settings) -> None:
    with session_scope(settings) as session:
        recovered = recover_runs_owned_by_pid(session, my_pid=os.getpid())
    if recovered:
        logger.info("Recovered %d stale running runs", recovered)


def main() -> None:
    settings = get_settings()
    setup_signal_handlers()
    from atlas20.api.install_check import warn_if_shadow_install

    warn_if_shadow_install()
    start_metrics_server(settings.worker_metrics_port)
    _recover_on_startup(settings)

    while not _shutdown_requested.is_set():
        run_id: str | None = None
        with session_scope(settings) as session:
            claimed = WorkerQueue(session).claim_one()
            if claimed is not None:
                run_id = claimed.run_id

        if run_id is None:
            _shutdown_requested.wait(settings.worker_poll_interval_seconds)
            continue
        _execute_run(run_id, settings)


if __name__ == "__main__":
    main()
