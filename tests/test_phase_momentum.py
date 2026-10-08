from __future__ import annotations

import pandas as pd
import pytest

from atlas20.strategies.phase_momentum import (
    MomentumSignalSpec,
    PhaseMomentumSpec,
    SleeveTargets,
    _desired_exposure,
    aggregate_sleeve_targets,
    build_parameter_ensemble_targets,
    build_signal_panel,
    build_sleeve_targets,
    dispersion_exposure,
    parameter_ensemble_sleeve_weights,
    top20_dispersion,
)
from atlas20.universe.builder import MarketDataBundle


def _market(price: pd.DataFrame) -> MarketDataBundle:
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000.0,
        volume=pd.DataFrame(1_000_000.0, index=price.index, columns=price.columns),
        history_count=pd.DataFrame(200, index=price.index, columns=price.columns),
        metadata=pd.DataFrame(
            {"sector": ["Other"] * len(price.columns)},
            index=price.columns,
        ),
    )


def _universe(rows: list[tuple[pd.Timestamp, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["rebalance_date", "coin_id"])


def test_signal_panel_requires_all_signal_windows_for_new_entrant() -> None:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0] * len(dates),
            "new": [float("nan")] * 4 + [100.0] * (len(dates) - 4),
            "bitcoin": [100.0] * len(dates),
        },
        index=dates,
    )
    market = _market(price)
    universe = _universe([(dates[-1], "a"), (dates[-1], "new")])
    spec = MomentumSignalSpec(name="full_history", window_weights=((2, 1.0), (7, 1.0)))

    panel = build_signal_panel(market, universe, spec, include_btc=False)

    assert "a" in panel.columns
    assert "new" in panel.columns
    assert panel.loc[dates[-1], "a"] == pytest.approx(0.0)
    assert pd.isna(panel.loc[dates[-1], "new"])


def test_sleeve_exits_immediately_when_holding_leaves_top20() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0, 110.0, 120.0, 130.0, 140.0],
            "b": [100.0, 90.0, 80.0, 70.0, 60.0],
            "bitcoin": [100.0] * 5,
        },
        index=dates,
    )
    market = _market(price)
    universe = _universe(
        [
            (dates[0], "a"),
            (dates[0], "b"),
            (dates[1], "a"),
            (dates[1], "b"),
            (dates[2], "b"),
            (dates[3], "b"),
            (dates[4], "b"),
        ]
    )
    signal_spec = MomentumSignalSpec(name="one_day", window_weights=((1, 1.0),))
    signal_panel = build_signal_panel(market, universe, signal_spec, include_btc=False)
    spec = PhaseMomentumSpec(
        rebalance_days=2,
        phase_offsets=(0,),
        hold_rank=1,
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
    )

    sleeve = build_sleeve_targets(
        market,
        signal_panel,
        dates,
        spec,
        signal_name=signal_spec.name,
        phase_offset=0,
    )

    assert sleeve.assets.loc[dates[1]] == "a"
    assert sleeve.assets.loc[dates[2]] == "b"
    assert sleeve.selection_history.loc[
        sleeve.selection_history["signal_date"] == dates[2], "selected_asset"
    ].iloc[0] == "b"


def test_phase_offsets_diverge_on_ranking_switches() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0] * 5,
            "b": [100.0] * 5,
            "bitcoin": [100.0] * 5,
        },
        index=dates,
    )
    market = _market(price)
    signal_panel = pd.DataFrame(
        {
            "a": [2.0, 1.0, 1.0, 2.0, 2.0],
            "b": [1.0, 2.0, 2.0, 1.0, 1.0],
        },
        index=dates,
    )
    spec = PhaseMomentumSpec(
        rebalance_days=2,
        phase_offsets=(0, 1),
        hold_rank=1,
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
    )

    first = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name="custom", phase_offset=0
    )
    second = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name="custom", phase_offset=1
    )

    assert first.assets.loc[dates[0]] == "a"
    assert first.assets.loc[dates[2]] == "b"
    assert second.assets.loc[dates[1]] == "b"
    assert second.assets.loc[dates[3]] == "a"
    assert not first.assets.dropna().equals(second.assets.dropna())


