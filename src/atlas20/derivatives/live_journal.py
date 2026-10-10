"""Append-only daily ledger for the live derivatives account.

Every daily run writes exactly one row: what the account was worth, what it
held, what it traded, what it cost, and how much it made or lost since the
previous row.  The Telegram report is a rendering of this ledger plus the
venue read-back, so the numbers in the message and the numbers in the file
can never drift apart.

The journal is idempotent per ``date``: re-running on the same day (a forced
re-run after a manual fix) replaces that day's row instead of appending a
second one, so day-over-day PnL never double counts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

JOURNAL_COLUMNS = [
    "date",
    "run_at_utc",
    "signal_date",
    "equity",
    "position_value",
    "cash",
    "day_pnl",
    "day_return",
    "fees_today",
    "funding_total",
    "unrealised_pnl",
    "positions",
    "trades",
    "notes",
]


@dataclass(frozen=True)
class JournalEntry:
    date: str
    run_at_utc: str
    signal_date: str
    equity: float
    position_value: float
    cash: float
    day_pnl: float | None
    day_return: float | None
    fees_today: float
    funding_total: float
    unrealised_pnl: float
    positions: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "run_at_utc": self.run_at_utc,
            "signal_date": self.signal_date,
            "equity": self.equity,
            "position_value": self.position_value,
            "cash": self.cash,
            "day_pnl": self.day_pnl,
            "day_return": self.day_return,
            "fees_today": self.fees_today,
            "funding_total": self.funding_total,
            "unrealised_pnl": self.unrealised_pnl,
            "positions": json.dumps(self.positions, ensure_ascii=False, sort_keys=True),
            "trades": json.dumps(self.trades, ensure_ascii=False, sort_keys=True),
            "notes": json.dumps(self.notes, ensure_ascii=False),
        }


def load_journal(path: Path) -> pd.DataFrame:
    """Read the ledger; a missing file is simply an empty ledger."""

    if not Path(path).exists():
        return pd.DataFrame(columns=JOURNAL_COLUMNS)
    frame = pd.read_csv(path)
    for column in JOURNAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame[JOURNAL_COLUMNS]


def previous_row(frame: pd.DataFrame, date: str) -> dict[str, Any] | None:
    """Most recent ledger row strictly before ``date`` (string compare, ISO)."""

    if frame.empty:
        return None
    candidates = frame[frame["date"].astype(str) < str(date)]
    if candidates.empty:
        return None
    record = candidates.sort_values("date").iloc[-1].to_dict()
    return {key: (None if pd.isna(value) else value) for key, value in record.items()}


def upsert_entry(path: Path, entry: JournalEntry) -> pd.DataFrame:
    """Write ``entry`` for its date, replacing any earlier row for that date."""

    frame = load_journal(path)
    row = pd.DataFrame([entry.as_row()])[JOURNAL_COLUMNS]
    if not frame.empty:
        frame = frame[frame["date"].astype(str) != str(entry.date)]
    frame = pd.concat([frame, row], ignore_index=True) if not frame.empty else row
    frame = frame.sort_values("date").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame
