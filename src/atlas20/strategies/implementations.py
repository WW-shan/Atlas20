"""Strategy definitions and target-weight generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.config import ResearchConfig
from atlas20.signals.momentum import compute_momentum_scores, trailing_return
from atlas20.universe.builder import MarketDataBundle


@dataclass
class StrategyDefinition:
    """Serializable strategy configuration for one test run."""

    name: str
    family: str
    frequency: str
    regime_mode: str
    params: dict[str, Any] = field(default_factory=dict)



def build_strategy_definitions(config: ResearchConfig) -> list[StrategyDefinition]:
    """Enumerate all benchmark and rotation strategy variants."""
    definitions: list[StrategyDefinition] = []
    for regime_mode in config.regime_modes:
        definitions.extend(
            [
                StrategyDefinition(name=f"BTC_BH__{regime_mode}", family="benchmark", frequency="monthly", regime_mode=regime_mode, params={"coin_id": "bitcoin"}),
                StrategyDefinition(name=f"ETH_BH__{regime_mode}", family="benchmark", frequency="monthly", regime_mode=regime_mode, params={"coin_id": "ethereum"}),
                StrategyDefinition(name=f"TOP20_EQ__{regime_mode}", family="equal_weight", frequency="monthly", regime_mode=regime_mode),
            ]
        )

        for hold_count in config.strategies.momentum_hold_counts:
            for frequency in config.strategies.momentum_frequencies:
                definitions.append(
                    StrategyDefinition(
                        name=f"TOP20_MOM_top{hold_count}_{frequency}__{regime_mode}",
                        family="momentum",
                        frequency=frequency,
                        regime_mode=regime_mode,
                        params={"hold_count": hold_count},
                    )
                )

        for top_k in config.strategies.sector_top_k:
            for frequency in config.strategies.sector_frequencies:
                definitions.append(
                    StrategyDefinition(
                        name=f"TOP20_SECTOR_top{top_k}_{frequency}__{regime_mode}",
                        family="sector",
                        frequency=frequency,
                        regime_mode=regime_mode,
                        params={"top_k": top_k},
                    )
                )
    return definitions



def _regime_allows(date: pd.Timestamp, regime_frame: pd.DataFrame, regime_mode: str) -> bool:
    if regime_mode == "always_on":
        return True
    if date not in regime_frame.index:
        return False
    return bool(regime_frame.loc[date, "bull"])



def _universe_lookup(universe: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    return {pd.Timestamp(date): frame.copy() for date, frame in universe.groupby("rebalance_date")}



def _equal_weight_series(coin_ids: list[str]) -> pd.Series:
    if not coin_ids:
        return pd.Series(dtype=float)
    weight = 1.0 / len(coin_ids)
    return pd.Series(weight, index=coin_ids, dtype=float)



def _compute_sector_scores(
    market: MarketDataBundle,
    rebalance_date: pd.Timestamp,
    universe_snapshot: pd.DataFrame,
    sector_score_weights: dict[str, float],
) -> pd.Series:
    sector_groups = universe_snapshot.groupby("sector")["coin_id"].apply(list)
    data_rows = []
    btc_ret_60 = trailing_return(market.price[["bitcoin"]], rebalance_date, 60).iloc[0]

    for sector, coin_ids in sector_groups.items():
        ret20 = trailing_return(market.price, rebalance_date, 20).reindex(coin_ids).dropna()
        ret60 = trailing_return(market.price, rebalance_date, 60).reindex(coin_ids).dropna()
        if ret20.empty and ret60.empty:
            continue
        data_rows.append(
            {
                "sector": sector,
                "ret_20": ret20.mean() if not ret20.empty else 0.0,
                "ret_60": ret60.mean() if not ret60.empty else 0.0,
                "btc_relative_60": (ret60.mean() if not ret60.empty else 0.0) - btc_ret_60,
            }
        )

    sector_frame = pd.DataFrame(data_rows).set_index("sector")
    if sector_frame.empty:
        return pd.Series(dtype=float)

    ranked = pd.DataFrame(index=sector_frame.index)
    ranked["ret_20_rank"] = sector_frame["ret_20"].rank(pct=True)
    ranked["ret_60_rank"] = sector_frame["ret_60"].rank(pct=True)
    ranked["btc_relative_60"] = sector_frame["btc_relative_60"].rank(pct=True)

    score = pd.Series(0.0, index=ranked.index)
    for column, weight in sector_score_weights.items():
        score = score.add(ranked[column] * float(weight), fill_value=0.0)
    return score.sort_values(ascending=False)



def build_rebalance_targets(
    strategy: StrategyDefinition,
    market: MarketDataBundle,
    universe: pd.DataFrame,
    regime_frame: pd.DataFrame,
    config: ResearchConfig,
) -> tuple[dict[pd.Timestamp, pd.Series], list[pd.Timestamp]]:
    """Build target-weight instructions for a strategy."""
    frequency_value = config.rebalancing.frequencies.get(strategy.frequency, strategy.frequency)
    rebalance_dates = get_rebalance_dates(market.price.index, config.start_timestamp, strategy.frequency, frequency_value)
    universe_by_date = _universe_lookup(universe)
    momentum_weights = config.signals.momentum_weight_map()
    sector_weights = {str(k): float(v) for k, v in config.signals.sector_score_weights.items()}

    targets: dict[pd.Timestamp, pd.Series] = {}

    if strategy.family == "benchmark":
        coin_id = strategy.params["coin_id"]
        for date in rebalance_dates[:1] if strategy.regime_mode == "always_on" else rebalance_dates:
            if _regime_allows(date, regime_frame, strategy.regime_mode):
                targets[date] = pd.Series({coin_id: 1.0})
            else:
                targets[date] = pd.Series(dtype=float)
        return targets, rebalance_dates

    for date in rebalance_dates:
        if strategy.regime_mode == "bull_only" and not _regime_allows(date, regime_frame, strategy.regime_mode):
            targets[date] = pd.Series(dtype=float)
            continue

        universe_snapshot = universe_by_date.get(date)
        if universe_snapshot is None or universe_snapshot.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        coin_ids = universe_snapshot["coin_id"].tolist()

        if strategy.family == "equal_weight":
            targets[date] = _equal_weight_series(coin_ids)
            continue

        if strategy.family == "momentum":
            scores = compute_momentum_scores(market.price, date, coin_ids, momentum_weights)
            selected = scores.dropna().head(int(strategy.params["hold_count"]))
            targets[date] = _equal_weight_series(selected.index.tolist())
            continue

        if strategy.family == "sector":
            sector_scores = _compute_sector_scores(market, date, universe_snapshot, sector_weights)
            selected_sectors = sector_scores.head(int(strategy.params["top_k"])).index.tolist()
            sector_target_parts: list[pd.Series] = []
            if selected_sectors:
                sector_weight = 1.0 / len(selected_sectors)
                for sector in selected_sectors:
                    sector_coin_ids = universe_snapshot.loc[universe_snapshot["sector"] == sector, "coin_id"].tolist()
                    scores = compute_momentum_scores(market.price, date, sector_coin_ids, momentum_weights).dropna()
                    selected_coins = scores.head(config.strategies.sector_max_coins_per_sector).index.tolist()
                    if not selected_coins:
                        continue
                    within_weight = sector_weight / len(selected_coins)
                    sector_target_parts.append(pd.Series(within_weight, index=selected_coins))
            targets[date] = pd.concat(sector_target_parts).groupby(level=0).sum() if sector_target_parts else pd.Series(dtype=float)
            continue

        raise ValueError(f"Unknown strategy family: {strategy.family}")

    return targets, rebalance_dates
