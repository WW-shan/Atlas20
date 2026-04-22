from __future__ import annotations

import pandas as pd

from atlas20.signals.sector import compute_sector_v2_scores
from atlas20.strategies.sector_v2 import _sector_rank_weights


def test_compute_sector_v2_scores_prefers_stronger_breadth_and_leader() -> None:
    metrics = pd.DataFrame(
        {
            "sector_ret_60": [0.40, 0.20],
            "sector_ret_90": [0.60, 0.10],
            "sector_rel_btc_60": [0.20, -0.05],
            "breadth_positive_30": [1.0, 0.5],
            "breadth_above_ma20": [1.0, 0.5],
            "leader_momentum": [0.70, 0.10],
        },
        index=["L1", "DeFi"],
    )
    scores = compute_sector_v2_scores(metrics)
    assert scores.index.tolist()[0] == "L1"
    assert scores.iloc[0] > scores.iloc[1]


def test_sector_rank_weights_follow_rank_emphasis() -> None:
    weights = _sector_rank_weights(3)
    assert round(sum(weights), 10) == 1.0
    assert weights[0] > weights[1] > weights[2]
