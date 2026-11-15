"""Gate.io exchange-candle client tests."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pandas as pd
import pytest
import requests

from atlas20.config import GateIOConfig
from atlas20.data.gateio import GateIOClient


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
            raise requests.HTTPError(f"status {self.status_code}")


class _FakeSession:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls = 0

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del url, params, timeout
        self.calls += 1
        return _FakeResponse(self.payload)


def _client(tmp_path: Path) -> GateIOClient:
    return GateIOClient(GateIOConfig(rate_limit_seconds=0.0, max_retries=1), tmp_path)


def test_fetch_daily_candles_normalizes_and_caches(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _FakeSession(
        [
            ["1789689600", "1000.5", "10.25", "11", "9", "10", "100", "true"],
            ["1789776000", "2000.5", "10.5", "12", "10", "10.25", "200", "true"],
        ]
    )
    client.session = session  # type: ignore[assignment]

    first = client.fetch_daily_candles("BTC")
    second = client.fetch_daily_candles("BTC")

    assert first["gate_price"].tolist() == [10.25, 10.5]
    assert first["gate_volume_usd"].tolist() == [1000.5, 2000.5]
    assert second["gate_price"].tolist() == [10.25, 10.5]
    assert session.calls == 1



class _RecordingSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del url, timeout
        self.calls.append(dict(params))
        start = int(params["from"])
        end = int(params["to"])
        return _FakeResponse([_candle(pd.Timestamp(start, unit="s", tz="UTC"), 1.0), _candle(pd.Timestamp(end, unit="s", tz="UTC"), 2.0)])


def test_fetch_daily_candles_chunks_a_multi_year_ended_feed(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _RecordingSession()
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_daily_candles(
        "HT", start=pd.Timestamp("2020-01-01"), end=pd.Timestamp("2022-12-31")
    )

    assert len(session.calls) > 1, "Gate.io rejects a from/to span longer than its page limit"
    assert all(int(call["to"]) - int(call["from"]) <= 400 * 86_400 for call in session.calls)
    assert int(session.calls[0]["from"]) == int(
        pd.Timestamp("2020-01-01", tz="UTC").timestamp()
    )
    assert int(session.calls[-1]["to"]) == int(
        pd.Timestamp("2022-12-31", tz="UTC").timestamp()
    )
    assert len(frame) == 2 * len(session.calls)
    assert frame["gate_price"].tolist()[:2] == [1.0, 2.0]


class _PartialFailureSession(_RecordingSession):
    def __init__(self) -> None:
        super().__init__()

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del url, timeout
        self.calls.append(dict(params))
        if len(self.calls) == 1:
            return _FakeResponse({"label": "INVALID_CURRENCY_PAIR"}, status_code=400)
        start = int(params["from"])
        return _FakeResponse([_candle(pd.Timestamp(start, unit="s", tz="UTC"), 2.0)])


def test_fetch_daily_candles_skips_an_unlisted_prefix_window(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _PartialFailureSession()
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_daily_candles(
        "HT", start=pd.Timestamp("2020-01-01"), end=pd.Timestamp("2022-12-31")
    )

    assert len(session.calls) > 1
    assert not frame.empty
    assert set(frame["gate_price"]) == {2.0}

def test_an_empty_success_payload_is_not_cached_as_coverage(tmp_path: Path) -> None:
    client = _client(tmp_path)
    session = _FakeSession([])
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_daily_candles(
        "POL", start=pd.Timestamp("2020-01-01"), end=pd.Timestamp("2020-12-31")
    )

    assert frame.empty
    assert session.calls == 1
    assert not list((tmp_path / "gateio" / "candles").glob("POL_USDT_*.json"))


def test_a_stale_empty_cached_window_is_removed_and_refetched(tmp_path: Path) -> None:
    client = _client(tmp_path)
    path = tmp_path / "gateio" / "candles" / "POL_USDT_400_2020-01-01_2020-12-31.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    session = _FakeSession([_candle(pd.Timestamp("2020-06-01", tz="UTC"), 0.4)])
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_daily_candles(
        "POL", start=pd.Timestamp("2020-01-01"), end=pd.Timestamp("2020-12-31")
    )

    assert len(frame) == 1
    assert session.calls == 1
    assert json.loads(path.read_text(encoding="utf-8"))


def test_invalid_pair_is_not_cached_as_a_valid_series(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.session = _FakeSession({"label": "INVALID_CURRENCY_PAIR", "message": "bad pair"})  # type: ignore[assignment]

    try:
        client.fetch_daily_candles("NOTLISTED")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid Gate.io pairs must raise")


def test_pair_alias_overrides_default_symbol_quote() -> None:
    client = GateIOConfig(pair_aliases={"XMR": "XMR_BTC"})
    from atlas20.data.gateio import GateIOClient as Client

    instance = Client(client, Path("/tmp/unused"))
    assert instance.resolve_pair("xmr") == "XMR_BTC"


# The processor asks Gate.io for a fresh 400-day window every day, so a date
# sits in up to ~400 cached windows. The newest window must win: the one
# fetched while a day was still trading carries a provisional close, and the
# loader used an unstable sort before ``keep="last"``.


def _candle(day: pd.Timestamp, close: float) -> list[str]:
    return [str(int(day.timestamp())), "1000000", str(close), "0", "0", "0", "0", "true"]


def _write_window(directory: Path, name: str, rows: list[list[str]], *, fetched_at: float) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(rows), encoding="utf-8")
    os.utime(path, (fetched_at, fetched_at))


def test_load_daily_candles_keeps_the_newest_window_on_duplicated_dates(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client = _client(tmp_path)
    directory = tmp_path / "gateio" / "candles"
    days = pd.date_range("2025-08-21", periods=398, freq="D", tz="UTC")
    _write_window(
        directory,
        "BTC_USDT_400_2025-08-16_2026-09-20.json",
        [_candle(day, 10.0) for day in days],
        fetched_at=1_780_000_000,
    )
    _write_window(
        directory,
        "BTC_USDT_400_2025-08-17_2026-09-21.json",
        [_candle(day, 11.0) for day in days],
        fetched_at=1_780_000_100,
    )

    with caplog.at_level(logging.WARNING):
        frame = client.load_daily_candles("BTC")

    assert len(frame) == 398
    stale = int((frame["gate_price"] != 11.0).sum())
    assert stale == 0, f"the older window survived on {stale} of 398 duplicated dates"
    assert client.duplicate_conflicts["BTC_USDT"] == 398
    assert "398" in caplog.text and "conflict" in caplog.text
