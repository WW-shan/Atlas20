from __future__ import annotations

import logging

import pandas as pd
import pytest

from atlas20.backtest.engine import cap_sector_weights, delay_by_trading_days, run_backtest
from atlas20.config import FrictionConfig, load_config


def test_delay_by_trading_days_moves_each_event_later_and_drops_overflow() -> None:
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    events = {dates[0]: "first", dates[2]: "second", dates[3]: "last"}

    assert delay_by_trading_days(events, dates, 0) == events
    assert delay_by_trading_days(events, dates, 1) == {dates[1]: "first", dates[3]: "second"}


def test_delay_by_trading_days_rejects_unknown_dates_and_negative_lags() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")

    with pytest.raises(ValueError, match="not in the index"):
        delay_by_trading_days({pd.Timestamp("2023-12-31"): 1.0}, dates, 1)
    with pytest.raises(ValueError, match="non-negative"):
        delay_by_trading_days({dates[0]: 1.0}, dates, -1)


def test_one_day_execution_lag_misses_the_first_day_of_the_move() -> None:
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"bitcoin": [0.0, 0.10, 0.20, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"bitcoin": 1.0})}
    friction = FrictionConfig(fee_bps=0, slippage_bps=0, max_weight_per_coin=1.0)

    result = run_backtest(
        "lagged",
        returns,
        delay_by_trading_days(targets, dates, 1),
        pd.Series({"bitcoin": "x"}),
        friction,
        1.0,
    )

    assert result.daily_returns.loc[dates[1]] == 0.0
    assert result.daily_returns.loc[dates[2]] == pytest.approx(0.20)


def test_run_backtest_applies_rebalance_one_day_later_and_records_turnover() -> None:
    config = load_config("config/base.yaml")
    config.frictions.fee_bps = 0.0
    config.frictions.slippage_bps = 0.0
    # This test is about the T+1 mechanics, not the diversification cap, so a
    # single pick is allowed to be a full position.
    config.frictions.max_weight_per_coin = 1.0
    config.frictions.max_weight_per_sector = 1.0
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


def test_sector_cap_is_enforced_without_redistributing_to_other_sectors() -> None:
    weights = pd.Series({"a": 0.6, "b": 0.2, "c": 0.2})
    sectors = pd.Series({"a": "x", "b": "x", "c": "y"})

    capped = cap_sector_weights(weights, sectors, 0.5)

    assert capped[["a", "b"]].sum() == pytest.approx(0.5)
    assert capped["a"] == pytest.approx(0.375)
    assert capped["b"] == pytest.approx(0.125)
    assert capped["c"] == pytest.approx(0.2)
    assert capped.sum() == pytest.approx(0.7)


def test_run_backtest_applies_sector_cap_after_per_coin_cap() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame(
        {"a": [0.0, 0.0, 0.0], "b": [0.0, 0.0, 0.0], "c": [0.0, 0.0, 0.0]},
        index=dates,
    )
    targets = {dates[0]: pd.Series({"a": 0.6, "b": 0.2, "c": 0.2})}
    sectors = pd.Series({"a": "x", "b": "x", "c": "y"})
    friction = FrictionConfig(
        fee_bps=0.0,
        slippage_bps=0.0,
        max_weight_per_coin=1.0,
        max_weight_per_sector=0.5,
    )

    result = run_backtest("t", returns, targets, sectors, friction, 100.0)

    assert result.weights.loc[dates[1], ["a", "b"]].sum() == pytest.approx(0.5)
    assert result.weights.loc[dates[1], "c"] == pytest.approx(0.2)
    assert result.weights.loc[dates[1]].sum() == pytest.approx(0.7)


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


