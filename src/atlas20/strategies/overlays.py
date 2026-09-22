"""Helpers for applying daily risk overlays to rebalance targets."""

from __future__ import annotations

import pandas as pd



def apply_daily_risk_overlay(
    base_targets: dict[pd.Timestamp, pd.Series],
    risk_on: pd.Series,
    *,
    immediate_reentry: bool = False,
    risk_off_target: pd.Series | None = None,
    initial_target: pd.Series | None = None,
) -> dict[pd.Timestamp, pd.Series]:
    """Apply a daily risk-off overlay to rebalance-date targets.

    Behavior:
    - If risk turns off on date t, add ``risk_off_target`` at t so the engine exits or parks on t+1.
    - If a scheduled rebalance lands on a risk-off date, replace its target with ``risk_off_target``.
    - By default, re-entry is allowed only on later scheduled rebalance dates when risk-on is true.
    - If ``immediate_reentry`` is true, a flip back to risk-on adds the latest desired target on that day
      so the engine can re-enter on the next trading day without waiting for the next rebalance.
    - ``initial_target`` can seed a position at the strategy start date before the first valid rebalance target.
    """
    overlay_targets: dict[pd.Timestamp, pd.Series] = {}
    zero_template: pd.Series | None = None
    normalized_base_targets = {pd.Timestamp(date): target.copy() for date, target in sorted(base_targets.items())}
    all_assets: set[str] = set()

    for _, target in normalized_base_targets.items():
        all_assets.update(map(str, target.index))
        if zero_template is None:
            zero_template = pd.Series(0.0, index=target.index)

    if risk_off_target is not None:
        all_assets.update(map(str, risk_off_target.index))
    if initial_target is not None:
        all_assets.update(map(str, initial_target.index))

    if zero_template is None:
        zero_template = pd.Series(0.0, index=sorted(all_assets))
    else:
        zero_template = zero_template.reindex(sorted(all_assets)).fillna(0.0)
    parked_target = risk_off_target.reindex(zero_template.index).fillna(0.0) if risk_off_target is not None else zero_template.copy()
    seeded_target = initial_target.reindex(zero_template.index).fillna(0.0) if initial_target is not None else None
    normalized_base_targets = {date: target.reindex(zero_template.index).fillna(0.0) for date, target in normalized_base_targets.items()}

    risk_on = risk_on.fillna(True).astype(bool)
    previous = risk_on.shift(1).fillna(risk_on.iloc[0] if not risk_on.empty else True)
    latest_desired_target = zero_template.copy()

    if seeded_target is not None and not risk_on.empty:
        start_date = pd.Timestamp(risk_on.index[0])
        overlay_targets[start_date] = seeded_target.copy() if bool(risk_on.loc[start_date]) else parked_target.copy()
        latest_desired_target = seeded_target.copy()

    for date in risk_on.index:
        current_date = pd.Timestamp(date)
        if current_date in normalized_base_targets:
            latest_desired_target = normalized_base_targets[current_date].copy()
            overlay_targets[current_date] = latest_desired_target.copy() if bool(risk_on.loc[current_date]) else parked_target.copy()

        flipped_off = bool(previous.loc[current_date]) and not bool(risk_on.loc[current_date])
        if flipped_off:
            overlay_targets[current_date] = parked_target.copy()

        flipped_on = (not bool(previous.loc[current_date])) and bool(risk_on.loc[current_date])
        if immediate_reentry and flipped_on and latest_desired_target is not None:
            overlay_targets[current_date] = latest_desired_target.copy()

    return dict(sorted(overlay_targets.items(), key=lambda item: item[0]))


def _targets_equal(left: pd.Series | None, right: pd.Series | None) -> bool:
    if left is None or right is None:
        return False
    if left.empty and right.empty:
        return True
    index = left.index.union(right.index)
    return bool(
        (left.reindex(index).fillna(0.0) - right.reindex(index).fillna(0.0))
        .abs()
        .max()
        <= 1e-12
    )


def apply_daily_asset_stop_overlay(
    base_targets: dict[pd.Timestamp, pd.Series],
    trend_on: pd.DataFrame,
) -> dict[pd.Timestamp, pd.Series]:
    """Exit an asset after it loses its own trend and wait for the next rebalance.

    The signal is evaluated on close ``t`` and the returned target is executed
    by the backtest engine on ``t+1``. A stopped asset is not re-entered between
    scheduled rebalances; this avoids repeated whipsaw trades. At the next
    scheduled rebalance, the base strategy is allowed to select it again only
    when that asset passes its own trend test on that date.

    Missing trend observations are treated as risk-off. This is deliberately
    conservative: an asset without enough history to define its stop should
    not be bought merely because the signal table has a hole.
    """
    if not base_targets:
        return {}

    normalized = {
        pd.Timestamp(date): target.fillna(0.0).clip(lower=0.0)
        for date, target in sorted(base_targets.items())
    }
    trend = trend_on.astype("boolean").fillna(False).astype(bool)
    schedule_dates = set(normalized)
    dates = sorted(set(trend.index) | schedule_dates)
    assets = sorted(
        {
            str(asset)
            for target in normalized.values()
            for asset in target.index
        }
    )

    adjusted: dict[pd.Timestamp, pd.Series] = {}
    current_target: pd.Series | None = None
    blocked: set[str] = set()
    previous: pd.Series | None = None

    for date in dates:
        timestamp = pd.Timestamp(date)
        if timestamp in normalized:
            current_target = normalized[timestamp].reindex(assets).fillna(0.0)
            blocked = {
                asset
                for asset, weight in current_target.items()
                if weight > 0.0
                and (
                    asset not in trend.columns
                    or timestamp not in trend.index
                    or not bool(trend.loc[timestamp, asset])
                )
            }

        if current_target is None:
            continue

        if timestamp not in schedule_dates:
            blocked.update(
                asset
                for asset, weight in current_target.items()
                if weight > 0.0
                and (
                    asset not in trend.columns
                    or timestamp not in trend.index
                    or not bool(trend.loc[timestamp, asset])
                )
            )

        desired = current_target.copy()
        if blocked:
            desired.loc[desired.index.intersection(sorted(blocked))] = 0.0
        if desired.sum() > 0.0:
            desired = desired / desired.sum()
        else:
            desired = pd.Series(dtype=float)

        if timestamp in schedule_dates or not _targets_equal(desired, previous):
            adjusted[timestamp] = desired.copy()
        previous = desired.copy()

    return dict(sorted(adjusted.items(), key=lambda item: item[0]))
