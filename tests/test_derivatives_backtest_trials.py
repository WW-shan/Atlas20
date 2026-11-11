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


def test_ls16_no_trade_band_candidate_is_frozen_to_five_percent_nav() -> None:
    from scripts.run_h5_regime_short_router import (
        NO_TRADE_BAND_CANDIDATE_ID,
        NO_TRADE_BAND_FRACTION,
    )

    assert NO_TRADE_BAND_CANDIDATE_ID == "PR2026-11-LS16-H5-REGIME-SHORT-NOTRADE5"
    assert NO_TRADE_BAND_FRACTION == 0.05


def test_ls17_high_funding_basket_is_frozen_to_weekly_four_names() -> None:
    from scripts.run_h5_regime_short_router import (
        HIGH_FUNDING_SHORT_CONFIG,
        LS17_CANDIDATE_ID,
    )

    assert LS17_CANDIDATE_ID == "PR2026-11-LS17-H5-FUNDING-BASKET"
    assert HIGH_FUNDING_SHORT_CONFIG == {
        "lookback_days": 7,
        "rebalance_days": 7,
        "short_count": 4,
        "per_asset_weight": 0.0625,
        "min_assets": 5,
    }


def test_ls17_runner_passes_high_funding_mode_to_schedule_builder(monkeypatch) -> None:
    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({"date": "target"}, "audit", {}, {})

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(runner, "build_regime_short_schedules", fake_builder)
    result = runner.build_short_targets_for_trial(
        trial_id=runner.LS17_CANDIDATE_ID,
        market=object(),
        universe=object(),
        index=object(),
        long_raw={},
        long_targets={},
        funding=object(),
        available=set(),
        mark_candles={},
        start_date="2022-01-01",
    )

    assert result is sentinel
    assert captured["non_bear_mode"] == "high_funding"


def test_ls18_funding_long_tilt_is_frozen_to_existing_risk_parameters() -> None:
    from scripts.run_h5_regime_short_router import (
        FUNDING_LONG_TILT_CONFIG,
        LS18_CANDIDATE_ID,
    )

    assert LS18_CANDIDATE_ID == "PR2026-11-LS18-H5-FUNDING-TILT"
    assert FUNDING_LONG_TILT_CONFIG == {
        "lookback_days": 7,
        "rank_min": 2.0 / 3.0,
        "min_assets": 5,
        "crowded_weight_scale": 0.5,
        "max_asset_weight": 0.60,
    }


def test_ls18_runner_applies_funding_tilt_to_long_targets(monkeypatch) -> None:
    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({"date": "tilted"}, "audit")

    def fake_tilt(targets, **kwargs):
        captured["targets"] = targets
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(runner, "tilt_long_targets_away_from_crowded_funding", fake_tilt)
    long_targets = {"date": "long"}
    result = runner.build_long_targets_for_trial(
        trial_id=runner.LS18_CANDIDATE_ID,
        long_targets=long_targets,
        funding_rates=object(),
        universe=object(),
        available={"BTC"},
    )

    assert result is sentinel
    assert captured["targets"] is long_targets
    assert captured["rank_min"] == 2.0 / 3.0
    assert captured["max_asset_weight"] == 0.60
