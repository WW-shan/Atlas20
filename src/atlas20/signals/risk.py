"""Daily risk-overlay signal builders."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RiskOverlayDefinition:
    """Definition for one daily risk-off overlay."""

    name: str
    description: str



def _confirmed_state(raw_signal: pd.Series, confirm_days: int) -> pd.Series:
    """Require a signal change to persist for N consecutive days before flipping state."""
    cleaned = raw_signal.fillna(True).astype(bool)
    if confirm_days <= 1:
        return cleaned

    values = cleaned.tolist()
    state = values[0] if values else True
    pending_state = state
    streak = 0
    result: list[bool] = []

    for raw in values:
        if raw == state:
            pending_state = state
            streak = 0
        else:
            if raw != pending_state:
                pending_state = raw
                streak = 1
            else:
                streak += 1
            if streak >= confirm_days:
                state = raw
                pending_state = state
                streak = 0
        result.append(state)

    return pd.Series(result, index=cleaned.index, name=cleaned.name)



def btc_above_trailing_price(price: pd.DataFrame, lookback_days: int, confirm_days: int = 1) -> pd.Series:
    """Risk-on when BTC is at or above its trailing price level."""
    btc = price['bitcoin']
    reference = btc.shift(lookback_days)
    raw = (btc >= reference).where(reference.notna(), True)
    return _confirmed_state(raw, confirm_days).rename(f'btc_ge_{lookback_days}d_ago')



def btc_above_moving_average(price: pd.DataFrame, ma_window: int, confirm_days: int = 1) -> pd.Series:
    """Risk-on when BTC is at or above a moving average."""
    btc = price['bitcoin']
    ma = btc.rolling(ma_window, min_periods=ma_window).mean()
    raw = (btc >= ma).where(ma.notna(), True)
    return _confirmed_state(raw, confirm_days).rename(f'btc_ge_ma_{ma_window}')



def build_default_risk_overlays(price: pd.DataFrame) -> dict[str, tuple[RiskOverlayDefinition, pd.Series]]:
    """Return the baseline stop-loss overlay candidates for the study."""
    return {
        'NO_STOP': (
            RiskOverlayDefinition(name='NO_STOP', description='No additional stop-loss overlay.'),
            pd.Series(True, index=price.index, name='no_stop'),
        ),
        'BTC_LT_14D': (
            RiskOverlayDefinition(
                name='BTC_LT_14D',
                description='Exit to cash when BTC closes below its level 14 days earlier; re-enter at next rebalance once the condition clears.',
            ),
            btc_above_trailing_price(price, lookback_days=14, confirm_days=1),
        ),
        'BTC_LT_14D_CONFIRM2': (
            RiskOverlayDefinition(
                name='BTC_LT_14D_CONFIRM2',
                description='Same as BTC_LT_14D but require the new state to persist for 2 consecutive days before switching.',
            ),
            btc_above_trailing_price(price, lookback_days=14, confirm_days=2),
        ),
        'BTC_LT_20DMA': (
            RiskOverlayDefinition(
                name='BTC_LT_20DMA',
                description='Exit to cash when BTC closes below its 20-day moving average; re-enter at next rebalance once back above.',
            ),
            btc_above_moving_average(price, ma_window=20, confirm_days=1),
        ),
    }


def btc_above_volatility_scaled_trailing(
    price: pd.DataFrame,
    lookback: int = 30,
    vol_window: int = 30,
    vol_multiple: float = 2.0,
    confirm_days: int = 1,
) -> pd.Series:
    """Risk-on while BTC holds a volatility-scaled trailing high (Chandelier stop).

    A fixed-day trailing stop (e.g. "BTC >= its price 11 days ago") has no idea
    how volatile the market is: in a calm grind it exits on noise, and in a
    crash it is far too slow. This variant sets the exit band from BTC's own
    realized volatility, so the stop widens exactly when turbulence rises.

    Exit level = trailing ``lookback``-day high x (1 - vol_multiple * sigma *
    sqrt(lookback)), where sigma is the daily return volatility over
    ``vol_window`` days. Everything is trailing, so there is no look-ahead.
    """
    btc = price["bitcoin"]
    trailing_high = btc.rolling(lookback, min_periods=lookback).max()
    daily_vol = btc.pct_change().rolling(vol_window, min_periods=vol_window).std()
    band = vol_multiple * daily_vol * (lookback ** 0.5)
    exit_level = trailing_high * (1.0 - band)
    raw = (btc >= exit_level).where(exit_level.notna(), True)
    return _confirmed_state(raw, confirm_days).rename(
        f"btc_chandelier_{lookback}_{vol_multiple}"
    )


def realized_volatility(price: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    """Annualized trailing realized volatility per asset (decimal, not %)."""
    return price.pct_change().rolling(window, min_periods=window).std() * (365 ** 0.5)


def volatility_target_leverage(
    price: pd.DataFrame,
    target_volatility: float,
    window: int = 30,
    max_leverage: float = 1.5,
    min_leverage: float = 0.0,
) -> pd.DataFrame:
    """Leverage per asset/date that scales exposure toward a constant volatility.

    ``target / realized`` so a calm asset is levered up and a wild one is cut
    back, clamped to ``[min_leverage, max_leverage]``. Undefined (warm-up) rows
    fall back to 1.0 so the strategy is not silently flat at the start.
    """
    vol = realized_volatility(price, window)
    leverage = (target_volatility / vol).clip(lower=min_leverage, upper=max_leverage)
    return leverage.where(vol.notna(), 1.0)


def absolute_trend_mask(price: pd.DataFrame, ma_window: int = 100) -> pd.DataFrame:
    """True where an asset trades above its own trailing moving average.

    This is the time-series (absolute) trend test. Published crypto evidence
    (Han et al.) finds time-series momentum far more reliable than
    cross-sectional momentum, so a relative-strength pick should also have to
    pass its own trend filter before it is bought.
    """
    ma = price.rolling(ma_window, min_periods=ma_window).mean()
    return (price > ma).where(ma.notna(), False)
