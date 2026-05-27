"""Subprocess entry point for executing one queued backtest run."""

from __future__ import annotations

import atexit
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

import pandas as pd
from sqlmodel import Session

from atlas20.api._time import utc_iso_from_timestamp
from atlas20.config import load_config
from atlas20.api.config_adapter import to_research_config
from atlas20.api.repositories import RunsRepo, get_engine
from atlas20.api.schemas import BacktestConfig
from atlas20.api.services_report import generate_run_report_with_warnings
from atlas20.api.settings import Settings, get_settings
from atlas20.backtest.engine import run_backtest
from atlas20.data.processor import download_and_cache_raw_data
from atlas20.pipeline import run_research_pipeline
from atlas20.reporting.report import _pipeline_version, _publish_report_dir, _write_latest_link, _write_latest_pointer


PRESET_SLUG_PATTERN = re.compile(r"[^a-z0-9_]+")


def _cleanup_metrics_files() -> None:
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(os.getpid())


atexit.register(_cleanup_metrics_files)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _code_commit(settings: Settings) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=settings.project_root,
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        commit = completed.stdout.strip()
        if commit:
            return commit
    except (OSError, subprocess.SubprocessError):
        pass
    return os.environ.get("ATLAS20_CODE_COMMIT", "unknown")


def _preset_slug(preset: str) -> str:
    slug = PRESET_SLUG_PATTERN.sub("_", preset.lower()).strip("_")
    if not slug:
        raise ValueError("invalid preset slug")
    return slug


