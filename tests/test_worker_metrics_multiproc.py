"""Real-port tests for worker Prometheus multiprocess aggregation."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from atlas20.api.db.models import Run
from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import Settings


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else os.pathsep.join([src_path, existing])
    return env


def test_worker_metrics_scrape_aggregates_subprocess_counter(tmp_path: Path) -> None:
    multiproc_dir = tmp_path / "prom"
    multiproc_dir.mkdir()
    port = _free_port()
    env = _child_env()
    env["PROMETHEUS_MULTIPROC_DIR"] = str(multiproc_dir)

    script = textwrap.dedent(
        """
        import os
        import re
        import subprocess
        import sys
        import time
        import urllib.request

        from prometheus_client import multiprocess

        from atlas20.api.worker.main import start_metrics_server

        port = int(os.environ["ATLAS20_TEST_METRICS_PORT"])
        start_metrics_server(port)

        child = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import os;"
                    "from atlas20.api import _metrics;"
                    "_metrics.BACKTESTS_TOTAL.labels(status='completed').inc();"
                    "from prometheus_client import multiprocess;"
                    "multiprocess.mark_process_dead(os.getpid())"
                ),
            ],
            check=True,
            env=os.environ.copy(),
        )
        del child

        body = ""
        for _ in range(20):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=2) as response:
                body = response.read().decode("utf-8")
            match = re.search(r'atlas20_backtests_total\\{status="completed"\\}\\s+([0-9.]+)', body)
            if match and float(match.group(1)) > 0:
                break
            time.sleep(0.05)
        else:
            print(body)
            raise AssertionError("completed backtest counter was not aggregated from subprocess")

        multiprocess.mark_process_dead(os.getpid())
        """
    )
    env["ATLAS20_TEST_METRICS_PORT"] = str(port)

    try:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            env=env,
            text=True,
            timeout=10,
        )
    finally:
        shutil.rmtree(multiproc_dir, ignore_errors=True)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_worker_package_import_does_not_eagerly_import_metrics() -> None:
    script = textwrap.dedent(
        """
        import os
        import sys

        os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
        import atlas20.api.worker

        if "atlas20.api._metrics" in sys.modules:
            raise AssertionError("worker package import eagerly imported metrics before __main__ bootstrap")
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        env=_child_env(),
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_real_run_one_subprocess_increments_terminal_counter_via_multiproc(tmp_path: Path) -> None:
    """End-to-end coverage of the real terminal-transition counter path.

    The other multiproc test only verifies the wire-level plumbing (a
    subprocess writes to mmap, parent reads). This test launches the real
    `python -m atlas20.api.worker.run_one` binary in mock mode, exercising the
    full path: RunsRepo.update_metrics_from_completion -> record_backtest_terminal
    -> BACKTESTS_TOTAL.inc inside the subprocess. After exit the parent uses
    MultiProcessCollector to confirm the counter survived the subprocess.
    """
    multiproc_dir = tmp_path / "prom"
    multiproc_dir.mkdir()

    settings = Settings(
        db_url=f"sqlite:///{(tmp_path / 'run.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        project_root=tmp_path,
        run_timeout_seconds=5,
        worker_poll_interval_seconds=0.01,
    )
    engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    config = BacktestConfig.model_validate(
        {
            "preset": "ATLAS Adaptive v3",
            "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
            "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
            "allocation": {"positionPct": 5.0, "slots": 10},
            "costs": {"feeBps": 10, "slippageBps": 5},
        }
    )
    with Session(engine) as session:
        session.add(
            Run(
                run_id="btk_0001",
                strategy=config.preset,
                strategy_family="ATLAS",
                universe="Top-20",
                window_start=date(2024, 1, 1),
                window_end=date(2026, 5, 18),
                status="running",
                params=config.model_dump_json(),
            )
        )
        session.commit()

    env = _child_env()
    env["PROMETHEUS_MULTIPROC_DIR"] = str(multiproc_dir)
    env["ATLAS20_WORKER_MOCK"] = "1"
    env["ATLAS20_DB_URL"] = settings.db_url
    env["ATLAS20_REPORT_ROOT"] = str(settings.report_root)
    env["ATLAS20_PROJECT_ROOT"] = str(settings.project_root)
    env["ATLAS20_RUN_TIMEOUT_SECONDS"] = str(settings.run_timeout_seconds)
    env["ATLAS20_WORKER_POLL_INTERVAL_SECONDS"] = str(settings.worker_poll_interval_seconds)

    completed = subprocess.run(
        [sys.executable, "-m", "atlas20.api.worker.run_one", "btk_0001"],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    scrape = textwrap.dedent(
        """
        import os
        from prometheus_client import CollectorRegistry, generate_latest, multiprocess

        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        print(generate_latest(registry).decode("utf-8"))
        """
    )
    parent = subprocess.run(
        [sys.executable, "-c", scrape],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    try:
        assert parent.returncode == 0, parent.stdout + parent.stderr
        match = re.search(
            r'atlas20_backtests_total\{status="completed"\}\s+([0-9.]+)',
            parent.stdout,
        )
        assert match is not None, parent.stdout
        assert float(match.group(1)) == 1.0, parent.stdout
    finally:
        shutil.rmtree(multiproc_dir, ignore_errors=True)
