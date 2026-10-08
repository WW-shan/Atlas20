from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from atlas20.backtest.engine import BacktestResult
from atlas20.config import load_config
from scripts.run_ctrend_champion import _asset_contributions, _latest_signal_payload


def test_latest_signal_uses_latest_data_date_and_latest_target() -> None:
    index = pd.date_range("2024-01-01", periods=15, freq="D")
    market = SimpleNamespace(price=pd.DataFrame({"bitcoin": range(15)}, index=index))
    targets = {
        pd.Timestamp("2024-01-01"): pd.Series({"bitcoin": 1.0}),
        pd.Timestamp("2024-01-10"): pd.Series(dtype=float),
    }
    risk_on = pd.Series(True, index=index)
    config = load_config("config/base.yaml")
    config.start_date = "2024-01-01"

    payload = _latest_signal_payload(targets, risk_on, market, config)

    assert payload["as_of"] == "2024-01-15"
    assert payload["latest_target_date"] == "2024-01-10"
    assert payload["btc_gate_open"] is True
    assert payload["targets"] == {}
    assert payload["gross_exposure"] == 0.0
    assert payload["next_scheduled_rebalance"] == "2024-01-22"


def _switching_backtest():
    # Hold A through days 1-2, then B through days 3-5 (targets execute T+1).
    from atlas20.backtest.engine import run_backtest
    from atlas20.config import FrictionConfig

    index = pd.date_range("2022-01-01", periods=6, freq="D")
    returns = pd.DataFrame(
        {"A": [0.0, 0.10, 0.10, 0.10, 0.10, 0.10], "B": [0.0, 0.50, -0.20, 0.30, 0.0, 0.0]},
        index=index,
    )
    targets = {index[0]: pd.Series({"A": 1.0}), index[2]: pd.Series({"B": 1.0})}
    friction = FrictionConfig(fee_bps=0, slippage_bps=0, max_weight_per_coin=1.0, max_weight_per_sector=1.0)
    result = run_backtest("switch", returns, targets, pd.Series({"A": "x", "B": "y"}), friction, 1.0)
    return result, returns


def test_asset_contributions_credit_each_day_to_the_coin_held() -> None:
    # weights[t] is the book held during day t.  The legacy weights.shift(1)
    # dropped each holding's first day and credited the sold coin with the
    # day after its exit: A=0.2, B=0.0 here instead of A=0.2, B=0.3.
    result, returns = _switching_backtest()

    contributions = _asset_contributions(result, returns)

    assert contributions.to_dict() == pytest.approx({"A": 0.2, "B": 0.3})
    assert float(contributions.sum()) == pytest.approx(float(result.daily_returns.sum()))


def test_subperiod_rows_compound_every_day_of_the_period() -> None:
    # _subperiod_rows slices one long BacktestResult per calendar year.  The
    # sliced equity curve starts after the period's first return, so a total
    # read off the equity ends dropped the first day of every year; the totals
    # must compound all of the period's daily returns.
    from scripts.run_ctrend_champion import _subperiod_rows

    index = pd.date_range("2022-12-30", "2023-01-03", freq="D")
    daily = pd.Series([0.10, -0.05, 0.20, 0.10, -0.10], index=index)
    weights = pd.DataFrame({"bitcoin": 1.0}, index=index)
    zeros = pd.Series(0.0, index=index)
    result = BacktestResult(
        name="probe",
        daily_returns=daily,
        equity_curve=(1.0 + daily).cumprod(),
        drawdown=zeros,
        weights=weights,
        turnover=zeros,
        holdings_count=pd.Series(1.0, index=index),
        sector_exposure=pd.DataFrame(index=index),
        rebalance_targets=weights,
    )

    rows = _subperiod_rows(result, load_config("config/base.yaml")).set_index("period")

    assert rows.loc["2022", "total_return"] == pytest.approx(1.10 * 0.95 - 1.0)
    assert rows.loc["2023", "total_return"] == pytest.approx(1.20 * 1.10 * 0.90 - 1.0)
    assert rows.loc["2023", "max_drawdown"] == pytest.approx(-0.10)
