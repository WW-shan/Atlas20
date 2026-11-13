from __future__ import annotations

import numpy as np
import pandas as pd


def test_rolling_skew_treats_a_constant_window_as_zero() -> None:
    from atlas20.analytics.rolling import rolling_skew

    frame = pd.DataFrame(
        {
            "constant": np.zeros(5),
            "missing": [0.0, 0.0, np.nan, 0.0, 0.0],
            "variable": [-0.1, 0.0, 0.1, 0.2, -0.2],
        }
    )

    skew = rolling_skew(frame, window=3)

    assert skew["constant"].iloc[-1] == 0.0
    assert pd.isna(skew["missing"].iloc[-1])
    assert not pd.isna(skew["variable"].iloc[-1])


def test_rolling_skew_keeps_the_full_window_requirement() -> None:
    from atlas20.analytics.rolling import rolling_skew

    frame = pd.DataFrame({"constant": np.zeros(5)})

    skew = rolling_skew(frame, window=3)

    assert skew["constant"].iloc[:2].isna().all()
    assert (skew["constant"].iloc[2:] == 0.0).all()
