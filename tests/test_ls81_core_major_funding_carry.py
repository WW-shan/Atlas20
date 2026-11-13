from __future__ import annotations

import pandas as pd
import pytest


def test_pit_funding_carry_uses_only_settlements_before_signal() -> None:
    from scripts.run_ls81_core_major_funding_carry import build_pit_funding_carry_schedule

    dates = pd.date_range("2022-01-01", "2022-01-15", freq="1D", tz="UTC")
    assets = ["a", "b", "c", "d", "e", "f", "g", "h"]
    funding = pd.DataFrame(
        {
            "a": [0.01] * 7 + [0.02] * 8,
            "b": [0.02] * 7 + [0.02] * 8,
            "c": [0.03] * 7 + [0.03] * 8,
            "d": [0.04] * 7 + [0.04] * 8,
            "e": [0.05] * 7 + [0.05] * 8,
            "f": [0.06] * 7 + [0.06] * 8,
            "g": [0.07] * 7 + [0.07] * 8,
            "h": [0.08] * 7 + [0.08] * 8,
        },
        index=dates,
    )

    schedule, audit = build_pit_funding_carry_schedule(
        funding_rates=funding,
        calendar=dates,
        assets=assets,
        rebalance_days=7,
        lookback_days=7,
        min_settlements=3,
        min_assets=6,
        count=2,
        per_asset_weight=0.25,
    )

    signal = pd.Timestamp("2022-01-08", tz="UTC")
    assert schedule[signal].to_dict() == {
        "a": 0.25,
        "b": 0.25,
        "g": -0.25,
        "h": -0.25,
    }
    assert audit.loc[audit["date"] == signal, "mean_funding"].notna().all()


def test_pit_funding_carry_excludes_base_book_overlap() -> None:
    from scripts.run_ls81_core_major_funding_carry import build_pit_funding_carry_schedule

    dates = pd.date_range("2022-01-01", "2022-01-15", freq="1D", tz="UTC")
    assets = ["a", "b", "c", "d", "e", "f", "g", "h"]
    funding = pd.DataFrame(
        {asset: [index / 1000.0] * len(dates) for index, asset in enumerate(assets)},
        index=dates,
    )
    base_targets = {
        pd.Timestamp("2022-01-01", tz="UTC"): pd.Series({"a": 0.5}),
    }

    schedule, _ = build_pit_funding_carry_schedule(
        funding_rates=funding,
        calendar=dates,
        assets=assets,
        base_targets=base_targets,
        rebalance_days=7,
        lookback_days=7,
        min_settlements=3,
        min_assets=6,
        count=2,
        per_asset_weight=0.25,
    )

    signal = pd.Timestamp("2022-01-08", tz="UTC")
    assert "a" not in schedule[signal].index
    assert set(schedule[signal].index) == {"b", "c", "g", "h"}


def test_pit_funding_carry_clears_sleeve_when_too_few_assets() -> None:
    from scripts.run_ls81_core_major_funding_carry import build_pit_funding_carry_schedule

    dates = pd.date_range("2022-01-01", "2022-01-15", freq="1D", tz="UTC")
    funding = pd.DataFrame(
        {"a": [0.01] * len(dates), "b": [0.02] * len(dates)},
        index=dates,
    )

    schedule, _ = build_pit_funding_carry_schedule(
        funding_rates=funding,
        calendar=dates,
        assets=["a", "b"],
        rebalance_days=7,
        lookback_days=7,
        min_settlements=3,
        min_assets=6,
        count=2,
        per_asset_weight=0.25,
    )

    assert schedule[pd.Timestamp("2022-01-08", tz="UTC")].empty


def test_pit_funding_carry_rejects_invalid_parameters() -> None:
    from scripts.run_ls81_core_major_funding_carry import build_pit_funding_carry_schedule

    with pytest.raises(ValueError, match="min_assets"):
        build_pit_funding_carry_schedule(
            funding_rates=pd.DataFrame(),
            calendar=pd.DatetimeIndex([]),
            assets=[],
            min_assets=3,
            count=2,
        )