def test_caps_bind_on_nav_weights_when_the_book_is_partly_invested() -> None:
    """Regression: the caps used to bind on the invested fraction, not on NAV.

    The target was normalized to sum to one and capped *before* the exposure
    was applied. At 50% exposure eth + sol (60% of the book, 30% of NAV) were
    trimmed by the 50% sector cap as if the book were fully invested, and the
    run ended at 42.5% gross instead of 50%.
    """
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame(0.0, index=dates, columns=["btc", "eth", "sol"])
    targets = {dates[0]: pd.Series({"btc": 0.4, "eth": 0.3, "sol": 0.3})}
    sectors = pd.Series({"btc": "Store of Value", "eth": "L1", "sol": "L1"})
    friction = FrictionConfig(
        fee_bps=0.0,
        slippage_bps=0.0,
        max_weight_per_coin=0.35,
        max_weight_per_sector=0.50,
    )

    result = run_backtest(
        "t", returns, targets, sectors, friction, 100.0, gross_target_exposure=0.5
    )

    executed = result.rebalance_targets.loc[dates[0]]
    assert executed.to_dict() == pytest.approx({"btc": 0.20, "eth": 0.15, "sol": 0.15})
    assert result.weights.loc[dates[1]].sum() == pytest.approx(0.5)


def test_single_pick_below_the_coin_cap_keeps_its_full_exposure() -> None:
    """A 30% position is inside a 35% NAV cap and must not become 10.5%."""
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"btc": [0.0, 0.10, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"btc": 1.0})}
    friction = FrictionConfig(fee_bps=0.0, slippage_bps=0.0, max_weight_per_coin=0.35)

    result = run_backtest(
        "t",
        returns,
        targets,
        pd.Series({"btc": "x"}),
        friction,
        100.0,
        leverage_by_date={dates[0]: 0.30},
    )

    assert result.rebalance_targets.loc[dates[0], "btc"] == pytest.approx(0.30)
    assert result.daily_returns.loc[dates[1]] == pytest.approx(0.03)


def test_nav_coin_cap_redistributes_up_to_the_exposure_and_parks_the_rest() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame(0.0, index=dates, columns=["a", "b", "c"])
    targets = {
        dates[0]: pd.Series({"a": 0.6, "b": 0.2, "c": 0.2}),
        dates[1]: pd.Series({"a": 0.5, "b": 0.5}),
    }
    friction = FrictionConfig(fee_bps=0.0, slippage_bps=0.0, max_weight_per_coin=0.35)

    result = run_backtest(
        "t",
        returns,
        targets,
        pd.Series({"a": "x", "b": "y", "c": "z"}),
        friction,
        100.0,
        leverage_by_date={dates[0]: 0.8, dates[1]: 0.9},
    )

    # a is 48% of NAV: trimmed to 35%, and the freed 13% goes to b and c, so
    # the book stays at its 80% exposure.
    first = result.rebalance_targets.loc[dates[0]]
    assert first.to_dict() == pytest.approx({"a": 0.35, "b": 0.225, "c": 0.225})
    # Both names are over the cap at 45% of NAV and nothing is left to take
    # the excess, so it stays in cash instead of breaching the cap.
    second = result.rebalance_targets.loc[dates[1]]
    assert second.to_dict() == pytest.approx({"a": 0.35, "b": 0.35, "c": 0.0})


def test_full_exposure_caps_match_cap_and_normalize_exactly() -> None:
    """At 1x the NAV caps must reproduce the historical rebalance targets bit for bit."""
    from atlas20.backtest.engine import cap_and_normalize

    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    columns = ["a", "b", "c", "d"]
    returns = pd.DataFrame(0.0, index=dates, columns=columns)
    raw = pd.Series({"a": 0.47, "b": 0.31, "c": 0.13, "d": 0.09})
    sectors = pd.Series({"a": "x", "b": "y", "c": "y", "d": "z"})
    friction = FrictionConfig(
        fee_bps=0.0,
        slippage_bps=0.0,
        max_weight_per_coin=0.35,
        max_weight_per_sector=0.50,
    )

    result = run_backtest("t", returns, {dates[0]: raw}, sectors, friction, 100.0)

    expected = cap_sector_weights(cap_and_normalize(raw, 0.35), sectors, 0.50)
    assert result.rebalance_targets.loc[dates[0]].tolist() == expected.reindex(columns).tolist()


