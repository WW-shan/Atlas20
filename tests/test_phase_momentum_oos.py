from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.engine import BacktestResult
from scripts.run_phase_momentum_oos import _observed_weight_share, _oos_index, _summary_row


def _result(dates: pd.DatetimeIndex) -> BacktestResult:
    empty = pd.DataFrame(index=dates)
    return BacktestResult(
        name="test",
        daily_returns=pd.Series(0.0, index=dates),
        equity_curve=pd.Series(1.0, index=dates),
        drawdown=pd.Series(0.0, index=dates),
        weights=empty,
        turnover=pd.Series(0.0, index=dates),
        holdings_count=pd.Series(0.0, index=dates),
        sector_exposure=empty,
        rebalance_targets=pd.DataFrame({"asset": [1.0]}, index=[dates[0]]),
    )


def test_oos_index_excludes_the_research_end_date() -> None:
    dates = pd.date_range("2026-09-20", periods=4, freq="D")

    result = _oos_index(dates, "2026-09-21")

    assert list(result) == list(dates[2:])


def test_oos_index_rejects_an_empty_window() -> None:
    dates = pd.date_range("2026-09-20", periods=2, freq="D")

    with pytest.raises(ValueError, match="no out-of-sample dates"):
        _oos_index(dates, "2026-09-21")


def test_observed_weight_share_uses_the_execution_day() -> None:
    dates = pd.date_range("2026-09-20", periods=3, freq="D")
    result = _result(dates)
    result.rebalance_targets = pd.DataFrame({"asset_a": [0.6], "asset_b": [0.4]}, index=[dates[0]])
    observed = pd.DataFrame(
        {"asset_a": [False, True, False], "asset_b": [False, False, False]},
        index=dates,
    )

    share = _observed_weight_share(result, observed, dates[1:2])

    assert share == pytest.approx(0.6)


def test_summary_row_keeps_the_frozen_cost_and_fill_labels() -> None:
    returns = pd.Series([0.01, -0.01], index=pd.date_range("2026-09-22", periods=2, freq="D"))

    row = _summary_row(
        returns,
        cost_bps=20.0,
        fill_policy="h3_day_close",
        observed_weight_share=1.0,
        turnover=0.25,
    )

    assert row["cost_bps"] == 20.0
    assert row["fill_policy"] == "h3_day_close"
    assert row["multiple"] == pytest.approx((1.01 * 0.99))
    assert row["observed_weight_share"] == 1.0
    assert row["turnover"] == 0.25
