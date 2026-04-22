"""Concentrated momentum rotation builders for profit-focused scans."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.config import ResearchConfig
from atlas20.signals.momentum import compute_momentum_scores, trailing_return
from atlas20.universe.builder import MarketDataBundle


@dataclass
class MomentumLeadBuildResult:
    """Targets plus selection history."""

    targets: dict[pd.Timestamp, pd.Series]
    selection_history: pd.DataFrame


DEFAULT_MOMENTUM_LEAD_WEIGHTS: dict[str, float] = {
    'momentum_rank': 0.45,
    'ret_21_rank': 0.25,
    'ret_42_rank': 0.20,
    'near_high_rank': 0.10,
}



def _regime_allows(date: pd.Timestamp, regime_frame: pd.DataFrame, regime_mode: str) -> bool:
    if regime_mode == 'always_on':
        return True
    if date not in regime_frame.index:
        return False
    return bool(regime_frame.loc[date, 'bull'])



def _universe_lookup(universe: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    return {pd.Timestamp(date): frame.copy() for date, frame in universe.groupby('rebalance_date')}



def _weight_scheme(top_n: int, weighted: bool) -> list[float]:
    if top_n <= 0:
        return []
    if not weighted:
        return [1.0 / top_n] * top_n
    if top_n == 1:
        return [1.0]
    if top_n == 2:
        return [0.6, 0.4]
    if top_n == 3:
        return [0.5, 0.3, 0.2]
    base = [0.4, 0.25, 0.2, 0.15]
    values = base[:top_n]
    total = sum(values)
    return [value / total for value in values]



def compute_momentum_lead_scores(
    market: MarketDataBundle,
    rebalance_date: pd.Timestamp,
    coin_ids: list[str],
    momentum_weights: dict[int, float],
    score_weights: dict[str, float] | None = None,
) -> pd.Series:
    """More aggressive coin-level scores than plain weighted momentum."""
    if not coin_ids:
        return pd.Series(dtype=float)

    momentum = compute_momentum_scores(market.price, rebalance_date, coin_ids, momentum_weights).reindex(coin_ids)
    ret_21 = trailing_return(market.price, rebalance_date, 21).reindex(coin_ids)
    ret_42 = trailing_return(market.price, rebalance_date, 42).reindex(coin_ids)
    rolling_high = market.price.shift(1).rolling(90, min_periods=30).max().loc[rebalance_date].reindex(coin_ids)
    current_price = market.price.loc[rebalance_date].reindex(coin_ids)
    near_high = (current_price / rolling_high).replace([pd.NA, float('inf'), float('-inf')], pd.NA)

    frame = pd.DataFrame(
        {
            'momentum': momentum,
            'ret_21': ret_21,
            'ret_42': ret_42,
            'near_high': near_high,
        }
    ).dropna(how='all')
    if frame.empty:
        return pd.Series(dtype=float)

    ranked = pd.DataFrame(index=frame.index)
    ranked['momentum_rank'] = frame['momentum'].rank(pct=True)
    ranked['ret_21_rank'] = frame['ret_21'].rank(pct=True)
    ranked['ret_42_rank'] = frame['ret_42'].rank(pct=True)
    ranked['near_high_rank'] = frame['near_high'].rank(pct=True)

    score_weights = score_weights or DEFAULT_MOMENTUM_LEAD_WEIGHTS
    score = pd.Series(0.0, index=ranked.index)
    for column, weight in score_weights.items():
        score = score.add(ranked[column] * float(weight), fill_value=0.0)
    return score.sort_values(ascending=False)



def build_momentum_lead_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    regime_frame: pd.DataFrame,
    config: ResearchConfig,
    *,
    top_n: int = 2,
    frequency: str = 'biweekly',
    regime_mode: str = 'bull_only',
    weighted: bool = True,
    score_weights: dict[str, float] | None = None,
) -> MomentumLeadBuildResult:
    """Build concentrated momentum-leader targets."""
    frequency_value = config.rebalancing.frequencies.get(frequency, frequency)
    rebalance_dates = get_rebalance_dates(market.price.index, config.start_timestamp, frequency, frequency_value)
    universe_by_date = _universe_lookup(universe)
    momentum_weights = config.signals.momentum_weight_map()

    targets: dict[pd.Timestamp, pd.Series] = {}
    selection_rows: list[dict] = []

    for date in rebalance_dates:
        if regime_mode == 'bull_only' and not _regime_allows(date, regime_frame, regime_mode):
            targets[date] = pd.Series(dtype=float)
            continue

        snapshot = universe_by_date.get(date)
        if snapshot is None or snapshot.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        coin_scores = compute_momentum_lead_scores(
            market,
            date,
            snapshot['coin_id'].tolist(),
            momentum_weights,
            score_weights=score_weights,
        )
        selected = coin_scores.head(top_n)
        if selected.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        weights = _weight_scheme(len(selected), weighted)
        target = pd.Series({coin_id: weight for (coin_id, _), weight in zip(selected.items(), weights)})
        targets[date] = target
        for rank, ((coin_id, score), weight) in enumerate(zip(selected.items(), weights), start=1):
            selection_rows.append(
                {
                    'rebalance_date': date,
                    'coin_id': coin_id,
                    'coin_rank': rank,
                    'coin_score': float(score),
                    'coin_weight': float(weight),
                }
            )

    return MomentumLeadBuildResult(targets=targets, selection_history=pd.DataFrame(selection_rows))
