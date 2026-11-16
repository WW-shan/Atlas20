from __future__ import annotations

import pandas as pd

from scripts.audit_bitget_funding_publication import evaluate_boundary_observation


def _timestamp_ms(value: str) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def _observation(*, include_history: bool = True) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "current_request_time": _timestamp_ms("2026-11-16T16:00:32Z"),
        "current": {
            "fundingRateInterval": "8",
            "nextUpdate": str(_timestamp_ms("2026-11-17T00:00:00Z")),
            "lastFundingRate": "0.000055",
        },
        "funding_time": {
            "nextFundingTime": str(_timestamp_ms("2026-11-17T00:00:00Z")),
            "ratePeriod": "8",
        },
        "history": (
            [
                {
                    "funding_time": "2026-11-16 16:00:00+00:00",
                    "funding_rate": 0.000055,
                }
            ]
            if include_history
            else []
        ),
    }


def test_boundary_observation_proves_current_and_history_publication() -> None:
    result = evaluate_boundary_observation(
        _observation(), expected_settlement="2026-11-16T16:00:00Z"
    )

    assert result["passed"] is True
    assert result["derived_settlement_time"] == "2026-11-16T16:00:00+00:00"
    assert result["publication_lag_seconds"] == 32.0
    assert result["history_matches_current"] is True


def test_boundary_observation_fails_when_history_has_not_published() -> None:
    result = evaluate_boundary_observation(
        _observation(include_history=False),
        expected_settlement="2026-11-16T16:00:00Z",
    )

    assert result["passed"] is False
    assert result["history_has_expected_settlement"] is False
