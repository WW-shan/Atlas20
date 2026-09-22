"""Time-series momentum target builders.

The validation work in this repository has repeatedly shown that simple
cross-sectional leader picking is fragile: the same parameter plateau does not
survive a 2022-start test.  The academic evidence is materially stronger for
time-series momentum, where each asset must first pass its own trend gate and
only then competes for capital.

This module deliberately keeps the strategy long-only and unlevered.  It
supports two distinct portfolio constructions:

* ``top_n > 0``: rank assets that pass their own trend gate and hold the
  strongest names.  This is a time-series gate with cross-sectional selection.
* ``top_n is None`` or ``top_n <= 0``: hold every asset that passes its own
  trend gate.  This is a pure portfolio TSMOM construction.

The resulting targets are positive weights that sum to at most one.  The
backtest engine applies T+1 execution and the normal friction model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.config import ResearchConfig
from atlas20.strategies.momentum_lead import MomentumLeadBuildResult
from atlas20.universe.builder import MarketDataBundle


TSMOM_SCORE_FAMILIES: tuple[str, ...] = (
    "tsmom",
    "tsmom_vol_adjusted",
    "tsmom_multi",
    "tsmom_breakout",
)

TSMOM_WEIGHTING_SCHEMES: tuple[str, ...] = ("equal", "inverse_vol")


@dataclass(frozen=True)
class TSMOMSettings:
    """Configuration for one TSMOM target construction."""

    lookback: int = 90
    score_family: str = "tsmom"
    weighting: str = "inverse_vol"
    vol_window: int = 30
    asset_ma_window: int | None = None
    min_lookback_return: float = 0.0
    max_weight: float = 1.0


def _clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _universe_lookup(universe: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    return {pd.Timestamp(date): frame.copy() for date, frame in universe.groupby("rebalance_date")}


def _trailing_return(
    price: pd.DataFrame,
    date: pd.Timestamp,
    coin_ids: list[str],
    window: int,
) -> pd.Series:
    current = _clean_numeric(price.loc[date].reindex(coin_ids))
    base = _clean_numeric(price.shift(window).loc[date].reindex(coin_ids))
    return (current / base - 1.0).replace([np.inf, -np.inf], np.nan)


def _realized_vol(
    price: pd.DataFrame,
    date: pd.Timestamp,
    coin_ids: list[str],
    window: int,
) -> pd.Series:
    history = _clean_frame(price.reindex(columns=coin_ids).loc[:date].tail(window + 1))
    return history.pct_change(fill_method=None).tail(window).std() * np.sqrt(365.0)


def _near_high(
    price: pd.DataFrame,
    date: pd.Timestamp,
    coin_ids: list[str],
    window: int = 90,
) -> pd.Series:
    history = _clean_frame(price.reindex(columns=coin_ids).loc[:date])
    current = history.loc[date].reindex(coin_ids)
    trailing_high = history.shift(1).rolling(window, min_periods=max(20, window // 2)).max().loc[date]
    return _clean_numeric(current / trailing_high.reindex(coin_ids))


def _score(
    ret: pd.Series,
    vol: pd.Series,
    near_high: pd.Series,
    price: pd.DataFrame,
    date: pd.Timestamp,
    coin_ids: list[str],
    lookback: int,
    score_family: str,
) -> pd.Series:
    if score_family == "tsmom":
        return ret
    if score_family == "tsmom_vol_adjusted":
        return (ret / vol.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    if score_family == "tsmom_breakout":
        # Keep the signal dominated by the asset's own return, but avoid
        # buying a coin that has already broken down relative to its range.
        return ret * (0.5 + 0.5 * near_high.clip(lower=0.0, upper=1.5))
    if score_family == "tsmom_multi":
        short = _trailing_return(price, date, coin_ids, min(30, lookback))
        medium = _trailing_return(price, date, coin_ids, max(60, min(lookback, 180)))
        long = _trailing_return(price, date, coin_ids, max(90, lookback))
        frame = pd.DataFrame({"short": short, "medium": medium, "long": long}).reindex(coin_ids)
        # Average the per-asset returns, not cross-sectional ranks.  The
        # factor remains a pure time-series signal and does not depend on how
        # many peers happen to be in the universe.
        return frame.mean(axis=1)
    known = ", ".join(TSMOM_SCORE_FAMILIES)
    raise ValueError(f"Unknown TSMOM score_family {score_family!r}; expected one of: {known}")


def _cap_and_normalize(weights: pd.Series, max_weight: float) -> pd.Series:
    """Cap one weight and redistribute the excess across uncapped names."""
    if weights.empty:
        return weights
    weights = weights.clip(lower=0.0).astype(float)
    total = float(weights.sum())
    if total <= 0.0:
        return pd.Series(dtype=float)
    weights = weights / total
    cap = min(max(float(max_weight), 0.0), 1.0)
    if cap >= 1.0:
        return weights

    capped = pd.Series(False, index=weights.index)
    result = weights.copy()
    for _ in range(len(weights) + 1):
        over = result > cap + 1e-12
        newly_capped = over & ~capped
        if not newly_capped.any():
            break
        capped |= over
        free = ~capped
        if not free.any():
            break
        fixed_sum = float(result[capped].clip(upper=cap).sum())
        remaining = max(1.0 - fixed_sum, 0.0)
        free_sum = float(result[free].sum())
        if free_sum <= 0.0:
            break
        result.loc[free] = result.loc[free] / free_sum * remaining
        result.loc[capped] = result.loc[capped].clip(upper=cap)
    # Floating-point residue can otherwise make gross exposure 1+epsilon and
    # trip the engine's hard no-leverage guard in some callers.
    result = result.clip(upper=cap)
    total = float(result.sum())
    if total > 1.0:
        result = result / total
    return result


def _weights_for_selection(
    selected: pd.Series,
    vol: pd.Series,
    weighting: str,
    max_weight: float,
) -> pd.Series:
    if selected.empty:
        return pd.Series(dtype=float)
    if len(selected) == 1 or weighting == "equal":
        raw = pd.Series(1.0 / len(selected), index=selected.index, dtype=float)
    elif weighting == "inverse_vol":
        inv = 1.0 / vol.reindex(selected.index).replace(0.0, np.nan)
        # If volatility is not yet available for one name, give it the median
        # risk estimate rather than silently dropping a qualifying asset.
        fill = float(inv[inv > 0.0].median()) if (inv > 0.0).any() else 1.0
        inv = inv.fillna(fill).clip(lower=1e-12)
        raw = inv / inv.sum()
    else:
        known = ", ".join(TSMOM_WEIGHTING_SCHEMES)
        raise ValueError(f"Unknown TSMOM weighting {weighting!r}; expected one of: {known}")
    # A lone eligible trend asset should be allowed to take the full book; a
    # cap is only useful once there is a cross-section of holdings to spread.
    cap = 1.0 if len(selected) == 1 else max_weight
    return _cap_and_normalize(raw, max_weight=cap)


def build_tsmom_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    config: ResearchConfig,
    *,
    top_n: int | None = 3,
    frequency: str = "14D",
    settings: TSMOMSettings | None = None,
    include_btc: bool = True,
) -> MomentumLeadBuildResult:
    """Build long-only TSMOM targets from the point-in-time universe."""
    settings = settings or TSMOMSettings()
    if settings.lookback <= 0:
        raise ValueError("TSMOM lookback must be positive")
    if settings.vol_window <= 1:
        raise ValueError("TSMOM vol_window must be greater than one")
    if not 0.0 <= float(settings.max_weight) <= 1.0:
        raise ValueError("TSMOM max_weight must be between zero and one")
    if settings.score_family not in TSMOM_SCORE_FAMILIES:
        known = ", ".join(TSMOM_SCORE_FAMILIES)
        raise ValueError(
            f"Unknown TSMOM score_family {settings.score_family!r}; expected one of: {known}"
        )
    if settings.weighting not in TSMOM_WEIGHTING_SCHEMES:
        known = ", ".join(TSMOM_WEIGHTING_SCHEMES)
        raise ValueError(
            f"Unknown TSMOM weighting {settings.weighting!r}; expected one of: {known}"
        )

    frequency_value = config.rebalancing.frequencies.get(frequency, frequency)
    rebalance_dates = get_rebalance_dates(
        market.price.index,
        config.start_timestamp,
        frequency,
        frequency_value,
    )
    universe_by_date = _universe_lookup(universe)
    targets: dict[pd.Timestamp, pd.Series] = {}
    rows: list[dict[str, object]] = []

    for date in rebalance_dates:
        snapshot = universe_by_date.get(date)
        if snapshot is None or snapshot.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        coin_ids = snapshot["coin_id"].astype(str).tolist()
        if not include_btc:
            coin_ids = [coin_id for coin_id in coin_ids if coin_id != "bitcoin"]
        coin_ids = list(dict.fromkeys(coin_ids))
        if not coin_ids:
            targets[date] = pd.Series(dtype=float)
            continue

        returns = _trailing_return(market.price, date, coin_ids, settings.lookback)
        vol = _realized_vol(market.price, date, coin_ids, settings.vol_window)
        near_high = _near_high(market.price, date, coin_ids)
        current = _clean_numeric(market.price.loc[date].reindex(coin_ids))

        eligible = (
            current.notna()
            & (current > 0.0)
            & returns.notna()
            & (returns > float(settings.min_lookback_return))
        )
        if settings.asset_ma_window is not None:
            ma_window = int(settings.asset_ma_window)
            history = _clean_frame(market.price.reindex(columns=coin_ids).loc[:date])
            ma = history.rolling(ma_window, min_periods=ma_window).mean().loc[date]
            eligible &= current >= ma.reindex(coin_ids)
        eligible &= vol.notna() & (vol > 0.0)

        if not eligible.any():
            targets[date] = pd.Series(dtype=float)
            rows.append(
                {
                    "rebalance_date": date,
                    "coin_id": "",
                    "coin_rank": 0,
                    "coin_score": 0.0,
                    "coin_weight": 0.0,
                    "lookback_return": np.nan,
                    "realized_vol": np.nan,
                    "eligible": False,
                }
            )
            continue

        scores = _score(
            returns,
            vol,
            near_high,
            market.price,
            date,
            coin_ids,
            settings.lookback,
            settings.score_family,
        ).reindex(coin_ids)
        scores = scores.where(eligible).dropna().sort_values(ascending=False, kind="mergesort")
        if scores.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        if top_n is not None and int(top_n) > 0:
            selected = scores.head(int(top_n))
        else:
            selected = scores
        weights = _weights_for_selection(
            selected,
            vol.reindex(selected.index),
            settings.weighting,
            settings.max_weight,
        )
        targets[date] = weights
        for rank, coin_id in enumerate(weights.index, start=1):
            rows.append(
                {
                    "rebalance_date": date,
                    "coin_id": coin_id,
                    "coin_rank": rank,
                    "coin_score": float(scores.loc[coin_id]),
                    "coin_weight": float(weights.loc[coin_id]),
                    "lookback_return": float(returns.loc[coin_id]),
                    "realized_vol": float(vol.loc[coin_id]),
                    "eligible": True,
                }
            )

    return MomentumLeadBuildResult(targets=targets, selection_history=pd.DataFrame(rows))
