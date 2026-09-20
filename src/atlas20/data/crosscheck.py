"""Cross-provider validation of recent price history.

CoinMarketCap is the only source that feeds the panel, which makes it a single
point of failure: CMC served Huobi Token at ~$0.000002 instead of ~$0.5 for 34
consecutive days in early 2025, and every one of those rows was internally
consistent (``market_cap == price x supply``). A per-row integrity check cannot
see that; an independent provider can.

This module compares CMC's recent daily closes against CoinGecko's recent daily
market chart. It only ever *validates* - the panel's prices stay 100% CMC - so a
disagreement never silently rewrites history, it just blocks the asset (or
raises an alert) until a human looks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# CoinGecko returns intraday points for short ranges and daily points beyond
# 90 days; both collapse to a daily close by taking the last print of the day.
# Thresholds calibrated on the live universe. Across 95 healthy assets the
# median provider gap tops out at 5.9%; the two genuinely broken ones (Huobi
# Token, Celsius) sit at 31% and 1,085x. A per-day "how many days disagree"
# test is *not* usable at tight tolerances: thin small caps disagree by 20-60%
# on 12% of days purely because CoinGecko snapshots at 00:00 UTC while CMC
# reports a session close.
MEDIAN_GAP_TOLERANCE = 0.10
LATEST_GAP_TOLERANCE = 0.35
# A sustained block: no healthy asset disagrees by 3x on more than 5% of days.
SUSTAINED_GAP = 2.0
MAX_SUSTAINED_SHARE = 0.05
# Even a single day this far apart is a data error, not a move: both providers
# quote the same underlying move, so only a corrupted print produces it.
CATASTROPHIC_GAP = 5.0
MIN_OVERLAP_DAYS = 30


@dataclass
class CrossCheckResult:
    """Agreement between the primary series and an independent provider."""

    passed: bool
    reason: str
    overlap_days: int
    median_gap: float
    latest_gap: float
    latest_overlap_date: pd.Timestamp | None
    disagreeing_share: float = 0.0
    worst_gap: float = float("nan")


def _daily_closes(frame: pd.DataFrame, price_column: str) -> pd.Series:
    if frame is None or frame.empty or price_column not in frame.columns:
        return pd.Series(dtype=float)
    prepared = frame[["date", price_column]].copy()
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    prepared[price_column] = pd.to_numeric(prepared[price_column], errors="coerce")
    prepared = prepared.dropna()
    prepared = prepared[prepared[price_column] > 0]
    series = prepared.sort_values("date").groupby("date")[price_column].last()
    return series.astype(float)


def compare_daily_prices(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    *,
    primary_column: str = "price",
    secondary_column: str = "cg_price",
    min_overlap_days: int = MIN_OVERLAP_DAYS,
    max_median_gap: float = MEDIAN_GAP_TOLERANCE,
    max_latest_gap: float = LATEST_GAP_TOLERANCE,
) -> CrossCheckResult:
    """Compare two daily close series over their overlapping window."""
    left = _daily_closes(primary, primary_column)
    right = _daily_closes(secondary, secondary_column)

    overlap = pd.concat({"primary": left, "secondary": right}, axis=1).dropna()
    if overlap.empty:
        return CrossCheckResult(False, "no_overlap", 0, np.nan, np.nan, None)

    # Symmetric multiplicative gap. A plain relative difference saturates at
    # 100% whenever the bad print is the *lower* one, which would hide a print
    # that is 250,000x too small - exactly the Huobi Token failure mode.
    low = overlap["primary"].abs().clip(lower=1e-18)
    high = overlap["secondary"].abs().clip(lower=1e-18)
    relative_gap = pd.concat([low / high, high / low], axis=1).max(axis=1) - 1.0
    median_gap = float(relative_gap.median())
    latest_gap = float(relative_gap.iloc[-1])
    worst_gap = float(relative_gap.max())
    disagreeing_share = float((relative_gap > SUSTAINED_GAP).mean())
    days = int(len(overlap))
    latest_date = pd.Timestamp(overlap.index[-1])

    def verdict(passed: bool, reason: str) -> CrossCheckResult:
        return CrossCheckResult(
            passed, reason, days, median_gap, latest_gap, latest_date, disagreeing_share, worst_gap
        )

    if days < min_overlap_days:
        return verdict(False, "insufficient_overlap")
    if median_gap > max_median_gap:
        return verdict(False, "median_price_gap")
    if disagreeing_share > MAX_SUSTAINED_SHARE:
        return verdict(False, "sustained_disagreement")
    if latest_gap > max_latest_gap:
        return verdict(False, "latest_price_gap")
    if worst_gap > CATASTROPHIC_GAP:
        return verdict(False, "catastrophic_print")
    return verdict(True, "ok")
