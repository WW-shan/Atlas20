from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.single_asset import SingleAssetWeightBacktestResult
from atlas20.universe.builder import MarketDataBundle
from scripts.run_momentum_event_breadth_overlay import (
    _blend_returns,
    _breadth_signal,
    _ensemble_returns,
)


def _result(returns: list[float]) -> SingleAssetWeightBacktestResult:
    index = pd.date_range("2024-01-01", periods=len(returns), freq="D")
    return SingleAssetWeightBacktestResult(
        daily_returns=pd.Series(returns, index=index, dtype=float),
        turnover=pd.Series(0.0, index=index, dtype=float),
        holdings=pd.Series(1.0, index=index, dtype=float),
        weights=pd.Series(1.0, index=index, dtype=float),
    )


def test_breadth_signal_uses_current_top20_membership() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    price = pd.DataFrame(
        {
            "a": [10.0, 11.0, 12.0],
            "b": [10.0, 9.0, 8.0],
            "bitcoin": [10.0, 10.0, 10.0],
        },
        index=dates,
    )
    market = MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=pd.DataFrame(1_000_000.0, index=dates, columns=price.columns),
        history_count=pd.DataFrame(200, index=dates, columns=price.columns),
        metadata=pd.DataFrame({"sector": ["S", "S", "S"]}, index=["a", "b", "bitcoin"]),
    )
    universe = pd.DataFrame(
        {
            "rebalance_date": [dates[0], dates[1], dates[2], dates[2]],
            "coin_id": ["a", "a", "a", "b"],
        }
    )

    breadth = _breadth_signal(market, universe, dates, ma_window=2)

    assert breadth.loc[dates[2]] == pytest.approx(0.5)


def test_ensemble_returns_average_all_sleeves() -> None:
    returns = [0.01, 0.02]
    sleeve_results = {}
    for family in ("ctrend_lite_balanced", "ctrend_lite_relative_strength", "ctrend_lite_breakout"):
        for target_vol in (0.7, 0.8):
            sleeve_results[f"{family}|tv{target_vol:.1f}"] = _result(returns)

    ensemble = _ensemble_returns(
        sleeve_results,
        target_vols=(0.7, 0.8),
        cost_bps=0.0,
    )

    assert ensemble.tolist() == pytest.approx(returns)


def _six_sleeves(returns: list[float]) -> dict[str, SingleAssetWeightBacktestResult]:
    return {
        f"{family}|tv{target_vol:.1f}": _result(returns)
        for family in ("ctrend_lite_balanced", "ctrend_lite_relative_strength", "ctrend_lite_breakout")
        for target_vol in (0.7, 0.8)
    }


def test_blend_holds_baseline_and_breadth_books_without_daily_rebalancing() -> None:
    # Incident: the 25/50/75 blends were weighted means of the two books' daily
    # returns, a daily rebalance between them that was never charged. A 50/50
    # book whose halves go 2.0 -> 1.0 and 0.5 -> 1.0 ends flat when held.
    baseline = _six_sleeves([1.0, -0.5])
    breadth = _six_sleeves([-0.5, 1.0])

    blend = _blend_returns(
        baseline,
        breadth,
        baseline_weight=0.5,
        target_vols=(0.7, 0.8),
        cost_bps=0.0,
    )

    assert blend.tolist() == pytest.approx([0.25, -0.2])


def test_blend_weights_split_initial_capital_between_books() -> None:
    baseline = _six_sleeves([1.0, 0.0])
    breadth = _six_sleeves([0.0, 0.0])

    all_baseline = _blend_returns(
        baseline, breadth, baseline_weight=1.0, target_vols=(0.7, 0.8), cost_bps=0.0
    )
    quarter = _blend_returns(
        baseline, breadth, baseline_weight=0.25, target_vols=(0.7, 0.8), cost_bps=0.0
    )

    assert all_baseline.tolist() == pytest.approx([1.0, 0.0])
    assert quarter.tolist() == pytest.approx([0.25, 0.0])
