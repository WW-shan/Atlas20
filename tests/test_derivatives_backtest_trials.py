from __future__ import annotations

import pandas as pd
import pytest

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


def test_ls24_is_registered_as_cross_venue_funding_trial() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS24_CANDIDATE_ID == "PR2026-11-LS24-H5-PROFIT-LOCK-CROSS-VENUE-SHORT"
    assert runner.LS24_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS24_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS24_CANDIDATE_ID in runner.CROSS_VENUE_FUNDING_TRIALS
    assert runner.LS24_BEAR_FUNDING_THRESHOLD == 0.0


def test_cross_venue_funding_uses_conservative_min_and_missing_is_nan() -> None:
    import pandas as pd

    import scripts.run_h5_regime_short_router as runner

    index = pd.to_datetime(["2022-01-01T00:00:00Z", "2022-01-02T00:00:00Z"])
    binance = pd.DataFrame(
        {"bitcoin": [0.001, 0.002], "ethereum": [0.001, float("nan")]},
        index=index,
    )
    bybit = pd.DataFrame(
        {"bitcoin": [0.0005, 0.003], "solana": [0.002, 0.001]},
        index=index,
    )

    combined = runner.conservative_cross_venue_funding(binance, bybit)

    assert combined.loc[index[0], "bitcoin"] == 0.0005
    assert combined.loc[index[1], "bitcoin"] == 0.002
    assert pd.isna(combined.loc[index[0], "ethereum"])
    assert pd.isna(combined.loc[index[1], "ethereum"])
    assert combined["solana"].isna().all()


def test_ls24_short_builder_uses_cross_venue_positive_only(monkeypatch) -> None:
    import pandas as pd

    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({}, pd.DataFrame(), {}, {})

    def fake_build(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(runner, "build_regime_short_schedules", fake_build)
    short_funding = pd.DataFrame({"bitcoin": [0.001]})
    result = runner.build_short_targets_for_trial(
        trial_id=runner.LS24_CANDIDATE_ID,
        market=object(),
        universe=object(),
        index=pd.DatetimeIndex(["2022-01-01"], tz="UTC"),
        long_raw={},
        long_targets={},
        funding=pd.DataFrame({"bitcoin": [0.002]}),
        available={"bitcoin"},
        mark_candles={},
        start_date="2022-01-01",
        short_funding=short_funding,
    )

    assert result is sentinel
    assert captured["funding"] is short_funding
    assert captured["bear_funding_threshold"] == 0.0
    assert captured["funding_positive_only"] is True


def test_cross_venue_funding_aligns_millisecond_settlement_jitter() -> None:
    import pandas as pd

    import scripts.run_h5_regime_short_router as runner

    binance = pd.DataFrame(
        {"bitcoin": [0.0]},
        index=pd.DatetimeIndex(["2022-01-08T00:00:00.014Z"]),
    )
    bybit = pd.DataFrame(
        {"bitcoin": [0.0001]},
        index=pd.DatetimeIndex(["2022-01-08T00:00:00Z"]),
    )

    combined = runner.conservative_cross_venue_funding(binance, bybit)

    assert combined.loc[pd.Timestamp("2022-01-08T00:00:00Z"), "bitcoin"] == 0.0


def test_ls25_is_registered_as_stateful_long_only_profit_lock() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS25_CANDIDATE_ID == "PR2026-11-LS25-H5-STATEFUL-PROFIT-LOCK"
    assert runner.LS25_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS25_CANDIDATE_ID in runner.LONG_STATEFUL_PROFIT_LOCK_TRIALS
    assert runner.LS25_CANDIDATE_ID not in runner.SHORT_CANDIDATES


def test_ls25_runner_uses_stateful_profit_lock(monkeypatch) -> None:
    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({"date": "locked"}, "audit")

    def fake_stateful(targets, *, prices, **kwargs):
        captured["targets"] = targets
        captured["prices"] = prices
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        runner,
        "trim_extreme_run_single_leader_stateful",
        fake_stateful,
    )
    long_targets = {"date": "long"}
    prices = {"BTC": [100.0, 200.0]}
    result = runner.build_long_targets_for_trial(
        trial_id=runner.LS25_CANDIDATE_ID,
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


def test_ls26_is_registered_as_rearming_long_only_profit_lock() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS26_CANDIDATE_ID == "PR2026-11-LS26-H5-REARMING-PROFIT-LOCK"
    assert runner.LS26_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS26_CANDIDATE_ID in runner.LONG_REARMING_PROFIT_LOCK_TRIALS
    assert runner.LS26_CANDIDATE_ID not in runner.SHORT_CANDIDATES


def test_ls26_runner_enables_threshold_release(monkeypatch) -> None:
    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({"date": "rearming"}, "audit")

    def fake_stateful(targets, *, prices, **kwargs):
        captured["targets"] = targets
        captured["prices"] = prices
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        runner,
        "trim_extreme_run_single_leader_stateful",
        fake_stateful,
    )
    result = runner.build_long_targets_for_trial(
        trial_id=runner.LS26_CANDIDATE_ID,
        long_targets={"date": "long"},
        funding_rates=object(),
        universe=object(),
        available={"BTC"},
        prices={"BTC": [100.0, 200.0]},
    )

    assert result is sentinel
    assert captured["release_at_threshold"] is True
    assert captured["lookback_days"] == 21
    assert captured["threshold"] == 1.0
    assert captured["scale"] == 0.5


