from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from atlas20.api.app import create_app
from atlas20.api import mock_data
from atlas20.api.cli.seed import main as seed_main
from atlas20.api.db.models import Run
from atlas20.api.repositories import get_engine
from atlas20.api.settings import get_settings


def test_seed_cli_populates_db_and_skips_when_rows_exist(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "atlas20.sqlite"
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()

    seed_main()
    first_output = capsys.readouterr().out

    settings = get_settings()
    with Session(get_engine(settings)) as session:
        count = session.exec(select(func.count()).select_from(Run)).one()

    seed_main()
    second_output = capsys.readouterr().out

    assert f"Seeded {len(mock_data.fallback_runs_list)} runs" in first_output
    assert count == len(mock_data.fallback_runs_list)
    assert "DB already seeded, skipping" in second_output


def test_seed_cli_records_migration_state_so_app_can_start(tmp_path, monkeypatch):
    db_path = tmp_path / "atlas20.sqlite"
    report_root = tmp_path / "reports"
    data_root = tmp_path / "data"
    report_root.mkdir()
    data_root.mkdir()
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(data_root))
    get_settings.cache_clear()

    seed_main()

    with TestClient(create_app()) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
