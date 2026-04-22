from __future__ import annotations

import pandas as pd

from atlas20.signals.momentum import compute_momentum_scores



def test_compute_momentum_scores_orders_assets_correctly() -> None:
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    price = pd.DataFrame(
        {
            "a": range(1, 101),
            "b": [50] * 100,
            "c": list(range(100, 0, -1)),
        },
        index=dates,
        dtype=float,
    )
    weights = {30: 0.5, 60: 0.3, 90: 0.2}
    scores = compute_momentum_scores(price, dates[-1], ["a", "b", "c"], weights)
    assert scores.index.tolist()[0] == "a"
    assert scores.index.tolist()[-1] == "c"
    assert scores["a"] > scores["b"] > scores["c"]