def test_ls27_is_registered_as_dynamic_two_sleeve_short_candidate() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS27_CANDIDATE_ID == "PR2026-11-LS27-H5-PROFIT-LOCK-DYNAMIC-SHORT"
    assert runner.LS27_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS27_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS27_MAX_REQUESTED_SHORT_GROSS == 0.50


def test_ls27_blends_ls12_and_bottom4_with_frozen_half_gross(monkeypatch) -> None:
    import pandas as pd
    from types import SimpleNamespace

    import scripts.run_h5_regime_short_router as runner

    date = pd.Timestamp("2022-01-01", tz="UTC")
    router_schedule = {date: pd.Series({"A": 0.0625})}
    bottom_schedule = {date: pd.Series({"B": 0.0625})}
    router_audit = pd.DataFrame(
        {
            "date": [date],
            "regime": ["non_bear"],
            "active_sleeve": ["funding_exit"],
            "short_gross": [0.0625],
        }
    )
    captured: dict[str, object] = {}
    sentinel = {date: pd.Series({"A": 0.0625, "B": 0.0625})}

    def fake_router(**kwargs):
        captured["router_kwargs"] = kwargs
        return router_schedule, router_audit, {}, {}

    def fake_bottom(*args, **kwargs):
        captured["bottom_args"] = args
        captured["bottom_kwargs"] = kwargs
        return bottom_schedule

    def fake_combine(sleeves, *, max_gross):
        captured["sleeves"] = sleeves
        captured["max_gross"] = max_gross
        return sentinel

    monkeypatch.setattr(runner, "build_regime_short_schedules", fake_router)
    monkeypatch.setattr(
        runner, "build_cross_sectional_weak_short_schedule", fake_bottom
    )
    monkeypatch.setattr(runner, "combine_sleeve_targets", fake_combine)

    combined, audit, _, _, bottom = runner.build_dynamic_short_schedules(
        market=SimpleNamespace(price=pd.DataFrame({"A": [1.0], "B": [2.0]})),
        universe=pd.DataFrame(),
        index=pd.DatetimeIndex([date]),
        long_raw={date: pd.Series({"A": 1.0})},
        long_targets={date: pd.Series({"A": 1.25})},
        funding=pd.DataFrame(),
        available={"A", "B"},
        mark_candles={},
        start_date="2022-01-01",
    )

    assert combined is sentinel
    assert bottom[date].equals(bottom_schedule[date])
    assert captured["max_gross"] == 0.50
    assert set(captured["sleeves"]) == {"ls12_router", "bottom4"}
    assert captured["sleeves"]["ls12_router"][1] == 1.0
    assert captured["sleeves"]["bottom4"][1] == 1.0
    assert captured["router_kwargs"]["non_bear_mode"] == "h5_exit"
    assert captured["bottom_kwargs"]["lookback"] == 14
    assert captured["bottom_kwargs"]["short_count"] == 4
    assert audit.loc[0, "active_sleeve"] == "dynamic_short_ensemble"
    assert audit.loc[0, "router_short_gross"] == 0.0625


