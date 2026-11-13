"""Fresh execution quotes from Bitget's public ticker endpoint.

The daily signal is intentionally based on completed CoinMarketCap daily data.
Exchange quotes are used only at execution time: to size orders from a current
price, reject stale snapshots, and surface abnormal spreads or a large gap
between the last price and mark price.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import math
from typing import Any

import pandas as pd
import requests

from atlas20.derivatives.http import get_json_with_retries

BITGET_TICKERS_URL = "https://api.bitget.com/api/v3/market/tickers"
_SUCCESS_CODES = {"0", "00000"}


class QuoteError(RuntimeError):
    """Raised when a live execution quote is missing, stale, or malformed."""


def _timestamp_ms(value: Any) -> pd.Timestamp:
    return pd.to_datetime(int(value), unit="ms", utc=True)


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not (number > 0.0):
        return None
    return number


@dataclass(frozen=True)
class ExecutionQuote:
    symbol: str
    last_price: float
    mark_price: float
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    observed_at: pd.Timestamp
    received_at: pd.Timestamp

    @property
    def mid_price(self) -> float:
        return (self.bid_price + self.ask_price) / 2.0

    @property
    def spread_bps(self) -> float:
        return (self.ask_price - self.bid_price) / self.mid_price * 10_000.0

    @property
    def mark_deviation_bps(self) -> float:
        return abs(self.last_price - self.mark_price) / self.mark_price * 10_000.0

    @property
    def age_seconds(self) -> float:
        return max(0.0, float((self.received_at - self.observed_at).total_seconds()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "last_price": self.last_price,
            "mark_price": self.mark_price,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "observed_at": self.observed_at.isoformat(),
            "received_at": self.received_at.isoformat(),
            "age_seconds": self.age_seconds,
            "spread_bps": self.spread_bps,
            "mark_deviation_bps": self.mark_deviation_bps,
        }


def _quote_from_row(row: Mapping[str, Any], received_at: pd.Timestamp) -> ExecutionQuote | None:
    symbol = str(row.get("symbol", "")).strip().upper()
    if not symbol:
        return None
    last = _positive_float(row.get("lastPrice"))
    mark = _positive_float(row.get("markPrice"))
    bid = _positive_float(row.get("bid1Price"))
    ask = _positive_float(row.get("ask1Price"))
    bid_size = _positive_float(row.get("bid1Size"))
    ask_size = _positive_float(row.get("ask1Size"))
    try:
        observed = _timestamp_ms(row.get("ts"))
    except (TypeError, ValueError, OverflowError):
        return None
    # A ticker timestamp materially ahead of the signed server response is not
    # a usable execution quote; accepting it would make ``age_seconds`` clamp
    # to zero and let corrupted time data pass the freshness gate.
    if observed > received_at + pd.Timedelta(seconds=60):
        return None
    if (
        last is None
        or mark is None
        or bid is None
        or ask is None
        or bid_size is None
        or ask_size is None
        or ask < bid
    ):
        return None
    return ExecutionQuote(
        symbol=symbol,
        last_price=last,
        mark_price=mark,
        bid_price=bid,
        ask_price=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        observed_at=observed,
        received_at=received_at,
    )


def fetch_execution_quotes(
    session: requests.Session,
    symbols: Iterable[str],
    *,
    url: str = BITGET_TICKERS_URL,
    timeout_seconds: float = 30.0,
) -> dict[str, ExecutionQuote]:
    """Fetch one server-timestamped quote snapshot for the requested symbols."""

    wanted = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
    try:
        payload = get_json_with_retries(
            session,
            url,
            params={"category": "USDT-FUTURES"},
            timeout_seconds=timeout_seconds,
        )
    except (requests.RequestException, ValueError) as exc:
        raise QuoteError(f"Bitget tickers request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise QuoteError("Bitget tickers returned an unexpected payload")
    code = str(payload.get("code", ""))
    if code not in _SUCCESS_CODES:
        raise QuoteError(f"Bitget tickers error {code}: {payload.get('msg', '')}")
    try:
        received_at = _timestamp_ms(payload.get("requestTime"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise QuoteError("Bitget tickers response has no valid requestTime") from exc
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise QuoteError("Bitget tickers data is not a list")
    quotes: dict[str, ExecutionQuote] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", "")).strip().upper()
        if symbol not in wanted:
            continue
        quote = _quote_from_row(row, received_at)
        if quote is not None:
            quotes[symbol] = quote
    return quotes


def require_fresh_quotes(
    quotes: Mapping[str, ExecutionQuote],
    symbols: Iterable[str],
    *,
    max_age_seconds: float = 120.0,
) -> None:
    """Fail closed when any symbol needed for this execution lacks a fresh quote."""

    wanted = set(symbols)
    missing = sorted(wanted - set(quotes))
    if missing:
        raise QuoteError(f"missing live quotes: {', '.join(missing)}")
    stale = [
        f"{symbol} ({quotes[symbol].age_seconds:.1f}s)"
        for symbol in sorted(wanted)
        if quotes[symbol].age_seconds > float(max_age_seconds)
    ]
    if stale:
        raise QuoteError(
            f"stale live quotes (limit {float(max_age_seconds):g}s): {', '.join(stale)}"
        )


def quote_warnings(
    quotes: Mapping[str, ExecutionQuote],
    symbols: Iterable[str],
    *,
    spread_warning_bps: float = 50.0,
    mark_deviation_warning_bps: float = 100.0,
) -> list[str]:
    """Return non-blocking warnings for a fresh quote snapshot."""

    warnings: list[str] = []
    for symbol in sorted(set(symbols)):
        quote = quotes.get(symbol)
        if quote is None:
            continue
        if quote.spread_bps > float(spread_warning_bps):
            warnings.append(
                f"{symbol}: live spread {quote.spread_bps:.1f} bps exceeds "
                f"{float(spread_warning_bps):g} bps"
            )
        if quote.mark_deviation_bps > float(mark_deviation_warning_bps):
            warnings.append(
                f"{symbol}: last/mark deviation {quote.mark_deviation_bps:.1f} bps exceeds "
                f"{float(mark_deviation_warning_bps):g} bps"
            )
    return warnings


def orderbook_warnings(
    quotes: Mapping[str, ExecutionQuote],
    orders: Iterable[tuple[str, str, float]],
) -> list[str]:
    """Warn when an order is larger than the visible top-of-book liquidity.

    Bitget's ticker endpoint exposes only the best bid/ask and their sizes. A
    market order larger than that visible size can walk into deeper liquidity,
    so the execution report must make the possible slippage explicit. This is
    a warning rather than a hard block: rejecting every order larger than one
    level would make routine rebalances impossible on thin Top20 contracts.
    """

    warnings: list[str] = []
    for raw_symbol, raw_side, raw_notional in orders:
        symbol = str(raw_symbol).strip().upper()
        side = str(raw_side).strip().lower()
        try:
            notional = float(raw_notional)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(notional) or notional <= 0.0:
            continue
        quote = quotes.get(symbol)
        if quote is None:
            warnings.append(f"{symbol}: no live quote available for orderbook depth check")
            continue
        if side == "buy":
            available = quote.ask_size * quote.ask_price
        elif side == "sell":
            available = quote.bid_size * quote.bid_price
        else:
            continue
        if notional > available:
            warnings.append(
                f"{symbol}: {side} order {notional:.2f} USDT exceeds visible "
                f"top-of-book {available:.2f} USDT; slippage possible"
            )
    return warnings


__all__ = [
    "BITGET_TICKERS_URL",
    "ExecutionQuote",
    "QuoteError",
    "fetch_execution_quotes",
    "orderbook_warnings",
    "quote_warnings",
    "require_fresh_quotes",
]
