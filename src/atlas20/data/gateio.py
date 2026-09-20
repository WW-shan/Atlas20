"""Gate.io exchange-candle client used for independent price validation.

Gate.io is the preferred third source because it is an exchange venue, has a
generous public API budget, and still serves historical daily candles for
delisted assets such as Celsius (CEL) and Huobi Token (HT).  The panel remains
100% CoinMarketCap; this client only supplies a vote when CoinGecko disagrees
with the primary provider.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from atlas20.config import GateIOConfig
from atlas20.logging_utils import get_logger

GATE_COLUMNS = ["date", "gate_price", "gate_volume_usd"]


class GateIOClient:
    """Cache-aware client for Gate.io spot daily candles."""

    def __init__(self, config: GateIOConfig, raw_dir: Path) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.raw_dir = raw_dir / "gateio"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()

    def _cache_path(self, pair: str, limit: int) -> Path:
        directory = self.raw_dir / "candles"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{pair}_{limit}.json"

    def resolve_pair(self, symbol: str) -> str:
        """Return the configured Gate.io pair for a CoinGecko ticker."""
        upper = symbol.upper()
        alias = self.config.pair_aliases.get(upper) or self.config.pair_aliases.get(symbol)
        if alias:
            return str(alias)
        return f"{upper}_{self.config.quote_currency.upper()}"

    def _request_json(self, endpoint: str, params: dict[str, Any], cache_path: Path, *, force: bool = False) -> Any:
        if cache_path.exists() and not force:
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            self.logger.info("Gate.io request: %s", url)
            response = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
            if response.ok:
                payload = response.json()
                if isinstance(payload, dict) and (payload.get("label") or payload.get("message")):
                    raise ValueError(f"Gate.io pair unavailable: {payload}")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                if self.config.rate_limit_seconds > 0:
                    time.sleep(self.config.rate_limit_seconds)
                return payload

            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            last_error = requests.HTTPError(
                f"Gate.io request failed with status {response.status_code}: {response.text[:200]}",
                response=response,
            )
            delay = max(self.config.rate_limit_seconds, self.config.retry_backoff_seconds * (2**attempt))
            self.logger.warning(
                "Gate.io retry %s/%s for %s after status %s",
                attempt + 1,
                self.config.max_retries,
                endpoint,
                response.status_code,
            )
            time.sleep(delay)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Gate.io request failed unexpectedly for {endpoint}")

    @staticmethod
    def _frame_from_payload(payload: object) -> pd.DataFrame:
        if not isinstance(payload, list) or not payload:
            return pd.DataFrame(columns=GATE_COLUMNS)
        rows: list[dict[str, Any]] = []
        for row in payload:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(int(row[0]), unit="s", utc=True).tz_localize(None).normalize(),
                    "gate_price": row[2],
                    "gate_volume_usd": row[1],
                }
            )
        if not rows:
            return pd.DataFrame(columns=GATE_COLUMNS)
        frame = pd.DataFrame(rows)
        frame["gate_price"] = pd.to_numeric(frame["gate_price"], errors="coerce")
        frame["gate_volume_usd"] = pd.to_numeric(frame["gate_volume_usd"], errors="coerce")
        frame = frame.dropna(subset=["date", "gate_price"])
        frame = frame[frame["gate_price"] > 0]
        return (
            frame[GATE_COLUMNS]
            .sort_values("date")
            .drop_duplicates("date", keep="last")
            .reset_index(drop=True)
        )

    def fetch_daily_candles(
        self,
        symbol: str,
        *,
        limit: int = 400,
        force: bool = False,
    ) -> pd.DataFrame:
        """Fetch the most recent daily candles for ``<SYMBOL>_USDT``."""
        pair = self.resolve_pair(symbol)
        payload = self._request_json(
            "spot/candlesticks",
            {"currency_pair": pair, "interval": "1d", "limit": limit},
            self._cache_path(pair, limit),
            force=force,
        )
        return self._frame_from_payload(payload)

    def load_daily_candles(self, symbol: str) -> pd.DataFrame:
        """Load every cached Gate.io candle window for a symbol."""
        pair = self.resolve_pair(symbol)
        directory = self.raw_dir / "candles"
        if not directory.exists():
            return pd.DataFrame(columns=GATE_COLUMNS)
        frames: list[pd.DataFrame] = []
        for path in sorted(directory.glob(f"{pair}_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            frame = self._frame_from_payload(payload)
            if not frame.empty:
                frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=GATE_COLUMNS)
        merged = pd.concat(frames, ignore_index=True)
        return merged.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
