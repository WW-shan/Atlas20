from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_short_events_require_negative_shock_and_non_overlap(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import scripts.run_intraday_down_shock_short as module
    from scripts.run_intraday_down_shock_short import DownShockVariant, build_short_events

    index = pd.date_range("2022-01-01", periods=40, freq="30min", tz="UTC")
    close = pd.DataFrame(100.0, index=index, columns=["bitcoin", *list("abcdefgh")])
    shock_z = pd.Series(float("nan"), index=index)
    shock_z.iloc[[2, 10, 20]] = -3.0
    gap = pd.DataFrame(
        [np.arange(8, dtype=float) - 4.0] * len(index),
        index=index,
        columns=list("abcdefgh"),
    )
    monkeypatch.setattr(module, "build_signal_gap", lambda **_: (gap, shock_z))
    beta = pd.DataFrame(0.5, index=index, columns=list("abcdefgh"))
    membership = pd.DataFrame(True, index=index, columns=list("abcdefgh"))
    variant = DownShockVariant("x", signal_bars=1, shock_threshold=2.5, hold_bars=4)

    events = build_short_events(
        variant=variant,
        close_frame=close,
        beta=beta,
        membership=membership,
        assets=list("abcdefgh"),
    )

    assert len(events) == 3
    for first, second in zip(events, events[1:]):
        assert first.exit_position < second.signal_position


def test_simulate_short_events_charges_both_sides_and_negative_return() -> None:
    from scripts.run_intraday_down_shock_short import ShortEvent, simulate_short_events

    index = pd.date_range("2022-01-01", periods=5, freq="30min", tz="UTC")
    returns = pd.DataFrame({"a": [0.0, -0.01, -0.01, 0.0, 0.0]}, index=index)
    event = ShortEvent(
        variant_id="x",
        signal_position=0,
        entry_position=1,
        exit_position=3,
        signal_time=index[0],
        entry_time=index[1],
        exit_time=index[3],
        z=-3.0,
        short_assets=("a",),
    )

    result = simulate_short_events(
        events=[event],
        bar_returns=returns,
        n_bars=len(index),
        cost_bps_per_side=10.0,
    )

    assert result["bar_returns"].iloc[1] == pytest.approx(0.009)
    assert result["bar_returns"].iloc[2] == pytest.approx(0.01)
    assert result["bar_returns"].iloc[3] == pytest.approx(-0.001)
    assert result["turnover"] == pytest.approx(2.0)


def test_select_candidate_ignores_validation_and_requires_12bps() -> None:
    from scripts.run_intraday_down_shock_short import select_candidate

    summary = pd.DataFrame(
        [
            {
                "variant_id": "good",
                "discovery_sharpe_6": 0.7,
                "discovery_sharpe_12": 0.2,
                "validation_sharpe_6": -10.0,
                "turnover_6": 10.0,
            },
            {
                "variant_id": "validation-winner",
                "discovery_sharpe_6": 0.1,
                "discovery_sharpe_12": 0.05,
                "validation_sharpe_6": 10.0,
                "turnover_6": 1.0,
            },
            {
                "variant_id": "cost-fragile",
                "discovery_sharpe_6": 2.0,
                "discovery_sharpe_12": -0.1,
                "validation_sharpe_6": 10.0,
                "turnover_6": 20.0,
            },
        ]
    )

    assert select_candidate(summary) == "good"
