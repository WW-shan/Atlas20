from __future__ import annotations

import pandas as pd
import pytest

from atlas20.derivatives.orderbook import OrderBookLevel, OrderBookSnapshot, walk_order_book


def _book() -> OrderBookSnapshot:
    observed = pd.Timestamp("2026-01-02T01:05:00Z")
    return OrderBookSnapshot(
        symbol="BTCUSDT",
        bids=(OrderBookLevel(99.0, 1.0), OrderBookLevel(98.0, 2.0)),
        asks=(OrderBookLevel(100.0, 1.0), OrderBookLevel(101.0, 2.0)),
        observed_at=observed,
        received_at=observed,
    )


def test_walk_order_book_sells_into_bid_depth_and_reports_unfilled_notional() -> None:
    fill = walk_order_book(_book(), "sell", 250.0)

    assert fill.filled_notional == pytest.approx(250.0)
    assert fill.filled_quantity == pytest.approx(1.0 + 151.0 / 98.0)
    assert fill.average_price == pytest.approx(250.0 / (1.0 + 151.0 / 98.0))
    assert fill.levels_consumed == 2
    assert fill.unfilled_notional == pytest.approx(0.0)
    assert fill.impact_bps == pytest.approx((99.0 - fill.average_price) / 99.0 * 10_000.0)


def test_walk_order_book_returns_residual_when_depth_is_insufficient() -> None:
    fill = walk_order_book(_book(), "buy", 500.0)

    assert fill.filled_notional == pytest.approx(302.0)
    assert fill.unfilled_notional == pytest.approx(198.0)
    assert fill.levels_consumed == 2


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.ok = True
        self.status_code = 200

    def json(self) -> dict[str, object]:
        return self._payload


class _Session:
    def __init__(self, payloads: dict[str, dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, object], timeout: float) -> _Response:
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        return _Response(self.payloads[str(params["symbol"])])


def _orderbook_payload() -> dict[str, object]:
    return {
        "code": "00000",
        "msg": "success",
        "requestTime": 1_800_000_000_500,
        "data": {
            "a": [["100.2", "2.0"], ["100.1", "1.0"]],
            "b": [["99.8", "3.0"], ["99.9", "1.5"]],
            "ts": "1800000000000",
        },
    }


def test_fetch_order_books_parses_sorted_levels_and_server_age() -> None:
    from atlas20.derivatives.orderbook import fetch_order_books

    session = _Session({"BTCUSDT": _orderbook_payload()})
    books = fetch_order_books(session, {"BTCUSDT"}, limit=50)

    assert session.calls == [
        {
            "url": "https://api.bitget.com/api/v3/market/orderbook",
            "params": {"category": "USDT-FUTURES", "symbol": "BTCUSDT", "limit": 50},
            "timeout": 30.0,
        }
    ]
    book = books["BTCUSDT"]
    assert [level.price for level in book.asks] == [100.1, 100.2]
    assert [level.price for level in book.bids] == [99.9, 99.8]
    assert book.observed_at == pd.Timestamp("2027-01-15T08:00:00Z")
    assert book.received_at == pd.Timestamp("2027-01-15T08:00:00.500Z")
    assert book.age_seconds == pytest.approx(0.5)
