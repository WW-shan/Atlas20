from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_momentum_chase_risk import (
    bucket_table,
    daily_frame,
    extreme_vs_rest,
    forward_frame,
)


@dataclass
class _Market:
    price: pd.DataFrame
    returns: pd.DataFrame


def test_forward_frame_compounds_and_measures_drawdown() -> None:
    index = pd.date_range("2024-01-01", periods=30, freq="D")
    daily = pd.Series(0.01, index=index)

    frame = forward_frame(daily)

    assert frame["forward_5d"].iloc[0] == pytest.approx(1.01**5 - 1.0)
    assert np.isnan(frame["forward_5d"].iloc[-1])
    assert frame["forward_21d_mdd"].iloc[0] == pytest.approx(0.0)


def test_forward_frame_records_a_loss_inside_the_window() -> None:
    index = pd.date_range("2024-01-01", periods=30, freq="D")
    daily = pd.Series(0.01, index=index)
    daily.iloc[3] = -0.20

    frame = forward_frame(daily)

    assert frame["forward_21d_mdd"].iloc[0] < -0.15


def test_daily_frame_reads_the_largest_holding_and_its_run() -> None:
    index = pd.date_range("2024-01-01", periods=60, freq="D")
    price = pd.DataFrame(
        {
            "alpha": np.linspace(1.0, 3.0, 60),
            "beta": np.linspace(1.0, 1.1, 60),
        },
        index=index,
    )
    weights = pd.DataFrame({"alpha": 0.0, "beta": 0.0}, index=index)
    weights.loc[index[40]:, "alpha"] = 0.5
    weights.loc[index[30]:index[39], "beta"] = 0.4
    daily = pd.Series(0.001, index=index)

    frame = daily_frame(_Market(price=price, returns=price.pct_change().fillna(0.0)), weights, daily)

    assert len(frame) == 30  # only invested days
    assert frame["largest_coin"].iloc[0] == "beta"
    assert frame["largest_coin"].iloc[-1] == "alpha"
    # alpha roughly triples over the sample, so its trailing 21-day run is large.
    assert frame["largest_trailing_21d"].iloc[-1] > 0.2
    # The forward window mixes the 0.4 beta days and the 0.5 alpha days.
    assert 0.4 <= frame["forward_gross"].iloc[0] <= 0.5


def test_bucket_table_orders_by_the_chased_run() -> None:
    index = pd.date_range("2024-01-01", periods=100, freq="D")
    frame = pd.DataFrame(
        {
            "largest_trailing_21d": np.linspace(0.0, 1.0, 100),
            "forward_5d": np.linspace(0.05, -0.05, 100),
            "forward_10d": np.linspace(0.05, -0.05, 100),
            "forward_21d": np.linspace(0.05, -0.05, 100),
            "forward_21d_mdd": -0.1,
        },
        index=index,
    )

    buckets = bucket_table(frame, buckets=4)

    assert list(buckets["bucket"]) == [1, 2, 3, 4]
    assert buckets["state_median"].is_monotonic_increasing
    assert buckets["mean_forward_21d"].is_monotonic_decreasing


def test_extreme_vs_rest_finds_the_weaker_edge_and_normalises_by_gross() -> None:
    index = pd.date_range("2024-01-01", periods=100, freq="D")
    trailing = np.linspace(0.0, 1.0, 100)
    # The most chased days earn nothing; everything else earns 2% a day.
    forward = np.where(trailing >= 0.8, 0.0, 0.02)
    frame = pd.DataFrame(
        {
            "largest_trailing_21d": trailing,
            "forward_5d": forward,
            "forward_10d": forward,
            "forward_21d": forward,
            "forward_21d_mdd": -0.05,
            "forward_gross": 0.5,
        },
        index=index,
    )

    table, threshold = extreme_vs_rest(frame, quantile=0.8)

    assert threshold == pytest.approx(0.8, abs=1e-9)
    row = table[table["horizon_days"] == 21].iloc[0]
    assert row["difference"] == pytest.approx(-0.02)
    # Per unit of gross the gap shrinks by the exposure, but keeps its sign.
    assert row["difference_per_gross"] == pytest.approx(-0.04)
    assert row["welch_t_per_gross"] < 0
