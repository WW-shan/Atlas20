"""Aggressive sector-leader rotation builders focused on return capture."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.config import ResearchConfig
from atlas20.signals.momentum import compute_momentum_scores, trailing_return
from atlas20.signals.sector import compute_sector_metrics
from atlas20.universe.builder import MarketDataBundle


SECTOR_LEAD_SCORE_WEIGHTS: dict[str, float] = {
    'leader_momentum_rank': 0.35,
    'top2_momentum_rank': 0.20,
    'sector_rel_btc_30_rank': 0.20,
    'sector_ret_21_rank': 0.15,
    'leader_vs_sector_rank': 0.10,
}

LEADER_COIN_SCORE_WEIGHTS: dict[str, float] = {
    'momentum_rank': 0.50,
    'ret_21_rank': 0.20,
    'rel_sector_21_rank': 0.20,
    'near_high_rank': 0.10,
}


@dataclass
class SectorLeadBuildResult:
    """Targets plus selected sector / leader history."""

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



def _weight_scheme(sector_count: int) -> list[float]:
    if sector_count <= 0:
        return []
    if sector_count == 1:
        return [1.0]
    if sector_count == 2:
        return [0.6, 0.4]
    base = [0.5, 0.3, 0.2]
    total = sum(base[:sector_count])
    return [value / total for value in base[:sector_count]]



def compute_sector_lead_scores(
    market: MarketDataBundle,
    rebalance_date: pd.Timestamp,
    universe_snapshot: pd.DataFrame,
    momentum_weights: dict[int, float],
) -> pd.DataFrame:
    """Build return-seeking sector scores with less emphasis on breadth."""
    sector_metrics = compute_sector_metrics(market, rebalance_date, universe_snapshot, momentum_weights)
    if sector_metrics.empty:
        return sector_metrics

    sector_metrics = sector_metrics.copy()
    sector_metrics['sector_ret_21'] = sector_metrics['sector_ret_30']
    btc_ret_30 = trailing_return(market.price[['bitcoin']], rebalance_date, 30).iloc[0]
    sector_metrics['sector_rel_btc_30'] = sector_metrics['sector_ret_30'] - float(btc_ret_30)
    sector_metrics['leader_vs_sector'] = sector_metrics['leader_momentum'] - sector_metrics['sector_ret_60']

    ranked = pd.DataFrame(index=sector_metrics.index)
    ranked['leader_momentum_rank'] = sector_metrics['leader_momentum'].rank(pct=True)
    ranked['top2_momentum_rank'] = sector_metrics['top2_momentum'].rank(pct=True)
    ranked['sector_rel_btc_30_rank'] = sector_metrics['sector_rel_btc_30'].rank(pct=True)
    ranked['sector_ret_21_rank'] = sector_metrics['sector_ret_21'].rank(pct=True)
    ranked['leader_vs_sector_rank'] = sector_metrics['leader_vs_sector'].rank(pct=True)

    score = pd.Series(0.0, index=sector_metrics.index)
    for column, weight in SECTOR_LEAD_SCORE_WEIGHTS.items():
        score = score.add(ranked[column] * float(weight), fill_value=0.0)
    sector_metrics['sector_lead_score'] = score
    return sector_metrics.sort_values('sector_lead_score', ascending=False)



def compute_leader_coin_scores(
    market: MarketDataBundle,
    rebalance_date: pd.Timestamp,
    coin_ids: list[str],
    momentum_weights: dict[int, float],
    sector_ret_21: float,
) -> pd.Series:
    """Score coins aggressively to choose the sector leader."""
    if not coin_ids:
        return pd.Series(dtype=float)

    momentum = compute_momentum_scores(market.price, rebalance_date, coin_ids, momentum_weights)
    ret_21 = trailing_return(market.price, rebalance_date, 21).reindex(coin_ids)
    rolling_high = market.price.shift(1).rolling(90, min_periods=30).max().loc[rebalance_date].reindex(coin_ids)
    current_price = market.price.loc[rebalance_date].reindex(coin_ids)
    near_high = (current_price / rolling_high).replace([pd.NA, float('inf'), float('-inf')], pd.NA)
    rel_sector = ret_21 - sector_ret_21

    frame = pd.DataFrame(
        {
            'momentum': momentum.reindex(coin_ids),
            'ret_21': ret_21,
            'rel_sector_21': rel_sector,
            'near_high': near_high,
        }
    )
    frame = frame.dropna(how='all')
    if frame.empty:
        return pd.Series(dtype=float)

    ranked = pd.DataFrame(index=frame.index)
    ranked['momentum_rank'] = frame['momentum'].rank(pct=True)
    ranked['ret_21_rank'] = frame['ret_21'].rank(pct=True)
    ranked['rel_sector_21_rank'] = frame['rel_sector_21'].rank(pct=True)
    ranked['near_high_rank'] = frame['near_high'].rank(pct=True)

    score = pd.Series(0.0, index=frame.index)
    for column, weight in LEADER_COIN_SCORE_WEIGHTS.items():
        score = score.add(ranked[column] * float(weight), fill_value=0.0)
    return score.sort_values(ascending=False)



def build_sector_lead_v3_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    regime_frame: pd.DataFrame,
    config: ResearchConfig,
    *,
    top_k: int = 2,
    frequency: str = 'biweekly',
    regime_mode: str = 'bull_only',
) -> SectorLeadBuildResult:
    """Build concentrated sector-leader targets."""
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
            continue

        snapshot = universe_by_date.get(date)
        if snapshot is None or snapshot.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        sector_frame = compute_sector_lead_scores(market, date, snapshot, momentum_weights)
        selected = sector_frame.head(top_k)
        if selected.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        weights = _weight_scheme(len(selected))
        parts: list[pd.Series] = []
        for rank, ((sector, row), sector_weight) in enumerate(zip(selected.iterrows(), weights), start=1):
            sector_coin_ids = snapshot.loc[snapshot['sector'] == sector, 'coin_id'].tolist()
            coin_scores = compute_leader_coin_scores(
                market,
                date,
                sector_coin_ids,
                momentum_weights,
                sector_ret_21=float(row['sector_ret_21']),
            )
            if coin_scores.empty:
                continue
            leader_id = coin_scores.index[0]
            parts.append(pd.Series({leader_id: sector_weight}))
            sector_rows.append(
                {
                    'rebalance_date': date,
                    'sector': sector,
                    'sector_rank': rank,
                    'sector_weight': sector_weight,
                    **row.to_dict(),
                }
            )
            coin_rows.append(
                {
                    'rebalance_date': date,
                    'sector': sector,
                    'coin_id': leader_id,
                    'coin_score': float(coin_scores.iloc[0]),
                    'coin_weight': sector_weight,
                }
            )

        targets[date] = pd.concat(parts).groupby(level=0).sum() if parts else pd.Series(dtype=float)

    return SectorLeadBuildResult(
        targets=targets,
        sector_history=pd.DataFrame(sector_rows),
        coin_history=pd.DataFrame(coin_rows),
    )
