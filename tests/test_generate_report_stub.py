from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from atlas20.api.app import create_app
from atlas20.api.settings import get_settings


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client


def test_generate_report_stub_returns_202_with_job_id(client: TestClient) -> None:
    response = client.post(
        "/api/reports/generate",
        json={
            "type": "compare",
            "formats": ["markdown", "pdf"],
            "strategy": "ATLAS Adaptive v3",
            "notes": "weekly review",
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "job_id": "stub-job-001",
        "status": "queued",
        "note": "report generation stubbed until Batch 12",
    }


def test_generate_report_stub_rejects_empty_formats(client: TestClient) -> None:
    response = client.post(
        "/api/reports/generate",
        json={"type": "weekly", "formats": []},
    )

    assert response.status_code == 422


def test_generate_report_stub_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post(
        "/api/reports/generate",
        json={
            "type": "weekly",
            "formats": ["markdown"],
            "priority": "high",
        },
    )

    assert response.status_code == 422
