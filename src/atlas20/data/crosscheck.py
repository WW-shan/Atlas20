"""Cross-provider validation of recent price history.

CoinMarketCap is the only source that feeds the panel, which makes it a single
point of failure: CMC served Huobi Token at ~$0.000002 instead of ~$0.5 for 34
consecutive days in early 2025, and every one of those rows was internally
consistent (``market_cap == price x supply``). A per-row integrity check cannot
see that; an independent provider can.

This module compares CMC's recent daily closes against an independent provider.
Gate.io is the preferred second source because its public candles have a much
larger request budget than CoinGecko's free API; CoinGecko remains the second
source for assets Gate.io does not list.  When the primary and secondary
providers disagree, another independent provider can supply a third vote.  The
third provider must pass the same full test as the second one; a similar median
alone is not enough to override a disagreement.  It only ever
*validates* - the panel's prices stay 100% CMC - so a disagreement never
silently rewrites history, it just blocks the asset until a human looks.
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
    # Providers mix timezone-aware UTC timestamps with naive dates.  Normalize
    # both to naive UTC dates before merging or pandas refuses to align them.
    prepared["date"] = (
        pd.to_datetime(prepared["date"], errors="coerce", utc=True)
        .dt.tz_convert(None)
        .dt.normalize()
    )
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


@dataclass
class CrossCheckDecision:
    """Final three-provider decision for one primary series.

    ``secondary`` is always the CMC-vs-CoinGecko comparison.  When CoinGecko
    disagrees, ``tertiary`` records the CMC-vs-third-source comparison and
    ``secondary_vs_tertiary`` records whether the two independent providers
    agree with each other.  ``confirmed_by`` names the provider that passed
    the full check against CMC.
    """

    passed: bool
    reason: str
    secondary: CrossCheckResult
    tertiary: CrossCheckResult | None = None
    secondary_vs_tertiary: CrossCheckResult | None = None
    tertiary_checked: bool = False
    confirmed_by: str | None = None

    @property
    def overlap_days(self) -> int:
        return self.secondary.overlap_days

    @property
    def median_gap(self) -> float:
        return self.secondary.median_gap

    @property
    def latest_gap(self) -> float:
        return self.secondary.latest_gap

    @property
    def latest_overlap_date(self) -> pd.Timestamp | None:
        return self.secondary.latest_overlap_date

    @property
    def disagreeing_share(self) -> float:
        return self.secondary.disagreeing_share

    @property
    def worst_gap(self) -> float:
        return self.secondary.worst_gap

    @property
    def effective_median_gap(self) -> float:
        """Median gap of the provider pair that actually supported CMC."""
        if self.confirmed_by is not None and self.tertiary is not None:
            return self.tertiary.median_gap
        return self.secondary.median_gap


def _has_overlap(result: CrossCheckResult, min_overlap_days: int) -> bool:
    return result.overlap_days >= min_overlap_days


def adjudicate_daily_prices(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    tertiary: pd.DataFrame | None = None,
    *,
    primary_column: str = "price",
    secondary_column: str = "cg_price",
    tertiary_column: str = "pap_price",
    tertiary_source: str = "coinpaprika",
    min_overlap_days: int = MIN_OVERLAP_DAYS,
    max_median_gap: float = MEDIAN_GAP_TOLERANCE,
    max_latest_gap: float = LATEST_GAP_TOLERANCE,
) -> CrossCheckDecision:
    """Decide whether the primary provider is corroborated.

    The normal path is provider-agnostic: if CMC and the selected secondary
    source agree, the asset passes without touching a third provider.  Only a
    primary-vs-secondary disagreement invokes the majority vote.  A median-level
    agreement is used for the vote because low-liquidity assets can have noisy
    single-day provider snapshots; a consensus between the two independent
    providers on the latest print is still treated as decisive.
    """
    secondary_result = compare_daily_prices(
        primary,
        secondary,
        primary_column=primary_column,
        secondary_column=secondary_column,
        min_overlap_days=min_overlap_days,
        max_median_gap=max_median_gap,
        max_latest_gap=max_latest_gap,
    )
    if secondary_result.passed:
        return CrossCheckDecision(True, secondary_result.reason, secondary_result)

    secondary_unverified = secondary_result.reason in {"no_overlap", "insufficient_overlap"}
    if tertiary is None or tertiary.empty:
        return CrossCheckDecision(
            False,
            "unverified" if secondary_unverified else "secondary_disagreement_unresolved",
            secondary_result,
        )

    tertiary_result = compare_daily_prices(
        primary,
        tertiary,
        primary_column=primary_column,
        secondary_column=tertiary_column,
        min_overlap_days=min_overlap_days,
        max_median_gap=max_median_gap,
        max_latest_gap=max_latest_gap,
    )
    if tertiary_result.reason in {"no_overlap", "insufficient_overlap"}:
        return CrossCheckDecision(
            False,
            "unverified" if secondary_unverified else "third_source_insufficient_overlap",
            secondary_result,
            tertiary_result,
            tertiary_checked=True,
        )

    if secondary_unverified:
        if tertiary_result.passed:
            return CrossCheckDecision(
                True,
                "third_source_only",
                secondary_result,
                tertiary_result,
                tertiary_checked=True,
                confirmed_by=tertiary_source,
            )
        return CrossCheckDecision(
            False,
            "unverified",
            secondary_result,
            tertiary_result,
            tertiary_checked=True,
        )

    secondary_vs_tertiary = compare_daily_prices(
        secondary,
        tertiary,
        primary_column=secondary_column,
        secondary_column=tertiary_column,
        min_overlap_days=min_overlap_days,
        max_median_gap=max_median_gap,
        max_latest_gap=max_latest_gap,
    )
    secondaries_have_overlap = _has_overlap(secondary_vs_tertiary, min_overlap_days)
    secondaries_agree_latest = secondaries_have_overlap and secondary_vs_tertiary.latest_gap <= max_latest_gap
    secondaries_agree_median = secondaries_have_overlap and secondary_vs_tertiary.median_gap <= max_median_gap

    # If both independent providers agree with each other but not with CMC,
    # CMC is the isolated outlier.  This is the Celsius failure mode.
    if (
        secondaries_agree_latest
        and secondary_result.latest_gap > max_latest_gap
        and tertiary_result.latest_gap > max_latest_gap
    ):
        return CrossCheckDecision(
            False,
            "cmc_isolated",
            secondary_result,
            tertiary_result,
            secondary_vs_tertiary,
            tertiary_checked=True,
        )
    if (
        secondaries_agree_median
        and secondary_result.median_gap > max_median_gap
        and tertiary_result.median_gap > max_median_gap
    ):
        return CrossCheckDecision(
            False,
            "cmc_isolated",
            secondary_result,
            tertiary_result,
            secondary_vs_tertiary,
            tertiary_checked=True,
        )

    # A median-only agreement is not enough to overrule a full disagreement:
    # Huobi Token is the motivating example.  CMC's median can line up with a
    # noisy provider while its latest/sustained prints remain wrong.  Require
    # the third provider to pass the same complete test as the second one.
    if tertiary_result.passed:
        return CrossCheckDecision(
            True,
            "third_source_confirms_cmc",
            secondary_result,
            tertiary_result,
            secondary_vs_tertiary,
            tertiary_checked=True,
            confirmed_by=tertiary_source,
        )

    return CrossCheckDecision(
        False,
        "two_providers_disagree",
        secondary_result,
        tertiary_result,
        secondary_vs_tertiary,
        tertiary_checked=True,
    )
