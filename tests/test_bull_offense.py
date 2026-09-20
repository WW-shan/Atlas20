"""Bull-market offense strategy: concentrated leaders with exit signals.

Goal is to beat buy-and-hold BTC on total return, not to minimise drawdown.
The design follows the evidence in this repo's own data:

- Only ~12% of coins beat BTC in a bull phase, so concentration matters.
- Year-over-year leadership rotates completely, so the signal must adapt.
- A -64% bear year erases a bull run, so exits must be fast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from atlas20.strategies.bull_offense import (
    build_bull_offense_targets,
    compute_offense_scores,
)
from atlas20.universe.builder import MarketDataBundle


def _bundle(prices: dict[str, np.ndarray], volumes: dict[str, np.ndarray] | None = None) -> MarketDataBundle:
    idx = pd.date_range("2022-01-01", periods=len(next(iter(prices.values()))), freq="D")
    price = pd.DataFrame(prices, index=idx)
    volume = pd.DataFrame(volumes or {k: np.full(len(v), 1e7) for k, v in prices.items()}, index=idx)
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1e6,
        volume=volume,
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame(),
    )


def test_offense_score_rewards_relative_strength() -> None:
    n = 200
    strong = np.linspace(100, 400, n)
    weak = np.linspace(100, 120, n)
    market = _bundle({"strong": strong, "weak": weak, "bitcoin": np.linspace(100, 200, n)})

    scores = compute_offense_scores(
        market,
        market.price.index[-1],
        ["strong", "weak"],
        lookback=30,
    )

    assert scores.loc["strong"] > scores.loc["weak"]


def test_targets_go_flat_when_exit_signal_triggers() -> None:
    n = 400
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    # Long uptrend then a hard crash in the final stretch.
    values = np.concatenate([np.linspace(100, 500, n - 40), np.linspace(500, 200, 40)])
    price = pd.DataFrame({"bitcoin": values, "alt": values * 1.5}, index=idx)
    market = MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1e6,
        volume=price * 0 + 1e7,
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame(),
    )

    result = build_bull_offense_targets(
        market,
        universe=None,
        hold_count=2,
        exit_ma_window=50,
        max_leverage=1.0,
    )

    # After the crash the strategy must be flat, never long into the decline.
    tail_dates = [d for d in result.targets if d >= idx[-10]]
    assert tail_dates, "schedule must cover the tail"
    assert all(result.targets[d].sum() == 0 for d in tail_dates)


def test_targets_are_long_and_concentrated_in_uptrend() -> None:
    n = 400
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": np.linspace(100, 300, n),
            "alt": np.linspace(100, 900, n),
            "slow": np.linspace(100, 150, n),
        },
        index=idx,
    )
    market = MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1e6,
        volume=price * 0 + 1e7,
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame(),
    )

    result = build_bull_offense_targets(
        market,
        universe=None,
        hold_count=2,
        exit_ma_window=50,
        max_leverage=1.0,
    )

    held = [t for t in result.targets.values() if not t.empty and t.sum() > 0]
    assert held, "an uptrend must produce positions"
    assert all(len(t) <= 2 for t in held), "holdings must stay concentrated"
    assert all(t.index.isin(["bitcoin", "alt", "slow"]).all() for t in held)


def test_targets_respect_point_in_time_universe() -> None:
    """Only coins present in the supplied universe may be selected."""
    n = 400
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": np.linspace(100, 200, n),
            "insider": np.linspace(100, 5000, n),  # huge but not in universe
            "allowed": np.linspace(100, 300, n),
        },
        index=idx,
    )
    market = MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1e6,
        volume=price * 0 + 1e7,
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame(),
    )
    universe = pd.DataFrame(
        {
            "rebalance_date": idx[::7],
            "coin_id": ["allowed"] * len(idx[::7]),
        }
    )

    result = build_bull_offense_targets(
        market,
        universe,
        hold_count=1,
        lookback=30,
        exit_ma_window=50,
        max_leverage=1.0,
    )

    held = [t for t in result.targets.values() if not t.empty and t.sum() > 0]
    assert held, "the allowed coin should be held"
    assert all("insider" not in t.index for t in held), (
        "a coin outside the point-in-time universe must never be selected"
    )


def test_targets_align_with_supplied_rebalance_dates() -> None:
    """Rebalance dates must be injectable so the universe and the strategy
    agree on the same calendar. Mismatched calendars silently produce an
    empty pool (every target flat)."""
    n = 400
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": np.linspace(100, 300, n),
            "alt": np.linspace(100, 900, n),
        },
        index=idx,
    )
    market = MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1e6,
        volume=price * 0 + 1e7,
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame(),
    )
    explicit = list(idx[30::7])
    universe = pd.DataFrame(
        {
            "rebalance_date": explicit,
            "coin_id": ["alt"] * len(explicit),
        }
    )

    result = build_bull_offense_targets(
        market,
        universe,
        rebalance_dates=explicit,
        hold_count=1,
        exit_ma_window=20,
        max_leverage=1.0,
    )

    assert set(result.targets) == set(explicit)
    held = [t for t in result.targets.values() if not t.empty and t.sum() > 0]
    assert held, "supplying matching calendars must not yield an empty pool"
    assert all(t.index.tolist() == ["alt"] for t in held)


def test_targets_tolerate_universe_on_a_different_calendar() -> None:
    """A universe built on a coarser calendar (e.g. monthly) must still be
    usable by a weekly strategy: the most recent snapshot carries forward."""
    n = 400
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    price = pd.DataFrame(
        {
            "bitcoin": np.linspace(100, 300, n),
            "alt": np.linspace(100, 900, n),
        },
        index=idx,
    )
    market = MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1e6,
        volume=price * 0 + 1e7,
        history_count=price.notna().cumsum(),
        metadata=pd.DataFrame(),
    )
    weekly = list(idx[30::7])
    monthly = list(idx[30::28])
    universe = pd.DataFrame(
        {"rebalance_date": monthly, "coin_id": ["alt"] * len(monthly)}
    )

    result = build_bull_offense_targets(
        market,
        universe,
        rebalance_dates=weekly,
        hold_count=1,
        exit_ma_window=20,
        max_leverage=1.0,
    )

    held = [t for t in result.targets.values() if not t.empty and t.sum() > 0]
    assert held, "carrying the latest snapshot forward must keep the pool non-empty"
    assert all(t.index.tolist() == ["alt"] for t in held)
