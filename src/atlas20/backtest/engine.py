"""Transparent pandas-based portfolio backtest engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from atlas20.config import FrictionConfig


@dataclass
class BacktestResult:
    """Container for one strategy backtest result."""

    name: str
    daily_returns: pd.Series
    equity_curve: pd.Series
    drawdown: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    holdings_count: pd.Series
    sector_exposure: pd.DataFrame
    rebalance_targets: pd.DataFrame



def cap_and_normalize(weights: pd.Series, max_weight: float) -> pd.Series:
    """Apply a simple iterative per-asset cap while keeping weights summing to one."""
    weights = weights.fillna(0.0).clip(lower=0.0)
    if weights.sum() <= 0:
        return weights * 0.0
    weights = weights / weights.sum()

    if max_weight >= 1.0:
        return weights

    for _ in range(10):
        over = weights > max_weight
        if not over.any():
            break
        capped = weights.where(~over, max_weight)
        deficit = 1.0 - capped.sum()
        under = ~over & (weights > 0)
        if deficit <= 0 or not under.any():
            weights = capped / capped.sum()
            break
        redistributed = capped.copy()
        redistributed.loc[under] = capped.loc[under] / capped.loc[under].sum() * deficit
        weights = redistributed
    return weights / weights.sum() if weights.sum() > 0 else weights



def aggregate_sector_exposure(weights: pd.DataFrame, sector_by_coin: pd.Series) -> pd.DataFrame:
    """Aggregate daily coin weights into daily sector exposure."""
    sector_map = sector_by_coin.reindex(weights.columns).fillna("Other")
    exposure = {}
    for sector in sorted(sector_map.unique()):
        cols = sector_map[sector_map == sector].index.tolist()
        exposure[sector] = weights[cols].sum(axis=1)
    return pd.DataFrame(exposure, index=weights.index)



def run_backtest(
    name: str,
    asset_returns: pd.DataFrame,
    rebalance_targets: dict[pd.Timestamp, pd.Series],
    sector_by_coin: pd.Series,
    friction: FrictionConfig,
    initial_capital: float,
    gross_target_exposure: float = 1.0,
) -> BacktestResult:
    """Run a long-only backtest with rebalances effective one day after signal generation."""
    returns = asset_returns.copy().sort_index()
    columns = returns.columns
    current_weights = pd.Series(0.0, index=columns)
    fee_rate = (friction.fee_bps + friction.slippage_bps) / 10_000.0

    daily_returns = pd.Series(0.0, index=returns.index, name=name)
    equity = pd.Series(index=returns.index, dtype=float, name=name)
    turnover = pd.Series(0.0, index=returns.index, name=name)
    holdings = pd.Series(0.0, index=returns.index, name=name)
    weights_history = pd.DataFrame(0.0, index=returns.index, columns=columns)
    target_rows: list[pd.DataFrame] = []

    pending_target: pd.Series | None = None
    portfolio_value = initial_capital
    previous_date: pd.Timestamp | None = None

    for date in returns.index:
        day_ret = returns.loc[date].reindex(columns).fillna(friction.missing_return_fill)

        if previous_date is not None and previous_date in rebalance_targets:
            pending_target = rebalance_targets[previous_date].reindex(columns).fillna(0.0)
            pending_target = cap_and_normalize(pending_target, friction.max_weight_per_coin) * gross_target_exposure
            target_rows.append(pending_target.rename(previous_date).to_frame().T)

        cost_return = 0.0
        if pending_target is not None:
            trade_turnover = float((pending_target - current_weights).abs().sum())
            turnover.loc[date] = trade_turnover
            cost_return = trade_turnover * fee_rate
            current_weights = pending_target.copy()
            pending_target = None

        gross_asset_return = float((current_weights * day_ret).sum())
        total_day_return = (1.0 - cost_return) * (1.0 + gross_asset_return) - 1.0
        if total_day_return <= -1.0:
            total_day_return = -1.0
        daily_returns.loc[date] = total_day_return
        portfolio_value *= 1.0 + total_day_return
        equity.loc[date] = portfolio_value

        post_return_gross = current_weights * (1.0 + day_ret)
        equity_multiplier = 1.0 + total_day_return
        current_weights = post_return_gross / equity_multiplier if equity_multiplier > 0 else current_weights * 0.0
        weights_history.loc[date] = current_weights
        holdings.loc[date] = float((current_weights > 1e-8).sum())
        previous_date = date

    drawdown = equity / equity.cummax() - 1.0
    target_history = pd.concat(target_rows).sort_index() if target_rows else pd.DataFrame(columns=columns)
    sector_exposure = aggregate_sector_exposure(weights_history, sector_by_coin)

    return BacktestResult(
        name=name,
        daily_returns=daily_returns,
        equity_curve=equity,
        drawdown=drawdown,
        weights=weights_history,
        turnover=turnover,
        holdings_count=holdings,
        sector_exposure=sector_exposure,
        rebalance_targets=target_history,
    )
