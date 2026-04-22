from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import load_config


def test_run_backtest_applies_rebalance_one_day_later_and_records_turnover() -> None:
    config = load_config("config/base.yaml")
    config.frictions.fee_bps = 0.0
    config.frictions.slippage_bps = 0.0
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = pd.DataFrame({"bitcoin": [0.0, 0.10, 0.0, 0.0], "ethereum": [0.0, 0.0, 0.0, 0.0]}, index=dates)
    targets = {dates[0]: pd.Series({"bitcoin": 1.0})}
    sector_map = pd.Series({"bitcoin": "Store of Value", "ethereum": "Smart Contract Platform / L1"})

    result = run_backtest("test", returns, targets, sector_map, config.frictions, config.initial_capital)

    assert result.turnover.loc[dates[1]] == 1.0
    assert result.daily_returns.loc[dates[1]] == pytest.approx(0.10)
    assert result.equity_curve.loc[dates[1]] > result.equity_curve.loc[dates[0]]
