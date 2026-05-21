"""Worker queue support for DB-backed backtest execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atlas20.api.worker.queue import WorkerQueue
    from atlas20.api.worker.recovery import recover_stale_runs

__all__ = ["WorkerQueue", "recover_stale_runs"]


def __getattr__(name: str) -> object:
    if name == "WorkerQueue":
        from atlas20.api.worker.queue import WorkerQueue

        return WorkerQueue
    if name == "recover_stale_runs":
        from atlas20.api.worker.recovery import recover_stale_runs

        return recover_stale_runs
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
