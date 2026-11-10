from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.diagnose_intraday_risk import (
    HourlyRiskOverlay,
    build_hourly_return_panel,
    run_hourly_simulation,
)


def _one_asset_returns(days: pd.DatetimeIndex, values: dict[tuple[str, int], float] | None = None) -> pd.DataFrame:
    hours = pd.DatetimeIndex(
        [
            pd.Timestamp(day, tz="UTC") + pd.Timedelta(hours=hour)
            for day in days
            for hour in range(24)
        ]
    )
    returns = pd.DataFrame({"A": 0.0}, index=hours)
    for (day, hour), value in (values or {}).items():
        returns.at[pd.Timestamp(day, tz="UTC") + pd.Timedelta(hours=hour), "A"] = value
    return returns


def test_baseline_hourly_simulation_executes_previous_day_target_at_one_utc() -> None:
    days = pd.DatetimeIndex(["2026-01-02"])
    hourly_returns = _one_asset_returns(days)
    targets = pd.DataFrame(
        {"A": [0.5]},
        index=pd.DatetimeIndex(["2026-01-01"]),
    )
    above_sma = pd.Series(True, index=hourly_returns.index)

    result = run_hourly_simulation(
        targets,
        hourly_returns,
        above_sma,
        days,
        cost_bps=20.0,
        overlay=HourlyRiskOverlay("baseline"),
    )

    assert result.daily_returns.iloc[0] == pytest.approx(-0.001)
    assert result.events.iloc[0]["timestamp"] == pd.Timestamp("2026-01-02T01:00:00Z")
    assert result.events.iloc[0]["reason"] == "rebalance"


def test_roundtrip_hourly_gate_executes_two_below_closes_on_the_next_hour() -> None:
    days = pd.DatetimeIndex(["2026-01-02"])
    hourly_returns = _one_asset_returns(days)
    targets = pd.DataFrame(
        {"A": [1.0]},
        index=pd.DatetimeIndex(["2026-01-01"]),
    )
    above_sma = pd.Series(True, index=hourly_returns.index)
    for hour in (2, 3):
        above_sma.at[pd.Timestamp("2026-01-02T00:00:00Z") + pd.Timedelta(hours=hour)] = False

    result = run_hourly_simulation(
        targets,
        hourly_returns,
        above_sma,
        days,
        cost_bps=20.0,
        overlay=HourlyRiskOverlay("fast_gate_roundtrip"),
    )

    exits = result.events[result.events["reason"] == "gate_off"]
    assert len(exits) == 1
    assert exits.iloc[0]["timestamp"] == pd.Timestamp("2026-01-02T04:00:00Z")


def test_roundtrip_hourly_gate_reenters_after_two_above_closes() -> None:
    days = pd.DatetimeIndex(["2026-01-02"])
    hourly_returns = _one_asset_returns(days)
    targets = pd.DataFrame(
        {"A": [1.0]},
        index=pd.DatetimeIndex(["2026-01-01"]),
    )
    above_sma = pd.Series(True, index=hourly_returns.index)
    for hour in (2, 3, 4, 5, 7):
        above_sma.at[pd.Timestamp("2026-01-02T00:00:00Z") + pd.Timedelta(hours=hour)] = False
    for hour in (8, 9):
        above_sma.at[pd.Timestamp("2026-01-02T00:00:00Z") + pd.Timedelta(hours=hour)] = True

    result = run_hourly_simulation(
        targets,
        hourly_returns,
        above_sma,
        days,
        cost_bps=20.0,
        overlay=HourlyRiskOverlay("fast_gate_roundtrip"),
    )

    entries = result.events[result.events["reason"] == "gate_on"]
    assert len(entries) == 1
    assert entries.iloc[0]["timestamp"] == pd.Timestamp("2026-01-02T10:00:00Z")


def test_fast_exit_slow_reentry_waits_for_the_next_target_event() -> None:
    days = pd.DatetimeIndex(["2026-01-02", "2026-01-03"])
    hourly_returns = _one_asset_returns(days)
    targets = pd.DataFrame(
        {"A": [1.0, 1.0]},
        index=pd.DatetimeIndex(["2026-01-01", "2026-01-02"]),
    )
    above_sma = pd.Series(True, index=hourly_returns.index)
    for hour in (2, 3):
        above_sma.at[pd.Timestamp("2026-01-02T00:00:00Z") + pd.Timedelta(hours=hour)] = False
    for hour in range(6, 20):
        above_sma.at[pd.Timestamp("2026-01-02T00:00:00Z") + pd.Timedelta(hours=hour)] = True

    result = run_hourly_simulation(
        targets,
        hourly_returns,
        above_sma,
        days,
        cost_bps=20.0,
        overlay=HourlyRiskOverlay("fast_gate_slow_reentry"),
    )

    entries = result.events[result.events["reason"] == "target_reentry"]
    assert len(entries) == 1
    assert entries.iloc[0]["timestamp"] == pd.Timestamp("2026-01-03T01:00:00Z")


