from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import pytest

from atlas20.derivatives.quotes import (
    ExecutionQuote,
    QuoteError,
    fetch_execution_quotes,
    orderbook_warnings,
    quote_warnings,
    require_fresh_quotes,
)


class _Response:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = dict(payload)
        self.ok = True
        self.status_code = 200
        self.text = ""

    def json(self) -> dict[str, Any]:
        return self._payload


class _Session:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: Mapping[str, Any], timeout: float) -> _Response:
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        return _Response(self.payload)


def _payload(*, request_time: int = 1_800_000_000_000) -> dict[str, Any]:
    return {
        "code": "00000",
        "msg": "success",
        "requestTime": request_time,
        "data": [
            {
                "symbol": "BTCUSDT",
                "ts": str(request_time - 1_000),
                "lastPrice": "100.0",
                "markPrice": "100.1",
                "bid1Price": "99.9",
                "ask1Price": "100.2",
                "bid1Size": "3.0",
                "ask1Size": "2.0",
            },
            {
                "symbol": "NEARUSDT",
                "ts": str(request_time - 2_000),
                "lastPrice": "5.0",
                "markPrice": "5.001",
                "bid1Price": "4.999",
                "ask1Price": "5.001",
                "bid1Size": "10.0",
                "ask1Size": "10.0",
            },
        ],
    }


def test_fetch_execution_quotes_uses_server_time_and_best_prices() -> None:
    session = _Session(_payload())

    quotes = fetch_execution_quotes(session, {"BTCUSDT"})

    assert session.calls[0]["params"] == {"category": "USDT-FUTURES"}
    quote = quotes["BTCUSDT"]
    assert quote.last_price == pytest.approx(100.0)
    assert quote.mark_price == pytest.approx(100.1)
    assert quote.bid_price == pytest.approx(99.9)
    assert quote.ask_price == pytest.approx(100.2)
    assert quote.bid_size == pytest.approx(3.0)
    assert quote.ask_size == pytest.approx(2.0)
    assert quote.observed_at == pd.Timestamp("2027-01-15T07:59:59Z")
    assert quote.received_at == pd.Timestamp("2027-01-15T08:00:00Z")
    assert quote.age_seconds == pytest.approx(1.0)
    assert "NEARUSDT" not in quotes


def test_quote_guard_rejects_a_stale_ticker() -> None:
    session = _Session(_payload(request_time=1_800_000_000_000))
    quotes = fetch_execution_quotes(session, {"BTCUSDT"})

    with pytest.raises(QuoteError, match="stale.*BTCUSDT"):
        require_fresh_quotes(quotes, {"BTCUSDT"}, max_age_seconds=0.5)


def test_quote_guard_consumes_a_symbol_generator_once() -> None:
    session = _Session(_payload())
    quotes = fetch_execution_quotes(session, {"BTCUSDT"})

    with pytest.raises(QuoteError, match="stale.*BTCUSDT"):
        require_fresh_quotes(
            quotes,
            (symbol for symbol in ["BTCUSDT"]),
            max_age_seconds=0.5,
        )


def test_quote_guard_warns_on_wide_spread_and_mark_disagreement() -> None:
    session = _Session(_payload())
    quotes = fetch_execution_quotes(session, {"BTCUSDT", "NEARUSDT"})

    warnings = quote_warnings(
        quotes,
        {"BTCUSDT", "NEARUSDT"},
        spread_warning_bps=20.0,
        mark_deviation_warning_bps=5.0,
    )

    assert any("BTCUSDT" in warning and "spread" in warning for warning in warnings)
    assert any("BTCUSDT" in warning and "mark" in warning for warning in warnings)
    assert not any("NEARUSDT" in warning for warning in warnings)


def test_fetch_execution_quotes_rejects_an_error_payload() -> None:
    session = _Session({"code": "40004", "msg": "bad request", "data": []})

    with pytest.raises(QuoteError, match="40004"):
        fetch_execution_quotes(session, {"BTCUSDT"})


def test_fetch_execution_quotes_rejects_a_materially_future_ticker() -> None:
    payload = _payload()
    payload["data"][0]["ts"] = str(1_800_000_061_000)

    quotes = fetch_execution_quotes(_Session(payload), {"BTCUSDT"})

    assert "BTCUSDT" not in quotes


def test_fetch_execution_quotes_rejects_non_finite_prices() -> None:
    payload = _payload()
    payload["data"][0]["lastPrice"] = "inf"
    session = _Session(payload)

    quotes = fetch_execution_quotes(session, {"BTCUSDT"})

    assert "BTCUSDT" not in quotes
    with pytest.raises(QuoteError, match="missing live quotes"):
        require_fresh_quotes(quotes, {"BTCUSDT"})


def test_orderbook_warnings_flag_orders_larger_than_visible_top_of_book() -> None:
    quotes = fetch_execution_quotes(_Session(_payload()), {"BTCUSDT", "NEARUSDT"})

    warnings = orderbook_warnings(
        quotes,
        [
            ("BTCUSDT", "buy", 500.0),
            ("NEARUSDT", "sell", 10.0),
        ],
    )

    assert any("BTCUSDT" in warning and "top-of-book" in warning for warning in warnings)
    assert not any("NEARUSDT" in warning for warning in warnings)


def test_orderbook_warnings_identifies_missing_quote_without_inventing_depth() -> None:
    quote = ExecutionQuote(
        symbol="BTCUSDT",
        last_price=100.0,
        mark_price=100.0,
        bid_price=99.9,
        ask_price=100.1,
        bid_size=1.0,
        ask_size=1.0,
        observed_at=pd.Timestamp("2027-01-15T08:00:00Z"),
        received_at=pd.Timestamp("2027-01-15T08:00:01Z"),
    )

    warnings = orderbook_warnings({quote.symbol: quote}, [("SOLUSDT", "buy", 10.0)])

    assert warnings == ["SOLUSDT: no live quote available for orderbook depth check"]
