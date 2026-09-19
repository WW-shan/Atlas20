"""Binance.US public daily-history client.

Binance.US exposes unauthenticated REST endpoints for spot klines. This
client is used as the long-history price/volume source after the
CryptoCompare free tier was shut down in mid-2026.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests

from atlas20.config import BinanceUSConfig
from atlas20.logging_utils import get_logger


class BinanceUSClient:
    """Cache-aware client around the Binance.US public klines endpoint."""

    def __init__(self, config: BinanceUSConfig, raw_dir: Path) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.raw_dir = raw_dir / "binanceus"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()

    def _cache_path(self, symbol: str) -> Path:
        directory = self.raw_dir / "klines"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{symbol.upper()}.json"

    def _fetch_page(self, symbol: str, end_time: int | None) -> list[list[object]]:
        params: dict[str, object] = {
            "symbol": symbol,
            "interval": "1d",
            "limit": self.config.page_limit,
        }
        if end_time is not None:
            params["endTime"] = end_time
        response = self.session.get(
            f"{self.base_url}/api/v3/klines",
            params=params,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError(f"Binance.US klines returned non-list payload for {symbol}")
        return payload

    def _fetch_symbol(self, symbol: str) -> list[list[object]]:
        """Fetch the full daily history, newest page first then backwards."""
        rows: list[list[object]] = []
        end_time: int | None = None
        while True:
            page = self._fetch_page(symbol, end_time)
            if not page:
                break
            rows = page + rows
            if len(page) < self.config.page_limit:
                break
            end_time = int(page[0][0]) - 1
        return rows

    def fetch_daily_history(self, symbol: str, force: bool = False) -> pd.DataFrame | None:
        """Return a normalized daily frame, or None when the pair is absent."""
        cache_path = self._cache_path(symbol)
        if cache_path.exists() and not force:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            payload = None
            last_error: Exception | None = None
            for quote in self.config.quote_currencies:
                pair = f"{symbol.upper()}{quote}"
                try:
                    rows = self._fetch_symbol(pair)
                except requests.HTTPError as exc:
                    last_error = exc
                    self.logger.info("Binance.US pair unavailable: %s (%s)", pair, exc)
                    continue
                if rows:
                    payload = rows
                    break
            if payload is None:
                if last_error is not None:
                    self.logger.info("Binance.US returned no history for %s", symbol)
                return None
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

        if not payload:
            return None

        frame = pd.DataFrame(
            {
                "date": pd.to_datetime([int(row[0]) for row in payload], unit="ms").normalize(),
                "close": [float(row[4]) for row in payload],
                "volume_usd": [float(row[7]) for row in payload],
            }
        )
        frame = frame[frame["close"] > 0].sort_values("date").reset_index(drop=True)
        if frame.empty:
            return None
        return frame
