"""Utility for launching multiple local worker child processes."""

from __future__ import annotations

import os
import subprocess
import sys


def spawn_workers(count: int | None = None) -> list[subprocess.Popen]:
    worker_count = count if count is not None else int(os.environ.get("ATLAS20_WORKERS", "2"))
    processes: list[subprocess.Popen] = []
    for _ in range(worker_count):
        env = os.environ.copy()
        env["ATLAS20_WORKERS"] = "1"
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
