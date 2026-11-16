from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts import repair_bitget_mark_gaps


def _mark_frame(times: list[str]) -> pd.DataFrame:
    index = pd.to_datetime(times, utc=True)
    return pd.DataFrame(
        {
            "open_time": index,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 10.0,
            "quote_volume": 10.0,
        }
    )


def test_missing_hour_runs_groups_contiguous_gaps() -> None:
    frame = _mark_frame(
        [
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T04:00:00Z",
            "2026-01-01T06:00:00Z",
            "2026-01-01T06:00:00Z",
        ]
    )

    assert repair_bitget_mark_gaps.missing_hour_runs(
        frame,
        start=pd.Timestamp("2021-01-01", tz="UTC"),
        end=pd.Timestamp("2026-01-02", tz="UTC"),
    ) == [
        (
            pd.Timestamp("2026-01-01T02:00:00Z"),
            pd.Timestamp("2026-01-01T03:00:00Z"),
        ),
        (
            pd.Timestamp("2026-01-01T05:00:00Z"),
            pd.Timestamp("2026-01-01T05:00:00Z"),
        ),
    ]


def test_repair_symbol_fetches_only_missing_windows(tmp_path: Path) -> None:
    path = tmp_path / "candles" / "BTCUSDT_mark.csv"
    path.parent.mkdir(parents=True)
    _mark_frame(
        [
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T03:00:00Z",
        ]
    ).to_csv(path, index=False)
    calls: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    class _Client:
        def fetch_history_candles(self, symbol, candle_type, start, end):
            calls.append((pd.Timestamp(start), pd.Timestamp(end)))
            return _mark_frame(["2026-01-01T02:00:00Z"])

    result = repair_bitget_mark_gaps.repair_symbol(
        tmp_path,
        symbol="BTCUSDT",
        client=_Client(),
        start=pd.Timestamp("2021-01-01", tz="UTC"),
        end=pd.Timestamp("2026-01-02", tz="UTC"),
    )

    assert result.missing_before == 1
    assert result.missing_after == 0
    assert calls == [
        (
            pd.Timestamp("2026-01-01T01:00:00Z"),
            pd.Timestamp("2026-01-01T04:00:00Z"),
        )
    ]
    repaired = pd.read_csv(path)
    assert len(repaired) == 4


def test_repair_symbol_preserves_partial_fetches_when_a_later_window_fails(
    tmp_path: Path,
) -> None:
    path = tmp_path / "candles" / "BTCUSDT_mark.csv"
    path.parent.mkdir(parents=True)
    _mark_frame(
        [
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T03:00:00Z",
            "2026-01-01T06:00:00Z",
        ]
    ).to_csv(path, index=False)

    class _Client:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_history_candles(self, symbol, candle_type, start, end):
            self.calls += 1
            if self.calls == 1:
                return _mark_frame(["2026-01-01T02:00:00Z"])
            raise RuntimeError("rate limited")

    result = repair_bitget_mark_gaps.repair_symbol(
        tmp_path,
        symbol="BTCUSDT",
        client=_Client(),
        start=pd.Timestamp("2021-01-01", tz="UTC"),
        end=pd.Timestamp("2026-01-02", tz="UTC"),
        flush_every=1,
    )

    assert result.missing_before == 3
    assert result.missing_after == 2
    assert "rate limited" in (result.error or "")
    repaired = pd.read_csv(path)
    assert pd.Timestamp("2026-01-01T02:00:00Z") in set(
        pd.to_datetime(repaired["open_time"], utc=True)
    )


def test_repair_symbol_flushes_successful_batches_before_a_later_failure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "candles" / "BTCUSDT_mark.csv"
    path.parent.mkdir(parents=True)
    _mark_frame(
        [
            "2026-01-01T00:00:00Z",
            "2026-01-01T02:00:00Z",
            "2026-01-01T04:00:00Z",
            "2026-01-01T06:00:00Z",
        ]
    ).to_csv(path, index=False)

    class _Client:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_history_candles(self, symbol, candle_type, start, end):
            self.calls += 1
            if self.calls == 1:
                return _mark_frame(["2026-01-01T01:00:00Z"])
            if self.calls == 2:
                raise KeyboardInterrupt
            return _mark_frame(["2026-01-01T05:00:00Z"])

    with pytest.raises(KeyboardInterrupt):
        repair_bitget_mark_gaps.repair_symbol(
            tmp_path,
            symbol="BTCUSDT",
            client=_Client(),
            start=pd.Timestamp("2021-01-01", tz="UTC"),
            end=pd.Timestamp("2026-01-02", tz="UTC"),
            flush_every=1,
        )

    repaired = pd.read_csv(path)
    assert pd.Timestamp("2026-01-01T01:00:00Z") in set(
        pd.to_datetime(repaired["open_time"], utc=True)
    )
