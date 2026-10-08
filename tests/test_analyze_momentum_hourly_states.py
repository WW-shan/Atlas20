from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_momentum_hourly_states import (
    HOURLY_STATE_COLUMNS,
    _coverage_table,
    _cross_section,
    _hourly_daily_frame,
    monthly_frame,
)


def _bars(hours: int = 48, *, start: str = "2024-01-01 00:00") -> pd.DataFrame:
    open_time = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    hourly = open_time.hour
    step = np.where(hourly < 8, 0.01, -0.01)
    close = 100.0 * np.exp(np.cumsum(step))
    quote_volume = np.full(hours, 1.0)
    if hours >= 48:
        quote_volume[29] = 11.0  # hour 5 of the second day
    return pd.DataFrame(
        {
            "open_time": open_time,
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": 1.0,
            "quote_volume": quote_volume,
        }
    )


def test_hourly_daily_frame_aggregates_the_day_it_belongs_to() -> None:
    daily = _hourly_daily_frame(_bars())

    assert list(daily.index) == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-02"),
    ]
    # 24 hourly returns of +-1%; the first bar of the sample has no return.
    assert daily.loc["2024-01-02", "realized_variance"] == pytest.approx(24 * 0.0001)
    assert daily.loc["2024-01-02", "down_share"] == pytest.approx(16 / 24)
    assert daily.loc["2024-01-02", "night_minus_day"] == pytest.approx(0.08 + 0.16)
    # The largest hour carries 11 of the day's 34 traded units (23 hours of 1).
    assert daily.loc["2024-01-02", "hour_share"] == pytest.approx(11.0 / 34.0)
    assert daily.loc["2024-01-02", "hours"] == 24


def test_hourly_daily_frame_drops_a_partial_day() -> None:
    bars = pd.concat([_bars(48), _bars(5, start="2024-01-03 00:00")], ignore_index=True)

    daily = _hourly_daily_frame(bars)

    assert pd.Timestamp("2024-01-03") not in daily.index


def test_cross_section_needs_the_minimum_number_of_members() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    members = [f"coin{number}" for number in range(1, 7)]
    wide = pd.DataFrame(
        {coin: [float(number), np.nan] for number, coin in enumerate(members, start=1)},
        index=index,
    )
    wide.loc[index[1], "coin1"] = 1.0
    values = _cross_section(wide, {index[0]: members, index[1]: members}, index)

    assert values.loc[index[0]] == pytest.approx(3.5)
    # Only one member has a reading on day two, below the five-member floor.
    assert np.isnan(values.loc[index[1]])


def test_monthly_frame_reads_hourly_states_before_the_month() -> None:
    index = pd.date_range("2024-01-01", periods=90, freq="D")
    port = pd.Series(0.001, index=index)
    btc = pd.Series(0.002, index=index)
    hourly = pd.DataFrame(0.0, index=index, columns=HOURLY_STATE_COLUMNS)
    hourly.loc["2024-02-15", "rv_ratio"] = 7.0
    legacy = pd.DataFrame(
        {
            "gate_open": 1.0,
            "breadth": 0.5,
            "disp_ratio": 1.0,
            "mkt_vol": 0.6,
            "own63_before": 0.1,
            "gross": 0.3,
        },
        index=index,
    )

    monthly = monthly_frame(port, btc, hourly, legacy)

    # March carries 0.0: February's mid-month spike is not read, only the last
    # close before the month starts.
    assert monthly.loc["2024-03-31", "rv_ratio"] == pytest.approx(0.0)
    assert monthly["excess"].iloc[-1] < 0
    assert "gate_open_before" in monthly.columns


def test_coverage_table_counts_member_days() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    universe = pd.DataFrame(
        {
            "rebalance_date": [index[0]] * 2 + [index[1]] * 2,
            "coin_id": ["coin1", "coin2", "coin1", "coin2"],
        }
    )
    hourly = {"coin1": _bars()}

    coverage = _coverage_table(hourly, universe, index)

    values = dict(zip(coverage["metric"], coverage["value"], strict=True))
    assert values["hourly pairs loaded"] == 1.0
    assert values["members without hourly data"] == 1.0
    assert values["member-days observed"] == 2.0
    assert values["member-day coverage"] == pytest.approx(0.5)
