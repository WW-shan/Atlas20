from __future__ import annotations

import pandas as pd

from atlas20.backtest.engine import run_backtest
from atlas20.backtest.single_asset import simulate_single_asset_targets
from atlas20.config import FrictionConfig, load_config
from atlas20.strategies.event_driven import (
    DailyEventSpec,
    build_daily_event_targets_from_scores,
)
from atlas20.universe.builder import MarketDataBundle


def _config() -> object:
    config = load_config("config/base.yaml").model_copy(deep=True)
    config.start_date = "2024-01-01"
    config.end_date = "2024-01-10"
    config.frictions.fee_bps = 0.0
    config.frictions.slippage_bps = 0.0
    config.frictions.max_weight_per_coin = 1.0
    return config


def _market(dates: pd.DatetimeIndex) -> MarketDataBundle:
    n = len(dates)
    price = pd.DataFrame(
        {
            "a": [100 + i for i in range(n)],
            "b": [100 + max(i - 1, 0) for i in range(n)],
            "bitcoin": [100] * n,
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
        metadata=pd.DataFrame(
            {"sector": ["S", "S", "S"]},
            index=["a", "b", "bitcoin"],
        ),
    )


def test_daily_event_requires_min_hold_before_switching() -> None:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    market = _market(dates)
    scores = pd.DataFrame(
        {
            "a": [0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10, 0.00],
            "b": [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00],
        },
        index=dates,
    )
    built = build_daily_event_targets_from_scores(
        market,
        scores,
        _config(),
        DailyEventSpec(min_hold_days=3, hold_rank=1, switch_score_gap=0.0, confirm_days=1),
    )

    assert list(built.selection_history["coin_id"].iloc[:4]) == ["a", "a", "a", "a"]
    assert built.selection_history["coin_id"].iloc[5] == "b"
    assert built.selection_history.loc[5, "event"] == "switch"


def test_daily_event_holds_when_incumbent_is_inside_rank_band() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    market = _market(dates[:5])
    scores = pd.DataFrame(
        {
            "a": [0.90, 0.85, 0.80, 0.75, 0.70],
            "b": [0.80, 0.88, 0.84, 0.79, 0.74],
        },
        index=dates[:5],
    )
    built = build_daily_event_targets_from_scores(
        market,
        scores,
        _config(),
        DailyEventSpec(min_hold_days=0, hold_rank=2, switch_score_gap=0.50, confirm_days=1),
    )

    assert set(built.selection_history["coin_id"]) == {"a"}


def test_single_asset_simulator_matches_general_engine() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    returns = pd.DataFrame(
        {
            "a": [0.0, 0.01, 0.02, -0.01, 0.03],
            "b": [0.0, 0.00, 0.01, 0.02, -0.02],
        },
        index=dates,
    )
    targets = pd.Series(["a", "a", "b", "b", "b"], index=dates)
    friction = FrictionConfig(fee_bps=2.0, slippage_bps=2.0, max_weight_per_coin=1.0)
    general = run_backtest(
        "general",
        returns,
        {dates[0]: pd.Series({"a": 1.0}), dates[2]: pd.Series({"b": 1.0})},
        pd.Series({"a": "S", "b": "S"}),
        friction,
        initial_capital=1.0,
        max_gross_exposure=1.0,
    )
    fast = simulate_single_asset_targets(returns, targets, total_cost_bps=4.0)

    pd.testing.assert_series_equal(
        general.daily_returns.rename("daily_return"),
        fast.daily_returns,
        check_names=False,
    )


def test_single_asset_simulator_matches_general_engine_on_cash_exit() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    returns = pd.DataFrame(
        {
            "a": [0.0, 0.01, -0.02, 0.03, -0.01],
            "b": [0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=dates,
    )
    targets = pd.Series(["a", "a", "", "", ""], index=dates)
    friction = FrictionConfig(fee_bps=2.0, slippage_bps=2.0, max_weight_per_coin=1.0)
    general = run_backtest(
        "general",
        returns,
        {dates[0]: pd.Series({"a": 1.0}), dates[2]: pd.Series(dtype=float)},
        pd.Series({"a": "S", "b": "S"}),
        friction,
        initial_capital=1.0,
        max_gross_exposure=1.0,
    )
    fast = simulate_single_asset_targets(returns, targets, total_cost_bps=4.0)

    pd.testing.assert_series_equal(
        general.daily_returns.rename("daily_return"),
        fast.daily_returns,
        check_names=False,
    )