def test_non_finite_exposure_is_rejected_with_its_date() -> None:
    """Regression: a NaN leverage used to become a silent all-cash book.

    The NaN weights then made the next entry look free: zero turnover and no
    trading cost when the book was rebuilt.
    """
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, 0.10, 0.10]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0}), dates[1]: pd.Series({"a": 1.0})}
    friction = FrictionConfig(fee_bps=10.0, slippage_bps=10.0, max_weight_per_coin=1.0)

    with pytest.raises(ValueError, match="exposure.*2024-01-02"):
        run_backtest(
            "t",
            returns,
            targets,
            pd.Series({"a": "x"}),
            friction,
            100.0,
            leverage_by_date={dates[0]: 1.0, dates[1]: float("nan")},
        )
    with pytest.raises(ValueError, match="exposure.*2024-01-01"):
        run_backtest(
            "t",
            returns,
            targets,
            pd.Series({"a": "x"}),
            friction,
            100.0,
            gross_target_exposure=float("inf"),
            max_gross_exposure=1.0,
        )


@pytest.mark.parametrize("bad_weight", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_target_weight_is_rejected_with_its_date(bad_weight: float) -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, 0.10], "b": [0.0, 0.0, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"a": bad_weight, "b": 1.0})}
    friction = FrictionConfig(fee_bps=0.0, slippage_bps=0.0, max_weight_per_coin=1.0)

    with pytest.raises(ValueError, match="target weight.*2024-01-01"):
        run_backtest("t", returns, targets, pd.Series({"a": "x", "b": "y"}), friction, 100.0)


def test_dates_outside_the_returns_window_are_skipped_with_a_warning(caplog) -> None:
    """Keys the engine can never reach used to vanish without a trace.

    Research scripts hand a full-sample overlay (it starts min_history_days
    before the window) to a window-sliced return frame, so such keys are still
    skipped, but the run now says how many there were and which dates.
    """
    dates = pd.date_range("2024-01-10", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, 0.0]}, index=dates)
    targets = {
        pd.Timestamp("2024-01-01"): pd.Series({"a": 1.0}),
        pd.Timestamp("2024-01-05"): pd.Series(dtype=float),
        dates[0]: pd.Series({"a": 1.0}),
        pd.Timestamp("2024-02-01"): pd.Series({"a": 1.0}),
    }
    leverage = {pd.Timestamp("2024-01-05"): 0.5, dates[0]: 1.0}
    friction = FrictionConfig(fee_bps=0.0, slippage_bps=0.0, max_weight_per_coin=1.0)

    with caplog.at_level(logging.WARNING, logger="atlas20.backtest.engine"):
        result = run_backtest(
            "t",
            returns,
            targets,
            pd.Series({"a": "x"}),
            friction,
            100.0,
            leverage_by_date=leverage,
        )

    assert result.daily_returns.loc[dates[1]] == pytest.approx(0.10)
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "3 rebalance target date(s)" in message and "2024-01-01" in message and "2024-02-01" in message
        for message in messages
    )
    assert any("1 leverage date(s)" in message and "2024-01-05" in message for message in messages)


def test_dates_inside_the_returns_window_do_not_warn(caplog) -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, 0.0]}, index=dates)
    friction = FrictionConfig(fee_bps=0.0, slippage_bps=0.0, max_weight_per_coin=1.0)

    with caplog.at_level(logging.WARNING, logger="atlas20.backtest.engine"):
        run_backtest(
            "t",
            returns,
            {dates[0]: pd.Series({"a": 1.0})},
            pd.Series({"a": "x"}),
            friction,
            100.0,
            leverage_by_date={dates[0]: 1.0},
        )

    assert caplog.records == []
