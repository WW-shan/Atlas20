from __future__ import annotations


def test_runner_freezes_monthly_sector_short_candidate() -> None:
    from scripts.run_monthly_sector_short import CANDIDATE_ID, FROZEN_CONFIG, SECTOR_SPEC

    assert CANDIDATE_ID == "PR2026-11-LS2-H5-MONTHLY-SECTOR"
    assert SECTOR_SPEC.base_id == "TOP20_SECTOR_top3_monthly_bull"
    assert SECTOR_SPEC.family == "sector"
    assert SECTOR_SPEC.frequency == "monthly"
    assert SECTOR_SPEC.regime_mode == "bull_only"
    assert SECTOR_SPEC.top_n == 3
    assert FROZEN_CONFIG["sector_short_weight"] == 1.0
    assert FROZEN_CONFIG["max_gross"] == 0.95
    assert FROZEN_CONFIG["hard_gross"] == 1.0
    assert FROZEN_CONFIG["long_buffer"] == 0.75
    assert FROZEN_CONFIG["short_buffer"] == 0.50
    assert FROZEN_CONFIG["short_stop_loss_pct"] == 0.20


def test_available_mark_assets_uses_loaded_coin_keys() -> None:
    import pandas as pd

    from scripts.run_monthly_sector_short import _available_mark_assets

    marks = {
        "bitcoin": pd.DataFrame({"close": [1.0]}),
        "ethereum": pd.DataFrame({"close": [2.0]}),
    }

    assert _available_mark_assets(marks) == {"bitcoin", "ethereum"}
