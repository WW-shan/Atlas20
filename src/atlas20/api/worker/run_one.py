"""Subprocess entry point for executing one queued backtest run."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

import pandas as pd
from sqlmodel import Session

from atlas20.api.config_adapter import to_research_config
from atlas20.api.repositories import RunsRepo, get_engine
from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import Settings, get_settings
from atlas20.pipeline import run_research_pipeline
from atlas20.reporting.report import _publish_report_dir


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


def _artifact_hashes(report_dir: Path) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            artifacts[path.relative_to(report_dir).as_posix()] = _sha256_file(path)
    return artifacts


def _write_manifest(report_dir: Path, settings: Settings, params_json: str) -> None:
    manifest = {
        "code_commit": _code_commit(settings),
        "config_hash": _sha256_text(params_json),
        "artifacts": _artifact_hashes(report_dir),
    }
    (report_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_mock_artifacts(report_dir: Path) -> None:
    weights_dir = report_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "summary.csv").write_text(
        "strategy,total_return,cagr,sharpe,max_drawdown\n"
        "ATLAS_MOCK,0.25,0.25,1.5,-0.1\n",
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


def _completion_metrics(report_dir: Path) -> dict[str, float | None]:
    summary_path = report_dir / "summary.csv"
    if not summary_path.exists():
        summary_path = report_dir / "strategy_summary.csv"
    summary = pd.read_csv(summary_path)
    if summary.empty:
        return {"return_pct": None, "sharpe": None, "max_dd": None}
    row = summary.iloc[0]
    return {
        "return_pct": _float_or_none(row.get("total_return", row.get("cagr"))),
        "sharpe": _float_or_none(row.get("sharpe")),
        "max_dd": _float_or_none(row.get("max_drawdown", row.get("max_dd"))),
    }


def _prepare_tmp_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)


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

    try:
        if not params_json:
            raise ValueError("run params are missing")
        _execute_pipeline(params_json, settings, tmp_dir)
        (tmp_dir / "params.json").write_text(
            json.dumps(json.loads(params_json), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_manifest(tmp_dir, settings, params_json)
        metrics = _completion_metrics(tmp_dir)
        _publish_report_dir(tmp_dir, final_dir)
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
        return 0
    except Exception as exc:
        with Session(engine) as session:
            RunsRepo(session).update(
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
