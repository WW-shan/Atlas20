from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_detect_membership_events_ignores_initial_members_and_uses_cooldown() -> None:
    from scripts.diagnose_top20_membership_events import detect_membership_events

    index = pd.date_range("2022-01-01", periods=10, freq="D", tz="UTC")
    present = pd.DataFrame(False, index=index, columns=["a", "b"])
    present.loc[index[3:7], "a"] = True
    present["b"] = True

    events = detect_membership_events(present, confirmation_days=2, cooldown_days=3)

    assert events[["coin_id", "event_type"]].values.tolist() == [
        ["a", "entry"],
        ["a", "exit"],
    ]
    assert events["event_date"].tolist() == [index[4], index[8]]


def test_forward_log_returns_start_at_next_close() -> None:
    from scripts.diagnose_top20_membership_events import forward_log_returns

    index = pd.date_range("2022-01-01", periods=4, freq="D", tz="UTC")
    price = pd.DataFrame({"a": [100.0, 110.0, 121.0, 133.1]}, index=index)

    result = forward_log_returns(price, horizon=2)

    assert result.iloc[0, 0] == pytest.approx(np.log(121.0 / 110.0))
    assert np.isnan(result.iloc[2, 0])


def test_event_study_verdict_requires_stable_signs() -> None:
    from scripts.diagnose_top20_membership_events import event_study_verdict

    summary = pd.DataFrame(
        [
            {"confirmation_days": 3, "horizon_days": 7, "event_type": "entry", "sample": "discovery", "mean_btc_excess": 0.02},
            {"confirmation_days": 3, "horizon_days": 7, "event_type": "entry", "sample": "validation", "mean_btc_excess": 0.01},
            {"confirmation_days": 3, "horizon_days": 7, "event_type": "exit", "sample": "discovery", "mean_btc_excess": -0.01},
            {"confirmation_days": 3, "horizon_days": 7, "event_type": "exit", "sample": "validation", "mean_btc_excess": -0.02},
        ]
    )

    verdict, reasons = event_study_verdict(summary)

    assert verdict == "candidate-for-backtest"
    assert reasons == ["m=3, h=7 passes sign stability"]
