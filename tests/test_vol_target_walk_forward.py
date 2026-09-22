from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_vol_target_walk_forward import (
    _apply_switch_cost,
    _candidate_columns,
    _select_candidate,
    _walk_forward,
)


def test_candidate_columns_map_summary_rows() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = pd.DataFrame(
        {
            "c14_tv0.5_vw60_own75_btc_ma100_20bps": [0.0, 0.01, 0.0],
            "c7_tv0.6_vw60_own75_btc_ma100_20bps": [0.0, 0.02, 0.0],
        },
        index=index,
    )
    summary = pd.DataFrame(
        [
            {
                "cycle_days": 14,
                "target_volatility": 0.5,
                "vol_window": 60,
                "stop_mode": "own75",
                "gate_mode": "btc_ma100",
                "cost_bps": 20.0,
            },
            {
                "cycle_days": 7,
                "target_volatility": 0.6,
                "vol_window": 60,
                "stop_mode": "own75",
                "gate_mode": "btc_ma100",
                "cost_bps": 20.0,
            },
        ]
    )

    columns = _candidate_columns(summary, returns, 20.0)

    assert columns == [
        "c14_tv0.5_vw60_own75_btc_ma100_20bps",
        "c7_tv0.6_vw60_own75_btc_ma100_20bps",
    ]


def test_select_candidate_uses_only_trailing_returns() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    train = pd.DataFrame(
        {
            "a": [0.01, 0.01, 0.01, 0.01],
            "b": [-0.01, -0.01, -0.01, -0.01],
        },
        index=index,
    )

    selected, scores = _select_candidate(train, ["a", "b"], "multiple")

    assert selected == "a"
    assert scores["a"] > scores["b"]


def test_apply_switch_cost_only_changes_first_day() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    returns = pd.Series([0.01, 0.02], index=index)

    adjusted = _apply_switch_cost(returns, 40.0)

    assert adjusted.iloc[0] == pytest.approx((1.0 - 0.004) * 1.01 - 1.0)
    assert adjusted.iloc[1] == pytest.approx(0.02)


def test_walk_forward_chains_only_out_of_sample_windows() -> None:
    index = pd.date_range("2024-01-01", periods=12, freq="D")
    returns = pd.DataFrame(
        {
            "a": [0.01] * 12,
            "b": [-0.01] * 12,
        },
        index=index,
    )

    chained, selections = _walk_forward(
        returns,
        ["a", "b"],
        train_days=4,
        test_days=4,
        selection_metric="multiple",
        switch_cost_bps=0.0,
    )

    assert len(chained) == 8
    assert chained.index.min() == index[4]
    assert chained.index.max() == index[11]
    assert (selections["selected_candidate"] == "a").all()
    assert not selections["switched"].any()


def test_walk_forward_charges_switch_cost() -> None:
    index = pd.date_range("2024-01-01", periods=12, freq="D")
    # The first train window prefers a, the second prefers b, forcing one switch.
    a = [0.01] * 4 + [-0.01] * 8
    b = [-0.01] * 4 + [0.01] * 8
    returns = pd.DataFrame({"a": a, "b": b}, index=index)

    chained, selections = _walk_forward(
        returns,
        ["a", "b"],
        train_days=4,
        test_days=4,
        selection_metric="multiple",
        switch_cost_bps=40.0,
    )

    assert selections["switched"].sum() == 1
    switch_date = selections.loc[selections["switched"], "test_start"].iloc[0]
    expected = (1.0 - 0.004) * (1.0 + returns.loc[switch_date, "b"]) - 1.0
    assert chained.loc[switch_date] == pytest.approx(expected)