def test_ls27_dispatch_uses_dynamic_builder(monkeypatch) -> None:
    import pandas as pd

    import scripts.run_h5_regime_short_router as runner

    captured: dict[str, object] = {}
    sentinel = ({}, pd.DataFrame(), {}, {})

    def fake_dynamic(**kwargs):
        captured.update(kwargs)
        return sentinel[0], sentinel[1], sentinel[2], sentinel[3], {}

    monkeypatch.setattr(runner, "build_dynamic_short_schedules", fake_dynamic)
    result = runner.build_short_targets_for_trial(
        trial_id=runner.LS27_CANDIDATE_ID,
        market=object(),
        universe=object(),
        index=pd.DatetimeIndex(["2022-01-01"], tz="UTC"),
        long_raw={},
        long_targets={},
        funding=pd.DataFrame(),
        available=set(),
        mark_candles={},
        start_date="2022-01-01",
    )

    assert result == sentinel
    assert captured["start_date"] == "2022-01-01"


def test_ls28_is_registered_as_priority_short_candidate() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS28_CANDIDATE_ID == "PR2026-11-LS28-H5-PROFIT-LOCK-PRIORITY-SHORT"
    assert runner.LS28_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS28_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS


def test_ls29_is_registered_with_concentration_conditioned_profit_lock() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS29_CANDIDATE_ID == "PR2026-11-LS29-H5-CONCENTRATION-PROFIT-LOCK-REGIME-SHORT"
    assert runner.LS29_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS29_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS29_CANDIDATE_ID in runner.LONG_CONCENTRATION_PROFIT_LOCK_TRIALS
    assert runner.LS29_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "min_leader_weight": 0.25,
    }


def test_ls30_is_registered_as_market_neutral_funding_carry() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS30_CANDIDATE_ID == "PR2026-11-LS30-H5-FUNDING-CARRY-NEUTRAL"
    assert runner.LS30_CANDIDATE_ID in runner.MARKET_NEUTRAL_TRIALS
    assert runner.FUNDING_CARRY_CONFIG == {
        "lookback_days": 7,
        "rebalance_days": 7,
        "count": 2,
        "per_asset_weight": 0.0625,
        "min_assets": 8,
        "min_settlements": 3,
    }


def test_ls32_registers_a_two_times_hold_band_funding_carry() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS32_CANDIDATE_ID == "PR2026-11-LS32-H5-FUNDING-CARRY-HOLD4-LONG60"
    assert runner.LS32_CANDIDATE_ID in runner.MARKET_NEUTRAL_TRIALS
    assert runner.LS32_CARRY_CONFIG == {
        "lookback_days": 7,
        "rebalance_days": 7,
        "count": 2,
        "hold_count": 4,
        "per_asset_weight": 0.0625,
        "min_assets": 8,
        "min_settlements": 3,
    }


def test_ls33_registers_residual_carry_with_buffer_control() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS33_CANDIDATE_ID == "PR2026-11-LS33-H5-LS23-RESIDUAL-CARRY-LONG60"
    assert runner.LS33_CONTROL_ID == "PR2026-11-LS33C-H5-LS23-LONG60-CONTROL"
    assert runner.LS33_CANDIDATE_ID in runner.RESIDUAL_CARRY_TRIALS
    assert runner.LS33_CONTROL_ID not in runner.RESIDUAL_CARRY_TRIALS
    for trial_id in (runner.LS33_CANDIDATE_ID, runner.LS33_CONTROL_ID):
        assert trial_id in runner.LONG_PROFIT_LOCK_TRIALS
        assert trial_id in runner.SHORT_CANDIDATES


