"""Splice a legacy cached price history with a newer data source.

After the CryptoCompare free tier shut down in mid-2026, existing cached
histories stopped updating. Rather than discard the deep legacy history, we
keep it up to and including a cutover date and continue with a currently
available source. Both sources are cross-checked over their overlap window so
a bad splice can be detected before it contaminates a backtest.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SpliceResult:
    """Outcome of combining two price histories."""

    frame: pd.DataFrame
    cutover: pd.Timestamp
    overlap_days: int
    median_gap: float
    max_gap: float
    correlation: float


def _normalize(frame: pd.DataFrame | None, price_col: str) -> pd.DataFrame:
    columns = ["date", price_col, "volume_usd"]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=columns)
    working = frame.copy()
    if "date" not in working.columns:
        return pd.DataFrame(columns=columns)
    working["date"] = pd.to_datetime(working["date"]).dt.normalize()
    # Callers may supply an explicitly named price column (tests) or the
    # shared ``close`` column produced by the download/processing helpers.
    source_price_col = price_col if price_col in working.columns else "close"
    if source_price_col not in working.columns:
        return pd.DataFrame(columns=columns)
    working = working.rename(columns={source_price_col: price_col})
    if "volume_usd" not in working.columns:
        working["volume_usd"] = np.nan
    working = working[columns]
    working = working[pd.to_numeric(working[price_col], errors="coerce") > 0]
    return working.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def splice_histories(
    legacy: pd.DataFrame | None,
    new: pd.DataFrame | None,
    *,
    cutover: pd.Timestamp | None = None,
) -> SpliceResult:
    """Combine ``legacy`` (deep history) with ``new`` (current source).

    Rows on or before ``cutover`` come from ``legacy``; rows strictly after come
    from ``new``. When ``cutover`` is omitted the last legacy date is used.
    Overlap statistics describe the shared window and let callers gate on
    source agreement.
    """
    legacy_norm = _normalize(legacy, "legacy_price")
    new_norm = _normalize(new, "new_price")

    if cutover is None:
        if not legacy_norm.empty:
            cutover = legacy_norm["date"].max()
        elif not new_norm.empty:
            cutover = new_norm["date"].min()
        else:
            empty = pd.DataFrame(columns=["date", "price", "volume_usd", "price_source"])
            return SpliceResult(empty, pd.NaT, 0, np.nan, np.nan, np.nan)
    cutover = pd.Timestamp(cutover).normalize()

    overlap = legacy_norm.merge(new_norm, on="date", how="inner")
    if overlap.empty:
        overlap_days = 0
        median_gap = np.nan
        max_gap = np.nan
        correlation = np.nan
    else:
        overlap = overlap[overlap["new_price"] > 0].copy()
        gaps = (overlap["legacy_price"] - overlap["new_price"]).abs() / overlap["new_price"].abs().clip(lower=1e-12)
        overlap_days = int(len(overlap))
        median_gap = float(gaps.median()) if overlap_days else np.nan
        max_gap = float(gaps.max()) if overlap_days else np.nan
        correlation = (
            float(overlap[["legacy_price", "new_price"]].corr().iloc[0, 1]) if overlap_days > 1 else np.nan
        )

    legacy_part = legacy_norm[legacy_norm["date"] <= cutover].copy()
    legacy_part = legacy_part.rename(columns={"legacy_price": "price"})
    legacy_part["price_source"] = "legacy"

    # Strictly after the cutover the new source is authoritative.
    new_after = new_norm[new_norm["date"] > cutover].copy()
    # On or before the cutover, fill any dates the legacy cache is missing
    # (gaps or an entirely empty cache) from the new source.
    legacy_dates = set(legacy_part["date"])
    new_fill = new_norm[
        (new_norm["date"] <= cutover) & (~new_norm["date"].isin(legacy_dates))
    ].copy()
    new_part = pd.concat([new_after, new_fill], ignore_index=True)
    new_part = new_part.rename(columns={"new_price": "price"})
    new_part["price_source"] = "new"

    combined = pd.concat([legacy_part, new_part], ignore_index=True)
    if combined.empty:
        combined = pd.DataFrame(columns=["date", "price", "volume_usd", "price_source"])
    else:
        combined = (
            combined[["date", "price", "volume_usd", "price_source"]]
            .sort_values("date")
            .drop_duplicates("date", keep="last")
            .reset_index(drop=True)
        )

    return SpliceResult(
        frame=combined,
        cutover=cutover,
        overlap_days=overlap_days,
        median_gap=median_gap,
        max_gap=max_gap,
        correlation=correlation,
    )
