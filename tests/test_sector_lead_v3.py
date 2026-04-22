from __future__ import annotations

import pandas as pd

from atlas20.strategies.sector_lead_v3 import compute_leader_coin_scores, _weight_scheme


def test_weight_scheme_is_concentrated() -> None:
    assert _weight_scheme(1) == [1.0]
    assert _weight_scheme(2) == [0.6, 0.4]


def test_compute_leader_coin_scores_prefers_stronger_coin() -> None:
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    price = pd.DataFrame(
        {
            "a": [100 + i * 2 for i in range(120)],
            "b": [100 + i * 0.5 for i in range(120)],
        },
        index=dates,
        dtype=float,
    )
    class Market:
        pass
    market = Market()
    market.price = price
    scores = compute_leader_coin_scores(market, dates[-1], ["a", "b"], {30: 0.5, 60: 0.3, 90: 0.2}, sector_ret_21=0.10)
    assert scores.index[0] == "a"
