from __future__ import annotations

import json

import pandas as pd
import pytest

from atlas20.derivatives.live_journal import JournalEntry
from scripts.audit_live_track import _ledger_expected_equity, _pnl_chain_errors


def _entry(
    *,
    date: str,
    equity: float,
    capital_flow: float,
    day_pnl: float,
) -> JournalEntry:
    return JournalEntry(
        date=date,
        run_at_utc=f"{date}T03:06:00+00:00",
        signal_date=date,
        equity=equity,
        position_value=0.0,
        cash=equity,
        day_pnl=day_pnl,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        capital_flow=capital_flow,
    )


def test_ledger_expected_equity_includes_flow_after_the_latest_snapshot() -> None:
    last = {
        "equity": 99.68,
        "positions": json.dumps([]),
    }

    expected, mismatches = _ledger_expected_equity(
        last,
        current_positions=[],
        capital_flow=400.0,
    )

    assert expected == pytest.approx(499.68)
    assert mismatches == []


def test_pnl_chain_excludes_capital_flow_from_strategy_performance() -> None:
    journal = pd.DataFrame(
        [
            _entry(date="2026-11-03", equity=99.68, capital_flow=0.0, day_pnl=0.0).as_row(),
            _entry(date="2026-11-04", equity=499.68, capital_flow=400.0, day_pnl=0.0).as_row(),
        ]
    )

    assert _pnl_chain_errors(journal) == []
