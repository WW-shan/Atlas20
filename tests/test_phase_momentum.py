from __future__ import annotations

import pandas as pd
import pytest

from atlas20.strategies.phase_momentum import (
    MomentumSignalSpec,
    PhaseMomentumSpec,
    SleeveTargets,
    aggregate_sleeve_targets,
    build_parameter_ensemble_targets,
    build_signal_panel,
    build_sleeve_targets,
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
