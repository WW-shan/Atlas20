"""Rebuild the Binance 30-minute cache with fail-closed timestamp units.

The previous cache was produced from monthly CSV archives whose ``open_time``
column switched from milliseconds to microseconds in 2025.  Treating both as
milliseconds produced 1970 or year-58718 dates, and a later repair converted
old rows twice.  This downloader deliberately uses Binance's public kline API
instead: every page carries integer epoch-millisecond timestamps.  Values with
seconds or microseconds units are rejected rather than guessed at, and the
resulting cache is validated before any coverage manifest is published.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.config import load_config  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir, get_logger  # noqa: E402

LOGGER = get_logger(__name__)

INTERVAL = "30m"
INTERVAL_MS = 30 * 60 * 1000
PAGE_LIMIT = 1000
MIN_EPOCH_MS = int(pd.Timestamp("2017-01-01", tz="UTC").timestamp() * 1000)
MAX_EPOCH_MS = int(pd.Timestamp("2100-01-01", tz="UTC").timestamp() * 1000)
INVALID_SYMBOL_CODE = -1121
CANDLE_COLUMNS = [
    "open_time_ms",
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
]
RAW_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
]


def validate_epoch_ms(value: object) -> int:
    """Return a Binance epoch-millisecond timestamp or fail closed."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid epoch timestamp {value!r}") from exc
    if not MIN_EPOCH_MS <= parsed < MAX_EPOCH_MS:
        raise ValueError(
            "Binance open_time is outside the supported epoch-milliseconds range "
            f"({MIN_EPOCH_MS}, {MAX_EPOCH_MS}): {parsed!r}"
        )
    return parsed


def validate_candle_frame(frame: pd.DataFrame, *, pair: str) -> None:
    """Reject corrupt dates, duplicates, malformed bars and misaligned rows."""
    required = set(CANDLE_COLUMNS[1:])
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{pair}: candle frame is missing columns {sorted(missing)}")
    if frame.empty:
        return

    times = pd.to_numeric(frame["open_time_ms"], errors="coerce")
    if times.isna().any():
        raise ValueError(f"{pair}: non-numeric open_time_ms")
    times_int = times.astype("int64")
    if (times_int < MIN_EPOCH_MS).any() or (times_int >= MAX_EPOCH_MS).any():
        minimum = pd.to_datetime(int(times_int.min()), unit="ms", utc=True)
        raise ValueError(f"{pair}: invalid candle date {minimum}; this is the 1970/unit-corruption pattern")
    if times_int.duplicated().any():
        raise ValueError(f"{pair}: duplicate open_time_ms rows")
    if not times_int.is_monotonic_increasing:
        raise ValueError(f"{pair}: open_time_ms is not sorted")
    if (times_int % INTERVAL_MS != 0).any():
        raise ValueError(f"{pair}: open_time_ms is not aligned to a 30-minute boundary")

    for column in ("open", "high", "low", "close", "volume", "quote_volume"):
        values = pd.to_numeric(frame[column], errors="coerce")
        if not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"{pair}: non-finite values in {column}")
    prices = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    if (prices <= 0.0).any().any():
        raise ValueError(f"{pair}: non-positive OHLC value")
    if (prices["high"] < prices[["open", "close"]].max(axis=1)).any():
        raise ValueError(f"{pair}: high is below open/close")
    if (prices["low"] > prices[["open", "close"]].min(axis=1)).any():
        raise ValueError(f"{pair}: low is above open/close")


def normalize_klines(rows: list[list[Any]], pair: str) -> pd.DataFrame:
    """Convert Binance kline payload rows into a canonical timestamp frame."""
    if not rows:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    raw = pd.DataFrame([row[:12] for row in rows], columns=RAW_COLUMNS)
    frame = pd.DataFrame(
        {
            "open_time_ms": [validate_epoch_ms(value) for value in raw["open_time"]],
            "open": raw["open"],
            "high": raw["high"],
            "low": raw["low"],
            "close": raw["close"],
            "volume": raw["volume"],
            "quote_volume": raw["quote_volume"],
        }
    )
    frame["open_time"] = pd.to_datetime(frame["open_time_ms"], unit="ms", utc=True)
    for column in ("open", "high", "low", "close", "volume", "quote_volume"):
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    frame = frame[CANDLE_COLUMNS]
    validate_candle_frame(frame, pair=pair)
    return frame


