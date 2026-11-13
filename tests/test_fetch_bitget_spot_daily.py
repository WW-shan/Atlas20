from __future__ import annotations

import pandas as pd
import pytest


def test_normalize_history_payload_rejects_missing_ohlc() -> None:
    from scripts.fetch_bitget_spot_daily import normalize_history_payload

    rows = [
        ["1640995200000", "100", "110", "90", "105", "1", "100"],
        ["1641081600000", "105", None, "95", "100", "1", "100"],
    ]

    with pytest.raises(ValueError, match="missing or non-finite"):
        normalize_history_payload(rows)


def test_audit_daily_coverage_reports_missing_dates() -> None:
    from scripts.fetch_bitget_spot_daily import audit_daily_coverage

    index = pd.DatetimeIndex(
        [
            "2024-01-01 00:00:00+00:00",
            "2024-01-02 00:00:00+00:00",
            "2024-01-04 00:00:00+00:00",
        ]
    )

    audit = audit_daily_coverage(index)

    assert audit["rows"] == 3
    assert audit["missing_dates"] == ["2024-01-03 00:00:00+00:00"]
    assert audit["is_continuous"] is False


def test_normalize_history_payload_sorts_and_deduplicates() -> None:
    from scripts.fetch_bitget_spot_daily import normalize_history_payload

    rows = [
        ["1641081600000", "105", "110", "95", "100", "1", "100"],
        ["1640995200000", "100", "105", "90", "101", "1", "100"],
        ["1641081600000", "105", "111", "95", "102", "1", "100"],
    ]

    frame = normalize_history_payload(rows)

    assert frame["open_time"].is_monotonic_increasing
    assert len(frame) == 2
    assert frame.iloc[-1]["close"] == pytest.approx(102.0)
