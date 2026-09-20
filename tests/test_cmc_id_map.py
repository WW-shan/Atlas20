"""CMC symbol/id mapping and universe-data integration."""

from __future__ import annotations

from pathlib import Path


from atlas20.data.coinmarketcap import CoinMarketCapClient
from atlas20.config import CoinMarketCapConfig


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"status {self.status_code}")


class _FakeSession:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.calls = 0

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del url, params, timeout
        self.calls += 1
        return _FakeResponse(self._payload)


def _listing_payload() -> dict:
    return {
        "data": {
            "cryptoCurrencyList": [
                {"id": 1, "symbol": "BTC", "name": "Bitcoin"},
                {"id": 1027, "symbol": "ETH", "name": "Ethereum"},
                {"id": 5426, "symbol": "SOL", "name": "Solana"},
            ]
        }
    }


def test_fetch_id_map_builds_symbol_lookup(tmp_path: Path) -> None:
    client = CoinMarketCapClient(CoinMarketCapConfig(), tmp_path)
    client.session = _FakeSession(_listing_payload())  # type: ignore[assignment]

    mapping = client.fetch_id_map(force=True)

    assert mapping["BTC"] == 1
    assert mapping["ETH"] == 1027
    assert mapping["SOL"] == 5426


def test_fetch_id_map_is_cached(tmp_path: Path) -> None:
    session = _FakeSession(_listing_payload())
    client = CoinMarketCapClient(CoinMarketCapConfig(), tmp_path)
    client.session = session  # type: ignore[assignment]

    client.fetch_id_map(force=True)
    calls = session.calls
    client.fetch_id_map()

    assert session.calls == calls, "second lookup must be served from cache"


def test_fetch_id_map_force_refetches(tmp_path: Path) -> None:
    session = _FakeSession(_listing_payload())
    client = CoinMarketCapClient(CoinMarketCapConfig(), tmp_path)
    client.session = session  # type: ignore[assignment]

    client.fetch_id_map(force=True)
    client.fetch_id_map(force=True)

    assert session.calls == 2


def test_fetch_id_map_handles_multiple_pages(tmp_path: Path) -> None:
    class _PagedSession:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
            del url, timeout
            self.calls += 1
            start = int(params.get("start", 1))
            if start == 1:
                return _FakeResponse(
                    {"data": {"cryptoCurrencyList": [{"id": 1, "symbol": "BTC", "name": "Bitcoin"}]}}
                )
            return _FakeResponse({"data": {"cryptoCurrencyList": []}})

    client = CoinMarketCapClient(CoinMarketCapConfig(), tmp_path)
    client.session = _PagedSession()  # type: ignore[assignment]

    mapping = client.fetch_id_map(force=True)

    assert mapping["BTC"] == 1
    assert client.session.calls >= 1  # type: ignore[attr-defined]
