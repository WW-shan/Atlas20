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


def test_ls19_reversal_pair_is_frozen_to_28d_four_by_four() -> None:
    from scripts.run_h5_reversal_pair import LS19_CONFIG, LS19_ID

    assert LS19_ID == "PR2026-11-LS19-H5-REVERSAL-PAIR"
    assert LS19_CONFIG == {
        "h5_leverage": 1.25,
        "max_total_gross": 1.50,
        "long_buffer": 0.50,
        "short_buffer": 0.50,
        "short_stop_loss_pct": 0.20,
        "lookback_days": 28,
        "rebalance_days": 28,
        "count": 4,
        "per_asset_weight": 0.025,
        "min_assets": 8,
    }


def test_ls20_common_gross_candidate_is_frozen() -> None:
    from scripts.run_h5_regime_short_router import LS20_CANDIDATE_ID

    assert LS20_CANDIDATE_ID == "PR2026-11-LS20-H5-COMMON-GROSS"


def test_ls20_runner_preserves_relative_weights_on_same_selection(monkeypatch) -> None:
    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({"date": "adjusted"}, "audit")

    def fake_transform(targets):
        captured["targets"] = targets
        return sentinel

    monkeypatch.setattr(runner, "preserve_relative_weights_on_same_selection", fake_transform)
    long_targets = {"date": "long"}
    result = runner.build_long_targets_for_trial(
        trial_id=runner.LS20_CANDIDATE_ID,
        long_targets=long_targets,
        funding_rates=object(),
        universe=object(),
        available={"BTC"},
    )

    assert result is sentinel
    assert captured["targets"] is long_targets


def test_ls21_positive_carry_short_is_frozen_to_strict_positive_bear_funding() -> None:
    from scripts.run_h5_regime_short_router import (
        LS21_BEAR_FUNDING_THRESHOLD,
        LS21_CANDIDATE_ID,
    )

    assert LS21_CANDIDATE_ID == "PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT"
    assert LS21_BEAR_FUNDING_THRESHOLD == 0.0


def test_ls21_runner_passes_strict_positive_bear_funding(monkeypatch) -> None:
    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({"date": "target"}, "audit", {}, {})

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(runner, "build_regime_short_schedules", fake_builder)
    result = runner.build_short_targets_for_trial(
        trial_id=runner.LS21_CANDIDATE_ID,
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
    assert captured["bear_funding_threshold"] == 0.0


def test_ls22_extreme_run_profit_lock_is_frozen_to_one_hundred_percent_and_half_scale() -> None:
    from scripts.run_h5_regime_short_router import (
        LS22_CANDIDATE_ID,
        LS22_PROFIT_LOCK_CONFIG,
    )

    assert LS22_CANDIDATE_ID == "PR2026-11-LS22-H5-EXTREME-RUN-PROFIT-LOCK"
    assert LS22_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
    }


def test_ls22_runner_applies_profit_lock_to_the_long_book(monkeypatch) -> None:
    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({"date": "trimmed"}, "audit")
    prices = {"BTC": [100.0, 200.0]}

    def fake_trim(targets, *, prices, **kwargs):
        captured["targets"] = targets
        captured["prices"] = prices
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(runner, "trim_extreme_run_single_leader", fake_trim)
    long_targets = {"date": "long"}
    result = runner.build_long_targets_for_trial(
        trial_id=runner.LS22_CANDIDATE_ID,
        long_targets=long_targets,
        funding_rates=object(),
        universe=object(),
        available={"BTC"},
        prices=prices,
    )

    assert result is sentinel
    assert captured["targets"] is long_targets
    assert captured["prices"] is prices
    assert captured["lookback_days"] == 21
    assert captured["threshold"] == 1.0
    assert captured["scale"] == 0.5


def test_ls23_combines_profit_lock_with_the_frozen_short_router() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS23_CANDIDATE_ID == "PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT"
    assert runner.LS23_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS23_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS


def test_ls23_runner_applies_profit_lock_to_the_long_book(monkeypatch) -> None:
    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({"date": "trimmed"}, "audit")

    def fake_trim(targets, *, prices, **kwargs):
        captured["targets"] = targets
        captured["prices"] = prices
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(runner, "trim_extreme_run_single_leader", fake_trim)
    result = runner.build_long_targets_for_trial(
        trial_id=runner.LS23_CANDIDATE_ID,
        long_targets={"date": "long"},
        funding_rates=object(),
        universe=object(),
        available={"BTC"},
        prices={"BTC": [100.0, 200.0]},
    )

    assert result is sentinel
    assert captured["lookback_days"] == 21
    assert captured["threshold"] == 1.0
    assert captured["scale"] == 0.5
