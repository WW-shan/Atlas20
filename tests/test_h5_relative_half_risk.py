from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_h5_relative_half_risk import (
    rotate_long_targets_to_btc,
    scale_long_targets_by_state,
    weekly_relative_half_state,
)


def test_weekly_relative_half_state_activates_after_relative_underperformance() -> None:
    index = pd.date_range("2024-01-01", periods=22, freq="D", tz="UTC")
    shadow = pd.Series(0.0, index=index)
    btc = pd.Series([100.0 * (1.01**position) for position in range(len(index))], index=index)

    state, h5_return, btc_return = weekly_relative_half_state(
        index=index,
        shadow_returns=shadow,
        btc_close=btc,
        lookback_days=14,
        evaluation_days=7,
        anchor=index[0],
    )

    assert state.iloc[:14].eq(False).all()
    assert state.iloc[14:].eq(True).all()
    assert h5_return.iloc[-1] == 0.0
    assert btc_return.iloc[-1] > 0.0


def test_scale_long_targets_by_state_changes_only_on_state_or_target_events() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    risk_off = pd.Series([False, False, False, True, True], index=index)
    long_targets = {index[0]: pd.Series({"A": 1.2, "B": 0.2})}

    scaled = scale_long_targets_by_state(
        long_targets,
        index=index,
        risk_off=risk_off,
        risk_off_scale=0.5,
    )

    assert scaled[index[0]].to_dict() == {"A": 1.2, "B": 0.2}
    assert scaled[index[3]].to_dict() == {"A": 0.6, "B": 0.1}
    assert len(scaled) == 2


def test_rotate_long_targets_to_btc_preserves_long_gross() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    risk_off = pd.Series([False, False, False, True, True], index=index)
    long_targets = {index[0]: pd.Series({"ETH": 1.0, "bitcoin": 0.2, "SOL": 0.1})}

    rotated = rotate_long_targets_to_btc(
        long_targets,
        index=index,
        risk_off=risk_off,
        rotation_fraction=0.25,
    )

    assert rotated[index[0]].to_dict() == pytest.approx({"ETH": 1.0, "SOL": 0.1, "bitcoin": 0.2})
    assert rotated[index[3]].to_dict() == pytest.approx({"ETH": 0.75, "SOL": 0.075, "bitcoin": 0.475})
    assert rotated[index[3]].sum() == pytest.approx(1.3)
