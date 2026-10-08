"""Download Binance 1-hour candles for every coin that has been in the Top20.

The production backtest fills at the daily close the signal was computed on.
Live orders go out only after CoinMarketCap publishes that close and the
02:30 UTC refresh finishes, so realistic fills sit a few hours into the next
UTC day.  Hourly candles let the backtest split each execution day at the
fill time.  Candles come from Binance's public market-data mirror
(``data-api.binance.vision``, the same venue the daily cross-check uses) and
are cached under ``data/raw/binance_1h/`` as one CSV per pair.  Coins
Binance does not list (Hyperliquid, OKB and other exchange tokens) can be
fetched from Gate.io instead with ``--venue gate``: its API only reaches back
10,000 hourly points, so older months come from Gate's public monthly archive
(``download.gatedata.org``).  Gate reuses tickers (its HYPE_USDT was a
different token in 2024), which the backtest's open-versus-prior-close check
catches.  A coin neither venue lists is recorded as unavailable and the
backtest brackets its fill time (next close vs. signal close).
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys
import time

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.config import load_config  # noqa: E402
from atlas20.logging_utils import configure_logging, get_logger  # noqa: E402

LOGGER = get_logger(__name__)
_HOUR_MS = 3_600_000
_PAGE_LIMIT = 1000
_INVALID_SYMBOL_CODE = -1121
CANDLE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "quote_volume"]
GATE_ARCHIVE_URL = "https://download.gatedata.org/spot/candlesticks_1h/{month}/{pair}-{month}.csv.gz"
# Gate's archive rows are timestamp, volume, close, high, low, open.
GATE_ARCHIVE_COLUMNS = ["open_time", "volume", "close", "high", "low", "open"]
_GATE_API_POINTS = 10_000
_GATE_API_PAGE = 1000


def _fetch_page(
    session: requests.Session,
    base_url: str,
    pair: str,
    start_ms: int,
    end_ms: int,
    *,
    retries: int = 4,
) -> list[list[object]] | None:
    """One klines page, or None when the venue does not list the pair."""
    params = {
        "symbol": pair,
        "interval": "1h",
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": _PAGE_LIMIT,
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
            return list(response.json())
        try:
            code = response.json().get("code")
        except ValueError:
            code = None
        if response.status_code == 400 and code == _INVALID_SYMBOL_CODE:
            return None
        last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"Binance 1h klines failed for {pair}: {last_error}")


def download_pair(
    session: requests.Session,
    base_url: str,
    pair: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    pause_seconds: float,
) -> pd.DataFrame | None:
    """All 1h candles for ``pair`` in [start, end), or None if not listed."""
    cursor = int(start.timestamp() * 1000)
    stop = int(end.timestamp() * 1000)
    rows: list[list[object]] = []
    while cursor < stop:
        page = _fetch_page(session, base_url, pair, cursor, stop - 1)
        if page is None:
            return None
        if not page:
            break
        rows.extend(page)
        next_cursor = int(page[-1][0]) + _HOUR_MS
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(pause_seconds)
    if not rows:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    frame = pd.DataFrame([row[:6] + [row[7]] for row in rows], columns=CANDLE_COLUMNS)
    frame["open_time"] = pd.to_datetime(frame["open_time"].astype("int64"), unit="ms", utc=True)
    for column in CANDLE_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)


def download_coin(
    session: requests.Session,
    base_url: str,
    pairs: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    pause_seconds: float,
) -> pd.DataFrame | None:
    """Splice every pair a coin has traded under (e.g. a ticker rebrand).

    Later pairs win on overlapping hours; None when no pair is listed.
    """
    frames = []
    for pair in pairs:
        frame = download_pair(session, base_url, pair, start, end, pause_seconds=pause_seconds)
        if frame is not None and not frame.empty:
            frames.append(frame)
    if not frames:
        return None
    spliced = pd.concat(frames, ignore_index=True)
    return spliced.drop_duplicates("open_time", keep="last").sort_values("open_time").reset_index(drop=True)


def _get_with_retries(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, object] | None = None,
    retries: int = 4,
    timeout: float = 60.0,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(1.0 + attempt)
            continue
        if response.ok or response.status_code in (400, 404):
            return response
        last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"Gate.io request failed for {url}: {last_error}")


def _normalized_candles(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.reindex(columns=CANDLE_COLUMNS)
    for column in CANDLE_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.drop_duplicates("open_time", keep="first").sort_values("open_time").reset_index(drop=True)


def _gate_archive_month(session: requests.Session, pair: str, month: pd.Period) -> pd.DataFrame | None:
    """One month from Gate's archive, or None when the archive has no file."""
    label = month.strftime("%Y%m")
    response = _get_with_retries(session, GATE_ARCHIVE_URL.format(month=label, pair=pair))
    if response.status_code == 404:
        return None
    if not response.ok:
        raise RuntimeError(f"Gate.io archive answered HTTP {response.status_code} for {pair} {label}")
    frame = pd.read_csv(io.BytesIO(response.content), compression="gzip", header=None, names=GATE_ARCHIVE_COLUMNS)
    frame["open_time"] = pd.to_datetime(frame["open_time"].astype("int64"), unit="s", utc=True)
    return frame