def test_fixed_stop_de_risks_after_the_threshold_and_waits_for_next_target() -> None:
    days = pd.DatetimeIndex(["2026-01-02"])
    hourly_returns = _one_asset_returns(
        days,
        {("2026-01-02", 2): -0.10},
    )
    targets = pd.DataFrame(
        {"A": [1.0]},
        index=pd.DatetimeIndex(["2026-01-01"]),
    )
    above_sma = pd.Series(True, index=hourly_returns.index)

    result = run_hourly_simulation(
        targets,
        hourly_returns,
        above_sma,
        days,
        cost_bps=20.0,
        overlay=HourlyRiskOverlay("fixed_stop", threshold=0.05),
    )

    exits = result.events[result.events["reason"] == "fixed_stop_off"]
    assert len(exits) == 1
    assert exits.iloc[0]["timestamp"] == pd.Timestamp("2026-01-02T03:00:00Z")


def test_fixed_stop_reenters_at_the_next_scheduled_target_event() -> None:
    days = pd.DatetimeIndex(["2026-01-02", "2026-01-03"])
    hourly_returns = _one_asset_returns(
        days,
        {("2026-01-02", 2): -0.10},
    )
    targets = pd.DataFrame(
        {"A": [1.0, 1.0]},
        index=pd.DatetimeIndex(["2026-01-01", "2026-01-02"]),
    )
    above_sma = pd.Series(True, index=hourly_returns.index)

    result = run_hourly_simulation(
        targets,
        hourly_returns,
        above_sma,
        days,
        cost_bps=20.0,
        overlay=HourlyRiskOverlay("fixed_stop", threshold=0.05),
    )

    entries = result.events[result.events["reason"] == "target_reentry"]
    assert len(entries) == 1
    assert entries.iloc[0]["timestamp"] == pd.Timestamp("2026-01-03T01:00:00Z")


def test_missing_hourly_asset_uses_geometric_interpolation_of_its_daily_return() -> None:
    days = pd.DatetimeIndex(["2026-01-02"])
    daily_returns = pd.DataFrame({"A": [0.10]}, index=days)
    hourly_returns = pd.DataFrame(
        1.0,
        index=pd.date_range("2026-01-02", periods=24, freq="h", tz="UTC"),
        columns=["A"],
    )
    hourly_returns.iloc[0] = np.nan

    panel, observed = build_hourly_return_panel(
        daily_returns,
        hourly_returns,
        days,
    )

    assert not bool(observed.at[pd.Timestamp(days[0], tz="UTC"), "A"])
    assert float((1.0 + panel["A"]).prod() - 1.0) == pytest.approx(0.10)


def test_coverage_mask_keeps_one_row_per_input_day() -> None:
    days = pd.DatetimeIndex(["2026-01-02", "2026-01-03"])
    daily_returns = pd.DataFrame({"A": [0.10, -0.05]}, index=days)
    hourly_returns = pd.DataFrame(
        np.nan,
        index=pd.date_range("2026-01-02", periods=48, freq="h", tz="UTC"),
        columns=["A"],
    )

    _, observed = build_hourly_return_panel(daily_returns, hourly_returns, days)

    assert observed.shape == (2, 1)
    assert observed.index.is_unique


def test_observed_hourly_day_does_not_append_a_second_coverage_row() -> None:
    days = pd.DatetimeIndex(["2026-01-02", "2026-01-03"])
    daily_returns = pd.DataFrame({"A": [0.10, -0.05]}, index=days)
    hourly_returns = pd.DataFrame(
        0.0,
        index=pd.date_range("2026-01-02", periods=48, freq="h", tz="UTC"),
        columns=["A"],
    )
    hourly_returns.iloc[24:] = np.nan

    _, observed = build_hourly_return_panel(daily_returns, hourly_returns, days)

    assert observed.shape == (2, 1)
    assert observed.index.is_unique
    assert bool(observed.iloc[0, 0])
    assert not bool(observed.iloc[1, 0])
