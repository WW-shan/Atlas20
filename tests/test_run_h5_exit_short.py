from __future__ import annotations

import pandas as pd


def test_runner_freezes_exit_short_candidate() -> None:
    from scripts.run_h5_exit_short import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS3-H5-EXIT-SHORT21"
    assert FROZEN_CONFIG["exit_short_holding_days"] == 21
    assert FROZEN_CONFIG["max_total_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.00
    assert FROZEN_CONFIG["long_buffer"] == 0.75
    assert FROZEN_CONFIG["short_buffer"] == 0.50
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20


def test_eligible_members_by_date_uses_latest_point_in_time_snapshot() -> None:
    from scripts.run_h5_exit_short import _eligible_members_by_date

    d1 = pd.Timestamp("2026-01-01", tz="UTC")
    d2 = pd.Timestamp("2026-01-03", tz="UTC")
    universe = pd.DataFrame(
        {
            "rebalance_date": [d1, d1, d2],
            "coin_id": ["bitcoin", "ethereum", "solana"],
        }
    )

    eligible = _eligible_members_by_date(
        universe,
        [pd.Timestamp("2026-01-02", tz="UTC"), pd.Timestamp("2026-01-04", tz="UTC")],
    )

    assert eligible[pd.Timestamp("2026-01-02", tz="UTC")] == {"bitcoin", "ethereum"}
    assert eligible[pd.Timestamp("2026-01-04", tz="UTC")] == {"solana"}
