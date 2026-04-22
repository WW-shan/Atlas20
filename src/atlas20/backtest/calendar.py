"""Rebalance calendar helpers."""

from __future__ import annotations

import pandas as pd


def get_rebalance_dates(index: pd.DatetimeIndex, start_date: pd.Timestamp, frequency_name: str, frequency_value: str) -> list[pd.Timestamp]:
    """Generate rebalance dates aligned to the available daily index."""
    usable_index = index[index >= pd.Timestamp(start_date)]
    if usable_index.empty:
        return []

    if frequency_value == "month_end":
        month_ends = usable_index.to_series().groupby(usable_index.to_period("M")).max().tolist()
        return [pd.Timestamp(value) for value in month_ends]

    if frequency_name == "biweekly" or frequency_value.endswith("D"):
        days = int(frequency_value.replace("D", ""))
        schedule = pd.date_range(usable_index.min(), usable_index.max(), freq=f"{days}D")
        return [pd.Timestamp(value) for value in schedule if value in usable_index]

    raise ValueError(f"Unsupported rebalance frequency: {frequency_name}={frequency_value}")
