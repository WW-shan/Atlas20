"""Signal construction for the Bitget derivatives research track.

The long book is exactly the frozen H5 target scaled by leverage.  Optional
short overlays are added only under the pre-registered bear-regime and funding
filters.  These helpers do not select new long assets and do not broaden the
universe.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Set
import heapq

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


def funding_rank_percentile(
    funding_rates: pd.DataFrame | None,
    universe: pd.DataFrame,
    asset: str,
    *,
    as_of: pd.Timestamp,
    eligible: Set[str] | None,
    lookback_days: int = 7,
    min_assets: int = 5,
) -> float | None:
    """Return an asset's PIT Top20 funding percentile, or None if incomplete."""
    if funding_rates is None or funding_rates.empty:
        return None
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    if min_assets < 2:
        raise ValueError("min_assets must be at least two")

    date = _as_utc(as_of)
    members = _members_at(universe, date)
    if eligible is not None:
        eligible_folded = {str(value).casefold() for value in eligible}
        members = {
            member for member in members if member.casefold() in eligible_folded
        }
    if not members:
        return None

    frame = funding_rates.copy()
    frame.index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
    window = frame.loc[
        (frame.index <= date)
        & (frame.index >= date - pd.Timedelta(days=lookback_days))
    ]
    columns_by_fold: dict[str, list[object]] = {}
    for column in frame.columns:
        columns_by_fold.setdefault(str(column).casefold(), []).append(column)

    means: dict[str, float] = {}
    for member in members:
        columns = columns_by_fold.get(member.casefold(), [])
        if len(columns) != 1:
            continue
        values = pd.to_numeric(window[columns[0]], errors="coerce").dropna()
        if values.empty:
            continue
        means[member] = float(values.mean())

    requested = next(
        (member for member in means if member.casefold() == str(asset).casefold()),
        None,
    )
    if requested is None or len(means) < min_assets:
        return None
    return float(pd.Series(means, dtype=float).rank(pct=True)[requested])


def funding_mean(
    funding_rates: pd.DataFrame | None,
    asset: str,
    *,
    as_of: pd.Timestamp,
    lookback_days: int = 7,
) -> float | None:
    """Return an asset's mean funding over a point-in-time trailing window."""
    if funding_rates is None or funding_rates.empty:
        return None
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")

    date = _as_utc(as_of)
    columns = [
        column
        for column in funding_rates.columns
        if str(column).casefold() == str(asset).casefold()
    ]
    if len(columns) != 1:
        return None
    frame = funding_rates.copy()
    frame.index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
    window = frame.loc[
        (frame.index <= date)
        & (frame.index >= date - pd.Timedelta(days=lookback_days)),
        columns[0],
    ]
    values = pd.to_numeric(window, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.mean())