def _relative_to_project(settings: Settings, path: Path) -> str:
    try:
        return path.resolve().relative_to(settings.project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _config_file(settings: Settings, params_json: str) -> Path:
    config = BacktestConfig.model_validate_json(params_json)
    config_dir = settings.project_root / "config"
    candidate = config_dir / f"{_preset_slug(config.preset)}.yaml"
    return candidate if candidate.exists() else config_dir / "base.yaml"


def _config_metadata(settings: Settings, params_json: str) -> tuple[str, str]:
    path = _config_file(settings, params_json)
    try:
        config_hash = _sha256_file(path)
    except FileNotFoundError:
        config_hash = "unknown"
    return _relative_to_project(settings, path), config_hash


def _data_snapshot(settings: Settings) -> dict[str, str]:
    raw_dir = settings.data_root / "raw"
    if not raw_dir.exists():
        return {}

    snapshot: dict[str, str] = {}
    for provider_dir in sorted(path for path in raw_dir.iterdir() if path.is_dir()):
        newest_mtime: float | None = None
        for path in provider_dir.rglob("*"):
            if not path.is_file():
                continue
            mtime = path.stat().st_mtime
            newest_mtime = mtime if newest_mtime is None else max(newest_mtime, mtime)
        if newest_mtime is not None:
            snapshot[provider_dir.name] = utc_iso_from_timestamp(newest_mtime)
    return snapshot


def _engine_version() -> str:
    override = os.environ.get("ATLAS20_ENGINE_VERSION")
    if override:
        return override
    try:
        engine_path = Path(run_backtest.__code__.co_filename)
        return _sha256_file(engine_path)
    except (OSError, AttributeError):
        return "unknown"


def _run_pipeline_version() -> str:
    return os.environ.get("ATLAS20_PIPELINE_VERSION") or _pipeline_version()


def _artifact_hashes(report_dir: Path) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            artifacts[path.relative_to(report_dir).as_posix()] = _sha256_file(path)
    return artifacts


def _write_manifest(report_dir: Path, settings: Settings, params_json: str) -> None:
    config_path, config_hash = _config_metadata(settings, params_json)
    manifest = {
        "code_commit": _code_commit(settings),
        "config_path": config_path,
        "config_hash": config_hash,
        "data_snapshot": _data_snapshot(settings),
        "engine_version": _engine_version(),
        "params_hash": _sha256_text(params_json),
        "pipeline_version": _run_pipeline_version(),
        "artifacts": _artifact_hashes(report_dir),
    }
    (report_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_mock_artifacts(report_dir: Path) -> None:
    weights_dir = report_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "summary.csv").write_text(
        "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,calmar,"
        "monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings\n"
        "ATLAS_MOCK,0.25,0.25,0.20,1.5,1.8,-0.1,2.5,0.60,0.20,0.05,5\n"
        "BTC_BH__always_on,0.12,0.12,0.25,0.8,1.0,-0.2,0.6,0.55,0.00,0.00,1\n"
        "TOP20_EQ__always_on,0.18,0.18,0.22,1.1,1.2,-0.15,1.2,0.58,0.10,0.04,20\n"
        "TOP20_MOM_alpha,0.25,0.25,0.20,1.5,1.8,-0.1,2.5,0.60,0.20,0.05,5\n"
        "TOP20_SECTOR_beta,0.20,0.20,0.21,1.2,1.4,-0.12,1.7,0.57,0.18,0.04,5\n",
        encoding="utf-8",
    )
    (report_dir / "yearly_returns.csv").write_text(
        "year,ATLAS_MOCK,BTC_BH__always_on,TOP20_EQ__always_on,TOP20_MOM_alpha,TOP20_SECTOR_beta\n"
        "2025,0.10,0.04,0.08,0.10,0.09\n"
        "2026,0.15,0.08,0.10,0.15,0.11\n",
        encoding="utf-8",
    )
    (report_dir / "regime_performance.csv").write_text(
        "strategy,regime,annualized_return\n"
        "ATLAS_MOCK,bull,0.25\n"
        "BTC_BH__always_on,bull,0.12\n"
        "TOP20_EQ__always_on,bull,0.18\n"
        "TOP20_MOM_alpha,bull,0.25\n"
        "TOP20_SECTOR_beta,bull,0.20\n",
        encoding="utf-8",
    )
    (report_dir / "equity_curve.csv").write_text(
        "date,ATLAS_MOCK\n2026-01-01,1.0\n2026-01-02,1.25\n",
        encoding="utf-8",
    )
    (report_dir / "daily_returns.csv").write_text(
        "date,ATLAS_MOCK\n2026-01-01,0.0\n2026-01-02,0.25\n",
        encoding="utf-8",
    )
    (weights_dir / "ATLAS_MOCK.csv").write_text(
        "date,BTC,ETH\n2026-01-01,0.5,0.5\n2026-01-02,0.6,0.4\n",
        encoding="utf-8",
    )
    (report_dir / "selection_history.csv").write_text(
        "rebalance_date,coin_id,rank,weight\n2026-01-01,bitcoin,1,0.5\n",
        encoding="utf-8",
    )


def _ensure_brief_artifact_names(report_dir: Path) -> None:
    aliases = {
        "strategy_summary.csv": "summary.csv",
        "equity_curves.csv": "equity_curve.csv",
    }
    for source_name, target_name in aliases.items():
        source = report_dir / source_name
        target = report_dir / target_name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)


