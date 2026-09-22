from __future__ import annotations

import pytest

from atlas20.config import load_config
from scripts.run_sector_lead_overlays import (
    DEFAULT_MAX_LEVERAGE,
    _config_with_liquidity,
    _friction_for_lane,
)


def test_liquidity_profile_changes_universe_gate_before_ranking() -> None:
    base = load_config("config/base.yaml")

    loose = _config_with_liquidity(base, "loose")
    medium = _config_with_liquidity(base, "medium")
    strict = _config_with_liquidity(base, "strict")

    assert loose.universe.min_history_days == 30
    assert loose.universe.min_daily_dollar_volume == 1_000_000.0
    assert loose.universe.min_turnover_ratio == 0.0
    assert medium.universe.min_history_days == 60
    assert medium.universe.min_daily_dollar_volume == 10_000_000.0
    assert medium.universe.min_turnover_ratio == 0.005
    assert strict.universe.min_history_days == 90
    assert strict.universe.min_daily_dollar_volume == 25_000_000.0
    assert strict.universe.min_turnover_ratio == 0.01


def test_liquidity_profile_does_not_mutate_original_config() -> None:
    base = load_config("config/base.yaml")
    original = base.universe.model_copy(deep=True)

    _config_with_liquidity(base, "loose")

    assert base.universe == original


def test_unknown_liquidity_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported liquidity profile"):
        _config_with_liquidity(load_config("config/base.yaml"), "unknown")


def test_concentrated_sector_lane_disables_diversification_caps() -> None:
    config = load_config("config/base.yaml")

    friction = _friction_for_lane(config, max_weight_per_coin=1.0)

    assert friction.max_weight_per_coin == 1.0
    assert friction.max_weight_per_sector == 1.0


def test_sector_overlay_default_is_unlevered() -> None:
    assert DEFAULT_MAX_LEVERAGE == 1.0
