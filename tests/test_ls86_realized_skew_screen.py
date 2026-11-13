from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _synthetic_skew_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    assets = ["a", "b", "c", "d", "e", "f", "g", "h"]
    days = pd.date_range("2022-01-01", periods=40, freq="1D", tz="UTC")
    returns = pd.DataFrame(0.0, index=days, columns=assets)
    returns.loc[days[:-1], ["a", "b"]] = 0.01
    returns.loc[days[-1], ["a", "b"]] = -0.20
    returns.loc[days[:-1], ["g", "h"]] = -0.01
    returns.loc[days[-1], ["g", "h"]] = 0.20
    daily_close = 100.0 * (1.0 + returns).cumprod()

    hours = pd.date_range("2022-01-01", "2022-02-20", freq="1h", tz="UTC")
    hourly = pd.DataFrame(100.0, index=hours, columns=assets)
    signal = days[-1]
    entry = signal + pd.Timedelta(days=1, hours=3)
    exit_time = entry + pd.Timedelta(days=7)
    hourly.loc[hourly.index >= exit_time, ["a", "b"]] = 102.0
    hourly.loc[hourly.index >= exit_time, ["g", "h"]] = 98.0
    return hourly, daily_close


def test_realized_skew_screen_selects_low_and_high_skew() -> None:
    from scripts.run_ls86_realized_skew_screen import build_realized_skew_events

    hourly, daily_close = _synthetic_skew_inputs()
    events = build_realized_skew_events(
        hourly_prices=hourly,
        daily_close=daily_close,
        assets=list(daily_close.columns),
        rebalance_days=1,
        lookback_days=30,
        horizon_days=7,
    )

    row = events.loc[events["signal_date"] == daily_close.index[-1]].iloc[0]
    assert row["long_assets"] == "a,b"
    assert row["short_assets"] == "g,h"
    assert row["spread_7d"] == pytest.approx(0.04)


def test_realized_skew_screen_skips_missing_exit() -> None:
    from scripts.run_ls86_realized_skew_screen import build_realized_skew_events

    hourly, daily_close = _synthetic_skew_inputs()
    signal = daily_close.index[-1]
    entry = signal + pd.Timedelta(days=1, hours=3)
    hourly = hourly.drop(entry + pd.Timedelta(days=7))
    events = build_realized_skew_events(
        hourly_prices=hourly,
        daily_close=daily_close,
        assets=list(daily_close.columns),
        rebalance_days=1,
        lookback_days=30,
        horizon_days=7,
    )
    assert not events.empty
    assert signal not in set(events["signal_date"])


def test_realized_skew_placebo_is_finite() -> None:
    from scripts.run_ls86_realized_skew_screen import placebo_skew_reversal

    assets = ["a", "b", "c", "d"]
    events = pd.DataFrame(
        [
            {
                "ret_a_7d": 0.05,
                "ret_b_7d": 0.04,
                "ret_c_7d": -0.04,
                "ret_d_7d": -0.05,
            }
        ]
    )
    simulated = placebo_skew_reversal(events, assets=assets, horizon=7, iterations=20, seed=2)
    assert len(simulated) == 20
    assert np.isfinite(simulated).all()
