"""Parse Bitget public trade/depth downloads and simulate passive fills.

The simulator is research-only. It uses actual aggressor-side trade prints to
test whether a hypothetical limit order could have filled, but it cannot prove
queue position, hidden liquidity, cancellation timing or a real venue fill.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import math
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd


class TradeTapeError(RuntimeError):
    """Raised when public trade or depth evidence is malformed."""


@dataclass(frozen=True)
class TradePrint:
    trade_id: str
    timestamp: pd.Timestamp
    price: float
    side: str
    quote_notional: float
    base_size: float


@dataclass(frozen=True)
class TopOfBook:
    timestamp: pd.Timestamp
    ask_price: float
    bid_price: float
    ask_volume: float
    bid_volume: float

    @property
    def mid_price(self) -> float:
        return (self.ask_price + self.bid_price) / 2.0


@dataclass(frozen=True)
class MakerOrderOutcome:
    side: str
    reference_price: float
    limit_price: float
    trigger_price: float
    requested_notional: float
    maker_filled_notional: float
    taker_filled_notional: float
    maker_fill_ratio: float
    vwap: float | None
    effective_cost_bps: float | None
    improvement_bps: float | None
    guard_triggered: bool
    timed_out: bool
    status: str
    last_trade_time: pd.Timestamp | None


def _timestamp(value: object) -> pd.Timestamp:
    number = int(float(str(value)))
    unit = "s" if number < 10_000_000_000 else "ms"
    return pd.to_datetime(number, unit=unit, utc=True)


def _positive(value: object, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise TradeTapeError(f"{field} must be numeric") from None
    if not math.isfinite(number) or number <= 0.0:
        raise TradeTapeError(f"{field} must be finite and positive")
    return number


def parse_trade_csv(data: bytes, *, _depth: int = 0) -> tuple[TradePrint, ...]:
    """Parse one Bitget transaction-history CSV or zip-wrapped CSV blob."""
    if _depth > 2:
        raise TradeTapeError("trade CSV nesting exceeds 2 levels")
    if zipfile.is_zipfile(io.BytesIO(data)):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                csv_names = sorted(name for name in archive.namelist() if name.lower().endswith(".csv"))
                if not csv_names:
                    raise TradeTapeError("trade zip has no CSV entry")
                return parse_trade_csv(archive.read(csv_names[0]), _depth=_depth + 1)
        except zipfile.BadZipFile as exc:
            raise TradeTapeError("trade payload is not a valid zip") from exc
    try:
        frame = pd.read_csv(io.BytesIO(data))
    except Exception as exc:
        raise TradeTapeError("trade CSV is unreadable") from exc
    required = {"trade_id", "timestamp", "price", "side", "volume(quote)", "size(base)"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise TradeTapeError(f"trade CSV missing columns: {missing}")
    rows: dict[str, TradePrint] = {}
    previous_timestamp: pd.Timestamp | None = None
    for record in frame.to_dict("records"):
        trade_id = str(record["trade_id"]).strip()
        if not trade_id:
            raise TradeTapeError("trade_id is empty")
        side = str(record["side"]).strip().lower()
        if side not in {"buy", "sell"}:
            raise TradeTapeError(f"unsupported trade side {side!r}")
        timestamp = _timestamp(record["timestamp"])
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise TradeTapeError("trade timestamps are not nondecreasing")
        previous_timestamp = timestamp
        trade = TradePrint(
            trade_id=trade_id,
            timestamp=timestamp,
            price=_positive(record["price"], field="price"),
            side=side,
            quote_notional=_positive(record["volume(quote)"], field="quote notional"),
            base_size=_positive(record["size(base)"], field="base size"),
        )
        previous = rows.get(trade_id)
        if previous is not None:
            if previous != trade:
                raise TradeTapeError(f"conflicting duplicate trade_id {trade_id}")
            raise TradeTapeError(f"duplicate trade_id {trade_id}")
        rows[trade_id] = trade
    if not rows:
        raise TradeTapeError("trade CSV has no rows")
    return tuple(sorted(rows.values(), key=lambda row: (row.timestamp, row.trade_id)))


def _cell_value(cell: ET.Element) -> str:
    inline = cell.find(".//{*}t")
    if inline is not None and inline.text is not None:
        return inline.text
    value = cell.find("{*}v")
    return value.text if value is not None and value.text is not None else ""


def parse_depth_xlsx(data: bytes, *, _depth: int = 0) -> tuple[TopOfBook, ...]:
    """Parse Bitget's small Level1 depth workbook without third-party XLSX code."""
    if _depth > 4:
        raise TradeTapeError("depth xlsx nesting exceeds 4 levels")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            sheet_names = [
                name
                for name in names
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            ]
            if not sheet_names:
                nested = sorted(name for name in names if name.lower().endswith(".xlsx"))
                if not nested:
                    raise TradeTapeError("depth xlsx has no worksheet XML")
                return parse_depth_xlsx(archive.read(nested[0]), _depth=_depth + 1)
            root = ET.fromstring(archive.read(sorted(sheet_names)[0]))
    except zipfile.BadZipFile as exc:
        raise TradeTapeError("depth payload is not a valid xlsx zip") from exc
    except ET.ParseError as exc:
        raise TradeTapeError("depth worksheet XML is malformed") from exc

    rows = root.findall(".//{*}sheetData/{*}row")
    if not rows:
        raise TradeTapeError("depth worksheet has no rows")
    header = [_cell_value(cell).strip() for cell in rows[0].findall("{*}c")]
    required = {"timestamp", "ask_price", "bid_price", "ask_volume", "bid_volume"}
    missing = sorted(required.difference(header))
    if missing:
        raise TradeTapeError(f"depth worksheet missing columns: {missing}")
    by_timestamp: dict[pd.Timestamp, TopOfBook] = {}
    for row in rows[1:]:
        values = [_cell_value(cell).strip() for cell in row.findall("{*}c")]
        if len(values) < len(header):
            continue
        record = dict(zip(header, values, strict=False))
        try:
            book = TopOfBook(
                timestamp=_timestamp(record["timestamp"]),
                ask_price=_positive(record["ask_price"], field="ask_price"),
                bid_price=_positive(record["bid_price"], field="bid_price"),
                ask_volume=_positive(record["ask_volume"], field="ask_volume"),
                bid_volume=_positive(record["bid_volume"], field="bid_volume"),
            )
        except TradeTapeError:
            continue
        if book.bid_price >= book.ask_price:
            continue
        by_timestamp[book.timestamp] = book
    if not by_timestamp:
        raise TradeTapeError("depth worksheet has no valid top-of-book rows")
    return tuple(by_timestamp[key] for key in sorted(by_timestamp))


