"""Signal construction for the Bitget derivatives research track.

The long book is exactly the frozen H5 target scaled by leverage.  Optional
short overlays are added only under the pre-registered bear-regime and funding
filters.  These helpers do not select new long assets and do not broaden the
universe.
"""

from __future__ import annotations

from collections.abc import Mapping, Set

import numpy as np
import pandas as pd


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def scale_long_targets(
    long_targets: Mapping[pd.Timestamp, pd.Series],
    *,
    leverage: float,
    max_gross: float,
) -> dict[pd.Timestamp, pd.Series]:
    """Scale the frozen long book and enforce a gross-exposure cap."""
    if leverage <= 0.0:
        raise ValueError("leverage must be positive")
    if max_gross <= 0.0:
        raise ValueError("max_gross must be positive")
    scaled: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_weights in long_targets.items():
        date = _as_utc(raw_date)
        weights = pd.Series(raw_weights, dtype=float).copy()
        weights.index = weights.index.astype(str)
        if weights.isna().any() or not np.isfinite(weights.to_numpy()).all():
            raise ValueError("long target weights must be finite")
        if (weights < 0.0).any():
            raise ValueError("long target weights must be non-negative")
        weights = weights * float(leverage)
        gross = float(weights.abs().sum())
        if gross > max_gross:
            weights = weights * (max_gross / gross)
        scaled[date] = weights
    return dict(sorted(scaled.items()))


def bear_regime(
    btc_close: pd.Series,
    *,
    ma_window: int = 200,
    return_window: int = 30,
) -> pd.Series:
    """Return ``BTC below its MA and negative over the lookback`` per day."""
    if ma_window < 2:
        raise ValueError("ma_window must be at least 2")
    if return_window < 1:
        raise ValueError("return_window must be positive")
    close = pd.to_numeric(btc_close, errors="coerce").sort_index()
    close.index = pd.DatetimeIndex([_as_utc(value) for value in close.index])
    moving_average = close.rolling(ma_window, min_periods=ma_window).mean()
    trailing = close / close.shift(return_window) - 1.0
    return ((close < moving_average) & (trailing < 0.0)).fillna(False)


def funding_filter(
    funding_rates: pd.DataFrame | None,
    asset: str,
    *,
    as_of: pd.Timestamp,
    threshold: float = -0.0001,
    lookback: int = 3,
) -> bool:
    """Mean of the last ``lookback`` settlements must clear ``threshold``.

    Missing history fails closed.  The filter is intentionally a pure
    point-in-time function: only settlements at or before ``as_of`` are used.
    """
    if lookback < 1:
        raise ValueError("lookback must be positive")
    if funding_rates is None or funding_rates.empty or asset not in funding_rates.columns:
        return False
    frame = funding_rates.loc[:, [asset]].copy()
    frame.index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    eligible = frame.loc[frame.index <= _as_utc(as_of), asset].dropna()
    if len(eligible) < lookback:
        return False
    return bool(float(eligible.iloc[-lookback:].mean()) > float(threshold))


def _members_at(universe: pd.DataFrame, as_of: pd.Timestamp) -> set[str]:
    if universe.empty:
        return set()
    frame = universe.copy()
    frame["rebalance_date"] = pd.DatetimeIndex(
        [_as_utc(value) for value in frame["rebalance_date"]]
    )
    date = _as_utc(as_of)
    exact = frame.loc[frame["rebalance_date"] == date, "coin_id"]
    if exact.empty:
        prior = frame.loc[frame["rebalance_date"] <= date, "rebalance_date"]
        if prior.empty:
            return set()
        latest = prior.max()
        exact = frame.loc[frame["rebalance_date"] == latest, "coin_id"]
    return {str(value) for value in exact.dropna().astype(str)}


def weakest_top20(
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    as_of: pd.Timestamp,
    *,
    eligible: Set[str] | None = None,
    lookback: int = 30,
) -> str | None:
    """Return the weakest eligible point-in-time Top20 coin by trailing return."""
    if lookback < 1:
        raise ValueError("lookback must be positive")
    date = _as_utc(as_of)
    members = _members_at(universe, date)
    if eligible is not None:
        members &= {str(value) for value in eligible}
    if not members:
        return None
    price_frame = prices.copy()
    price_frame.index = pd.DatetimeIndex([_as_utc(value) for value in price_frame.index])
    price_frame = price_frame.sort_index()
    if date not in price_frame.index:
        return None
    base_date = date - pd.Timedelta(days=lookback)
    if base_date not in price_frame.index:
        candidates = price_frame.index[price_frame.index <= base_date]
        if candidates.empty:
            return None
        base_date = candidates[-1]
    current = pd.to_numeric(price_frame.loc[date].reindex(sorted(members)), errors="coerce")
    base = pd.to_numeric(price_frame.loc[base_date].reindex(sorted(members)), errors="coerce")
    trailing = (current / base - 1.0).replace([np.inf, -np.inf], np.nan).dropna()
    if trailing.empty:
        return None
    return str(trailing.idxmin())


def build_derivative_targets(
    long_targets: Mapping[pd.Timestamp, pd.Series],
    *,
    btc_close: pd.Series,
    universe: pd.DataFrame,
    prices: pd.DataFrame,
    funding_rates: pd.DataFrame | None,
    leverage: float,
    max_gross: float,
    short_asset: str | None = None,
    short_weight: float = 0.0,
    eligible: Set[str] | None = None,
    btc_asset: str = "BTC",
    btc_funding_threshold: float = -0.0001,
    short_funding_threshold: float = -0.0002,
) -> dict[pd.Timestamp, pd.Series]:
    """Combine the scaled H5 long book with the pre-registered short overlay."""
    if short_weight < 0.0:
        raise ValueError("short_weight must be non-negative")
    scaled = scale_long_targets(long_targets, leverage=leverage, max_gross=max_gross)
    regime = bear_regime(btc_close)
    targets: dict[pd.Timestamp, pd.Series] = {}
    for date, long_weights in scaled.items():
        combined = long_weights.copy()
        if short_asset is not None and short_weight > 0.0 and bool(regime.get(date, False)):
            chosen: str | None
            if short_asset == "weakest":
                chosen = weakest_top20(
                    prices,
                    universe,
                    date,
                    eligible=eligible,
                    lookback=30,
                )
            else:
                chosen = str(short_asset)
            if chosen is not None:
                btc_ok = funding_filter(
                    funding_rates,
                    btc_asset,
                    as_of=date,
                    threshold=btc_funding_threshold,
                )
                weak_ok = funding_filter(
                    funding_rates,
                    chosen,
                    as_of=date,
                    threshold=short_funding_threshold,
                )
                if btc_ok and weak_ok:
                    combined.loc[chosen] = float(combined.get(chosen, 0.0)) - float(short_weight)
        gross = float(combined.abs().sum())
        if gross > max_gross:
            combined = combined * (max_gross / gross)
        targets[date] = combined
    return targets


__all__ = [
    "bear_regime",
    "build_derivative_targets",
    "funding_filter",
    "scale_long_targets",
    "weakest_top20",
]
