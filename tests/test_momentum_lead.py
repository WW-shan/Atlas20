from __future__ import annotations

import pandas as pd

from atlas20.strategies.momentum_lead import compute_momentum_lead_scores


def test_compute_momentum_lead_scores_prefers_stronger_near_high_asset() -> None:
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    price = pd.DataFrame(
        {
            "a": [100 + i * 2 for i in range(120)],
            "b": [100 + i * 0.8 for i in range(120)],
        },
        index=dates,
        dtype=float,
    )
    class Market:
        pass
    market = Market()
    market.price = price
    scores = compute_momentum_lead_scores(market, dates[-1], ["a", "b"], {30: 0.5, 60: 0.3, 90: 0.2})
    assert scores.index[0] == "a"
