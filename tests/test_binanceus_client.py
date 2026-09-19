"""Tests for the Binance.US public daily-history client."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from atlas20.config import BinanceUSConfig
from atlas20.data.binanceus import BinanceUSClient


def _kline(day_ms: int, close: float, volume_quote: float) -> list[object]:
    return [day_ms, "0", "0", "0", str(close), "0", day_ms + 86_399_999, str(volume_quote), 0, "0", "0", "0"]


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)[:200]

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class _FakeSession:
    """Returns pre-seeded pages keyed by endTime (None first)."""

    def __init__(self, pages: dict[int | None, list[list[object]]]) -> None:
        self.pages = pages
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del url, timeout
        self.calls.append(dict(params))
        end = params.get("endTime")
        key = int(end) if end is not None else None
        return _FakeResponse(self.pages.get(key, []))


def _config(page_limit: int = 1000) -> BinanceUSConfig:
    return BinanceUSConfig(page_limit=page_limit)


def test_fetch_daily_history_paginates_until_short_page(tmp_path: Path) -> None:
    day = 86_400_000
    page_two_end = 1_600_000_000_000
    first = [_kline(page_two_end + i * day, 100.0 + i, 10.0) for i in range(2)]
    second = [_kline(page_two_end - 2 * day, 90.0, 5.0)]
    session = _FakeSession({None: first, page_two_end - 1: second})

    client = BinanceUSClient(_config(page_limit=2), tmp_path)
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_daily_history("BTC")

    assert frame is not None
    assert list(frame.columns) == ["date", "close", "volume_usd"]
    assert len(frame) == 3
    assert frame["date"].is_monotonic_increasing
    assert frame["close"].iloc[-1] == pytest.approx(101.0)
    assert len(session.calls) == 2
    assert session.calls[1]["endTime"] == page_two_end - 1


def test_fetch_daily_history_returns_none_when_symbol_absent(tmp_path: Path) -> None:
    session = _FakeSession({None: []})
    client = BinanceUSClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    assert client.fetch_daily_history("NOTACOIN") is None


def test_fetch_daily_history_uses_cache_without_network(tmp_path: Path) -> None:
    session = _FakeSession({None: [_kline(1_700_000_000_000, 42.0, 7.0)]})
    client = BinanceUSClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    first = client.fetch_daily_history("BTC")
    calls_after_first = len(session.calls)
    second = client.fetch_daily_history("BTC")

    assert first is not None and second is not None
    assert calls_after_first == 1
    assert len(session.calls) == calls_after_first, "second call must be served from cache"
    assert second["close"].iloc[0] == pytest.approx(42.0)


def test_fetch_daily_history_force_refetches(tmp_path: Path) -> None:
    session = _FakeSession({None: [_kline(1_700_000_000_000, 42.0, 7.0)]})
    client = BinanceUSClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    client.fetch_daily_history("BTC")
    client.fetch_daily_history("BTC", force=True)

    assert len(session.calls) == 2


def test_fetch_daily_history_prefers_usdt_then_usd(tmp_path: Path) -> None:
    session = _FakeSession({None: [_kline(1_700_000_000_000, 42.0, 7.0)]})
    client = BinanceUSClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    client.fetch_daily_history("BTC")

    assert session.calls[0]["symbol"] == "BTCUSDT"


def test_fetch_daily_history_falls_back_to_usd_pair(tmp_path: Path) -> None:
    class _PairSession(_FakeSession):
        def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
            del url, timeout
            self.calls.append(dict(params))
            if str(params["symbol"]).endswith("USDT"):
                return _FakeResponse({"code": -1121, "msg": "Invalid symbol."}, status_code=400)
            return _FakeResponse([_kline(1_700_000_000_000, 42.0, 7.0)])

    session = _PairSession({})
    client = BinanceUSClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_daily_history("BTC")

    assert frame is not None
    assert [c["symbol"] for c in session.calls] == ["BTCUSDT", "BTCUSD"]
