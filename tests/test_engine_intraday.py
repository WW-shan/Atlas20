from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import FrictionConfig


def _friction(bps: float = 0.0) -> FrictionConfig:
    return FrictionConfig(fee_bps=bps, slippage_bps=0.0, max_weight_per_coin=1.0)


def test_entry_only_earns_the_move_after_the_fill() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, 0.0]}, index=dates)
    # 4% of day 1's 10% happened between the prior close and the fill.
    pre_fill = pd.DataFrame({"a": [0.0, 0.04, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}

    result = run_backtest(
        "t", returns, targets, pd.Series({"a": "x"}), _friction(), 1.0, pre_fill_returns=pre_fill
    )

    assert result.daily_returns.loc[dates[1]] == pytest.approx(1.10 / 1.04 - 1.0)


def test_exit_keeps_the_old_book_until_the_fill() -> None:
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.0, -0.05, 0.0]}, index=dates)
    pre_fill = pd.DataFrame({"a": [0.0, 0.0, -0.02, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0}), dates[1]: pd.Series({"a": 0.0})}

    result = run_backtest(
        "t", returns, targets, pd.Series({"a": "x"}), _friction(), 1.0, pre_fill_returns=pre_fill
    )

    assert result.daily_returns.loc[dates[2]] == pytest.approx(-0.02)
    assert result.weights.loc[dates[2], "a"] == 0.0


def test_turnover_is_measured_against_the_book_at_the_fill() -> None:
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame(
        {"a": [0.0, 0.0, 0.10, 0.0], "b": [0.0, 0.0, 0.0, 0.0]},
        index=dates,
    )
    pre_fill = pd.DataFrame({"a": [0.0, 0.0, 0.10, 0.0], "b": [0.0] * 4}, index=dates)
    targets = {
        dates[0]: pd.Series({"a": 0.5, "b": 0.5}),
        dates[1]: pd.Series({"a": 0.5, "b": 0.5}),
    }

    result = run_backtest(
        "t",
        returns,
        targets,
        pd.Series({"a": "x", "b": "x"}),
        _friction(),
        1.0,
        pre_fill_returns=pre_fill,
    )

    # "a" rose 10% before the fill, so the book was 0.55/0.45 of NAV
    # (0.524/0.476) when it traded back to 50/50.
    drifted_a = 0.5 * 1.10 / 1.05
    assert result.turnover.loc[dates[2]] == pytest.approx(2.0 * (drifted_a - 0.5))


def test_no_pre_fill_matrix_keeps_the_close_fill() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame({"a": [0.0, 0.10, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"a": 1.0})}

    result = run_backtest("t", returns, targets, pd.Series({"a": "x"}), _friction(), 1.0)

    assert result.daily_returns.loc[dates[1]] == pytest.approx(0.10)
