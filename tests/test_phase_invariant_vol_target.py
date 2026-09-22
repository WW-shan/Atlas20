from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_phase_invariant_vol_target import (
    _daily_target_series,
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


def test_daily_target_weights_are_forward_filled_between_rebalances() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    targets = {index[0]: pd.Series({"asset_a": 1.0})}
    exposure = pd.Series([0.5], index=[index[0]])

    assets, weights = _daily_target_series(targets, exposure, index)

    assert assets.tolist() == ["asset_a", "asset_a", "asset_a", "asset_a"]
    assert weights.tolist() == pytest.approx([0.5, 0.5, 0.5, 0.5])
