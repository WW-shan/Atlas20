from __future__ import annotations


def test_runner_freezes_cap1_candidate() -> None:
    from scripts.run_h5_weak4_cap1 import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS7-H5-WEAK4-CAP1"
    assert FROZEN_CONFIG["h5_long_weight"] == 0.80
    assert FROZEN_CONFIG["short_total_weight"] == 0.25
    assert FROZEN_CONFIG["short_per_asset_weight"] == 0.0625
    assert FROZEN_CONFIG["cross_sectional_short_count"] == 4
    assert FROZEN_CONFIG["max_total_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.00
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
