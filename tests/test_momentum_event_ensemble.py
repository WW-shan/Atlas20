from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.single_asset import SingleAssetWeightBacktestResult
from atlas20.universe.builder import MarketDataBundle
from scripts.run_momentum_event_ensemble import (
    _ensemble_returns,
    _net_returns,
    _vol_target_events,
)


def _result(returns: list[float], turnover: list[float]) -> SingleAssetWeightBacktestResult:
    index = pd.date_range("2024-01-01", periods=len(returns), freq="D")
    return SingleAssetWeightBacktestResult(
        daily_returns=pd.Series(returns, index=index, dtype=float),
        turnover=pd.Series(turnover, index=index, dtype=float),
        holdings=pd.Series([1.0] * len(returns), index=index, dtype=float),
        weights=pd.Series([1.0] * len(returns), index=index, dtype=float),
    )


def _market(dates: pd.DatetimeIndex) -> MarketDataBundle:
    price = pd.DataFrame(
        {
            "a": [100.0] * len(dates),
            "bitcoin": [100.0] * len(dates),
        },
        index=dates,
    )
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000,
        volume=pd.DataFrame(1_000_000.0, index=dates, columns=price.columns),
        history_count=pd.DataFrame(200, index=dates, columns=price.columns),
        metadata=pd.DataFrame({"sector": ["S", "S"]}, index=["a", "bitcoin"]),
    )


def test_vol_target_events_are_sparse_and_go_to_cash_when_gate_off() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    market = _market(dates)
    target_assets = pd.Series(["a", "a", "a", "", ""], index=dates, dtype="object")
    risk_on = pd.Series([True, False, True, True, True], index=dates)

    assets, weights = _vol_target_events(
        market,
        target_assets,
        risk_on,
        target_volatility=0.5,
        vol_window=2,
    )

    assert assets.loc[dates[0]] == "a"
    assert assets.loc[dates[1]] == "__cash__"
    assert assets.loc[dates[2]] == "a"
    assert assets.loc[dates[3]] == "__cash__"
    assert pd.isna(assets.loc[dates[4]])
    assert weights.loc[dates[0]] == pytest.approx(1.0)
    assert weights.loc[dates[1]] == pytest.approx(0.0)
    assert weights.loc[dates[2]] == pytest.approx(1.0)


def test_net_returns_charge_turnover() -> None:
    result = _result([0.01], [2.0])

    net = _net_returns(result, 10.0)

    assert net.iloc[0] == pytest.approx((1.0 - 0.002) * 1.01 - 1.0)


def test_ensemble_returns_average_all_sleeves() -> None:
    returns = [0.01, 0.02]
    turnover = [0.0, 0.0]
    sleeve_results = {}
    for family in ("ctrend_lite_balanced", "ctrend_lite_relative_strength", "ctrend_lite_breakout"):
        for target_vol in (0.7, 0.8):
            sleeve_results[f"primary_mh5_hr2_g10_c1|{family}|tv{target_vol:.1f}"] = _result(
                returns,
                turnover,
            )

    ensemble = _ensemble_returns(
        sleeve_results,
        spec_name="primary_mh5_hr2_g10_c1",
        target_vols=(0.7, 0.8),
        cost_bps=0.0,
    )

    assert ensemble.tolist() == pytest.approx(returns)
