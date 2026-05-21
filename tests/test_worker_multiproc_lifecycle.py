"""Tests for worker Prometheus multiprocess directory lifecycle."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


def _load_worker_bootstrap():
    module = importlib.import_module("atlas20.api.worker.__main__")
    return importlib.reload(module)


def test_initialize_multiproc_dir_wipes_existing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.delenv("ATLAS20_WORKER_MULTIPROC_SKIP_WIPE", raising=False)
    multiproc_dir = tmp_path / ".prom-multiproc-worker"
    multiproc_dir.mkdir()
    stale_file = multiproc_dir / "stale_counter_999.db"
    stale_file.touch()

    worker_bootstrap = _load_worker_bootstrap()
    initialized = worker_bootstrap._initialize_multiproc_dir()

    assert initialized == multiproc_dir
    assert multiproc_dir.exists()
    assert not stale_file.exists()
    assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == str(multiproc_dir)


def test_initialize_multiproc_dir_skips_wipe_when_env_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_WORKER_MULTIPROC_SKIP_WIPE", "1")
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    multiproc_dir = tmp_path / ".prom-multiproc-worker"
    multiproc_dir.mkdir()
    stale_file = multiproc_dir / "stale_counter_999.db"
    stale_file.touch()

    worker_bootstrap = _load_worker_bootstrap()
    initialized = worker_bootstrap._initialize_multiproc_dir()

    assert initialized == multiproc_dir
    assert multiproc_dir.exists()
    assert stale_file.exists()
    assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == str(multiproc_dir)


def test_spawn_workers_wipes_once_and_signals_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from atlas20.api.worker import spawn

    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    multiproc_dir = tmp_path / ".prom-multiproc-worker"
    multiproc_dir.mkdir()
    stale_file = multiproc_dir / "stale_counter_999.db"
    stale_file.touch()
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_popen(args: list[str], *, env: dict[str, str]):
        calls.append((args, env))
        return object()

    monkeypatch.setattr(spawn.subprocess, "Popen", fake_popen)

    processes = spawn.spawn_workers(count=2)

    assert len(processes) == 2
    assert not stale_file.exists()
    assert multiproc_dir.exists()
    assert [args for args, _env in calls] == [
        [sys.executable, "-m", "atlas20.api.worker"],
        [sys.executable, "-m", "atlas20.api.worker"],
    ]
    assert [env["ATLAS20_WORKERS"] for _args, env in calls] == ["1", "1"]
    assert [env["ATLAS20_WORKER_MULTIPROC_SKIP_WIPE"] for _args, env in calls] == ["1", "1"]
