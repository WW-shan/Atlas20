from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from atlas20.api.app import create_app
from atlas20.api.repositories import RunsRepo, get_session
from atlas20.api.settings import get_settings


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch, db_session: Session) -> Iterator[TestClient]:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'atlas20.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client


def test_favorite_post_updates_repo_and_favorited_filter(client: TestClient, db_session: Session) -> None:
    run_id = "btk_0141"

    response = client.post(f"/api/runs/{run_id}/favorite")

    assert response.status_code == 200
    assert response.json() == {"run_id": run_id, "favorited": True}
    row = RunsRepo(db_session).get(run_id)
    assert row is not None
    assert row.favorited is True

    filter_response = client.get("/api/runs?dateRange=all&chips=favorited&pageSize=20")
    assert filter_response.status_code == 200
    ids = [item["run_id"] for item in filter_response.json()["items"]]
    assert run_id in ids


def test_favorite_toggle_keeps_queue_endpoint_db_backed(client: TestClient, db_session: Session) -> None:
    run_id = "btk_0147"
    before = client.get("/api/runs/queue")
    assert before.status_code == 200
    before_ids = [item["run_id"] for item in before.json()]
    assert run_id in before_ids

    response = client.post(f"/api/runs/{run_id}/favorite")

    assert response.status_code == 200
    assert response.json() == {"run_id": run_id, "favorited": True}
    row = RunsRepo(db_session).get(run_id)
    assert row is not None
    assert row.favorited is True

    after = client.get("/api/runs/queue")
    assert after.status_code == 200
    after_payload = after.json()
    after_ids = [item["run_id"] for item in after_payload]
    assert after_ids == before_ids
    queue_row = next(item for item in after_payload if item["run_id"] == run_id)
    assert queue_row["favorited"] is True
