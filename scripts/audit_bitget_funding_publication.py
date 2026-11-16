"""Probe Bitget funding publication at one settlement boundary.

The probe is read-only and uses two independent public endpoints:

* ``current-fund-rate`` exposes ``lastFundingRate`` and ``nextUpdate``;
  ``nextUpdate - fundingRateInterval`` is the latest settled timestamp.
* ``history-fund-rate`` should contain that same timestamp and rate.

The report preserves Bitget's own ``requestTime`` for each call, so it can prove
whether the settlement was actually published by the observation instant rather
than inferring publication from a local clock.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from atlas20.derivatives.bitget import BitgetClient
from atlas20.logging_utils import atomic_write_text, ensure_dir

DEFAULT_SYMBOLS = (
    "BTCUSDT",
    "BCHUSDT",
    "NEARUSDT",
    "HYPEUSDT",
    "ZECUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
)
DEFAULT_OUTPUT = Path("reports/ls45_live_g175/funding_publication_boundary_probe.json")


def _timestamp_ms(value: object) -> pd.Timestamp | None:
    try:
        milliseconds = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return pd.Timestamp(milliseconds, unit="ms", tz="UTC") if milliseconds > 0 else None


def _float_or_nan(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def evaluate_boundary_observation(
    observation: dict[str, Any], *, expected_settlement: object
) -> dict[str, Any]:
    """Evaluate one raw two-endpoint observation against a settlement instant."""

    expected = pd.Timestamp(expected_settlement)
    if expected.tzinfo is None:
        expected = expected.tz_localize("UTC")
    else:
        expected = expected.tz_convert("UTC")
    current = observation.get("current")
    funding_time = observation.get("funding_time")
    current = current if isinstance(current, dict) else {}
    funding_time = funding_time if isinstance(funding_time, dict) else {}
    interval = _float_or_nan(
        current.get("fundingRateInterval", funding_time.get("ratePeriod"))
    )
    next_update = _timestamp_ms(
        current.get("nextUpdate", funding_time.get("nextFundingTime"))
    )
    derived = (
        next_update - pd.Timedelta(hours=interval)
        if next_update is not None and math.isfinite(interval) and interval > 0.0
        else None
    )
    request_times = [
        _timestamp_ms(observation.get(key))
        for key in (
            "current_request_time",
            "funding_time_request_time",
            "history_request_time",
        )
    ]
    request_times = [stamp for stamp in request_times if stamp is not None]
    observed_at = max(request_times) if request_times else None
    publication_lag = (
        (observed_at - expected).total_seconds() if observed_at is not None else None
    )
    current_rate = _float_or_nan(current.get("lastFundingRate"))
    history_rows = observation.get("history")
    history_rows = history_rows if isinstance(history_rows, list) else []
    matching_history: dict[str, Any] | None = None
    for row in history_rows:
        if not isinstance(row, dict):
            continue
        try:
            stamp = pd.Timestamp(row.get("funding_time"))
        except (TypeError, ValueError):
            continue
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        else:
            stamp = stamp.tz_convert("UTC")
        if stamp == expected:
            matching_history = row
            break
    history_rate = _float_or_nan(
        matching_history.get("funding_rate") if matching_history else None
    )
    history_matches_current = bool(
        math.isfinite(history_rate)
        and math.isfinite(current_rate)
        and math.isclose(history_rate, current_rate, rel_tol=1e-12, abs_tol=1e-12)
    )
    current_matches_expected = derived is not None and derived == expected
    request_after_settlement = publication_lag is not None and publication_lag >= 0.0
    history_has_expected = matching_history is not None
    passed = bool(
        current_matches_expected
        and request_after_settlement
        and history_has_expected
        and history_matches_current
    )
    return {
        "symbol": observation.get("symbol"),
        "expected_settlement_time": expected.isoformat(),
        "derived_settlement_time": derived.isoformat() if derived else None,
        "next_funding_time": next_update.isoformat() if next_update else None,
        "interval_hours": interval if math.isfinite(interval) else None,
        "observed_at": observed_at.isoformat() if observed_at else None,
        "publication_lag_seconds": publication_lag,
        "current_funding_rate": (
            current_rate if math.isfinite(current_rate) else None
        ),
        "history_funding_rate": (
            history_rate if math.isfinite(history_rate) else None
        ),
        "current_settlement_matches_expected": current_matches_expected,
        "request_after_settlement": request_after_settlement,
        "history_has_expected_settlement": history_has_expected,
        "history_matches_current": history_matches_current,
        "passed": passed,
    }


def probe_boundary(
    client: BitgetClient,
    *,
    symbols: list[str],
    expected_settlement: object,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    for symbol in symbols:
        observation: dict[str, Any] = {"symbol": symbol.upper()}
        try:
            observation["current"] = client.fetch_current_funding(symbol)
            observation["current_request_time"] = client.last_request_time_ms
        except Exception as exc:  # noqa: BLE001 - retain partial two-source evidence
            observation["current_error"] = repr(exc)
        try:
            observation["funding_time"] = client.fetch_funding_time(symbol)
            observation["funding_time_request_time"] = client.last_request_time_ms
        except Exception as exc:  # noqa: BLE001
            observation["funding_time_error"] = repr(exc)
        try:
            history = client.fetch_funding_history(symbol, page_size=5, max_pages=1)
            observation["history_request_time"] = client.last_request_time_ms
            observation["history"] = history.to_dict("records")
        except Exception as exc:  # noqa: BLE001
            observation["history_error"] = repr(exc)
            observation["history"] = []
        observations.append(observation)
        evaluations.append(
            evaluate_boundary_observation(
                observation, expected_settlement=expected_settlement
            )
        )
    return {
        "probe": "bitget-public-funding-publication",
        "expected_settlement_time": str(expected_settlement),
        "symbol_count": len(symbols),
        "passed_count": sum(1 for item in evaluations if item["passed"]),
        "failed_count": sum(1 for item in evaluations if not item["passed"]),
        "publication_lag_seconds": {
            "min": min(
                (
                    item["publication_lag_seconds"]
                    for item in evaluations
                    if item["publication_lag_seconds"] is not None
                ),
                default=None,
            ),
            "max": max(
                (
                    item["publication_lag_seconds"]
                    for item in evaluations
                    if item["publication_lag_seconds"] is not None
                ),
                default=None,
            ),
        },
        "evaluations": evaluations,
        "observations": observations,
        "passed": bool(evaluations) and all(item["passed"] for item in evaluations),
        "limitation": (
            "This proves publication at the recorded settlement/request instants. "
            "It does not retroactively prove an unrecorded earlier observation."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--expected-settlement", required=True)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args(argv)
    symbols = [
        item.strip().upper() for item in args.symbols.split(",") if item.strip()
    ]
    if not symbols:
        raise SystemExit("--symbols must contain at least one contract")
    if args.timeout_seconds <= 0.0:
        raise SystemExit("--timeout-seconds must be positive")
    client = BitgetClient(
        timeout_seconds=float(args.timeout_seconds),
        rate_limit_seconds=0.02,
    )
    result = probe_boundary(
        client,
        symbols=symbols,
        expected_settlement=args.expected_settlement,
    )
    ensure_dir(args.json_out.parent)
    atomic_write_text(
        args.json_out,
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
    )
    print(
        f"funding publication boundary: {'PASS' if result['passed'] else 'FAIL'} "
        f"({result['passed_count']}/{result['symbol_count']}, "
        f"lag={result['publication_lag_seconds']['min']}.."
        f"{result['publication_lag_seconds']['max']}s)"
    )
    for item in result["evaluations"]:
        if not item["passed"]:
            print(
                f"  FAIL {item['symbol']}: derived={item['derived_settlement_time']} "
                f"history={item['history_has_expected_settlement']} "
                f"rate_match={item['history_matches_current']}"
            )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
