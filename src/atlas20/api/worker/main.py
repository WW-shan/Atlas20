"""Long-running worker process for queued backtest runs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import logging
import os
import signal
import subprocess
import sys
import threading

from sqlmodel import Session

from atlas20.api._time import utc_now
from atlas20.api.repositories import RunsRepo, get_engine
from atlas20.api.settings import Settings, get_settings
from atlas20.api.worker.queue import WorkerQueue
from atlas20.api.worker.recovery import recover_my_own_stale_runs

logger = logging.getLogger(__name__)
_shutdown_requested = threading.Event()


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
        RunsRepo(session).update(
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
        with session_scope(settings) as session:
            repo = RunsRepo(session)
            run = repo.get(run_id)
            if run is None or run.status != "running":
                return
            if run.requested_cancel:
                should_cancel = True
            else:
                repo.update(run_id, heartbeat_at=utc_now())

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
    proc = subprocess.Popen(
        [sys.executable, "-m", "atlas20.api.worker.run_one", run_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
        recovered = recover_my_own_stale_runs(session, my_pid=os.getpid())
    if recovered:
        logger.info("Recovered %d stale running runs", recovered)


def main() -> None:
    settings = get_settings()
    setup_signal_handlers()
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
