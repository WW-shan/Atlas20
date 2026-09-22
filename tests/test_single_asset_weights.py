from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import FrictionConfig
from atlas20.backtest.single_asset import (
    simulate_single_asset_targets,
    simulate_single_asset_weight_targets,
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


def test_sparse_weight_targets_drift_between_rebalances() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"asset_a": [0.0, 0.10, 0.10, 0.10]}, index=index)
    assets = pd.Series(["asset_a", pd.NA, pd.NA, pd.NA], index=index, dtype="object")
    weights = pd.Series([0.5, float("nan"), float("nan"), float("nan")], index=index)

    result = simulate_single_asset_weight_targets(
        returns,
        assets,
        weights,
        total_cost_bps=0.0,
    )

    assert result.daily_returns.tolist() == pytest.approx(
        [0.0, 0.05, 0.05238095238095242, 0.054751131221719485]
    )
    assert result.weights.tolist() == pytest.approx(
        [0.0, 0.5238095238095238, 0.5475113122171946, 0.5709995709995711]
    )


def test_sparse_weight_targets_reject_partial_events() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    returns = pd.DataFrame({"asset_a": [0.0, 0.0]}, index=index)
    assets = pd.Series(["asset_a", pd.NA], index=index, dtype="object")
    weights = pd.Series([float("nan"), float("nan")], index=index)

    with pytest.raises(ValueError, match="present together"):
        simulate_single_asset_weight_targets(
            returns,
            assets,
            weights,
            total_cost_bps=0.0,
        )


def test_sparse_weight_targets_match_production_engine() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"asset_a": [0.0, 0.10, 0.10, 0.10]}, index=index)
    assets = pd.Series(["asset_a", pd.NA, pd.NA, pd.NA], index=index, dtype="object")
    weights = pd.Series([0.5, float("nan"), float("nan"), float("nan")], index=index)

    fast = simulate_single_asset_weight_targets(
        returns,
        assets,
        weights,
        total_cost_bps=0.0,
    )
    engine = run_backtest(
        "engine_check",
        returns,
        {index[0]: pd.Series({"asset_a": 1.0})},
        pd.Series({"asset_a": "Other"}),
        FrictionConfig(
            fee_bps=0.0,
            slippage_bps=0.0,
            max_weight_per_coin=1.0,
            max_weight_per_sector=1.0,
        ),
        initial_capital=1.0,
        leverage_by_date={index[0]: 0.5},
        max_gross_exposure=1.0,
    )

    pd.testing.assert_series_equal(
        fast.daily_returns,
        engine.daily_returns,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        fast.weights,
        engine.weights["asset_a"],
        check_names=False,
    )
