"""CryptoCompare client for long daily price and volume histories."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests

from atlas20.config import CryptoCompareConfig
from atlas20.logging_utils import get_logger


class CryptoCompareClient:
    """Cache-aware client around the public CryptoCompare histoday endpoint."""

    def __init__(self, config: CryptoCompareConfig, raw_dir: Path) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.raw_dir = raw_dir / "cryptocompare"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()

    def _cache_path(self, symbol: str) -> Path:
        directory = self.raw_dir / "histoday"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{symbol.upper()}.json"

    def fetch_daily_history(self, symbol: str, force: bool = False) -> pd.DataFrame:
        """Fetch full daily history for a symbol quoted in USD."""
        cache_path = self._cache_path(symbol)
        if cache_path.exists() and not force:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            url = f"{self.base_url}/histoday"
            self.logger.info("CryptoCompare request: %s %s", symbol.upper(), url)
            response = self.session.get(
                url,
                params={
                    "fsym": symbol.upper(),
                    "tsym": self.config.quote_currency,
                    "allData": "true",
                },
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if payload.get("Response") != "Success":
            message = payload.get("Message", "Unknown CryptoCompare error")
            raise ValueError(f"CryptoCompare history failed for {symbol}: {message}")

        frame = pd.DataFrame(payload["Data"]["Data"])
        if frame.empty:
            raise ValueError(f"CryptoCompare history is empty for {symbol}")
        frame["date"] = pd.to_datetime(frame["time"], unit="s").dt.normalize()
        return frame
