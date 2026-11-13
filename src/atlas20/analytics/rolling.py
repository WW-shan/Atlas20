"""Pandas-version-stable rolling statistics used by research screens."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_skew(
    values: pd.DataFrame,
    *,
    window: int,
    min_periods: int | None = None,
) -> pd.DataFrame:
    """Rolling sample skew with a stable convention for constant windows.

    Pandas 3.1 changed constant-window skew from ``0.0`` to ``NaN``.  A screen
    that requires every eligible asset to have a skew then silently drops every
    date containing a constant return series.  The mathematically useful
    convention here is zero skew for a fully observed zero-variance window;
    windows with missing data remain ``NaN`` so they stay ineligible.
    """

    if window < 1:
        raise ValueError("window must be positive")
    minimum = window if min_periods is None else int(min_periods)
    if minimum < 1 or minimum > window:
        raise ValueError("min_periods must be in [1, window]")
    rolling = values.rolling(window, min_periods=minimum)
    skew = rolling.skew()
    variance = rolling.var(ddof=1)
    constant_window = variance.notna() & np.isclose(variance, 0.0, atol=1e-24, rtol=0.0)
    return skew.mask(skew.isna() & constant_window, 0.0)
