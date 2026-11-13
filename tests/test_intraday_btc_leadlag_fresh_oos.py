from __future__ import annotations

import pandas as pd
import pytest


def test_oos_events_require_complete_holding_period_inside_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.run_intraday_btc_leadlag_fresh_oos as module
    from scripts.run_intraday_btc_leadlag_phase_backtest import PhaseVariant

    index = pd.date_range("2026-09-30 20:00", periods=20, freq="30min", tz="UTC")
    close = pd.DataFrame({"bitcoin": 100.0, "A": 10.0, "B": 20.0}, index=index)
    beta = pd.DataFrame({"A": 1.0, "B": 1.0}, index=index)
    membership = pd.DataFrame(True, index=index, columns=["A", "B"])
    gap = pd.DataFrame(0.0, index=index, columns=["A", "B"])
    shock = pd.Series(4.0, index=index)
    monkeypatch.setattr(module, "build_signal_gap", lambda **_: (gap, shock))
    monkeypatch.setattr(module, "_select_cross_section", lambda *_, **__: (("A",), ("B",)))

    events = module.build_oos_events(
        variant=PhaseVariant("test", signal_bars=2, future_bars=4, shock_threshold=3.0),
        close_frame=close,
        beta=beta,
        membership=membership,
        assets=["A", "B"],
        oos_start=pd.Timestamp("2026-10-01 00:00", tz="UTC"),
        oos_end=pd.Timestamp("2026-10-01 03:00", tz="UTC"),
    )

    assert len(events) == 1
    assert events[0].signal_time == pd.Timestamp("2026-10-01 00:00", tz="UTC")
    assert events[0].entry_time == pd.Timestamp("2026-10-01 00:30", tz="UTC")
    assert events[0].exit_time == pd.Timestamp("2026-10-01 02:00", tz="UTC")


def test_oos_tier_labels_mixed_and_failed_correctly() -> None:
    from scripts.run_intraday_btc_leadlag_fresh_oos import _tier

    assert _tier({"multiple": 1.1, "max_drawdown": -0.1}, {"multiple": 1.01}) == "fresh-oos-positive"
    assert _tier({"multiple": 1.1, "max_drawdown": -0.1}, {"multiple": 0.99}) == "fresh-oos-mixed"
    assert _tier({"multiple": 0.99, "max_drawdown": -0.1}, {"multiple": 1.01}) == "fresh-oos-failed"


def test_oos_tier_rejects_large_drawdown_even_when_both_costs_are_positive() -> None:
    from scripts.run_intraday_btc_leadlag_fresh_oos import _tier

    assert _tier({"multiple": 1.1, "max_drawdown": -0.2}, {"multiple": 1.01}) == "fresh-oos-mixed"
