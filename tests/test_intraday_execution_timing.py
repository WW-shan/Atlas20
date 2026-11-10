from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from atlas20.backtest.engine import BacktestResult
from scripts.analyze_intraday_execution_timing import (
    _combine_half_sleeves,
    execution_price_edge_bps,
    load_30m_bars,
    pre_fill_returns_at_minutes,
)


def _bars() -> dict[str, pd.DataFrame]:
    start = pd.Timestamp("2024-01-02 00:00", tz="UTC")
    return {
        "bitcoin": pd.DataFrame(
            {
                "open_time": [start, start + pd.Timedelta(minutes=30), start + pd.Timedelta(minutes=60)],
                "open": [100.0, 101.0, 104.0],
                "high": [102.0, 105.0, 105.0],
                "low": [99.0, 100.0, 101.0],
                "close": [101.0, 104.0, 103.0],
                "volume": [1.0, 1.0, 1.0],
                "quote_volume": [100.0, 100.0, 100.0],
            }
        )
    }


def test_pre_fill_returns_at_minutes_uses_the_bar_closing_at_the_fill() -> None:
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    daily = pd.DataFrame({"bitcoin": [0.0, 0.10]}, index=dates)
    closes = pd.DataFrame({"bitcoin": [100.0, 110.0]}, index=dates)

    prefill = pre_fill_returns_at_minutes(
        daily,
        _bars(),
        fill_minutes=60,
        missing_fill="prior_close",
        reference_close=closes,
    )

    assert prefill.loc[dates[1], "bitcoin"] == pytest.approx(0.04)


def test_pre_fill_returns_at_minutes_maps_the_0130_fill_to_the_0100_bar() -> None:
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    daily = pd.DataFrame({"bitcoin": [0.0, 0.10]}, index=dates)
    closes = pd.DataFrame({"bitcoin": [100.0, 110.0]}, index=dates)

    prefill = pre_fill_returns_at_minutes(
        daily,
        _bars(),
        fill_minutes=90,
        missing_fill="prior_close",
        reference_close=closes,
    )

    assert prefill.loc[dates[1], "bitcoin"] == pytest.approx(0.03)


def test_pre_fill_returns_at_minutes_brackets_a_missing_bar() -> None:
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    daily = pd.DataFrame({"bitcoin": [0.0, 0.10]}, index=dates)

    day_close = pre_fill_returns_at_minutes(daily, {}, fill_minutes=60, missing_fill="day_close")
    prior_close = pre_fill_returns_at_minutes(daily, {}, fill_minutes=60, missing_fill="prior_close")

    assert day_close.loc[dates[1], "bitcoin"] == pytest.approx(0.10)
    assert prior_close.loc[dates[1], "bitcoin"] == pytest.approx(0.0)


def test_execution_price_edge_is_favourable_positive_for_both_trade_sides() -> None:
    assert execution_price_edge_bps(100.0, 95.0, 1.0) == pytest.approx(500.0)
    assert execution_price_edge_bps(100.0, 95.0, -1.0) == pytest.approx(-500.0)
    assert np.isnan(execution_price_edge_bps(100.0, float("nan"), 1.0))


def test_load_30m_bars_rejects_an_open_time_not_in_milliseconds(tmp_path) -> None:
    (tmp_path / "BTCUSDT.csv").write_text(
        "open_time_ms,open_time,open,high,low,close,volume,quote_volume\n"
        "1640995200000,2022-01-01 00:00:00+00:00,1,1,1,1,1,1\n",
        encoding="utf-8",
    )
    (tmp_path / "coverage.json").write_text(
        json.dumps(
            {
                "bitcoin": {
                    "available": True,
                    "file": "BTCUSDT.csv",
                    "rows": 1,
                    "first": "2022-01-01T00:00:00+00:00",
                    "last": "2022-01-01T00:00:00+00:00",
                }
            }
        ),
        encoding="utf-8",
    )
    frame = tmp_path / "BTCUSDT.csv"
    text = frame.read_text(encoding="utf-8").replace("1640995200000", "1640995200")
    frame.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="milliseconds"):
        load_30m_bars(tmp_path)


def test_split_execution_combines_equal_capital_equity_not_daily_return_average() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")

    def result(name: str, equity: list[float]) -> BacktestResult:
        equity_series = pd.Series(equity, index=index, name=name, dtype=float)
        returns = equity_series.pct_change().fillna(0.0)
        return BacktestResult(
            name=name,
            daily_returns=returns,
            equity_curve=equity_series,
            drawdown=equity_series / equity_series.cummax() - 1.0,
            weights=pd.DataFrame(0.0, index=index, columns=["bitcoin"]),
            turnover=pd.Series(0.0, index=index),
            holdings_count=pd.Series(0, index=index),
            sector_exposure=pd.DataFrame(0.0, index=index, columns=["Other"]),
            rebalance_targets=pd.DataFrame(),
        )

    returns, equity = _combine_half_sleeves(
        result("first", [1.0, 1.1, 1.2]),
        result("second", [1.0, 0.9, 1.0]),
    )

    assert equity.tolist() == pytest.approx([1.0, 1.0, 1.1])
    assert returns.tolist() == pytest.approx([0.0, 0.0, 0.1])
