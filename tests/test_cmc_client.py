"""CoinMarketCap historical market-cap client.

The repo previously derived long-history market caps by scaling price against
a current snapshot. That proxy does not track real supply changes, so the
Top-N universe it produced was not the real historical Top-N. CMC's public
data-api exposes true daily market cap and circulating supply.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from atlas20.config import CoinMarketCapConfig
from atlas20.data.coinmarketcap import CoinMarketCapClient


def _quote(day: str, close: float, supply: float) -> dict:
    return {
        "timeOpen": f"{day}T00:00:00.000Z",
        "timeClose": f"{day}T23:59:59.999Z",
        "quote": {
            "name": "2781",
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1_000_000.0,
            "marketCap": close * supply,
            "circulatingSupply": supply,
        },
    }


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class _FakeSession:
    """Serves pages keyed by how far back ``timeEnd`` has walked."""

    def __init__(self, pages: list[list[dict]]) -> None:
        self.pages = pages
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del url, timeout
        self.calls.append(dict(params))
        index = len(self.calls) - 1
        if index < len(self.pages):
            return _FakeResponse({"data": {"quotes": self.pages[index]}})
        return _FakeResponse({"data": {"quotes": []}})

    def page_for(self, start: int, end: int) -> list[dict]:
        """Return the page whose dates fall inside the requested window."""
        return [
            row
            for page in self.pages
            for row in page
            if start <= int(pd.Timestamp(row["timeOpen"]).timestamp()) <= end
        ]


def _config(page_size: int = 400, request_interval_seconds: float = 0.0) -> CoinMarketCapConfig:
    return CoinMarketCapConfig(page_size=page_size, request_interval_seconds=request_interval_seconds)


def test_fetch_history_returns_market_cap_and_supply(tmp_path: Path) -> None:
    page = [_quote("2024-01-01", 100.0, 1000.0), _quote("2024-01-02", 110.0, 1010.0)]
    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = _FakeSession([page])  # type: ignore[assignment]

    frame = client.fetch_history(1, start="2024-01-01", end="2024-01-03")

    assert list(frame.columns) == ["date", "close", "volume_usd", "market_cap", "circulating_supply"]
    assert len(frame) == 2
    assert frame["market_cap"].iloc[1] == pytest.approx(110.0 * 1010.0)
    assert frame["circulating_supply"].iloc[1] == pytest.approx(1010.0)


def test_fetch_history_paginates_across_full_range(tmp_path: Path) -> None:
    first = [_quote(f"2024-01-{d:02d}", 100.0 + d, 1000.0) for d in range(1, 11)]
    second = [_quote(f"2024-02-{d:02d}", 200.0 + d, 1000.0) for d in range(1, 6)]

    class _WindowSession(_FakeSession):
        """Mimics the server: returns the most recent rows ending at timeEnd."""

        def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
            del url, timeout
            self.calls.append(dict(params))
            start = int(params["timeStart"])
            end = int(params["timeEnd"])
            rows = self.page_for(start, end)
            rows = [r for r in rows if int(pd.Timestamp(r["timeOpen"]).timestamp()) <= end]
            if not rows:
                return _FakeResponse({"data": {"quotes": []}})
            return _FakeResponse({"data": {"quotes": rows[-self.page_size :]}})

    session = _WindowSession([first, second])
    session.page_size = 10  # type: ignore[attr-defined]
    client = CoinMarketCapClient(_config(page_size=10), tmp_path)
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_history(1, start="2024-01-01", end="2024-02-05")

    assert len(frame) == 15
    assert frame["date"].is_monotonic_increasing
    assert len(session.calls) >= 2


def test_fetch_history_caches_to_disk(tmp_path: Path) -> None:
    page = [_quote("2024-01-01", 100.0, 1000.0)]
    session = _FakeSession([page])
    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    client.fetch_history(1, start="2024-01-01", end="2024-01-05")
    calls = len(session.calls)
    client.fetch_history(1, start="2024-01-01", end="2024-01-05")

    assert len(session.calls) == calls, "second call must be served from cache"


def test_fetch_history_force_bypasses_cache(tmp_path: Path) -> None:
    page = [_quote("2024-01-01", 100.0, 1000.0)]
    session = _FakeSession([page])
    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    client.fetch_history(1, start="2024-01-01", end="2024-01-05")
    client.fetch_history(1, start="2024-01-01", end="2024-01-05", force=True)

    assert len(session.calls) == 2


def test_fetch_history_empty_returns_empty_frame(tmp_path: Path) -> None:
    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = _FakeSession([[]])  # type: ignore[assignment]

    frame = client.fetch_history(999999, start="2024-01-01", end="2024-01-03")

    assert frame.empty
    assert list(frame.columns) == ["date", "close", "volume_usd", "market_cap", "circulating_supply"]


def test_fetch_history_persists_rows_in_ascending_order(tmp_path: Path) -> None:
    """Paging walks backwards; the cache must still be chronological."""
    newer = [_quote(f"2024-02-{d:02d}", 200.0, 1000.0) for d in range(1, 4)]
    older = [_quote(f"2024-01-{d:02d}", 100.0, 1000.0) for d in range(1, 4)]

    class _BackwardsSession(_FakeSession):
        def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
            del url, timeout
            self.calls.append(dict(params))
            return _FakeResponse({"data": {"quotes": newer if len(self.calls) == 1 else older}})

    session = _BackwardsSession([newer, older])
    client = CoinMarketCapClient(_config(page_size=3), tmp_path)
    client.session = session  # type: ignore[assignment]

    client.fetch_history(1, start="2024-01-01", end="2024-02-03")

    cached = json.loads(
        (tmp_path / "coinmarketcap" / "history" / "1_1704067200_1706918400.json").read_text()
    )
    dates = [row["timeOpen"][:10] for row in cached]
    assert dates == sorted(dates), "cached rows must be chronological"
