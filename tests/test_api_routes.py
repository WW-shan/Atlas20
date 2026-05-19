from copy import deepcopy
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from atlas20.api import mock_data
from atlas20.api.app import create_app
from atlas20.api.schemas import (
    BacktestConfig,
    ComparePayload,
    DataAlert,
    DataSource,
    FeaturedDigest,
    OverviewPayload,
    ReportEntry,
    RunDetailPayload,
    RunRow,
    RunRowSummary,
    UniverseTimelinePayload,
)
from atlas20.api.settings import get_settings


DEFAULT_BACKTEST_CONFIG = {
    "preset": "ATLAS Adaptive v3",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}

MUTABLE_FIXTURES = {
    "fallback_runs_queue": deepcopy(mock_data.fallback_runs_queue),
    "fallback_runs_list": deepcopy(mock_data.fallback_runs_list),
    "fallback_run_detail": deepcopy(mock_data.fallback_run_detail),
}


@pytest.fixture(autouse=True)
def restore_mock_data():
    yield
    mock_data.fallback_runs_queue[:] = deepcopy(MUTABLE_FIXTURES["fallback_runs_queue"])
    mock_data.fallback_runs_list[:] = deepcopy(MUTABLE_FIXTURES["fallback_runs_list"])
    mock_data.fallback_run_detail.clear()
    mock_data.fallback_run_detail.update(deepcopy(MUTABLE_FIXTURES["fallback_run_detail"]))


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    return TestClient(create_app())


def test_overview_endpoint_returns_r3_payload(client: TestClient):
    response = client.get("/api/overview")

    assert response.status_code == 200
    raw = response.json()
    payload = OverviewPayload.model_validate(raw)
    assert payload.hero_kpi.ytdReturn == mock_data.fallback_overview["hero_kpi"]["ytdReturn"]
    assert raw["rebalance"]["swaps"][0]["in"] == "DOT"
    assert payload.rebalance.swaps[0].in_ == "DOT"


def test_options_endpoint_returns_empty_payload(client: TestClient):
    response = client.get("/api/options")

    assert response.status_code == 200
    assert response.json() == {}


def test_runs_queue_endpoint_returns_summaries(client: TestClient):
    response = client.get("/api/runs/queue")

    assert response.status_code == 200
    payload = [RunRowSummary.model_validate(row) for row in response.json()]
    assert len(payload) == 6
    assert payload[0].run_id == "btk_0148"


def test_runs_endpoint_filters_and_paginates_rows(client: TestClient):
    response = client.get("/api/runs?page=1&pageSize=14&dateRange=all&q=&chips=&view=list")

    assert response.status_code == 200
    payload = response.json()
    rows = [RunRow.model_validate(row) for row in payload["items"]]
    assert payload["total"] == 14
    assert payload["pageSize"] == 14
    assert len(rows) == 14
    assert rows[6].run_id == "btk_0142"


def test_run_endpoint_returns_single_row(client: TestClient):
    response = client.get("/api/runs/btk_0142")

    assert response.status_code == 200
    payload = RunRow.model_validate(response.json())
    assert payload.strategy == "ATLAS Adaptive v3"
    assert payload.favorited is True


def test_run_detail_endpoint_returns_detail_payload(client: TestClient):
    response = client.get("/api/runs/btk_0142/detail")

    assert response.status_code == 200
    payload = RunDetailPayload.model_validate(response.json())
    assert payload.kpi.sharpe == 3.42
    assert payload.equity_overlay.series[-1].atlas == 1247


def test_run_favorite_endpoint_toggles_favorite(client: TestClient):
    response = client.post("/api/runs/btk_0142/favorite")

    assert response.status_code == 200
    assert response.json() == {"run_id": "btk_0142", "favorited": False}


def test_backtests_run_endpoint_registers_queued_run(client: TestClient):
    BacktestConfig.model_validate(DEFAULT_BACKTEST_CONFIG)

    response = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG)

    assert response.status_code == 200
    payload = RunRowSummary.model_validate(response.json())
    assert payload.run_id == "btk_0150"
    assert payload.status == "queued"
    assert payload.params_summary == "N=20 · Weekly · 2024→2026"


def test_compare_endpoint_returns_compare_payload(client: TestClient):
    response = client.get("/api/compare?ids=atlas,momentum,meanrev&range=YTD")

    assert response.status_code == 200
    payload = ComparePayload.model_validate(response.json())
    assert payload.metrics.cagr["atlas"] == 1.584
    assert payload.overlap.symbols == ["ATLAS v3", "Momentum", "MeanRev"]


def test_universe_timeline_endpoint_returns_timeline(client: TestClient):
    response = client.get("/api/universe/timeline")

    assert response.status_code == 200
    payload = UniverseTimelinePayload.model_validate(response.json())
    assert len(payload.tokens) == 32
    assert payload.segments[0].token == "ETH"


def test_universe_sources_endpoint_returns_data_sources(client: TestClient):
    response = client.get("/api/universe/sources")

    assert response.status_code == 200
    payload = [DataSource.model_validate(row) for row in response.json()]
    assert len(payload) == 9
    assert payload[-1].status == "error"


def test_universe_alerts_endpoint_returns_alerts(client: TestClient):
    response = client.get("/api/universe/alerts")

    assert response.status_code == 200
    payload = [DataAlert.model_validate(row) for row in response.json()]
    assert len(payload) == 6
    assert payload[0].id == "a1"


def test_universe_refresh_endpoint_returns_timestamp(client: TestClient):
    response = client.post("/api/universe/refresh")

    assert response.status_code == 200
    refreshed_at = response.json()["refreshed_at"]
    assert refreshed_at.endswith("Z")
    datetime.fromisoformat(refreshed_at.replace("Z", "+00:00"))


def test_featured_digest_endpoint_returns_digest(client: TestClient):
    response = client.get("/api/reports/digest/featured")

    assert response.status_code == 200
    payload = FeaturedDigest.model_validate(response.json())
    assert payload.defaultFormat == "markdown"
    assert payload.id == mock_data.fallback_featured_digest["id"]


def test_reports_endpoint_returns_sorted_reports(client: TestClient):
    response = client.get("/api/reports?sort=recent")

    assert response.status_code == 200
    payload = [ReportEntry.model_validate(row) for row in response.json()]
    assert len(payload) == 6
    assert payload[0].id == "r2"


def test_digest_download_endpoint_returns_placeholder_url(client: TestClient):
    response = client.get("/api/reports/digest/download?format=bundle")

    assert response.status_code == 200
    assert response.json() == {"url": "/static/reports/digest.bundle"}


def test_report_download_endpoint_returns_placeholder_url(client: TestClient):
    response = client.get("/api/reports/r2/download?format=pdf")

    assert response.status_code == 200
    assert response.json() == {"url": "/static/reports/r2.pdf"}
