"""Public Bitget USDT-M derivatives data client.

The derivatives research track needs three things from Bitget that the spot
panel does not carry:

* current contract metadata (symbol, fees, funding interval, minimum order);
* historical 1H mark/index/market candles for liquidation-path modelling;
* the exchange's own recent funding history for overlap validation against the
  longer Binance funding archive.

The public API is intentionally used without keys.  Historical candle windows
are capped at 90 days and 100 rows per request by Bitget, so the client walks
89-day windows and pages forward with the timestamp cursor.  A zero-row page
ends the current window; callers should compare the returned frame with the
expected window to detect listing/delisting gaps.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
import requests

from atlas20.derivatives.integrity import deduplicate_by_keys_or_raise

BITGET_CATEGORY = "USDT-FUTURES"
BITGET_BASE_URL = "https://api.bitget.com"

CANDLE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "quote_volume"]
FUNDING_COLUMNS = ["symbol", "funding_time", "funding_rate"]

_ALLOWED_CANDLE_TYPES = {"market", "mark", "index"}
_ALLOWED_INTERVALS = {
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1H",
    "4H",
    "6H",
    "12H",
    "1D",
    "3D",
    "1W",
    "1M",
}
_CANDLE_PAGE_LIMIT = 100
_MAX_WINDOW_DAYS = 89
_HOUR_MS = 3_600_000
_SUCCESS_CODES = {"0", "00000"}


class BitgetAPIError(RuntimeError):
    """Raised when Bitget answers with an error code or malformed payload."""


def _utc_timestamp(value: str | pd.Timestamp) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _millis(value: pd.Timestamp) -> int:
    return int(value.timestamp() * 1000)


def candle_frame(rows: list[list[Any]]) -> pd.DataFrame:
    """Parse Bitget's positional candle payload into a typed frame."""
    if not rows:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    parsed: list[list[Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or len(row) < 7:
            raise BitgetAPIError(f"Bitget candle row {index} is malformed")
        parsed.append(list(row[:7]))
    if not parsed:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    frame = pd.DataFrame(parsed, columns=CANDLE_COLUMNS)
    try:
        frame["open_time"] = pd.to_datetime(
            frame["open_time"].astype("int64"), unit="ms", utc=True
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise BitgetAPIError(f"Bitget candle timestamp is malformed: {exc}") from exc
    for column in CANDLE_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if not np.isfinite(
        frame.loc[:, CANDLE_COLUMNS[1:]].to_numpy(dtype=float)
    ).all():
        raise BitgetAPIError("Bitget candle payload contains a missing or non-finite value")
    frame = deduplicate_by_keys_or_raise(
        frame,
        keys=["open_time"],
        values=CANDLE_COLUMNS,
        label="Bitget candles",
    )
    return frame.sort_values("open_time").reset_index(drop=True)


def funding_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Parse v2/v3 funding-rate payloads into one canonical frame."""
    if not rows:
        return pd.DataFrame(columns=FUNDING_COLUMNS)
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise BitgetAPIError(f"Bitget funding row {index} is malformed")
        stamp = row.get("fundingRateTimestamp", row.get("fundingTime"))
        if stamp is None:
            raise BitgetAPIError(f"Bitget funding row {index} has no timestamp")
        try:
            funding_time = pd.to_datetime(int(stamp), unit="ms", utc=True)
        except (TypeError, ValueError, OverflowError) as exc:
            raise BitgetAPIError(
                f"Bitget funding row {index} timestamp is malformed: {exc}"
            ) from exc
        funding_rate = pd.to_numeric(row.get("fundingRate"), errors="coerce")
        if not np.isfinite(float(funding_rate)):
            raise BitgetAPIError(
                f"Bitget funding row {index} has no finite numeric rate"
            )
        records.append(
            {
                "symbol": str(row.get("symbol", "")),
                "funding_time": funding_time,
                "funding_rate": funding_rate,
            }
        )
    if not records:
        return pd.DataFrame(columns=FUNDING_COLUMNS)
    frame = pd.DataFrame.from_records(records, columns=FUNDING_COLUMNS)
    frame = deduplicate_by_keys_or_raise(
        frame,
        keys=["funding_time"],
        values=["symbol", "funding_rate"],
        label="Bitget funding",
    )
    return frame.sort_values("funding_time").reset_index(drop=True)


class BitgetClient:
    """Small, cache-agnostic client for Bitget public USDT-M endpoints."""

    def __init__(
        self,
        *,
        base_url: str = BITGET_BASE_URL,
        timeout_seconds: float = 30.0,
        max_retries: int = 4,
        retry_backoff_seconds: float = 1.0,
        rate_limit_seconds: float = 0.05,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.rate_limit_seconds = rate_limit_seconds
        self.session = session or requests.Session()
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update({"User-Agent": "atlas20-research/0.1"})
        self.request_count = 0
        self.last_request_time_ms: int | None = None

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        self.last_request_time_ms = None
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout_seconds)
            except (requests.RequestException, OSError) as exc:
                # requests normally wraps TLS/read failures, but a proxy or
                # platform socket path can surface the same timeout as a bare
                # OSError.  Retry only failures whose message identifies them
                # as transient; a programming error must still escape.
                transient = isinstance(exc, requests.RequestException) or any(
                    marker in str(exc).lower()
                    for marker in (
                        "timed out",
                        "timeout",
                        "connection reset",
                        "connection refused",
                        "temporarily unavailable",
                        "network is unreachable",
                    )
                )
                if not transient:
                    raise
                last_error = exc
                if attempt + 1 >= self.max_retries:
                    raise
                time.sleep(self.retry_backoff_seconds * (2**attempt))
                continue

            if response.ok:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise BitgetAPIError(f"Bitget {path} returned non-JSON payload") from exc
                if not isinstance(payload, dict):
                    raise BitgetAPIError(f"Bitget {path} returned an unexpected payload")
                code = str(payload.get("code", ""))
                if code not in _SUCCESS_CODES:
                    raise BitgetAPIError(f"Bitget {path} error {code}: {payload.get('msg', '')}")
                self.request_count += 1
                try:
                    request_time_ms = int(payload.get("requestTime"))
                except (TypeError, ValueError):
                    request_time_ms = 0
                if request_time_ms > 0:
                    self.last_request_time_ms = request_time_ms
                if self.rate_limit_seconds > 0:
                    time.sleep(self.rate_limit_seconds)
                return payload

            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = requests.HTTPError(
                    f"Bitget {path} HTTP {response.status_code}: {response.text[:200]}",
                    response=response,  # type: ignore[arg-type]
                )
                if attempt + 1 >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * (2**attempt))
                continue

            raise BitgetAPIError(
                f"Bitget {path} HTTP {response.status_code}: {response.text[:200]}"
            )

        if last_error is not None:
            raise last_error
        raise BitgetAPIError(f"Bitget {path} failed without a response")

    def fetch_contracts(self) -> list[dict[str, Any]]:
        """Return the current USDT-M perpetual contract universe."""
        payload = self._get("/api/v2/mix/market/contracts", {"productType": BITGET_CATEGORY})
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise BitgetAPIError("Bitget contracts payload is not a list")
        return [dict(item) for item in data if isinstance(item, dict)]

    def fetch_history_candles(
        self,
        symbol: str,
        candle_type: str,
        start: str | pd.Timestamp,
        end: str | pd.Timestamp,
        *,
        interval: str = "1H",
    ) -> pd.DataFrame:
        """Fetch 1H candles in ``[start, end)`` for one Bitget contract.

        Bitget limits one request to 100 rows and one window to 90 days, so the
        client walks 89-day windows.  A zero-row page ends the current window;
        the caller can compare the returned timestamps with the requested
        window to identify listing gaps.
        """
        if candle_type not in _ALLOWED_CANDLE_TYPES:
            raise ValueError(f"candle_type must be one of {sorted(_ALLOWED_CANDLE_TYPES)}")
        if interval not in _ALLOWED_INTERVALS:
            raise ValueError(f"unsupported Bitget interval: {interval}")
        start_ts = _utc_timestamp(start)
        end_ts = _utc_timestamp(end)
        if end_ts <= start_ts:
            return pd.DataFrame(columns=CANDLE_COLUMNS)

        rows: list[list[Any]] = []
        window_start = start_ts
        while window_start < end_ts:
            window_end = min(window_start + pd.Timedelta(days=_MAX_WINDOW_DAYS), end_ts)
            end_cursor = window_end
            while end_cursor > window_start:
                payload = self._get(
                    "/api/v3/market/history-candles",
                    {
                        "category": BITGET_CATEGORY,
                        "symbol": symbol.upper(),
                        "interval": interval,
                        "type": candle_type,
                        "startTime": _millis(window_start),
                        "endTime": _millis(end_cursor),
                        "limit": _CANDLE_PAGE_LIMIT,
                    },
                )
                data = payload.get("data")
                if data is None:
                    page: list[Any] = []
                elif not isinstance(data, list):
                    raise BitgetAPIError("Bitget candle data is not an array")
                else:
                    page = data
                if not page:
                    break
                page_times = [int(row[0]) for row in page if isinstance(row, (list, tuple)) and row]
                if not page_times:
                    break
                # Bitget returns the most recent rows before endTime; page
                # backwards until the window start is covered.
                if max(page_times) < _millis(window_start):
                    break
                rows.extend(page)
                first_open = pd.to_datetime(min(page_times), unit="ms", utc=True)
                # Bitget treats endTime as an hour-exclusive boundary.  Using
                # first_open - 1ms floors back to the previous hour and drops
                # that hour on every 100-row page; use the first open itself.
                next_end = first_open
                if next_end >= end_cursor:
                    break
                end_cursor = next_end
            window_start = window_end
        frame = candle_frame(rows)
        if frame.empty:
            return frame
        return frame.loc[(frame["open_time"] >= start_ts) & (frame["open_time"] < end_ts)].reset_index(drop=True)

    def fetch_funding_history(
        self,
        symbol: str,
        *,
        page_size: int = 100,
        max_pages: int = 20,
    ) -> pd.DataFrame:
        """Fetch Bitget's public funding history (currently about 90 days)."""
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")
        frames: list[pd.DataFrame] = []
        request_times_ms: list[int] = []
        for page_no in range(1, max_pages + 1):
            payload = self._get(
                "/api/v2/mix/market/history-fund-rate",
                {
                    "productType": BITGET_CATEGORY,
                    "symbol": symbol.upper(),
                    "pageSize": page_size,
                    "pageNo": page_no,
                },
            )
            if self.last_request_time_ms is not None:
                request_times_ms.append(self.last_request_time_ms)
            data = payload.get("data")
            if data is None:
                page: list[Any] = []
            elif isinstance(data, dict):
                result_list = data.get("resultList")
                if result_list is None:
                    page = []
                elif not isinstance(result_list, list):
                    raise BitgetAPIError("Bitget funding data resultList is not an array")
                else:
                    page = result_list
            elif isinstance(data, list):
                page = data
            else:
                raise BitgetAPIError("Bitget funding data is not an array or object")
            if not isinstance(page, list) or not page:
                break
            frame = funding_frame(page)
            if frame.empty:
                break
            frames.append(frame)
        if not frames:
            empty = pd.DataFrame(columns=FUNDING_COLUMNS)
            empty.attrs["request_times_ms"] = request_times_ms
            empty.attrs["request_time_ms"] = (
                max(request_times_ms) if request_times_ms else None
            )
            return empty
        combined = pd.concat(frames, ignore_index=True)
        combined = deduplicate_by_keys_or_raise(
            combined,
            keys=["funding_time"],
            values=["symbol", "funding_rate"],
            label=f"Bitget {symbol.upper()} funding history",
        ).sort_values("funding_time")
        combined = combined.reset_index(drop=True)
        combined.attrs["request_times_ms"] = request_times_ms
        combined.attrs["request_time_ms"] = (
            max(request_times_ms) if request_times_ms else None
        )
        return combined

    def fetch_current_funding(self, symbol: str) -> dict[str, Any]:
        """Return the current funding-rate record for one contract."""
        payload = self._get("/api/v3/market/current-fund-rate", {"symbol": symbol.upper()})
        data = payload.get("data") or []
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return dict(data[0])
        return {}

    def fetch_funding_time(self, symbol: str) -> dict[str, Any]:
        """Return the next funding time and interval for one contract."""
        payload = self._get(
            "/api/v2/mix/market/funding-time",
            {"productType": BITGET_CATEGORY, "symbol": symbol.upper()},
        )
        data = payload.get("data") or []
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return dict(data[0])
        return {}


__all__ = [
    "BITGET_BASE_URL",
    "BITGET_CATEGORY",
    "CANDLE_COLUMNS",
    "FUNDING_COLUMNS",
    "BitgetAPIError",
    "BitgetClient",
    "candle_frame",
    "funding_frame",
]