def test_ls38_registers_ls23_same_side_no_trade_band() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS38_CANDIDATE_ID == "PR2026-11-LS38-H5-LS23-NOTRADE5"
    assert runner.LS38_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS38_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.SHORT_CANDIDATES[runner.LS38_CANDIDATE_ID] == 0.05
    config = runner._trial_frozen_config(runner.LS38_CANDIDATE_ID)
    assert config["rebalance_no_trade_band"] == 0.05
    assert config["long_buffer"] == 0.50


def test_ls37_registers_fourteen_day_residual_carry() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS37_CANDIDATE_ID == "PR2026-11-LS37-H5-LS23-RESIDUAL-CARRY-14D"
    assert runner.LS37_CANDIDATE_ID in runner.RESIDUAL_CARRY_TRIALS
    assert runner.LS37_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS37_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS37_CARRY_CONFIG == {
        **runner.FUNDING_CARRY_CONFIG,
        "rebalance_days": 14,
    }
    config = runner._trial_frozen_config(runner.LS37_CANDIDATE_ID)
    assert config["long_buffer"] == 0.60
    assert config["funding_carry"] == runner.LS37_CARRY_CONFIG


def test_ls36_registers_short_only_residual_carry() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS36_CANDIDATE_ID == "PR2026-11-LS36-H5-LS23-RESIDUAL-SHORT-CARRY"
    assert runner.LS36_CANDIDATE_ID in runner.RESIDUAL_CARRY_TRIALS
    assert runner.LS36_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS36_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS36_CARRY_CONFIG == {
        **runner.FUNDING_CARRY_CONFIG,
        "carry_sign_only": True,
        "long_enabled": False,
        "short_enabled": True,
    }
    config = runner._trial_frozen_config(runner.LS36_CANDIDATE_ID)
    assert config["long_buffer"] == 0.60
    assert config["funding_carry"] == runner.LS36_CARRY_CONFIG


def test_ls35_registers_sign_conditioned_residual_carry() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS35_CANDIDATE_ID == "PR2026-11-LS35-H5-LS23-RESIDUAL-CARRY-SIGN"
    assert runner.LS35_CANDIDATE_ID in runner.RESIDUAL_CARRY_TRIALS
    assert runner.LS35_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS35_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS35_CARRY_CONFIG == {
        **runner.FUNDING_CARRY_CONFIG,
        "carry_sign_only": True,
    }
    config = runner._trial_frozen_config(runner.LS35_CANDIDATE_ID)
    assert config["long_buffer"] == 0.60
    assert config["funding_carry"] == runner.LS35_CARRY_CONFIG


def test_ls34_registers_short_only_carry_hold_band() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS34_CANDIDATE_ID == "PR2026-11-LS34-H5-LS23-RESIDUAL-CARRY-SHORTHOLD"
    assert runner.LS34_CANDIDATE_ID in runner.RESIDUAL_CARRY_TRIALS
    assert runner.LS34_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS34_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS34_CARRY_CONFIG == {
        "lookback_days": 7,
        "rebalance_days": 7,
        "count": 2,
        "hold_count": 4,
        "hold_long": False,
        "hold_short": True,
        "per_asset_weight": 0.0625,
        "min_assets": 8,
        "min_settlements": 3,
    }
    config = runner._trial_frozen_config(runner.LS34_CANDIDATE_ID)
    assert config["long_buffer"] == 0.60
    assert config["non_bear_sleeve"] == "ls12_router_plus_residual_funding_carry"
    assert config["funding_carry"] == runner.LS34_CARRY_CONFIG


