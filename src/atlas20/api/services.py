"""Services for the Atlas20 R3 mock-backed API."""

from __future__ import annotations

import logging
import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session

from atlas20.api import mock_data
from atlas20.api._time import today, utc_iso_from_path_mtime, utc_now
from atlas20.api.config_adapter import to_research_config
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
from atlas20.api.db.models import Run
from atlas20.api.repositories import IdempotencyRepo, KvRepo, ReportsRepo, RunsRepo
from atlas20.api.services_download import resolve_download as _resolve_download
from atlas20.api.settings import Settings, get_settings

logger = logging.getLogger(__name__)

RUN_FAMILY_CHIPS = {"ATLAS", "Momentum", "MeanRev", "Carry", "Other"}
RUN_STATUS_CHIPS = {"queued", "running", "completed", "failed", "cancelled"}
DATA_SOURCE_CACHE_TTL_SECONDS = 300
DATA_SOURCE_STALE_SECONDS = 999999
_DATA_SOURCES_CACHE: tuple[Path, float, list[DataSource]] | None = None


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


def list_runs_queue(session: Session) -> list[RunRowSummary]:
    return [_run_to_summary(row) for row in RunsRepo(session).list_queue()]


def _date_cutoff(date_range: str) -> date | None:
    if date_range == "all":
        return None
    current_day = today()
    if date_range == "ytd":
        return date(current_day.year, 1, 1)
    days = {"7d": 7, "30d": 30, "90d": 90}.get(date_range, 30)
    return current_day - timedelta(days=days)


def _datetime_to_api_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _spark_values(value: str | None) -> list[float] | None:
    if not value:
        return None
    try:
        raw = json.loads(value)
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, list) else None


def _run_to_row(run: Run) -> RunRow:
    return RunRow.model_validate(
        {
            "run_id": run.run_id,
            "strategy": run.strategy,
            "strategy_family": run.strategy_family,
            "universe": run.universe,
            "window": {"start": run.window_start.isoformat(), "end": run.window_end.isoformat()},
            "status": run.status,
            "return_pct": run.return_pct,
            "sharpe": run.sharpe,
            "max_dd": run.max_dd,
            "duration_s": run.duration_s,
            "eta_s": run.eta_s,
            "spark": _spark_values(run.spark),
            "created_at": _datetime_to_api_iso(run.created_at),
            "favorited": run.favorited,
        }
    )


def _run_to_summary(run: Run) -> RunRowSummary:
    return RunRowSummary.model_validate(
        {
            "run_id": run.run_id,
            "strategy": run.strategy,
            "status": run.status,
            "duration_s": run.duration_s,
            "eta_s": run.eta_s,
            "params_summary": _params_summary_from_run(run),
            "favorited": run.favorited,
        }
    )


def _params_summary_from_run(run: Run) -> str:
    if run.params:
        try:
            return _params_summary_from_config(BacktestConfig.model_validate(json.loads(run.params)))
        except (json.JSONDecodeError, ValueError):
            pass
    return f"{run.universe} \u00b7 {run.window_start.year}\u2192{run.window_end.year}"


def _params_summary_from_config(config: BacktestConfig) -> str:
    return (
        f"N={config.universe.topN} \u00b7 {config.window.rebalance} \u00b7 "
        f"{config.window.start.year}\u2192{config.window.end.year}"
    )


def list_runs(
    session: Session,
    q: str = "",
    chips: list[str] | None = None,
    date_range: str = "30d",
    page: int = 1,
    page_size: int = 14,
) -> tuple[list[RunRow], int]:
    chip_values = [chip for chip in chips or [] if chip]
    date_cutoff = _date_cutoff(date_range)
    repo = RunsRepo(session)
    rows, total = repo.list(
        q=q,
        chips=chip_values,
        date_cutoff=date_cutoff,
        page=page,
        page_size=page_size,
    )
    if total > 0:
        return [_run_to_row(row) for row in rows], total

    _, unfiltered_total = repo.list(date_cutoff=None, page=1, page_size=1)
    if unfiltered_total > 0:
        return [], 0

    settings = get_settings()
    disk_rows = _load_runs_from_disk(
        settings.report_root / "app_runs",
        q=q,
        chips=chip_values,
        date_cutoff=date_cutoff,
    )
    if not disk_rows:
        return [], 0

    safe_page = max(page, 1)
    safe_page_size = max(page_size, 1)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return disk_rows[start:end], len(disk_rows)


