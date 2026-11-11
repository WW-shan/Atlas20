from __future__ import annotations

import pytest


def test_runner_freezes_funding_exit_candidate() -> None:
    from scripts.run_h5_funding_exit_short import CANDIDATE_ID, FROZEN_CONFIG

    assert CANDIDATE_ID == "PR2026-11-LS6-H5-FUNDING-EXIT-RISK05"
    assert FROZEN_CONFIG["funding_lookback_days"] == 7
    assert FROZEN_CONFIG["funding_rank_min"] == pytest.approx(2 / 3)
    assert FROZEN_CONFIG["funding_min_assets"] == 5
    assert FROZEN_CONFIG["short_per_asset_weight"] == 0.025
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20
    assert FROZEN_CONFIG["max_total_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.00
