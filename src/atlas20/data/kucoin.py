"""KuCoin public daily-candle client.

KuCoin is an additional exchange-venue source for assets its native book is
best able to verify, especially KCS. It is opt-in per symbol through
``providers.kucoin.pair_aliases`` so the normal refresh does not spend a
request per asset at a third centralised exchange.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from atlas20.config import KuCoinConfig
from atlas20.data.cache_merge import describe_conflicts, fetch_ordered, merge_by_fetch_order
from atlas20.logging_utils import get_logger

KUCOIN_COLUMNS = ["date", "kucoin_price", "kucoin_volume_usd"]


class KuCoinClient:
    """Cache-aware client for KuCoin spot daily candles."""

    def __init__(self, config: KuCoinConfig, raw_dir: Path) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.raw_dir = raw_dir / "kucoin"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()
        self.duplicate_conflicts: dict[str, int] = {}

    def resolve_pair(self, symbol: str) -> str:
        upper = symbol.upper()
        alias = self.config.pair_aliases.get(upper) or self.config.pair_aliases.get(symbol)
        if alias:
            return str(alias)
        return f"{upper}-{self.config.quote_currency.upper()}"

    def has_configured_pair(self, symbol: str) -> bool:
        return bool(
            self.config.pair_aliases.get(symbol.upper())
            or self.config.pair_aliases.get(symbol)
        )

    def _cache_path(self, pair: str, start: pd.Timestamp, end: pd.Timestamp) -> Path:
        directory = self.raw_dir / "candles"
        directory.mkdir(parents=True, exist_ok=True)
        window = f"{pd.Timestamp(start).date().isoformat()}_{pd.Timestamp(end).date().isoformat()}"
        return directory / f"{pair}_{window}.json"

    def _request_json(self, pair: str, start: pd.Timestamp, end: pd.Timestamp, *, force: bool) -> list:
        cache_path = self._cache_path(pair, start, end)
        if cache_path.exists() and not force:
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                payload = None
            if isinstance(payload, list):
                return payload

        url = f"{self.base_url}/api/v1/market/candles"
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        start_ts = (
            start_ts.tz_localize("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
        )
        end_ts = end_ts.tz_localize("UTC") if end_ts.tzinfo is None else end_ts.tz_convert("UTC")
        # KuCoin returns no candle for a one-day startAt==endAt query. Pad both
        # ends; the caller filters the merged frame back to the requested days.
        api_start = start_ts - pd.Timedelta(days=1)
        api_end = end_ts + pd.Timedelta(days=1)
        params: dict[str, Any] = {
            "type": "1day",
            "symbol": pair,
            "startAt": int(api_start.timestamp()),
            "endAt": int(api_end.timestamp()),
        }
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            response = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
            if response.ok:
                body = response.json()
                if not isinstance(body, dict) or str(body.get("code")) != "200000":
                    raise ValueError(f"KuCoin pair unavailable: {str(body)[:300]}")
                data = body.get("data")
                if not isinstance(data, list):
                    raise ValueError(f"KuCoin returned an unexpected payload: {str(body)[:300]}")
                if data:
                    cache_path.write_text(json.dumps(data), encoding="utf-8")
                else:
                    self.logger.warning(
                        "KuCoin %s returned no candles for %s..%s; not caching coverage",
                        pair,
                        start.date(),
                        end.date(),
                    )
                if self.config.rate_limit_seconds > 0:
                    time.sleep(self.config.rate_limit_seconds)
                return data
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            last_error = RuntimeError(f"KuCoin request failed with status {response.status_code}")
            delay = max(
                self.config.rate_limit_seconds,
                self.config.retry_backoff_seconds * (2**attempt),
            )
            time.sleep(delay)
        if last_error is not None:
            raise last_error
        raise RuntimeError("KuCoin request failed unexpectedly")

    @staticmethod
    def _frame_from_payload(payload: object) -> pd.DataFrame:
        if not isinstance(payload, list) or not payload:
            return pd.DataFrame(columns=KUCOIN_COLUMNS)
        rows: list[dict[str, Any]] = []
        for row in payload:
            if not isinstance(row, (list, tuple)) or len(row) < 7:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(int(row[0]), unit="s", utc=True).tz_localize(None).normalize(),
                    "kucoin_price": row[2],
                    "kucoin_volume_usd": row[6],
                }
            )
        if not rows:
            return pd.DataFrame(columns=KUCOIN_COLUMNS)
        frame = pd.DataFrame(rows)
        frame["kucoin_price"] = pd.to_numeric(frame["kucoin_price"], errors="coerce")
        frame["kucoin_volume_usd"] = pd.to_numeric(frame["kucoin_volume_usd"], errors="coerce")
        frame = frame.dropna(subset=["date", "kucoin_price"])
        frame = frame[frame["kucoin_price"] > 0]
        return (
            frame[KUCOIN_COLUMNS]
            .sort_values("date", kind="mergesort")
            .drop_duplicates("date", keep="last")
            .reset_index(drop=True)
        )

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        start: pd.Timestamp | str,
        end: pd.Timestamp | str,
        force: bool = False,
    ) -> pd.DataFrame:
        pair = self.resolve_pair(symbol)
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        start_ts = (
            start_ts.tz_convert("UTC").tz_localize(None)
            if start_ts.tzinfo is not None
            else start_ts
        ).normalize()
        end_ts = (
            end_ts.tz_convert("UTC").tz_localize(None)
            if end_ts.tzinfo is not None
            else end_ts
        ).normalize()
        payload = self._request_json(pair, start_ts, end_ts, force=force)
        frame = self._frame_from_payload(payload)
        if frame.empty:
            return frame
        return frame[(frame["date"] >= start_ts) & (frame["date"] <= end_ts)].reset_index(drop=True)

    def load_daily_candles(self, symbol: str) -> pd.DataFrame:
        pair = self.resolve_pair(symbol)
        directory = self.raw_dir / "candles"
        if not directory.exists():
            return pd.DataFrame(columns=KUCOIN_COLUMNS)
        frames: list[pd.DataFrame] = []
        for path in fetch_ordered(directory.glob(f"{pair}_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            frame = self._frame_from_payload(payload)
            if not frame.empty:
                frames.append(frame)
        result = merge_by_fetch_order(
            frames,
            value_columns=["kucoin_price", "kucoin_volume_usd"],
            columns=KUCOIN_COLUMNS,
        )
        self.duplicate_conflicts[pair] = result.conflicting_dates
        if result.conflicting_dates:
            self.logger.warning("KuCoin %s: %s", pair, describe_conflicts(result))
        return result.frame
