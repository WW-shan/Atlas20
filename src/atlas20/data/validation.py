"""Data sufficiency checks for the CoinMarketCap-only data chain.

Every price, volume and market-cap value in the processed panel comes from a
single provider snapshot. That removes the cross-source reconciliation this
module used to perform (CryptoCompare vs CoinGecko price gaps), and with it the
synthetic market-cap fallback: an asset that has no real supply history is
simply not rankable, rather than being given a price-scaled guess.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas20.config import DataQualityConfig


@dataclass
class ValidationResult:
    """Outcome of the data sufficiency check for one asset."""

    passed: bool
    summary: dict
    history: pd.DataFrame


def summarize_market_history(
    coin_id: str,
    symbol: str,
    name: str,
    history: pd.DataFrame,
    quality_config: DataQualityConfig,
) -> ValidationResult:
    """Normalize a CMC history frame and report how much of it is usable.

    ``history`` is expected to carry ``date``, ``price``, ``volume_usd`` and
    ``market_cap``; anything missing is treated as unavailable rather than
    filled in.
    """
    frame = history.copy() if history is not None else pd.DataFrame()
    for column in ("price", "volume_usd", "market_cap"):
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "date" not in frame.columns:
        frame["date"] = pd.NaT
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()

    frame = frame.dropna(subset=["date"])
    frame = frame[frame["price"] > 0]
    frame = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)

    price_days = int(frame["price"].notna().sum())
    market_cap_days = int((frame["market_cap"] > 0).sum())

    passed = True
    reason = "ok"
    if price_days == 0:
        passed, reason = False, "no_price_history"
    elif price_days < quality_config.min_price_days:
        passed, reason = False, "insufficient_price_history"
    elif market_cap_days < quality_config.min_market_cap_days:
        # Without real supply the asset can never hold a genuine Top-N rank,
        # so it is kept out of the panel entirely.
        passed, reason = False, "insufficient_market_cap_history"

    with_market_cap = frame.loc[frame["market_cap"] > 0, "date"]
    latest_market_cap_date = with_market_cap.max() if not with_market_cap.empty else pd.NaT

    summary = {
        "coin_id": coin_id,
        "symbol": symbol,
        "name": name,
        "price_days": price_days,
        "market_cap_days": market_cap_days,
        "history_days": price_days,
        "first_date": frame["date"].min(),
        "latest_date": frame["date"].max(),
        "latest_overlap_date": latest_market_cap_date,
        "validation_passed": passed,
        "validation_reason": reason,
        # Retained for the data-quality alert contract in the API. There is no
        # second price series to compare against any more.
        "latest_price_gap": np.nan,
        "median_price_gap": np.nan,
        "price_correlation": np.nan,
        "direct_market_cap_days": market_cap_days,
        "direct_price_days": price_days,
    }
    return ValidationResult(passed=passed, summary=summary, history=frame)
