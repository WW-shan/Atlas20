from __future__ import annotations

from pathlib import Path

import pytest

from atlas20.derivatives.live_journal import (
    JOURNAL_COLUMNS,
    JournalEntry,
    append_capital_flow,
    latest_row,
    load_capital_flows,
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


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    ("timestamp", "amount"),
    [
        ("2026-11-04", float("nan")),
        ("2026-11-04", float("inf")),
        ("2026-11-04", float("-inf")),
        ("NaT", 100.0),
    ],
)
def test_invalid_capital_flow_does_not_change_the_file(
    tmp_path: Path,
    existing: bool,
    timestamp: str,
    amount: float,
) -> None:
    path = tmp_path / "capital_flows.csv"
    if existing:
        append_capital_flow(path, timestamp_utc="2026-11-03", amount_usdt=25.0)
    before = path.read_bytes() if existing else None

    with pytest.raises(ValueError):
        append_capital_flow(path, timestamp_utc=timestamp, amount_usdt=amount)

    assert (path.read_bytes() if path.exists() else None) == before


@pytest.mark.parametrize("amount", ["inf", "-inf"])
def test_loading_non_finite_capital_flow_rejects_the_ledger(tmp_path: Path, amount: str) -> None:
    path = tmp_path / "capital_flows.csv"
    path.write_text(
        f"timestamp_utc,amount_usdt,note\n2026-11-04T11:17:00Z,{amount},deposit\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid timestamp or amount"):
        load_capital_flows(path)


def test_capital_flows_accept_mixed_timestamp_precision(tmp_path: Path) -> None:
    path = tmp_path / "capital_flows.csv"
    path.write_text(
        "timestamp_utc,amount_usdt,note\n"
        "2026-11-04 11:00:00+00:00,400.0,deposit\n"
        "2026-11-13 19:56:16.525604+00:00,-0.18,drill fees\n",
        encoding="utf-8",
    )

    frame = load_capital_flows(path)

    assert len(frame) == 2
    assert frame["timestamp_utc"].notna().all()
    assert frame["amount_usdt"].tolist() == pytest.approx([400.0, -0.18])


def test_journal_rejects_a_non_numeric_capital_flow_instead_of_zeroing_it(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    path.write_text(
        "date,run_at_utc,signal_date,equity,position_value,cash,capital_flow,"
        "day_pnl,day_return,fees_today,funding_total,unrealised_pnl,positions,trades,notes\n"
        "2026-10-31,2026-10-31T03:06:00+00:00,2026-10-30,99.68,0,99.68,oops,"
        "0,0,0,0,0,[],[],[]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="capital_flow"):
        load_journal(path)


def test_journal_rejects_duplicate_dates(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    upsert_entry(path, _entry("2026-10-31", 100.0, 0.0))
    frame = load_journal(path)
    duplicate = frame.copy()
    duplicate.to_csv(path, index=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(duplicate.to_csv(index=False, header=False))

    with pytest.raises(ValueError, match="duplicate date"):
        load_journal(path)
