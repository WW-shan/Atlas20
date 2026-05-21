"""Bootstrap entry for ``python -m atlas20.api.worker``.

Sets ``PROMETHEUS_MULTIPROC_DIR`` before importing atlas20 worker modules so
per-process Counter writes land in shared mmap files that the parent
``/metrics`` endpoint aggregates. Required because ``run_one`` runs in a
subprocess; without this, its counter increments vanish on subprocess exit.

The multiproc directory is wiped on startup to prevent unbounded growth
of dead-pid mmap files (per prometheus_client multiprocess guidance).
spawn.py sets ATLAS20_WORKER_MULTIPROC_SKIP_WIPE=1 on its children so only
the spawn-time owner wipes once before any worker starts.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _initialize_multiproc_dir() -> Path:
    explicit = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if explicit:
        multiproc_dir = Path(explicit)
    else:
        data_root = Path(os.environ.get("ATLAS20_DATA_ROOT", "data"))
        multiproc_dir = data_root / ".prom-multiproc-worker"
    if os.environ.get("ATLAS20_WORKER_MULTIPROC_SKIP_WIPE") != "1" and multiproc_dir.exists():
        # Best-effort wipe -- if a file is still mmap'd by an in-flight subprocess
        # (rare during a clean restart), let the leftover stay rather than crash.
        shutil.rmtree(multiproc_dir, ignore_errors=True)
    multiproc_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(multiproc_dir))
    return multiproc_dir


_initialize_multiproc_dir()

from atlas20.api.worker.main import main  # noqa: E402


if __name__ == "__main__":
    main()