def test_ls33_frozen_config_separates_carry_from_buffer_control() -> None:
    import scripts.run_h5_regime_short_router as runner

    primary = runner._trial_frozen_config(runner.LS33_CANDIDATE_ID)
    assert primary["long_buffer"] == 0.60
    assert primary["non_bear_sleeve"] == "ls12_router_plus_residual_funding_carry"
    assert primary["funding_carry"] == runner.FUNDING_CARRY_CONFIG

    control = runner._trial_frozen_config(runner.LS33_CONTROL_ID)
    assert control["long_buffer"] == 0.60
    assert control["non_bear_sleeve"] == "h5_exit"
    assert "funding_carry" not in control


def test_carry_trial_frozen_config_records_its_actual_rules() -> None:
    import scripts.run_h5_regime_short_router as runner

    config31 = runner._trial_frozen_config(runner.LS31_CANDIDATE_ID)
    assert config31["long_buffer"] == 0.60
    assert config31["non_bear_sleeve"] == "funding_carry_market_neutral"
    assert config31["funding_carry"] == runner.FUNDING_CARRY_CONFIG

    config32 = runner._trial_frozen_config(runner.LS32_CANDIDATE_ID)
    assert config32["long_buffer"] == 0.60
    assert config32["non_bear_sleeve"] == "funding_carry_market_neutral"
    assert config32["funding_carry"] == runner.LS32_CARRY_CONFIG


def test_ls31_is_the_same_carry_sleeve_with_sixty_percent_long_buffer() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS31_CANDIDATE_ID == "PR2026-11-LS31-H5-FUNDING-CARRY-LONG60"
    assert runner.LS31_CANDIDATE_ID in runner.MARKET_NEUTRAL_TRIALS
    assert runner.LS31_LONG_BUFFER == 0.60


def test_ls39_lowvol_pair_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS39_CANDIDATE_ID == "PR2026-11-LS39-H5-LS23-LOWVOL-PAIR"
    assert runner.LS39_VOL_PAIR_CONFIG == {
        "lookback_days": 60,
        "min_observations": 45,
        "rebalance_days": 28,
        "count": 4,
        "per_asset_weight": 0.025,
        "min_assets": 8,
    }
    assert runner.LS39_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS39_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS


def test_ls40_inverse_vol_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS40_CANDIDATE_ID == "PR2026-11-LS40-H5-LS23-INVVOL60"
    assert runner.LS40_INVERSE_VOL_CONFIG == {
        "lookback_days": 60,
        "min_observations": 45,
    }
    assert runner.LS40_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS40_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS40_CANDIDATE_ID in runner.LONG_INVERSE_VOL_TRIALS


def test_ls41_long_stop_is_frozen_to_twenty_percent() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS41_CANDIDATE_ID == "PR2026-11-LS41-H5-LS23-LONGSTOP20"
    assert runner.LS41_LONG_STOP_CONFIG == {"long_stop_loss_pct": 0.20}
    assert runner.LS41_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS41_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS


def test_ls42_profit_lock_redistribution_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS42_CANDIDATE_ID == "PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE"
    assert runner.LS42_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "max_asset_weight": 0.60,
    }
    assert runner.LS42_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS42_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS


def test_ls43_stronger_recipient_confirmation_is_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS43_CANDIDATE_ID == "PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7"
    assert runner.LS43_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "max_asset_weight": 0.60,
        "recipient_confirmation_days": 7,
    }
    assert runner.LS43_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS43_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS43_CANDIDATE_ID in runner.PROFIT_LOCK_REDISTRIBUTE_TRIALS


def test_ls44_breakdown_full_exit_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS44_CANDIDATE_ID == "PR2026-11-LS44-H5-LS23-PROFITLOCK-FULLEXIT-NEG7"
    assert runner.LS44_BREAKDOWN_EXIT_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "confirmation_days": 7,
    }
    assert runner.LS44_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS44_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS44_CANDIDATE_ID in runner.LONG_BREAKDOWN_EXIT_TRIALS


