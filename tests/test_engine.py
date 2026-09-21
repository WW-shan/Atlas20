from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import FrictionConfig, load_config


def test_run_backtest_applies_rebalance_one_day_later_and_records_turnover() -> None:
    config = load_config("config/base.yaml")
    config.frictions.fee_bps = 0.0
    config.frictions.slippage_bps = 0.0
    # This test is about the T+1 mechanics, not the diversification cap, so a
    # single pick is allowed to be a full position.
    config.frictions.max_weight_per_coin = 1.0
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"bitcoin": [0.0, 0.10, 0.0, 0.0], "ethereum": [0.0, 0.0, 0.0, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"bitcoin": 1.0})}
    sector_map = pd.Series({"bitcoin": "Store of Value", "ethereum": "Smart Contract Platform / L1"})

    result = run_backtest("test", returns, targets, sector_map, config.frictions, config.initial_capital)

    assert result.turnover.loc[dates[1]] == 1.0
    assert result.daily_returns.loc[dates[1]] == pytest.approx(0.10)
    assert result.equity_curve.loc[dates[1]] > result.equity_curve.loc[dates[0]]


def test_weights_stay_fully_invested_after_paying_trading_costs() -> None:
    """Regression: costs shrink capital, not holdings.

    The drift denominator used to be the *net* return, which divided by
    (1 - cost) as well and left the book implicitly levered by 1/(1-cost)
    after every rebalance. That compounded into an overstated return.
    """
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame(
        {"a": [0.0, 0.10, 0.0, 0.0], "b": [0.0, 0.0, 0.05, 0.0]},
        index=dates,
    )
    targets = {dates[0]: pd.Series({"a": 1.0}), dates[1]: pd.Series({"b": 1.0})}
    friction = FrictionConfig(fee_bps=10, slippage_bps=10, max_weight_per_coin=1.0)

    result = run_backtest(
        "t", returns, targets, pd.Series({"a": "x", "b": "x"}), friction, 100.0
    )

    # Fully invested whenever in the market, never implicitly levered.
    sums = result.weights.sum(axis=1)
    assert sums.tolist() == pytest.approx([0.0, 1.0, 1.0, 1.0])

    # Hand-derived: build at 20bp on day 1, rotate (turnover 2.0) on day 2.
    capital = 100.0 * (1.0 - 1.0 * 0.002) * 1.10
    capital = capital * (1.0 - 2.0 * 0.002) * 1.05
    assert result.equity_curve.iloc[-1] == pytest.approx(capital, rel=1e-12)


def test_per_coin_cap_is_enforced_and_never_raises_the_largest_weight() -> None:
    """Regression: the cap used to be silently defeated.

    The old redistribution overwrote the under-cap weights with the freed
    weight (instead of adding to them) and then renormalized, so a capped
    weight could come back *larger* than it went in.
    """
    from atlas20.backtest.engine import cap_and_normalize

    # A single pick cannot be capped without going to cash: 35% invested.
    single = cap_and_normalize(pd.Series({"a": 1.0}), 0.35)
    assert single["a"] == pytest.approx(0.35)
    assert single.sum() == pytest.approx(0.35)

    # Two assets that are both over the cap leave the residual in cash.
    pair = cap_and_normalize(pd.Series({"a": 0.6, "b": 0.4}), 0.35)
    assert pair.max() == pytest.approx(0.35)
    assert pair.sum() == pytest.approx(0.70)

    # Mixed book: cap the offender, redistribute to the rest, stay invested.
    mixed = cap_and_normalize(pd.Series({"a": 0.5, "b": 0.3, "c": 0.2}), 0.35)
    assert mixed.max() <= 0.35 + 1e-12
    assert mixed.sum() == pytest.approx(1.0)
    assert mixed["a"] == pytest.approx(0.35)

    # Nothing over the cap is left untouched.
    even = cap_and_normalize(pd.Series({"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}), 0.35)
    assert even.tolist() == pytest.approx([0.25, 0.25, 0.25, 0.25])

    # The largest weight must never grow past the cap.
    skewed = cap_and_normalize(pd.Series({"a": 0.7, "b": 0.2, "c": 0.1}), 0.5)
    assert skewed.max() <= 0.5 + 1e-12
    assert skewed.sum() == pytest.approx(1.0)


def test_interior_missing_return_for_a_held_asset_fails_closed() -> None:
    """A provider hole in the middle of a live series must never be marked flat.

    The asset prints again on the last day, so this is a gap in the feed, not a
    delisting: the engine has no defensible price for it and refuses to guess.
    """
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, float("nan"), 0.05]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}
    friction = FrictionConfig(fee_bps=0.0, slippage_bps=0.0, max_weight_per_coin=1.0)

    with pytest.raises(ValueError, match="Missing returns for held assets"):
        run_backtest("t", returns, targets, pd.Series({"a": "x"}), friction, 100.0)


def test_missing_return_fill_requires_an_explicit_policy() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, float("nan"), 0.05]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}
    friction = FrictionConfig(
        fee_bps=0.0,
        slippage_bps=0.0,
        max_weight_per_coin=1.0,
        missing_return_policy="fill",
        missing_return_fill=-1.0,
    )

    result = run_backtest("t", returns, targets, pd.Series({"a": "x"}), friction, 100.0)

    assert result.daily_returns.loc[dates[1]] == pytest.approx(-1.0)
    assert result.equity_curve.loc[dates[1]] == pytest.approx(0.0)


def test_ended_feed_is_liquidated_at_its_last_price() -> None:
    """A delisted holding is sold, not carried at a price nobody quotes.

    MATIC's feed stops on 2025-03-24 when the token migrates to POL. A strategy
    holding it that day can still sell at the last print, so the position is
    marked there, the exit cost is charged, and the proceeds sit in cash
    instead of aborting the run or being marked flat forever.
    """
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, float("nan"), float("nan")]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}
    friction = FrictionConfig(fee_bps=10.0, slippage_bps=10.0, max_weight_per_coin=1.0)

    result = run_backtest("t", returns, targets, pd.Series({"a": "x"}), friction, 100.0)

    # Day 1: the entry is executed at the day-0 signal, so +10% net of the
    # 20bps entry cost.
    assert result.daily_returns.loc[dates[1]] == pytest.approx((1 - 0.002) * 1.10 - 1)
    # Day 2: the feed has ended, so the position is sold at the last close.
    # The only cost is the exit (2 * 10bps on a full position).
    assert result.daily_returns.loc[dates[2]] == pytest.approx(-0.002)
    # Day 3: in cash.
    assert result.daily_returns.loc[dates[3]] == pytest.approx(0.0)
    assert result.weights.loc[dates[2], "a"] == pytest.approx(0.0)
    assert result.turnover.loc[dates[2]] == pytest.approx(1.0)
    assert result.holdings_count.loc[dates[3]] == 0