def _fetch_page(
    session: requests.Session,
    base_url: str,
    pair: str,
    start_ms: int,
    end_ms: int,
    *,
    retries: int = 4,
) -> list[list[Any]] | None:
    params = {
        "symbol": pair,
        "interval": INTERVAL,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": PAGE_LIMIT,
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(f"{base_url}/klines", params=params, timeout=30)
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(1.0 + attempt)
            continue
        if response.ok:
            payload = response.json()
            if not isinstance(payload, list):
                raise RuntimeError(f"Binance returned a non-list kline payload for {pair}")
            return payload
        try:
            code = response.json().get("code")
        except (ValueError, AttributeError):
            code = None
        if response.status_code == 400 and code == INVALID_SYMBOL_CODE:
            return None
        last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"Binance 30m klines failed for {pair}: {last_error}")


def download_pair(
    session: requests.Session,
    base_url: str,
    pair: str,
    start_ms: int,
    end_ms: int,
    *,
    pause_seconds: float,
) -> pd.DataFrame | None:
    """Download one pair in [start_ms, end_ms), or None when unlisted."""
    cursor = start_ms
    rows: list[list[Any]] = []
    while cursor < end_ms:
        page = _fetch_page(session, base_url, pair, cursor, end_ms - 1)
        if page is None:
            return None
        if not page:
            break
        normalized = normalize_klines(page, pair)
        rows.extend(page)
        next_cursor = int(normalized["open_time_ms"].iloc[-1]) + INTERVAL_MS
        if next_cursor <= cursor:
            raise RuntimeError(f"{pair}: kline pagination did not advance at {cursor}")
        cursor = next_cursor
        time.sleep(pause_seconds)

    frame = normalize_klines(rows, pair)
    if frame.empty:
        return frame
    frame = frame[(frame["open_time_ms"] >= start_ms) & (frame["open_time_ms"] < end_ms)]
    return frame.drop_duplicates("open_time_ms", keep="last").sort_values("open_time_ms").reset_index(drop=True)


def download_coin(
    session: requests.Session,
    base_url: str,
    pairs: list[str],
    start_ms: int,
    end_ms: int,
    *,
    pause_seconds: float,
) -> pd.DataFrame | None:
    frames: list[pd.DataFrame] = []
    for pair in pairs:
        frame = download_pair(
            session,
            base_url,
            pair,
            start_ms,
            end_ms,
            pause_seconds=pause_seconds,
        )
        if frame is not None and not frame.empty:
            frames.append(frame.assign(pair=pair))
    if not frames:
        return None
    combined = pd.concat(frames, ignore_index=True).sort_values("open_time_ms")
    combined = combined.drop_duplicates("open_time_ms", keep="last").reset_index(drop=True)
    validate_candle_frame(combined, pair="+".join(pairs))
    return combined


