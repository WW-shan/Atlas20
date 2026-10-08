"""Tests for the rebalance calendar in ``atlas20.backtest.calendar``."""

from __future__ import annotations

import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates


def test_month_end_skips_the_last_date_of_an_unfinished_month() -> None:
    """Only a calendar month end is a month-end rebalance.

    The last date of each month in the index used to count, so a panel ending
    2026-09-22 rebalanced on 09-22 as if September had closed (and the date
    moved every day the panel grew).
    """
    index = pd.date_range("2026-07-15", "2026-09-22", freq="D")

    dates = get_rebalance_dates(index, pd.Timestamp("2026-07-15"), "monthly", "month_end")

    assert dates == [pd.Timestamp("2026-07-31"), pd.Timestamp("2026-08-31")]


def test_month_end_keeps_a_month_that_closes_on_the_last_index_date() -> None:
    index = pd.date_range("2026-07-15", "2026-08-31", freq="D")

    dates = get_rebalance_dates(index, pd.Timestamp("2026-07-15"), "monthly", "month_end")

    assert dates == [pd.Timestamp("2026-07-31"), pd.Timestamp("2026-08-31")]
