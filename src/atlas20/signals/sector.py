"""Sector-strength metrics and V2 scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from atlas20.signals.momentum import compute_momentum_scores, trailing_return
from atlas20.universe.builder import MarketDataBundle


DEFAULT_SECTOR_V2_SCORE_WEIGHTS: dict[str, float] = {
    'sector_ret_60_rank': 0.25,
    'sector_ret_90_rank': 0.20,
    'sector_rel_btc_60_rank': 0.20,
    'breadth_positive_30_rank': 0.15,
    'breadth_above_ma20_rank': 0.10,
    'leader_momentum_rank': 0.10,
}


@dataclass(frozen=True)
class SectorScoreDefinition:
    """Configuration for sector V2 composite scoring."""

    weights: dict[str, float]



def compute_sector_metrics(
    market: MarketDataBundle,
    rebalance_date: pd.Timestamp,
    universe_snapshot: pd.DataFrame,
    momentum_weights: dict[int, float],
) -> pd.DataFrame:
    """Build richer sector metrics from point-in-time universe members."""
    groups = universe_snapshot.groupby('sector')['coin_id'].apply(list)
    btc_ret_60 = trailing_return(market.price[['bitcoin']], rebalance_date, 60).iloc[0]
    ret30_all = trailing_return(market.price, rebalance_date, 30)
    ret60_all = trailing_return(market.price, rebalance_date, 60)
    ret90_all = trailing_return(market.price, rebalance_date, 90)
    ma20 = market.price.rolling(20, min_periods=20).mean().loc[rebalance_date]
    current_price = market.price.loc[rebalance_date]

    rows: list[dict] = []
    for sector, coin_ids in groups.items():
        momentum_scores = compute_momentum_scores(market.price, rebalance_date, coin_ids, momentum_weights).dropna()
        sector_ret_30 = ret30_all.reindex(coin_ids).dropna()
        sector_ret_60 = ret60_all.reindex(coin_ids).dropna()
        sector_ret_90 = ret90_all.reindex(coin_ids).dropna()
        sector_current = current_price.reindex(coin_ids)
        sector_ma20 = ma20.reindex(coin_ids)
        if sector_ret_60.empty and momentum_scores.empty:
            continue

        breadth_positive_30 = float((sector_ret_30 > 0).mean()) if not sector_ret_30.empty else 0.0
        breadth_above_ma20 = float((sector_current > sector_ma20).mean()) if not sector_current.empty else 0.0
        leader_momentum = float(momentum_scores.iloc[0]) if not momentum_scores.empty else 0.0
        top2_momentum = float(momentum_scores.head(2).mean()) if not momentum_scores.empty else 0.0

        rows.append(
            {
                'sector': sector,
                'sector_ret_30': float(sector_ret_30.mean()) if not sector_ret_30.empty else 0.0,
                'sector_ret_60': float(sector_ret_60.mean()) if not sector_ret_60.empty else 0.0,
                'sector_ret_90': float(sector_ret_90.mean()) if not sector_ret_90.empty else 0.0,
                'sector_rel_btc_60': (float(sector_ret_60.mean()) if not sector_ret_60.empty else 0.0) - float(btc_ret_60),
                'breadth_positive_30': breadth_positive_30,
                'breadth_above_ma20': breadth_above_ma20,
                'leader_momentum': leader_momentum,
                'top2_momentum': top2_momentum,
                'member_count': len(coin_ids),
            }
        )

    return pd.DataFrame(rows).set_index('sector') if rows else pd.DataFrame()



def compute_sector_v2_scores(
    sector_metrics: pd.DataFrame,
    definition: SectorScoreDefinition | None = None,
) -> pd.Series:
    """Turn sector metrics into a composite sector-strength ranking."""
    if sector_metrics.empty:
        return pd.Series(dtype=float)

    definition = definition or SectorScoreDefinition(weights=DEFAULT_SECTOR_V2_SCORE_WEIGHTS)
    ranked = pd.DataFrame(index=sector_metrics.index)
    ranked['sector_ret_60_rank'] = sector_metrics['sector_ret_60'].rank(pct=True)
    ranked['sector_ret_90_rank'] = sector_metrics['sector_ret_90'].rank(pct=True)
    ranked['sector_rel_btc_60_rank'] = sector_metrics['sector_rel_btc_60'].rank(pct=True)
    ranked['breadth_positive_30_rank'] = sector_metrics['breadth_positive_30'].rank(pct=True)
    ranked['breadth_above_ma20_rank'] = sector_metrics['breadth_above_ma20'].rank(pct=True)
    ranked['leader_momentum_rank'] = sector_metrics['leader_momentum'].rank(pct=True)

    score = pd.Series(0.0, index=sector_metrics.index)
    for column, weight in definition.weights.items():
        score = score.add(ranked[column] * float(weight), fill_value=0.0)
    return score.sort_values(ascending=False)
