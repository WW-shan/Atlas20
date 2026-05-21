"""Bootstrap entry for ``python -m atlas20.api.worker``.

Sets ``PROMETHEUS_MULTIPROC_DIR`` before importing atlas20 worker modules so
per-process Counter writes land in shared mmap files that the parent
``/metrics`` endpoint aggregates. Required because ``run_one`` runs in a
subprocess; without this, its counter increments vanish on subprocess exit.
"""

from __future__ import annotations

import os
from pathlib import Path

_data_root = Path(os.environ.get("ATLAS20_DATA_ROOT", "data"))
_multiproc_dir = _data_root / ".prom-multiproc-worker"
_multiproc_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(_multiproc_dir))

from atlas20.api.worker.main import main  # noqa: E402


if __name__ == "__main__":
    main()
