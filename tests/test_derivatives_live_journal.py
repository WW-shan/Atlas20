from __future__ import annotations

from pathlib import Path

from atlas20.derivatives.live_journal import (
    JOURNAL_COLUMNS,
    JournalEntry,
    load_journal,
    previous_row,
    upsert_entry,
)


def _entry(date: str, equity: float, day_pnl: float | None, **kwargs) -> JournalEntry:
    return JournalEntry(
        date=date,
        run_at_utc=f"{date}T03:05:00+00:00",
        signal_date="2026-10-08",
        equity=equity,
        position_value=75.0,
        cash=equity,
        day_pnl=day_pnl,
        day_return=None if day_pnl is None else day_pnl / 100.0,
        fees_today=0.045,
        funding_total=0.0,
        unrealised_pnl=0.23,
        positions=kwargs.get("positions", [{"asset": "near", "qty": 14.0}]),
        trades=kwargs.get("trades", [{"side": "buy", "qty": 14.0}]),
        notes=kwargs.get("notes", []),
    )


def test_missing_journal_is_an_empty_frame(tmp_path: Path) -> None:
    frame = load_journal(tmp_path / "journal.csv")

    assert frame.empty
    assert list(frame.columns) == JOURNAL_COLUMNS


def test_entries_accumulate_and_previous_row_walks_back(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"

    upsert_entry(path, _entry("2026-10-10", 100.0, None))
    upsert_entry(path, _entry("2026-10-11", 101.5, 1.5))

    frame = load_journal(path)
    assert list(frame["date"]) == ["2026-10-10", "2026-10-11"]
    previous = previous_row(frame, "2026-10-11")
    assert previous is not None
    assert previous["equity"] == 100.0
    assert previous_row(frame, "2026-10-10") is None
    assert previous_row(frame, "2026-10-12")["equity"] == 101.5


def test_rerunning_a_day_replaces_its_row_instead_of_double_counting(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"

    upsert_entry(path, _entry("2026-10-11", 101.5, 1.5))
    upsert_entry(path, _entry("2026-10-11", 101.7, 1.7))

    frame = load_journal(path)
    assert len(frame) == 1
    assert float(frame.iloc[0]["equity"]) == 101.7


def test_positions_and_trades_round_trip_as_json(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    entry = _entry("2026-10-11", 100.0, None, notes=["全仓：跳过 1 笔逐仓保证金调整"])

    upsert_entry(path, entry)

    frame = load_journal(path)
    import json

    positions = json.loads(frame.iloc[0]["positions"])
    trades = json.loads(frame.iloc[0]["trades"])
    notes = json.loads(frame.iloc[0]["notes"])
    assert positions[0]["asset"] == "near"
    assert trades[0]["side"] == "buy"
    assert notes == ["全仓：跳过 1 笔逐仓保证金调整"]
