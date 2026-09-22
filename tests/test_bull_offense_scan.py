from __future__ import annotations

import pytest

from atlas20.config import load_config
from scripts.run_bull_offense_scan import _parse_leverage_levels, _uncapped_friction


def test_bull_offense_research_friction_is_truly_uncapped():
    """Concentrated strategies and their BTC yardstick must use full notional."""
    config = load_config("config/base.yaml")

    friction = _uncapped_friction(config)

    assert friction.max_weight_per_coin == 1.0
    assert friction.max_weight_per_sector == 1.0
    assert friction is not config.frictions
    assert config.frictions.max_weight_per_coin < 1.0
    assert config.frictions.max_weight_per_sector < 1.0


def test_bull_offense_scan_defaults_to_unlevered_and_rejects_leverage():
    assert _parse_leverage_levels("1.0") == (1.0,)
    with pytest.raises(ValueError, match="unlevered"):
        _parse_leverage_levels("1.0,1.5")
