from __future__ import annotations

import pandas as pd
import pytest


def test_phase_builder_only_checks_phase_zero_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.run_intraday_btc_leadlag_phase_backtest as module

    index = pd.date_range("2026-01-01", periods=25, freq="30min", tz="UTC")
    close = pd.DataFrame({"bitcoin": 100.0, "A": 10.0, "B": 20.0}, index=index)
    beta = pd.DataFrame({"A": 1.0, "B": 1.0}, index=index)
    membership = pd.DataFrame(True, index=index, columns=["A", "B"])
    gap = pd.DataFrame(0.0, index=index, columns=["A", "B"])
    shock = pd.Series(4.0, index=index)
    monkeypatch.setattr(module, "build_signal_gap", lambda **_: (gap, shock))
    monkeypatch.setattr(module, "_select_cross_section", lambda *_, **__: (("A",), ("B",)))

    events = module.build_phase_events(
        variant=module.PhaseVariant("test", signal_bars=2, future_bars=8, shock_threshold=3.0),
        close_frame=close,
        beta=beta,
        membership=membership,
        assets=["A", "B"],
    )

    assert [event.signal_position for event in events] == [0, 8, 16]
    assert [event.entry_position for event in events] == [1, 9, 17]
    assert [event.exit_position for event in events] == [8, 16, 24]


def test_phase_builder_respects_the_higher_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.run_intraday_btc_leadlag_phase_backtest as module

    index = pd.date_range("2026-01-01", periods=17, freq="30min", tz="UTC")
    close = pd.DataFrame({"bitcoin": 100.0, "A": 10.0, "B": 20.0}, index=index)
    beta = pd.DataFrame({"A": 1.0, "B": 1.0}, index=index)
    membership = pd.DataFrame(True, index=index, columns=["A", "B"])
    gap = pd.DataFrame(0.0, index=index, columns=["A", "B"])
    shock = pd.Series(3.2, index=index)
    monkeypatch.setattr(module, "build_signal_gap", lambda **_: (gap, shock))
    monkeypatch.setattr(module, "_select_cross_section", lambda *_, **__: (("A",), ("B",)))

    events = module.build_phase_events(
        variant=module.PhaseVariant("test", signal_bars=2, future_bars=8, shock_threshold=3.5),
        close_frame=close,
        beta=beta,
        membership=membership,
        assets=["A", "B"],
    )

    assert events == []
