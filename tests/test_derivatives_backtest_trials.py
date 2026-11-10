from __future__ import annotations

from scripts.run_derivatives_backtest import TRIAL_RULES


def test_reversal_short_family_is_frozen_to_four_small_short_variants() -> None:
    expected = {
        "PR2026-11-RS-R-BTC25": ("bitcoin", "replace"),
        "PR2026-11-RS-R-WEAK25": ("weakest", "replace"),
        "PR2026-11-RS-F-BTC25": ("bitcoin", "flat-only"),
        "PR2026-11-RS-F-WEAK25": ("weakest", "flat-only"),
    }

    for trial_id, (short_asset, short_mode) in expected.items():
        rule = TRIAL_RULES[trial_id]
        assert rule["short_asset"] == short_asset
        assert rule["short_mode"] == short_mode
        assert rule["short_weight"] == 0.25
        assert rule["leverage"] == 1.25
