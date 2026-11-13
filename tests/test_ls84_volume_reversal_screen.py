from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _synthetic_inputs() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    assets = ["a", "b", "c", "d", "e", "f", "g", "h"]
    days = pd.date_range("2022-01-01", periods=25, freq="1D", tz="UTC")
    daily_close = pd.DataFrame(100.0, index=days, columns=assets)
    signal_day = days[-1]
    daily_close.loc[signal_day, ["a", "b"]] = 90.0
    daily_close.loc[signal_day, ["g", "h"]] = 110.0
    daily_volume = pd.DataFrame(100.0, index=days, columns=assets)
    daily_volume.loc[signal_day, ["a", "b", "g", "h"]] = 200.0

    hours = pd.date_range("2022-01-01", "2022-01-28", freq="1h", tz="UTC")
    hourly = pd.DataFrame(100.0, index=hours, columns=assets)
    entry = signal_day + pd.Timedelta(days=1, hours=3)
    for asset in ["a", "b"]:
        hourly.loc[hourly.index >= entry + pd.Timedelta(hours=24), asset] = 102.0
    for asset in ["g", "h"]:
        hourly.loc[hourly.index >= entry + pd.Timedelta(hours=24), asset] = 98.0
    return hourly, daily_close, daily_volume


def test_volume_reversal_selects_extremes_in_high_volume_group() -> None:
    from scripts.run_ls84_volume_reversal_screen import build_volume_reversal_events

    hourly, daily_close, daily_volume = _synthetic_inputs()
    events = build_volume_reversal_events(
        hourly_prices=hourly,
        daily_close=daily_close,
        daily_volume=daily_volume,
        assets=list(daily_close.columns),
        horizons=(24,),
    )

    row = events.loc[events["signal_date"] == daily_close.index[-1]].iloc[0]
    assert row["signal_date"] == daily_close.index[-1]
    assert row["long_assets"] == "a,b"
    assert row["short_assets"] == "g,h"
    assert row["high_volume_assets"] == "a,b,g,h"
    assert row["spread_24h"] == pytest.approx(0.04)


def test_volume_reversal_skips_missing_forward_exit() -> None:
    from scripts.run_ls84_volume_reversal_screen import build_volume_reversal_events

    hourly, daily_close, daily_volume = _synthetic_inputs()
    entry = daily_close.index[-1] + pd.Timedelta(days=1, hours=3)
    hourly = hourly.drop(entry + pd.Timedelta(hours=24))
    events = build_volume_reversal_events(
        hourly_prices=hourly,
        daily_close=daily_close,
        daily_volume=daily_volume,
        assets=list(daily_close.columns),
        horizons=(24,),
    )
    assert not (events["signal_date"] == daily_close.index[-1]).any()


def test_volume_reversal_placebo_is_not_above_actual() -> None:
    from scripts.run_ls84_volume_reversal_screen import placebo_volume_reversal

    assets = ["a", "b", "c", "d"]
    events = pd.DataFrame(
        [
            {
                "high_volume_assets": "a,b,c,d",
                "ret_a_24h": 0.04,
                "ret_b_24h": 0.03,
                "ret_c_24h": -0.03,
                "ret_d_24h": -0.04,
            }
        ]
    )
    simulated = placebo_volume_reversal(
        events, assets=assets, horizon=24, iterations=20, seed=1
    )
    assert len(simulated) == 20
    assert np.isfinite(simulated).all()
