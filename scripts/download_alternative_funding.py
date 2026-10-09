"""Download OKX / Bybit perpetual funding history as an independent funding check.

Bitget only publishes about 90 days of funding, so the 2022+ funding cost has
to come from a proxy.  Two more venues with long public history let the
*venue premium* be measured across the whole sample instead of assumed, which
is what the derivatives funding gate needs.  The script is resumable: one CSV
per coin plus a state file.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir, get_logger  # noqa: E402

LOGGER = get_logger(__name__)
_HEADERS = {"User-Agent": "atlas20-research/0.1"}
_OKX_URL = "https://www.okx.com/api/v5/public/funding-rate-history"
_BYBIT_URL = "https://api.bybit.com/v5/market/funding/history"
_EIGHT_HOURS_MS = 8 * 3_600_000


def _get(session: requests.Session, url: str, params: dict[str, Any], *, retries: int = 4) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, headers=_HEADERS, timeout=25)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - network retries are the point
            last = exc
            time.sleep(1.5 * (2**attempt))
    raise RuntimeError(f"request failed for {url} {params}: {last}")


def _okx_history(
    session: requests.Session,
    inst_id: str,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    pause_seconds: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cursor: int | None = None
    for _ in range(400):
        params: dict[str, Any] = {"instId": inst_id, "limit": 100}
        if cursor is not None:
            params["after"] = str(cursor)
        payload = _get(session, _OKX_URL, params)
        data = payload.get("data") or []
        if not data:
            break
        for row in data:
            rows.append({"funding_time": int(row["fundingTime"]), "funding_rate": float(row["fundingRate"])})
        oldest = min(int(row["fundingTime"]) for row in data)
        if oldest <= int(start.timestamp() * 1000):
            break
        cursor = oldest
        time.sleep(pause_seconds)
    if not rows:
        return pd.DataFrame(columns=["funding_time", "funding_rate"])
    frame = pd.DataFrame(rows).drop_duplicates("funding_time").sort_values("funding_time")
    frame["funding_time"] = pd.to_datetime(frame["funding_time"], unit="ms", utc=True)
    return frame[(frame["funding_time"] >= start) & (frame["funding_time"] < end)].reset_index(drop=True)


def _bybit_history(
    session: requests.Session,
    symbol: str,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    pause_seconds: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cursor = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    for _ in range(200):
        window_end = min(cursor + 200 * _EIGHT_HOURS_MS, end_ms)
        payload = _get(
            session,
            _BYBIT_URL,
            {
                "category": "linear",
                "symbol": symbol,
                "startTime": cursor,
                "endTime": window_end,
                "limit": 200,
            },
        )
        data = (payload.get("result") or {}).get("list") or []
        for row in data:
            rows.append(
                {
                    "funding_time": int(row["fundingRateTimestamp"]),
                    "funding_rate": float(row["fundingRate"]),
                }
            )
        if window_end >= end_ms:
            break
        cursor = window_end + 1
        time.sleep(pause_seconds)
    if not rows:
        return pd.DataFrame(columns=["funding_time", "funding_rate"])
    frame = pd.DataFrame(rows).drop_duplicates("funding_time").sort_values("funding_time")
    frame["funding_time"] = pd.to_datetime(frame["funding_time"], unit="ms", utc=True)
    return frame[(frame["funding_time"] >= start) & (frame["funding_time"] < end)].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--venue", choices=("okx", "bybit"), required=True)
    parser.add_argument("--symbol-map", type=Path, default=Path("data/raw/bitget_derivatives/symbol_map.csv"))
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2026-09-21")
    parser.add_argument("--only", default="")
    parser.add_argument("--pause-seconds", type=float, default=0.2)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    configure_logging("INFO")
    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    symbol_map = pd.read_csv(args.symbol_map)
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    if only:
        symbol_map = symbol_map[symbol_map["coin_id"].astype(str).isin(only)]

    output_dir = ensure_dir(args.output_dir / args.venue)
    state_path = args.output_dir / f"{args.venue}_state.json"
    state: dict[str, dict[str, Any]] = (
        json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    )
    session = requests.Session()
    written = 0
    for record in symbol_map.to_dict("records"):
        coin_id = str(record["coin_id"])
        ticker = str(record["panel_symbol"]).upper()
        path = output_dir / f"{coin_id}.csv"
        if coin_id in state and state[coin_id].get("status") == "complete" and path.exists():
            continue
        try:
            if args.venue == "okx":
                frame = _okx_history(
                    session, f"{ticker}-USDT-SWAP", start=start, end=end, pause_seconds=args.pause_seconds
                )
            else:
                frame = _bybit_history(
                    session, f"{ticker}USDT", start=start, end=end, pause_seconds=args.pause_seconds
                )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("%s %s failed: %s", args.venue, coin_id, exc)
            state[coin_id] = {"status": "error", "reason": str(exc)}
            continue
        if frame.empty:
            state[coin_id] = {"status": "missing"}
            LOGGER.info("%s %s: no rows", args.venue, coin_id)
            continue
        frame.to_csv(path, index=False)
        written += 1
        state[coin_id] = {
            "status": "complete",
            "rows": int(len(frame)),
            "first": str(frame["funding_time"].min()),
            "last": str(frame["funding_time"].max()),
        }
        LOGGER.info("%s %s: %d rows %s → %s", args.venue, coin_id, len(frame), state[coin_id]["first"], state[coin_id]["last"])

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    complete = sum(1 for item in state.values() if item.get("status") == "complete")
    print(f"{args.venue}: {complete} coins with funding history ({written} written this run)")


if __name__ == "__main__":
    main()