def _gate_api_window(
    session: requests.Session,
    base_url: str,
    pair: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    pause_seconds: float,
) -> pd.DataFrame | None:
    """Hourly candles in [start, end) from Gate's API; None if it lacks the pair."""
    rows: list[list[object]] = []
    cursor = start
    while cursor < end:
        stop = min(cursor + pd.Timedelta(hours=_GATE_API_PAGE - 1), end - pd.Timedelta(hours=1))
        response = _get_with_retries(
            session,
            f"{base_url}/spot/candlesticks",
            params={
                "currency_pair": pair,
                "interval": "1h",
                "from": int(cursor.timestamp()),
                "to": int(stop.timestamp()),
            },
            timeout=30.0,
        )
        if response.status_code == 400:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("label") == "INVALID_CURRENCY_PAIR":
                return None
            raise RuntimeError(f"Gate.io API rejected {pair} from {cursor}: {payload}")
        rows.extend(list(response.json()))
        cursor = stop + pd.Timedelta(hours=1)
        time.sleep(pause_seconds)
    # API rows are t, quote volume, close, high, low, open, base volume, closed.
    frame = pd.DataFrame(
        [[row[0], row[5], row[3], row[4], row[2], row[6], row[1]] for row in rows],
        columns=CANDLE_COLUMNS,
    )
    frame["open_time"] = pd.to_datetime(frame["open_time"].astype("int64"), unit="s", utc=True)
    return frame


