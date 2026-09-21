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
    """Apply a per-asset weight cap, holding any residual in cash.

    Weights are first normalized to sum to one. Any asset above ``max_weight``
    is then trimmed back to the cap and the freed weight is redistributed to
    the assets still below the cap, in proportion to their existing weight.
    This repeats until no asset is over the cap. When *every* remaining asset
    is already at the cap there is nowhere left to redistribute to, so the
    residual stays in cash: the returned weights never exceed ``max_weight``
    and never sum to more than one.

    A previous implementation overwrote the under-cap weights with the freed
    weight instead of adding to them and then renormalized, which silently
    defeated the cap entirely (``[0.5, 0.3, 0.2]`` came back as
    ``[0.7, 0.18, 0.12]``). The cap is a real constraint, so a deliberately
    concentrated book must raise ``max_weight_per_coin`` rather than rely on
    the cap being ignored.
    """
    weights = weights.fillna(0.0).clip(lower=0.0)
    if weights.sum() <= 0:
        return weights * 0.0
    weights = weights / weights.sum()

    if max_weight >= 1.0 or max_weight <= 0.0:
        return weights

    remaining = weights.copy()
    for _ in range(len(remaining) + 1):
        over = remaining > max_weight + 1e-15
        if not over.any():
            break
        freed = float((remaining[over] - max_weight).sum())
        remaining[over] = max_weight
        under = remaining < max_weight - 1e-15
        if not under.any() or freed <= 0.0:
            break
        base = float(remaining[under].sum())
        if base <= 0.0:
            break
        remaining[under] = remaining[under] + remaining[under] / base * freed
    return remaining



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
    leverage_by_date: dict[pd.Timestamp, float] | None = None,
    max_gross_exposure: float | None = None,
) -> BacktestResult:
    """Run a long-only backtest with rebalances effective one day after signal generation.

    ``leverage_by_date`` optionally overrides ``gross_target_exposure`` per
    rebalance date so a strategy can amplify confirmed uptrends and return to
    1x (or flat) elsewhere. Values are clamped to ``max_gross_exposure``.
    """
    returns = asset_returns.copy().sort_index()
    columns = returns.columns
    current_weights = pd.Series(0.0, index=columns)
    fee_rate = (friction.fee_bps + friction.slippage_bps) / 10_000.0

    # The last day each asset actually printed. A feed that ends mid-window is
    # a delisting or a token migration (MATIC stops on 2025-03-24, EOS and MKR
    # migrate to Vaulta and SKY), not a gap the provider will fill later: the
    # position has to be sold rather than carried at a price nobody quotes.
    last_print: dict[object, pd.Timestamp | None] = {
        column: returns[column].last_valid_index() for column in columns
    }

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
        if previous_date is not None and previous_date in rebalance_targets:
            pending_target = rebalance_targets[previous_date].reindex(columns).fillna(0.0)
            exposure = gross_target_exposure
            if leverage_by_date is not None and previous_date in leverage_by_date:
                exposure = float(leverage_by_date[previous_date])
            if max_gross_exposure is not None:
                exposure = min(exposure, float(max_gross_exposure))
            exposure = max(exposure, 0.0)
            pending_target = cap_and_normalize(pending_target, friction.max_weight_per_coin) * exposure
            target_rows.append(pending_target.rename(previous_date).to_frame().T)

        cost_return = 0.0
        if pending_target is not None:
            trade_turnover = float((pending_target - current_weights).abs().sum())
            turnover.loc[date] = trade_turnover
            cost_return = trade_turnover * fee_rate
            current_weights = pending_target.copy()
            pending_target = None

        raw_day_ret = returns.loc[date].reindex(columns)
        missing = raw_day_ret.isna()
        if missing.any():
            held_missing = missing & (current_weights.abs() > 1e-12)
            # A holding whose feed has ended can never print again. Mark it at
            # its last observed close (return 0 for the day it is sold), pay
            # the exit cost and move the proceeds to cash - the alternative,
            # aborting the whole run, makes any strategy that ever held a
            # delisted name unrunnable.
            ended = pd.Series(
                [last_print[column] is not None and date > last_print[column] for column in columns],
                index=columns,
            )
            forced_exit = held_missing & ended
            if forced_exit.any():
                exit_turnover = float(current_weights[forced_exit].abs().sum())
                turnover.loc[date] = float(turnover.loc[date]) + exit_turnover
                cost_return += exit_turnover * fee_rate
                current_weights = current_weights.copy()
                current_weights[forced_exit] = 0.0
                raw_day_ret = raw_day_ret.copy()
                raw_day_ret[forced_exit] = 0.0
                missing = raw_day_ret.isna()
                held_missing = missing & (current_weights.abs() > 1e-12)
            if friction.missing_return_policy == "error" and held_missing.any():
                assets = ", ".join(str(asset) for asset in held_missing.index[held_missing])
                raise ValueError(
                    f"Missing returns for held assets on {pd.Timestamp(date).date()}: {assets}. "
                    "Repair the provider history or explicitly set "
                    "frictions.missing_return_policy=fill with a conservative "
                    "frictions.missing_return_fill."
                )
            day_ret = raw_day_ret.fillna(friction.missing_return_fill)
        else:
            day_ret = raw_day_ret

        gross_asset_return = float((current_weights * day_ret).sum())
        total_day_return = (1.0 - cost_return) * (1.0 + gross_asset_return) - 1.0
        if total_day_return <= -1.0:
            total_day_return = -1.0
        daily_returns.loc[date] = total_day_return
        portfolio_value *= 1.0 + total_day_return
        equity.loc[date] = portfolio_value

        post_return_gross = current_weights * (1.0 + day_ret)
        # Weights are holdings divided by *capital*. Trading costs shrink the
        # capital base but do not shrink the mark-to-market value of what is
        # held, so the drift denominator has to be the gross return. Dividing
        # by the net return instead divided by (1 - cost) as well, leaving the
        # book implicitly levered by 1/(1-cost) after every rebalance; that
        # compounded into an overstated return.
        gross_multiplier = 1.0 + gross_asset_return
        current_weights = post_return_gross / gross_multiplier if gross_multiplier > 0 else current_weights * 0.0
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