def build_cross_sectional_funding_short_schedule(
    universe: pd.DataFrame,
    h5_targets: Mapping[pd.Timestamp, pd.Series],
    *,
    calendar: Iterable[pd.Timestamp],
    funding_rates: pd.DataFrame | None,
    eligible: Set[str] | None,
    short_available: Callable[[str, pd.Timestamp], bool] | None = None,
    lookback_days: int = 7,
    rebalance_days: int = 7,
    short_count: int = 4,
    per_asset_weight: float = 0.0625,
    min_assets: int = 5,
    anchor: object | None = None,
) -> dict[pd.Timestamp, pd.Series]:
    """Build a weekly positive-funding short basket outside the H5 long book."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    if rebalance_days < 1:
        raise ValueError("rebalance_days must be positive")
    if short_count < 1:
        raise ValueError("short_count must be positive")
    if min_assets < 2:
        raise ValueError("min_assets must be at least two")
    if not np.isfinite(per_asset_weight) or per_asset_weight <= 0.0:
        raise ValueError("per_asset_weight must be positive and finite")

    evaluation_dates = sorted({_as_utc(value) for value in calendar})
    if not evaluation_dates:
        return {}
    rebalance_anchor = _as_utc(anchor) if anchor is not None else evaluation_dates[0]

    normalized_h5: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in h5_targets.items():
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
            raise ValueError("h5 target weights must be finite")
        if (target < 0.0).any():
            raise ValueError("h5 target weights must be non-negative")
        normalized_h5[date] = target.astype(float)
    h5_dates = sorted(normalized_h5)

    eligible_folded = (
        {str(value).casefold() for value in eligible}
        if eligible is not None
        else None
    )
    schedule: dict[pd.Timestamp, pd.Series] = {}
    long_weights = pd.Series(dtype=float)
    cursor = 0
    for date in evaluation_dates:
        while cursor < len(h5_dates) and h5_dates[cursor] <= date:
            long_weights = normalized_h5[h5_dates[cursor]]
            cursor += 1
        if date < rebalance_anchor:
            continue
        if (date.normalize() - rebalance_anchor.normalize()).days % rebalance_days:
            continue

        held = {
            str(asset).casefold()
            for asset in long_weights.loc[long_weights > 1e-15].index
        }
        members = _members_at(universe, date)
        funding_by_asset: dict[str, float] = {}
        valid_funding = 0
        for asset in sorted(members):
            folded = asset.casefold()
            if folded in held:
                continue
            if eligible_folded is not None and folded not in eligible_folded:
                continue
            if short_available is not None and not short_available(asset, date):
                continue
            mean = funding_mean(
                funding_rates,
                asset,
                as_of=date,
                lookback_days=lookback_days,
            )
            if mean is None:
                continue
            valid_funding += 1
            if mean > 0.0:
                funding_by_asset[asset] = mean

        selected: list[str] = []
        if valid_funding >= min_assets:
            selected = [
                asset
                for asset, _ in sorted(
                    funding_by_asset.items(),
                    key=lambda item: (-item[1], item[0].casefold()),
                )[:short_count]
            ]
        schedule[date] = pd.Series(
            float(per_asset_weight),
            index=selected,
            dtype=float,
        )
    return schedule


def _ranked_weakest_top20(
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    as_of: pd.Timestamp,
    *,
    eligible: Set[str] | None = None,
    exclude: Set[str] | None = None,
    lookback: int = 30,
) -> list[str]:
    """Rank eligible point-in-time Top20 coins from weakest trailing return."""
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
        return []
    price_frame = prices.copy()
    price_frame.index = pd.DatetimeIndex([_as_utc(value) for value in price_frame.index])
    price_frame = price_frame.sort_index()
    if date not in price_frame.index:
        return []
    base_date = date - pd.Timedelta(days=lookback)
    if base_date not in price_frame.index:
        candidates = price_frame.index[price_frame.index <= base_date]
        if candidates.empty:
            return []
        base_date = candidates[-1]
    current = pd.to_numeric(price_frame.loc[date].reindex(sorted(members)), errors="coerce")
    base = pd.to_numeric(price_frame.loc[base_date].reindex(sorted(members)), errors="coerce")
    trailing = (current / base - 1.0).replace([np.inf, -np.inf], np.nan).dropna()
    if trailing.empty:
        return []
    return [str(value) for value in trailing.sort_values(kind="stable").index]


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
    ranked = _ranked_weakest_top20(
        prices,
        universe,
        as_of,
        eligible=eligible,
        exclude=exclude,
        lookback=lookback,
    )
    return ranked[0] if ranked else None


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


def _combine_sleeve_targets(
    sleeves: Mapping[str, tuple[Mapping[pd.Timestamp, pd.Series], float]],
    *,
    max_gross: float,
    cap_total_gross: bool,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Forward-fill signed sleeves and apply the selected gross-cap definition."""
    if not np.isfinite(max_gross) or max_gross <= 0.0:
        raise ValueError("max_gross must be positive and finite")
    if not sleeves:
        return {}, pd.DataFrame()

    schedules: dict[str, dict[pd.Timestamp, pd.Series]] = {}
    multipliers: dict[str, float] = {}
    event_dates: set[pd.Timestamp] = set()
    for name, (raw_schedule, multiplier) in sleeves.items():
        if not np.isfinite(multiplier):
            raise ValueError(f"{name}: multiplier must be finite")
        schedule: dict[pd.Timestamp, pd.Series] = {}
        for raw_date, raw_target in raw_schedule.items():
            date = _as_utc(raw_date)
            target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
            target.index = target.index.astype(str)
            if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
                raise ValueError(f"{name}: target weights must be finite")
            schedule[date] = target.astype(float)
            event_dates.add(date)
        schedules[name] = dict(sorted(schedule.items()))
        multipliers[name] = float(multiplier)

    dates = sorted(event_dates)
    if not dates:
        return {}, pd.DataFrame()
    states: dict[str, pd.Series] = {
        name: pd.Series(dtype=float) for name in schedules
    }
    cursors = {name: 0 for name in schedules}
    combined_targets: dict[pd.Timestamp, pd.Series] = {}
    audit_rows: list[dict[str, object]] = []
    for date in dates:
        union_index = pd.Index([], dtype=object)
        for name, schedule in schedules.items():
            schedule_dates = list(schedule)
            cursor = cursors[name]
            while cursor < len(schedule_dates) and schedule_dates[cursor] <= date:
                states[name] = schedule[schedule_dates[cursor]].copy()
                cursor += 1
            cursors[name] = cursor
            union_index = union_index.union(states[name].index)
        combined = pd.Series(0.0, index=union_index, dtype=float)
        long_gross = 0.0
        short_gross = 0.0
        for name in schedules:
            if states[name].empty:
                continue
            contribution = states[name].reindex(union_index).fillna(0.0) * multipliers[name]
            combined = combined.add(contribution, fill_value=0.0)
            if cap_total_gross:
                long_gross += float(contribution.clip(lower=0.0).sum())
                short_gross += float(-contribution.clip(upper=0.0).sum())
        combined = combined[combined.abs() > 1e-15]
        net_gross = float(combined.abs().sum())
        total_gross = long_gross + short_gross
        gross = total_gross if cap_total_gross else net_gross
        scale = min(1.0, max_gross / gross) if gross > 0.0 else 0.0
        combined *= scale
        combined_targets[date] = combined
        audit_rows.append(
            {
                "date": date,
                "long_gross": long_gross,
                "short_gross": short_gross,
                "total_gross": total_gross,
                "net_gross": net_gross,
                "scale": scale,
                "scaled_total_gross": total_gross * scale,
                "scaled_net_gross": net_gross * scale,
            }
        )
    audit = pd.DataFrame(audit_rows).set_index("date")
    return combined_targets, audit


