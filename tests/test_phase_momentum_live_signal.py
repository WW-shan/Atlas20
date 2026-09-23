from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from atlas20.strategies.phase_momentum import (
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    SleeveTargets,
)
from scripts.run_phase_momentum_live_signal import _latest_signal_payload


def test_latest_signal_uses_latest_target_and_reports_sleeve_state() -> None:
    index = pd.date_range("2024-01-01", periods=16, freq="D")
    market = SimpleNamespace(
        price=pd.DataFrame(
            {
                "ethereum": [100.0] * len(index),
                "solana": [50.0] * len(index),
                "bitcoin": list(range(100, 100 + len(index))),
            },
            index=index,
        )
    )

    first_assets = pd.Series(pd.NA, index=index, dtype="object")
    first_weights = pd.Series(float("nan"), index=index, dtype=float)
    first_assets.loc[index[0]] = "ethereum"
    first_weights.loc[index[0]] = 0.75
    first_assets.loc[index[9]] = "solana"
    first_weights.loc[index[9]] = 0.50

    second_assets = pd.Series(pd.NA, index=index, dtype="object")
    second_weights = pd.Series(float("nan"), index=index, dtype=float)
    second_assets.loc[index[0]] = "__cash__"
    second_weights.loc[index[0]] = 0.0

    built = PhaseMomentumBuildResult(
        targets={
            index[0]: pd.Series({"ethereum": 0.50}),
            index[9]: pd.Series({"ethereum": 0.25, "solana": 0.25}),
        },
        exposures={index[0]: 0.50, index[9]: 0.50},
        selection_history=pd.DataFrame(),
        sleeve_targets=(
            SleeveTargets("signal_a", 0, first_assets, first_weights, pd.DataFrame()),
            SleeveTargets("signal_b", 1, second_assets, second_weights, pd.DataFrame()),
        ),
    )
    spec = PhaseMomentumSpec(btc_ma_window=2, btc_confirm_days=1)

    payload = _latest_signal_payload(
        market,
        built,
        spec,
        as_of=index[-1],
    )

    assert payload["as_of"] == "2024-01-16"
    assert payload["latest_target_date"] == "2024-01-10"
    assert payload["btc_gate_open"] is True
    assert payload["targets"] == {"ethereum": 0.25, "solana": 0.25}
    assert payload["gross_exposure"] == pytest.approx(0.50)
    assert payload["next_check_date"] == "2024-01-17"
    assert payload["sleeves"] == [
        {
            "signal_name": "signal_a",
            "phase_offset": 0,
            "asset": "solana",
            "weight": 0.50,
            "target_date": "2024-01-10",
        },
        {
            "signal_name": "signal_b",
            "phase_offset": 1,
            "asset": "__cash__",
            "weight": 0.0,
            "target_date": "2024-01-01",
        },
    ]
