"""Prometheus business metrics for the API."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

TERMINAL_BACKTEST_STATUSES = ("completed", "failed", "cancelled")
REPORT_STATUSES = ("completed", "failed")
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

for _status in TERMINAL_BACKTEST_STATUSES:
    BACKTESTS_TOTAL.labels(status=_status)
for _format in REPORT_FORMATS:
    for _status in REPORT_STATUSES:
        REPORT_GENERATIONS_TOTAL.labels(format=_format, status=_status)


def record_backtest_terminal(status: str, duration_seconds: float | None = None) -> None:
    if status not in TERMINAL_BACKTEST_STATUSES:
        return
    BACKTESTS_TOTAL.labels(status=status).inc()
    if duration_seconds is not None:
        BACKTEST_DURATION_SECONDS.observe(max(0.0, duration_seconds))


def record_report_generation(format_name: str, status: str) -> None:
    REPORT_GENERATIONS_TOTAL.labels(format=format_name, status=status).inc()


def record_rate_limit_hit(route: str) -> None:
    RATE_LIMIT_HITS_TOTAL.labels(route=route).inc()
