from __future__ import annotations

import pandas as pd
import pytest


def test_single_event_builder_blocks_overlapping_trades(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.run_intraday_btc_leadlag_single_event as module
    from scripts.run_intraday_btc_leadlag_backtest import LeadLagVariant

    index = pd.date_range("2026-01-01", periods=20, freq="30min", tz="UTC")
    close = pd.DataFrame({"bitcoin": 100.0, "A": 10.0, "B": 20.0}, index=index)
    beta = pd.DataFrame({"A": 1.0, "B": 1.0}, index=index)
    membership = pd.DataFrame(True, index=index, columns=["A", "B"])
    gap = pd.DataFrame(0.0, index=index, columns=["A", "B"])
    shock = pd.Series(3.0, index=index)

    monkeypatch.setattr(module, "build_signal_gap", lambda **_: (gap, shock))
    monkeypatch.setattr(
        module,
        "_select_cross_section",
        lambda *_: (("A",), ("B",)),
    )

    events = module.build_single_events(
        variant=LeadLagVariant("test", signal_bars=2, future_bars=4),
        close_frame=close,
        beta=beta,
        membership=membership,
        assets=["A", "B"],
    )

    assert [event.signal_position for event in events] == [0, 4, 8, 12]
    assert [event.exit_position for event in events] == [4, 8, 12, 16]
    assert events[0].entry_position == 1


def test_single_event_builder_skips_signals_inside_holding_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.run_intraday_btc_leadlag_single_event as module
    from scripts.run_intraday_btc_leadlag_backtest import LeadLagVariant

    index = pd.date_range("2026-01-01", periods=8, freq="30min", tz="UTC")
    close = pd.DataFrame({"bitcoin": 100.0, "A": 10.0, "B": 20.0}, index=index)
    beta = pd.DataFrame({"A": 1.0, "B": 1.0}, index=index)
    membership = pd.DataFrame(True, index=index, columns=["A", "B"])
    gap = pd.DataFrame(0.0, index=index, columns=["A", "B"])
    shock = pd.Series([3.0, 3.0, 3.0, 3.0, 3.0, 0.0, 0.0, 0.0], index=index)
    monkeypatch.setattr(module, "build_signal_gap", lambda **_: (gap, shock))
    monkeypatch.setattr(module, "_select_cross_section", lambda *_: (("A",), ("B",)))

    events = module.build_single_events(
        variant=LeadLagVariant("test", signal_bars=1, future_bars=4),
        close_frame=close,
        beta=beta,
        membership=membership,
        assets=["A", "B"],
    )

    assert [event.signal_position for event in events] == [0]
    assert events[0].exit_position == 4
