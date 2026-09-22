from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.single_asset import SingleAssetWeightBacktestResult
from atlas20.universe.builder import MarketDataBundle
from scripts.run_momentum_event_breadth_overlay import (
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
