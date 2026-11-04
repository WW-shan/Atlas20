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
from datetime import datetime
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
    "capital_flow",
    "day_pnl",
    "day_return",
    "fees_today",
    "funding_total",
    "unrealised_pnl",
    "positions",
    "trades",
    "notes",
]

CAPITAL_FLOW_COLUMNS = ["timestamp_utc", "amount_usdt", "note"]
DEFAULT_CAPITAL_FLOWS_FILE = Path("reports/derivatives_track_live/capital_flows.csv")


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
    capital_flow: float = 0.0
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
            "capital_flow": self.capital_flow,
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
    frame["capital_flow"] = pd.to_numeric(frame["capital_flow"], errors="coerce").fillna(0.0)
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


def latest_row(frame: pd.DataFrame) -> dict[str, Any] | None:
    """Most recent ledger row, including today's row."""

    if frame.empty:
        return None
    record = frame.sort_values(["date", "run_at_utc"]).iloc[-1].to_dict()
    return {key: (None if pd.isna(value) else value) for key, value in record.items()}


def _utc_timestamp(value: datetime | str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def load_capital_flows(path: Path) -> pd.DataFrame:
    """Load external deposits/withdrawals (positive = deposit)."""

    if not Path(path).exists():
        return pd.DataFrame(columns=CAPITAL_FLOW_COLUMNS)
    frame = pd.read_csv(path)
    missing = set(CAPITAL_FLOW_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"capital flows file is missing columns: {sorted(missing)}")
    frame = frame.loc[:, CAPITAL_FLOW_COLUMNS].copy()
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="coerce")
    frame["amount_usdt"] = pd.to_numeric(frame["amount_usdt"], errors="coerce")
    if frame["timestamp_utc"].isna().any() or frame["amount_usdt"].isna().any():
        raise ValueError("capital flows contain an invalid timestamp or amount")
    frame["note"] = frame["note"].fillna("").astype(str)
    return frame.sort_values("timestamp_utc").reset_index(drop=True)


def net_capital_flow(
    path: Path,
    *,
    after: datetime | str | None = None,
    through: datetime | str | None = None,
) -> float:
    """Net external cash flow in ``(after, through]`` in USDT."""

    frame = load_capital_flows(path)
    if frame.empty:
        return 0.0
    timestamps = frame["timestamp_utc"]
    if after is not None:
        frame = frame[timestamps > _utc_timestamp(after)]
        timestamps = frame["timestamp_utc"]
    if through is not None:
        frame = frame[timestamps <= _utc_timestamp(through)]
    return float(frame["amount_usdt"].sum())


def append_capital_flow(
    path: Path,
    *,
    timestamp_utc: datetime | str,
    amount_usdt: float,
    note: str = "",
) -> pd.DataFrame:
    """Append one external deposit (positive) or withdrawal (negative)."""

    amount = float(amount_usdt)
    if amount == 0.0:
        raise ValueError("capital flow amount must be non-zero")
    timestamp = _utc_timestamp(timestamp_utc)
    frame = load_capital_flows(path)
    row = pd.DataFrame(
        [{"timestamp_utc": timestamp, "amount_usdt": amount, "note": note}],
        columns=CAPITAL_FLOW_COLUMNS,
    )
    frame = pd.concat([frame, row], ignore_index=True).sort_values("timestamp_utc")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame.reset_index(drop=True)


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
