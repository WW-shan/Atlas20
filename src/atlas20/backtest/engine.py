"""Transparent pandas-based portfolio backtest engine."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TypeVar

import numpy as np
import pandas as pd

from atlas20.config import FrictionConfig
from atlas20.logging_utils import get_logger

LOGGER = get_logger(__name__)

GAP_CARRY_COLUMNS = ["date", "asset", "weight", "event"]

T = TypeVar("T")


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
    # Under missing_return_policy="carry": one row per held coin marked at its
    # last close through a provider gap ("carried") and per trade priced at a
    # carried close ("stale_fill"), with the coin's weight at that point.
    gap_carries: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=GAP_CARRY_COLUMNS))



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
    return cap_coin_weights(_normalize_weights(weights), max_weight)


def _normalize_weights(weights: pd.Series) -> pd.Series:
    """Clean a target into long-only relative weights that sum to one (or zero)."""
    weights = weights.fillna(0.0).clip(lower=0.0)
    if weights.sum() <= 0:
        return weights * 0.0
    return weights / weights.sum()


def cap_coin_weights(weights: pd.Series, max_weight: float) -> pd.Series:
    """Trim every asset to ``max_weight`` without renormalizing the book.

    ``weights`` are fractions of NAV, so the cap is too. The weight freed by a
    trim is redistributed to the assets still below the cap, in proportion to
    their existing weight, which keeps the book at its gross exposure. Once
    every asset is at the cap the residual stays in cash. A cap of 1.0 or more
    (or a non-positive one) is disabled, as it always has been.
    """
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


def cap_sector_weights(
    weights: pd.Series,
    sector_by_coin: pd.Series,
    max_weight: float,
) -> pd.Series:
    """Trim any sector whose total weight exceeds a configured cap.

    The freed weight is deliberately left in cash instead of being redistributed
    to other sectors. Redistribution would make the cap depend on which sectors
    happen to be under the limit and can create a new, unintended concentration
    elsewhere. This function is applied after the per-coin cap, so both limits
    hold simultaneously.
    """
    cleaned = weights.fillna(0.0).clip(lower=0.0)
    if cleaned.sum() <= 0.0 or max_weight >= 1.0 or max_weight <= 0.0:
        return cleaned

    sectors = sector_by_coin.reindex(cleaned.index).fillna("Other")
    capped = cleaned.copy()
    for sector in sectors.unique():
        columns = sectors[sectors == sector].index
        sector_weight = float(capped[columns].sum())
        if sector_weight > max_weight:
            capped[columns] = capped[columns] * (max_weight / sector_weight)
    return capped



def aggregate_sector_exposure(weights: pd.DataFrame, sector_by_coin: pd.Series) -> pd.DataFrame:
    """Aggregate daily coin weights into daily sector exposure."""
    sector_map = sector_by_coin.reindex(weights.columns).fillna("Other")
    exposure = {}
    for sector in sorted(sector_map.unique()):
        cols = sector_map[sector_map == sector].index.tolist()
        exposure[sector] = weights[cols].sum(axis=1)
    return pd.DataFrame(exposure, index=weights.index)


def delay_by_trading_days(
    events: dict[pd.Timestamp, T],
    index: pd.DatetimeIndex,
    days: int,
) -> dict[pd.Timestamp, T]:
    """Move every dated event ``days`` positions later along ``index``.

    ``run_backtest`` applies a target from signal date D to D+1's
    close-to-close return, i.e. it fills at D's close.  Delaying the target
    keys by one trading day fills at D+1's close instead, which bounds the
    cost of executing only after the provider has published D's close.
    Events that would land beyond the last date are dropped.
    """
    if days < 0:
        raise ValueError("days must be non-negative")
    positions = {pd.Timestamp(date): position for position, date in enumerate(index)}
    delayed: dict[pd.Timestamp, T] = {}
    for date, value in events.items():
        position = positions.get(pd.Timestamp(date))
        if position is None:
            raise ValueError(f"event date {pd.Timestamp(date).date()} is not in the index")
        if position + days < len(index):
            delayed[pd.Timestamp(index[position + days])] = value
    return delayed


def _warn_about_dates_outside(
    name: str,
    label: str,
    keys: Iterable[object],
    index: pd.DatetimeIndex,
) -> None:
    """Log the keys ``run_backtest`` will skip because they are not in ``index``.

    Several research scripts pass a daily overlay built over the full market
    index, which starts ``min_history_days`` before the evaluated window,
    together with a window-sliced return frame. Those keys can never execute
    and are skipped as before, but no longer silently.
    """
    known = set(index)
    ignored = sorted(pd.Timestamp(key) for key in keys if key not in known)
    if ignored:
        LOGGER.warning(
            "%s: ignoring %d %s date(s) outside the returns index, %s to %s",
            name,
            len(ignored),
            label,
            ignored[0].date(),
            ignored[-1].date(),
        )



def run_backtest(
    name: str,
    asset_returns: pd.DataFrame,
    rebalance_targets: dict[pd.Timestamp, pd.Series],
    sector_by_coin: pd.Series,
    friction: FrictionConfig,
    initial_capital: float,
    gross_target_exposure: float = 1.0,
    leverage_by_date: dict[pd.Timestamp, float] | None = None,
    max_gross_exposure: float = 1.0,
    pre_fill_returns: pd.DataFrame | None = None,
) -> BacktestResult:
    """Run a long-only backtest with rebalances effective one day after signal generation.

    Each target holds relative weights: it is normalized to sum to one and
    scaled to the rebalance's gross exposure, and only then are
    ``max_weight_per_coin`` and ``max_weight_per_sector`` applied, as fractions
    of NAV. ``leverage_by_date`` optionally overrides ``gross_target_exposure``
    per rebalance date so a strategy can scale down (or go flat) outside
    confirmed uptrends. Values are clamped to ``max_gross_exposure``, which
    defaults to 1.0 and may not exceed it: Atlas20 is unlevered long-only spot.
    A non-finite target weight or exposure raises ``ValueError``; target and
    leverage dates outside ``asset_returns.index`` never execute and are
    skipped with a warning.

    Without ``pre_fill_returns`` a target from signal date D fills at D's
    close. With it (see ``atlas20.backtest.intraday.pre_fill_returns``), the
    fill happens part-way through D+1: the book held before the trade earns
    the move from D's close to the fill, turnover is measured against that
    drifted book, and the new book earns only the rest of D+1. A missing
    pre-fill value means the fill waits for D+1's close.
    """
    # The cap used to default to None, so a stray gross_target_exposure or
    # exposure schedule above 1.0 levered the book without anyone asking.
    if not 0.0 <= max_gross_exposure <= 1.0:
        raise ValueError(
            f"max_gross_exposure={max_gross_exposure} is outside [0, 1]: Atlas20 backtests are unlevered"
        )
    returns = asset_returns.copy().sort_index()
    _warn_about_dates_outside(name, "rebalance target", rebalance_targets, returns.index)
    if leverage_by_date is not None:
        _warn_about_dates_outside(name, "leverage", leverage_by_date, returns.index)
    columns = returns.columns
    current_weights = pd.Series(0.0, index=columns)
    fee_rate = (friction.fee_bps + friction.slippage_bps) / 10_000.0

    fill_split: pd.DataFrame | None = None
    if pre_fill_returns is not None:
        pre_fill = pre_fill_returns.reindex(index=returns.index, columns=columns).astype(float)
        # Where no candle shows the fill, assume it waited for the close (the
        # whole day passes before the fill); where the day itself has no
        # return there is nothing to split and the missing-return rules below
        # apply to the new book as usual.
        fill_split = pre_fill.where(pre_fill.notna(), returns).fillna(0.0)

    # The last day each asset actually printed. A feed that ends mid-window is
    # a delisting or a token migration (MATIC stops on 2025-03-24, EOS and MKR
    # migrate to Vaulta and SKY), not a gap the provider will fill later: the
    # position has to be sold rather than carried at a price nobody quotes.
    last_print: dict[object, pd.Timestamp | None] = {
        column: returns[column].last_valid_index() for column in columns
    }
    first_print: dict[object, pd.Timestamp | None] = {
        column: returns[column].first_valid_index() for column in columns
    }

    def live_on(day: pd.Timestamp) -> pd.Series:
        """True for assets whose printed range covers ``day`` (not ended, not unborn)."""
        return pd.Series(
            [
                first_print[column] is not None
                and last_print[column] is not None
                and first_print[column] <= day <= last_print[column]
                for column in columns
            ],
            index=columns,
        )

    carry_gaps = friction.missing_return_policy == "carry"
    gap_days: dict[object, int] = {}
    gap_events: list[dict[str, object]] = []

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
            signal_day = pd.Timestamp(previous_date).date()
            raw_target = rebalance_targets[previous_date].astype(float)
            # A NaN weight used to read as "not held" and an infinite one wiped
            # the whole target to cash. Either is a signal bug, not a position.
            non_finite = ~np.isfinite(raw_target)
            if non_finite.any():
                assets = ", ".join(str(asset) for asset in raw_target.index[non_finite])
                raise ValueError(f"Non-finite target weight for {assets} in the target on {signal_day}")
            pending_target = raw_target.reindex(columns).fillna(0.0)
            exposure = gross_target_exposure
            if leverage_by_date is not None and previous_date in leverage_by_date:
                exposure = float(leverage_by_date[previous_date])
            # A NaN exposure survived the clamps below and turned the book into
            # NaN weights: silently all cash, and the next entry then paid no
            # turnover and no cost.
            if not np.isfinite(exposure):
                raise ValueError(f"Non-finite exposure {exposure} for the target on {signal_day}")
            exposure = min(exposure, float(max_gross_exposure))
            exposure = max(exposure, 0.0)
            # Targets are relative weights: normalize them to sum to one and
            # scale them to the exposure *before* the caps, which are fractions
            # of NAV. Capping first bound them on the invested fraction instead,
            # so a lone pick at 30% exposure came out at 35% x 30% = 10.5%.
            pending_target = _normalize_weights(pending_target) * exposure
            pending_target = cap_coin_weights(pending_target, friction.max_weight_per_coin)
            pending_target = cap_sector_weights(
                pending_target,
                sector_by_coin,
                friction.max_weight_per_sector,
            )
            target_rows.append(pending_target.rename(previous_date).to_frame().T)

        cost_return = 0.0
        pre_fill_growth = 1.0
        split: pd.Series | None = None
        if pending_target is not None:
            if fill_split is not None:
                # The book held overnight rides until the order fills, and the
                # trade is sized against that drifted book.
                split = fill_split.loc[date]
                pre_fill_growth = 1.0 + float((current_weights * split).sum())
                if pre_fill_growth > 0:
                    current_weights = current_weights * (1.0 + split) / pre_fill_growth
                else:
                    current_weights = current_weights * 0.0
            if carry_gaps and previous_date is not None:
                unpriced = returns.loc[previous_date].reindex(columns).isna() & live_on(previous_date)
                traded = (pending_target - current_weights).abs() > 1e-12
                for asset in columns[unpriced & traded]:
                    gap_events.append(
                        {
                            "date": pd.Timestamp(previous_date),
                            "asset": asset,
                            "weight": float(current_weights[asset]),
                            "event": "stale_fill",
                        }
                    )
            trade_turnover = float((pending_target - current_weights).abs().sum())
            turnover.loc[date] = trade_turnover
            cost_return = trade_turnover * fee_rate
            current_weights = pending_target.copy()
            pending_target = None

        raw_day_ret = returns.loc[date].reindex(columns)
        if split is not None:
            # The new book only earns the move from the fill to the close.
            remaining = 1.0 + split
            raw_day_ret = ((1.0 + raw_day_ret) / remaining.where(remaining > 0) - 1.0).where(
                remaining > 0, raw_day_ret
            )
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
            carried = held_missing & live_on(date) if carry_gaps else held_missing & False
            if carried.any():
                # Inside its printed range, so not an ended feed: a provider
                # gap. Mark the holding at its last close for the day.
                raw_day_ret = raw_day_ret.copy()
                for asset in columns[carried]:
                    gap_days[asset] = gap_days.get(asset, 0) + 1
                    if gap_days[asset] > friction.missing_return_max_carry_days:
                        raise ValueError(
                            f"Held asset {asset} has had no print for {gap_days[asset]} days by "
                            f"{pd.Timestamp(date).date()}, beyond missing_return_max_carry_days="
                            f"{friction.missing_return_max_carry_days}; repair the provider history "
                            "instead of carrying it."
                        )
                    gap_events.append(
                        {
                            "date": pd.Timestamp(date),
                            "asset": asset,
                            "weight": float(current_weights[asset]),
                            "event": "carried",
                        }
                    )
                    raw_day_ret[asset] = 0.0
                held_missing = held_missing & ~carried
            if friction.missing_return_policy in ("error", "carry") and held_missing.any():
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

        if carry_gaps:
            for asset in [asset for asset in gap_days if pd.notna(returns.at[date, asset])]:
                del gap_days[asset]
        gross_asset_return = float((current_weights * day_ret).sum())
        total_day_return = pre_fill_growth * (1.0 - cost_return) * (1.0 + gross_asset_return) - 1.0
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
    gap_carries = pd.DataFrame(gap_events, columns=GAP_CARRY_COLUMNS)
    if not gap_carries.empty:
        LOGGER.warning(
            "%s: %d held coin-day(s) carried at the last close through provider gaps and %d "
            "trade(s) priced at a carried close: %s",
            name,
            int((gap_carries["event"] == "carried").sum()),
            int((gap_carries["event"] == "stale_fill").sum()),
            ", ".join(
                f"{row.asset} {pd.Timestamp(row.date).date()} ({row.event})"
                for row in gap_carries.itertuples(index=False)
            ),
        )
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
        gap_carries=gap_carries,
    )
