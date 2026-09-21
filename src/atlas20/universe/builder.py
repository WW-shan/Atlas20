"""Historical universe construction from processed market data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from atlas20.config import ResearchConfig
from atlas20.logging_utils import get_logger

LOGGER = get_logger(__name__)


@dataclass
class MarketDataBundle:
    """Wide daily matrices used by the backtest engine."""

    raw_price: pd.DataFrame
    price: pd.DataFrame
    returns: pd.DataFrame
    market_cap: pd.DataFrame
    volume: pd.DataFrame
    history_count: pd.DataFrame
    metadata: pd.DataFrame



def prepare_market_data(panel: pd.DataFrame, metadata: pd.DataFrame, config: ResearchConfig) -> MarketDataBundle:
    """Transform the long panel into aligned wide matrices."""
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel.sort_values(["date", "coin_id"])

    raw_price = panel.pivot(index="date", columns="coin_id", values="price").sort_index()
    market_cap = panel.pivot(index="date", columns="coin_id", values="market_cap").sort_index()
    volume = panel.pivot(index="date", columns="coin_id", values="volume_usd").sort_index()

    full_index = pd.date_range(raw_price.index.min(), raw_price.index.max(), freq="D")
    raw_price = raw_price.reindex(full_index)
    market_cap = market_cap.reindex(full_index)
    volume = volume.reindex(full_index).fillna(0.0)

    history_count = raw_price.notna().cumsum()
    price = raw_price.ffill(limit=3)
    market_cap = market_cap.ffill(limit=3)
    # Interior provider gaps are carried at the last observed price, and the
    # first print after the gap applies the cumulative move.  This is not the
    # same as treating a delisted asset as permanently flat: returns after the
    # *last* observed price stay NaN so the engine can fail closed (or apply an
    # explicit, conservative fill policy).  The old code forward-filled the
    # entire tail, silently turning a truncated feed into a zero-return asset.
    carried_price = raw_price.ffill()
    returns = carried_price.pct_change().replace([float("inf"), float("-inf")], float("nan"))
    for column in raw_price.columns:
        last_observed = raw_price[column].last_valid_index()
        if last_observed is not None:
            returns.loc[returns.index > last_observed, column] = float("nan")

    return MarketDataBundle(
        raw_price=raw_price,
        price=price,
        returns=returns,
        market_cap=market_cap,
        volume=volume,
        history_count=history_count,
        metadata=metadata,
    )


def build_rebalance_universe(
    market: MarketDataBundle,
    rebalance_dates: list[pd.Timestamp],
    config: ResearchConfig,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Build the top-20 eligible universe at each rebalance date using point-in-time data."""
    metadata = market.metadata.copy()
    rows: list[pd.DataFrame] = []

    for rebalance_date in rebalance_dates:
        snapshot = pd.DataFrame(
            {
                "price": market.price.loc[rebalance_date],
                "market_cap": market.market_cap.loc[rebalance_date],
                "volume_usd": market.volume.loc[rebalance_date],
                "history_days": market.history_count.loc[rebalance_date],
            }
        )
        snapshot.index.name = "coin_id"
        snapshot = snapshot.join(metadata[["symbol", "name", "sector"]], how="left")
        snapshot = snapshot.reset_index()
        snapshot = snapshot[
            snapshot["price"].notna()
            & (snapshot["price"] > 0)
            # A zero or negative market cap means the provider has no supply
            # data for that asset (CMC returns marketCap: 0 for e.g. WhiteBIT).
            # Treating it as valid would let the asset rank inside the Top-N
            # and displace a genuine constituent.
            & snapshot["market_cap"].notna()
            & (snapshot["market_cap"] > 0)
            & (snapshot["price"] >= config.universe.min_price)
            & (snapshot["volume_usd"] >= config.universe.min_daily_dollar_volume)
            & (snapshot["history_days"] >= config.universe.min_history_days)
        ].copy()

        if snapshot.empty:
            LOGGER.warning("No eligible assets on rebalance date %s", rebalance_date.date())
            continue

        # Liquidity gate: an inflated-supply / thin-float asset can rank highly
        # on market cap while being untradeable in size. Require either a
        # meaningful turnover ratio or a large absolute dollar volume.
        if config.universe.min_turnover_ratio > 0:
            turnover = snapshot["volume_usd"] / snapshot["market_cap"]
            liquid = (turnover >= config.universe.min_turnover_ratio) | (
                snapshot["volume_usd"] >= config.universe.min_turnover_volume_usd
            )
            snapshot = snapshot[liquid].copy()
            if snapshot.empty:
                LOGGER.warning("No liquid assets on rebalance date %s", rebalance_date.date())
                continue

        snapshot = snapshot.sort_values("market_cap", ascending=False).head(config.universe.universe_size).copy()
        snapshot["rebalance_date"] = rebalance_date
        snapshot["universe_rank"] = range(1, len(snapshot) + 1)
        rows.append(snapshot)

    if not rows:
        raise ValueError("No rebalance universes could be built")

    universe = pd.concat(rows, ignore_index=True)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        universe.to_csv(output_path, index=False)
    return universe
