"""Atlas20 Prometheus metric recorders.

Recorder timing trade-off
-------------------------
All counters/histograms here are emitted BEFORE the surrounding DB transaction
commits (see worker/queue.py, worker/recovery.py, repositories/runs_repo.py).
A rollback after a recorder call leaves Prometheus permanently over-counted
versus the DB. We accept this trade-off because (a) post-flush commits
rarely fail in this codebase, (b) Prometheus counters are monotonic so
"slightly high" is operationally tolerable, and (c) an after-commit hook
would couple metric emission to ORM lifecycle events in ways that hurt
testability. Track for future hardening if the divergence ever becomes
operationally visible.
"""

from __future__ import annotations

import logging
import time

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

TERMINAL_BACKTEST_STATUSES = ("completed", "failed", "cancelled")
REPORT_STATUSES = ("completed", "failed", "skipped")
REPORT_FORMATS = ("markdown", "pdf", "png", "csv", "bundle")

BACKTESTS_TOTAL = Counter(
    "atlas20_backtests_total",
    "Backtest terminal status transitions.",
    ["status"],
)
BACKTEST_DURATION_SECONDS = Histogram(
    "atlas20_backtest_duration_seconds",
    "Backtest duration in seconds for terminal runs.",
)
REPORT_GENERATIONS_TOTAL = Counter(
    "atlas20_report_generations_total",
    "Report generation attempts by requested format and status.",
    ["format", "status"],
)
RATE_LIMIT_HITS_TOTAL = Counter(
    "atlas20_rate_limit_hits_total",
    "Rate limit hits by route.",
    ["route"],
)
WORKER_LAST_POLL_TIMESTAMP = Gauge(
    "atlas20_worker_last_poll_timestamp_seconds",
    "Unix timestamp the worker queue loop last completed an iteration. "
    "Healthchecks scraping the worker /metrics endpoint can compare this to "
    "the current time to detect a stuck queue loop even when the metrics "
    "HTTP listener is still serving 200.",
    multiprocess_mode="max",
)

for _status in TERMINAL_BACKTEST_STATUSES:
    BACKTESTS_TOTAL.labels(status=_status)
for _format in REPORT_FORMATS:
    for _status in REPORT_STATUSES:
        REPORT_GENERATIONS_TOTAL.labels(format=_format, status=_status)
RATE_LIMIT_HITS_TOTAL.labels(route="unmatched")


def record_backtest_terminal(status: str, duration_seconds: float | None = None) -> None:
    if status not in TERMINAL_BACKTEST_STATUSES:
        return
    try:
        BACKTESTS_TOTAL.labels(status=status).inc()
        if duration_seconds is not None:
            BACKTEST_DURATION_SECONDS.observe(max(0.0, duration_seconds))
    except Exception:
        logger.warning("failed to record backtest terminal metric", exc_info=True)


def record_report_generation(format_name: str, status: str) -> None:
    """Record report generation status: completed, failed, or skipped."""
    if format_name not in REPORT_FORMATS:
        logger.warning("ignoring metric for unknown report format: %s", format_name)
        return
    if status not in REPORT_STATUSES:
        logger.warning("ignoring metric for unknown report status: %s", status)
        return
    try:
        REPORT_GENERATIONS_TOTAL.labels(format=format_name, status=status).inc()
    except Exception:
        logger.warning("failed to record report generation metric", exc_info=True)


def record_rate_limit_hit(route: str) -> None:
    try:
        RATE_LIMIT_HITS_TOTAL.labels(route=route).inc()
    except Exception:
        logger.warning("failed to record rate limit metric", exc_info=True)


def record_worker_poll_tick() -> None:
    """Stamp the worker queue loop's last iteration timestamp.

    Called from the worker's main poll loop each time it either claims a run
    or sleeps after finding the queue empty. Healthchecks can read this gauge
    to distinguish a stuck queue loop (gauge stale) from a healthy idle
    worker (gauge advances every poll_interval).
    """
    try:
        WORKER_LAST_POLL_TIMESTAMP.set(time.time())
    except Exception:
        logger.warning("failed to record worker poll tick", exc_info=True)