def _coverage_entry(frame: pd.DataFrame, pairs: list[str], file_name: str) -> dict[str, object]:
    times = frame["open_time_ms"].astype("int64")
    gaps_ms = times.diff().dropna()
    missing_bars = int(((gaps_ms // INTERVAL_MS) - 1).clip(lower=0).sum())
    return {
        "pair": pairs[-1],
        "pairs": pairs,
        "file": file_name,
        "available": True,
        "rows": int(len(frame)),
        "first": str(frame["open_time"].min()),
        "last": str(frame["open_time"].max()),
        "missing_bars": missing_bars,
        "gap_count": int((gaps_ms > INTERVAL_MS).sum()),
        "max_gap_hours": float(gaps_ms.max() / 3_600_000) if not gaps_ms.empty else 0.0,
    }


def _month_range(start: pd.Timestamp, end: pd.Timestamp) -> list[str]:
    if start >= end:
        raise ValueError("start must be before end")
    return [period.strftime("%Y-%m") for period in pd.period_range(start, end - pd.Timedelta(days=1), freq="M")]


def _build_one(
    *,
    coin_id: str,
    symbol: str,
    pairs: list[str],
    base_url: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    pause_seconds: float,
) -> tuple[str, dict[str, object], pd.DataFrame | None, str]:
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    session = requests.Session()
    try:
        frame = download_coin(
            session,
            base_url,
            pairs,
            start_ms,
            end_ms,
            pause_seconds=pause_seconds,
        )
    finally:
        session.close()
    if frame is None or frame.empty:
        return coin_id, {"pair": pairs[-1], "pairs": pairs, "available": False, "rows": 0}, None, symbol

    file_name = f"{'__'.join(pairs)}.csv"
    return coin_id, _coverage_entry(frame, pairs, file_name), frame, symbol


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--members",
        type=Path,
        required=True,
        help="CSV with coin_id and symbol columns; use --only to bound the research universe.",
    )
    parser.add_argument("--only", default="", help="Comma-separated coin ids to rebuild.")
    parser.add_argument("--start-month", default="2022-01")
    parser.add_argument("--end-month", default="2026-09", help="Inclusive final month.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/binance_30m"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    parser.add_argument("--force", action="store_true", help="Delete existing CSV and coverage files first.")
    parser.add_argument(
        "--coin-pairs",
        default='{"the-open-network": ["TONUSDT", "GRAMUSDT"]}',
        help="JSON map of coin_id to pairs traded in chronological order.",
    )
    args = parser.parse_args(argv)

    configure_logging("INFO")
    config = load_config(args.config)
    base_url = config.providers.binance.base_url.rstrip("/")
    quote = config.providers.binance.quote_currency.upper()
    aliases = {str(key).upper(): str(value) for key, value in config.providers.binance.pair_aliases.items()}
    coin_pairs = {
        str(key): [str(pair) for pair in value]
        for key, value in json.loads(args.coin_pairs).items()
    }
    members = pd.read_csv(args.members)
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    if only:
        members = members[members["coin_id"].astype(str).isin(only)]
    if members.empty:
        raise SystemExit("No member rows selected")

    start = pd.Timestamp(args.start_month + "-01", tz="UTC")
    end = pd.Timestamp(args.end_month + "-01", tz="UTC") + pd.offsets.MonthBegin(1)
    _month_range(start, end)

    output_dir = args.output_dir
    if output_dir.exists() and any(output_dir.glob("*.csv")):
        if not args.force:
            raise SystemExit(f"{output_dir} already contains candle CSVs; pass --force to rebuild from scratch")
        for path in output_dir.glob("*.csv"):
            path.unlink()
    ensure_dir(output_dir)
    coverage_path = output_dir / "coverage.json"
    if args.force and coverage_path.exists():
        coverage_path.unlink()

    tasks = []
    seen: set[str] = set()
    for member in members.itertuples(index=False):
        coin_id = str(member.coin_id)
        if coin_id in seen:
            continue
        seen.add(coin_id)
        symbol = str(member.symbol).upper()
        pairs = coin_pairs.get(coin_id) or [aliases.get(symbol, f"{symbol}{quote}")]
        tasks.append((coin_id, symbol, pairs))

    coverage: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(
                _build_one,
                coin_id=coin_id,
                symbol=symbol,
                pairs=pairs,
                base_url=base_url,
                start=start,
                end=end,
                pause_seconds=args.pause_seconds,
            ): coin_id
            for coin_id, symbol, pairs in tasks
        }
        for future in as_completed(futures):
            coin_id, entry, frame, symbol = future.result()
            coverage[coin_id] = entry
            if frame is None:
                LOGGER.warning("No Binance 30m candles for %s (%sUSDT)", coin_id, symbol)
                continue
            file_name = str(entry["file"])
            path = output_dir / file_name
            temporary = path.with_suffix(path.suffix + ".tmp")
            frame.to_csv(temporary, index=False)
            temporary.replace(path)
            LOGGER.info(
                "%s (%s): %s rows, %s -> %s",
                coin_id,
                entry["pair"],
                entry["rows"],
                entry["first"],
                entry["last"],
            )

    coverage_path.write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    available = sum(bool(item["available"]) for item in coverage.values())
    print(f"Binance 30m candles for {available}/{len(coverage)} coins written to {output_dir}")


if __name__ == "__main__":
    main()
