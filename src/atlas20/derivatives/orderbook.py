"""Typed public order-book snapshots and liquidity measurements.

This module is read-only market-data support for execution research. It does
not place orders or depend on private account state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

import pandas as pd
import requests

BITGET_ORDERBOOK_URL = "https://api.bitget.com/api/v3/market/orderbook"
_SUCCESS_CODES = {"0", "00000"}


class OrderBookError(RuntimeError):
    """Raised when public order-book data is missing, stale, or malformed."""


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    size: float

    @property
    def notional(self) -> float:
        return self.price * self.size


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    observed_at: pd.Timestamp
    received_at: pd.Timestamp

    @property
    def age_seconds(self) -> float:
        return max(0.0, float((self.received_at - self.observed_at).total_seconds()))


@dataclass(frozen=True)
class DepthFill:
    side: str
    requested_notional: float
    filled_notional: float
    filled_quantity: float
    average_price: float | None
    best_price: float | None
    levels_consumed: int
    unfilled_notional: float
    impact_bps: float | None


def walk_order_book(
    book: OrderBookSnapshot,
    side: str,
    notional: float,
) -> DepthFill:
    """Walk visible levels for a marketable buy or sell of ``notional``."""
    normalized_side = str(side).strip().lower()
    if normalized_side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")
    target = float(notional)
    if target <= 0.0:
        raise ValueError("notional must be positive")

    levels: Sequence[OrderBookLevel] = book.asks if normalized_side == "buy" else book.bids
    remaining = target
    quantity = 0.0
    filled = 0.0
    consumed = 0
    best_price = levels[0].price if levels else None
    for level in levels:
        level_cash = min(remaining, level.notional)
        if level_cash <= 0.0:
            break
        level_quantity = level_cash / level.price
        quantity += level_quantity
        filled += level_cash
        remaining -= level_cash
        consumed += 1
        if remaining <= 1e-12:
            remaining = 0.0
            break

    average = filled / quantity if quantity > 0.0 else None
    impact = None
    if average is not None and best_price is not None and best_price > 0.0:
        sign = 1.0 if normalized_side == "buy" else -1.0
        impact = sign * (average - best_price) / best_price * 10_000.0
    return DepthFill(
        side=normalized_side,
        requested_notional=target,
        filled_notional=filled,
        filled_quantity=quantity,
        average_price=average,
        best_price=best_price,
        levels_consumed=consumed,
        unfilled_notional=max(0.0, remaining),
        impact_bps=impact,
    )


def _timestamp_ms(value: Any) -> pd.Timestamp:
    return pd.to_datetime(int(value), unit="ms", utc=True)


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _levels(rows: Any, *, reverse: bool) -> tuple[OrderBookLevel, ...]:
    if not isinstance(rows, list):
        raise OrderBookError("Bitget orderbook levels are not a list")
    parsed: list[OrderBookLevel] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        price = _positive_float(row[0])
        size = _positive_float(row[1])
        if price is None or size is None:
            continue
        parsed.append(OrderBookLevel(price=price, size=size))
    parsed.sort(key=lambda level: level.price, reverse=reverse)
    return tuple(parsed)


def fetch_order_books(
    session: requests.Session,
    symbols: Iterable[str],
    *,
    limit: int = 50,
    timeout_seconds: float = 30.0,
    url: str = BITGET_ORDERBOOK_URL,
) -> dict[str, OrderBookSnapshot]:
    """Fetch one public order-book snapshot per requested symbol."""
    if limit < 1:
        raise ValueError("limit must be positive")
    wanted = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    books: dict[str, OrderBookSnapshot] = {}
    for symbol in wanted:
        response = session.get(
            url,
            params={"category": "USDT-FUTURES", "symbol": symbol, "limit": int(limit)},
            timeout=timeout_seconds,
        )
        if not bool(getattr(response, "ok", False)):
            raise OrderBookError(
                f"Bitget orderbook HTTP {getattr(response, 'status_code', 'unknown')} for {symbol}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise OrderBookError(f"Bitget orderbook returned non-JSON payload for {symbol}") from exc
        if not isinstance(payload, Mapping):
            raise OrderBookError(f"Bitget orderbook returned an unexpected payload for {symbol}")
        code = str(payload.get("code", ""))
        if code not in _SUCCESS_CODES:
            raise OrderBookError(
                f"Bitget orderbook error {code} for {symbol}: {payload.get('msg', '')}"
            )
        try:
            received_at = _timestamp_ms(payload.get("requestTime"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise OrderBookError(f"Bitget orderbook has no valid requestTime for {symbol}") from exc
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise OrderBookError(f"Bitget orderbook data is not an object for {symbol}")
        try:
            observed_at = _timestamp_ms(data.get("ts"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise OrderBookError(f"Bitget orderbook has no valid ts for {symbol}") from exc
        bids = _levels(data.get("b"), reverse=True)
        asks = _levels(data.get("a"), reverse=False)
        if not bids or not asks or bids[0].price >= asks[0].price:
            continue
        books[symbol] = OrderBookSnapshot(
            symbol=symbol,
            bids=bids,
            asks=asks,
            observed_at=observed_at,
            received_at=received_at,
        )
    return books


def require_fresh_order_books(
    books: Mapping[str, OrderBookSnapshot],
    symbols: Iterable[str],
    *,
    max_age_seconds: float = 120.0,
) -> None:
    """Fail closed when any requested public order book is absent or stale."""
    wanted = set(symbols)
    missing = sorted(wanted - set(books))
    if missing:
        raise OrderBookError(f"missing live order books: {', '.join(missing)}")
    stale = [
        f"{symbol} ({books[symbol].age_seconds:.1f}s)"
        for symbol in sorted(wanted)
        if books[symbol].age_seconds > float(max_age_seconds)
    ]
    if stale:
        raise OrderBookError(
            f"stale live order books (limit {float(max_age_seconds):g}s): {', '.join(stale)}"
        )


__all__ = [
    "BITGET_ORDERBOOK_URL",
    "DepthFill",
    "OrderBookError",
    "OrderBookLevel",
    "OrderBookSnapshot",
    "fetch_order_books",
    "require_fresh_order_books",
    "walk_order_book",
]