def download_gate_pair(
    session: requests.Session,
    base_url: str,
    pair: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    now: pd.Timestamp,
    pause_seconds: float,
) -> pd.DataFrame | None:
    """All Gate.io 1h candles for ``pair`` in [start, end), or None if none exist.

    The monthly archive comes first; the API only fills the hours after the
    last archived one, within its 10,000-point reach.  Archived hours win over
    API hours for the same timestamp.
    """
    frames: list[pd.DataFrame] = []
    for month in pd.period_range(start.tz_convert(None), (end - pd.Timedelta(hours=1)).tz_convert(None), freq="M"):
        frame = _gate_archive_month(session, pair, month)
        if frame is not None and not frame.empty:
            frames.append(frame)
    archived_until = max((frame["open_time"].max() for frame in frames), default=None)
    api_start = start if archived_until is None else max(start, archived_until + pd.Timedelta(hours=1))
    api_start = max(api_start, now.floor("h") - pd.Timedelta(hours=_GATE_API_POINTS - 1))
    if api_start < end:
        recent = _gate_api_window(session, base_url, pair, api_start, end, pause_seconds=pause_seconds)
        if recent is not None and not recent.empty:
            frames.append(recent)
    if not frames:
        return None
    candles = _normalized_candles(pd.concat(frames, ignore_index=True))
    candles = candles[(candles["open_time"] >= start) & (candles["open_time"] < end)]
    return candles.reset_index(drop=True) if not candles.empty else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--members",
        type=Path,
        required=True,
        help="CSV with coin_id and symbol columns (every coin that entered the Top20).",
    )
    parser.add_argument("--start", default="2021-12-25")
    parser.add_argument("--end", default=None, help="Exclusive UTC end; defaults to the current hour.")
    parser.add_argument("--pause-seconds", type=float, default=0.1)
    parser.add_argument(
        "--coin-pairs",
        default='{"the-open-network": ["TONUSDT", "GRAMUSDT"]}',
        help="JSON map of coin_id to the pairs it traded under, oldest first "
        "(Toncoin was renamed Gram/GRAM in 2026).",
    )
    parser.add_argument("--only", default="", help="Comma-separated coin ids to (re)download.")
    parser.add_argument(
        "--venue",
        choices=("binance", "gate"),
        default="binance",
        help="gate fills coins Binance does not list; it keeps an existing Binance entry otherwise.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/binance_1h"))
    args = parser.parse_args()

    configure_logging("INFO")
    config = load_config(args.config)
    base_url = config.providers.binance.base_url.rstrip("/")
    quote = config.providers.binance.quote_currency.upper()
    aliases = {str(key).upper(): str(value) for key, value in config.providers.binance.pair_aliases.items()}
    coin_pairs = {str(key): [str(pair) for pair in value] for key, value in json.loads(args.coin_pairs).items()}
    members = pd.read_csv(args.members)
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    if only:
        members = members[members["coin_id"].astype(str).isin(only)]
    start = pd.Timestamp(args.start, tz="UTC")
    end = (
        pd.Timestamp(args.end, tz="UTC")
        if args.end
        else pd.Timestamp.now(tz="UTC").floor("h")
    )
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = output_dir / "coverage.json"
    coverage: dict[str, dict[str, object]] = (
        json.loads(coverage_path.read_text(encoding="utf-8")) if only and coverage_path.exists() else {}
    )

    session = requests.Session()
    if args.venue == "gate":
        gate = config.providers.gateio
        gate_aliases = {str(key).upper(): str(value) for key, value in gate.pair_aliases.items()}
        now = pd.Timestamp.now(tz="UTC")
        for member in members.itertuples(index=False):
            coin_id = str(member.coin_id)
            symbol = str(member.symbol).upper()
            existing = coverage.get(coin_id, {})
            if existing.get("available") and existing.get("venue", "binance") == "binance":
                LOGGER.info("%s already has Binance candles; skipping Gate.io", coin_id)
                continue
            pair = gate_aliases.get(symbol, f"{symbol}_{gate.quote_currency.upper()}")
            frame = download_gate_pair(
                session,
                gate.base_url.rstrip("/"),
                pair,
                start,
                end,
                now=now,
                pause_seconds=args.pause_seconds,
            )
            if frame is None:
                coverage[coin_id] = {**existing, "available": False, "gate_pair": pair, "gate_available": False}
                LOGGER.warning("No Gate.io 1h candles for %s (%s)", coin_id, pair)
                continue
            file_name = f"gate_{pair}.csv"
            frame.to_csv(output_dir / file_name, index=False)
            coverage[coin_id] = {
                "venue": "gate",
                "pair": pair,
                "file": file_name,
                "available": True,
                "rows": int(len(frame)),
                "first": frame["open_time"].min().isoformat(),
                "last": frame["open_time"].max().isoformat(),
            }
            LOGGER.info("%s (Gate.io %s): %s candles", coin_id, pair, len(frame))
        coverage_path.write_text(json.dumps(coverage, indent=2), encoding="utf-8")
        available = sum(1 for item in coverage.values() if item.get("available"))
        print(f"Hourly candles for {available}/{len(coverage)} coins listed in {coverage_path}")
        return

    for member in members.itertuples(index=False):
        coin_id = str(member.coin_id)
        symbol = str(member.symbol).upper()
        pairs = coin_pairs.get(coin_id) or [aliases.get(symbol, f"{symbol}{quote}")]
        pair = pairs[-1]
        frame = download_coin(session, base_url, pairs, start, end, pause_seconds=args.pause_seconds)
        if frame is None or frame.empty:
            coverage[coin_id] = {"pair": pair, "pairs": pairs, "available": False, "rows": 0}
            LOGGER.warning("No Binance 1h candles for %s (%s)", coin_id, ", ".join(pairs))
            continue
        frame.to_csv(output_dir / f"{pair}.csv", index=False)
        coverage[coin_id] = {
            "pair": pair,
            "pairs": pairs,
            "available": True,
            "rows": int(len(frame)),
            "first": frame["open_time"].min().isoformat(),
            "last": frame["open_time"].max().isoformat(),
        }
        LOGGER.info("%s (%s): %s candles", coin_id, ", ".join(pairs), len(frame))
    coverage_path.write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    available = sum(1 for item in coverage.values() if item["available"])
    print(f"Binance 1h candles for {available}/{len(coverage)} coins written to {output_dir}")


if __name__ == "__main__":
    main()
