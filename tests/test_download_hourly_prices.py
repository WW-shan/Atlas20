from __future__ import annotations

import gzip

import pandas as pd

from scripts.download_hourly_prices import download_gate_pair


class _Response:
    def __init__(self, status_code: int, *, content: bytes = b"", payload: object = None) -> None:
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.content = content
        self._payload = payload
        self.text = ""

    def json(self) -> object:
        return self._payload


class _Session:
    """Answers Gate's bulk archive by month and its API from a fixed list."""

    def __init__(self, archive: dict[str, bytes], api_rows: list[list[str]]) -> None:
        self.archive = archive
        self.api_rows = api_rows
        self.urls: list[str] = []
        self.api_windows: list[tuple[int, int]] = []

    def get(self, url: str, params: dict[str, object] | None = None, timeout: float = 0.0) -> _Response:
        self.urls.append(url)
        if "download.gatedata.org" in url:
            month = url.rsplit("-", 1)[-1].split(".")[0]
            if month not in self.archive:
                return _Response(404)
            return _Response(200, content=self.archive[month])
        assert params is not None
        start, stop = int(params["from"]), int(params["to"])
        self.api_windows.append((start, stop))
        rows = [row for row in self.api_rows if start <= int(row[0]) <= stop]
        return _Response(200, payload=rows)


def _archive_month(rows: list[tuple[int, float, float, float, float, float]]) -> bytes:
    # Gate's archive columns: timestamp, volume, close, high, low, open.
    text = "\n".join(",".join(str(value) for value in row) for row in rows) + "\n"
    return gzip.compress(text.encode("utf-8"))


def _ts(value: str) -> int:
    return int(pd.Timestamp(value, tz="UTC").timestamp())


def test_gate_archive_columns_map_to_open_and_close() -> None:
    archive = {
        "202401": _archive_month(
            [
                (_ts("2024-01-31 22:00"), 10.0, 101.0, 102.0, 99.0, 100.0),
                (_ts("2024-01-31 23:00"), 11.0, 103.0, 104.0, 100.5, 101.0),
            ]
        )
    }
    session = _Session(archive, api_rows=[])

    frame = download_gate_pair(
        session,
        "https://api.gateio.ws/api/v4",
        "AAA_USDT",
        pd.Timestamp("2024-01-31 22:00", tz="UTC"),
        pd.Timestamp("2024-02-01 00:00", tz="UTC"),
        now=pd.Timestamp("2026-01-01", tz="UTC"),
        pause_seconds=0.0,
    )

    assert frame is not None
    assert frame["open"].tolist() == [100.0, 101.0]
    assert frame["close"].tolist() == [101.0, 103.0]
    assert frame["high"].tolist() == [102.0, 104.0]
    assert str(frame["open_time"].dt.tz) == "UTC"


def test_gate_api_fills_the_hours_after_the_last_archived_month() -> None:
    archive = {"202608": _archive_month([(_ts("2026-08-31 23:00"), 1.0, 11.0, 11.5, 10.0, 10.5)])}
    # API rows: t, quote volume, close, high, low, open, base volume, closed.
    api_rows = [
        [str(_ts("2026-08-31 23:00")), "9", "99.0", "99", "99", "99", "1", "true"],
        [str(_ts("2026-09-01 00:00")), "9", "12.0", "12.5", "10.9", "11.0", "1", "true"],
    ]
    session = _Session(archive, api_rows)

    frame = download_gate_pair(
        session,
        "https://api.gateio.ws/api/v4",
        "AAA_USDT",
        pd.Timestamp("2026-08-31 23:00", tz="UTC"),
        pd.Timestamp("2026-09-01 01:00", tz="UTC"),
        now=pd.Timestamp("2026-09-01 01:00", tz="UTC"),
        pause_seconds=0.0,
    )

    assert frame is not None
    # The archive keeps its hour; the API only adds what the archive lacks.
    assert frame["close"].tolist() == [11.0, 12.0]
    assert frame["open"].tolist() == [10.5, 11.0]


def test_gate_pair_without_any_candles_is_unavailable() -> None:
    session = _Session(archive={}, api_rows=[])

    frame = download_gate_pair(
        session,
        "https://api.gateio.ws/api/v4",
        "NONE_USDT",
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-03-01", tz="UTC"),
        now=pd.Timestamp("2026-01-01", tz="UTC"),
        pause_seconds=0.0,
    )

    assert frame is None


def test_gate_api_window_never_reaches_past_the_ten_thousand_hour_limit() -> None:
    session = _Session(archive={}, api_rows=[])
    now = pd.Timestamp("2026-09-24 00:00", tz="UTC")

    download_gate_pair(
        session,
        "https://api.gateio.ws/api/v4",
        "AAA_USDT",
        pd.Timestamp("2022-01-01", tz="UTC"),
        now,
        now=now,
        pause_seconds=0.0,
    )

    # Gate answers "Candlestick too long ago" beyond 10,000 hourly points, so
    # older hours can only come from the monthly archive.
    assert session.api_windows
    earliest = min(start for start, _ in session.api_windows)
    assert earliest >= int((now - pd.Timedelta(hours=10_000)).timestamp())
    assert all(stop - start < 1000 * 3600 for start, stop in session.api_windows)