def get_run(session: Session, run_id: str) -> RunRow | None:
    row = RunsRepo(session).get(run_id)
    return _run_to_row(row) if row else None


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


def get_run_detail(session: Session, run_id: str) -> RunDetailPayload | None:
    if run_id == mock_data.fallback_run_detail["run_id"]:
        canonical = deepcopy(mock_data.fallback_run_detail)
        db_row = RunsRepo(session).get(run_id)
        if db_row is not None:
            canonical["favorited"] = db_row.favorited
        return RunDetailPayload.model_validate(canonical)

    run = RunsRepo(session).get(run_id)
    if run is None:
        return None
    row = _run_to_row(run).model_dump(mode="json")
    detail = {
        **row,
        "equity_overlay": {"series": mock_data.fallback_overview["equity_overlay"]["series"]},
        "kpi": _derive_kpi_from_row(row),
    }
    return RunDetailPayload.model_validate(detail)


def toggle_run_favorite(session: Session, run_id: str) -> dict[str, Any] | None:
    run = RunsRepo(session).toggle_favorite(run_id)
    if run is None:
        return None
    return {"run_id": run_id, "favorited": run.favorited}


def _load_runs_from_disk(
    app_runs_root: Path,
    *,
    q: str = "",
    chips: list[str] | tuple[str, ...] = (),
    date_cutoff: date | None = None,
) -> list[RunRow]:
    if not app_runs_root.exists():
        return []

    manifests = sorted(
        app_runs_root.glob("*/manifest.json"),
        key=lambda path: (path.stat().st_mtime, path.as_posix()),
        reverse=True,
    )
    rows: list[RunRow] = []
    for manifest_path in manifests:
        try:
            row = _load_run_row_from_manifest(manifest_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Skipping disk run manifest %s: %s", manifest_path, exc)
            continue
        if _disk_run_matches_filters(row, q=q, chips=chips, date_cutoff=date_cutoff):
            rows.append(row)
    return rows


def _load_run_row_from_manifest(manifest_path: Path) -> RunRow:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")

    metrics = manifest.get("metrics")
    metrics_dict = metrics if isinstance(metrics, dict) else {}
    window = manifest.get("window")
    if isinstance(window, dict):
        window_start = _manifest_string(window, "start", "start_date", "from")
        window_end = _manifest_string(window, "end", "end_date", "to")
    else:
        window_start = None
        window_end = None
    created_at = _manifest_created_at(manifest, manifest_path)
    if window_start is None or window_end is None:
        created_date = created_at[:10]
        window_start = window_start or created_date
        window_end = window_end or created_date

    return RunRow.model_validate(
        {
            "run_id": _manifest_string(manifest, "run_id", "id", "runId"),
            "strategy": _manifest_string(manifest, "strategy", "preset", "name"),
            "strategy_family": _manifest_string(manifest, "strategy_family", "family"),
            "universe": _manifest_universe(manifest),
            "window": {"start": window_start, "end": window_end},
            "status": _manifest_string(manifest, "status") or "completed",
            "return_pct": _manifest_metric_float(manifest, metrics_dict, "return_pct", "total_return", "cagr"),
            "sharpe": _manifest_metric_float(manifest, metrics_dict, "sharpe"),
            "max_dd": _manifest_metric_float(manifest, metrics_dict, "max_dd", "max_drawdown"),
            "duration_s": _manifest_metric_int(manifest, metrics_dict, "duration_s", "duration"),
            "eta_s": _manifest_metric_int(manifest, metrics_dict, "eta_s", "eta"),
            "spark": _manifest_spark(manifest, metrics_dict),
            "created_at": created_at,
            "favorited": bool(manifest.get("favorited", False)),
        }
    )


def _disk_run_matches_filters(
    row: RunRow,
    *,
    q: str,
    chips: list[str] | tuple[str, ...],
    date_cutoff: date | None,
) -> bool:
    if q:
        pattern = q.lower()
        if not any(
            pattern in value
            for value in [
                row.run_id.lower(),
                row.strategy.lower(),
                row.universe.lower(),
                (row.strategy_family or "").lower(),
            ]
        ):
            return False

    for chip in [item for item in chips if item]:
        if chip == "favorited":
            if not row.favorited:
                return False
        elif chip in RUN_STATUS_CHIPS:
            if row.status != chip:
                return False
        elif chip in RUN_FAMILY_CHIPS:
            if row.strategy_family != chip:
                return False
        else:
            if chip.lower() not in row.strategy.lower():
                return False

    if date_cutoff is not None:
        created_at = _parse_api_datetime(row.created_at)
        if created_at.date() < date_cutoff:
            return False
    return True


def _manifest_string(manifest: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = manifest.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _manifest_universe(manifest: dict[str, Any]) -> str:
    universe = manifest.get("universe")
    if isinstance(universe, str) and universe.strip():
        return universe.strip()

    params = manifest.get("params")
    if isinstance(params, dict):
        nested_universe = params.get("universe")
        if isinstance(nested_universe, dict):
            top_n = nested_universe.get("topN")
            if top_n is not None:
                return f"Top-{top_n}"
    return "Unknown"


def _manifest_metric_float(
    manifest: dict[str, Any],
    metrics: dict[str, Any],
    *keys: str,
) -> float | None:
    for source in (metrics, manifest):
        for key in keys:
            value = source.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _manifest_metric_int(
    manifest: dict[str, Any],
    metrics: dict[str, Any],
    *keys: str,
) -> int | None:
    for source in (metrics, manifest):
        for key in keys:
            value = source.get(key)
            if value is None:
                continue
            try:
                return int(float(value))
            except (TypeError, ValueError):
                continue
    return None


def _manifest_spark(manifest: dict[str, Any], metrics: dict[str, Any]) -> list[float] | None:
    for source in (metrics, manifest):
        value = source.get("spark")
        if isinstance(value, list):
            try:
                return [float(item) for item in value]
            except (TypeError, ValueError):
                continue
    return None


def _manifest_created_at(manifest: dict[str, Any], manifest_path: Path) -> str:
    for key in ("created_at", "generated_at", "timestamp"):
        value = manifest.get(key)
        if isinstance(value, str) and value.strip():
            parsed = _parse_api_datetime(value)
            return _datetime_to_api_iso(parsed)
    return utc_iso_from_path_mtime(manifest_path)


def _parse_api_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)




def _strategy_family(strategy: str) -> str:
    if "ATLAS" in strategy:
        return "ATLAS"
    if "Momentum" in strategy:
        return "Momentum"
    if "Mean" in strategy:
        return "MeanRev"
    if "Carry" in strategy:
        return "Carry"
    return "Other"




def register_new_backtest(session: Session, config: BacktestConfig) -> RunRowSummary:
    settings = get_settings()
    # Validate adapter inputs before persisting; the worker rebuilds this config when executing.
    to_research_config(config, config.preset, settings)
    repo = RunsRepo(session)
    run = repo.create_with_unique_id(
        {
            "strategy": config.preset,
            "strategy_family": _strategy_family(config.preset),
            "universe": f"Top-{config.universe.topN}",
            "window_start": config.window.start,
            "window_end": config.window.end,
            "status": "queued",
            "spark": json.dumps([]),
            "params": config.model_dump_json(),
            "created_at": utc_now(),
        }
    )
    IdempotencyRepo(session).purge_expired()
    return _run_to_summary(run)


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
    settings = get_settings()
    raw_root = settings.data_root / "raw"
    if not raw_root.exists():
        return [DataSource.model_validate(row) for row in mock_data.fallback_data_sources]

    global _DATA_SOURCES_CACHE
    now_ts = utc_now().timestamp()
    if _DATA_SOURCES_CACHE is not None:
        cached_root, cached_at, cached_sources = _DATA_SOURCES_CACHE
        if cached_root == settings.data_root and now_ts - cached_at < DATA_SOURCE_CACHE_TTL_SECONDS:
            return [source.model_copy(deep=True) for source in cached_sources]

    sources = [
        _data_source_status(row["id"], row["name"], raw_root / row["id"], now_ts)
        for row in mock_data.fallback_data_sources
    ]
    _DATA_SOURCES_CACHE = (settings.data_root, now_ts, sources)
    return [source.model_copy(deep=True) for source in sources]


def _data_source_status(source_id: str, name: str, path: Path, now_ts: float) -> DataSource:
    latest_mtime = _latest_file_mtime(path)
    if latest_mtime is None:
        return DataSource(id=source_id, name=name, status="error", last_sync_seconds=DATA_SOURCE_STALE_SECONDS)

    age_seconds = max(0, int(now_ts - latest_mtime))
    if age_seconds < 3600:
        status = "healthy"
    elif age_seconds < 86400:
        status = "degraded"
    else:
        status = "error"
    return DataSource(id=source_id, name=name, status=status, last_sync_seconds=age_seconds)


def _latest_file_mtime(path: Path) -> float | None:
    if not path.exists():
        return None
    latest_mtime: float | None = None
    for candidate in path.rglob("*"):
        if not candidate.is_file():
            continue
        mtime = candidate.stat().st_mtime
        latest_mtime = mtime if latest_mtime is None else max(latest_mtime, mtime)
    return latest_mtime


def get_data_alerts() -> list[DataAlert]:
    settings = get_settings()
    try:
        rows = load_data_alerts_from_processed(settings)
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Falling back to mock data alerts: %s", exc)
        rows = deepcopy(mock_data.fallback_data_alerts)
    return [DataAlert.model_validate(row) for row in rows]


def refresh_universe(session: Session) -> dict[str, str]:
    repo = RunsRepo(session)
    existing = repo.find_latest_by_strategy_status("universe_refresh", ("queued", "running"))
    if existing is not None:
        return {"run_id": existing.run_id, "status": existing.status}

    current_day = today()
    run = repo.create_with_unique_id(
        {
            "strategy": "universe_refresh",
            "strategy_family": "Other",
            "universe": "Data Sources",
            "window_start": current_day,
            "window_end": current_day,
            "status": "queued",
            "spark": json.dumps([]),
            "params": json.dumps({"kind": "universe_refresh"}),
            "created_at": utc_now(),
        }
    )
    return {"run_id": run.run_id, "status": run.status}


def get_universe_refresh_status(session: Session) -> dict[str, str | None]:
    row = RunsRepo(session).find_latest_by_strategy_status("universe_refresh", tuple(RUN_STATUS_CHIPS))
    if row is None:
        return {"run_id": None, "status": "idle"}
    return {"run_id": row.run_id, "status": row.status}


def get_featured_digest(session: Session | None = None) -> FeaturedDigest:
    settings = get_settings().model_copy(update={"anchor_date": today()})
    if session is not None:
        featured = _featured_digest_from_kv(session, settings)
        if featured is not None:
            return featured

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
            "title": f"Atlas20 Digest \u2014 {generated_date}",
            "subtitle": f"{overview['champion']['strategy']} \u00b7 YTD {ytd_pct:+,.2f}% \u00b7 generated {generated_at}",
            "formats": deepcopy(mock_data.fallback_featured_digest["formats"]),
            "defaultFormat": "markdown",
            "generated_at": generated_at,
        }
    )


