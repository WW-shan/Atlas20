from __future__ import annotations

import pandas as pd
import pytest

from scripts.download_binance_30m import normalize_klines, validate_candle_frame, validate_epoch_ms


def _row(open_time: int) -> list[object]:
    return [
        open_time,
        "100.0",
        "101.0",
        "99.0",
        "100.5",
        "10.0",
        open_time + 1_799_999,
        "1000.0",
        5,
        "6.0",
        "600.0",
        "0",
    ]


def test_validate_epoch_ms_accepts_only_current_binance_milliseconds() -> None:
    assert validate_epoch_ms(1_735_689_600_000) == 1_735_689_600_000

    with pytest.raises(ValueError, match="milliseconds"):
        validate_epoch_ms(1_735_689_600_000_000)
    with pytest.raises(ValueError, match="milliseconds"):
        validate_epoch_ms(1_735_689_600)
    with pytest.raises(ValueError, match="milliseconds"):
        validate_epoch_ms(0)


def test_normalize_klines_writes_a_canonical_integer_open_time_ms() -> None:
    frame = normalize_klines([_row(1_735_689_600_000), _row(1_735_691_400_000)], "BTCUSDT")

    assert frame["open_time_ms"].tolist() == [1_735_689_600_000, 1_735_691_400_000]
    assert str(frame["open_time"].dt.tz) == "UTC"
    assert frame["open_time"].iloc[0] == pd.Timestamp("2025-01-01 00:00:00+00:00")
    assert frame["close"].tolist() == [100.5, 100.5]


def test_validate_candle_frame_rejects_the_1970_corruption_pattern() -> None:
    frame = pd.DataFrame(
        {
            "open_time_ms": [293_300_000, 294_000_000],
            "open_time": pd.to_datetime([293_300_000, 294_000_000], unit="ms", utc=True),
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1.0, 1.0],
            "quote_volume": [100.0, 100.0],
        }
    )

    with pytest.raises(ValueError, match="1970"):
        validate_candle_frame(frame, pair="BTCUSDT")
