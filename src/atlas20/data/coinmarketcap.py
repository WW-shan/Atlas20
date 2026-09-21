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


# CMC bills the trailing days after a coin's last print against the page, so a
# window that ends more than ``page_size`` days late comes back empty even
# though the series exists. Rewinding by one page per attempt finds the real
# end of a delisted series (MATIC, 2025-03-24) in a single extra request.
_EMPTY_PAGE_REWIND_SECONDS = 400 * 86_400


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

    @staticmethod
    def _merge_id_map(cached: dict[str, int], discovered: dict[str, int]) -> dict[str, int]:
        """Additive merge: a symbol is never dropped by a refresh.

        Only new symbols are added, so a coin that has since rebranded keeps
        the id it was first mapped to.
        """
        merged = dict(cached)
        for symbol, coin_id in discovered.items():
            merged.setdefault(symbol, coin_id)
        return merged

    def fetch_id_map(self, *, force: bool = False, max_pages: int = 6) -> dict[str, int]:
        """Return a SYMBOL -> CMC id mapping.

        The listing endpoint is paginated; symbols already seen are kept so a
        later page never overwrites an earlier (higher market cap) match.

        A refresh is *additive*: it merges into the existing map instead of
        replacing it. Coins rebrand and fall off the listing - EOS became
        Vaulta, MKR became SKY, FTM became Sonic - and a replacing refresh
        would silently drop their ids, making every retired-but-still-tradable
        asset disappear from the candidate pool. That is precisely the
        survivorship bias this cache exists to avoid.
        """
        path = self._id_map_path()
        cached: dict[str, int] = {}
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    cached = {str(k): int(v) for k, v in payload.items()}
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                cached = {}
        if cached and not force:
            return cached

        mapping: dict[str, int] = dict(cached)
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

        An empty page is *not* proof that the coin has no history. The provider
        charges the trailing empty days against the page: a coin whose last
        print is 2025-03-24 returns nothing for a window ending today (547 days
        later, more than one page), but 253 rows for a window ending 400 days
        earlier. Reading that first empty page as "no data" is what erased
        MATIC - a Top-20 member on 123 of the strategy's rebalance dates - from
        the panel, so an empty page rewinds the cursor and retries before the
        coin is written off.
        """
        rows: list[dict] = []
        cursor_end = end
        guard = 0
        max_requests = 200
        while cursor_end > start and guard < max_requests:
            guard += 1
            page = self._fetch_page(coin_id, start, cursor_end)
            if not page:
                rewind = cursor_end - _EMPTY_PAGE_REWIND_SECONDS
                if rewind <= start:
                    break
                self.logger.info(
                    "CoinMarketCap id=%s: no rows ending %s, rewinding to %s",
                    coin_id,
                    pd.Timestamp(cursor_end, unit="s").date(),
                    pd.Timestamp(rewind, unit="s").date(),
                )
                cursor_end = rewind
                time.sleep(self.config.request_interval_seconds)
                continue
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

    def _cached_windows(self, coin_id: int) -> list[tuple[int, int]]:
        """Return the (start, end) epoch pairs this coin was already asked for.

        Read from the cache filenames rather than the payload so coverage can
        be assessed without parsing every file.
        """
        directory = self.raw_dir / "history"
        if not directory.exists():
            return []
        windows: list[tuple[int, int]] = []
        for path in directory.glob(f"{coin_id}_*.json"):
            parts = path.stem.split("_")
            if len(parts) != 3:
                continue
            try:
                windows.append((int(parts[1]), int(parts[2])))
            except ValueError:
                continue
        return windows

    def _merged_cache(self, coin_id: int) -> pd.DataFrame:
        """Every cached window for this coin, merged and normalized."""
        directory = self.raw_dir / "history"
        if not directory.exists():
            return _empty()
        frames: list[pd.DataFrame] = []
        for path in sorted(directory.glob(f"{coin_id}_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not payload:
                continue
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
            if records:
                frames.append(pd.DataFrame(records))
        if not frames:
            return _empty()

        frame = pd.concat(frames, ignore_index=True)[COLUMNS]
        frame = frame.dropna(subset=["close", "market_cap"])
        frame = frame[frame["close"] > 0]
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)

    def cached_history(self, coin_id: int) -> pd.DataFrame:
        """Return the merged on-disk history without making a network request."""
        return self._merged_cache(coin_id)

    def has_backfill(self, coin_id: int, *, start: str | date | datetime) -> bool:
        """True when a cached window reaches back to the required start."""
        start_ts = _to_epoch(start)
        return any(window_start <= start_ts for window_start, _ in self._cached_windows(coin_id))

    def ensure_history(
        self,
        coin_id: int,
        *,
        start: str | date | datetime,
        end: str | date | datetime,
        force: bool = False,
    ) -> pd.DataFrame:
        """Guarantee the cache covers ``[start, end]`` for ``coin_id``.

        A coin that newly enters the Top-N must be fully backfilled on the same
        run - it cannot be scored on partial history. An already-onboarded coin
        must not be re-downloaded in full every day, so a fresh cache triggers
        no request at all and a stale one triggers only a short tail pull.
        """
        start_ts = _to_epoch(start)
        end_ts = _to_epoch(end)
        windows = self._cached_windows(coin_id)

        if force or not windows:
            self.fetch_history(coin_id, start=start, end=end, force=force)
            return self._merged_cache(coin_id)

        if not any(window_start <= start_ts for window_start, _ in windows):
            # Never backfilled to the required depth (a new entrant).
            self.fetch_history(coin_id, start=start, end=end, force=False)
            return self._merged_cache(coin_id)

        merged = self._merged_cache(coin_id)
        if self._lags_last_completed_day(merged, end_ts):
            # Only the tail is missing; pull a short window instead of
            # re-downloading the coin's whole history. ``force`` is required:
            # an earlier run today already wrote a window with this exact name
            # *before* the provider published the newest close, so an ordinary
            # cache read would hand back that stale payload and the cache would
            # never advance past it.
            tail_start = max(
                pd.Timestamp(end_ts, unit="s").normalize() - pd.Timedelta(days=self.config.tail_refresh_days),
                pd.Timestamp(start_ts, unit="s").normalize(),
            )
            self.fetch_history(coin_id, start=tail_start.date(), end=end, force=True)
            merged = self._merged_cache(coin_id)

        return merged

    @staticmethod
    def _lags_last_completed_day(merged: pd.DataFrame, end_ts: int) -> bool:
        """True when the cached payload stops before the last completed day.

        Window *filenames* record the requested end (today's midnight), not the
        last row actually stored. A run that executes before the provider has
        published day D's close writes a window named for today but holding
        data only through D-1; comparing filenames then reports a false
        "already covered" and the cache freezes a day behind. The real last row
        date is what has to be checked, and the newest completed day is
        ``end - 1`` (the current UTC day is still in progress).
        """
        if merged.empty:
            return True
        last_completed_day = (pd.Timestamp(end_ts, unit="s") - pd.Timedelta(days=1)).normalize()
        last_data_date = pd.Timestamp(merged["date"].max())
        if last_data_date.tzinfo is not None:
            last_data_date = last_data_date.tz_convert("UTC").tz_localize(None)
        return bool(last_data_date.normalize() < last_completed_day)


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
