import json
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo, get_session
from atlas20.api.settings import Settings, get_settings
from atlas20.api.worker import run_one

# What POST /api/universe/refresh and the daily scheduler store for the job.
REFRESH_PARAMS = json.dumps({"kind": "universe_refresh"})


def _client(tmp_path, monkeypatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'refresh.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def test_universe_refresh_endpoint_enqueues_job_and_status_endpoint_returns_latest(tmp_path, monkeypatch, db_session: Session):
    client = _client(tmp_path, monkeypatch, db_session)

    response = client.post("/api/universe/refresh")
    status_response = client.get("/api/universe/refresh-status")

    assert response.status_code == 202
    payload = response.json()
    assert payload["run_id"].startswith("btk_")
    assert payload["status"] == "queued"
    assert status_response.status_code == 200
    assert status_response.json() == payload


def test_run_one_mock_processes_universe_refresh_job(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = Settings(
        db_url=f"sqlite:///{(tmp_path / 'refresh-worker.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        data_root=tmp_path / "data",
        project_root=tmp_path,
    )
    engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Run(
                run_id="btk_9001",
                strategy="universe_refresh",
                strategy_family="Other",
                universe="Data Sources",
                window_start=date(2026, 5, 19),
                window_end=date(2026, 5, 19),
                status="running",
                params=REFRESH_PARAMS,
            )
        )
        session.commit()

    exit_code = run_one.run("btk_9001", settings)

    with Session(engine) as session:
        row = RunsRepo(session).get("btk_9001")
        assert exit_code == 0
    assert row is not None
    assert row.status == "completed"
    assert row.duration_s is not None
    assert (settings.data_root / "raw" / "coingecko" / "universe_refresh_mock.json").exists()
    heartbeat = json.loads((settings.data_root / "data_freshness.json").read_text(encoding="utf-8"))
    assert heartbeat["status"] == "completed"
    assert heartbeat["run_id"] == "btk_9001"
    assert "coinmarketcap" in heartbeat["source_dates"]


def test_run_one_records_universe_refresh_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings = Settings(
        db_url=f"sqlite:///{(tmp_path / 'refresh-failure.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        data_root=tmp_path / "data",
        project_root=tmp_path,
    )
    engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Run(
                run_id="btk_9002",
                strategy="universe_refresh",
                strategy_family="Other",
                universe="Data Sources",
                window_start=date(2026, 5, 19),
                window_end=date(2026, 5, 19),
                status="running",
                params=REFRESH_PARAMS,
            )
        )
        session.commit()

    def fail_refresh(_: Settings) -> None:
        raise RuntimeError("provider timeout")

    monkeypatch.setattr(run_one, "_execute_universe_refresh", fail_refresh)

    exit_code = run_one.run("btk_9002", settings)

    heartbeat = json.loads((settings.data_root / "data_freshness.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert heartbeat["status"] == "failed"
    assert heartbeat["run_id"] == "btk_9002"
    assert heartbeat["error"] == "provider timeout"


class _FakeConfig:
    def __init__(self, project_root) -> None:
        self.project_root = project_root
        self.paths = SimpleNamespace(raw_dir="old", processed_dir="old")

    def resolve_path(self, relative_path):
        return self.project_root / relative_path


def _fake_refresh_pipeline(monkeypatch, tmp_path, calls: list[tuple[str, object]], *, build_error: Exception | None = None):
    config = _FakeConfig(tmp_path)

    def fake_load_config(path):
        calls.append(("load_config", path))
        return config

    def fake_download(download_config):
        calls.append(("download", download_config.paths.raw_dir))

    def fake_load_sector_config(path):
        calls.append(("sectors", path))
        return "sector-config"

    def fake_build(build_config, sector_config, **kwargs):
        calls.append(("build", (build_config.paths.raw_dir, build_config.paths.processed_dir, sector_config, kwargs)))
        if build_error is not None:
            raise build_error

    monkeypatch.setattr(run_one, "load_config", fake_load_config)
    monkeypatch.setattr(run_one, "download_and_cache_raw_data", fake_download)
    monkeypatch.setattr(run_one, "load_sector_config", fake_load_sector_config)
    monkeypatch.setattr(run_one, "build_processed_datasets", fake_build)


def test_universe_refresh_worker_non_mock_wires_download_to_settings_data_root(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    settings = Settings(
        db_url=f"sqlite:///{(tmp_path / 'refresh-worker.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        data_root=tmp_path / "data",
        project_root=tmp_path,
    )
    calls: list[tuple[str, object]] = []
    _fake_refresh_pipeline(monkeypatch, tmp_path, calls)

    run_one._execute_universe_refresh(settings)

    assert calls[0] == ("load_config", tmp_path / "config" / "base.yaml")
    assert ("download", str(settings.data_root / "raw")) in calls


def test_universe_refresh_rebuilds_processed_datasets_after_downloading(tmp_path, monkeypatch):
    # Mirrors the launchd job: scripts/download_data.py then scripts/build_datasets.py.
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    settings = Settings(
        db_url=f"sqlite:///{(tmp_path / 'refresh-build.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        data_root=tmp_path / "data",
        project_root=tmp_path,
    )
    calls: list[tuple[str, object]] = []
    _fake_refresh_pipeline(monkeypatch, tmp_path, calls)

    run_one._execute_universe_refresh(settings)

    steps = [name for name, _ in calls]
    assert steps.index("download") < steps.index("build")
    assert ("sectors", tmp_path / "config" / "sectors.yaml") in calls
    raw_dir, processed_dir, sector_config, kwargs = dict(calls)["build"]
    assert raw_dir == str(settings.data_root / "raw")
    assert processed_dir == str(settings.data_root / "processed")
    assert sector_config == "sector-config"
    # persist (and with it the panel regression guard) must stay on.
    assert kwargs.get("persist", True) is True


def _refresh_run_settings(tmp_path, name: str) -> tuple[Settings, object]:
    settings = Settings(
        db_url=f"sqlite:///{(tmp_path / f'{name}.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        data_root=tmp_path / "data",
        project_root=tmp_path,
    )
    engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return settings, engine


def _add_run(engine, run_id: str, *, strategy: str, params: str) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                run_id=run_id,
                strategy=strategy,
                strategy_family="Other",
                universe="Top-20",
                window_start=date(2026, 5, 19),
                window_end=date(2026, 5, 19),
                status="running",
                params=params,
            )
        )
        session.commit()


def test_universe_refresh_panel_regression_fails_the_refresh(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    settings, engine = _refresh_run_settings(tmp_path, "refresh-guard")
    _add_run(engine, "btk_9003", strategy="universe_refresh", params=REFRESH_PARAMS)
    calls: list[tuple[str, object]] = []
    _fake_refresh_pipeline(
        monkeypatch,
        tmp_path,
        calls,
        build_error=RuntimeError("Processed panel regression: refusing to overwrite an existing panel"),
    )

    exit_code = run_one.run("btk_9003", settings)

    heartbeat = json.loads((settings.data_root / "data_freshness.json").read_text(encoding="utf-8"))
    with Session(engine) as session:
        row = RunsRepo(session).get("btk_9003")
    assert exit_code == 1
    assert row is not None and row.status == "failed"
    assert heartbeat["status"] == "failed"
    assert "Processed panel regression" in heartbeat["error"]


def test_user_backtest_named_universe_refresh_never_runs_a_data_refresh(tmp_path, monkeypatch):
    # Queued before presets were validated: a user backtest whose preset was the
    # internal job name. Only the job's own params may trigger a refresh.
    monkeypatch.setenv("ATLAS20_WORKER_MOCK", "1")
    settings, engine = _refresh_run_settings(tmp_path, "refresh-spoof")
    user_params = json.dumps(
        {
            "preset": "universe_refresh",
            "universe": {"topN": 5, "excludeStable": True, "excludeWrapped": True},
            "window": {"start": "2026-01-01", "end": "2026-02-01", "rebalance": "Weekly"},
            "allocation": {"positionPct": 25.0, "slots": 3},
            "costs": {"feeBps": 1.0, "slippageBps": 1.0},
        }
    )
    _add_run(engine, "btk_9004", strategy="universe_refresh", params=user_params)
    refreshes: list[Settings] = []
    monkeypatch.setattr(run_one, "_execute_universe_refresh", refreshes.append)

    run_one.run("btk_9004", settings)

    assert refreshes == []
    assert not (settings.data_root / "data_freshness.json").exists()
