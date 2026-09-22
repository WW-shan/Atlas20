from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_phase_invariant_vol_target import (
    _target_event_series,
    _exposure_series_for_targets,
    _volatility_target_variants,
)


def test_volatility_target_variants_are_unique_and_include_baseline() -> None:
    variants = _volatility_target_variants(
        cycles=(14, 21),
        target_vols=(0.4, 0.5),
        vol_windows=(30,),
        stop_modes=("none", "own75"),
        gate_modes=("none", "btc_ma200"),
    )

    assert (14, 0.4, 30, "none", "none") in variants
    assert (21, 0.5, 30, "own75", "btc_ma200") in variants
    assert len(variants) == len(set(variants))


def test_exposure_series_caps_target_volatility_at_one() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    price = pd.DataFrame(
        {"asset_a": [100.0, 100.0, 100.0, 100.0]},
        index=index,
    )
    targets = {index[0]: pd.Series({"asset_a": 1.0})}

    exposure = _exposure_series_for_targets(
        targets,
        price,
        target_volatility=0.4,
        vol_window=2,
    )

    assert exposure.loc[index[0]] == pytest.approx(1.0)


def test_target_events_are_sparse_and_not_forward_filled() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    targets = {index[0]: pd.Series({"asset_a": 1.0})}
    exposure = pd.Series([0.5], index=[index[0]])

    assets, weights = _target_event_series(targets, exposure, index)

    assert assets.iloc[0] == "asset_a"
    assert assets.iloc[1:].isna().all()
    assert weights.iloc[0] == pytest.approx(0.5)
    assert weights.iloc[1:].isna().all()
