"""CoinPaprika client used as a fallback third-provider adjudicator.

CoinMarketCap remains the only provider that feeds the research panel.  A
recent CMC block can nevertheless be internally consistent while being wrong,
so the pipeline checks it against CoinGecko first.  Gate.io is the preferred
third source when that check disagrees; CoinPaprika is consulted only for
assets Gate.io does not list.  The third source never rewrites a price; it
only supplies the majority vote needed to admit or reject CMC's print.

The public CoinPaprika historical endpoint has a free-plan window of roughly
the last 365 days.  The client therefore only asks for the recent validation
window and treats older requests as unavailable rather than fabricating data.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from atlas20.config import CoinPaprikaConfig
from atlas20.logging_utils import get_logger


def _normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]", "", text)


def _to_iso_date(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return pd.Timestamp(value).date().isoformat()


class CoinPaprikaClient:
    """Cache-aware client for the third-provider validation series."""

    def __init__(self, config: CoinPaprikaConfig, raw_dir: Path) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.raw_dir = raw_dir / "coinpaprika"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()
        self._coins_cache: list[dict[str, Any]] | None = None

    def _cache_path(self, namespace: str, name: str) -> Path:
        directory = self.raw_dir / namespace
        directory.mkdir(parents=True, exist_ok=True)
        return directory / name

    def _coins_path(self) -> Path:
        return self._cache_path("catalog", "coins.json")

    def _id_map_path(self) -> Path:
        return self._cache_path("catalog", "id_map.json")

    def _history_path(self, coin_id: str, start: str, end: str) -> Path:
        return self._cache_path("history", f"{coin_id}_{start}_{end}.json")

    def _sleep_after_response(self, response: requests.Response | None, attempt: int) -> None:
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

    def _request_json(
        self,
        endpoint: str,
        params: dict[str, Any],
        cache_path: Path,
        *,
        force: bool = False,
    ) -> Any:
        if cache_path.exists() and not force:
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # A partial cache must not poison the run; refresh it instead.
                pass

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response: requests.Response | None = None
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            self.logger.info("CoinPaprika request: %s", url)
            response = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
            if response.ok:
                payload = response.json()
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                if self.config.rate_limit_seconds > 0:
                    time.sleep(self.config.rate_limit_seconds)
                return payload

            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()

            last_error = requests.HTTPError(
                f"CoinPaprika request failed with status {response.status_code}: {response.text[:200]}",
                response=response,
            )
            self.logger.warning(
                "CoinPaprika retry %s/%s for %s after status %s",
                attempt + 1,
                self.config.max_retries,
                endpoint,
                response.status_code,
            )
            self._sleep_after_response(response, attempt)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"CoinPaprika request failed unexpectedly for {endpoint}")

    def fetch_coins(self, *, force: bool = False) -> list[dict[str, Any]]:
        """Return CoinPaprika's catalog, cached locally."""
        if self._coins_cache is not None and not force:
            return self._coins_cache
        payload = self._request_json("coins", {}, self._coins_path(), force=force)
        rows = [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []
        self._coins_cache = rows
        return rows

    @staticmethod
    def _load_id_map(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key): str(value) for key, value in payload.items() if value}

    @staticmethod
    def _write_id_map(path: Path, mapping: dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")

    def resolve_coin_id(
        self,
        *,
        coin_id: str,
        symbol: str,
        name: str,
        market_cap_rank: int | float | None = None,
        force: bool = False,
        bypass_id_map: bool = False,
    ) -> str | None:
        """Resolve a CoinGecko id to a CoinPaprika id.

        Matching is deliberately conservative: an exact ticker is required and
        the closest provider rank is used to break ties.  Rank matters because
        symbols are reused (for example, CoinPaprika lists both Jupiter
        Exchange Token and an unrelated ``JUP`` token); the CoinGecko rank is a
        strong signal for which listing is the same asset.  A manual alias in
        the config always wins, which is the escape hatch for rebrands and
        tokens whose CoinGecko name differs from CoinPaprika's.
        """
        alias = self.config.id_aliases.get(coin_id) or self.config.id_aliases.get(symbol.upper())
        if alias:
            return str(alias)

        mapping = self._load_id_map(self._id_map_path())
        if not bypass_id_map and not force and coin_id in mapping:
            return mapping[coin_id]

        coins = self.fetch_coins(force=force)
        target_symbol = symbol.upper()
        candidates = [
            row
            for row in coins
            if str(row.get("symbol", "")).upper() == target_symbol
            and str(row.get("id", "")).strip()
        ]
        if not candidates:
            return None

        target_rank = (
            int(float(market_cap_rank))
            if market_cap_rank is not None and pd.notna(market_cap_rank)
            else None
        )
        target_name = _normalize_name(name)

        def candidate_key(row: dict[str, Any]) -> tuple[int, int, float, int]:
            rank = int(row.get("rank") or 0)
            active = bool(row.get("is_active"))
            if rank <= 0:
                rank_penalty = 10**9
            elif target_rank is None:
                rank_penalty = rank
            else:
                rank_penalty = abs(rank - target_rank)
            similarity = SequenceMatcher(None, target_name, _normalize_name(row.get("name"))).ratio()
            return (0 if active and rank > 0 else 1, rank_penalty, -similarity, rank if rank > 0 else 10**9)

        candidates.sort(key=candidate_key)
        chosen = candidates[0]
        resolved = str(chosen["id"])
        mapping[coin_id] = resolved
        self._write_id_map(self._id_map_path(), mapping)
        return resolved

    @staticmethod
    def _frame_from_payload(payload: object) -> pd.DataFrame:
        if not isinstance(payload, list) or not payload:
            return pd.DataFrame(columns=["date", "pap_price", "pap_volume_usd", "pap_market_cap"])
        frame = pd.DataFrame(payload)
        if "timestamp" not in frame.columns or "price" not in frame.columns:
            return pd.DataFrame(columns=["date", "pap_price", "pap_volume_usd", "pap_market_cap"])
        frame = frame.rename(
            columns={
                "timestamp": "date",
                "price": "pap_price",
                "volume_24h": "pap_volume_usd",
                "market_cap": "pap_market_cap",
            }
        )
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
        for column in ("pap_price", "pap_volume_usd", "pap_market_cap"):
            if column not in frame.columns:
                frame[column] = float("nan")
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["date", "pap_price"])
        frame = frame[frame["pap_price"] > 0]
        return (
            frame[["date", "pap_price", "pap_volume_usd", "pap_market_cap"]]
            .sort_values("date")
            .drop_duplicates("date", keep="last")
            .reset_index(drop=True)
        )

    def fetch_daily_history(
        self,
        coin_id: str,
        *,
        start: str | date | datetime,
        end: str | date | datetime,
        force: bool = False,
    ) -> pd.DataFrame:
        """Fetch daily historical prices for a CoinPaprika coin id."""
        start_date = _to_iso_date(start)
        end_date = _to_iso_date(end)
        cache_path = self._history_path(coin_id, start_date, end_date)
        payload = self._request_json(
            f"tickers/{coin_id}/historical",
            {"start": start_date, "end": end_date, "interval": "1d", "quote": "USD"},
            cache_path,
            force=force,
        )
        return self._frame_from_payload(payload)

    def load_daily_history(self, coin_id: str) -> pd.DataFrame:
        """Load every cached CoinPaprika history window for a coin id."""
        directory = self.raw_dir / "history"
        if not directory.exists():
            return pd.DataFrame(columns=["date", "pap_price", "pap_volume_usd", "pap_market_cap"])
        frames: list[pd.DataFrame] = []
        for path in sorted(directory.glob(f"{coin_id}_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            frame = self._frame_from_payload(payload)
            if not frame.empty:
                frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=["date", "pap_price", "pap_volume_usd", "pap_market_cap"])
        merged = pd.concat(frames, ignore_index=True)
        return (
            merged.sort_values("date")
            .drop_duplicates("date", keep="last")
            .reset_index(drop=True)
        )
