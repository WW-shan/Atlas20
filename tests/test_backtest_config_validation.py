from copy import deepcopy

import pytest
from pydantic import ValidationError

from atlas20.api.schemas import BacktestConfig


BASE_CONFIG = {
    "preset": "ATLAS Adaptive v3",
    "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
    "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
    "allocation": {"positionPct": 5.0, "slots": 10},
    "costs": {"feeBps": 10, "slippageBps": 5},
}


def valid_config() -> dict:
    return deepcopy(BASE_CONFIG)


def test_backtest_config_rejects_top_n_over_50():
    data = valid_config()
    data["universe"]["topN"] = 100

    with pytest.raises(ValidationError) as exc:
        BacktestConfig.model_validate(data)

    assert "topN" in str(exc.value)


def test_backtest_config_rejects_slots_over_top_n():
    data = valid_config()
    data["universe"]["topN"] = 5
    data["allocation"]["slots"] = 10

    with pytest.raises(ValidationError) as exc:
        BacktestConfig.model_validate(data)

    message = str(exc.value)
    assert "slots" in message
    assert "topN" in message


def test_backtest_config_rejects_window_span_over_10_years():
    data = valid_config()
    data["window"]["start"] = "2015-05-18"
    data["window"]["end"] = "2026-05-18"

    with pytest.raises(ValidationError) as exc:
        BacktestConfig.model_validate(data)

    assert "window span" in str(exc.value)


def test_backtest_config_rejects_future_end_date():
    data = valid_config()
    data["window"]["end"] = "2030-01-01"

    with pytest.raises(ValidationError) as exc:
        BacktestConfig.model_validate(data)

    assert "future" in str(exc.value)


def test_backtest_config_rejects_combined_costs_over_1000_bps():
    data = valid_config()
    data["costs"]["feeBps"] = 600
    data["costs"]["slippageBps"] = 500

    with pytest.raises(ValidationError) as exc:
        BacktestConfig.model_validate(data)

    message = str(exc.value)
    assert "feeBps" in message
    assert "slippageBps" in message


def test_validator_errors_include_field_names():
    costs = valid_config()
    costs["costs"]["feeBps"] = 750
    costs["costs"]["slippageBps"] = 300

    with pytest.raises(ValidationError) as exc:
        BacktestConfig.model_validate(costs)

    assert "feeBps" in str(exc.value)

    slots = valid_config()
    slots["universe"]["topN"] = 5
    slots["allocation"]["slots"] = 10

    with pytest.raises(ValidationError) as exc:
        BacktestConfig.model_validate(slots)

    message = str(exc.value)
    assert "slots" in message or "topN" in message


def test_backtest_config_accepts_valid_config():
    config = BacktestConfig.model_validate(valid_config())

    assert config.universe.topN == 20
    assert config.allocation.slots == 10
