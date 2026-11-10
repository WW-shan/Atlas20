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


def test_round2_fast_btc_trials_are_frozen_to_two_modes() -> None:
    expected = {
        "PR2026-11-RS2-A-BTC28": "additive",
        "PR2026-11-RS2-F-BTC28": "flat-only",
    }

    for trial_id, short_mode in expected.items():
        rule = TRIAL_RULES[trial_id]
        assert rule["short_asset"] == "bitcoin"
        assert rule["short_mode"] == short_mode
        assert rule["short_weight"] == 0.25
        assert rule["leverage"] == 1.25
        assert rule["bear_ma_window"] == 50
        assert rule["bear_return_window"] == 28


def test_round3_cross_sectional_trial_is_frozen_to_weekly_weakest() -> None:
    rule = TRIAL_RULES["PR2026-11-RS3-X-WEAK14"]
    assert rule["short_asset"] == "weakest"
    assert rule["short_mode"] == "cross-sectional"
    assert rule["short_weight"] == 0.25
    assert rule["leverage"] == 1.25
    assert rule["cross_sectional_lookback"] == 14
    assert rule["cross_sectional_rebalance_days"] == 7


def test_round4_cross_sectional_basket_is_frozen_to_four_names() -> None:
    rule = TRIAL_RULES["PR2026-11-RS4-X-WEAK4"]
    assert rule["short_mode"] == "cross-sectional"
    assert rule["short_weight"] == 0.25
    assert rule["cross_sectional_short_count"] == 4
    assert rule["cross_sectional_lookback"] == 14
    assert rule["cross_sectional_rebalance_days"] == 7


def test_round5_cross_sectional_basket_uses_only_the_prespecified_short_buffer() -> None:
    rule = TRIAL_RULES["PR2026-11-RS5-X-WEAK4-SB75"]
    assert rule["short_mode"] == "cross-sectional"
    assert rule["short_weight"] == 0.25
    assert rule["cross_sectional_short_count"] == 4
    assert rule["short_buffer"] == 0.75


def test_round6_cross_sectional_basket_uses_the_prespecified_stop20() -> None:
    rule = TRIAL_RULES["PR2026-11-RS6-X-WEAK4-STOP20"]
    assert rule["short_mode"] == "cross-sectional"
    assert rule["short_weight"] == 0.25
    assert rule["cross_sectional_short_count"] == 4
    assert rule["short_stop_loss_pct"] == 0.20
    assert "short_buffer" not in rule


def test_round7_cross_sectional_basket_uses_only_the_prespecified_bottom8_hold_band() -> None:
    rule = TRIAL_RULES["PR2026-11-RS7-X-WEAK4-HOLD8-STOP20"]
    assert rule["short_mode"] == "cross-sectional"
    assert rule["short_weight"] == 0.25
    assert rule["cross_sectional_short_count"] == 4
    assert rule["cross_sectional_hold_rank"] == 8
    assert rule["short_stop_loss_pct"] == 0.20
    assert "short_buffer" not in rule
