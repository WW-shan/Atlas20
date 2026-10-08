from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.single_asset import SingleAssetWeightBacktestResult
from atlas20.config import load_config
from atlas20.strategies.momentum_lead import MomentumLeadBuildResult
from atlas20.universe.builder import MarketDataBundle
from scripts.run_momentum_event_ensemble import (
    PRIMARY_SPEC,
    _buy_and_hold_returns,
    _ensemble_returns,
    _net_returns,
    _target_assets_from_scores,
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


def _sleeves(paths_by_target_vol: dict[float, list[float]]) -> dict[str, SingleAssetWeightBacktestResult]:
    sleeve_results = {}
    for family in ("ctrend_lite_balanced", "ctrend_lite_relative_strength", "ctrend_lite_breakout"):
        for target_vol, returns in paths_by_target_vol.items():
            sleeve_results[f"primary_mh5_hr2_g10_c1|{family}|tv{target_vol:.1f}"] = _result(
                returns,
                [0.0] * len(returns),
            )
    return sleeve_results


def test_ensemble_holds_sleeves_without_daily_re_equalising() -> None:
    # Incident: the ensemble was the mean of the sleeves' daily returns, i.e. a
    # book re-equalised across sleeves every day for free (~1.7x a year of
    # uncharged sleeve turnover; the RESEARCH 0.7 book was 28.92x at 2 bps,
    # 25.08x with the sleeves simply held). Sleeve equity 2.0 -> 1.0 and
    # 0.5 -> 1.0 must leave a buy-and-hold book flat, not up 56%.
    sleeve_results = _sleeves({0.7: [1.0, -0.5], 0.8: [-0.5, 1.0]})

    ensemble = _ensemble_returns(
        sleeve_results,
        spec_name="primary_mh5_hr2_g10_c1",
        target_vols=(0.7, 0.8),
        cost_bps=0.0,
    )

    assert ensemble.tolist() == pytest.approx([0.25, -0.2])
    assert float((1.0 + ensemble).prod()) == pytest.approx(1.0)


def test_ensemble_period_starts_with_equal_capital_in_every_sleeve() -> None:
    # A sub-period (post_2024, the stress window) is a book funded on its own
    # start date, not the full-window book's drifted sleeve weights.
    sleeve_results = _sleeves({0.7: [1.0, -0.5, 0.1], 0.8: [-0.5, 1.0, 0.1]})
    start = pd.Timestamp("2024-01-02")

    ensemble = _ensemble_returns(
        sleeve_results,
        spec_name="primary_mh5_hr2_g10_c1",
        target_vols=(0.7, 0.8),
        cost_bps=0.0,
        start=start,
    )

    assert ensemble.index[0] == start
    # (0.5 + 2.0) / 2 on the first day, then 10% on the whole book.
    assert ensemble.tolist() == pytest.approx([0.25, 0.1])


def test_buy_and_hold_refuses_missing_sleeve_returns() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    sleeves = pd.DataFrame({"a": [0.01, float("nan")], "b": [0.0, 0.01]}, index=index)

    with pytest.raises(ValueError, match="missing"):
        _buy_and_hold_returns(sleeves)


def test_target_assets_refuse_a_coin_outside_the_days_top20(monkeypatch: pytest.MonkeyPatch) -> None:
    # The old opt-out held coins that had left the Top20 for up to min_hold
    # days. The builder no longer can, and the runner checks every sleeve
    # target against that day's scored Top20 so a regression cannot reach
    # the results silently.
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    market = _market(dates)
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.start_date = "2024-01-01"
    config.end_date = "2024-01-03"
    score_panel = pd.DataFrame({"a": [0.9, float("nan"), 0.8]}, index=dates)
    leaky = MomentumLeadBuildResult(
        targets={date: pd.Series({"a": 1.0}) for date in dates},
        selection_history=pd.DataFrame(),
    )
    monkeypatch.setattr(
        "scripts.run_momentum_event_ensemble.build_daily_event_targets_from_scores",
        lambda *args, **kwargs: leaky,
    )

    with pytest.raises(ValueError, match="outside the day's point-in-time Top20"):
        _target_assets_from_scores(market, score_panel, config, PRIMARY_SPEC, dates)
