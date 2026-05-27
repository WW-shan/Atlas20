"""Utility for launching multiple local worker child processes."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _wipe_multiproc_dir() -> None:
    explicit = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if explicit:
        multiproc_dir = Path(explicit)
    else:
        data_root = Path(os.environ.get("ATLAS20_DATA_ROOT", "data"))
        multiproc_dir = data_root / ".prom-multiproc-worker"
    if multiproc_dir.exists():
        shutil.rmtree(multiproc_dir, ignore_errors=True)
    multiproc_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(multiproc_dir))


def spawn_workers(count: int | None = None) -> list[subprocess.Popen[bytes]]:
    worker_count = count if count is not None else int(os.environ.get("ATLAS20_WORKERS", "2"))
    _wipe_multiproc_dir()
    processes: list[subprocess.Popen[bytes]] = []
    for _ in range(worker_count):
        env = os.environ.copy()
        env["ATLAS20_WORKERS"] = "1"
        env["ATLAS20_WORKER_MULTIPROC_SKIP_WIPE"] = "1"
        processes.append(subprocess.Popen([sys.executable, "-m", "atlas20.api.worker"], env=env))
    return processes


def main() -> None:
    processes = spawn_workers()
    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        for process in processes:
            process.terminate()


if __name__ == "__main__":
    main()
