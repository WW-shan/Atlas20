from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo, get_session


def _error_message(response) -> str:
    return response.json()["error"]["message"]


@pytest.fixture
def client_session(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'cancel.sqlite').as_posix()}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for run_id, status in (
            ("btk_0001", "queued"),
            ("btk_0002", "running"),
            ("btk_0003", "completed"),
            ("btk_0004", "failed"),
            ("btk_0005", "cancelled"),
        ):
            session.add(
                Run(
                    run_id=run_id,
                    strategy="ATLAS Adaptive v3",
                    strategy_family="ATLAS",
                    universe="Top-20",
                    window_start=date(2024, 1, 1),
                    window_end=date(2026, 5, 18),
                    status=status,
                )
            )
        session.commit()
        yield session


@pytest.fixture
def client(client_session):
    app = create_app()

    def override_get_session():
        yield client_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def test_cancel_route_returns_404_for_missing_run(client: TestClient):
    response = client.post("/api/runs/btk_9999/cancel")

    assert response.status_code == 404


def test_cancel_route_returns_409_for_completed_run(client: TestClient):
    response = client.post("/api/runs/btk_0003/cancel")

    assert response.status_code == 409
    assert _error_message(response) == "run already completed; cannot cancel"


def test_cancel_route_returns_409_for_failed_run(client: TestClient):
    response = client.post("/api/runs/btk_0004/cancel")

    assert response.status_code == 409
    assert _error_message(response) == "run already failed; cannot cancel"


def test_cancel_route_returns_409_for_cancelled_run(client: TestClient):
    response = client.post("/api/runs/btk_0005/cancel")

    assert response.status_code == 409
    assert _error_message(response) == "run is already cancelled"


def test_cancel_route_accepts_queued_run(client: TestClient):
    response = client.post("/api/runs/btk_0001/cancel")

    assert response.status_code == 202
    assert response.json() == {"run_id": "btk_0001", "requested_cancel": True}


def test_cancel_route_accepts_running_run(client: TestClient):
    response = client.post("/api/runs/btk_0002/cancel")

    assert response.status_code == 202
    assert response.json() == {"run_id": "btk_0002", "requested_cancel": True}


def test_cancel_route_sets_requested_cancel_in_db(client: TestClient, client_session: Session):
    response = client.post("/api/runs/btk_0002/cancel")

    run = RunsRepo(client_session).get("btk_0002")
    assert response.status_code == 202
    assert run is not None
    assert run.requested_cancel is True