def test_ls45_stronger21_recipient_confirmation_is_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS45_CANDIDATE_ID == "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
    assert runner.LS45_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "max_asset_weight": 0.60,
        "recipient_confirmation_days": 21,
    }
    assert runner.LS45_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS45_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS45_CANDIDATE_ID in runner.PROFIT_LOCK_REDISTRIBUTE_TRIALS


def test_ls46_reversal_short_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS46_CANDIDATE_ID == "PR2026-11-LS46-H5-LS23-PROFITLOCK-REVERSAL-SHORT28"
    assert runner.LS46_REVERSAL_SHORT_CONFIG == {
        "short_weight": 0.20,
        "hold_days": 28,
    }
    assert runner.LS46_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS46_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS46_CANDIDATE_ID in runner.LONG_BREAKDOWN_EXIT_TRIALS
    assert runner.LS46_CANDIDATE_ID in runner.REVERSAL_SHORT_TRIALS


def test_reversal_short_schedule_prioritizes_active_events_then_ls12() -> None:
    import scripts.run_h5_regime_short_router as runner

    d0 = pd.Timestamp("2026-01-01T00:00:00Z")
    d2 = d0 + pd.Timedelta(days=2)
    d3 = d0 + pd.Timedelta(days=3)
    d10 = d0 + pd.Timedelta(days=10)
    base = {
        d0: pd.Series({"A": 0.25}),
        d10: pd.Series({"B": 0.25}),
    }
    audit = pd.DataFrame(
        [
            {"date": d2, "leader": "C", "full_exit": True},
            {"date": d3, "leader": "D", "full_exit": True},
            {"date": d3, "leader": "E", "full_exit": False},
        ]
    )

    schedule = runner.build_reversal_short_schedule(
        base,
        audit,
        hold_days=5,
        short_weight=0.20,
    )

    assert sorted(schedule) == [d0, d2, d3, d0 + pd.Timedelta(days=7), d0 + pd.Timedelta(days=8), d10]
    assert schedule[d2].to_dict() == {"C": pytest.approx(0.20)}
    assert schedule[d3].to_dict() == {
        "C": pytest.approx(0.10),
        "D": pytest.approx(0.10),
    }
    assert schedule[d0 + pd.Timedelta(days=7)].to_dict() == {"D": pytest.approx(0.20)}
    assert schedule[d0 + pd.Timedelta(days=8)].to_dict() == {"A": pytest.approx(0.25)}
    assert schedule[d10].to_dict() == {"B": pytest.approx(0.25)}


def test_ls47_no_reentry_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS47_CANDIDATE_ID == "PR2026-11-LS47-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-NOREENTRY"
    assert runner.LS47_REVERSAL_SHORT_CONFIG == {
        "short_weight": 0.20,
        "hold_days": 28,
        "suppress_long_reentry": True,
    }
    assert runner.LS47_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS47_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS47_CANDIDATE_ID in runner.LONG_BREAKDOWN_EXIT_TRIALS
    assert runner.LS47_CANDIDATE_ID in runner.REVERSAL_SHORT_TRIALS


def test_ls48_oneshot_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS48_CANDIDATE_ID == (
        "PR2026-11-LS48-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-ONESHOT"
    )
    assert runner.LS48_REVERSAL_SHORT_CONFIG == {
        "short_weight": 0.20,
        "hold_days": 28,
        "suppress_long_reentry": True,
        "block_reentry_after_stop": True,
    }
    assert runner.LS48_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS48_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS48_CANDIDATE_ID in runner.LONG_BREAKDOWN_EXIT_TRIALS
    assert runner.LS48_CANDIDATE_ID in runner.REVERSAL_SHORT_TRIALS
    assert runner.LS48_CANDIDATE_ID in runner.STOP_STATE_REVERSAL_SHORT_TRIALS


