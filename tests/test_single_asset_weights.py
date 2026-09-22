from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.single_asset import (
    simulate_single_asset_targets,
    simulate_single_asset_weights,
)


def test_fractional_weights_reproduce_binary_simulator() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"asset_a": [0.0, 0.10, -0.05, 0.02]}, index=index)
    assets = pd.Series(["__cash__", "asset_a", "asset_a", "__cash__"], index=index)
    weights = pd.Series([0.0, 1.0, 1.0, 0.0], index=index)

    binary = simulate_single_asset_targets(
        returns,
        assets,
        total_cost_bps=4.0,
    )
    fractional = simulate_single_asset_weights(
        returns,
        assets,
        weights,
        total_cost_bps=4.0,
    )

    pd.testing.assert_series_equal(
        fractional.daily_returns,
        binary.daily_returns,
        check_names=False,
    )
    pd.testing.assert_series_equal(fractional.turnover, binary.turnover, check_names=False)


def test_fractional_weight_scales_return_and_turnover() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"asset_a": [0.0, 0.0, 0.10]}, index=index)
    assets = pd.Series(["__cash__", "asset_a", "asset_a"], index=index)
    weights = pd.Series([0.0, 0.5, 0.5], index=index)

    result = simulate_single_asset_weights(
        returns,
        assets,
        weights,
        total_cost_bps=2.0,
    )

    assert result.turnover.tolist() == pytest.approx([0.0, 0.0, 0.5])
    assert result.daily_returns.iloc[2] == pytest.approx((1.0 - 0.0001) * 1.05 - 1.0)
    assert result.weights.tolist() == pytest.approx([0.0, 0.0, 0.5])


def test_fractional_weights_reject_out_of_range_weights() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    returns = pd.DataFrame({"asset_a": [0.0, 0.0]}, index=index)
    assets = pd.Series(["asset_a", "asset_a"], index=index)
    weights = pd.Series([1.2, 1.2], index=index)

    with pytest.raises(ValueError, match="between 0 and 1"):
        simulate_single_asset_weights(returns, assets, weights, total_cost_bps=2.0)
