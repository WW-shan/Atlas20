from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_decision_point_ablation import apply_immediate_asset_stop_overlay


def test_immediate_asset_stop_waits_for_reentry_confirmation() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D")
    base_targets = {
        index[0]: pd.Series({"asset_a": 1.0}),
    }
    exit_confirmed = pd.DataFrame(
        {"asset_a": [False, True, True, False, False]},
        index=index,
    )
    reentry_confirmed = pd.DataFrame(
        {"asset_a": [False, False, False, True, True]},
        index=index,
    )

    targets = apply_immediate_asset_stop_overlay(
        base_targets,
        exit_confirmed,
        reentry_confirmed,
    )

    assert targets[index[0]].to_dict() == {"asset_a": 1.0}
    assert targets[index[1]].empty
    assert index[2] not in targets
    assert targets[index[3]].to_dict() == {"asset_a": 1.0}


def test_immediate_asset_stop_rejects_missing_reentry_signal() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    base_targets = {index[0]: pd.Series({"asset_a": 1.0})}
    exit_confirmed = pd.DataFrame({"asset_a": [False, True]}, index=index)
    reentry_confirmed = pd.DataFrame({"asset_b": [False, True]}, index=index)

    with pytest.raises(ValueError, match="missing assets"):
        apply_immediate_asset_stop_overlay(
            base_targets,
            exit_confirmed,
            reentry_confirmed,
        )
