from __future__ import annotations

import pandas as pd

from scripts.run_h5_regime_short_router import _btc_bear_regime, route_short_sleeves


def test_btc_bear_regime_uses_only_completed_close_history() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    close = pd.Series([3.0, 2.0, 1.0, 4.0, 5.0], index=index)

    regime = _btc_bear_regime(close, index, ma_window=3)

    assert regime.tolist() == [False, False, True, False, False]


def test_route_short_sleeves_switches_and_does_not_resurrect_stale_exits() -> None:
    calendar = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    bear = pd.Series([False, False, True, False, False], index=calendar)
    exit_schedule = {
        calendar[0]: pd.Series({"A": 0.025}),
        calendar[1]: pd.Series({"A": 0.025, "B": 0.025}),
        calendar[3]: pd.Series({"A": 0.025, "B": 0.025}),
        calendar[4]: pd.Series({"A": 0.025, "B": 0.025, "C": 0.025}),
    }
    bear_schedule = {calendar[2]: pd.Series({"X": 0.0625})}

    routed, audit = route_short_sleeves(
        calendar=calendar,
        bear=bear,
        bear_schedule=bear_schedule,
        non_bear_schedule=exit_schedule,
    )

    assert routed[calendar[0]].to_dict() == {"A": 0.025}
    assert routed[calendar[1]].to_dict() == {"A": 0.025, "B": 0.025}
    assert routed[calendar[2]].to_dict() == {"X": 0.0625}
    assert routed[calendar[3]].empty
    assert routed[calendar[4]].to_dict() == {"C": 0.025}
    assert audit["active_sleeve"].tolist() == [
        "funding_exit",
        "funding_exit",
        "bear_weak4",
        "funding_exit",
        "funding_exit",
    ]


def test_route_short_sleeves_waits_for_a_fresh_bear_rebalance() -> None:
    calendar = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    bear = pd.Series([False, True, True, True], index=calendar)
    bear_schedule = {calendar[0]: pd.Series({"X": 0.0625})}

    routed, _ = route_short_sleeves(
        calendar=calendar,
        bear=bear,
        bear_schedule=bear_schedule,
        non_bear_schedule={},
    )

    assert all(target.empty for target in routed.values())

def test_btc_bear_regime_aligns_naive_calendar_to_utc_prices() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    price_index = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    close = pd.Series([3.0, 2.0, 1.0, 4.0], index=price_index)

    regime = _btc_bear_regime(close, index, ma_window=3)

    assert regime.tolist() == [False, False, True, False]

