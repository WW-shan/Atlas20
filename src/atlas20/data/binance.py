"""Binance exchange-candle client used as a second independent venue.

Gate.io is the preferred venue vote, but one venue cannot corroborate itself.
When CoinMarketCap disagrees with Gate.io there is no way to tell which side is
wrong without a second order book.

``api.binance.com`` (and its ``api1-4`` mirrors) answer HTTP 451 from this
host, and ``api.binance.us`` is a different, much thinner market: of the 73
panel pairs it quoted, 51 traded under $10k a day and 27 under $1k, so its
"close" was frequently a stale print rather than a market (it reported ENJ
14.25% away from CMC purely from illiquidity).  ``data-api.binance.vision`` is
Binance's official public market-data mirror: same venue, same books, no key,
no geo-block.

Like the Gate.io client this never rewrites a panel value: it only supplies an
independent vote over the requested window.  A symbol the venue does not carry
(HT and CEL answer ``Invalid symbol``) yields an empty frame, so the
adjudicator can fall through to another provider instead of aborting the
refresh for one delisted ticker.  Days below the configured dollar-volume floor
are dropped for the same reason: a thin print is not evidence about the current
price, so it must read as "this venue cannot certify today" rather than as a
disagreement with CoinMarketCap.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from atlas20.config import BinanceConfig
from atlas20.logging_utils import get_logger

BINANCE_COLUMNS = ["date", "binance_price", "binance_volume_usd"]

# Binance caps a klines page at 1000 rows and asks for millisecond timestamps.
_PAGE_LIMIT = 1000
_DAY_MS = 86_400_000
# Stop paging well before a bad cursor could loop forever.
_MAX_PAGES = 40
# Returned with HTTP 400 when the venue has no such pair.
_INVALID_SYMBOL_CODE = -1121


class BinanceClient:
    """Cache-aware client for Binance spot daily klines."""

    def __init__(self, config: BinanceConfig, raw_dir: Path) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.raw_dir = raw_dir / "binance"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()

    def _cache_path(self, pair: str, start: str, end: str) -> Path:
        directory = self.raw_dir / "candles"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{pair}_{start}_{end}.json"

    def resolve_pair(self, symbol: str) -> str:
        """Return the configured Binance pair for a ticker."""
        upper = symbol.upper()
        alias = self.config.pair_aliases.get(upper) or self.config.pair_aliases.get(symbol)
        if alias:
            return str(alias)
        return f"{upper}{self.config.quote_currency.upper()}"

    def _request(self, params: dict[str, Any]) -> list[Any] | None:
        """Return one klines page, or None when the venue has no such pair."""
        url = f"{self.base_url}/klines"
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            response = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
            if response.ok:
                payload = response.json()
                if self.config.rate_limit_seconds > 0:
                    time.sleep(self.config.rate_limit_seconds)
                return payload if isinstance(payload, list) else []
            if response.status_code == 400:
                payload = response.json()
                if isinstance(payload, dict) and payload.get("code") == _INVALID_SYMBOL_CODE:
                    # Not an error condition: the venue simply does not list it.
                    return None
                raise ValueError(f"Binance rejected the request: {payload}")
            if response.status_code not in {418, 429, 500, 502, 503, 504}:
                response.raise_for_status()
            last_error = requests.HTTPError(
                f"Binance request failed with status {response.status_code}: {response.text[:200]}",
                response=response,  # type: ignore[arg-type]
            )
            delay = max(self.config.rate_limit_seconds, self.config.retry_backoff_seconds * (2**attempt))
            self.logger.warning(
                "Binance retry %s/%s after status %s",
                attempt + 1,
                self.config.max_retries,
                response.status_code,
            )
            time.sleep(delay)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Binance request failed unexpectedly")

    def _fetch_range(self, pair: str, start_ms: int, end_ms: int) -> list[Any]:
        """Walk ``[start_ms, end_ms]`` in pages, oldest first."""
        rows: list[Any] = []
        cursor = start_ms
        for _ in range(_MAX_PAGES):
            if cursor > end_ms:
                break
            page = self._request(
                {
                    "symbol": pair,
                    "interval": "1d",
                    "startTime": cursor,
                    "endTime": end_ms,
                    "limit": _PAGE_LIMIT,
                }
            )
            if page is None:
                return []
            if not page:
                break
            rows.extend(page)
            if len(page) < _PAGE_LIMIT:
                break
            try:
                last_open = int(page[-1][0])
            except (TypeError, ValueError, IndexError):
                break
            next_cursor = last_open + _DAY_MS
            if next_cursor <= cursor:
                break
            cursor = next_cursor
        return rows

    def _frame_from_payload(self, payload: object, *, pair: str = "") -> pd.DataFrame:
        if not isinstance(payload, list) or not payload:
            return pd.DataFrame(columns=BINANCE_COLUMNS)
        rows: list[dict[str, Any]] = []
        for row in payload:
            # [openTime, open, high, low, close, volume, closeTime, quoteVolume, ...]
            if not isinstance(row, (list, tuple)) or len(row) < 8:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(int(row[0]), unit="ms", utc=True).tz_localize(None).normalize(),
                    "binance_price": row[4],
                    "binance_volume_usd": row[7],
                }
            )
        if not rows:
            return pd.DataFrame(columns=BINANCE_COLUMNS)
        frame = pd.DataFrame(rows)
        frame["binance_price"] = pd.to_numeric(frame["binance_price"], errors="coerce")
        frame["binance_volume_usd"] = pd.to_numeric(frame["binance_volume_usd"], errors="coerce")
        frame = frame.dropna(subset=["date", "binance_price"])
        frame = frame[frame["binance_price"] > 0]
        frame = self._apply_liquidity_floor(frame, pair=pair)
        return (
            frame[BINANCE_COLUMNS]
            .sort_values("date")
            .drop_duplicates("date", keep="last")
            .reset_index(drop=True)
        )

    def _apply_liquidity_floor(self, frame: pd.DataFrame, *, pair: str) -> pd.DataFrame:
        """Drop days whose dollar volume is too thin to be a real print.

        `api.binance.us` was retired precisely because its thin pairs (ENS at
        $1.74/day, FLOW at $2.71/day) produced closes that disagreed with
        CoinMarketCap by double digits without anything being wrong with the
        primary feed.  A thin day is dropped instead of counted, so the venue
        reports "cannot certify this day" rather than a false disagreement.
        """
        floor = float(self.config.min_daily_dollar_volume)
        if floor <= 0 or frame.empty:
            return frame
        volume = frame["binance_volume_usd"].fillna(0.0)
        kept = frame[volume >= floor]
        dropped = len(frame) - len(kept)
        if dropped:
            self.logger.info(
                "Binance %s: dropped %s/%s day(s) below the $%.0f volume floor",
                pair or "pair",
                dropped,
                len(frame),
                floor,
            )
        return kept.reset_index(drop=True)

    def load_daily_candles(self, symbol: str) -> pd.DataFrame:
        """Load every cached Binance candle window for a symbol."""
        pair = self.resolve_pair(symbol)
        directory = self.raw_dir / "candles"
        if not directory.exists():
            return pd.DataFrame(columns=BINANCE_COLUMNS)
        frames: list[pd.DataFrame] = []
        for path in sorted(directory.glob(f"{pair}_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            frame = self._frame_from_payload(payload, pair=pair)
            if not frame.empty:
                frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=BINANCE_COLUMNS)
        merged = pd.concat(frames, ignore_index=True)
        return merged.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        force: bool = False,
    ) -> pd.DataFrame:
        """Fetch daily closes for ``<SYMBOL><quote>`` over ``[start, end]``."""
        pair = self.resolve_pair(symbol)
        start_label = pd.Timestamp(start).date().isoformat()
        end_label = pd.Timestamp(end).date().isoformat()
        cache_path = self._cache_path(pair, start_label, end_label)

        if cache_path.exists() and not force:
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                payload = None
            if isinstance(payload, list):
                return self._frame_from_payload(payload, pair=pair)

        start_ms = int(pd.Timestamp(start_label, tz="UTC").timestamp() * 1000)
        # Cover the whole of the end day, not just its midnight boundary.
        end_ms = int(pd.Timestamp(end_label, tz="UTC").timestamp() * 1000) + _DAY_MS - 1
        rows = self._fetch_range(pair, start_ms, end_ms)
        cache_path.write_text(json.dumps(rows), encoding="utf-8")
        return self._frame_from_payload(rows, pair=pair)
