"""Bull-market offense strategy.

Objective: beat buy-and-hold BTC on total return while staying in the market
only during confirmed uptrends.

Design is driven by this repository's own measurements:
- Only about 12% of the Top-20 universe beats BTC during a bull phase, so the
  portfolio must stay concentrated rather than diversified.
- Leadership rotates completely year over year, so selection is momentum
  based and re-evaluated frequently.
- A single bear year (-64% for BTC in 2022) erases a bull run, so exits use a
  fast trend break rather than waiting for a slow regime filter.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.universe.builder import MarketDataBundle


@dataclass
class BullOffenseBuildResult:
    """Targets plus the per-date diagnostics used to build them."""

    targets: dict[pd.Timestamp, pd.Series]
    leverage_by_date: dict[pd.Timestamp, float]
    signal_history: pd.DataFrame


def compute_offense_scores(
    market: MarketDataBundle,
    as_of_date: pd.Timestamp,
    coin_ids: list[str],
    *,
    lookback: int = 30,
    btc_relative_weight: float = 0.5,
) -> pd.Series:
    """Rank candidates by absolute momentum blended with strength vs BTC."""
    if not coin_ids:
        return pd.Series(dtype=float)

    price = market.price
    current = price.loc[as_of_date].reindex(coin_ids)
    base = price.shift(lookback).loc[as_of_date].reindex(coin_ids)
    absolute = (current / base - 1.0).replace([np.inf, -np.inf], np.nan)

    if "bitcoin" in price.columns:
        btc_current = price.loc[as_of_date, "bitcoin"]
        btc_base = price.shift(lookback).loc[as_of_date, "bitcoin"]
        btc_return = (btc_current / btc_base - 1.0) if btc_base and btc_base > 0 else 0.0
    else:
        btc_return = 0.0

    relative = absolute - float(btc_return)
    blended = absolute + float(btc_relative_weight) * relative
    return blended.dropna().sort_values(ascending=False)


def _btc_trend_ok(price: pd.DataFrame, as_of_date: pd.Timestamp, ma_window: int) -> bool:
    """True while BTC trades above its trailing moving average."""
    if "bitcoin" not in price.columns:
        return True
    history = price["bitcoin"].loc[:as_of_date]
    if len(history) < ma_window:
        return False
    ma = history.tail(ma_window).mean()
    return bool(history.iloc[-1] > ma)


def build_bull_offense_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame | None,
    *,
    hold_count: int = 2,
    frequency: str = "weekly",
    frequency_value: str = "7D",
    lookback: int = 30,
    exit_ma_window: int = 50,
    weighted: bool = True,
    max_leverage: float = 1.0,
    leverage_when_strong: float = 1.0,
    rebalance_dates: list[pd.Timestamp] | None = None,
) -> BullOffenseBuildResult:
    """Build concentrated bull-market targets with a fast trend exit.

    ``rebalance_dates`` may be injected so the strategy shares exactly the
    same calendar as the point-in-time universe. If it is left as ``None`` the
    schedule is derived from the price index, which risks silently
    misaligning with a universe built on a different frequency and produces
    an empty candidate pool (every target flat).
    """
    price = market.price
    if price.empty:
        return BullOffenseBuildResult(targets={}, leverage_by_date={}, signal_history=pd.DataFrame())

    if rebalance_dates is None:
        rebalance_dates = get_rebalance_dates(
            price.index, price.index.min(), frequency, frequency_value
        )
    else:
        rebalance_dates = [pd.Timestamp(d) for d in rebalance_dates]

    targets: dict[pd.Timestamp, pd.Series] = {}
    leverage: dict[pd.Timestamp, float] = {}
    rows: list[dict] = []

    # Point-in-time universe: only coins that actually ranked inside the
    # configured Top-N at this rebalance date may be selected. Falling back to
    # every column in the price matrix would silently look ahead, because the
    # panel also contains coins that were never in the top ranks.
    universe_by_date: dict[pd.Timestamp, list[str]] = {}
    if universe is not None and not universe.empty:
        universe_by_date = {
            pd.Timestamp(d): frame["coin_id"].tolist()
            for d, frame in universe.groupby("rebalance_date")
        }
    # Latest universe snapshot on or before a date. The universe is a step
    # function (it only changes on its own rebalance dates), so a strategy
    # date that falls between snapshots must reuse the most recent one rather
    # than dropping out of the eligible pool.
    universe_dates = sorted(universe_by_date)

    def _universe_at(date: pd.Timestamp) -> list[str]:
        pos = bisect_right(universe_dates, date) - 1
        if pos < 0:
            return []
        return universe_by_date[universe_dates[pos]]

    for date in rebalance_dates:
        trend_ok = _btc_trend_ok(price, date, exit_ma_window)
        if universe is not None and not universe.empty:
            allowed = set(_universe_at(pd.Timestamp(date)))
            pool = [c for c in price.columns if c in allowed]
        else:
            pool = list(price.columns)
        candidates = [
            c
            for c in pool
            if pd.notna(price.loc[date, c]) and price.loc[date, c] > 0
        ]

        if not trend_ok or not candidates:
            targets[date] = pd.Series(dtype=float)
            leverage[date] = 0.0
            rows.append({"date": date, "trend_ok": trend_ok, "selected": 0, "leverage": 0.0})
            continue

        scores = compute_offense_scores(market, date, candidates, lookback=lookback)
        selected = scores.head(hold_count)
        if selected.empty:
            targets[date] = pd.Series(dtype=float)
            leverage[date] = 0.0
            rows.append({"date": date, "trend_ok": trend_ok, "selected": 0, "leverage": 0.0})
            continue

        if weighted:
            if len(selected) == 1:
                weights = [1.0]
            elif len(selected) == 2:
                weights = [0.65, 0.35]
            else:
                base = np.array([0.5, 0.3, 0.2][: len(selected)], dtype=float)
                weights = (base / base.sum()).tolist()
        else:
            weights = [1.0 / len(selected)] * len(selected)

        targets[date] = pd.Series(
            {coin: weight for coin, weight in zip(selected.index, weights)}
        )
        exposure = min(float(leverage_when_strong), float(max_leverage))
        leverage[date] = exposure
        rows.append(
            {
                "date": date,
                "trend_ok": trend_ok,
                "selected": len(selected),
                "leverage": exposure,
                "top_coin": selected.index[0],
                "top_score": float(selected.iloc[0]),
            }
        )

    return BullOffenseBuildResult(
        targets=targets,
        leverage_by_date=leverage,
        signal_history=pd.DataFrame(rows),
    )