def test_aggregate_sleeve_targets_never_exceeds_full_investment() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    empty_assets = pd.Series(pd.NA, index=dates, dtype="object")
    empty_weights = pd.Series(float("nan"), index=dates, dtype=float)

    first_assets = empty_assets.copy()
    first_weights = empty_weights.copy()
    first_assets.loc[dates[0]] = "a"
    first_weights.loc[dates[0]] = 1.0
    second_assets = empty_assets.copy()
    second_weights = empty_weights.copy()
    second_assets.loc[dates[0]] = "a"
    second_weights.loc[dates[0]] = 1.0
    third_assets = empty_assets.copy()
    third_weights = empty_weights.copy()
    third_assets.loc[dates[0]] = "b"
    third_weights.loc[dates[0]] = 1.0

    targets, exposures, _ = aggregate_sleeve_targets(
        (
            SleeveTargets("s1", 0, first_assets, first_weights, pd.DataFrame()),
            SleeveTargets("s2", 0, second_assets, second_weights, pd.DataFrame()),
            SleeveTargets("s3", 0, third_assets, third_weights, pd.DataFrame()),
        ),
        pd.Index(["a", "b"]),
    )

    assert exposures[dates[0]] == pytest.approx(1.0)
    assert targets[dates[0]].sum() == pytest.approx(1.0)
    assert targets[dates[0]].loc["a"] == pytest.approx(2.0 / 3.0)
    assert targets[dates[0]].loc["b"] == pytest.approx(1.0 / 3.0)


def test_fixed_stop_exits_and_waits_for_scheduled_reentry() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0, 70.0, 70.0, 70.0, 80.0],
            "bitcoin": [100.0] * 5,
        },
        index=dates,
    )
    market = _market(price)
    signal_panel = pd.DataFrame({"a": [1.0] * 5}, index=dates)
    spec = PhaseMomentumSpec(
        rebalance_days=3,
        phase_offsets=(0,),
        hold_rank=1,
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
        stop_loss_kind="fixed",
        stop_loss_pct=0.20,
    )

    sleeve = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name="stop_test", phase_offset=0
    )

    assert sleeve.assets.loc[dates[0]] == "a"
    assert sleeve.assets.loc[dates[1]] == "__cash__"
    assert pd.isna(sleeve.assets.loc[dates[2]])
    assert sleeve.assets.loc[dates[3]] == "a"


def test_trailing_stop_uses_high_watermark() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0, 110.0, 80.0, 80.0, 80.0],
            "bitcoin": [100.0] * 5,
        },
        index=dates,
    )
    market = _market(price)
    signal_panel = pd.DataFrame({"a": [1.0] * 5}, index=dates)
    spec = PhaseMomentumSpec(
        rebalance_days=3,
        phase_offsets=(0,),
        hold_rank=1,
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
        stop_loss_kind="trailing",
        stop_loss_pct=0.20,
    )

    sleeve = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name="trailing_test", phase_offset=0
    )

    assert sleeve.assets.loc[dates[0]] == "a"
    assert sleeve.assets.loc[dates[2]] == "__cash__"


def test_asset_trend_filter_skips_leader_below_own_moving_average() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0, 100.0, 100.0, 100.0, 100.0],
            "b": [100.0, 101.0, 102.0, 103.0, 104.0],
            "bitcoin": [100.0] * 5,
        },
        index=dates,
    )
    market = _market(price)
    signal_panel = pd.DataFrame(
        {
            "a": [2.0, 2.0, 2.0, 2.0, 2.0],
            "b": [1.0, 1.0, 1.0, 1.0, 1.0],
        },
        index=dates,
    )
    spec = PhaseMomentumSpec(
        rebalance_days=2,
        phase_offsets=(0,),
        hold_rank=1,
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
        use_asset_trend_filter=True,
        asset_ma_window=2,
    )

    sleeve = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name="trend_test", phase_offset=0
    )

    assert sleeve.assets.loc[dates[1]] == "b"


def test_selection_history_records_score_rank_not_column_position() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0] * 3,
            "b": [100.0] * 3,
            "c": [100.0] * 3,
            "bitcoin": [100.0] * 3,
        },
        index=dates,
    )
    market = _market(price)
    # "c" leads on every day but is the last column of the signal panel.
    signal_panel = pd.DataFrame(
        {"a": [1.0] * 3, "b": [2.0] * 3, "c": [3.0] * 3},
        index=dates,
    )
    spec = PhaseMomentumSpec(
        rebalance_days=1,
        phase_offsets=(0,),
        hold_rank=2,
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
    )

    sleeve = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name="rank_test", phase_offset=0
    )

    history = sleeve.selection_history
    assert history["selected_asset"].tolist() == ["c", "c", "c"]
    assert history["selected_rank"].tolist() == [1, 1, 1]


