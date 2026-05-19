from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo, get_session


@pytest.fixture
def client_session(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'cancel.sqlite').as_posix()}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for run_id, status in (
            ("btk_queued", "queued"),
            ("btk_running", "running"),
            ("btk_completed", "completed"),
            ("btk_failed", "failed"),
            ("btk_cancelled", "cancelled"),
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
    response = client.post("/api/runs/missing/cancel")

    assert response.status_code == 404


def test_cancel_route_returns_409_for_completed_run(client: TestClient):
    response = client.post("/api/runs/btk_completed/cancel")

    assert response.status_code == 409
    assert response.json()["detail"] == "run already completed; cannot cancel"


def test_cancel_route_returns_409_for_failed_run(client: TestClient):
    response = client.post("/api/runs/btk_failed/cancel")

    assert response.status_code == 409
    assert response.json()["detail"] == "run already failed; cannot cancel"


def test_cancel_route_returns_409_for_cancelled_run(client: TestClient):
    response = client.post("/api/runs/btk_cancelled/cancel")

    assert response.status_code == 409
    assert response.json()["detail"] == "run is already cancelled"


def test_cancel_route_accepts_queued_run(client: TestClient):
    response = client.post("/api/runs/btk_queued/cancel")

    assert response.status_code == 202
    assert response.json() == {"run_id": "btk_queued", "requested_cancel": True}


def test_cancel_route_accepts_running_run(client: TestClient):
    response = client.post("/api/runs/btk_running/cancel")

    assert response.status_code == 202
    assert response.json() == {"run_id": "btk_running", "requested_cancel": True}


def test_cancel_route_sets_requested_cancel_in_db(client: TestClient, client_session: Session):
    response = client.post("/api/runs/btk_running/cancel")

    run = RunsRepo(client_session).get("btk_running")
    assert response.status_code == 202
    assert run is not None
    assert run.requested_cancel is True
