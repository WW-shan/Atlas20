"""Tests for the research-backed risk overlays in ``atlas20.signals.risk``."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas20.signals.risk import (
    absolute_trend_mask,
    btc_above_moving_average,
    btc_above_trailing_price,
    btc_above_volatility_scaled_trailing,
    realized_volatility,
    volatility_target_leverage,
)


def test_btc_ma_gate_is_open_in_warm_up_but_closed_on_a_later_gap() -> None:
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    btc = [100.0, 101.0, 102.0, 103.0, float("nan"), 105.0, 106.0, 107.0]
    price = pd.DataFrame({"bitcoin": btc}, index=dates)

    risk_on = btc_above_moving_average(price, ma_window=3, confirm_days=1)

    assert risk_on.iloc[:4].tolist() == [True, True, True, True]
    # The gap blanks the moving average for a full window: that is missing
    # data, not a warm-up, so the gate must not stay open.
    assert risk_on.iloc[4:7].tolist() == [False, False, False]
    assert bool(risk_on.iloc[7]) is True


def test_btc_trailing_gate_fails_closed_on_a_gap_after_warm_up() -> None:
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    btc = [100.0, 101.0, 102.0, float("nan"), 104.0, 105.0]
    price = pd.DataFrame({"bitcoin": btc}, index=dates)

    risk_on = btc_above_trailing_price(price, lookback_days=1, confirm_days=1)

    assert risk_on.iloc[:3].tolist() == [True, True, True]
    assert risk_on.iloc[3:5].tolist() == [False, False]
    assert bool(risk_on.iloc[5]) is True


def test_chandelier_gate_fails_closed_on_a_gap_after_warm_up() -> None:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    btc = [100.0, 101.0, 102.0, 103.0, 104.0, float("nan"), 106.0, 107.0, 108.0, 109.0]
    price = pd.DataFrame({"bitcoin": btc}, index=dates)

    risk_on = btc_above_volatility_scaled_trailing(
        price, lookback=2, vol_window=2, vol_multiple=1.0, confirm_days=1
    )

    assert bool(risk_on.iloc[0]) is True
    assert not risk_on.iloc[5:8].any()


def test_chandelier_stop_exits_after_a_deep_break_from_the_high() -> None:
    calm = [100.0 + (i % 3) - 1.0 for i in range(100)]
    crash = [95.0, 90.0, 85.0, 80.0, 70.0, 60.0, 50.0]
    dates = pd.date_range("2024-01-01", periods=len(calm) + len(crash), freq="D")
    price = pd.DataFrame({"bitcoin": calm + crash}, index=dates)

    risk_on = btc_above_volatility_scaled_trailing(
        price, lookback=30, vol_window=30, vol_multiple=1.0, confirm_days=1
    )

    assert bool(risk_on.iloc[95]) is True
    assert bool(risk_on.iloc[-1]) is False


def test_realized_volatility_tracks_turbulence() -> None:
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    quiet = pd.Series(100.0, index=dates[:60])
    choppy = pd.Series(
        100.0 * np.cumprod(1.0 + np.tile([0.05, -0.05], 30)), index=dates[60:]
    )
    volatile_price = pd.DataFrame({"bitcoin": pd.concat([quiet, choppy])})
    calm_price = pd.DataFrame({"bitcoin": pd.Series(100.0, index=dates)})

    vol = float(realized_volatility(volatile_price, 30).iloc[-1, 0])
    calm_vol = float(realized_volatility(calm_price, 30).iloc[-1, 0])

    assert vol > 0.5
    assert calm_vol == pytest.approx(0.0, abs=1e-9)


def test_realized_volatility_is_annualised() -> None:
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    daily = np.tile([0.02, -0.02], 45)
    price = pd.DataFrame({"bitcoin": 100.0 * np.cumprod(1.0 + daily)}, index=dates)

    vol = float(realized_volatility(price, 30).iloc[-1, 0])

    # 2% daily -> ~2% * sqrt(365) annualised.
    assert vol == pytest.approx(0.02 * (365 ** 0.5), rel=0.15)


def test_volatility_target_leverage_respects_bounds_and_scales_inversely() -> None:
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    quiet = np.tile([0.002, -0.002], 60)
    wild = np.tile([0.08, -0.08], 60)
    price = pd.DataFrame(
        {"quiet": 100.0 * np.cumprod(1.0 + quiet), "wild": 100.0 * np.cumprod(1.0 + wild)},
        index=dates,
    )

    leverage = volatility_target_leverage(price, target_volatility=0.40, window=30, max_leverage=1.5)

    assert float(leverage.max().max()) <= 1.5
    assert float(leverage.min().min()) >= 0.0
    # The calm asset is levered up; the wild one is cut back.
    assert leverage.loc[dates[-1], "quiet"] > leverage.loc[dates[-1], "wild"]


def test_volatility_target_leverage_is_flat_not_full_on_a_gap_after_warm_up() -> None:
    """Only the warm-up falls back to full exposure.

    A provider gap longer than the 3-day carry leaves one missing price, which
    blanks the rolling std for a whole window. The fallback used to apply
    there too, so a ~115% vol asset targeted at 0.5 went from ~0.43 to 1.0
    for a month right after the gap.
    """
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    wild = pd.Series(100.0 * np.cumprod(1.0 + np.tile([0.06, -0.06], 60)), index=dates)
    wild.iloc[60:64] = np.nan
    price = wild.ffill(limit=3).to_frame("wild")

    leverage = volatility_target_leverage(price, target_volatility=0.5, window=30)["wild"]

    assert leverage.iloc[:30].tolist() == [1.0] * 30
    assert leverage.iloc[30:63].between(0.40, 0.46).all()
    undefined_after_warm_up = leverage.iloc[63:94]
    assert undefined_after_warm_up.tolist() == [0.0] * 31
    assert leverage.iloc[94:].between(0.40, 0.46).all()


def test_absolute_trend_mask_requires_price_above_own_average() -> None:
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    up = pd.Series(np.linspace(100.0, 200.0, 40), index=dates)
    down = pd.Series(np.linspace(200.0, 100.0, 40), index=dates)

    mask = absolute_trend_mask(pd.DataFrame({"up": up, "down": down}), ma_window=20)

    assert bool(mask.loc[dates[-1], "up"]) is True
    assert bool(mask.loc[dates[-1], "down"]) is False
    # Warm-up rows are explicitly False rather than silently True.
    assert bool(mask.loc[dates[0], "up"]) is False
