"""Fetch Bitget UTC daily spot candles for the LS100 research snapshot.

The public API endpoint returns at most 200 candles per request.  We walk
backwards with an inclusive ``endTime`` and deduplicate overlapping pages.  The
script is acquisition-only: it never sends orders and never modifies live
state.  Raw files stay under the git-ignored ``data/raw`` tree; the manifest
records hashes and coverage so a report can be audited.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas20.logging_utils import ensure_dir  # noqa: E402

ENDPOINT = "https://api.bitget.com/api/v2/spot/market/history-candles"
GRANULARITY = "1Dutc"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
COLUMNS = ["open_time", "open", "high", "low", "close", "base_volume", "quote_volume"]


def _parse_timestamp(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tz is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _period_index(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    start = _parse_timestamp(start).normalize()
    end = _parse_timestamp(end).normalize()
    if end < start:
        raise ValueError("end must not be earlier than start")
    return pd.date_range(start, end, freq="D", tz="UTC")


def normalize_history_payload(rows: Iterable[Iterable[object]]) -> pd.DataFrame:
    """Normalize API rows, reject missing prices, and deduplicate by timestamp."""
    parsed: list[dict[str, Any]] = []
    for row in rows:
        values = list(row)
        if len(values) < 7:
            raise ValueError("history row has fewer than seven fields")
        parsed.append(
            {
                "open_time": pd.to_datetime(int(values[0]), unit="ms", utc=True),
                "open": values[1],
                "high": values[2],
                "low": values[3],
                "close": values[4],
                "base_volume": values[5],
                "quote_volume": values[6],
            }
        )
    if not parsed:
        return pd.DataFrame(columns=COLUMNS)
    frame = pd.DataFrame(parsed)
    numeric = ["open", "high", "low", "close", "base_volume", "quote_volume"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    if frame[numeric].isna().to_numpy().any() or not np.isfinite(
        frame[numeric].to_numpy(dtype=float)
    ).all():
        raise ValueError("history payload contains missing or non-finite values")
    if (frame[["open", "high", "low", "close"]] <= 0.0).to_numpy().any():
        raise ValueError("history payload contains non-positive OHLC prices")
    if (frame["high"] < frame["low"]).any():
        raise ValueError("history payload contains high below low")
    return (
        frame.loc[:, COLUMNS]
        .sort_values("open_time", kind="mergesort")
        .drop_duplicates("open_time", keep="last")
        .reset_index(drop=True)
    )


def audit_daily_coverage(index: pd.DatetimeIndex) -> dict[str, Any]:
    """Return explicit daily gaps for a candle index."""
    if len(index) == 0:
        return {
            "rows": 0,
            "start": None,
            "end": None,
            "missing_dates": [],
            "is_continuous": False,
        }
    normalized = pd.DatetimeIndex(pd.to_datetime(index, utc=True)).normalize().sort_values()
    if normalized.duplicated().any():
        raise ValueError("daily coverage index contains duplicate dates")
    expected = pd.date_range(normalized.min(), normalized.max(), freq="D", tz="UTC")
    missing = expected.difference(normalized)
    return {
        "rows": int(len(normalized)),
        "start": str(normalized.min()),
        "end": str(normalized.max()),
        "missing_dates": [str(value) for value in missing],
        "is_continuous": bool(len(missing) == 0),
    }


def _request_page(
    session: requests.Session,
    *,
    symbol: str,
    end_time: pd.Timestamp,
    limit: int,
    retries: int,
) -> list[list[object]]:
    params = {
        "symbol": symbol,
        "granularity": GRANULARITY,
        "limit": int(limit),
        "endTime": int(end_time.timestamp() * 1000),
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(ENDPOINT, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != "00000":
                raise RuntimeError(f"Bitget error for {symbol}: {payload}")
            data = payload.get("data") or []
            if not isinstance(data, list):
                raise ValueError(f"Bitget returned non-list data for {symbol}")
            return data
        except Exception as error:  # noqa: BLE001 - retry boundary
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("Bitget request failed without an error")


def fetch_history_candles(
    symbol: str,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    session: requests.Session | None = None,
    sleep_seconds: float = 0.2,
    retries: int = 5,
) -> pd.DataFrame:
    """Fetch all available UTC daily candles in the requested interval."""
    start = _parse_timestamp(start)
    end = _parse_timestamp(end)
    if end < start:
        raise ValueError("end must not be earlier than start")
    active_session = session or requests.Session()
    rows: list[list[object]] = []
    end_time = end
    previous_earliest: pd.Timestamp | None = None
    while True:
        page = _request_page(
            active_session,
            symbol=symbol,
            end_time=end_time,
            limit=200,
            retries=retries,
        )
        if not page:
            break
        rows.extend(page)
        earliest = min(pd.to_datetime(int(row[0]), unit="ms", utc=True) for row in page)
        if earliest <= start:
            break
        if previous_earliest is not None and earliest >= previous_earliest:
            raise RuntimeError(f"Bitget pagination did not advance for {symbol}")
        previous_earliest = earliest
        end_time = earliest
        if sleep_seconds > 0.0:
            time.sleep(sleep_seconds)
    frame = normalize_history_payload(rows)
    if frame.empty:
        return frame
    frame = frame.loc[(frame["open_time"] >= start) & (frame["open_time"] <= end)]
    audit = audit_daily_coverage(pd.DatetimeIndex(frame["open_time"]))
    if not audit["is_continuous"]:
        raise ValueError(f"{symbol}: spot candle coverage has gaps: {audit['missing_dates']}")
    return frame.reset_index(drop=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", default="2021-08-01")
    parser.add_argument("--end", default="2026-09-20")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()) and not args.overwrite:
        raise SystemExit(f"output directory is not empty: {output_dir}; pass --overwrite")
    output_dir = ensure_dir(output_dir)
    start = _parse_timestamp(args.start)
    end = _parse_timestamp(args.end)
    session = requests.Session()
    files: dict[str, Any] = {}
    for symbol in SYMBOLS:
        frame = fetch_history_candles(symbol, start=start, end=end, session=session)
        path = output_dir / f"{symbol}_{GRANULARITY}.csv"
        frame.to_csv(path, index=False)
        files[symbol] = {
            "path": str(path),
            "sha256": _sha256(path),
            "coverage": audit_daily_coverage(pd.DatetimeIndex(frame["open_time"])),
        }
        print(f"{symbol}: {len(frame)} rows -> {path}")
    manifest = {
        "source": ENDPOINT,
        "granularity": GRANULARITY,
        "start": str(start),
        "end": str(end),
        "files": files,
        "orders_sent": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
