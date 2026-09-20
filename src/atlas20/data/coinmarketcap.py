"""CoinMarketCap historical market-cap client.

Uses CMC's public ``data-api`` endpoint, which exposes true daily market cap
and circulating supply. This replaces the price-scaled proxy that the pipeline
previously used for long-history market caps, because the proxy ignored supply
changes and therefore produced an incorrect historical Top-N universe.

The endpoint returns at most ``page_size`` rows per request, so the client
walks the requested range in pages and caches the merged result.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from atlas20.config import CoinMarketCapConfig
from atlas20.logging_utils import get_logger

COLUMNS = ["date", "close", "volume_usd", "market_cap", "circulating_supply"]


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def _to_epoch(value: str | date | datetime) -> int:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


class CoinMarketCapClient:
    """Cache-aware client for daily historical market-cap data."""

    def __init__(self, config: CoinMarketCapConfig, raw_dir: Path) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        # The listing endpoint lives under v3 while historical lives under v3.1.
        self.listing_base_url = self.base_url.replace("/v3.1", "/v3")
        self.raw_dir = raw_dir / "coinmarketcap"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()

    def _cache_path(self, coin_id: int, start: int, end: int) -> Path:
        directory = self.raw_dir / "history"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{coin_id}_{start}_{end}.json"

    def _id_map_path(self) -> Path:
        return self.raw_dir / "id_map.json"

    def fetch_id_map(self, *, force: bool = False, max_pages: int = 6) -> dict[str, int]:
        """Return a SYMBOL -> CMC id mapping.

        The listing endpoint is paginated; symbols already seen are kept so a
        later page never overwrites an earlier (higher market cap) match.
        """
        path = self._id_map_path()
        if path.exists() and not force:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and cached:
                return {str(k): int(v) for k, v in cached.items()}

        mapping: dict[str, int] = {}
        for page in range(max_pages):
            start = 1 + page * 200
            response = self.session.get(
                f"{self.listing_base_url}/cryptocurrency/listing",
                params={
                    "start": start,
                    "limit": 200,
                    "sortBy": "market_cap",
                    "sortType": "desc",
                    "convert": "USD",
                    "cryptoType": "all",
                    "tagType": "all",
                },
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            rows = (payload.get("data") or {}).get("cryptoCurrencyList") or []
            if not rows:
                break
            for row in rows:
                symbol = str(row.get("symbol", "")).upper()
                coin_id = row.get("id")
                if symbol and coin_id is not None and symbol not in mapping:
                    mapping[symbol] = int(coin_id)
            if len(rows) < 200:
                break
            time.sleep(self.config.request_interval_seconds)

        if mapping:
            path.write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")
        return mapping

    def _fetch_page(self, coin_id: int, start: int, end: int) -> list[dict]:
        response = self.session.get(
            f"{self.base_url}/cryptocurrency/historical",
            params={
                "id": coin_id,
                "convertId": self.config.convert_id,
                "timeStart": start,
                "timeEnd": end,
                "interval": "1d",
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "data" not in payload:
            message = payload.get("status", {}).get("error_message") if isinstance(payload, dict) else None
            raise ValueError(f"CoinMarketCap returned no data for id={coin_id}: {message or payload}")
        return list(payload["data"].get("quotes") or [])

    def _fetch_range(self, coin_id: int, start: int, end: int) -> list[dict]:
        """Walk backwards from ``end`` until ``start`` is covered.

        The endpoint returns the most recent ``page_size`` rows ending at
        ``timeEnd`` regardless of ``timeStart``, so paging must move the end
        cursor backwards rather than the start cursor forwards.
        """
        rows: list[dict] = []
        cursor_end = end
        guard = 0
        max_requests = 200
        while cursor_end > start and guard < max_requests:
            guard += 1
            page = self._fetch_page(coin_id, start, cursor_end)
            if not page:
                break
            rows.extend(page)
            earliest = page[0].get("timeOpen")
            if not earliest:
                break
            earliest_ts = _to_epoch(earliest)
            if earliest_ts <= start:
                break
            if earliest_ts >= cursor_end:
                break
            cursor_end = earliest_ts - 86_400
            # Do not stop on a short page: the endpoint caps at page_size but
            # may return slightly fewer rows for the requested window, so the
            # only reliable stop conditions are covering `start` or making no
            # progress.
            time.sleep(self.config.request_interval_seconds)
        return rows

    def fetch_history(
        self,
        coin_id: int,
        *,
        start: str | date | datetime,
        end: str | date | datetime,
        force: bool = False,
    ) -> pd.DataFrame:
        """Return daily close, volume, market cap and supply for a CMC id."""
        start_ts = _to_epoch(start)
        end_ts = _to_epoch(end)
        cache_path = self._cache_path(coin_id, start_ts, end_ts)

        if cache_path.exists() and not force:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            payload = self._fetch_range(coin_id, start_ts, end_ts)
            # Paging walks backwards, so the merged rows arrive newest-first.
            # Persist them chronologically: downstream dedupe/merge logic
            # assumes ascending order.
            payload = sorted(payload, key=lambda row: row.get("timeOpen", ""))
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

        if not payload:
            return _empty()

        records = []
        for row in payload:
            quote = row.get("quote") or {}
            opened = row.get("timeOpen")
            if not opened:
                continue
            records.append(
                {
                    "date": pd.Timestamp(opened).normalize(),
                    "close": quote.get("close"),
                    "volume_usd": quote.get("volume"),
                    "market_cap": quote.get("marketCap"),
                    "circulating_supply": quote.get("circulatingSupply"),
                }
            )
        if not records:
            return _empty()

        frame = pd.DataFrame(records)[COLUMNS]
        frame = frame.dropna(subset=["close", "market_cap"])
        frame = frame[frame["close"] > 0]
        return frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
