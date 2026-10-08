"""Held positions across short provider gaps under ``missing_return_policy="carry"``.

A provider gap inside a live series (CMC has no row for chainlink on
2022-07-31, then resumes) is not evidence that the coin was flat, halted or
worthless. ``carry`` marks a held coin at its last close through gaps of at
most ``missing_return_max_carry_days`` and books the move on the first print
after the gap, whose return the market-data builder measures from the last
print. Every carried holding, and every trade priced at a carried close, is
recorded on the result, so nothing is filled silently.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import FrictionConfig


def _friction(max_carry_days: int = 3) -> FrictionConfig:
    return FrictionConfig(
        fee_bps=0.0,
        slippage_bps=0.0,
        max_weight_per_coin=1.0,
        missing_return_policy="carry",
        missing_return_max_carry_days=max_carry_days,
    )


def test_carry_marks_a_held_coin_flat_through_a_gap_and_books_the_move_on_resume() -> None:
    dates = pd.date_range("2022-07-29", periods=5, freq="D")
    # Price 100 -> 110, no print on day 2, 133.1 on day 3 (+21% from the last print).
    returns = pd.DataFrame({"a": [0.0, 0.10, np.nan, 0.21, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}

    result = run_backtest("t", returns, targets, pd.Series({"a": "x"}), _friction(), 1.0)

    assert result.daily_returns.tolist() == pytest.approx([0.0, 0.10, 0.0, 0.21, 0.0])
    assert result.equity_curve.iloc[-1] == pytest.approx(1.10 * 1.21)
    carries = result.gap_carries
    assert carries[["date", "asset", "event"]].values.tolist() == [[dates[2], "a", "carried"]]
    assert carries["weight"].tolist() == pytest.approx([1.0])


def test_an_unheld_coin_with_a_gap_is_not_reported() -> None:
    dates = pd.date_range("2022-07-29", periods=4, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.01, 0.01, 0.01], "b": [0.0, 0.02, np.nan, 0.03]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}

    result = run_backtest("t", returns, targets, pd.Series({"a": "x", "b": "x"}), _friction(), 1.0)

    assert result.gap_carries.empty


def test_carry_refuses_a_gap_longer_than_the_limit() -> None:
    dates = pd.date_range("2022-07-01", periods=7, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.01, np.nan, np.nan, np.nan, np.nan, 0.02]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}

    with pytest.raises(ValueError, match="a.*carry"):
        run_backtest("t", returns, targets, pd.Series({"a": "x"}), _friction(max_carry_days=3), 1.0)


def test_a_trade_priced_at_a_carried_close_is_recorded_as_a_stale_fill() -> None:
    dates = pd.date_range("2022-07-29", periods=5, freq="D")
    returns = pd.DataFrame(
        {"a": [0.0, 0.10, np.nan, 0.21, 0.0], "b": [0.0, 0.0, 0.0, 0.05, 0.0]},
        index=dates,
    )
    # The signal on day 2 sells "a", whose day-2 close does not exist.
    targets = {dates[0]: pd.Series({"a": 1.0}), dates[2]: pd.Series({"b": 1.0})}

    result = run_backtest("t", returns, targets, pd.Series({"a": "x", "b": "x"}), _friction(), 1.0)

    events = result.gap_carries.set_index("event")
    assert events.loc["stale_fill", "asset"] == "a"
    assert events.loc["stale_fill", "date"] == dates[2]
    # Sold at the carried day-1 close: the book is in "b" for day 3.
    assert result.daily_returns.loc[dates[3]] == pytest.approx(0.05)


def test_an_ended_feed_is_still_sold_at_its_last_print_under_carry() -> None:
    dates = pd.date_range("2022-07-29", periods=4, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, np.nan, np.nan]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}

    result = run_backtest("t", returns, targets, pd.Series({"a": "x"}), _friction(), 1.0)

    assert result.weights.loc[dates[2], "a"] == 0.0
    assert result.gap_carries.empty


def test_the_error_policy_still_aborts_on_a_held_gap() -> None:
    dates = pd.date_range("2022-07-29", periods=4, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, np.nan, 0.21]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}
    friction = FrictionConfig(fee_bps=0.0, slippage_bps=0.0, max_weight_per_coin=1.0)

    with pytest.raises(ValueError, match="Missing returns for held assets"):
        run_backtest("t", returns, targets, pd.Series({"a": "x"}), friction, 1.0)


def test_carry_never_fills_a_held_coin_outside_its_printed_range() -> None:
    dates = pd.date_range("2022-07-29", periods=4, freq="D")
    # "a" has not printed yet when the target buys it: no gap to carry.
    returns = pd.DataFrame({"a": [np.nan, np.nan, 0.05, 0.01]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}

    with pytest.raises(ValueError, match="Missing returns for held assets"):
        run_backtest("t", returns, targets, pd.Series({"a": "x"}), _friction(), 1.0)
