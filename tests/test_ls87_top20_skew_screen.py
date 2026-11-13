from __future__ import annotations

import pandas as pd
import pytest


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assets = ["a", "b", "c", "d", "e", "f", "g", "h"]
    days = pd.date_range("2022-01-01", periods=40, freq="1D", tz="UTC")
    returns = pd.DataFrame(0.0, index=days, columns=assets)
    returns.loc[days[:-1], ["a", "b"]] = 0.01
    returns.loc[days[-1], ["a", "b"]] = -0.20
    returns.loc[days[:-1], ["g", "h"]] = -0.01
    returns.loc[days[-1], ["g", "h"]] = 0.20
    daily_close = 100.0 * (1.0 + returns).cumprod()
    present = pd.DataFrame(True, index=days, columns=assets)

    hours = pd.date_range("2022-01-01", "2022-02-20", freq="1h", tz="UTC")
    hourly = pd.DataFrame(100.0, index=hours, columns=assets)
    signal = days[-1]
    entry = signal + pd.Timedelta(days=1, hours=3)
    exit_time = entry + pd.Timedelta(days=7)
    hourly.loc[hourly.index >= exit_time, ["a", "b"]] = 102.0
    hourly.loc[hourly.index >= exit_time, ["g", "h"]] = 98.0
    return daily_close, present, hourly


def test_pit_top20_skew_selects_eligible_extremes() -> None:
    from scripts.run_ls87_top20_skew_screen import build_pit_top20_skew_events

    daily_close, present, hourly = _inputs()
    events = build_pit_top20_skew_events(
        price=daily_close,
        present=present,
        hourly_prices=hourly,
        assets=list(daily_close.columns),
        rebalance_days=1,
        lookback_days=30,
        horizon_days=7,
    )

    row = events.loc[events["signal_date"] == daily_close.index[-1]].iloc[0]
    assert row["long_assets"] == "a,b"
    assert row["short_assets"] == "g,h"
    assert row["spread_7d"] == pytest.approx(0.04)


def test_pit_top20_skew_respects_membership_mask() -> None:
    from scripts.run_ls87_top20_skew_screen import build_pit_top20_skew_events

    daily_close, present, hourly = _inputs()
    signal = daily_close.index[-1]
    present.loc[signal, ["g", "h"]] = False
    events = build_pit_top20_skew_events(
        price=daily_close,
        present=present,
        hourly_prices=hourly,
        assets=list(daily_close.columns),
        rebalance_days=1,
        lookback_days=30,
        horizon_days=7,
    )
    row = events.loc[events["signal_date"] == signal].iloc[0]
    assert "g" not in row["long_assets"].split(",")
    assert "g" not in row["short_assets"].split(",")
    assert "h" not in row["short_assets"].split(",")


def test_pit_top20_skew_requires_six_eligible_assets() -> None:
    from scripts.run_ls87_top20_skew_screen import build_pit_top20_skew_events

    daily_close, present, hourly = _inputs()
    present.loc[daily_close.index[-1], ["c", "d", "e", "f", "g", "h"]] = False
    events = build_pit_top20_skew_events(
        price=daily_close,
        present=present,
        hourly_prices=hourly,
        assets=list(daily_close.columns),
        rebalance_days=1,
        lookback_days=30,
        horizon_days=7,
    )
    assert not events.empty
    assert daily_close.index[-1] not in set(events["signal_date"])
