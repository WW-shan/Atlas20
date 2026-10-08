"""CoinMarketCap historical market-cap client.

The repo previously derived long-history market caps by scaling price against
a current snapshot. That proxy does not track real supply changes, so the
Top-N universe it produced was not the real historical Top-N. CMC's public
data-api exposes true daily market cap and circulating supply.
"""

from __future__ import annotations

import json
import logging
import os
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


def test_cached_history_and_backfill_do_not_require_network(tmp_path: Path) -> None:
    page = [_quote("2024-01-01", 100.0, 1000.0), _quote("2024-01-02", 110.0, 1000.0)]
    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = _FakeSession([page])  # type: ignore[assignment]
    client.fetch_history(1, start="2024-01-01", end="2024-01-05")

    class _FailingSession:
        def get(self, *args, **kwargs):
            raise AssertionError("cached_history and has_backfill must not call the network")

    client.session = _FailingSession()  # type: ignore[assignment]

    assert len(client.cached_history(1)) == 2
    assert client.has_backfill(1, start="2024-01-01") is True
    assert client.has_backfill(1, start="2023-12-31") is False


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


def test_fetch_history_rewinds_past_a_delisted_series(tmp_path: Path) -> None:
    """A window ending long after a coin's last print comes back empty.

    The provider charges trailing empty days against the page, so a delisted
    coin (MATIC ends 2025-03-24) answers nothing for a window ending today even
    though 2,153 rows exist. Reading that as "no history" is what silently
    dropped MATIC - a Top-20 member on 123 rebalance dates - from the panel.
    """

    class _DelistedSession(_FakeSession):
        def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
            del url, timeout
            self.calls.append(dict(params))
            end = int(params["timeEnd"])
            last_print = int(pd.Timestamp("2025-03-24", tz="UTC").timestamp())
            if end - last_print > 400 * 86_400:
                return _FakeResponse({"data": {"quotes": []}})
            rows = self.page_for(int(params["timeStart"]), min(end, last_print))
            return _FakeResponse({"data": {"quotes": rows}})

    rows = [_quote(f"2025-03-{d:02d}", 0.2 + d / 100, 5_000_000_000.0) for d in range(20, 25)]
    session = _DelistedSession([rows])
    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = session  # type: ignore[assignment]

    frame = client.fetch_history(3890, start="2020-01-01", end="2026-09-22")

    assert not frame.empty, "a delisted series must not read as empty"
    assert pd.Timestamp(frame["date"].max()).date().isoformat() == "2025-03-24"
    assert len(session.calls) >= 2, "the empty page must trigger a rewind"
    assert session.calls[1]["timeEnd"] < session.calls[0]["timeEnd"]


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


# --------------------------------------------------------------------------
# Duplicate dates across cache windows: the newest fetch must win.
#
# The daily refresh writes a ~400-row tail window every day, so almost every
# date is cached several times (43,939 overlapping rows on 2026-09-24). The
# merge concatenated the windows and then ran pandas' default quicksort, which
# is not stable, so ``keep="last"`` kept whichever copy the sort happened to
# leave last: with a revised tail the new value survived on 209 of 398 dates
# and the stale one on the other 189.


