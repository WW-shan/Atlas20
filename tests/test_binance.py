"""Binance exchange-candle client.

``api.binance.com`` answers 451 from this host, so the venue is reached through
Binance's official public data mirror ``data-api.binance.vision``. It is an
exchange order book like Gate.io, which is what makes it useful as an
independent vote against CoinMarketCap: when two separate venues agree with
each other and CMC does not, the venues are the evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from atlas20.config import BinanceConfig
from atlas20.data.binance import BinanceClient


def _kline(day: str, close: float, *, volume_usd: float = 1_000_000.0) -> list:
    opened = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
    return [opened, "0", "0", "0", str(close), "1", opened + 86_399_999, str(volume_usd), 1, "0", "0", "0"]


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}", response=self)  # type: ignore[arg-type]


def _config(**overrides) -> BinanceConfig:
    values = {"rate_limit_seconds": 0.0, "retry_backoff_seconds": 0.0}
    values.update(overrides)
    return BinanceConfig(**values)


def test_fetch_daily_candles_returns_close_and_dollar_volume(tmp_path: Path) -> None:
    class _Session:
        def get(self, url, params, timeout):
            del url, timeout
            assert params["symbol"] == "BTCUSDT"
            return _FakeResponse([_kline("2026-09-19", 80_000.0), _kline("2026-09-20", 81_000.0, volume_usd=5_000.0)])

    client = BinanceClient(_config(min_daily_dollar_volume=1_000.0), tmp_path)
    client.session = _Session()  # type: ignore[assignment]

    frame = client.fetch_daily_candles("BTC", start="2026-09-01", end="2026-09-21")

    assert list(frame.columns) == ["date", "binance_price", "binance_volume_usd"]
    assert len(frame) == 2
    assert frame["binance_price"].iloc[-1] == pytest.approx(81_000.0)
    assert frame["binance_volume_usd"].iloc[-1] == pytest.approx(5_000.0)
    assert frame["date"].is_monotonic_increasing


def test_thin_days_are_dropped_rather_than_reported_as_disagreement(tmp_path: Path) -> None:
    """A $2/day "close" is a stale print, not evidence about today's price.

    Binance.US quoted ENS at $1.74/day and FLOW at $2.71/day; those closes sat
    double digits away from CoinMarketCap and read as a data error in the
    primary feed. A day below the floor must simply not be offered as a vote.
    """

    class _Session:
        def get(self, url, params, timeout):
            del url, params, timeout
            return _FakeResponse(
                [
                    _kline("2026-09-18", 80_000.0),
                    _kline("2026-09-19", 79_000.0, volume_usd=1.74),
                    _kline("2026-09-20", 81_000.0, volume_usd=2.71),
                ]
            )

    client = BinanceClient(_config(min_daily_dollar_volume=100_000.0), tmp_path)
    client.session = _Session()  # type: ignore[assignment]

    frame = client.fetch_daily_candles("ENS", start="2026-09-01", end="2026-09-21")

    assert [day.date().isoformat() for day in frame["date"]] == ["2026-09-18"]


def test_resolve_pair_uses_quote_currency_suffix(tmp_path: Path) -> None:
    client = BinanceClient(_config(), tmp_path)

    assert client.resolve_pair("eth") == "ETHUSDT"


def test_default_endpoint_is_the_public_data_mirror(tmp_path: Path) -> None:
    """api.binance.com is geo-blocked here and api.binance.us is a thin book."""
    config = BinanceConfig()
    client = BinanceClient(config, tmp_path)

    assert config.base_url == "https://data-api.binance.vision/api/v3"
    assert client.base_url == "https://data-api.binance.vision/api/v3"


def test_unlisted_symbol_returns_an_empty_frame_rather_than_raising(tmp_path: Path) -> None:
    """HT and CEL answer 'Invalid symbol'.

    A venue that does not carry a name must read as "no source available" so
    the adjudicator can fall through to another provider; raising would abort
    the whole refresh for one delisted ticker.
    """

    class _Session:
        def get(self, url, params, timeout):
            del url, params, timeout
            return _FakeResponse({"code": -1121, "msg": "Invalid symbol."}, status_code=400)

    client = BinanceClient(_config(), tmp_path)
    client.session = _Session()  # type: ignore[assignment]

    frame = client.fetch_daily_candles("HT", start="2026-09-01", end="2026-09-21")

    assert frame.empty
    assert list(frame.columns) == ["date", "binance_price", "binance_volume_usd"]


def test_cached_window_is_not_re_requested(tmp_path: Path) -> None:
    calls: list[dict] = []

    class _Session:
        def get(self, url, params, timeout):
            del url, timeout
            calls.append(dict(params))
            return _FakeResponse([_kline("2026-09-20", 81_000.0)])

    client = BinanceClient(_config(), tmp_path)
    client.session = _Session()  # type: ignore[assignment]

    first = client.fetch_daily_candles("BTC", start="2026-09-01", end="2026-09-21")
    second = client.fetch_daily_candles("BTC", start="2026-09-01", end="2026-09-21")

    assert len(calls) == 1, "a cached window must not be re-downloaded"
    assert first.equals(second)


def test_long_range_is_walked_in_pages(tmp_path: Path) -> None:
    """The endpoint caps a page at 1000 rows, so a 5-year cross-check window
    needs several requests rather than one silently-truncated one."""
    day = 86_400_000

    class _Session:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def get(self, url, params, timeout):
            del url, timeout
            self.calls.append(dict(params))
            first = params["startTime"]
            rows = [
                [
                    first + index * day,
                    "0",
                    "0",
                    "0",
                    "1",
                    "1",
                    first + index * day + 86_399_999,
                    "1000000",
                    1,
                    "0",
                    "0",
                    "0",
                ]
                for index in range(1000)
            ]
            if len(self.calls) > 1:
                rows = rows[:1]
            return _FakeResponse(rows)

    session = _Session()
    client = BinanceClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_daily_candles("BTC", start="2021-01-01", end="2026-09-21")

    assert len(session.calls) > 1, "a multi-year window must be paged"
    assert not frame.empty
    assert frame["date"].is_unique


def test_corrupt_cache_falls_back_to_the_network(tmp_path: Path) -> None:
    directory = tmp_path / "binance" / "candles"
    directory.mkdir(parents=True)
    (directory / "BTCUSDT_2021-01-01_2026-09-21.json").write_text("{not json", encoding="utf-8")

    class _Session:
        def get(self, url, params, timeout):
            del url, params, timeout
            return _FakeResponse([_kline("2026-09-20", 81_000.0)])

    client = BinanceClient(_config(), tmp_path)
    client.session = _Session()  # type: ignore[assignment]

    frame = client.fetch_daily_candles("BTC", start="2021-01-01", end="2026-09-21")

    assert not frame.empty
