"""Fast single-asset backtest used by large event-driven parameter sweeps.

The production engine is deliberately general and handles arbitrary portfolios.
That generality is useful for reporting but expensive when a research grid
contains thousands of one-asset paths.  This helper reproduces the engine's
T+1 execution, turnover cost, and no-leverage semantics for the restricted
case of a 0/1 asset target.  It is only a research accelerator; the final
candidate is still checked against :func:`atlas20.backtest.engine.run_backtest`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SingleAssetBacktestResult:
    daily_returns: pd.Series
    turnover: pd.Series
    holdings: pd.Series


@dataclass(frozen=True)
class SingleAssetWeightBacktestResult:
    daily_returns: pd.Series
    turnover: pd.Series
    holdings: pd.Series
    weights: pd.Series


def simulate_single_asset_weights(
    asset_returns: pd.DataFrame,
    target_assets: pd.Series,
    target_weights: pd.Series,
    *,
    total_cost_bps: float,
    missing_return_policy: str = "error",
    missing_return_fill: float = -1.0,
) -> SingleAssetWeightBacktestResult:
    """Simulate one long-only asset with a fractional target weight.

    This is the fractional-exposure counterpart to
    :func:`simulate_single_asset_targets`.  Weights are capped at 1.0, so the
    helper cannot introduce leverage.  It is used for volatility-target and
    risk-budget research where the selected asset may be held at less than
    100% exposure.
    """
    if total_cost_bps < 0:
        raise ValueError("total_cost_bps must be non-negative")
    if missing_return_policy not in {"error", "fill"}:
        raise ValueError("missing_return_policy must be 'error' or 'fill'")

    returns = asset_returns.copy().sort_index()
    assets = target_assets.reindex(returns.index).astype("object")
    weights = pd.to_numeric(target_weights.reindex(returns.index), errors="coerce").fillna(0.0)
    if ((weights < 0.0) | (weights > 1.0)).any():
        raise ValueError("target weights must be between 0 and 1")

    fee_rate = float(total_cost_bps) / 10_000.0
    return_values = returns.to_numpy(dtype=float, copy=False)
    asset_values = assets.to_numpy(dtype=object, copy=False)
    weight_values = weights.to_numpy(dtype=float, copy=False)
    column_positions = {str(column): position for position, column in enumerate(returns.columns)}
    current_asset: str | None = None
    current_weight = 0.0
    pending_asset: str | None = None
    pending_weight = 0.0
    pending_target_set = False
    daily_returns: list[float] = []
    turnovers: list[float] = []
    holdings: list[float] = []
    held_weights: list[float] = []

    for row_position, date in enumerate(returns.index):
        if row_position > 0:
            raw_asset = asset_values[row_position - 1]
            pending_asset = None if pd.isna(raw_asset) or str(raw_asset) in {"", "__cash__"} else str(raw_asset)
            pending_weight = float(weight_values[row_position - 1]) if pending_asset is not None else 0.0
            pending_target_set = True

        turnover = 0.0
        cost = 0.0
        if pending_target_set:
            next_asset = pending_asset if pending_weight > 0.0 else None
            next_weight = pending_weight if next_asset is not None else 0.0
            if next_asset == current_asset:
                turnover = abs(next_weight - current_weight)
            else:
                turnover = abs(current_weight) + abs(next_weight)
            cost = turnover * fee_rate
            current_asset = next_asset
            current_weight = next_weight
            pending_target_set = False

        asset_return = 0.0
        if current_asset is not None and current_weight > 0.0:
            column_position = column_positions.get(current_asset)
            if column_position is None:
                raise ValueError(f"Target asset {current_asset!r} is absent from asset_returns")
            raw_return = return_values[row_position, column_position]
            if pd.isna(raw_return):
                if missing_return_policy == "error":
                    raise ValueError(
                        f"Missing return for held asset {current_asset!r} on {pd.Timestamp(date).date()}"
                    )
                asset_return = float(missing_return_fill)
            else:
                asset_return = float(raw_return)

        gross_return = current_weight * asset_return
        net_return = (1.0 - cost) * (1.0 + gross_return) - 1.0
        daily_returns.append(net_return)
        turnovers.append(turnover)
        holdings.append(1.0 if current_asset is not None and current_weight > 0.0 else 0.0)
        held_weights.append(current_weight)

    return SingleAssetWeightBacktestResult(
        daily_returns=pd.Series(daily_returns, index=returns.index, name="daily_return"),
        turnover=pd.Series(turnovers, index=returns.index, name="turnover"),
        holdings=pd.Series(holdings, index=returns.index, name="holdings"),
        weights=pd.Series(held_weights, index=returns.index, name="weight"),
    )


def simulate_single_asset_targets(
    asset_returns: pd.DataFrame,
    target_assets: pd.Series,
    *,
    total_cost_bps: float,
    missing_return_policy: str = "error",
    missing_return_fill: float = -1.0,
) -> SingleAssetBacktestResult:
    """Simulate a long-only 0/1 asset target with T+1 execution.

    ``target_assets`` is indexed by signal date; an empty string or missing
    value means cash.  A full switch has turnover 2 (sell plus buy), matching
    the production engine's ``sum(abs(target - current))`` convention.
    """
    if total_cost_bps < 0:
        raise ValueError("total_cost_bps must be non-negative")
    if missing_return_policy not in {"error", "fill"}:
        raise ValueError("missing_return_policy must be 'error' or 'fill'")

    returns = asset_returns.copy().sort_index()
    targets = target_assets.reindex(returns.index).astype("object")
    fee_rate = float(total_cost_bps) / 10_000.0
    return_values = returns.to_numpy(dtype=float, copy=False)
    target_values = targets.to_numpy(dtype=object, copy=False)
    column_positions = {str(column): position for position, column in enumerate(returns.columns)}
    current_asset: str | None = None
    pending_asset: str | None = None
    pending_target_set = False
    daily_returns: list[float] = []
    turnovers: list[float] = []
    holdings: list[float] = []

    for row_position, date in enumerate(returns.index):
        if row_position > 0:
            raw_target = target_values[row_position - 1]
            pending_asset = None if pd.isna(raw_target) or str(raw_target) == "" else str(raw_target)
            pending_target_set = True

        turnover = 0.0
        cost = 0.0
        if pending_target_set:
            next_asset = None if pending_asset == "__cash__" else pending_asset
            if next_asset != current_asset:
                turnover = 1.0 if current_asset is None or next_asset is None else 2.0
                cost = turnover * fee_rate
                current_asset = next_asset
            pending_target_set = False

        asset_return = 0.0
        if current_asset is not None:
            column_position = column_positions.get(current_asset)
            if column_position is None:
                raise ValueError(f"Target asset {current_asset!r} is absent from asset_returns")
            raw_return = return_values[row_position, column_position]
            if pd.isna(raw_return):
                if missing_return_policy == "error":
                    raise ValueError(
                        f"Missing return for held asset {current_asset!r} on {pd.Timestamp(date).date()}"
                    )
                asset_return = float(missing_return_fill)
            else:
                asset_return = float(raw_return)

        net_return = (1.0 - cost) * (1.0 + asset_return) - 1.0
        daily_returns.append(net_return)
        turnovers.append(turnover)
        holdings.append(1.0 if current_asset is not None else 0.0)

    return SingleAssetBacktestResult(
        daily_returns=pd.Series(daily_returns, index=returns.index, name="daily_return"),
        turnover=pd.Series(turnovers, index=returns.index, name="turnover"),
        holdings=pd.Series(holdings, index=returns.index, name="holdings"),
    )
