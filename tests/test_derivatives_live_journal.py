from __future__ import annotations

from pathlib import Path

from atlas20.derivatives.live_journal import (
    JOURNAL_COLUMNS,
    JournalEntry,
    append_capital_flow,
    latest_row,
    load_journal,
    net_capital_flow,
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
        capital_flow=kwargs.get("capital_flow", 0.0),
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


def test_net_capital_flow_is_scoped_to_the_ledger_period(tmp_path: Path) -> None:
    path = tmp_path / "capital_flows.csv"
    append_capital_flow(
        path,
        timestamp_utc="2026-11-03T04:00:00+00:00",
        amount_usdt=100.0,
        note="deposit",
    )
    append_capital_flow(
        path,
        timestamp_utc="2026-11-04T11:15:00+00:00",
        amount_usdt=400.0,
        note="deposit",
    )
    append_capital_flow(
        path,
        timestamp_utc="2026-11-04T12:00:00+00:00",
        amount_usdt=-25.0,
        note="withdrawal",
    )

    flow = net_capital_flow(
        path,
        after="2026-11-04T03:06:00+00:00",
        through="2026-11-04T11:30:00+00:00",
    )

    assert flow == 400.0


def test_latest_row_returns_the_most_recent_ledger_row(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    upsert_entry(path, _entry("2026-11-03", 100.0, 0.0))
    upsert_entry(path, _entry("2026-11-04", 101.0, 1.0))

    latest = latest_row(load_journal(path))

    assert latest is not None
    assert latest["date"] == "2026-11-04"
    assert latest["equity"] == 101.0


def test_old_journal_rows_default_missing_capital_flow_to_zero(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    path.write_text(
        "date,run_at_utc,signal_date,equity,position_value,cash,day_pnl,day_return,"
        "fees_today,funding_total,unrealised_pnl,positions,trades,notes\n"
        "2026-10-31,2026-10-31T03:06:00+00:00,2026-10-30,99.68,0,99.68,0,0,"
        "0,0,0,[],[],[]\n",
        encoding="utf-8",
    )

    frame = load_journal(path)

    assert float(frame.iloc[0]["capital_flow"]) == 0.0
