"""Backtest submissions must name a known preset; internal run kinds are reserved."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import Session, select

from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.settings import get_settings


BACKTEST = {
    "preset": "base",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Monthly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'presets.sqlite').as_posix()}")
    monkeypatch.delenv("ATLAS20_API_KEYS", raising=False)
    get_settings.cache_clear()
    return TestClient(create_app())


def _run_strategies(tmp_path) -> list[str]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'presets.sqlite').as_posix()}")
    try:
        with Session(engine) as session:
            return [run.strategy for run in session.exec(select(Run)).all()]
    finally:
        engine.dispose()


def test_backtest_with_reserved_preset_is_rejected(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/backtests/run", json={**BACKTEST, "preset": "universe_refresh"})

    assert response.status_code == 422
    assert "reserved for internal runs" in response.text
    assert _run_strategies(tmp_path) == []


def test_backtest_with_known_preset_is_queued(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/backtests/run", json=BACKTEST)

    assert response.status_code == 200
    assert _run_strategies(tmp_path) == ["base"]


def test_strategy_lab_batch_with_reserved_preset_queues_nothing(tmp_path, monkeypatch):
    batch = {"presets": ["base", "universe_refresh"], "topNs": [20], "rebalances": ["Monthly"], "baseConfig": BACKTEST}

    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/strategy-lab/batches", json=batch)

    assert response.status_code == 422
    assert "reserved for internal runs" in response.text
    assert _run_strategies(tmp_path) == []


def test_strategy_lab_batch_with_unknown_preset_queues_nothing(tmp_path, monkeypatch):
    batch = {"presets": ["base", "no-such-preset"], "topNs": [20], "rebalances": ["Monthly"], "baseConfig": BACKTEST}

    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/strategy-lab/batches", json=batch)

    assert response.status_code == 422
    assert "unknown preset" in response.text
    assert _run_strategies(tmp_path) == []