def _float_or_none(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _normalised_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _completion_summary_row(summary: pd.DataFrame, strategy: str | None) -> Any:
    if summary.empty:
        return None
    if strategy and "strategy" in summary.columns:
        target = _normalised_name(strategy)
        for _, row in summary.iterrows():
            row_strategy = row.get("strategy")
            if isinstance(row_strategy, str) and _normalised_name(row_strategy) == target:
                return row
    return summary.iloc[0]


def _completion_metrics(report_dir: Path, strategy: str | None = None) -> dict[str, float | None]:
    summary_path = report_dir / "summary.csv"
    if not summary_path.exists():
        summary_path = report_dir / "strategy_summary.csv"
    summary = pd.read_csv(summary_path)
    row = _completion_summary_row(summary, strategy)
    if row is None:
        return {"return_pct": None, "sharpe": None, "max_dd": None}
    return {
        "return_pct": _float_or_none(row.get("total_return", row.get("cagr"))),
        "sharpe": _float_or_none(row.get("sharpe")),
        "max_dd": _float_or_none(row.get("max_drawdown", row.get("max_dd"))),
    }


def _prepare_tmp_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _execute_pipeline(params_json: str, settings: Settings, tmp_dir: Path) -> None:
    config = BacktestConfig.model_validate_json(params_json)
    if os.environ.get("ATLAS20_WORKER_MOCK") == "1":
        _prepare_tmp_dir(tmp_dir)
        _write_mock_artifacts(tmp_dir)
        return

    research_config = to_research_config(config, config.preset, settings)
    research_config.paths.reports_dir = str(tmp_dir)
    run_research_pipeline(research_config)
    _ensure_brief_artifact_names(tmp_dir)


def _execute_universe_refresh(settings: Settings) -> None:
    if os.environ.get("ATLAS20_WORKER_MOCK") == "1":
        coingecko_dir = settings.data_root / "raw" / "coingecko"
        cryptocompare_dir = settings.data_root / "raw" / "cryptocompare" / "histoday"
        coingecko_dir.mkdir(parents=True, exist_ok=True)
        cryptocompare_dir.mkdir(parents=True, exist_ok=True)
        (coingecko_dir / "universe_refresh_mock.json").write_text('{"status": "ok"}\n', encoding="utf-8")
        (cryptocompare_dir / "BTC.json").write_text('{"Response": "Success", "Data": {"Data": []}}\n', encoding="utf-8")
        return

    config = load_config(settings.project_root / "config" / "base.yaml")
    config.paths.raw_dir = str(settings.data_root / "raw")
    download_and_cache_raw_data(config)


def _register_completion_reports(run_id: str, settings: Settings) -> None:
    engine = get_engine(settings)
    with Session(engine) as session:
        generate_run_report_with_warnings(
            run_id,
            {"markdown", "png", "csv", "bundle"},
            session=session,
            settings=settings,
        )
        session.commit()


def run(run_id: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    engine = get_engine(settings)
    report_root = Path(settings.report_root)
    tmp_dir = report_root / "app_runs" / f"{run_id}.tmp"
    final_dir = report_root / "app_runs" / run_id
    started = time.monotonic()

    with Session(engine) as session:
        run_row = RunsRepo(session).get(run_id)
        if run_row is None:
            print(f"run not found: {run_id}", file=sys.stderr)
            return 1
        params_json = run_row.params
        strategy = run_row.strategy

    try:
        if strategy == "universe_refresh":
            _execute_universe_refresh(settings)
            duration_s = max(0, int(time.monotonic() - started))
            with Session(engine) as session:
                RunsRepo(session).update_metrics_from_completion(
                    run_id,
                    return_pct=None,
                    sharpe=None,
                    max_dd=None,
                    duration_s=duration_s,
                )
                session.commit()
            return 0

        if not params_json:
            raise ValueError("run params are missing")
        _execute_pipeline(params_json, settings, tmp_dir)
        (tmp_dir / "params.json").write_text(
            json.dumps(json.loads(params_json), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_manifest(tmp_dir, settings, params_json)
        metrics = _completion_metrics(tmp_dir, strategy)
        # Batch 1's publisher uses backup-rename semantics: move existing to
        # .backup, move tmp to final, then delete .backup after success.
        # This keeps rollback behavior for partial publish failures.
        _publish_report_dir(tmp_dir, final_dir)
        # Re-point latest aliases at the *final* directory, not the .tmp path
        # the pipeline wrote during export_result_tables.
        _write_latest_pointer(final_dir)
        _write_latest_link(final_dir)
        duration_s = max(0, int(time.monotonic() - started))

        with Session(engine) as session:
            RunsRepo(session).update_metrics_from_completion(
                run_id,
                return_pct=metrics["return_pct"],
                sharpe=metrics["sharpe"],
                max_dd=metrics["max_dd"],
                duration_s=duration_s,
            )
            session.commit()
        try:
            _register_completion_reports(run_id, settings)
        except Exception as exc:
            print(f"report generation failed for {run_id}: {exc}", file=sys.stderr)
        return 0
    except Exception as exc:
        with Session(engine) as session:
            RunsRepo(session).update_metrics_from_completion(
                run_id,
                status="failed",
                error=str(exc)[:1000],
                heartbeat_at=None,
                worker_pid=None,
            )
            session.commit()
        print(str(exc), file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m atlas20.api.worker.run_one RUN_ID", file=sys.stderr)
        return 2
    return run(args[0])


if __name__ == "__main__":
    raise SystemExit(main())
