"""API runs must not touch shared data or become the published source unless they complete."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import shutil

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from atlas20.api.db.models import ReportFile, Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.settings import Settings
from atlas20.api.worker import run_one
from atlas20.reporting.report import _write_latest_pointer

REPO_ROOT = Path(__file__).resolve().parents[1]
PARAMS = {
    "preset": "base",
    "universe": {"topN": 5, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2026-01-01", "end": "2026-02-01", "rebalance": "Weekly"},
    "allocation": {"positionPct": 25.0, "slots": 3},
    "costs": {"feeBps": 1.0, "slippageBps": 1.0},
}
SUMMARY = (
    "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,calmar,"
    "monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings\n"
    "base,0.30,0.30,0.20,1.40,1.60,-0.10,3.0,0.60,0.20,0.05,3\n"
)
SHARED_PROCESSED = ("panel_daily.csv", "metadata.csv", "data_quality.csv", "regime_frame.csv", "rebalance_universe.csv")


@pytest.fixture
def isolated(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "config").mkdir(parents=True)
    for name in ("base.yaml", "sectors.yaml"):
        shutil.copy2(REPO_ROOT / "config" / name, project_root / "config" / name)
    data_root = tmp_path / "data"
    settings = Settings(
        db_url=f"sqlite:///{(tmp_path / 'isolation.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        data_root=data_root,
        project_root=project_root,
    )
    engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    # The shared processed data the universe timeline and alerts serve.
    for processed in (data_root / "processed", project_root / "data" / "processed"):
        processed.mkdir(parents=True)
        for name in SHARED_PROCESSED:
            (processed / name).write_text(f"shared {name}\n", encoding="utf-8")
    settings.report_root.mkdir(parents=True)
    (settings.report_root / "latest.txt").write_text("app_runs/btk_0000\n", encoding="utf-8")
    (settings.report_root / "app_runs" / "btk_0000").mkdir(parents=True)
    yield settings, engine
    engine.dispose()


def _create_run(engine, *, status: str = "running", requested_cancel: bool = False) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                run_id="btk_0001",
                strategy="base",
                universe="Top-5",
                window_start=date(2026, 1, 1),
                window_end=date(2026, 2, 1),
                status=status,
                requested_cancel=requested_cancel,
                params=json.dumps(PARAMS),
            )
        )
        session.commit()


def _fake_pipeline(calls: dict[str, object]):
    def pipeline(config):
        processed = config.resolve_path(config.paths.processed_dir)
        processed.mkdir(parents=True, exist_ok=True)
        for name in SHARED_PROCESSED:
            (processed / name).write_text(f"run-specific {name}\n", encoding="utf-8")
        reports = config.resolve_path(config.paths.reports_dir)
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "strategy_summary.csv").write_text(SUMMARY, encoding="utf-8")
        (reports / "equity_curves.csv").write_text("date,base\n2026-01-01,1.0\n", encoding="utf-8")
        # export_result_tables publishes by pointing the nearest reports/ root at its output.
        _write_latest_pointer(reports)
        calls["raw_dir"] = config.resolve_path(config.paths.raw_dir)

    return pipeline


def _shared_processed_contents(settings: Settings) -> dict[str, str]:
    contents = {}
    for processed in (settings.data_root / "processed", settings.project_root / "data" / "processed"):
        for path in sorted(processed.iterdir()):
            contents[str(path)] = path.read_text(encoding="utf-8")
    return contents


def test_api_backtest_leaves_shared_processed_data_untouched(isolated, monkeypatch) -> None:
    settings, engine = isolated
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    _create_run(engine)
    before = _shared_processed_contents(settings)
    calls: dict[str, object] = {}
    monkeypatch.setattr(run_one, "run_research_pipeline", _fake_pipeline(calls))

    assert run_one.run("btk_0001", settings) == 0

    final_dir = settings.report_root / "app_runs" / "btk_0001"
    assert _shared_processed_contents(settings) == before
    assert calls["raw_dir"] == (settings.data_root / "raw").resolve()
    assert (final_dir / "summary.csv").exists()
    assert sorted(path.name for path in final_dir.iterdir() if path.name.startswith(".") or path.name == "processed") == []
    assert not (settings.report_root / "app_runs" / "btk_0001.tmp").exists()


def test_completed_run_becomes_the_published_source(isolated, monkeypatch) -> None:
    settings, engine = isolated
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    _create_run(engine)
    monkeypatch.setattr(run_one, "run_research_pipeline", _fake_pipeline({}))

    assert run_one.run("btk_0001", settings) == 0

    assert (settings.report_root / "latest.txt").read_text(encoding="utf-8").strip() == "app_runs/btk_0001"


def test_pipeline_output_never_repoints_the_shared_latest_pointer_mid_run(isolated, monkeypatch) -> None:
    settings, engine = isolated
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    _create_run(engine)
    seen: dict[str, str] = {}
    pipeline = _fake_pipeline({})

    def pipeline_then_crash(config):
        pipeline(config)
        seen["latest"] = (settings.report_root / "latest.txt").read_text(encoding="utf-8").strip()
        raise RuntimeError("plotting failed")

    monkeypatch.setattr(run_one, "run_research_pipeline", pipeline_then_crash)

    assert run_one.run("btk_0001", settings) == 1

    assert seen["latest"] == "app_runs/btk_0000"
    assert (settings.report_root / "latest.txt").read_text(encoding="utf-8").strip() == "app_runs/btk_0000"


@pytest.mark.parametrize(
    ("status", "requested_cancel", "final_status"),
    [("running", True, "cancelled"), ("failed", False, "failed"), ("cancelled", False, "cancelled")],
)
def test_run_that_does_not_complete_is_not_published(isolated, monkeypatch, status, requested_cancel, final_status) -> None:
    settings, engine = isolated
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    _create_run(engine, status=status, requested_cancel=requested_cancel)

    run_one.run("btk_0001", settings)

    with Session(engine) as session:
        run = RunsRepo(session).get("btk_0001")
        reports = session.exec(select(ReportFile).where(ReportFile.run_id == "btk_0001")).all()
    assert run is not None
    assert run.status == final_status
    assert (settings.report_root / "latest.txt").read_text(encoding="utf-8").strip() == "app_runs/btk_0000"
    assert not (settings.report_root / "app_runs" / "btk_0001").exists()
    assert reports == []


def test_run_whose_results_cannot_be_published_ends_failed(isolated, monkeypatch) -> None:
    settings, engine = isolated
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    _create_run(engine)

    def full_disk(tmp_dir, final_dir):
        raise OSError("No space left on device")

    monkeypatch.setattr(run_one, "_publish_report_dir", full_disk)

    assert run_one.run("btk_0001", settings) == 1

    with Session(engine) as session:
        run = RunsRepo(session).get("btk_0001")
    assert run is not None
    assert run.status == "failed"
    assert "No space left on device" in str(run.error)
    assert (settings.report_root / "latest.txt").read_text(encoding="utf-8").strip() == "app_runs/btk_0000"
