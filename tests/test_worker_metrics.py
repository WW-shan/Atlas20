"""Tests for the worker process Prometheus /metrics endpoint."""
from __future__ import annotations

import errno
import logging
from pathlib import Path
import sys
import threading

import pytest

from atlas20.api import settings as settings_module
from atlas20.api.worker import main as worker_main


def test_worker_metrics_port_default() -> None:
    s = settings_module.Settings()
    assert s.worker_metrics_port == 8001


def test_worker_metrics_port_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS20_WORKER_METRICS_PORT", "9100")
    s = settings_module.Settings()
    assert s.worker_metrics_port == 9100


def test_start_metrics_server_binds_configured_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """First call must invoke prometheus_client.start_http_server with the
    configured port — otherwise worker-side counters would be invisible to
    Prometheus and split-process counters would silently drop."""
    calls: list[int] = []
    monkeypatch.setattr(worker_main, "start_http_server", lambda port: calls.append(port))
    monkeypatch.setattr(worker_main, "_metrics_server_started", False)

    worker_main.start_metrics_server(8765)

    assert calls == [8765]


def test_start_metrics_server_tolerates_port_in_use(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    def raise_port_in_use(port: int, *args: object, **kwargs: object) -> None:
        raise OSError(errno.EADDRINUSE, "address already in use")

    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    monkeypatch.setattr(worker_main, "start_http_server", raise_port_in_use)
    monkeypatch.setattr(worker_main, "_metrics_server_started", False)

    with caplog.at_level(logging.INFO, logger=worker_main.logger.name):
        worker_main.start_metrics_server(8765)

    assert worker_main._metrics_server_started is True
    assert "worker prometheus /metrics port 8765 already bound" in caplog.text
    assert f"PROMETHEUS_MULTIPROC_DIR={tmp_path}" in caplog.text


def test_start_metrics_server_reraises_unrelated_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_permission_denied(port: int, *args: object, **kwargs: object) -> None:
        raise PermissionError(13, "denied")

    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.setattr(worker_main, "start_http_server", raise_permission_denied)
    monkeypatch.setattr(worker_main, "_metrics_server_started", False)

    with pytest.raises(PermissionError):
        worker_main.start_metrics_server(8765)

    assert worker_main._metrics_server_started is False


def test_start_metrics_server_warns_when_collision_without_multiproc(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def raise_port_in_use(port: int, *args: object, **kwargs: object) -> None:
        raise OSError(errno.EADDRINUSE, "address already in use")

    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.setattr(worker_main, "start_http_server", raise_port_in_use)
    monkeypatch.setattr(worker_main, "_metrics_server_started", False)

    with caplog.at_level(logging.WARNING, logger=worker_main.logger.name):
        worker_main.start_metrics_server(8765)

    assert worker_main._metrics_server_started is True
    assert "worker prometheus /metrics port 8765 already bound" in caplog.text
    assert "DROPPED" in caplog.text


def test_spawn_workers_uses_worker_bootstrap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from atlas20.api.worker import spawn

    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_popen(args: list[str], *, env: dict[str, str]):
        calls.append((args, env))
        return object()

    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path / "prom"))
    monkeypatch.setattr(spawn.subprocess, "Popen", fake_popen)

    processes = spawn.spawn_workers(count=2)

    assert len(processes) == 2
    assert [args for args, _env in calls] == [
        [sys.executable, "-m", "atlas20.api.worker"],
        [sys.executable, "-m", "atlas20.api.worker"],
    ]
    assert [env["ATLAS20_WORKERS"] for _args, env in calls] == ["1", "1"]


def test_worker_main_invokes_shadow_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    from atlas20.api import install_check

    calls: list[None] = []
    shutdown = threading.Event()
    shutdown.set()

    monkeypatch.setattr(install_check, "warn_if_shadow_install", lambda: calls.append(None))
    monkeypatch.setattr(worker_main, "_shutdown_requested", shutdown)
    monkeypatch.setattr(worker_main, "setup_signal_handlers", lambda: None)
    monkeypatch.setattr(worker_main, "start_metrics_server", lambda port: None)
    monkeypatch.setattr(worker_main, "_recover_on_startup", lambda settings: None)
    monkeypatch.setattr(worker_main.WorkerQueue, "claim_one", lambda self: None)

    worker_main.main()

    assert calls == [None]


def test_start_metrics_server_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-importing or re-invoking the worker in the same process (test runs,
    threaded tests) must not double-bind the port."""
    calls: list[int] = []
    monkeypatch.setattr(worker_main, "start_http_server", lambda port: calls.append(port))
    monkeypatch.setattr(worker_main, "_metrics_server_started", False)

    worker_main.start_metrics_server(8765)
    worker_main.start_metrics_server(8765)
    worker_main.start_metrics_server(9999)

    assert calls == [8765]
