from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo, get_session
from atlas20.api.settings import Settings, get_settings
from atlas20.api.worker import run_one


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
                params="{}",
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


def test_universe_refresh_worker_non_mock_wires_download_to_settings_data_root(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS20_WORKER_MOCK", raising=False)
    settings = Settings(
        db_url=f"sqlite:///{(tmp_path / 'refresh-worker.sqlite').as_posix()}",
        report_root=tmp_path / "reports",
        data_root=tmp_path / "data",
        project_root=tmp_path,
    )
    calls: dict[str, object] = {}
    config = SimpleNamespace(paths=SimpleNamespace(raw_dir="old"))

    def fake_load_config(path):
        calls["config_path"] = path
        return config

    def fake_download_and_cache_raw_data(download_config):
        calls["raw_dir"] = download_config.paths.raw_dir

    monkeypatch.setattr(run_one, "load_config", fake_load_config)
    monkeypatch.setattr(run_one, "download_and_cache_raw_data", fake_download_and_cache_raw_data)

    run_one._execute_universe_refresh(settings)

    assert calls["config_path"] == tmp_path / "config" / "base.yaml"
    assert calls["raw_dir"] == str(settings.data_root / "raw")
