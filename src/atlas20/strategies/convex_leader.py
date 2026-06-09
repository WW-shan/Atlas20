"""CTREND-lite convex leader scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.config import ResearchConfig
from atlas20.strategies.momentum_lead import MomentumLeadBuildResult
from atlas20.universe.builder import MarketDataBundle


RETURN_WINDOWS: tuple[int, ...] = (7, 14, 21, 28, 42, 60)
REFERENCE_ASSETS: tuple[str, str] = ("bitcoin", "ethereum")


@dataclass(frozen=True)
class CTrendLiteScoreWeights:
    """Weights for CTREND-lite ranked factor scoring."""

    trend: float
    acceleration: float
    breakout: float
    relative_strength: float
    volume_expansion: float
    volatility_penalty: float
    overheat_penalty: float


CTREND_LITE_SCORE_FAMILIES: dict[str, CTrendLiteScoreWeights] = {
    "ctrend_lite_balanced": CTrendLiteScoreWeights(
        trend=0.32,
        acceleration=0.12,
        breakout=0.16,
        relative_strength=0.20,
        volume_expansion=0.10,
        volatility_penalty=0.06,
        overheat_penalty=0.04,
    ),
    "ctrend_lite_acceleration": CTrendLiteScoreWeights(
        trend=0.20,
        acceleration=0.30,
        breakout=0.15,
        relative_strength=0.15,
        volume_expansion=0.10,
        volatility_penalty=0.05,
        overheat_penalty=0.05,
    ),
    "ctrend_lite_breakout": CTrendLiteScoreWeights(
        trend=0.25,
        acceleration=0.10,
        breakout=0.30,
        relative_strength=0.15,
        volume_expansion=0.10,
        volatility_penalty=0.05,
        overheat_penalty=0.05,
    ),
    "ctrend_lite_relative_strength": CTrendLiteScoreWeights(
        trend=0.25,
        acceleration=0.10,
        breakout=0.10,
        relative_strength=0.35,
        volume_expansion=0.10,
        volatility_penalty=0.05,
        overheat_penalty=0.05,
    ),
    "ctrend_lite_vol_adjusted": CTrendLiteScoreWeights(
        trend=0.14,
        acceleration=0.04,
        breakout=0.07,
        relative_strength=0.08,
        volume_expansion=0.05,
        volatility_penalty=0.36,
        overheat_penalty=0.26,
    ),
}


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _clean_numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _rank_high(series: pd.Series) -> pd.Series:
    """Percentile rank where larger values are better."""
    clean = _clean_numeric(series)
    if clean.dropna().empty:
        return pd.Series(np.nan, index=series.index, dtype=float)
    return clean.rank(pct=True)


def _trailing_return(
    price: pd.DataFrame,
    rebalance_date: pd.Timestamp,
    coin_ids: list[str],
    window: int,
) -> pd.Series:
    current = _clean_numeric(price.loc[rebalance_date].reindex(coin_ids))
    base = _clean_numeric(price.shift(window).loc[rebalance_date].reindex(coin_ids))
    return _clean_numeric(current / base - 1.0)


def _near_high(
    price: pd.DataFrame,
    rebalance_date: pd.Timestamp,
    coin_ids: list[str],
) -> pd.Series:
    price_history = _clean_numeric_frame(price.reindex(columns=coin_ids).loc[:rebalance_date])
    current = _clean_numeric(price_history.loc[rebalance_date].reindex(coin_ids))
    rolling_high = (
        price_history.shift(1)
        .rolling(90, min_periods=30)
        .max()
        .loc[rebalance_date]
        .reindex(coin_ids)
    )
    return _clean_numeric(current / _clean_numeric(rolling_high))


def _volume_expansion(
    volume: pd.DataFrame,
    rebalance_date: pd.Timestamp,
    coin_ids: list[str],
) -> pd.Series:
    volume_history = _clean_numeric_frame(volume.reindex(columns=coin_ids).loc[:rebalance_date])
    recent = volume_history.tail(7).mean()
    base_history = volume_history.iloc[:-7]
    base = base_history.tail(60).mean() if not base_history.empty else volume_history.tail(60).mean()
    base = base.where(base > 0)
    return _clean_numeric(recent / base - 1.0).reindex(coin_ids)


def _volatility_14(
    price: pd.DataFrame,
    rebalance_date: pd.Timestamp,
    coin_ids: list[str],
) -> pd.Series:
    price_history = _clean_numeric_frame(price.reindex(columns=coin_ids).loc[:rebalance_date].tail(15))
    return price_history.pct_change(fill_method=None).tail(14).std()


def _reference_returns_28(market: MarketDataBundle, rebalance_date: pd.Timestamp) -> pd.Series:
    if any(asset not in market.price.columns for asset in REFERENCE_ASSETS):
        return pd.Series(np.nan, index=REFERENCE_ASSETS, dtype=float)
    return _trailing_return(
        market.price,
        rebalance_date,
        list(REFERENCE_ASSETS),
        28,
    ).reindex(list(REFERENCE_ASSETS))


def _universe_lookup(universe: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    return {pd.Timestamp(date): frame.copy() for date, frame in universe.groupby("rebalance_date")}


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
    return [1.0 / top_n] * top_n


def compute_ctrend_lite_scores(
    market: MarketDataBundle,
    rebalance_date: pd.Timestamp,
    coin_ids: list[str],
    weights: CTrendLiteScoreWeights,
    require_reference_assets: bool = False,
) -> pd.Series:
    """Compute CTREND-lite scores for a point-in-time candidate list."""
    candidate_ids = _dedupe(coin_ids)
    rebalance_date = pd.Timestamp(rebalance_date)
    reference_returns = _reference_returns_28(market, rebalance_date)
    if require_reference_assets and (
        not set(REFERENCE_ASSETS).issubset(candidate_ids) or reference_returns.isna().any()
    ):
        raise ValueError(
            "CTREND-lite relative strength requires bitcoin and ethereum in coin_ids "
            "with usable 28d market price history"
        )
    if not candidate_ids:
        return pd.Series(dtype=float)

    frame = pd.DataFrame(index=candidate_ids)
    for window in RETURN_WINDOWS:
        frame[f"ret_{window}"] = _trailing_return(market.price, rebalance_date, candidate_ids, window)

    current_price = _clean_numeric(market.price.loc[rebalance_date].reindex(candidate_ids))
    return_columns = [f"ret_{window}" for window in RETURN_WINDOWS]
    usable_price = current_price.notna() & frame[return_columns].notna().any(axis=1)
    frame = frame.loc[usable_price].copy()
    if frame.empty:
        return pd.Series(dtype=float)

    frame["near_high"] = _near_high(market.price, rebalance_date, frame.index.tolist())
    frame["volume_expansion"] = _volume_expansion(market.volume, rebalance_date, frame.index.tolist())
    frame = frame.loc[frame["volume_expansion"].notna()].copy()
    if frame.empty:
        return pd.Series(dtype=float)

    frame["volatility_14"] = _volatility_14(market.price, rebalance_date, frame.index.tolist())
    frame["overheat_7"] = frame["ret_7"].abs()

    if reference_returns.notna().all():
        frame["relative_strength_28"] = frame["ret_28"] - float(reference_returns.mean())
    else:
        frame["relative_strength_28"] = np.nan

    short_return = frame[["ret_7", "ret_14"]].mean(axis=1)
    longer_return = frame[["ret_28", "ret_42", "ret_60"]].mean(axis=1)
    frame["acceleration"] = short_return - longer_return

    return_ranks = pd.DataFrame(
        {f"ret_{window}_rank": _rank_high(frame[f"ret_{window}"]) for window in RETURN_WINDOWS},
        index=frame.index,
    )
    ranked = pd.DataFrame(index=frame.index)
    ranked["trend"] = return_ranks.mean(axis=1)
    ranked["acceleration"] = _rank_high(frame["acceleration"])
    ranked["breakout"] = _rank_high(frame["near_high"])
    ranked["relative_strength"] = _rank_high(frame["relative_strength_28"])
    ranked["volume_expansion"] = _rank_high(frame["volume_expansion"])
    ranked["volatility_penalty"] = _rank_high(frame["volatility_14"])
    ranked["overheat_penalty"] = _rank_high(frame["overheat_7"])

    score = pd.Series(0.0, index=ranked.index, dtype=float)
    score = score.add(ranked["trend"].fillna(0.0) * weights.trend, fill_value=0.0)
    score = score.add(ranked["acceleration"].fillna(0.0) * weights.acceleration, fill_value=0.0)
    score = score.add(ranked["breakout"].fillna(0.0) * weights.breakout, fill_value=0.0)
    score = score.add(
        ranked["relative_strength"].fillna(0.0) * weights.relative_strength,
        fill_value=0.0,
    )
    score = score.add(
        ranked["volume_expansion"].fillna(0.0) * weights.volume_expansion,
        fill_value=0.0,
    )
    score = score.sub(
        ranked["volatility_penalty"].fillna(0.0) * weights.volatility_penalty,
        fill_value=0.0,
    )
    score = score.sub(
        ranked["overheat_penalty"].fillna(0.0) * weights.overheat_penalty,
        fill_value=0.0,
    )
    return score.sort_values(ascending=False, kind="mergesort")


def build_ctrend_lite_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    config: ResearchConfig,
    *,
    top_n: int = 2,
    frequency: str = "biweekly",
    score_family: str = "ctrend_lite_balanced",
    include_btc: bool = True,
) -> MomentumLeadBuildResult:
    """Build concentrated CTREND-lite leader targets."""
    frequency_value = config.rebalancing.frequencies.get(frequency, frequency)
    rebalance_dates = get_rebalance_dates(
        market.price.index,
        config.start_timestamp,
        frequency,
        frequency_value,
    )
    universe_by_date = _universe_lookup(universe)
    try:
        weights = CTREND_LITE_SCORE_FAMILIES[score_family]
    except KeyError as exc:
        known_families = ", ".join(sorted(CTREND_LITE_SCORE_FAMILIES))
        raise ValueError(
            f"Unknown CTREND-lite score_family {score_family!r}; expected one of: {known_families}"
        ) from exc

    targets: dict[pd.Timestamp, pd.Series] = {}
    selection_rows: list[dict] = []

    for date in rebalance_dates:
        snapshot = universe_by_date.get(date)
        if snapshot is None or snapshot.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        coin_ids = snapshot["coin_id"].tolist()
        if not include_btc:
            coin_ids = [coin_id for coin_id in coin_ids if coin_id != "bitcoin"]

        scores = compute_ctrend_lite_scores(
            market,
            date,
            coin_ids,
            weights,
        )
        selected = scores.head(top_n)
        if selected.empty:
            targets[date] = pd.Series(dtype=float)
            continue

        allocation_weights = _weight_scheme(len(selected), weighted=True)
        target = pd.Series(
            {coin_id: weight for (coin_id, _), weight in zip(selected.items(), allocation_weights)}
        )
        targets[date] = target
        for rank, ((coin_id, score), weight) in enumerate(
            zip(selected.items(), allocation_weights),
            start=1,
        ):
            selection_rows.append(
                {
                    "rebalance_date": date,
                    "coin_id": coin_id,
                    "coin_rank": rank,
                    "coin_score": float(score),
                    "coin_weight": float(weight),
                    "score_family": score_family,
                }
            )

    return MomentumLeadBuildResult(targets=targets, selection_history=pd.DataFrame(selection_rows))
