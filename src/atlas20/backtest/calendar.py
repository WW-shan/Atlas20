"""Rebalance calendar helpers."""

from __future__ import annotations

import pandas as pd


def get_rebalance_dates(index: pd.DatetimeIndex, start_date: pd.Timestamp, frequency_name: str, frequency_value: str) -> list[pd.Timestamp]:
    """Generate rebalance dates aligned to the available daily index."""
    usable_index = index[index >= pd.Timestamp(start_date)]
    if usable_index.empty:
        return []

    if frequency_value == "month_end":
        # Only a calendar month end counts. Taking each month's last index date
        # made the final date of an unfinished month (a panel ending 2026-09-22)
        # a rebalance, and that date moved every day the panel grew.
        return [pd.Timestamp(value) for value in usable_index[usable_index.is_month_end]]

    if frequency_name == "biweekly" or frequency_value.endswith("D"):
        days = int(frequency_value.replace("D", ""))
        schedule = pd.date_range(usable_index.min(), usable_index.max(), freq=f"{days}D")
        return [pd.Timestamp(value) for value in schedule if value in usable_index]

    raise ValueError(f"Unsupported rebalance frequency: {frequency_name}={frequency_value}")