def test_ls49_ma21_rearm_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS49_CANDIDATE_ID == (
        "PR2026-11-LS49-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-MA21"
    )
    assert runner.LS49_REVERSAL_SHORT_CONFIG == {
        "short_weight": 0.20,
        "hold_days": 28,
        "suppress_long_reentry": True,
        "block_reentry_after_stop": True,
        "rearm_ma_days": 21,
    }
    assert runner.LS49_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS49_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS49_CANDIDATE_ID in runner.LONG_BREAKDOWN_EXIT_TRIALS
    assert runner.LS49_CANDIDATE_ID in runner.REVERSAL_SHORT_TRIALS
    assert runner.LS49_CANDIDATE_ID in runner.STOP_STATE_REVERSAL_SHORT_TRIALS


def test_ls50_below_stop_rearm_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS50_CANDIDATE_ID == (
        "PR2026-11-LS50-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-BELOWSTOP"
    )
    assert runner.LS50_REVERSAL_SHORT_CONFIG == {
        "short_weight": 0.20,
        "hold_days": 28,
        "suppress_long_reentry": True,
        "block_reentry_after_stop": True,
        "rearm_below_stop": True,
    }
    assert runner.LS50_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS50_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS50_CANDIDATE_ID in runner.LONG_BREAKDOWN_EXIT_TRIALS
    assert runner.LS50_CANDIDATE_ID in runner.REVERSAL_SHORT_TRIALS
    assert runner.LS50_CANDIDATE_ID in runner.STOP_STATE_REVERSAL_SHORT_TRIALS


def test_ls51_skip_negative_7d_confirmation_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS51_CANDIDATE_ID == (
        "PR2026-11-LS51-H5-LS23-PROFITLOCK-SKIP7DNEG"
    )
    assert runner.LS51_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "skip_if_confirmation_negative_days": 7,
    }
    assert runner.LS51_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS51_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS51_CANDIDATE_ID in runner.LONG_SKIP_NEGATIVE_CONFIRMATION_TRIALS
    assert runner.LS51_CANDIDATE_ID not in runner.REVERSAL_SHORT_TRIALS


def test_ls52_bull_only_skip_negative_7d_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS52_CANDIDATE_ID == (
        "PR2026-11-LS52-H5-LS23-PROFITLOCK-SKIP7DNEG-BULL"
    )
    assert runner.LS52_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "skip_if_confirmation_negative_days": 7,
        "skip_negative_confirmation_regime": "btc_above_ma200",
    }
    assert runner.LS52_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS52_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS52_CANDIDATE_ID in runner.LONG_BULL_SKIP_NEGATIVE_CONFIRMATION_TRIALS


def test_ls53_ma21_skip_negative_7d_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS53_CANDIDATE_ID == (
        "PR2026-11-LS53-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21"
    )
    assert runner.LS53_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "skip_if_confirmation_negative_days": 7,
        "skip_negative_confirmation_above_ma_days": 21,
    }
    assert runner.LS53_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS53_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS53_CANDIDATE_ID in runner.LONG_ABOVE_MA_SKIP_NEGATIVE_CONFIRMATION_TRIALS


def test_ls54_skip_plus_redistribute_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS54_CANDIDATE_ID == (
        "PR2026-11-LS54-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-REDISTRIBUTE"
    )
    assert runner.LS54_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "max_asset_weight": 0.60,
        "recipient_confirmation_days": 21,
        "skip_if_confirmation_negative_days": 7,
        "skip_negative_confirmation_above_ma_days": 21,
    }
    assert runner.LS54_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS54_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS54_CANDIDATE_ID in runner.LONG_SKIP_REDISTRIBUTE_TRIALS


def test_ls55_partial_skip_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS55_CANDIDATE_ID == (
        "PR2026-11-LS55-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-S075-REDISTRIBUTE"
    )
    assert runner.LS55_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "skip_scale": 0.75,
        "max_asset_weight": 0.60,
        "recipient_confirmation_days": 21,
        "skip_if_confirmation_negative_days": 7,
        "skip_negative_confirmation_above_ma_days": 21,
    }
    assert runner.LS55_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS55_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS55_CANDIDATE_ID in runner.LONG_SKIP_REDISTRIBUTE_TRIALS


