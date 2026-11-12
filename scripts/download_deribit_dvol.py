"""Download Deribit's public BTC DVOL daily OHLC history.

DVOL is an independent options-market state series. This script is research
data acquisition only: it does not use private API credentials, execute code
from the response, or place orders.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests

DVOL_URL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
DEFAULT_OUTPUT = Path("data/raw/deribit_dvol/BTC_DVOL_1D.csv")


def parse_dvol_rows(rows: list[list[Any]]) -> pd.DataFrame:
    """Normalize Deribit DVOL rows to one validated UTC row per day."""
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        try:
            timestamp = int(row[0])
        except (TypeError, ValueError):
            raise ValueError("DVOL row contains a malformed timestamp") from None
        raw_values = list(row[1:5])
        if any(value is None or value == "" for value in raw_values):
            raise ValueError("DVOL row contains missing or non-finite OHLC")
        try:
            values = [float(value) for value in raw_values]
        except (TypeError, ValueError):
            raise ValueError("DVOL row contains a malformed OHLC value") from None
        if not all(pd.notna(value) and abs(value) != float("inf") for value in values):
            raise ValueError("DVOL row contains missing or non-finite OHLC")
        if any(value <= 0.0 for value in values):
            raise ValueError("DVOL row contains non-positive OHLC")
        parsed.append(
            {
                "ts": timestamp,
                "date": pd.to_datetime(timestamp, unit="ms", utc=True),
                "open": values[0],
                "high": values[1],
                "low": values[2],
                "close": values[3],
            }
        )
    if not parsed:
        raise ValueError("DVOL response has no usable rows")
    frame = pd.DataFrame(parsed).drop_duplicates("ts", keep="last").sort_values("ts")
    frame["date"] = pd.to_datetime(frame["ts"], unit="ms", utc=True)
    return frame[["date", "open", "high", "low", "close"]].reset_index(drop=True)


def fetch_dvol_rows(
    session: requests.Session,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    timeout_seconds: float = 30.0,
) -> list[list[Any]]:
    """Page backward through Deribit's 1,000-row API response limit."""
    start_ts = int(pd.Timestamp(start).timestamp() * 1000)
    end_ts = int(pd.Timestamp(end).timestamp() * 1000)
    rows: dict[int, list[Any]] = {}
    for _ in range(20):
        response = session.get(
            DVOL_URL,
            params={
                "currency": "BTC",
                "start_timestamp": start_ts,
                "end_timestamp": end_ts,
                "resolution": "1D",
            },
            timeout=timeout_seconds,
        )
        if not bool(getattr(response, "ok", False)):
            raise RuntimeError(
                f"Deribit DVOL HTTP {getattr(response, 'status_code', 'unknown')}"
            )
        payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise RuntimeError("Deribit DVOL response has no result object")
        batch = result.get("data")
        if not isinstance(batch, list):
            raise RuntimeError("Deribit DVOL result.data is not a list")
        if not batch:
            break
        for row in batch:
            if isinstance(row, (list, tuple)) and row:
                rows[int(row[0])] = list(row)
        earliest = min(int(row[0]) for row in batch if isinstance(row, (list, tuple)))
        if earliest <= start_ts:
            break
        end_ts = earliest - 1
    if not rows:
        raise RuntimeError("Deribit DVOL returned no rows")
    return [rows[key] for key in sorted(rows)]


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--start", default="2021-03-24")
    parser.add_argument("--end", default=pd.Timestamp.now(tz="UTC").date().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"{args.output} exists; pass --overwrite to refresh it")

    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
    with requests.Session() as session:
        rows = fetch_dvol_rows(session, start=start, end=end, timeout_seconds=args.timeout_seconds)
    frame = parse_dvol_rows(rows)
    frame = frame.loc[(frame["date"] >= start) & (frame["date"] <= end)].reset_index(drop=True)
    if frame.empty:
        raise SystemExit("no DVOL rows in the requested window")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(args.output)
    manifest = {
        "source": DVOL_URL,
        "currency": "BTC",
        "resolution": "1D",
        "start": str(frame["date"].min()),
        "end": str(frame["date"].max()),
        "rows": int(len(frame)),
        "sha256": _sha256(args.output),
        "retrieved_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    args.output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output} ({len(frame)} rows)")


if __name__ == "__main__":
    main()