def _write_window(directory: Path, name: str, rows: list[dict], *, fetched_at: float) -> Path:
    """Write a cache window and stamp it with the time it was fetched."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(rows), encoding="utf-8")
    os.utime(path, (fetched_at, fetched_at))
    return path


def _overlap_days() -> list[str]:
    return [day.date().isoformat() for day in pd.date_range("2025-08-21", periods=398, freq="D")]


def test_merged_cache_keeps_the_newest_fetch_on_every_duplicated_date(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client = CoinMarketCapClient(_config(), tmp_path)
    history = tmp_path / "coinmarketcap" / "history"
    _write_window(
        history,
        "99_1577836800_1789862400.json",
        [_quote(day, 100.0, 1000.0) for day in _overlap_days()],
        fetched_at=1_780_000_000,
    )
    _write_window(
        history,
        "99_1789516800_1789948800.json",
        [_quote(day, 101.0, 1000.0) for day in _overlap_days()],
        fetched_at=1_780_000_100,
    )

    with caplog.at_level(logging.WARNING):
        merged = client.cached_history(99)

    assert len(merged) == 398
    stale = int((merged["close"] != 101.0).sum())
    assert stale == 0, f"the older fetch survived on {stale} of 398 duplicated dates"
    assert client.duplicate_conflicts[99] == 398
    assert "398" in caplog.text and "conflict" in caplog.text


def test_merged_cache_orders_windows_by_fetch_time_not_by_filename(tmp_path: Path) -> None:
    """A forced full re-download is the newest fetch, yet its filename (the
    earliest start epoch) sorts before every tail window, so filename order is
    not fetch order."""
    client = CoinMarketCapClient(_config(), tmp_path)
    history = tmp_path / "coinmarketcap" / "history"
    _write_window(
        history,
        "99_1789516800_1789948800.json",
        [_quote(day, 100.0, 1000.0) for day in _overlap_days()],
        fetched_at=1_780_000_000,
    )
    _write_window(
        history,
        "99_1577836800_1790035200.json",
        [_quote(day, 102.0, 1000.0) for day in _overlap_days()],
        fetched_at=1_780_000_100,
    )

    merged = client.cached_history(99)

    assert (merged["close"] == 102.0).all()


def test_identical_duplicates_are_not_reported_as_conflicts(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client = CoinMarketCapClient(_config(), tmp_path)
    history = tmp_path / "coinmarketcap" / "history"
    rows = [_quote(day, 100.0, 1000.0) for day in _overlap_days()]
    _write_window(history, "99_1577836800_1789862400.json", rows, fetched_at=1_780_000_000)
    _write_window(history, "99_1789516800_1789948800.json", rows, fetched_at=1_780_000_100)

    with caplog.at_level(logging.WARNING):
        merged = client.cached_history(99)

    assert len(merged) == 398
    assert client.duplicate_conflicts[99] == 0
    assert "conflict" not in caplog.text


# --------------------------------------------------------------------------
# An empty or unreadable answer is not coverage.
#
# The first run for a new entrant cached a 0-row answer to the full backfill
# under the full-range filename (99_1577836800_...json). From then on the
# filename alone made ``has_backfill`` True, so every later run only pulled a
# "tail" - which the endpoint answers with the most recent ~400 rows - and the
# coin's history stayed truncated at 2025-08 although it starts in 2021.


def _history_rows(first: str, last: str) -> list[dict]:
    return [_quote(day.date().isoformat(), 1.0, 1000.0) for day in pd.date_range(first, last, freq="D")]


class _EndpointSession(_FakeSession):
    """Answers like the endpoint: the newest 400 rows opened at or before
    timeEnd (inclusive - the real 2019-2026 backfills have no gap at any of
    their page boundaries)."""

    def __init__(self, rows: list[dict], *, healthy: bool = True) -> None:
        super().__init__([])
        self.rows = rows
        self.healthy = healthy

    def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
        del url, timeout
        self.calls.append(dict(params))
        if not self.healthy:
            return _FakeResponse({"data": {"quotes": []}, "status": {"error_code": "0"}})
        end = int(params["timeEnd"])
        rows = [row for row in self.rows if int(pd.Timestamp(row["timeOpen"]).timestamp()) <= end]
        return _FakeResponse({"data": {"quotes": rows[-400:]}, "status": {"error_code": "0"}})


def test_an_empty_backfill_answer_is_neither_cached_nor_counted(tmp_path: Path) -> None:
    rows = _history_rows("2021-01-01", "2026-09-22")
    client = CoinMarketCapClient(_config(), tmp_path)
    history_dir = tmp_path / "coinmarketcap" / "history"

    client.session = _EndpointSession(rows, healthy=False)  # type: ignore[assignment]
    first = client.ensure_history(99, start="2020-01-01", end="2026-09-22")
    persisted_after_empty_answer = sorted(path.name for path in history_dir.glob("99_*.json"))
    backfilled_after_empty_answer = client.has_backfill(99, start="2020-01-01")

    client.session = _EndpointSession(rows)  # type: ignore[assignment]
    second = client.ensure_history(99, start="2020-01-01", end="2026-09-23")

    assert first.empty
    assert pd.Timestamp(second["date"].min()).date().isoformat() == "2021-01-01", (
        "the healthy run after an empty backfill answer must backfill in full, "
        f"not pull a tail (got {len(second)} rows from {pd.Timestamp(second['date'].min()).date()})"
    )
    assert len(second) == len(rows)
    assert persisted_after_empty_answer == [], "an empty backfill answer must not be cached"
    assert backfilled_after_empty_answer is False


def test_a_legacy_empty_backfill_file_is_not_coverage(tmp_path: Path) -> None:
    """A 0-row file left by an older run - even under today's exact filename -
    must neither satisfy ``has_backfill`` nor be served as a cache hit."""
    rows = _history_rows("2021-01-01", "2026-09-22")
    history_dir = tmp_path / "coinmarketcap" / "history"
    history_dir.mkdir(parents=True)
    (history_dir / "99_1577836800_1790121600.json").write_text("[]", encoding="utf-8")
    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = _EndpointSession(rows)  # type: ignore[assignment]

    assert client.has_backfill(99, start="2020-01-01") is False
    history = client.ensure_history(99, start="2020-01-01", end="2026-09-23")

    assert pd.Timestamp(history["date"].min()).date().isoformat() == "2021-01-01"
    assert len(history) == len(rows)


def test_an_unreadable_backfill_file_is_not_coverage(tmp_path: Path) -> None:
    """A truncated write would otherwise count as a backfill forever too."""
    rows = _history_rows("2021-01-01", "2026-09-22")
    history_dir = tmp_path / "coinmarketcap" / "history"
    history_dir.mkdir(parents=True)
    (history_dir / "99_1577836800_1790121600.json").write_text('[{"timeOpen": "2021-01-0', encoding="utf-8")
    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = _EndpointSession(rows)  # type: ignore[assignment]

    assert client.has_backfill(99, start="2020-01-01") is False
    history = client.ensure_history(99, start="2020-01-01", end="2026-09-23")

    assert len(history) == len(rows)


@pytest.mark.parametrize("error_code", ["500", 1006])
def test_a_nonzero_error_code_raises_even_when_a_data_key_is_present(tmp_path: Path, error_code: object) -> None:
    class _ErrorSession(_FakeSession):
        def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
            del url, timeout
            self.calls.append(dict(params))
            return _FakeResponse(
                {
                    "data": {"quotes": []},
                    "status": {"error_code": error_code, "error_message": "Internal system error"},
                }
            )

    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = _ErrorSession([])  # type: ignore[assignment]

    with pytest.raises(ValueError, match="error_code"):
        client.fetch_history(99, start="2020-01-01", end="2026-09-23")
    assert not list((tmp_path / "coinmarketcap" / "history").glob("99_*.json"))


@pytest.mark.parametrize("error_code", ["0", 0, None])
def test_a_success_status_code_is_accepted(tmp_path: Path, error_code: object) -> None:
    class _OkSession(_FakeSession):
        def get(self, url: str, params: dict[str, object], timeout: int) -> _FakeResponse:
            del url, timeout
            self.calls.append(dict(params))
            return _FakeResponse(
                {"data": {"quotes": [_quote("2024-01-01", 1.0, 10.0)]}, "status": {"error_code": error_code}}
            )

    client = CoinMarketCapClient(_config(), tmp_path)
    client.session = _OkSession([])  # type: ignore[assignment]

    assert len(client.fetch_history(99, start="2024-01-01", end="2024-01-02")) == 1
