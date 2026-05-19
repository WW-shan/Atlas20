"""Services for the Atlas20 R3 mock-backed API."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from atlas20.api import mock_data
from atlas20.api._time import today, utc_iso_from_path_mtime, utc_now_iso
from atlas20.api.data_access.compare import load_compare_from_reports
from atlas20.api.data_access.options import load_options_from_reports
from atlas20.api.data_access.overview import load_overview_from_reports
from atlas20.api.data_access.universe import (
    load_data_alerts_from_processed,
    load_universe_timeline_from_processed,
)
from atlas20.api.schemas import (
    BacktestConfig,
    ComparePayload,
    DataAlert,
    DataSource,
    FeaturedDigest,
    OptionsPayload,
    OverviewPayload,
    ReportEntry,
    RunDetailPayload,
    RunRow,
    RunRowSummary,
    UniverseTimelinePayload,
)
from atlas20.api.settings import Settings, get_settings

logger = logging.getLogger(__name__)

RUN_FAMILY_CHIPS = {"ATLAS", "Momentum", "MeanRev", "Carry", "Other"}
RUN_STATUS_CHIPS = {"queued", "running", "completed", "failed"}


def get_overview() -> OverviewPayload:
    settings = get_settings().model_copy(update={"anchor_date": today()})
    payload, _used_fallback = _load_overview_payload(settings, log_warning=True)
    return OverviewPayload.model_validate(payload)


def get_options_payload() -> OptionsPayload:
    settings = get_settings()
    try:
        payload = load_options_from_reports(settings)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock options: %s", exc)
        payload = deepcopy(mock_data.fallback_options)
    return OptionsPayload.model_validate(payload)


def list_runs_queue() -> list[RunRowSummary]:
    return [RunRowSummary.model_validate(row) for row in mock_data.fallback_runs_queue]


def _created_date(row: dict[str, Any]) -> date:
    return datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).date()


def _date_cutoff(date_range: str) -> date | None:
    if date_range == "all":
        return None
    current_day = today()
    if date_range == "ytd":
        return date(current_day.year, 1, 1)
    days = {"7d": 7, "30d": 30, "90d": 90}.get(date_range, 30)
    return current_day - timedelta(days=days)


def _matches_query(row: dict[str, Any], q: str) -> bool:
    if not q:
        return True
    needle = q.lower()
    return (
        needle in row["strategy"].lower()
        or needle in row["run_id"].lower()
        or needle in row.get("universe", "").lower()
        or needle in row.get("strategy_family", "").lower()
    )


def _matches_chip(row: dict[str, Any], chip: str) -> bool:
    if chip == "favorited":
        return bool(row.get("favorited"))
    if chip in RUN_STATUS_CHIPS:
        return row["status"] == chip
    if chip in RUN_FAMILY_CHIPS:
        return row.get("strategy_family") == chip
    return chip in row["strategy"]


def _matches_date_range(row: dict[str, Any], date_range: str) -> bool:
    cutoff = _date_cutoff(date_range)
    return cutoff is None or _created_date(row) >= cutoff


def list_runs(
    q: str = "",
    chips: list[str] | None = None,
    date_range: str = "30d",
    view: str = "list",
    page: int = 1,
    page_size: int = 14,
) -> tuple[list[RunRow], int]:
    del view
    chip_values = [chip for chip in chips or [] if chip]
    rows = [
        row
        for row in mock_data.fallback_runs_list
        if _matches_query(row, q)
        and all(_matches_chip(row, chip) for chip in chip_values)
        and _matches_date_range(row, date_range)
    ]
    total = len(rows)
    safe_page = max(page, 1)
    safe_page_size = max(page_size, 1)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return [RunRow.model_validate(row) for row in rows[start:end]], total


def get_run(run_id: str) -> RunRow | None:
    row = next((item for item in mock_data.fallback_runs_list if item["run_id"] == run_id), None)
    return RunRow.model_validate(row) if row else None


def _derive_kpi_from_row(row: dict[str, Any]) -> dict[str, float]:
    """Synthesize a kpi block for non-canonical runs from RunRow fields.

    Avoids substituting btk_0142 numbers, which would mislead users looking at
    a different run's detail page.
    """
    sharpe = float(row.get("sharpe") or 0.0)
    max_dd = float(row.get("max_dd") or 0.0)
    return_pct = float(row.get("return_pct") or 0.0)
    sortino = round(sharpe * 1.5, 2) if sharpe else 0.0
    calmar = round(return_pct / abs(max_dd), 2) if max_dd else 0.0
    win_rate = round(0.5 + min(max(sharpe / 10, -0.2), 0.2), 3)
    return {
        "cagr": round(return_pct, 4),
        "sharpe": round(sharpe, 2),
        "sortino": sortino,
        "max_dd": round(max_dd, 4),
        "calmar": calmar,
        "win_rate": win_rate,
    }


def get_run_detail(run_id: str) -> RunDetailPayload | None:
    if run_id == mock_data.fallback_run_detail["run_id"]:
        return RunDetailPayload.model_validate(deepcopy(mock_data.fallback_run_detail))
    row = next((item for item in mock_data.fallback_runs_list if item["run_id"] == run_id), None)
    if row is None:
        return None
    detail = {
        **deepcopy(row),
        "equity_overlay": {"series": mock_data.fallback_overview["equity_overlay"]["series"]},
        "kpi": _derive_kpi_from_row(row),
    }
    return RunDetailPayload.model_validate(detail)


def toggle_run_favorite(run_id: str) -> dict[str, Any] | None:
    row = next((item for item in mock_data.fallback_runs_list if item["run_id"] == run_id), None)
    if row is None:
        return None
    row["favorited"] = not bool(row.get("favorited"))
    if mock_data.fallback_run_detail["run_id"] == run_id:
        mock_data.fallback_run_detail["favorited"] = row["favorited"]
    return {"run_id": run_id, "favorited": row["favorited"]}


def _next_backtest_id() -> str:
    ids = [row["run_id"] for row in mock_data.fallback_runs_list + mock_data.fallback_runs_queue]
    max_number = max((int(run_id.rsplit("_", 1)[1]) for run_id in ids if run_id.startswith("btk_")), default=0)
    return f"btk_{max_number + 1:04d}"


def register_new_backtest(config: BacktestConfig) -> RunRowSummary:
    summary = {
        "run_id": _next_backtest_id(),
        "strategy": config.preset,
        "status": "queued",
        "params_summary": (
            f"N={config.universe.topN} · {config.window.rebalance} · "
            f"{config.window.start.year}→{config.window.end.year}"
        ),
    }
    mock_data.fallback_runs_queue.insert(0, summary)
    return RunRowSummary.model_validate(summary)


def get_compare(ids: list[str], range_: str) -> ComparePayload:
    settings = get_settings().model_copy(update={"anchor_date": today()})
    try:
        payload = load_compare_from_reports(settings, ids, range_)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock compare: %s", exc)
        return _get_compare_mock(ids, range_)
    return ComparePayload.model_validate(payload)


def _get_compare_mock(ids: list[str], range_: str) -> ComparePayload:
    del range_
    payload = deepcopy(mock_data.fallback_compare)
    present = [run_id for run_id in ids if run_id in payload["metrics"]["cagr"]]
    if not present:
        return ComparePayload.model_validate(payload)
    index_by_id = {"atlas": 0, "momentum": 1, "meanrev": 2}
    label_by_id = {"atlas": "ATLAS v3", "momentum": "Momentum", "meanrev": "MeanRev"}
    indices = [index_by_id[run_id] for run_id in present]
    payload["equity"] = [
        {"ts": point["ts"], "values": {run_id: point["values"][run_id] for run_id in present}}
        for point in payload["equity"]
    ]
    payload["metrics"] = {
        metric: {run_id: values[run_id] for run_id in present}
        for metric, values in payload["metrics"].items()
    }
    payload["overlap"]["symbols"] = [label_by_id[run_id] for run_id in present]
    payload["overlap"]["matrix"] = [
        [payload["overlap"]["matrix"][row_index][column_index] for column_index in indices]
        for row_index in indices
    ]
    payload["overlap"]["sharedHoldings"] = [
        {**holding, "count": min(holding["count"], len(present)), "total": len(present)}
        for holding in payload["overlap"]["sharedHoldings"]
    ]
    return ComparePayload.model_validate(payload)


def get_universe_timeline() -> UniverseTimelinePayload:
    settings = get_settings()
    try:
        payload = load_universe_timeline_from_processed(settings)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock universe timeline: %s", exc)
        payload = deepcopy(mock_data.fallback_universe_timeline)
    return UniverseTimelinePayload.model_validate(payload)


def get_data_sources() -> list[DataSource]:
    return [DataSource.model_validate(row) for row in mock_data.fallback_data_sources]


def get_data_alerts() -> list[DataAlert]:
    settings = get_settings()
    try:
        rows = load_data_alerts_from_processed(settings)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock data alerts: %s", exc)
        rows = deepcopy(mock_data.fallback_data_alerts)
    return [DataAlert.model_validate(row) for row in rows]


def refresh_universe() -> dict[str, str]:
    return {"refreshed_at": utc_now_iso()}


def get_featured_digest() -> FeaturedDigest:
    settings = get_settings().model_copy(update={"anchor_date": today()})
    markdown = _newest_markdown(settings.report_root)
    if markdown is None:
        return FeaturedDigest.model_validate(deepcopy(mock_data.fallback_featured_digest))

    overview, used_fallback = _load_overview_payload(settings, log_warning=True)
    if used_fallback:
        return FeaturedDigest.model_validate(deepcopy(mock_data.fallback_featured_digest))

    generated_at = utc_iso_from_path_mtime(markdown)
    generated_date = generated_at[:10]
    ytd_pct = overview["hero_kpi"]["ytdReturn"] * 100.0
    return FeaturedDigest.model_validate(
        {
            "id": markdown.stem,
            "title": f"Atlas20 Digest — {generated_date}",
            "subtitle": f"{overview['champion']['strategy']} · YTD {ytd_pct:+,.2f}% · generated {generated_at}",
            "formats": deepcopy(mock_data.fallback_featured_digest["formats"]),
            "defaultFormat": "markdown",
            "generated_at": generated_at,
        }
    )


def _newest_markdown(report_root: Path) -> Path | None:
    reports = [path for path in report_root.rglob("*.md") if path.is_file()]
    if not reports:
        return None
    return max(reports, key=lambda path: path.stat().st_mtime)

def _load_overview_payload(settings: Settings, *, log_warning: bool) -> tuple[dict[str, Any], bool]:
    try:
        return load_overview_from_reports(settings), False
    except (FileNotFoundError, ValueError) as exc:
        if log_warning:
            logger.warning("Falling back to mock overview: %s", exc)
        return deepcopy(mock_data.fallback_overview), True


def list_reports(sort: str = "recent") -> list[ReportEntry]:
    rows = list(mock_data.fallback_reports)
    if sort == "oldest":
        rows.sort(key=lambda row: row["generated_at"])
    elif sort == "size":
        rows.sort(key=lambda row: row["size_bytes"], reverse=True)
    elif sort == "type":
        rows.sort(key=lambda row: row["report_type"])
    else:
        rows.sort(key=lambda row: row["generated_at"], reverse=True)
    return [ReportEntry.model_validate(row) for row in rows]


def build_digest_download_url(fmt: str) -> dict[str, str]:
    return {"url": f"/static/reports/digest.{fmt}"}


def build_report_download_url(report_id: str, fmt: str | None = None) -> dict[str, str] | None:
    if not any(row["id"] == report_id for row in mock_data.fallback_reports):
        return None
    extension = fmt or "markdown"
    return {"url": f"/static/reports/{report_id}.{extension}"}
