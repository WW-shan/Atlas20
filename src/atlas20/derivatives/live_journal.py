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
from math import isfinite
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
_FILLED_STATUS = "filled"


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


def protected_short_symbols(frame: pd.DataFrame) -> set[str]:
    """Current short symbols whose whole open cycle carried a venue stop.

    A scan of all historical sells is unsafe: an old protected short could
    mask a later manual or failed reopen without a stop.  This state machine
    follows quantity and position snapshots in chronological order so only the
    *current* short cycle can make a symbol protected.
    """

    if frame.empty:
        return set()

    def _records(value: Any) -> list[dict[str, Any]] | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            parsed = json.loads(value or "[]")
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, list):
            return None
        return [item for item in parsed if isinstance(item, dict)]

    def _qty(trade: dict[str, Any]) -> float:
        has_quantity = any(
            key in trade for key in ("qty", "filled_size", "requested_size")
        )
        for key in ("qty", "filled_size", "requested_size"):
            try:
                value = abs(float(trade.get(key) or 0.0))
            except (TypeError, ValueError):
                value = 0.0
            if value > 0.0:
                return value
        # Legacy test/ledger rows carried only symbol/side/stop.
        return 0.0 if has_quantity else 1.0

    def _stop_is_confirmed(trade: dict[str, Any]) -> bool:
        try:
            stop_loss = float(trade.get("stop_loss") or 0.0)
        except (TypeError, ValueError):
            return False
        if stop_loss <= 0.0:
            return False
        requested_raw = trade.get("requested_stop_loss")
        if requested_raw not in (None, ""):
            try:
                requested = float(requested_raw)
            except (TypeError, ValueError):
                return False
            tolerance = max(1e-9, abs(requested) * 1e-8)
            if abs(stop_loss - requested) > tolerance:
                return False
        # Older journal rows did not carry the trigger metadata.  New rows do;
        # once those keys exist, require the exact venue contract.
        if "stop_trigger_by" not in trade and "stop_order_type" not in trade:
            return True
        return (
            str(trade.get("stop_trigger_by") or "").lower() == "mark_price"
            and str(trade.get("stop_order_type") or "").lower() == "market"
        )

    def _trade_direction(trade: dict[str, Any]) -> tuple[str, str]:
        explicit = str(trade.get("position_side") or "").lower()
        side = str(trade.get("side") or "").lower()
        action = str(trade.get("action") or "").upper()
        if explicit in {"long", "short"}:
            return explicit, action
        if side == "sell" and action in {"OPEN", "INCREASE"}:
            return "short", action
        if side == "buy" and action in {"REDUCE", "CLOSE"}:
            return "short", action
        if side == "buy" and action in {"OPEN", "INCREASE"}:
            return "long", action
        if side == "sell" and action in {"REDUCE", "CLOSE"}:
            return "long", action
        # Legacy rows had no action; a stopped sell is a short entry and a buy
        # is a short reduction for this function's purposes.
        if side == "sell" and _stop_is_confirmed(trade):
            return "short", "OPEN"
        if side == "buy":
            return "short", "REDUCE"
        return "", action

    ordered = (
        frame.sort_values([column for column in ("date", "run_at_utc") if column in frame.columns])
        if any(column in frame.columns for column in ("date", "run_at_utc"))
        else frame
    )
    short_qty: dict[str, float] = {}
    protected: dict[str, bool] = {}
    for _, row in ordered.iterrows():
        for trade in _records(row.get("trades")) or []:
            symbol = str(trade.get("symbol") or "").upper()
            if not symbol:
                continue
            status = str(trade.get("status") or "").lower()
            if status and status != _FILLED_STATUS:
                continue
            direction, action = _trade_direction(trade)
            if direction != "short":
                continue
            qty = _qty(trade)
            if qty <= 0.0:
                continue
            current = short_qty.get(symbol, 0.0)
            if action in {"OPEN", "INCREASE"}:
                confirmed = _stop_is_confirmed(trade)
                protected[symbol] = confirmed if current <= 1e-12 else (
                    protected.get(symbol, False) and confirmed
                )
                short_qty[symbol] = current + qty
            elif action in {"REDUCE", "CLOSE"}:
                remaining = max(0.0, current - qty)
                if remaining <= 1e-12:
                    short_qty.pop(symbol, None)
                    protected.pop(symbol, None)
                else:
                    short_qty[symbol] = remaining

        snapshot = _records(row.get("positions"))
        if snapshot is None:
            continue
        snapshot_qty: dict[str, float] = {}
        for position in snapshot:
            symbol = str(position.get("symbol") or "").upper()
            side = str(position.get("side") or "").lower()
            try:
                qty = abs(float(position.get("qty") or position.get("size") or 0.0))
            except (TypeError, ValueError):
                qty = 0.0
            if symbol and side == "short":
                snapshot_qty[symbol] = qty
        for symbol in set(short_qty).difference(snapshot_qty):
            short_qty.pop(symbol, None)
            protected.pop(symbol, None)
        for symbol, qty in snapshot_qty.items():
            if short_qty.get(symbol, 0.0) <= 1e-12:
                # A short present without a journaled open is unsafe by default.
                protected[symbol] = False
                short_qty[symbol] = 1.0
            elif qty > 1e-12:
                short_qty[symbol] = qty

    return {
        symbol
        for symbol, qty in short_qty.items()
        if qty > 1e-12 and protected.get(symbol, False)
    }


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
    if pd.isna(timestamp):
        raise ValueError("capital flow timestamp must be valid")
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
    if frame["timestamp_utc"].isna().any() or not frame["amount_usdt"].map(isfinite).all():
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
    if not isfinite(amount) or amount == 0.0:
        raise ValueError("capital flow amount must be finite and non-zero")
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
