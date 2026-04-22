"""Data blending and validation helpers for crypto market data."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas20.config import DataQualityConfig


@dataclass
class ValidationResult:
    """Structured validation output for one asset."""

    passed: bool
    summary: dict[str, object]
    blended_history: pd.DataFrame


EMPTY_CG_HISTORY = pd.DataFrame(columns=["date", "cg_price", "cg_market_cap", "cg_volume_usd"])



def prepare_cryptocompare_history(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize a CryptoCompare histoday frame."""
    history = frame.copy()
    history["date"] = pd.to_datetime(history["time"], unit="s").dt.normalize()
    history = history.rename(columns={"close": "cc_price", "volumeto": "cc_volume_usd"})
    return history[["date", "cc_price", "cc_volume_usd"]].sort_values("date").reset_index(drop=True)



def prepare_coingecko_history(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize a CoinGecko market_chart frame."""
    if frame is None or frame.empty:
        return EMPTY_CG_HISTORY.copy()
    history = frame.copy()
    history["date"] = pd.to_datetime(history["date"]).dt.normalize()
    return history[["date", "cg_price", "cg_market_cap", "cg_volume_usd"]].sort_values("date").reset_index(drop=True)



def validate_and_blend_history(
    coin_id: str,
    symbol: str,
    name: str,
    cc_history: pd.DataFrame,
    cg_history: pd.DataFrame,
    current_market_cap: float,
    quality_config: DataQualityConfig,
    use_proxy_market_caps: bool,
) -> ValidationResult:
    """Blend sources and compute overlap-based validation metrics."""
    cc = prepare_cryptocompare_history(cc_history)
    cg = prepare_coingecko_history(cg_history)

    overlap = cc.merge(cg, on="date", how="inner")
    overlap = overlap[(overlap["cc_price"] > 0) & (overlap["cg_price"] > 0)].copy()
    if overlap.empty:
        latest_gap = np.nan
        median_gap = np.nan
        price_correlation = np.nan
        overlap_days = 0
        latest_overlap_date = pd.NaT
    else:
        overlap["abs_pct_gap"] = (overlap["cc_price"] - overlap["cg_price"]).abs() / overlap["cg_price"].abs().clip(lower=1e-12)
        latest_gap = float(overlap["abs_pct_gap"].iloc[-1])
        median_gap = float(overlap["abs_pct_gap"].median())
        price_correlation = float(overlap[["cc_price", "cg_price"]].corr().iloc[0, 1]) if len(overlap) > 1 else np.nan
        overlap_days = int(len(overlap))
        latest_overlap_date = pd.Timestamp(overlap["date"].iloc[-1])

    passed = True
    validation_reason = "ok"
    if overlap_days >= quality_config.min_overlap_days:
        if not np.isnan(latest_gap) and latest_gap > quality_config.max_latest_price_gap:
            passed = False
            validation_reason = "latest_price_gap"
        elif not np.isnan(median_gap) and median_gap > quality_config.max_median_overlap_gap:
            passed = False
            validation_reason = "median_price_gap"

    merged = cc.merge(cg, on="date", how="outer").sort_values("date").reset_index(drop=True)
    merged["price"] = merged["cg_price"].combine_first(merged["cc_price"])
    merged["volume_usd"] = merged["cg_volume_usd"].combine_first(merged["cc_volume_usd"])

    anchor = merged[merged["cg_market_cap"].notna() & merged["price"].notna()].tail(1)
    if not anchor.empty:
        anchor_market_cap = float(anchor["cg_market_cap"].iloc[0])
        anchor_price = float(anchor["price"].iloc[0])
    else:
        positive_prices = merged.loc[merged["price"] > 0, "price"]
        anchor_market_cap = current_market_cap
        anchor_price = float(positive_prices.iloc[-1]) if not positive_prices.empty else 0.0

    market_cap_scale = anchor_market_cap / anchor_price if anchor_price > 0 else 0.0
    proxy_market_cap = merged["price"] * market_cap_scale if use_proxy_market_caps else pd.Series(pd.NA, index=merged.index)
    merged["market_cap"] = merged["cg_market_cap"].combine_first(proxy_market_cap)
    merged["price_source"] = np.where(merged["cg_price"].notna(), "coingecko_recent", "cryptocompare")
    merged["volume_source"] = np.where(merged["cg_volume_usd"].notna(), "coingecko_recent", "cryptocompare")
    merged["market_cap_source"] = np.where(
        merged["cg_market_cap"].notna(),
        "coingecko_direct",
        np.where(merged["market_cap"].notna(), "proxy_anchor", "missing"),
    )

    summary = {
        "coin_id": coin_id,
        "symbol": symbol,
        "name": name,
        "overlap_days": overlap_days,
        "latest_overlap_date": latest_overlap_date,
        "latest_price_gap": latest_gap,
        "median_price_gap": median_gap,
        "price_correlation": price_correlation,
        "direct_market_cap_days": int(merged["cg_market_cap"].notna().sum()),
        "direct_price_days": int(merged["cg_price"].notna().sum()),
        "history_days": int(merged["price"].notna().sum()),
        "validation_passed": passed,
        "validation_reason": validation_reason,
        "market_cap_anchor": float(anchor_market_cap),
        "market_cap_anchor_price": float(anchor_price),
    }
    return ValidationResult(passed=passed, summary=summary, blended_history=merged)