def test_asset_trend_filter_keeps_trending_incumbent_between_checks() -> None:
    dates = pd.date_range("2024-01-01", periods=7, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            "b": [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0],
            "bitcoin": [100.0] * 7,
        },
        index=dates,
    )
    market = _market(price)
    # "a" leads on day 1, then stays rank 2 and above its own moving average.
    signal_panel = pd.DataFrame(
        {"a": [2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0], "b": [1.0, 1.0, 2.0, 2.0, 2.0, 2.0, 2.0]},
        index=dates,
    )
    spec = PhaseMomentumSpec(
        rebalance_days=3,
        phase_offsets=(0,),
        hold_rank=2,
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
        use_asset_trend_filter=True,
        asset_ma_window=2,
    )

    sleeve = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name="trend_hold", phase_offset=0
    )

    assert sleeve.selection_history["selected_asset"].tolist()[1:] == ["a"] * 6


def test_missing_volatility_leaves_the_sleeve_in_cash() -> None:
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    volatility = pd.DataFrame({"a": [float("nan"), float("nan")]}, index=dates)

    assert _desired_exposure(volatility, dates[1], "a", target_volatility=0.8) == 0.0
    assert _desired_exposure(volatility, dates[1], "unknown", target_volatility=0.8) == 0.0


def test_parameter_ensemble_gives_each_parameter_set_the_same_weight() -> None:
    specs = (
        PhaseMomentumSpec(rebalance_days=1, phase_offsets=(0,)),
        PhaseMomentumSpec(rebalance_days=5, phase_offsets=(0, 1, 2, 3, 4)),
    )

    weights = parameter_ensemble_sleeve_weights(specs, signal_count=2)

    # 2 signals x 1 phase, then 2 signals x 5 phases, in build order.
    assert len(weights) == 2 + 10
    assert sum(weights[:2]) == pytest.approx(0.5)
    assert sum(weights[2:]) == pytest.approx(0.5)


def test_aggregate_sleeve_targets_applies_explicit_sleeve_weights() -> None:
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    sleeves = []
    for asset in ("a", "b", "b"):
        assets = pd.Series(pd.NA, index=dates, dtype="object")
        weights = pd.Series(float("nan"), index=dates, dtype=float)
        assets.loc[dates[0]] = asset
        weights.loc[dates[0]] = 1.0
        sleeves.append(SleeveTargets("s", 0, assets, weights, pd.DataFrame()))

    targets, exposures, _ = aggregate_sleeve_targets(
        tuple(sleeves), pd.Index(["a", "b"]), sleeve_weights=(0.5, 0.25, 0.25)
    )

    assert targets[dates[0]].loc["a"] == pytest.approx(0.5)
    assert targets[dates[0]].loc["b"] == pytest.approx(0.5)
    assert exposures[dates[0]] == pytest.approx(1.0)


def test_parameter_ensemble_build_uses_equal_weight_per_parameter_set() -> None:
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
            # BTC falls below its moving average, closing the gated spec.
            "bitcoin": [100.0, 99.0, 98.0, 97.0, 96.0, 95.0],
        },
        index=dates,
    )
    market = _market(price)
    universe = _universe([(date, "a") for date in dates])
    common = dict(btc_ma_window=2, btc_confirm_days=1, target_volatility=10.0, vol_window=2)
    ungated_one_phase = PhaseMomentumSpec(
        rebalance_days=1, phase_offsets=(0,), use_btc_gate=False, **common
    )
    gated_five_phases = PhaseMomentumSpec(
        rebalance_days=5, phase_offsets=(0, 1, 2, 3, 4), **common
    )

    built = build_parameter_ensemble_targets(
        market,
        universe,
        dates,
        parameter_specs=(ungated_one_phase, gated_five_phases),
        signal_specs=(MomentumSignalSpec(name="one_day", window_weights=((1, 1.0),)),),
    )

    # Half the book follows the ungated spec; per-sleeve weighting gave 1/6.
    assert built.exposures[max(built.exposures)] == pytest.approx(0.5)


def test_parameter_ensemble_combines_pre_specified_specs() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0 + index for index in range(12)],
            "b": [100.0 + 2.0 * index for index in range(12)],
            "bitcoin": [100.0] * 12,
        },
        index=dates,
    )
    market = _market(price)
    universe = _universe([(date, "a") for date in dates] + [(date, "b") for date in dates])
    specs = (PhaseMomentumSpec(), PhaseMomentumSpec(hold_rank=1))
    signals = (
        MomentumSignalSpec(name="one_day", window_weights=((1, 1.0),)),
        MomentumSignalSpec(name="two_day", window_weights=((2, 1.0),)),
    )

    built = build_parameter_ensemble_targets(
        market,
        universe,
        dates,
        parameter_specs=specs,
        signal_specs=signals,
    )

    assert len(built.sleeve_targets) == 12
    assert built.targets
    assert all(exposure <= 1.0 + 1e-12 for exposure in built.exposures.values())


