from __future__ import annotations


def test_runner_freezes_candidate_constants() -> None:
    from scripts.run_long_short_cash_sleeve import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS1-H5-H4-SECTOR20"
    assert FROZEN_CONFIG["h4_weight"] == 0.2
    assert FROZEN_CONFIG["sector_short_weight"] == 0.2
    assert FROZEN_CONFIG["max_gross"] == 0.95
    assert FROZEN_CONFIG["long_buffer"] == 0.75
    assert FROZEN_CONFIG["short_buffer"] == 0.50
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
