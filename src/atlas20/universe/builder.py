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
    returns = price.pct_change().replace([pd.NA, float("inf"), float("-inf")], 0.0).fillna(0.0)

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
            & snapshot["market_cap"].notna()
            & (snapshot["price"] >= config.universe.min_price)
            & (snapshot["volume_usd"] >= config.universe.min_daily_dollar_volume)
            & (snapshot["history_days"] >= config.universe.min_history_days)
        ].copy()

        if snapshot.empty:
            LOGGER.warning("No eligible assets on rebalance date %s", rebalance_date.date())
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