def combine_sleeve_targets(
    sleeves: Mapping[str, tuple[Mapping[pd.Timestamp, pd.Series], float]],
    *,
    max_gross: float,
) -> dict[pd.Timestamp, pd.Series]:
    """Forward-fill signed sleeve targets and cap net absolute exposure."""
    targets, _ = _combine_sleeve_targets(
        sleeves,
        max_gross=max_gross,
        cap_total_gross=False,
    )
    return targets


def combine_sleeve_targets_by_total_gross(
    sleeves: Mapping[str, tuple[Mapping[pd.Timestamp, pd.Series], float]],
    *,
    max_gross: float,
) -> dict[pd.Timestamp, pd.Series]:
    """Cap long plus short exposure before the broker nets same-asset legs."""
    targets, _ = _combine_sleeve_targets(
        sleeves,
        max_gross=max_gross,
        cap_total_gross=True,
    )
    return targets


def combine_sleeve_targets_by_total_gross_with_audit(
    sleeves: Mapping[str, tuple[Mapping[pd.Timestamp, pd.Series], float]],
    *,
    max_gross: float,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Return capped targets plus sleeve gross before same-asset netting."""
    return _combine_sleeve_targets(
        sleeves,
        max_gross=max_gross,
        cap_total_gross=True,
    )


CASH_SLEEVE_H4_WEIGHT = 0.20
CASH_SLEEVE_SECTOR_SHORT_WEIGHT = 0.20
CASH_SLEEVE_MAX_GROSS = 0.95


def build_cash_sleeve_targets(
    h5_targets: Mapping[pd.Timestamp, pd.Series],
    h4_targets: Mapping[pd.Timestamp, pd.Series],
    sector_targets: Mapping[pd.Timestamp, pd.Series],
) -> dict[pd.Timestamp, pd.Series]:
    """Build the pre-registered H5+H4-minus-sector candidate target."""
    return combine_sleeve_targets(
        {
            "h5": (h5_targets, 1.0),
            "h4": (h4_targets, CASH_SLEEVE_H4_WEIGHT),
            "sector_short": (sector_targets, -CASH_SLEEVE_SECTOR_SHORT_WEIGHT),
        },
        max_gross=CASH_SLEEVE_MAX_GROSS,
    )


EXIT_SHORT_HOLDING_DAYS = 21


def build_exit_short_schedule(
    h5_targets: Mapping[pd.Timestamp, pd.Series],
    *,
    holding_days: int = EXIT_SHORT_HOLDING_DAYS,
    eligible_by_date: Mapping[pd.Timestamp, Set[str]],
    per_asset_weight: float | None = None,
    entry_allowed: Callable[[str, pd.Timestamp], bool] | None = None,
) -> dict[pd.Timestamp, pd.Series]:
    """Short H5 exits for a fixed hold, closing early when an asset re-enters."""
    if holding_days < 1:
        raise ValueError("holding_days must be positive")
    if per_asset_weight is not None and (
        not np.isfinite(per_asset_weight) or per_asset_weight <= 0.0
    ):
        raise ValueError("per_asset_weight must be positive and finite")

    normalized_h5: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in h5_targets.items():
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
            raise ValueError("h5 target weights must be finite")
        normalized_h5[date] = target.astype(float)
    normalized_eligible = {
        _as_utc(date): {str(asset) for asset in assets}
        for date, assets in eligible_by_date.items()
    }

    pending = list(normalized_h5)
    heapq.heapify(pending)
    processed: set[pd.Timestamp] = set()
    active: dict[str, pd.Timestamp] = {}
    previous_holdings: set[str] | None = None
    schedule: dict[pd.Timestamp, pd.Series] = {}
    while pending:
        date = pd.Timestamp(heapq.heappop(pending))
        if date in processed:
            continue
        processed.add(date)

        for asset, expiry in list(active.items()):
            if expiry <= date:
                active.pop(asset, None)

        if date in normalized_h5:
            target = normalized_h5[date]
            holdings = {
                str(asset)
                for asset, weight in target.items()
                if float(weight) > 1e-15
            }
            for asset in holdings:
                active.pop(asset, None)
            if previous_holdings is not None:
                eligible = normalized_eligible.get(date, set())
                for asset in sorted(previous_holdings - holdings):
                    if asset not in eligible or asset in active:
                        continue
                    if entry_allowed is not None and not entry_allowed(asset, date):
                        continue
                    expiry = date + pd.Timedelta(days=holding_days)
                    active[asset] = expiry
                    if expiry not in processed:
                        heapq.heappush(pending, expiry)
            previous_holdings = holdings

        if active:
            weight = (
                float(per_asset_weight)
                if per_asset_weight is not None
                else 1.0 / float(len(active))
            )
            weights = pd.Series(weight, index=sorted(active), dtype=float)
        else:
            weights = pd.Series(dtype=float)
        schedule[date] = weights
    return dict(sorted(schedule.items()))


def build_cross_sectional_weak_short_schedule(
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    h5_targets: Mapping[pd.Timestamp, pd.Series],
    *,
    calendar: Iterable[pd.Timestamp],
    funding_rates: pd.DataFrame | None,
    eligible: Set[str] | None,
    short_available: Callable[[str, pd.Timestamp], bool] | None = None,
    lookback: int = 14,
    rebalance_days: int = 7,
    short_count: int = 4,
    per_asset_weight: float = 0.025,
    funding_threshold: float = -0.0002,
    funding_lookback: int = 3,
    anchor: object | None = None,
) -> dict[pd.Timestamp, pd.Series]:
    """Build the pre-registered weekly bottom-four Top20 short schedule."""
    if lookback < 1:
        raise ValueError("lookback must be positive")
    if rebalance_days < 1:
        raise ValueError("rebalance_days must be positive")
    if short_count < 1:
        raise ValueError("short_count must be positive")
    if not np.isfinite(per_asset_weight) or per_asset_weight <= 0.0:
        raise ValueError("per_asset_weight must be positive and finite")
    if funding_lookback < 1:
        raise ValueError("funding_lookback must be positive")

    evaluation_dates = sorted({_as_utc(value) for value in calendar})
    if not evaluation_dates:
        return {}
    rebalance_anchor = (
        _as_utc(anchor) if anchor is not None else evaluation_dates[0]
    )

    normalized_h5: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in h5_targets.items():
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
            raise ValueError("h5 target weights must be finite")
        if (target < 0.0).any():
            raise ValueError("h5 target weights must be non-negative")
        normalized_h5[date] = target.astype(float)
    h5_dates = sorted(normalized_h5)

    schedule: dict[pd.Timestamp, pd.Series] = {}
    long_weights = pd.Series(dtype=float)
    cursor = 0
    for date in evaluation_dates:
        while cursor < len(h5_dates) and h5_dates[cursor] <= date:
            long_weights = normalized_h5[h5_dates[cursor]]
            cursor += 1
        if date < rebalance_anchor:
            continue
        if (date.normalize() - rebalance_anchor.normalize()).days % rebalance_days:
            continue

        holdings = set(long_weights.loc[long_weights > 1e-15].index.astype(str))
        ranked = _ranked_weakest_top20(
            prices,
            universe,
            date,
            eligible=eligible,
            exclude=holdings,
            lookback=lookback,
        )
        selected: list[str] = []
        for asset in ranked:
            if short_available is not None and not short_available(asset, date):
                continue
            if not funding_filter(
                funding_rates,
                asset,
                as_of=date,
                threshold=funding_threshold,
                lookback=funding_lookback,
            ):
                continue
            selected.append(asset)
            if len(selected) >= short_count:
                break
        schedule[date] = pd.Series(
            float(per_asset_weight), index=selected, dtype=float
        )
    return schedule


def combine_fixed_risk_short_schedules(
    schedules: Mapping[str, Mapping[pd.Timestamp, pd.Series]],
    *,
    per_asset_weight: float,
) -> dict[pd.Timestamp, pd.Series]:
    """Union fixed-risk short sleeves without double sizing an asset."""
    if not np.isfinite(per_asset_weight) or per_asset_weight <= 0.0:
        raise ValueError("per_asset_weight must be positive and finite")

    normalized: dict[str, dict[pd.Timestamp, pd.Series]] = {}
    event_dates: set[pd.Timestamp] = set()
    for name, raw_schedule in schedules.items():
        sleeve: dict[pd.Timestamp, pd.Series] = {}
        for raw_date, raw_target in raw_schedule.items():
            date = _as_utc(raw_date)
            target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
            target.index = target.index.astype(str)
            if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
                raise ValueError(f"{name}: target weights must be finite")
            if (target < 0.0).any():
                raise ValueError(f"{name}: short target weights must be non-negative")
            if (target > per_asset_weight + 1e-12).any():
                raise ValueError(
                    f"{name}: short target weight exceeds per-asset cap"
                )
            sleeve[date] = target.astype(float)
            event_dates.add(date)
        normalized[str(name)] = dict(sorted(sleeve.items()))

    if not event_dates:
        return {}
    states: dict[str, pd.Series] = {
        name: pd.Series(dtype=float) for name in normalized
    }
    cursors = {name: 0 for name in normalized}
    combined_targets: dict[pd.Timestamp, pd.Series] = {}
    previous: pd.Series | None = None
    for date in sorted(event_dates):
        for name, sleeve in normalized.items():
            dates = list(sleeve)
            cursor = cursors[name]
            while cursor < len(dates) and dates[cursor] <= date:
                states[name] = sleeve[dates[cursor]].copy()
                cursor += 1
            cursors[name] = cursor

        assets = pd.Index([], dtype=object)
        for state in states.values():
            assets = assets.union(state.index)
        weights: dict[str, float] = {}
        for asset in assets:
            weight = max(
                (float(state.get(asset, 0.0)) for state in states.values()),
                default=0.0,
            )
            if weight > 1e-15:
                weights[str(asset)] = float(weight)
        combined = pd.Series(weights, dtype=float).sort_index()
        if previous is None or not _target_equal(previous, combined):
            combined_targets[date] = combined
            previous = combined.copy()
    return combined_targets


def combine_long_with_cash_budgeted_short(
    long_targets: Mapping[pd.Timestamp, pd.Series],
    short_targets: Mapping[pd.Timestamp, pd.Series],
    *,
    max_total_gross: float,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Use only unused long gross for shorts; never scale down the long book."""
    if not np.isfinite(max_total_gross) or max_total_gross <= 0.0:
        raise ValueError("max_total_gross must be positive and finite")

    schedules: dict[str, dict[pd.Timestamp, pd.Series]] = {"long": {}, "short": {}}
    for name, raw_schedule in (("long", long_targets), ("short", short_targets)):
        for raw_date, raw_target in raw_schedule.items():
            date = _as_utc(raw_date)
            target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
            target.index = target.index.astype(str)
            if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
                raise ValueError(f"{name}: target weights must be finite")
            if (target < 0.0).any():
                raise ValueError(f"{name}: target weights must be non-negative")
            schedules[name][date] = target.astype(float)

    dates = sorted(set(schedules["long"]) | set(schedules["short"]))
    states: dict[str, pd.Series] = {
        "long": pd.Series(dtype=float),
        "short": pd.Series(dtype=float),
    }
    cursors = {"long": 0, "short": 0}
    targets: dict[pd.Timestamp, pd.Series] = {}
    audit_rows: list[dict[str, object]] = []
    for date in dates:
        union_index = pd.Index([], dtype=object)
        for name in ("long", "short"):
            schedule_dates = list(schedules[name])
            cursor = cursors[name]
            while cursor < len(schedule_dates) and schedule_dates[cursor] <= date:
                states[name] = schedules[name][schedule_dates[cursor]].copy()
                cursor += 1
            cursors[name] = cursor
            union_index = union_index.union(states[name].index)

        long = states["long"].reindex(union_index).fillna(0.0)
        short = states["short"].reindex(union_index).fillna(0.0)
        long_gross = float(long.sum())
        requested_short_gross = float(short.sum())
        long_scale = (
            min(1.0, max_total_gross / long_gross)
            if long_gross > max_total_gross + 1e-12
            else 1.0
        )
        long = long * long_scale
        scaled_long_gross = long_gross * long_scale
        available = max(0.0, max_total_gross - scaled_long_gross)
        short_scale = (
            min(1.0, available / requested_short_gross)
            if requested_short_gross > 0.0
            else 0.0
        )
        funded_short = short * short_scale
        combined = long - funded_short
        combined = combined[combined.abs() > 1e-15]
        targets[date] = combined
        audit_rows.append(
            {
                "date": date,
                "long_gross": long_gross,
                "long_scale": long_scale,
                "scaled_long_gross": scaled_long_gross,
                "requested_short_gross": requested_short_gross,
                "short_scale": short_scale,
                "funded_short_gross": requested_short_gross * short_scale,
                "total_gross": scaled_long_gross + requested_short_gross * short_scale,
                "net_gross": float(combined.abs().sum()),
            }
        )
    audit = pd.DataFrame(audit_rows).set_index("date")
    return targets, audit


MONTHLY_SECTOR_SHORT_WEIGHT = 1.0
MONTHLY_SECTOR_SHORT_MAX_GROSS = 0.95


def build_monthly_sector_short_targets(
    h5_targets: Mapping[pd.Timestamp, pd.Series],
    sector_targets: Mapping[pd.Timestamp, pd.Series],
) -> dict[pd.Timestamp, pd.Series]:
    """Build the pre-registered H5-minus-monthly-sector short candidate."""
    return combine_sleeve_targets_by_total_gross(
        {
            "h5": (h5_targets, 1.0),
            "sector_short": (sector_targets, -MONTHLY_SECTOR_SHORT_WEIGHT),
        },
        max_gross=MONTHLY_SECTOR_SHORT_MAX_GROSS,
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
    cross_sectional_hold_rank: int | None = None,
    cross_sectional_anchor: object | None = None,
    cross_sectional_entry_allowed: Callable[[pd.Timestamp], bool] | None = None,
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
    if cross_sectional_hold_rank is not None:
        if cross_sectional_hold_rank < cross_sectional_short_count:
            raise ValueError(
                "cross_sectional_hold_rank must be at least "
                "cross_sectional_short_count"
            )
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
                if (
                    cross_sectional_entry_allowed is not None
                    and not cross_sectional_entry_allowed(date)
                ):
                    active_cross_sectional_shorts = []
                else:
                    eligible_folded = (
                        {str(value).casefold() for value in eligible}
                        if eligible is not None
                        else None
                    )
                    ranked = _ranked_weakest_top20(
                        prices,
                        universe,
                        date,
                        eligible=eligible,
                        exclude=set(long_members),
                        lookback=cross_sectional_lookback,
                    )
                    investable: list[str] = []
                    for chosen in ranked:
                        if eligible_folded is not None and chosen.casefold() not in eligible_folded:
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
                        investable.append(chosen)

                    if cross_sectional_hold_rank is None:
                        selected = investable[:cross_sectional_short_count]
                    else:
                        hold_set = set(investable[:cross_sectional_hold_rank])
                        selected = [
                            asset
                            for asset in active_cross_sectional_shorts
                            if asset in hold_set
                        ]
                        selected.extend(
                            asset
                            for asset in investable
                            if asset not in selected
                        )
                        selected = selected[:cross_sectional_short_count]
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
    "build_cash_sleeve_targets",
    "build_cross_sectional_weak_short_schedule",
    "build_exit_short_schedule",
    "combine_fixed_risk_short_schedules",
    "combine_long_with_cash_budgeted_short",
    "EXIT_SHORT_HOLDING_DAYS",
    "build_monthly_sector_short_targets",
    "CASH_SLEEVE_H4_WEIGHT",
    "CASH_SLEEVE_MAX_GROSS",
    "CASH_SLEEVE_SECTOR_SHORT_WEIGHT",
    "combine_sleeve_targets",
    "combine_sleeve_targets_by_total_gross",
    "combine_sleeve_targets_by_total_gross_with_audit",
    "MONTHLY_SECTOR_SHORT_MAX_GROSS",
    "MONTHLY_SECTOR_SHORT_WEIGHT",
    "bear_regime",
    "build_derivative_targets",
    "funding_filter",
    "funding_rank_percentile",
    "scale_long_targets",
    "weakest_top20",
]
