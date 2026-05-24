import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from sqlmodel import Session

from atlas20.api import mock_data
from atlas20.api.app import create_app
from atlas20.api.repositories import get_session
from atlas20.api.schemas import (
    BacktestConfig,
    ComparePayload,
    DataAlert,
    DataSource,
    FeaturedDigest,
    OptionsPayload,
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

@pytest.fixture
def client(tmp_path, monkeypatch, db_session: Session) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'atlas20.sqlite').as_posix()}")
    get_settings.cache_clear()
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def test_overview_endpoint_returns_r3_payload(client: TestClient):
    response = client.get("/api/overview")

    assert response.status_code == 200
    raw = response.json()
    payload = OverviewPayload.model_validate(raw)
    assert payload.hero_kpi.ytdReturn == mock_data.fallback_overview["hero_kpi"]["ytdReturn"]
    assert raw["rebalance"]["swaps"][0]["in"] == "DOT"
    assert payload.rebalance.swaps[0].in_ == "DOT"


def test_options_endpoint_returns_options_payload(client: TestClient):
    response = client.get("/api/options")

    assert response.status_code == 200
    payload = OptionsPayload.model_validate(response.json())
    # No real strategy_summary.csv under tmp_path's report_root, so the
    # endpoint falls back via load_options_from_reports → config/*.yaml
    # slugs (project_root defaults to the repo root, which has yaml
    # presets) rather than the legacy mock_data fallback names.
    # `sectors.yaml` is shared config, not a runnable preset.
    expected_presets = sorted(p.stem for p in Path("config").glob("*.yaml") if p.stem != "sectors")
    assert [preset.slug for preset in payload.presets] == expected_presets
    assert [preset.display_name for preset in payload.presets] == [
        "Base Config" if slug == "base" else slug.replace("_", " ").title()
        for slug in expected_presets
    ]
    assert payload.feeBpsRange == [0.0, 10.0, 50.0]


def test_options_payload_includes_display_names(client: TestClient):
    response = client.get("/api/options")

    assert response.status_code == 200
    raw = response.json()
    assert raw["presets"]
    assert {"slug", "display_name"} <= set(raw["presets"][0])
    assert "strategies" in raw


def test_runs_queue_endpoint_returns_summaries(client: TestClient):
    response = client.get("/api/runs/queue")

    assert response.status_code == 200
    payload = [RunRowSummary.model_validate(row) for row in response.json()]
    assert len(payload) == 2
    assert payload[0].run_id == "btk_0148"


def test_runs_endpoint_filters_and_paginates_rows(client: TestClient):
    response = client.get("/api/runs?page=1&pageSize=14&dateRange=all&q=&chips=")

    assert response.status_code == 200
    payload = response.json()
    rows = [RunRow.model_validate(row) for row in payload["items"]]
    assert payload["total"] == 14
    assert payload["pageSize"] == 14
    assert len(rows) == 14
    assert rows[6].run_id == "btk_0142"


def test_runs_route_rejects_unknown_query_param(client: TestClient):
    response = client.get("/api/runs?view=list")

    assert response.status_code == 422


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
    assert payload.run_id == "btk_0149"
    assert payload.status == "queued"
    assert payload.params_summary == "N=20 · Weekly · 2024→2026"


def test_backtests_run_endpoint_returns_422_when_base_yaml_missing(client: TestClient, tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "project_root", tmp_path)

    response = client.post("/api/backtests/run", json=DEFAULT_BACKTEST_CONFIG)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "config/base.yaml" in detail
    assert "not found" in detail


def test_compare_endpoint_returns_compare_payload(client: TestClient):
    response = client.get("/api/compare?ids=atlas,momentum,meanrev&range=YTD")

    assert response.status_code == 200
    payload = ComparePayload.model_validate(response.json())
    assert payload.metrics.cagr["atlas"] == 1.584
    assert payload.overlap.symbols == ["ATLAS v3", "Momentum", "MeanRev"]


def test_compare_payload_includes_display_names(client: TestClient):
    response = client.get("/api/compare?ids=atlas,momentum,meanrev&range=YTD")

    assert response.status_code == 200
    raw = response.json()
    assert raw["strategies"] == [
        {"strategy": "atlas", "display_name": "Atlas"},
        {"strategy": "momentum", "display_name": "Momentum"},
        {"strategy": "meanrev", "display_name": "Meanrev"},
    ]


def test_compare_endpoint_rejects_unknown_query_params(client: TestClient):
    response = client.get("/api/compare?ids=atlas&ranges=YTD")

    assert response.status_code == 422
    assert response.json()["detail"] == "unknown query parameter(s): ranges"


def test_universe_timeline_endpoint_returns_timeline(client: TestClient):
    response = client.get("/api/universe/timeline")

    assert response.status_code == 200
    payload = UniverseTimelinePayload.model_validate(response.json())
    assert len(payload.tokens) == 20
    assert payload.tokens[0] == "ADA"
    assert payload.segments[0].token == "ADA"


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


def test_universe_refresh_endpoint_returns_queued_job(client: TestClient):
    response = client.post("/api/universe/refresh")

    assert response.status_code == 202
    assert response.json()["run_id"].startswith("btk_")
    assert response.json()["status"] == "queued"


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


def test_digest_download_endpoint_returns_404_when_bundle_is_missing(client: TestClient):
    response = client.get("/api/reports/digest/download?format=bundle")

    assert response.status_code == 404


def test_report_download_endpoint_returns_404_when_artifact_is_missing(client: TestClient):
    response = client.get("/api/reports/r2/download?format=pdf")

    assert response.status_code == 404