def _five_coin_panel() -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0, 100.0, 110.0, 110.0, 121.0],
            "b": [100.0, 100.0, 100.0, 100.0, 100.0],
            "c": [100.0, 100.0, 90.0, 90.0, 81.0],
            "d": [100.0, 100.0, 105.0, 105.0, 110.25],
            "e": [100.0, 100.0, 95.0, 95.0, 90.25],
        },
        index=dates,
    )
    return price, dates


def test_top20_dispersion_is_cross_sectional_std_of_trailing_returns() -> None:
    price, dates = _five_coin_panel()
    market = _market(price)
    universe = _universe([(date, coin) for date in dates for coin in price.columns])

    dispersion = top20_dispersion(market, universe, dates, window=2)

    # Trailing 2D returns on the last day: [0.10, 0.00, -0.10, 0.05, -0.05];
    # sample std (ddof=1) = sqrt(0.025 / 4).
    assert dispersion.loc[dates[-1]] == pytest.approx(0.0790569, rel=1e-4)


def test_top20_dispersion_needs_at_least_five_usable_members() -> None:
    price, dates = _five_coin_panel()
    market = _market(price)
    universe = _universe(
        [(date, coin) for date in dates for coin in ("a", "b", "c", "d")]
    )

    dispersion = top20_dispersion(market, universe, dates, window=2)

    assert pd.isna(dispersion.loc[dates[-1]])


def test_top20_dispersion_rejects_a_window_below_two() -> None:
    price, dates = _five_coin_panel()
    market = _market(price)
    universe = _universe([(date, coin) for date in dates for coin in price.columns])

    with pytest.raises(ValueError):
        top20_dispersion(market, universe, dates, window=1)


def test_dispersion_exposure_scales_down_only_above_the_rolling_target() -> None:
    series = pd.Series([0.1] * 10 + [0.2])

    multiplier = dispersion_exposure(series, percentile=0.75, lookback=5, min_periods=2)

    # A flat stretch has target == current, so the overlay is a no-op.
    assert multiplier.iloc[:10].eq(1.0).all()
    # The spike sits above its own 75th percentile, so it is scaled to 0.1/0.2.
    assert multiplier.iloc[-1] == pytest.approx(0.5)


def test_dispersion_exposure_defaults_to_one_when_flat_or_missing() -> None:
    flat = dispersion_exposure(pd.Series([0.1] * 20), percentile=0.75, lookback=10)
    assert flat.eq(1.0).all()

    sparse = dispersion_exposure(
        pd.Series([float("nan"), float("nan"), 0.1]),
        percentile=0.75,
        lookback=2,
        min_periods=1,
    )
    assert sparse.iloc[0] == pytest.approx(1.0)
    assert sparse.iloc[-1] == pytest.approx(1.0)


def test_dispersion_exposure_rejects_bad_parameters() -> None:
    series = pd.Series([0.1, 0.2])

    with pytest.raises(ValueError):
        dispersion_exposure(series, percentile=0.0)
    with pytest.raises(ValueError):
        dispersion_exposure(series, percentile=1.5)
    with pytest.raises(ValueError):
        dispersion_exposure(series, lookback=1)


def test_sleeve_weight_is_scaled_by_the_dispersion_multiplier() -> None:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    price = pd.DataFrame(
        {
            "a": [100.0 + index for index in range(12)],
            "b": [100.0 - index for index in range(12)],
            "bitcoin": [100.0] * 12,
        },
        index=dates,
    )
    market = _market(price)
    universe = _universe([(date, "a") for date in dates] + [(date, "b") for date in dates])
    signal_spec = MomentumSignalSpec(name="one_day", window_weights=((1, 1.0),))
    signal_panel = build_signal_panel(market, universe, signal_spec, include_btc=False)
    spec = PhaseMomentumSpec(
        rebalance_days=2,
        phase_offsets=(0,),
        hold_rank=1,
        btc_ma_window=2,
        btc_confirm_days=1,
        target_volatility=10.0,
        vol_window=2,
    )

    baseline = build_sleeve_targets(
        market, signal_panel, dates, spec, signal_name=signal_spec.name, phase_offset=0
    )
    scaled = build_sleeve_targets(
        market,
        signal_panel,
        dates,
        spec,
        signal_name=signal_spec.name,
        phase_offset=0,
        dispersion_multiplier=pd.Series(0.5, index=dates),
    )

    first = baseline.weights[baseline.weights > 0.0].index[0]
    assert scaled.weights.loc[first] == pytest.approx(0.5 * baseline.weights.loc[first])
