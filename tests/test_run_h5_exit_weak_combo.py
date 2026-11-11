from __future__ import annotations


def test_runner_freezes_combined_candidate() -> None:
    from scripts.run_h5_exit_weak_combo import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS5-H5-EXIT-WEAK4-RISK05"
    assert FROZEN_CONFIG["short_per_asset_weight"] == 0.025
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
    assert FROZEN_CONFIG["max_total_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.00
    assert FROZEN_CONFIG["cross_sectional_lookback"] == 14
    assert FROZEN_CONFIG["cross_sectional_rebalance_days"] == 7
    assert FROZEN_CONFIG["cross_sectional_short_count"] == 4
    assert FROZEN_CONFIG["cross_sectional_funding_threshold"] == -0.0002
    assert FROZEN_CONFIG["cross_sectional_funding_lookback"] == 3
