"""Enhanced sector-rotation target builders."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.config import ResearchConfig
from atlas20.signals.momentum import compute_momentum_scores
from atlas20.signals.sector import SectorScoreDefinition, compute_sector_metrics, compute_sector_v2_scores
from atlas20.universe.builder import MarketDataBundle


@dataclass
class SectorV2BuildResult:
    """Targets plus point-in-time sector and coin selections."""

    targets: dict[pd.Timestamp, pd.Series]
    sector_history: pd.DataFrame
    coin_history: pd.DataFrame



def _regime_allows(date: pd.Timestamp, regime_frame: pd.DataFrame, regime_mode: str) -> bool:
    if regime_mode == 'always_on':
        return True
    if date not in regime_frame.index:
        return False
    return bool(regime_frame.loc[date, 'bull'])



def _universe_lookup(universe: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    return {pd.Timestamp(date): frame.copy() for date, frame in universe.groupby('rebalance_date')}



def _sector_rank_weights(count: int) -> list[float]:
    if count <= 0:
        return []
    base = [0.5, 0.3, 0.2]
    if count <= len(base):
        values = base[:count]
    else:
        tail = [max(0.05, 0.2 / (i - len(base) + 2)) for i in range(len(base), count)]
        values = base + tail
    total = sum(values)
    return [value / total for value in values]



def build_sector_v2_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    regime_frame: pd.DataFrame,
    config: ResearchConfig,
    *,
    top_k: int = 3,
    frequency: str = 'biweekly',
    regime_mode: str = 'bull_only',
    weighted_sectors: bool = False,
    coins_per_sector: int = 2,
    score_definition: SectorScoreDefinition | None = None,
) -> SectorV2BuildResult:
    """Build improved sector-rotation targets for a study run."""
    frequency_value = config.rebalancing.frequencies.get(frequency, frequency)
    rebalance_dates = get_rebalance_dates(market.price.index, config.start_timestamp, frequency, frequency_value)
    universe_by_date = _universe_lookup(universe)
    momentum_weights = config.signals.momentum_weight_map()

    targets: dict[pd.Timestamp, pd.Series] = {}
    sector_rows: list[dict] = []
    coin_rows: list[dict] = []

    for date in rebalance_dates:
        if regime_mode == 'bull_only' and not _regime_allows(date, regime_frame, regime_mode):
            targets[date] = pd.Series(dtype=float)
            sector_rows.append({'rebalance_date': date, 'sector': 'CASH', 'sector_score': 0.0, 'sector_weight': 1.0})
            continue

        snapshot = universe_by_date.get(date)
        if snapshot is None or snapshot.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        sector_metrics = compute_sector_metrics(market, date, snapshot, momentum_weights)
        sector_scores = compute_sector_v2_scores(sector_metrics, definition=score_definition)
        selected_sectors = sector_scores.head(top_k)
        if selected_sectors.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        sector_weights = _sector_rank_weights(len(selected_sectors)) if weighted_sectors else [1.0 / len(selected_sectors)] * len(selected_sectors)
        target_parts: list[pd.Series] = []

        for rank, ((sector, sector_score), sector_weight) in enumerate(zip(selected_sectors.items(), sector_weights), start=1):
            sector_coin_ids = snapshot.loc[snapshot['sector'] == sector, 'coin_id'].tolist()
            coin_scores = compute_momentum_scores(market.price, date, sector_coin_ids, momentum_weights).dropna()
            selected_coin_scores = coin_scores.head(coins_per_sector)
            if selected_coin_scores.empty:
                continue

            within_weight = sector_weight / len(selected_coin_scores)
            target_parts.append(pd.Series(within_weight, index=selected_coin_scores.index))
            sector_rows.append(
                {
                    'rebalance_date': date,
                    'sector': sector,
                    'sector_rank': rank,
                    'sector_score': float(sector_score),
                    'sector_weight': float(sector_weight),
                    **sector_metrics.loc[sector].to_dict(),
                }
            )
            for coin_rank, (coin_id, coin_score) in enumerate(selected_coin_scores.items(), start=1):
                coin_rows.append(
                    {
                        'rebalance_date': date,
                        'sector': sector,
                        'coin_id': coin_id,
                        'coin_rank_in_sector': coin_rank,
                        'coin_score': float(coin_score),
                        'coin_weight': float(within_weight),
                    }
                )

        targets[date] = pd.concat(target_parts).groupby(level=0).sum() if target_parts else pd.Series(dtype=float)

    return SectorV2BuildResult(
        targets=targets,
        sector_history=pd.DataFrame(sector_rows),
        coin_history=pd.DataFrame(coin_rows),
    )
