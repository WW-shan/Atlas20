"""Real-port tests for worker Prometheus multiprocess aggregation."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import textwrap
from pathlib import Path


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
