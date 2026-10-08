from __future__ import annotations

import pandas as pd

from scripts.run_event_driven_validation import (
    _rank_stop_asset_series,
    _risk_gate_asset_series,
    _scheduled_asset_series,
)


def test_rank_stop_keeps_the_btc_gate_cash_days_between_schedule_dates() -> None:
    # Incident: the rank stop read the BTC-gated base only on schedule dates,
    # so every mid-period risk-off (cash) day was overwritten with the
    # scheduled coin. hr5/c3/mh10 at 20 bps: 23.16x as run vs 21.14x with the
    # gate respected; 273 of its 717 held days were gate-cash days.
    index = pd.date_range("2022-01-01", periods=12, freq="D")
    schedule = [index[0], index[10]]
    scores = pd.DataFrame({"a": [0.9] * 12, "b": [0.1] * 12}, index=index)
    risk_on = pd.Series(True, index=index)
    risk_on.iloc[3:6] = False
    base = _scheduled_asset_series(scores, schedule, index)
    gated = _risk_gate_asset_series(
        base,
        risk_on,
        immediate_reentry=False,
        schedule_dates=set(schedule),
    )

    held = _rank_stop_asset_series(
        gated,
        scores,
        set(schedule),
        hold_rank=1,
        confirm_days=1,
        min_hold_days=0,
    )

    # Out on the risk-off flip, back only on the next scheduled date.
    assert gated.tolist() == ["a"] * 3 + [""] * 7 + ["a"] * 2
    assert held.tolist() == gated.tolist()
