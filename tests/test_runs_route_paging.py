"""GET /api/runs bounds its paging parameters."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.repositories import get_session
from atlas20.api.routes import runs as runs_routes
from atlas20.api.settings import get_settings


@pytest.fixture
def client(tmp_path, monkeypatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'paging.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "params",
    [
        {"page": str(10**19)},
        {"page": str(runs_routes.MAX_RUNS_PAGE + 1)},
        {"pageSize": str(runs_routes.MAX_RUNS_PAGE_SIZE + 1)},
        {"pageSize": str(10**9)},
    ],
)
def test_runs_list_rejects_out_of_range_paging(client: TestClient, params: dict[str, str]) -> None:
    response = client.get("/api/runs", params={"dateRange": "all", **params})

    assert response.status_code == 422


def test_runs_list_accepts_the_largest_allowed_page(client: TestClient) -> None:
    response = client.get(
        "/api/runs",
        params={
            "dateRange": "all",
            "page": str(runs_routes.MAX_RUNS_PAGE),
            "pageSize": str(runs_routes.MAX_RUNS_PAGE_SIZE),
        },
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