def test_ls56_partial_skip_midpoint_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS56_CANDIDATE_ID == (
        "PR2026-11-LS56-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-S0625-REDISTRIBUTE"
    )
    assert runner.LS56_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "skip_scale": 0.625,
        "max_asset_weight": 0.60,
        "recipient_confirmation_days": 21,
        "skip_if_confirmation_negative_days": 7,
        "skip_negative_confirmation_above_ma_days": 21,
    }
    assert runner.LS56_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS56_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS56_CANDIDATE_ID in runner.LONG_SKIP_REDISTRIBUTE_TRIALS


def test_ls57_stabilizing_daily_confirmation_parameters_are_frozen() -> None:
    import scripts.run_h5_regime_short_router as runner

    assert runner.LS57_CANDIDATE_ID == (
        "PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE"
    )
    assert runner.LS57_PROFIT_LOCK_CONFIG == {
        "lookback_days": 21,
        "threshold": 1.0,
        "scale": 0.5,
        "max_asset_weight": 0.60,
        "recipient_confirmation_days": 21,
        "skip_if_confirmation_negative_days": 7,
        "skip_negative_confirmation_above_ma_days": 21,
        "skip_negative_confirmation_min_daily_return": 0.0,
    }
    assert runner.LS57_CANDIDATE_ID in runner.SHORT_CANDIDATES
    assert runner.LS57_CANDIDATE_ID in runner.LONG_PROFIT_LOCK_TRIALS
    assert runner.LS57_CANDIDATE_ID in runner.LONG_SKIP_REDISTRIBUTE_TRIALS


def test_reversal_short_block_windows_cover_execution_through_expiry() -> None:
    import scripts.run_h5_regime_short_router as runner

    audit = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-10-03", tz="UTC"), "leader": "near", "full_exit": True},
            {"date": pd.Timestamp("2026-10-04", tz="UTC"), "leader": "near", "full_exit": False},
        ]
    )

    windows = runner.build_reversal_short_block_windows(audit, hold_days=28)

    assert windows == (
        (
            "near",
            pd.Timestamp("2026-10-04T03:00:00Z"),
            pd.Timestamp("2026-11-01T03:00:00Z"),
        ),
    )


def test_reversal_short_block_windows_follow_the_configured_execution_clock() -> None:
    import scripts.run_h5_regime_short_router as runner

    audit = pd.DataFrame(
        [{"date": pd.Timestamp("2026-10-03", tz="UTC"), "leader": "near", "full_exit": True}]
    )

    windows = runner.build_reversal_short_block_windows(
        audit,
        hold_days=28,
        execution_hour=1,
        execution_minute=5,
    )

    assert windows == (
        (
            "near",
            pd.Timestamp("2026-10-04T01:05:00Z"),
            pd.Timestamp("2026-11-01T01:05:00Z"),
        ),
    )


def test_suppress_long_targets_while_reversal_short_removes_active_asset() -> None:
    import scripts.run_h5_regime_short_router as runner

    d0 = pd.Timestamp("2026-01-01T00:00:00Z")
    d2 = d0 + pd.Timedelta(days=2)
    d7 = d0 + pd.Timedelta(days=7)
    d10 = d0 + pd.Timedelta(days=10)
    long_targets = {
        d0: pd.Series({"C": 0.50}),
        d10: pd.Series({"C": 0.50}),
    }
    base_short = {d0: pd.Series({"B": 0.25})}
    reversal_short = {
        d0: pd.Series({"B": 0.25}),
        d2: pd.Series({"C": 0.20}),
        d7: pd.Series({"B": 0.25}),
    }

    suppressed = runner.suppress_long_targets_while_reversal_short(
        long_targets,
        reversal_short,
        base_short,
    )

    assert suppressed[d0].to_dict() == {"C": pytest.approx(0.50)}
    assert suppressed[d2].empty
    assert suppressed[d7].to_dict() == {"C": pytest.approx(0.50)}
    assert suppressed[d10].to_dict() == {"C": pytest.approx(0.50)}
