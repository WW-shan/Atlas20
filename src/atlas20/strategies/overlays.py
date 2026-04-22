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