def simulate_maker_order(
    trades: tuple[TradePrint, ...],
    *,
    side: str,
    reference_price: float,
    order_notional: float,
    entry_time: pd.Timestamp,
    timeout_hours: float = 2.0,
    offset_bps: float = 5.0,
    through_bps: float = 1.0,
    guard_bps: float = 30.0,
    maker_fee_bps: float = 2.0,
    taker_fee_bps: float = 20.0,
    fill_haircut: float = 1.0,
) -> MakerOrderOutcome:
    """Simulate one passive order against public aggressor-side trades."""
    normalized_side = str(side).strip().lower()
    if normalized_side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")
    reference = _positive(reference_price, field="reference_price")
    requested = _positive(order_notional, field="order_notional")
    if timeout_hours <= 0.0 or offset_bps < 0.0 or through_bps < 0.0 or guard_bps <= 0.0:
        raise ValueError("invalid maker simulation parameters")
    if not 0.0 < fill_haircut <= 1.0:
        raise ValueError("fill_haircut must be in (0, 1]")
    start = pd.Timestamp(entry_time)
    end = start + pd.Timedelta(hours=float(timeout_hours))
    active = [trade for trade in trades if start <= trade.timestamp <= end]
    limit = reference * (1.0 - offset_bps / 10_000.0 if normalized_side == "buy" else 1.0 + offset_bps / 10_000.0)
    trigger = limit * (1.0 - through_bps / 10_000.0 if normalized_side == "buy" else 1.0 + through_bps / 10_000.0)

    remaining = requested
    maker_filled = 0.0
    taker_filled = 0.0
    maker_quantity = 0.0
    taker_quantity = 0.0
    guard = False
    last_trade_time = None
    last_trade_price = None
    status = "timeout"
    for trade in active:
        last_trade_time = trade.timestamp
        last_trade_price = trade.price
        direction_matches = trade.side == ("sell" if normalized_side == "buy" else "buy")
        strict_price = trade.price <= trigger if normalized_side == "buy" else trade.price >= trigger
        if remaining > 0.0 and direction_matches and strict_price:
            fill = min(remaining, trade.quote_notional * fill_haircut)
            maker_filled += fill
            maker_quantity += fill / limit
            remaining -= fill
        if remaining <= 1e-12:
            remaining = 0.0
            status = "filled"
            break
        adverse_bps = (
            (trade.price / reference - 1.0) * 10_000.0
            if normalized_side == "buy"
            else (1.0 - trade.price / reference) * 10_000.0
        )
        if adverse_bps >= guard_bps:
            taker_filled = remaining
            taker_quantity += remaining / trade.price
            remaining = 0.0
            guard = True
            status = "guard"
            break

    if remaining > 0.0 and last_trade_price is not None:
        taker_filled = remaining
        taker_quantity += remaining / last_trade_price
        remaining = 0.0
        status = "timeout"
    elif remaining > 0.0:
        status = "no_trades"

    total_filled = maker_filled + taker_filled
    total_quantity = maker_quantity + taker_quantity
    vwap = None
    effective_cost = None
    improvement = None
    if total_filled > 0.0 and total_quantity > 0.0:
        total_cash = maker_filled + taker_filled
        vwap = total_cash / total_quantity
        fee_notional = maker_filled * maker_fee_bps / 10_000.0 + taker_filled * taker_fee_bps / 10_000.0
        fee_bps = fee_notional / total_filled * 10_000.0
        effective_cost = (
            (vwap - reference) / reference * 10_000.0 + fee_bps
            if normalized_side == "buy"
            else (reference - vwap) / reference * 10_000.0 + fee_bps
        )
        improvement = 20.0 - effective_cost
    return MakerOrderOutcome(
        side=normalized_side,
        reference_price=reference,
        limit_price=limit,
        trigger_price=trigger,
        requested_notional=requested,
        maker_filled_notional=maker_filled,
        taker_filled_notional=taker_filled,
        maker_fill_ratio=maker_filled / requested,
        vwap=vwap,
        effective_cost_bps=effective_cost,
        improvement_bps=improvement,
        guard_triggered=guard,
        timed_out=status == "timeout",
        status=status,
        last_trade_time=last_trade_time,
    )


__all__ = [
    "MakerOrderOutcome",
    "TopOfBook",
    "TradePrint",
    "TradeTapeError",
    "parse_depth_xlsx",
    "parse_trade_csv",
    "simulate_maker_order",
]
