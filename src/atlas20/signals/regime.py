"""Bull-market regime filter construction."""

from __future__ import annotations

import math

import pandas as pd

from atlas20.config import ResearchConfig



def build_regime_frame(price: pd.DataFrame, market_cap: pd.DataFrame, config: ResearchConfig) -> pd.DataFrame:
    """Build a modular bull-market regime state using tracked market data."""
    if "bitcoin" not in price.columns:
        raise KeyError("bitcoin must be present in the price matrix to build the regime filter")

    btc_price = price["bitcoin"]
    tracked_total_mcap = market_cap.sum(axis=1, min_count=1)
    tracked_alt_mcap = tracked_total_mcap - market_cap.get("bitcoin", 0.0)

    frame = pd.DataFrame(index=price.index)
    conditions: list[str] = []

    if config.regime.use_btc_ma:
        btc_ma = btc_price.rolling(config.regime.btc_ma_window, min_periods=config.regime.btc_ma_window).mean()
        frame["btc_above_ma"] = btc_price > btc_ma
        conditions.append("btc_above_ma")

    if config.regime.use_tracked_total_mcap_ma:
        total_ma = tracked_total_mcap.rolling(
            config.regime.tracked_total_mcap_ma_window,
            min_periods=config.regime.tracked_total_mcap_ma_window,
        ).mean()
        frame["tracked_total_mcap_above_ma"] = tracked_total_mcap > total_ma
        conditions.append("tracked_total_mcap_above_ma")

    if config.regime.use_tracked_alt_momentum:
        alt_mom = tracked_alt_mcap.pct_change(config.regime.tracked_alt_mcap_momentum_window)
        frame["tracked_alt_momentum_positive"] = alt_mom > 0
        conditions.append("tracked_alt_momentum_positive")

    if not conditions:
        frame["bull"] = True
        return frame

    cond_frame = frame[conditions].fillna(False)
    if config.regime.combine_method == "all":
        frame["bull"] = cond_frame.all(axis=1)
    elif config.regime.combine_method == "any":
        frame["bull"] = cond_frame.any(axis=1)
    else:
        threshold = math.ceil(len(conditions) / 2)
        frame["bull"] = cond_frame.sum(axis=1) >= threshold

    frame["tracked_total_market_cap"] = tracked_total_mcap
    frame["tracked_alt_market_cap"] = tracked_alt_mcap
    return frame
