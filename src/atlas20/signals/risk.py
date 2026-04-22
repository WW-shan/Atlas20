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
