"""Third-provider resolution and cache behavior."""

from __future__ import annotations

import json
from pathlib import Path

import requests

from atlas20.config import CoinPaprikaConfig
from atlas20.data.coinpaprika import CoinPaprikaClient


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers: dict[str, str] = {}
        self.text = json.dumps(payload)

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise requests.HTTPError(f"status {self.status_code}")


class _FakeSession:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del timeout
        self.calls.append((url, dict(params)))
        payload = self.responses.pop(0)
        return _FakeResponse(payload)


def _client(tmp_path: Path) -> CoinPaprikaClient:
    return CoinPaprikaClient(
        CoinPaprikaConfig(rate_limit_seconds=0.0, max_retries=1),
        tmp_path,
    )


def test_resolve_coin_id_prefers_rank_over_ambiguous_exact_name(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.session = _FakeSession(  # type: ignore[assignment]
        [
            [
                {"id": "jup-jupiter", "name": "Jupiter", "symbol": "JUP", "rank": 1724, "is_active": True},
                {
                    "id": "jup-jupiter-exchange-token",
                    "name": "Jupiter Exchange Token",
                    "symbol": "JUP",
                    "rank": 88,
                    "is_active": True,
                },
            ]
        ]
    )

    resolved = client.resolve_coin_id(
        coin_id="jupiter-exchange-solana",
        symbol="JUP",
        name="Jupiter",
        market_cap_rank=84,
    )

    assert resolved == "jup-jupiter-exchange-token"
    assert len(client.session.calls) == 1  # type: ignore[attr-defined]


def test_fetch_daily_history_is_normalized_and_cached(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _FakeSession(
        [
            [
                {"timestamp": "2026-09-18T00:00:00Z", "price": 1.25, "volume_24h": 1000, "market_cap": 5000},
                {"timestamp": "2026-09-19T00:00:00Z", "price": 1.5, "volume_24h": 1200, "market_cap": 6000},
            ]
        ]
    )
    client.session = session  # type: ignore[assignment]

    first = client.fetch_daily_history("jup-jupiter-exchange-token", start="2026-09-18", end="2026-09-19")
    second = client.fetch_daily_history("jup-jupiter-exchange-token", start="2026-09-18", end="2026-09-19")

    assert list(first.columns) == ["date", "pap_price", "pap_volume_usd", "pap_market_cap"]
    assert first["pap_price"].tolist() == [1.25, 1.5]
    assert second["pap_price"].tolist() == [1.25, 1.5]
    assert len(session.calls) == 1, "the second call must be served from disk"


def test_resolve_can_bypass_a_stale_id_map_after_catalog_refresh(tmp_path: Path) -> None:
    client = _client(tmp_path)
    map_path = tmp_path / "coinpaprika" / "catalog" / "id_map.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps({"jupiter-exchange-solana": "jup-jupiter"}), encoding="utf-8")
    client.session = _FakeSession(  # type: ignore[assignment]
        [
            [
                {"id": "jup-jupiter", "name": "Jupiter", "symbol": "JUP", "rank": 1724, "is_active": True},
                {
                    "id": "jup-jupiter-exchange-token",
                    "name": "Jupiter Exchange Token",
                    "symbol": "JUP",
                    "rank": 88,
                    "is_active": True,
                },
            ]
        ]
    )

    resolved = client.resolve_coin_id(
        coin_id="jupiter-exchange-solana",
        symbol="JUP",
        name="Jupiter",
        market_cap_rank=84,
        bypass_id_map=True,
    )

    assert resolved == "jup-jupiter-exchange-token"