def _featured_digest_from_kv(session: Session, settings: Settings) -> FeaturedDigest | None:
    run_id = KvRepo(session).get("featured_digest_run_id")
    if not run_id:
        return None
    run = RunsRepo(session).get(run_id)
    if run is None:
        return None
    reports_repo = ReportsRepo(session)
    markdown = reports_repo.by_run_kind(run_id, "markdown")
    if markdown is None:
        return None
    markdown_path = settings.report_root / markdown.path
    if not markdown_path.exists():
        return None
    generated_at = _datetime_to_api_iso(markdown.generated_at)
    available_formats = [
        kind
        for kind in ("markdown", "pdf", "png", "csv")
        if reports_repo.by_run_kind(run_id, kind) is not None
    ]
    return FeaturedDigest.model_validate(
        {
            "id": run_id,
            "title": f"Atlas20 Digest - {generated_at[:10]}",
            "subtitle": f"{run.strategy} - generated {generated_at}",
            "formats": available_formats or ["markdown"],
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


def _report_file_to_entry(row) -> ReportEntry:
    report_id = str(row.id or row.run_id or row.sha256[:12])
    title_id = row.run_id or report_id
    thumbnail_by_kind = {
        "markdown": "lines",
        "pdf": "bars",
        "png": "equity",
        "csv": "horizontal-bars",
        "bundle": "sparkbar",
    }
    return ReportEntry.model_validate(
        {
            "id": report_id,
            "title": f"{title_id} {row.kind} report",
            "subtitle": f"{row.path} - {row.size_bytes} bytes",
            "thumbnail": thumbnail_by_kind.get(row.kind, "lines"),
            "status": "ready",
            "generated_at": _datetime_to_api_iso(row.generated_at),
            "size_bytes": row.size_bytes,
            "report_type": "run" if row.run_id else "weekly",
        }
    )


def list_reports(sort: str = "recent", session: Session | None = None) -> list[ReportEntry]:
    if session is not None:
        rows = ReportsRepo(session).list(sort=sort)
        if rows:
            return [_report_file_to_entry(row) for row in rows]

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


def resolve_download(report_id: str, fmt: str | None, session: Session):
    return _resolve_download(report_id, fmt, session)
