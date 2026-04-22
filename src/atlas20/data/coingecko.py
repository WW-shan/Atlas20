"""CoinGecko client for current market snapshots and metadata."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests import Response

from atlas20.config import CoinGeckoConfig
from atlas20.logging_utils import get_logger


class CoinGeckoClient:
    """Thin cache-aware client around the public CoinGecko API."""

    def __init__(self, config: CoinGeckoConfig, raw_dir: Path) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.raw_dir = raw_dir / "coingecko"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()

    def _cache_path(self, namespace: str, name: str) -> Path:
        directory = self.raw_dir / namespace
        directory.mkdir(parents=True, exist_ok=True)
        return directory / name

    def _sleep_after_response(self, response: Response | None, attempt: int) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        if retry_after is not None:
            try:
                delay = max(float(retry_after), self.config.rate_limit_seconds)
            except ValueError:
                delay = self.config.rate_limit_seconds
        else:
            delay = max(
                self.config.rate_limit_seconds,
                self.config.retry_backoff_seconds * (2**attempt),
            )
        time.sleep(delay)

    def _request_json(self, endpoint: str, params: dict[str, Any], cache_path: Path, force: bool = False) -> Any:
        if cache_path.exists() and not force:
            return json.loads(cache_path.read_text(encoding="utf-8"))

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response: Response | None = None
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            self.logger.info("CoinGecko request: %s", url)
            response = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
            if response.ok:
                payload = response.json()
                cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                time.sleep(self.config.rate_limit_seconds)
                return payload

            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()

            last_error = requests.HTTPError(
                f"CoinGecko request failed with status {response.status_code}: {response.text[:200]}",
                response=response,
            )
            self.logger.warning(
                "CoinGecko retry %s/%s for %s after status %s",
                attempt + 1,
                self.config.max_retries,
                endpoint,
                response.status_code,
            )
            self._sleep_after_response(response, attempt)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"CoinGecko request failed unexpectedly for {endpoint}")

    def fetch_top_markets(self, per_page: int, force: bool = False) -> pd.DataFrame:
        """Fetch the current top assets ranked by market cap."""
        payload = self._request_json(
            endpoint="coins/markets",
            params={
                "vs_currency": self.config.vs_currency,
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h",
            },
            cache_path=self._cache_path("snapshots", f"top_markets_{per_page}.json"),
            force=force,
        )
        return pd.DataFrame(payload)

    def fetch_markets_by_ids(self, coin_ids: list[str], force: bool = False) -> pd.DataFrame:
        """Fetch current market snapshot rows for specific CoinGecko ids."""
        if not coin_ids:
            return pd.DataFrame()

        chunks: list[pd.DataFrame] = []
        for idx in range(0, len(coin_ids), 100):
            chunk = sorted(set(coin_ids[idx : idx + 100]))
            digest = hashlib.md5(",".join(chunk).encode("utf-8")).hexdigest()[:12]
            payload = self._request_json(
                endpoint="coins/markets",
                params={
                    "vs_currency": self.config.vs_currency,
                    "ids": ",".join(chunk),
                    "order": "market_cap_desc",
                    "per_page": len(chunk),
                    "page": 1,
                    "sparkline": "false",
                },
                cache_path=self._cache_path("snapshots", f"markets_by_ids_{digest}.json"),
                force=force,
            )
            chunks.append(pd.DataFrame(payload))
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

    def fetch_coin_metadata(self, coin_id: str, force: bool = False) -> dict[str, Any]:
        """Fetch CoinGecko metadata for a coin."""
        return self._request_json(
            endpoint=f"coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "false",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
            cache_path=self._cache_path("coin_metadata", f"{coin_id}.json"),
            force=force,
        )

    def fetch_daily_market_chart(self, coin_id: str, days: int, force: bool = False) -> pd.DataFrame:
        """Fetch recent daily price, market-cap, and volume history for a coin."""
        payload = self._request_json(
            endpoint=f"coins/{coin_id}/market_chart",
            params={
                "vs_currency": self.config.vs_currency,
                "days": days,
                "interval": "daily",
            },
            cache_path=self._cache_path("market_chart", f"{coin_id}_{days}d.json"),
            force=force,
        )

        prices = pd.DataFrame(payload.get("prices", []), columns=["timestamp_ms", "cg_price"])
        market_caps = pd.DataFrame(payload.get("market_caps", []), columns=["timestamp_ms", "cg_market_cap"])
        volumes = pd.DataFrame(payload.get("total_volumes", []), columns=["timestamp_ms", "cg_volume_usd"])
        if prices.empty:
            return pd.DataFrame(columns=["date", "cg_price", "cg_market_cap", "cg_volume_usd"])

        frame = prices.merge(market_caps, on="timestamp_ms", how="outer").merge(volumes, on="timestamp_ms", how="outer")
        frame["date"] = pd.to_datetime(frame["timestamp_ms"], unit="ms").dt.normalize()
        frame = (
            frame.sort_values("timestamp_ms")
            .groupby("date", as_index=False)
            .last()[["date", "cg_price", "cg_market_cap", "cg_volume_usd"]]
        )
        return frame
