"""Bull-market regime filter construction."""

from __future__ import annotations

import math

import pandas as pd

from atlas20.config import ResearchConfig



def _chain_linked_total(market_cap: pd.DataFrame) -> pd.Series:
    """Total market cap chain-linked over the assets present on consecutive days.

    The panel was assembled with hindsight, so a plain sum jumps when an asset
    enters it (ICP added +2.4% of the total on 2021-05-10) and drops when a
    market-cap feed stops (EOS, MKR, MATIC). Each day's growth is measured only
    over assets with a positive market cap on both days; the level starts at
    the first day's sum. A day with no market cap at all stays missing, and a
    day sharing no asset with the previous one carries the level unchanged.
    """
    caps = market_cap.where(market_cap > 0)
    observed = caps.notna().any(axis=1)
    caps = caps.loc[observed]
    if caps.empty:
        return pd.Series(float("nan"), index=market_cap.index)
    previous = caps.shift(1)
    both = caps.notna() & previous.notna()
    growth = caps.where(both).sum(axis=1) / previous.where(both).sum(axis=1)
    growth = growth.where(both.any(axis=1), 1.0)
    level = float(caps.iloc[0].sum()) * growth.cumprod()
    return level.reindex(market_cap.index)


def build_regime_frame(price: pd.DataFrame, market_cap: pd.DataFrame, config: ResearchConfig) -> pd.DataFrame:
    """Build a modular bull-market regime state using tracked market data."""
    if "bitcoin" not in price.columns:
        raise KeyError("bitcoin must be present in the price matrix to build the regime filter")

    btc_price = price["bitcoin"]
    tracked_total_mcap = market_cap.sum(axis=1, min_count=1)
    tracked_alt_mcap = tracked_total_mcap - market_cap.get("bitcoin", 0.0)
    # The signals use the chain-linked totals: panel entries and ended feeds
    # are not market moves. The plain sums are kept as descriptive columns.
    linked_total_mcap = _chain_linked_total(market_cap)
    linked_alt_mcap = _chain_linked_total(market_cap.drop(columns="bitcoin", errors="ignore"))

    frame = pd.DataFrame(index=price.index)
    conditions: list[str] = []

    if config.regime.use_btc_ma:
        btc_ma = btc_price.rolling(config.regime.btc_ma_window, min_periods=config.regime.btc_ma_window).mean()
        frame["btc_above_ma"] = btc_price > btc_ma
        conditions.append("btc_above_ma")

    if config.regime.use_tracked_total_mcap_ma:
        total_ma = linked_total_mcap.rolling(
            config.regime.tracked_total_mcap_ma_window,
            min_periods=config.regime.tracked_total_mcap_ma_window,
        ).mean()
        frame["tracked_total_mcap_above_ma"] = linked_total_mcap > total_ma
        conditions.append("tracked_total_mcap_above_ma")

    if config.regime.use_tracked_alt_momentum:
        alt_mom = linked_alt_mcap.pct_change(config.regime.tracked_alt_mcap_momentum_window)
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
    frame["tracked_total_market_cap_linked"] = linked_total_mcap
    frame["tracked_alt_market_cap_linked"] = linked_alt_mcap
    return frame
