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


def test_runner_freezes_risk_budget_exit_short_candidate() -> None:
    from scripts.run_h5_exit_short import RISK_BUDGET_CANDIDATE_ID, RISK_BUDGET_CONFIG

    assert RISK_BUDGET_CANDIDATE_ID == "PR2026-11-LS4-H5-EXIT-RISK05"
    assert RISK_BUDGET_CONFIG["exit_short_holding_days"] == 21
    assert RISK_BUDGET_CONFIG["short_risk_per_trade"] == 0.005
    assert RISK_BUDGET_CONFIG["short_stop_loss_pct"] == 0.20
    assert RISK_BUDGET_CONFIG["short_per_asset_weight"] == 0.025
    assert RISK_BUDGET_CONFIG["max_total_gross"] == 0.95
    assert RISK_BUDGET_CONFIG["hard_gross"] == 1.00


def test_manifest_construction_override() -> None:
    from scripts.run_h5_exit_short import _manifest_construction

    class Args:
        construction = "H5 1.0x + exit + weak-four fixed-risk shorts"

    assert _manifest_construction(Args(), baseline=False) == Args.construction
    assert _manifest_construction(Args(), baseline=True) == "H5 1.0x"
