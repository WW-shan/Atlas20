"""Momentum and ranking signal helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd



def trailing_return(price: pd.DataFrame, as_of_date: pd.Timestamp, window: int) -> pd.Series:
    """Compute trailing simple returns for all assets at a date."""
    shifted = price.shift(window)
    current = price.loc[as_of_date]
    base = shifted.loc[as_of_date]
    return current / base - 1.0



def compute_momentum_scores(
    price: pd.DataFrame,
    as_of_date: pd.Timestamp,
    coin_ids: list[str],
    window_weights: dict[int, float],
) -> pd.Series:
    """Compute weighted multi-horizon momentum scores for a subset of coins."""
    if not coin_ids:
        return pd.Series(dtype=float)

    score = pd.Series(0.0, index=coin_ids, dtype=float)
    valid_counts = pd.Series(0, index=coin_ids, dtype=float)
    for window, weight in window_weights.items():
        ret = trailing_return(price, as_of_date, int(window)).reindex(coin_ids)
        score = score.add(ret.fillna(0.0) * float(weight), fill_value=0.0)
        valid_counts = valid_counts.add(ret.notna().astype(float), fill_value=0.0)
    score = score.where(valid_counts > 0, np.nan)
    return score.sort_values(ascending=False)
