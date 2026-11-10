"""Signal construction for the Bitget derivatives research track.

The long book is exactly the frozen H5 target scaled by leverage.  Optional
short overlays are added only under the pre-registered bear-regime and funding
filters.  These helpers do not select new long assets and do not broaden the
universe.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Set

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
    if funding_rates is None or funding_rates.empty:
        return False
    requested = str(asset)
    column: str | None = requested if requested in funding_rates.columns else None
    if column is None:
        matches = [
            str(candidate)
            for candidate in funding_rates.columns
            if str(candidate).casefold() == requested.casefold()
        ]
        if len(matches) != 1:
            return False
        column = matches[0]
    frame = funding_rates.loc[:, [column]].copy()
    frame.index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    eligible = frame.loc[frame.index <= _as_utc(as_of), column].dropna()
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
    exclude: Set[str] | None = None,
    lookback: int = 30,
) -> str | None:
    """Return the weakest eligible point-in-time Top20 coin by trailing return."""
    if lookback < 1:
        raise ValueError("lookback must be positive")
    date = _as_utc(as_of)
    members = _members_at(universe, date)
    if eligible is not None:
        eligible_folded = {str(value).casefold() for value in eligible}
        members = {member for member in members if member.casefold() in eligible_folded}
    if exclude:
        excluded_folded = {str(value).casefold() for value in exclude}
        members = {member for member in members if member.casefold() not in excluded_folded}
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


def _member_name(members: set[str], requested: str) -> str | None:
    """Return the exact universe spelling for a requested fixed asset."""
    if requested in members:
        return requested
    folded = requested.casefold()
    matches = [member for member in members if member.casefold() == folded]
    return matches[0] if len(matches) == 1 else None


def _target_equal(left: pd.Series, right: pd.Series) -> bool:
    """Compare sparse target vectors after aligning their coin ids."""
    index = left.index.union(right.index)
    return bool(
        np.allclose(
            left.reindex(index).fillna(0.0).to_numpy(dtype=float),
            right.reindex(index).fillna(0.0).to_numpy(dtype=float),
            rtol=1e-12,
            atol=1e-12,
        )
    )


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
    short_mode: str = "additive",
    calendar: Iterable[pd.Timestamp] | None = None,
    bear_ma_window: int = 200,
    bear_return_window: int = 30,
    short_available: Callable[[str, pd.Timestamp], bool] | None = None,
    cross_sectional_lookback: int = 14,
    cross_sectional_rebalance_days: int = 7,
    cross_sectional_short_count: int = 1,
    cross_sectional_anchor: object | None = None,
) -> dict[pd.Timestamp, pd.Series]:
    """Combine the scaled H5 long book with a pre-registered short overlay.

    ``short_mode`` is deliberately explicit:

    * ``additive`` keeps the long book and adds the short leg (the original
      overlay already rejected by the drawdown gate);
    * ``flat-only`` opens the short only when the H5 long book is entirely in
      cash;
    * ``replace`` flips the whole target to cash plus the small short when the
      bear and funding gates are active.
    * ``cross-sectional`` keeps the long book and shorts the weakest eligible
      point-in-time Top20 coin on a fixed weekly grid, excluding coins already
      held long.
    """
    if short_weight < 0.0:
        raise ValueError("short_weight must be non-negative")
    if short_mode not in {"additive", "flat-only", "replace", "cross-sectional"}:
        raise ValueError(
            "short_mode must be one of 'additive', 'flat-only', 'replace', or "
            "'cross-sectional'"
        )
    if short_mode == "cross-sectional" and short_asset not in {None, "weakest"}:
        raise ValueError("cross-sectional mode requires short_asset='weakest'")
    scaled = scale_long_targets(long_targets, leverage=leverage, max_gross=max_gross)
    regime = bear_regime(
        btc_close,
        ma_window=bear_ma_window,
        return_window=bear_return_window,
    )
    scaled_dates = sorted(scaled)
    if calendar is None:
        # Preserve the sparse event schedule when the caller does not request a
        # daily signal calendar. The research runner supplies the full index.
        evaluation_dates = scaled_dates
    else:
        evaluation_dates = sorted({_as_utc(value) for value in calendar})
    if not evaluation_dates:
        return {}
    if cross_sectional_lookback < 1:
        raise ValueError("cross_sectional_lookback must be positive")
    if cross_sectional_rebalance_days < 1:
        raise ValueError("cross_sectional_rebalance_days must be positive")
    if cross_sectional_short_count < 1:
        raise ValueError("cross_sectional_short_count must be positive")
    rebalance_anchor = (
        _as_utc(cross_sectional_anchor)
        if cross_sectional_anchor is not None
        else evaluation_dates[0]
    )

    # H5 targets are event-driven. Forward-fill them across the daily calendar
    # before evaluating the short regime, otherwise a short entry or exit is
    # delayed until the next unrelated H5 rebalance event.
    long_weights = pd.Series(dtype=float)
    long_cursor = 0
    targets: dict[pd.Timestamp, pd.Series] = {}
    previous_target: pd.Series | None = None
    active_cross_sectional_shorts: list[str] = []
    for date in evaluation_dates:
        while long_cursor < len(scaled_dates) and scaled_dates[long_cursor] <= date:
            long_weights = scaled[scaled_dates[long_cursor]].copy()
            long_cursor += 1
        combined = long_weights.copy()
        if short_mode == "cross-sectional":
            # The relative-value short is held through the week. It exits early
            # only when the coin leaves the PIT Top20 or becomes a long holding,
            # so the long and short books cannot silently net against each other.
            rebalance_due = (
                (date - rebalance_anchor).days % cross_sectional_rebalance_days == 0
            )
            long_members = {
                str(asset)
                for asset, weight in long_weights.items()
                if abs(float(weight)) > 1e-12
            }
            members = _members_at(universe, date)
            if long_cursor == 0:
                active_cross_sectional_shorts = []
            else:
                active_cross_sectional_shorts = [
                    asset
                    for asset in active_cross_sectional_shorts
                    if _member_name(members, asset) is not None
                    and asset not in long_members
                ]
            if long_cursor > 0 and rebalance_due and short_weight > 0.0:
                selected: list[str] = []
                excluded = set(long_members)
                for _ in range(cross_sectional_short_count):
                    chosen = weakest_top20(
                        prices,
                        universe,
                        date,
                        eligible=eligible,
                        exclude=excluded,
                        lookback=cross_sectional_lookback,
                    )
                    if chosen is None:
                        break
                    excluded.add(chosen)
                    if eligible is not None:
                        eligible_folded = {str(value).casefold() for value in eligible}
                        if chosen.casefold() not in eligible_folded:
                            continue
                    if short_available is not None and not short_available(chosen, date):
                        continue
                    if not funding_filter(
                        funding_rates,
                        chosen,
                        as_of=date,
                        threshold=short_funding_threshold,
                    ):
                        continue
                    selected.append(chosen)
                # A failed weekly selection exits the old basket rather than
                # retaining coins that no longer clear the screen.
                active_cross_sectional_shorts = selected
            leg_weight = float(short_weight) / float(cross_sectional_short_count)
            for asset in active_cross_sectional_shorts:
                combined.loc[asset] = -leg_weight
            gross = float(combined.abs().sum())
            if gross > max_gross:
                combined = combined * (max_gross / gross)
            if previous_target is None or not _target_equal(previous_target, combined):
                targets[date] = combined
                previous_target = combined.copy()
            continue
        # Do not open a short before the H5 book has emitted its first target:
        # that period is model warm-up, not a deliberate all-cash risk state.
        if (
            long_cursor > 0
            and short_asset is not None
            and short_weight > 0.0
            and bool(regime.get(date, False))
        ):
            long_gross = float(long_weights.abs().sum())
            if short_mode == "flat-only" and long_gross > 1e-12:
                chosen = None
            elif short_asset == "weakest":
                chosen = weakest_top20(
                    prices,
                    universe,
                    date,
                    eligible=eligible,
                    lookback=30,
                )
            else:
                chosen = _member_name(_members_at(universe, date), str(short_asset))
            if chosen is not None:
                if eligible is not None:
                    eligible_folded = {str(value).casefold() for value in eligible}
                    if chosen.casefold() not in eligible_folded:
                        chosen = None
            if chosen is not None and short_available is not None and not short_available(chosen, date):
                chosen = None
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
                    if short_mode == "replace":
                        combined = pd.Series(dtype=float)
                    combined.loc[chosen] = float(combined.get(chosen, 0.0)) - float(short_weight)
        gross = float(combined.abs().sum())
        if gross > max_gross:
            combined = combined * (max_gross / gross)
        if previous_target is None or not _target_equal(previous_target, combined):
            targets[date] = combined
            previous_target = combined.copy()
    return targets


__all__ = [
    "bear_regime",
    "build_derivative_targets",
    "funding_filter",
    "scale_long_targets",
    "weakest_top20",
]
