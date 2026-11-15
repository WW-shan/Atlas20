"""KuCoin exchange-candle client tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from atlas20.config import KuCoinConfig
from atlas20.data.kucoin import KuCoinClient


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = json.dumps(payload)

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError(f"status {self.status_code}")


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del timeout
        self.calls.append({"url": url, **params})
        return _FakeResponse(
            {
                "code": "200000",
                "data": [
                    ["1659312000", "9.90", "10.05", "10.20", "9.80", "1000", "10050"],
                    ["1659225600", "10.10", "9.95", "10.30", "9.90", "1100", "10945"],
                ],
            }
        )


def _client(tmp_path: Path) -> KuCoinClient:
    return KuCoinClient(KuCoinConfig(rate_limit_seconds=0.0, max_retries=1), tmp_path)


def test_fetch_daily_candles_normalizes_and_caches(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _FakeSession()
    client.session = session  # type: ignore[assignment]

    first = client.fetch_daily_candles(
        "KCS", start=pd.Timestamp("2022-07-30"), end=pd.Timestamp("2022-08-01")
    )
    second = client.fetch_daily_candles(
        "KCS", start=pd.Timestamp("2022-07-30"), end=pd.Timestamp("2022-08-01")
    )

    assert first["kucoin_price"].tolist() == [9.95, 10.05]
    assert first["kucoin_volume_usd"].tolist() == [10945.0, 10050.0]
    assert second["kucoin_price"].tolist() == [9.95, 10.05]
    assert len(session.calls) == 1
    assert session.calls[0]["symbol"] == "KCS-USDT"



def test_a_single_day_gap_pads_the_api_window_but_filters_the_result(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _FakeSession()
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_daily_candles(
        "KCS", start=pd.Timestamp("2022-07-31"), end=pd.Timestamp("2022-07-31")
    )

    assert len(frame) == 1
    assert frame.iloc[0]["date"] == pd.Timestamp("2022-07-31")
    assert session.calls[0]["startAt"] == int(pd.Timestamp("2022-07-30", tz="UTC").timestamp())
    assert session.calls[0]["endAt"] == int(pd.Timestamp("2022-08-01", tz="UTC").timestamp())


class _EmptySession:
    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del url, params, timeout
        return _FakeResponse({"code": "200000", "data": []})


def test_an_empty_response_is_not_cached_as_coverage(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.session = _EmptySession()  # type: ignore[assignment]

    frame = client.fetch_daily_candles(
        "KCS", start=pd.Timestamp("2022-07-31"), end=pd.Timestamp("2022-07-31")
    )

    assert frame.empty
    assert not list((tmp_path / "kucoin" / "candles").glob("*.json"))


def test_fetch_accepts_timezone_aware_cmc_dates(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.session = _FakeSession()  # type: ignore[assignment]

    frame = client.fetch_daily_candles(
        "KCS",
        start=pd.Timestamp("2022-07-31", tz="UTC"),
        end=pd.Timestamp("2022-07-31", tz="UTC"),
    )

    assert frame["date"].tolist() == [pd.Timestamp("2022-07-31")]

def test_pair_alias_overrides_the_default_pair(tmp_path: Path) -> None:
    client = KuCoinClient(
        KuCoinConfig(pair_aliases={"KCS": "KCS-USDT"}, rate_limit_seconds=0.0),
        tmp_path,
    )

    assert client.resolve_pair("kcs") == "KCS-USDT"
    assert client.has_configured_pair("KCS")
    assert not client.has_configured_pair("BTC")
