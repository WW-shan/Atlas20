from datetime import date
import hashlib
import json
import os
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine

from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import Settings
from atlas20.api.worker import run_one


CONFIG_DATA = {
    "preset": "ATLAS Adaptive v3",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}


def _settings(tmp_path) -> Settings:
    return Settings(
        db_url=f"sqlite:///{(tmp_path / 'run_one.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        project_root=tmp_path,
        run_timeout_seconds=5,
        worker_poll_interval_seconds=0.01,
    )


def _engine(settings: Settings):
    engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _create_run(engine, run_id: str = "btk_0001", *, params: str | None = None) -> None:
    config = BacktestConfig.model_validate(CONFIG_DATA)
    with Session(engine) as session:
        session.add(
            Run(
                run_id=run_id,
                strategy=config.preset,
                strategy_family="ATLAS",
                universe="Top-20",
                window_start=date(2024, 1, 1),
                window_end=date(2026, 5, 18),
                status="running",
                params=params if params is not None else config.model_dump_json(),
            )
        )
        session.commit()


def _read_run(engine, run_id: str = "btk_0001") -> Run:
    with Session(engine) as session:
        run = RunsRepo(session).get(run_id)
        assert run is not None
        return run


def test_run_one_mock_happy_path_completes_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = _settings(tmp_path)
    engine = _engine(settings)
    _create_run(engine)

    exit_code = run_one.run("btk_0001", settings)

    completed = _read_run(engine)
    assert exit_code == 0
    assert completed.status == "completed"
    assert completed.return_pct == 0.25
    assert completed.sharpe == 1.5
    assert completed.max_dd == -0.1


def test_run_one_writes_atomic_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = _settings(tmp_path)
    engine = _engine(settings)
    _create_run(engine)

    assert run_one.run("btk_0001", settings) == 0

    final_dir = tmp_path / "reports" / "app_runs" / "btk_0001"
    assert final_dir.exists()
    assert not final_dir.with_name("btk_0001.tmp").exists()
    assert (final_dir / "summary.csv").exists()
    assert (final_dir / "equity_curve.csv").exists()
    assert (final_dir / "daily_returns.csv").exists()
    assert (final_dir / "weights" / "ATLAS_MOCK.csv").exists()
    assert (final_dir / "selection_history.csv").exists()


def test_run_one_mock_preserves_existing_tmp_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = _settings(tmp_path)
    engine = _engine(settings)
    _create_run(engine)
    tmp_dir = tmp_path / "reports" / "app_runs" / "btk_0001.tmp"
    tmp_dir.mkdir(parents=True)
    (tmp_dir / "debug.log").write_text("keep this artifact\n", encoding="utf-8")

    assert run_one.run("btk_0001", settings) == 0

    final_dir = tmp_path / "reports" / "app_runs" / "btk_0001"
    assert (final_dir / "debug.log").read_text(encoding="utf-8") == "keep this artifact\n"


def test_run_one_missing_run_id_returns_one_without_db_change(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = _settings(tmp_path)
    engine = _engine(settings)

    exit_code = run_one.run("missing", settings)

    with Session(engine) as session:
        assert exit_code == 1
        assert RunsRepo(session).get("missing") is None


def test_run_one_records_sha256_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = _settings(tmp_path)
    engine = _engine(settings)
    _create_run(engine)

    assert run_one.run("btk_0001", settings) == 0

    final_dir = tmp_path / "reports" / "app_runs" / "btk_0001"
    manifest = json.loads((final_dir / "manifest.json").read_text(encoding="utf-8"))
    summary_hash = hashlib.sha256((final_dir / "summary.csv").read_bytes()).hexdigest()
    assert manifest["artifacts"]["summary.csv"] == summary_hash
    assert manifest["code_commit"]
    assert manifest["config_hash"]


def test_run_one_writes_params_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = _settings(tmp_path)
    engine = _engine(settings)
    _create_run(engine)

    assert run_one.run("btk_0001", settings) == 0

    params = json.loads((tmp_path / "reports" / "app_runs" / "btk_0001" / "params.json").read_text(encoding="utf-8"))
    assert params == CONFIG_DATA


def test_run_one_failure_marks_status_failed_and_keeps_tmp(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    settings = _settings(tmp_path)
    settings.project_root = Path(os.getcwd())
    engine = _engine(settings)
    _create_run(engine)

    def fail_pipeline(config):
        config.resolve_path(config.paths.reports_dir).mkdir(parents=True, exist_ok=True)
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(run_one, "run_research_pipeline", fail_pipeline)

    assert run_one.run("btk_0001", settings) == 1

    failed = _read_run(engine)
    assert failed.status == "failed"
    assert failed.error == "pipeline exploded"
    assert (tmp_path / "reports" / "app_runs" / "btk_0001.tmp").exists()


def test_run_one_subprocess_entry_happy_path(tmp_path, worker_subprocess):
    settings = _settings(tmp_path)
    engine = _engine(settings)
    _create_run(engine)

    completed = worker_subprocess("btk_0001", settings)

    assert completed.returncode == 0
    assert _read_run(engine).status == "completed"


def test_run_one_manifest_includes_all_artifact_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = _settings(tmp_path)
    engine = _engine(settings)
    _create_run(engine)

    assert run_one.run("btk_0001", settings) == 0

    manifest = json.loads((tmp_path / "reports" / "app_runs" / "btk_0001" / "manifest.json").read_text(encoding="utf-8"))
    assert {
        "summary.csv",
        "equity_curve.csv",
        "daily_returns.csv",
        "weights/ATLAS_MOCK.csv",
        "selection_history.csv",
        "params.json",
    }.issubset(manifest["artifacts"])
