"""Tests for the worker process Prometheus /metrics endpoint."""
from __future__ import annotations

import logging
import sys

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
) -> None:
    def raise_port_in_use(port: int) -> None:
        raise OSError("address already in use")

    monkeypatch.setattr(worker_main, "start_http_server", raise_port_in_use)
    monkeypatch.setattr(worker_main, "_metrics_server_started", False)

    with caplog.at_level(logging.INFO, logger=worker_main.logger.name):
        worker_main.start_metrics_server(8765)

    assert worker_main._metrics_server_started is True
    assert "worker prometheus /metrics port 8765 already bound" in caplog.text


def test_spawn_workers_uses_worker_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    from atlas20.api.worker import spawn

    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_popen(args: list[str], *, env: dict[str, str]):
        calls.append((args, env))
        return object()

    monkeypatch.setattr(spawn.subprocess, "Popen", fake_popen)

    processes = spawn.spawn_workers(count=2)

    assert len(processes) == 2
    assert [args for args, _env in calls] == [
        [sys.executable, "-m", "atlas20.api.worker"],
        [sys.executable, "-m", "atlas20.api.worker"],
    ]
    assert [env["ATLAS20_WORKERS"] for _args, env in calls] == ["1", "1"]


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
