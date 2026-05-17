from fastapi.testclient import TestClient

from atlas20.api.app import create_app


def test_overview_endpoint_returns_champion_top_strategies_and_series():
    client = TestClient(create_app())

    response = client.get("/api/overview")

    assert response.status_code == 200
    payload = response.json()
    assert "champion" in payload
    assert "top_strategies" in payload
    assert "equity_curve" in payload


def test_options_endpoint_returns_control_ranges():
    client = TestClient(create_app())

    response = client.get("/api/options")

    assert response.status_code == 200
    payload = response.json()
    assert "strategy_families" in payload
    assert "risk_modes" in payload


def test_placeholder_runs_and_backtests_routes_are_registered():
    client = TestClient(create_app())

    assert client.get("/api/runs").status_code == 200
    assert client.get("/api/backtests").status_code == 200


def test_backtest_run_endpoint_uses_constrained_request(monkeypatch):
    from atlas20.api.schemas import RunStatus

    captured = {}

    def fake_execute(request):
        captured["family"] = request.strategy.family
        return RunStatus(
            run_id="demo",
            status="completed",
            name="demo",
            summary={"strategy": "demo"},
        )

    monkeypatch.setattr("atlas20.api.routes.backtests.execute_backtest_request", fake_execute)
    client = TestClient(create_app())

    response = client.post(
        "/api/backtests/run",
        json={
            "window": {"start_date": "2022-11-21", "end_date": "2026-04-21"},
            "strategy": {"family": "momentum_lead", "top_n": 1, "frequency": "14D"},
            "universe": {
                "min_history_days": 30,
                "min_daily_dollar_volume": 1000000,
                "exclude_btc": False,
            },
            "risk": {
                "mode": "always_on",
                "stop_lookback_days": 11,
                "confirm_days": 2,
                "risk_off_asset": "bitcoin",
            },
            "weights": {
                "momentum_rank": 0.607681,
                "ret_21_rank": 0.268948,
                "ret_42_rank": 0.017319,
                "near_high_rank": 0.106052,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["run_id"] == "demo"
    assert captured["family"] == "momentum_lead"
