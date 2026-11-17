"""Download Bitget USDT-M derivative research data for the PIT Top20.

The script is deliberately resumable.  It stores one CSV per
``<symbol>_<candle_type>.csv`` and a small ``state.json`` keyed by 89-day
window.  A completed or known-missing window is never fetched twice unless
``--force`` is passed.  ``--max-requests`` provides a bounded run for CI or an
initial coverage audit without hammering the public endpoint.

Usage::

    .venv/bin/python scripts/download_bitget_derivatives_data.py \
        --sample-windows 4 --max-requests 600

    .venv/bin/python scripts/download_bitget_derivatives_data.py \
        --start 2022-01-01 --end 2026-09-21
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import time
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time as time_module
from typing import Any, Callable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.bitget import BitgetClient, CANDLE_COLUMNS  # noqa: E402
from atlas20.derivatives.data_audit import required_last_mark_time  # noqa: E402
from atlas20.derivatives.mapping import build_symbol_map  # noqa: E402
from atlas20.logging_utils import (  # noqa: E402
    atomic_write_text,
    configure_logging,
    ensure_dir,
    get_logger,
)

LOGGER = get_logger(__name__)
DEFAULT_TYPES = ("mark", "index", "market")
_WINDOW_DAYS = 89
DEFAULT_FUNDING_REFRESH_HOURS = 12.0
MAX_RETRYABLE_MARK_TAIL_LAG = pd.Timedelta(hours=3)


def _read_panel(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"coin_id", "symbol"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"panel {path} is missing columns {sorted(missing)}")
    columns = ["coin_id", "symbol"]
    if "name" in frame.columns:
        columns.append("name")
    if "date" in frame.columns:
        columns.append("date")
    frame = frame.loc[:, columns].copy()
    frame["coin_id"] = frame["coin_id"].astype(str)
    frame["symbol"] = frame["symbol"].astype(str)
    return frame


def _iter_windows(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cursor = start
    while cursor < end:
        stop = min(cursor + pd.Timedelta(days=_WINDOW_DAYS), end)
        windows.append((cursor, stop))
        cursor = stop
    return windows


def _sample_windows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    count: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return ``count`` evenly spaced 7-day windows inside [start, end)."""
    if count <= 0:
        return _iter_windows(start, end)
    total_days = max((end - start).days, 1)
    window_days = min(7, max(total_days // max(count, 1), 1))
    offsets = [round(index * (total_days - window_days) / max(count - 1, 1)) for index in range(count)]
    return [
        (start + pd.Timedelta(days=offset), min(start + pd.Timedelta(days=offset + window_days), end))
        for offset in sorted(set(offsets))
    ]


def _load_state(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(path: Path, state: dict[str, dict[str, Any]]) -> None:
    atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True))


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    """Replace a cache CSV only after the complete new file is written."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _merge_candles(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in (existing, new) if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    combined["open_time"] = pd.to_datetime(combined["open_time"], utc=True)
    for column in CANDLE_COLUMNS[1:]:
        combined[column] = pd.to_numeric(combined[column], errors="coerce")
    combined = combined.drop_duplicates("open_time", keep="last").sort_values("open_time")
    return combined.reset_index(drop=True)


def _merge_coverage_rows(
    existing: object,
    refreshed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Replace refreshed coin/symbol/type rows without dropping aliases."""

    prior = [dict(row) for row in existing if isinstance(row, dict)] if isinstance(existing, list) else []
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in prior:
        coin_id = str(row.get("coin_id") or "").strip()
        symbol = str(row.get("bitget_symbol") or "").strip().upper()
        candle_type = str(row.get("candle_type") or "").strip().lower()
        if symbol and candle_type:
            by_key[(coin_id, symbol, candle_type)] = row
    for row in refreshed:
        coin_id = str(row.get("coin_id") or "").strip()
        symbol = str(row.get("bitget_symbol") or "").strip().upper()
        candle_type = str(row.get("candle_type") or "").strip().lower()
        if symbol and candle_type:
            by_key[(coin_id, symbol, candle_type)] = dict(row)
    return [by_key[key] for key in sorted(by_key)]



def _window_status(
    frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[str, int]:
    """Classify a fetched window without calling a gapped frame complete."""
    expected = max(int((end - start).total_seconds() // 3600), 0)
    if frame.empty:
        return "missing", expected
    times = pd.to_datetime(frame["open_time"], utc=True)
    actual = int(((times >= start) & (times < end)).sum())
    expected_index = pd.date_range(start, end, freq="h", inclusive="left")
    actual_index = pd.DatetimeIndex(times[(times >= start) & (times < end)])
    if actual >= expected and expected_index.difference(actual_index).empty:
        return "complete", expected
    return "partial", expected


def _cached_window_needs_refetch(cached_status: str | None, actual_status: str) -> bool:
    """Repair cached gaps instead of treating a stale status as final.

    Older caches were written before the page-boundary fix and can still say
    ``complete`` while the file is missing one hour per 100-row page.  A
    partial window is never final: fetch it once more and merge the exact API
    timestamps.  A known-missing listing window remains final.
    """

    if actual_status == "partial":
        return True
    return cached_status == "complete" and actual_status == "missing"


def _window_needs_refresh(window_end: pd.Timestamp, now: pd.Timestamp) -> bool:
    """Return whether a cached window can still grow with new hourly bars."""

    end = pd.Timestamp(window_end)
    current = pd.Timestamp(now)
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    else:
        end = end.tz_convert("UTC")
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    else:
        current = current.tz_convert("UTC")
    return end > current.floor("h")


def _mark_times(path: Path) -> pd.DatetimeIndex | None:
    """Read one cached mark file's open times, or ``None`` if unusable."""

    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None
    if frame.empty or "open_time" not in frame.columns:
        return None
    times = pd.to_datetime(frame["open_time"], utc=True, format="mixed", errors="coerce")
    valid = times.dropna().drop_duplicates().sort_values()
    return pd.DatetimeIndex(valid) if not valid.empty else None


def _mark_tail_gaps(
    symbol_map: pd.DataFrame,
    output_dir: Path,
    *,
    required_last: pd.Timestamp,
) -> tuple[list[str], list[str]]:
    """Split stale marks into retryable last-bar lag and deeper data gaps."""

    retryable: list[str] = []
    blocked: list[str] = []
    normal = symbol_map.loc[
        symbol_map["contract_status"].astype(str).str.lower().eq("normal")
    ]
    for record in normal.to_dict("records"):
        symbol = str(record.get("bitget_symbol") or "").strip().upper()
        if not symbol:
            continue
        times = _mark_times(output_dir / "candles" / f"{symbol}_mark.csv")
        if times is None:
            blocked.append(symbol)
            continue
        required = pd.Timestamp(required_last)
        if required in times:
            continue
        last = pd.Timestamp(times.max())
        lag = abs(last - required)
        if lag <= MAX_RETRYABLE_MARK_TAIL_LAG:
            retryable.append(symbol)
        else:
            blocked.append(symbol)
    return sorted(set(retryable)), sorted(set(blocked))


def _refresh_mark_tails(
    client: BitgetClient,
    symbols: list[str],
    output_dir: Path,
    *,
    required_last: pd.Timestamp,
) -> None:
    """Fetch only the two hours before the required bar and merge it atomically."""

    start = pd.Timestamp(required_last) - pd.Timedelta(hours=2)
    end = pd.Timestamp(required_last) + pd.Timedelta(hours=1)
    for symbol in symbols:
        path = output_dir / "candles" / f"{symbol}_mark.csv"
        try:
            existing = pd.read_csv(path)
        except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
            existing = pd.DataFrame(columns=CANDLE_COLUMNS)
        try:
            frame = client.fetch_history_candles(symbol, "mark", start, end)
        except Exception as exc:  # noqa: BLE001 - the next bounded poll can retry
            LOGGER.warning("live mark tail refresh %s failed: %s", symbol, exc)
            continue
        if frame.empty:
            continue
        _write_csv_atomic(_merge_candles(existing, frame), path)


def _wait_for_live_mark_tail(
    client: BitgetClient,
    symbol_map: pd.DataFrame,
    output_dir: Path,
    *,
    required_last: pd.Timestamp,
    max_wait_seconds: float,
    poll_seconds: float,
    sleep_fn: Callable[[float], None] = time_module.sleep,
    clock_fn: Callable[[], float] = time_module.monotonic,
) -> list[str]:
    """Wait for the live exchange to publish its last completed hourly mark bar."""

    if max_wait_seconds <= 0.0:
        raise ValueError("max_wait_seconds must be positive")
    if poll_seconds <= 0.0:
        raise ValueError("poll_seconds must be positive")
    required = pd.Timestamp(required_last)
    deadline = clock_fn() + float(max_wait_seconds)
    while True:
        retryable, blocked = _mark_tail_gaps(
            symbol_map,
            output_dir,
            required_last=required,
        )
        if not retryable and not blocked:
            return []
        if blocked:
            return sorted(set(retryable) | set(blocked))
        remaining = deadline - clock_fn()
        if remaining <= 0.0:
            return retryable
        wait_seconds = min(float(poll_seconds), remaining)
        LOGGER.warning(
            "waiting %.0fs for Bitget live mark %s on %s symbol(s)",
            wait_seconds,
            required,
            len(retryable),
        )
        sleep_fn(wait_seconds)
        _refresh_mark_tails(
            client,
            retryable,
            output_dir,
            required_last=required,
        )


def _max_gap_hours(frame: pd.DataFrame) -> float:
    if len(frame) < 2:
        return 0.0
    times = pd.to_datetime(frame["open_time"], utc=True).sort_values()
    gaps = times.diff().dropna().dt.total_seconds() / 3600.0
    return float(gaps.max()) if not gaps.empty else 0.0


def _max_gap_hours_within_windows(
    frame: pd.DataFrame,
    windows: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> float:
    if frame.empty:
        return 0.0
    max_gap = 0.0
    times = pd.to_datetime(frame["open_time"], utc=True)
    for start, end in windows:
        subset = frame.loc[(times >= start) & (times < end)]
        max_gap = max(max_gap, _max_gap_hours(subset))
    return max_gap


def _coverage_row(
    coin_id: str,
    symbol: str,
    candle_type: str,
    frame: pd.DataFrame,
    window_state: dict[str, Any],
    windows: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> dict[str, Any]:
    complete = sum(1 for value in window_state.values() if value.get("status") == "complete")
    missing = sum(1 for value in window_state.values() if value.get("status") == "missing")
    partial = sum(1 for value in window_state.values() if value.get("status") == "partial")
    return {
        "coin_id": coin_id,
        "bitget_symbol": symbol,
        "candle_type": candle_type,
        "rows": int(len(frame)),
        "first": frame["open_time"].min() if not frame.empty else pd.NaT,
        "last": frame["open_time"].max() if not frame.empty else pd.NaT,
        "complete_windows": complete,
        "missing_windows": missing,
        "partial_windows": partial,
        "window_coverage": (
            complete / (complete + missing + partial)
            if complete + missing + partial
            else 0.0
        ),
        "max_gap_hours": _max_gap_hours_within_windows(frame, windows),
    }


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_funding_publication(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    assets = payload.get("assets")
    return dict(assets) if isinstance(assets, dict) else {}


def _timestamp_ms(value: object) -> pd.Timestamp | None:
    try:
        milliseconds = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    if milliseconds <= 0:
        return None
    return pd.Timestamp(milliseconds, unit="ms", tz="UTC")


def _current_funding_observation(
    row: dict[str, Any],
) -> tuple[pd.Timestamp | None, float | None, float | None]:
    """Derive the last settled timestamp/rate from Bitget current-fund-rate.

    ``nextUpdate`` is the next settlement instant and ``fundingRateInterval``
    is the exchange's declared cadence.  Therefore the most recently settled
    funding timestamp is exactly ``nextUpdate - interval``.  This endpoint is
    independent of the paginated history endpoint and has remained available
    when history publication lagged during the live incident.
    """

    next_update = _timestamp_ms(row.get("nextUpdate"))
    try:
        interval = float(row.get("fundingRateInterval"))
        rate = float(row.get("lastFundingRate"))
    except (TypeError, ValueError):
        return None, None, None
    if (
        next_update is None
        or not math.isfinite(interval)
        or interval <= 0.0
        or not math.isfinite(rate)
    ):
        return None, None, None
    settlement = next_update - pd.Timedelta(hours=interval)
    return settlement, rate, interval


def _download_funding(
    client: BitgetClient,
    symbol_map: pd.DataFrame,
    output_dir: Path,
    *,
    force: bool,
    now: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Refresh stale funding caches while retaining older local history.

    The Bitget funding history endpoint returns a rolling window and can lag a
    settlement.  Every refresh therefore also reads the independent
    ``current-fund-rate`` endpoint: its ``lastFundingRate`` plus
    ``nextUpdate - fundingRateInterval`` identifies the latest settled row.
    The observation time and source are retained in ``funding_publication.json``
    so the data audit can prove that a required settlement was actually visible
    to this process, rather than inferring publication from wall-clock time.
    """

    current = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    else:
        current = current.tz_convert("UTC")
    funding_dir = ensure_dir(output_dir / "funding")
    publication_path = output_dir / "funding_publication.json"
    previous_publication = _load_funding_publication(publication_path)
    publication_entries: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    for record in symbol_map.to_dict("records"):
        if not record.get("bitget_symbol"):
            continue
        coin_id = str(record["coin_id"])
        symbol = str(record["bitget_symbol"])
        path = funding_dir / f"{coin_id}.csv"
        if path.exists():
            try:
                cached = pd.read_csv(path)
            except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
                LOGGER.warning("cached funding %s is unreadable (%s); refetching", path, exc)
                cached = pd.DataFrame()
        else:
            cached = pd.DataFrame()
        if not cached.empty:
            cached["funding_time"] = pd.to_datetime(
                cached["funding_time"], utc=True, errors="coerce"
            )
            cached["funding_rate"] = pd.to_numeric(
                cached["funding_rate"], errors="coerce"
            )
            cached = cached.dropna(subset=["funding_time", "funding_rate"])
        interval_raw = pd.to_numeric(record.get("fund_interval"), errors="coerce")
        interval_hours = float(interval_raw) if pd.notna(interval_raw) else 0.0
        last_cached = cached["funding_time"].max() if not cached.empty else pd.NaT
        cached_hash = _file_sha256(path)
        previous_entry = previous_publication.get(coin_id)
        preserved_entry = (
            previous_entry
            if isinstance(previous_entry, dict)
            and cached_hash is not None
            and previous_entry.get("funding_sha256") == cached_hash
            and str(previous_entry.get("funding_last") or "")
            == (str(last_cached) if not pd.isna(last_cached) else "")
            else None
        )
        # A cache is only fresh for its own settlement clock plus one hour of
        # provider publication lag.  The old max(12h, interval) rule let a 4h
        # asset miss two settlements while still being declared fresh, so the
        # downloader skipped the very refresh the live audit needed.
        stale_after_hours = (
            interval_hours + 1.0
            if interval_hours > 0.0
            else DEFAULT_FUNDING_REFRESH_HOURS
        )
        cached_is_fresh = (
            not pd.isna(last_cached)
            and (current - last_cached).total_seconds() / 3600.0 <= stale_after_hours
        )
        if not force and cached_is_fresh:
            if not cached.empty:
                manifest[coin_id] = {
                    "symbol": symbol,
                    "rows": int(len(cached)),
                    "first": str(cached["funding_time"].min()),
                    "last": str(cached["funding_time"].max()),
                    "cached": True,
                }
                if preserved_entry is not None:
                    publication_entries[coin_id] = preserved_entry
                continue
        def cached_entry(error: str | None = None) -> dict[str, Any]:
            entry: dict[str, Any] = {
                "symbol": symbol,
                "rows": int(len(cached)),
                "first": str(cached["funding_time"].min()),
                "last": str(cached["funding_time"].max()),
                "cached": True,
            }
            if error is not None:
                entry["refresh_error"] = error
            return entry

        history_request_time_ms: int | None = None
        history_frame = pd.DataFrame()
        try:
            history_frame = client.fetch_funding_history(symbol)
            raw_history_time = history_frame.attrs.get("request_time_ms")
            if raw_history_time is None:
                raw_history_time = getattr(client, "last_request_time_ms", None)
            if raw_history_time is not None:
                history_request_time_ms = int(raw_history_time)
        except Exception as exc:  # noqa: BLE001 - one bad contract must not abort the audit
            LOGGER.warning("funding %s (%s) failed: %s", coin_id, symbol, exc)
            # A transient endpoint failure is not evidence that the cached
            # rows disappeared.  Keep the old manifest identity so the data
            # audit can distinguish a refresh warning from an actual gap;
            # settlement coverage still fails closed if the cache is stale.
            manifest[coin_id] = (
                cached_entry(str(exc))
                if not cached.empty
                else {"symbol": symbol, "available": False, "error": str(exc)}
            )
            if preserved_entry is not None:
                publication_entries[coin_id] = preserved_entry
            continue
        if history_frame.empty:
            manifest[coin_id] = (
                cached_entry("no funding rows returned")
                if not cached.empty
                else {
                    "symbol": symbol,
                    "available": False,
                    "reason": "no funding rows",
                }
            )
            if preserved_entry is not None:
                publication_entries[coin_id] = preserved_entry
            continue
        history_frame["funding_time"] = pd.to_datetime(
            history_frame["funding_time"], utc=True, errors="coerce"
        )
        history_frame["funding_rate"] = pd.to_numeric(
            history_frame["funding_rate"], errors="coerce"
        )
        history_frame = history_frame.dropna(
            subset=["funding_time", "funding_rate"]
        ).sort_values("funding_time")
        history_last = (
            pd.Timestamp(history_frame["funding_time"].max())
            if not history_frame.empty
            else pd.NaT
        )
        frames = [item for item in (cached, history_frame) if not item.empty]
        merged = pd.concat(frames, ignore_index=True)
        merged["funding_time"] = pd.to_datetime(
            merged["funding_time"], utc=True, errors="coerce"
        )
        merged["funding_rate"] = pd.to_numeric(merged["funding_rate"], errors="coerce")
        merged = (
            merged.dropna(subset=["funding_time", "funding_rate"])
            .drop_duplicates("funding_time", keep="last")
            .sort_values("funding_time")
            .reset_index(drop=True)
        )

        current_row: dict[str, Any] = {}
        current_request_time_ms: int | None = None
        current_error: str | None = None
        current_settlement: pd.Timestamp | None = None
        current_rate: float | None = None
        api_interval_hours: float | None = None
        current_funding_fn = getattr(client, "fetch_current_funding", None)
        if callable(current_funding_fn):
            try:
                raw_current = current_funding_fn(symbol)
                if isinstance(raw_current, dict):
                    current_row = dict(raw_current)
                raw_current_time = getattr(client, "last_request_time_ms", None)
                if raw_current_time is not None:
                    current_request_time_ms = int(raw_current_time)
                current_settlement, current_rate, api_interval_hours = (
                    _current_funding_observation(current_row)
                )
            except Exception as exc:  # noqa: BLE001 - history remains usable
                current_error = str(exc)
                LOGGER.warning(
                    "current funding %s (%s) failed: %s", coin_id, symbol, exc
                )

        rate_relation = "unavailable"
        latest_source = "history"
        history_rate_at_current: float | None = None
        if current_settlement is not None and current_rate is not None:
            existing = merged.loc[merged["funding_time"] == current_settlement]
            history_matches = history_frame.loc[
                history_frame["funding_time"] == current_settlement
            ]
            if not history_matches.empty:
                history_rate_at_current = float(
                    history_matches["funding_rate"].iloc[-1]
                )
            if current_settlement > history_last or history_last is pd.NaT:
                if existing.empty:
                    merged = pd.concat(
                        [
                            merged,
                            pd.DataFrame(
                                {
                                    "symbol": [symbol],
                                    "funding_time": [current_settlement],
                                    "funding_rate": [current_rate],
                                }
                            ),
                        ],
                        ignore_index=True,
                    )
                    rate_relation = "fallback"
                    latest_source = "current_fund_rate"
                else:
                    existing_rate = float(existing["funding_rate"].iloc[-1])
                    if math.isclose(
                        existing_rate,
                        current_rate,
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    ):
                        rate_relation = "match"
                    else:
                        rate_relation = "conflict"
                    latest_source = "history"
            elif current_settlement == history_last:
                existing_rate = (
                    float(existing["funding_rate"].iloc[-1])
                    if not existing.empty
                    else None
                )
                if existing_rate is None:
                    merged = pd.concat(
                        [
                            merged,
                            pd.DataFrame(
                                {
                                    "symbol": [symbol],
                                    "funding_time": [current_settlement],
                                    "funding_rate": [current_rate],
                                }
                            ),
                        ],
                        ignore_index=True,
                    )
                    rate_relation = "fallback"
                    latest_source = "current_fund_rate"
                elif math.isclose(
                    existing_rate,
                    current_rate,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ):
                    rate_relation = "match"
                else:
                    rate_relation = "conflict"
            else:
                rate_relation = "history_ahead"

        merged = (
            merged.drop_duplicates("funding_time", keep="last")
            .sort_values("funding_time")
            .reset_index(drop=True)
        )
        _write_csv_atomic(merged, path)
        actual_last = pd.Timestamp(merged["funding_time"].max())
        actual_rate = float(merged["funding_rate"].iloc[-1])
        manifest[coin_id] = {
            "symbol": symbol,
            "rows": int(len(merged)),
            "first": str(merged["funding_time"].min()),
            "last": str(actual_last),
            "cached": False,
        }

        request_times = [
            value
            for value in (history_request_time_ms, current_request_time_ms)
            if value is not None
        ]
        verified_at = (
            pd.Timestamp(max(request_times), unit="ms", tz="UTC")
            if request_times
            else None
        )
        history_requested_at = (
            pd.Timestamp(history_request_time_ms, unit="ms", tz="UTC")
            if history_request_time_ms is not None
            else None
        )
        publication_entries[coin_id] = {
            "symbol": symbol,
            "funding_sha256": _file_sha256(path),
            "funding_last": str(actual_last),
            "funding_rate": actual_rate,
            "history_last": None if pd.isna(history_last) else str(history_last),
            "history_request_time": (
                history_requested_at.isoformat() if history_requested_at else None
            ),
            "current_settlement_time": (
                current_settlement.isoformat() if current_settlement else None
            ),
            "current_funding_rate": current_rate,
            "current_request_time": (
                pd.Timestamp(current_request_time_ms, unit="ms", tz="UTC").isoformat()
                if current_request_time_ms is not None
                else None
            ),
            "api_interval_hours": api_interval_hours,
            "contract_interval_hours": interval_hours if interval_hours > 0.0 else None,
            "interval_matches_contract": bool(
                api_interval_hours is not None
                and interval_hours > 0.0
                and math.isclose(api_interval_hours, interval_hours, abs_tol=1e-9)
            ),
            "history_rate_at_current_settlement": history_rate_at_current,
            "rate_relation": rate_relation,
            "latest_source": latest_source,
            "verified_at": verified_at.isoformat() if verified_at else None,
            "publication_lag_seconds": (
                (verified_at - actual_last).total_seconds() if verified_at else None
            ),
            "history_lag_seconds": (
                (history_requested_at - history_last).total_seconds()
                if history_requested_at is not None and not pd.isna(history_last)
                else None
            ),
            "current_funding_error": current_error,
        }
    manifest_path = output_dir / "funding_manifest.json"
    persisted: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, dict):
            persisted = existing
    persisted.update(manifest)
    atomic_write_text(
        manifest_path,
        json.dumps(persisted, indent=2, sort_keys=True),
    )
    publication_payload = {
        "version": 1,
        "generated_at": current.isoformat(),
        "assets": {
            **previous_publication,
            **publication_entries,
        },
    }
    atomic_write_text(
        publication_path,
        json.dumps(publication_payload, indent=2, sort_keys=True),
    )
    return persisted


def _archive_contract_snapshot(
    output_dir: Path,
    contracts: list[dict[str, Any]],
    *,
    captured_at: pd.Timestamp,
    request_time_ms: int | None,
) -> dict[str, Any]:
    """Persist contract metadata change points with content identity.

    Repeated observations of unchanged metadata update ``last_seen_at`` in the
    index instead of writing a large duplicate file.  A changed payload creates
    a new immutable snapshot, which lets later research distinguish a genuine
    venue specification change from using today's contract table as history.
    """

    moment = pd.Timestamp(captured_at)
    if moment.tzinfo is None:
        moment = moment.tz_localize("UTC")
    else:
        moment = moment.tz_convert("UTC")
    canonical = json.dumps(contracts, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    snapshot_dir = ensure_dir(output_dir / "contract_snapshots")
    index_path = snapshot_dir / "index.json"
    payload: dict[str, Any] = {}
    if index_path.is_file():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                payload = existing
        except (OSError, json.JSONDecodeError):
            payload = {}
    snapshots = payload.get("snapshots")
    entries = list(snapshots) if isinstance(snapshots, list) else []
    request_time = (
        pd.Timestamp(request_time_ms, unit="ms", tz="UTC").isoformat()
        if request_time_ms is not None
        else None
    )
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get("sha256") != digest:
            continue
        updated = dict(entry)
        updated["last_seen_at"] = moment.isoformat()
        updated["last_request_time"] = request_time
        entries[index] = updated
        atomic_write_text(
            index_path,
            json.dumps(
                {"version": 1, "snapshots": entries}, indent=2, sort_keys=True
            )
            + "\n",
        )
        return updated

    filename = f"contracts_{moment.strftime('%Y%m%dT%H%M%SZ')}_{digest[:12]}.json"
    snapshot_path = snapshot_dir / filename
    snapshot_payload = {
        "captured_at": moment.isoformat(),
        "request_time": request_time,
        "contracts_sha256": digest,
        "rows": len(contracts),
        "contracts": contracts,
    }
    atomic_write_text(
        snapshot_path,
        json.dumps(snapshot_payload, indent=2, sort_keys=True) + "\n",
    )
    entry = {
        "path": str(snapshot_path.relative_to(output_dir)),
        "sha256": digest,
        "rows": len(contracts),
        "first_seen_at": moment.isoformat(),
        "last_seen_at": moment.isoformat(),
        "first_request_time": request_time,
        "last_request_time": request_time,
    }
    entries.append(entry)
    entries.sort(key=lambda item: str(item.get("first_seen_at") or ""))
    atomic_write_text(
        index_path,
        json.dumps({"version": 1, "snapshots": entries}, indent=2, sort_keys=True)
        + "\n",
    )
    return entry


def _parse_clock(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not HH:MM") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--panel", type=Path, default=Path("data/processed/panel_daily.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/bitget_derivatives"))
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2026-09-21")
    parser.add_argument("--types", default=",".join(DEFAULT_TYPES))
    parser.add_argument("--symbols", default="", help="Comma-separated coin ids or Bitget symbols")
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument("--sample-windows", type=int, default=0, help="0 downloads the full range")
    parser.add_argument("--max-requests", type=int, default=0, help="0 means unlimited")
    parser.add_argument("--rate-limit-seconds", type=float, default=0.05)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--client-retries", type=int, default=4)
    parser.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--funding-only", action="store_true")
    parser.add_argument("--skip-funding", action="store_true")
    parser.add_argument(
        "--wait-for-live-mark-seconds",
        type=float,
        default=0.0,
        help="bounded wait for the last completed live mark bar",
    )
    parser.add_argument(
        "--wait-for-live-mark-poll-seconds",
        type=float,
        default=30.0,
        help="poll interval used by --wait-for-live-mark-seconds",
    )
    parser.add_argument(
        "--execution-utc",
        type=_parse_clock,
        default=time(1, 5),
        help="live fill clock used to derive the required completed mark bar",
    )
    args = parser.parse_args()
    configure_logging("INFO")

    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    if end <= start:
        raise SystemExit("--end must be after --start")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    if args.client_retries < 1:
        raise SystemExit("--client-retries must be at least 1")
    if args.retry_backoff_seconds < 0:
        raise SystemExit("--retry-backoff-seconds must be non-negative")
    if args.wait_for_live_mark_seconds < 0:
        raise SystemExit("--wait-for-live-mark-seconds must be non-negative")
    if args.wait_for_live_mark_poll_seconds <= 0:
        raise SystemExit("--wait-for-live-mark-poll-seconds must be positive")
    types = [item.strip() for item in args.types.split(",") if item.strip()]
    output_dir = ensure_dir(args.output_dir)
    candle_dir = ensure_dir(output_dir / "candles")
    state_path = output_dir / "state.json"
    state = _load_state(state_path)

    panel = _read_panel(args.panel)
    client = BitgetClient(
        timeout_seconds=args.timeout_seconds,
        max_retries=args.client_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        rate_limit_seconds=args.rate_limit_seconds,
    )
    contracts = client.fetch_contracts()
    symbol_map = build_symbol_map(panel, contracts)
    _write_csv_atomic(symbol_map, output_dir / "symbol_map.csv")
    atomic_write_text(
        output_dir / "contracts.json", json.dumps(contracts, indent=2, sort_keys=True)
    )
    _archive_contract_snapshot(
        output_dir,
        contracts,
        captured_at=pd.Timestamp.now(tz="UTC"),
        request_time_ms=getattr(client, "last_request_time_ms", None),
    )
    LOGGER.info("Bitget contracts: %s; mapped coins: %s", len(contracts), int(symbol_map["bitget_symbol"].ne("").sum()))

    selected = symbol_map[symbol_map["bitget_symbol"].ne("")].copy()
    if args.symbols:
        wanted = {item.strip().lower() for item in args.symbols.split(",") if item.strip()}
        selected = selected[
            selected["coin_id"].str.lower().isin(wanted)
            | selected["bitget_symbol"].str.lower().isin(wanted)
        ]
    if args.max_symbols > 0:
        selected = selected.head(args.max_symbols)
    if selected.empty:
        raise SystemExit("no Bitget contracts selected")

    if not args.skip_funding:
        _download_funding(client, selected, output_dir, force=args.force)
    if args.funding_only:
        print(f"wrote {output_dir} (funding only)")
        return

    windows = (
        _sample_windows(start, end, args.sample_windows)
        if args.sample_windows > 0
        else _iter_windows(start, end)
    )
    now = pd.Timestamp.now(tz="UTC")
    LOGGER.info("candle windows: %s x %s symbols x %s types", len(windows), len(selected), len(types))

    coverage_rows: list[dict[str, Any]] = []
    for record in selected.to_dict("records"):
        coin_id = str(record["coin_id"])
        symbol = str(record["bitget_symbol"])
        for candle_type in types:
            state_key = f"{symbol}_{candle_type}"
            window_state: dict[str, Any] = state.setdefault(state_key, {})
            path = candle_dir / f"{symbol}_{candle_type}.csv"
            if path.exists() and not args.force:
                try:
                    existing = pd.read_csv(path)
                except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
                    LOGGER.warning("cached candles %s are unreadable (%s); refetching", path, exc)
                    existing = pd.DataFrame(columns=CANDLE_COLUMNS)
            else:
                existing = pd.DataFrame(columns=CANDLE_COLUMNS)
            for window_start, window_end in windows:
                key = window_start.isoformat()
                cached_status = window_state.get(key, {}).get("status")
                if _window_needs_refresh(window_end, now):
                    cached_status = None
                if not args.force and cached_status in {"complete", "missing", "partial"}:
                    cached_frame = existing.loc[
                        (pd.to_datetime(existing["open_time"], utc=True) >= window_start)
                        & (pd.to_datetime(existing["open_time"], utc=True) < window_end)
                    ]
                    actual_status, _ = _window_status(
                        cached_frame,
                        window_start,
                        window_end,
                    )
                    if not _cached_window_needs_refetch(cached_status, actual_status):
                        window_state[key]["status"] = actual_status
                        _save_state(state_path, state)
                        continue
                if args.max_requests > 0 and client.request_count >= args.max_requests:
                    LOGGER.warning("request budget reached at %s %s", symbol, candle_type)
                    break
                try:
                    frame = client.fetch_history_candles(symbol, candle_type, window_start, window_end)
                except Exception as exc:  # noqa: BLE001 - keep the audit moving across contracts
                    LOGGER.warning("%s %s %s failed: %s", coin_id, symbol, candle_type, exc)
                    window_state[key] = {"status": "error", "error": str(exc)}
                    _save_state(state_path, state)
                    continue
                existing = _merge_candles(existing, frame)
                status, expected_rows = _window_status(frame, window_start, window_end)
                window_state[key] = {
                    "status": status,
                    "rows": int(len(frame)),
                    "expected_rows": int(expected_rows),
                }
                _save_state(state_path, state)
            _write_csv_atomic(existing, path)
            coverage_rows.append(_coverage_row(coin_id, symbol, candle_type, existing, window_state, windows))
            last_open = existing["open_time"].max() if not existing.empty else "missing"
            LOGGER.info(
                "%s %s: %s rows, last=%s, %s complete windows, %s missing",
                symbol,
                candle_type,
                len(existing),
                last_open,
                window_state and sum(1 for value in window_state.values() if value.get("status") == "complete"),
                sum(1 for value in window_state.values() if value.get("status") == "missing"),
            )

    if args.wait_for_live_mark_seconds > 0.0:
        required_last = required_last_mark_time(
            pd.Timestamp.now(tz="UTC").to_pydatetime(),
            execution_utc=args.execution_utc,
        )
        LOGGER.info("live mark requirement: %s", required_last)
        stale_marks = _wait_for_live_mark_tail(
            client,
            selected,
            output_dir,
            required_last=required_last,
            max_wait_seconds=float(args.wait_for_live_mark_seconds),
            poll_seconds=float(args.wait_for_live_mark_poll_seconds),
        )
        for row in coverage_rows:
            if row.get("candle_type") != "mark":
                continue
            path = candle_dir / f"{row['bitget_symbol']}_mark.csv"
            try:
                refreshed = pd.read_csv(path)
            except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
                continue
            row["rows"] = int(len(refreshed))
            row["first"] = refreshed["open_time"].min() if not refreshed.empty else pd.NaT
            row["last"] = refreshed["open_time"].max() if not refreshed.empty else pd.NaT
            row["max_gap_hours"] = _max_gap_hours_within_windows(refreshed, windows)
        try:
            existing_coverage = json.loads(
                (output_dir / "coverage.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            existing_coverage = []
        coverage_rows = _merge_coverage_rows(existing_coverage, coverage_rows)
        coverage = pd.DataFrame(coverage_rows)
        _write_csv_atomic(coverage, output_dir / "coverage.csv")
        atomic_write_text(
            output_dir / "coverage.json",
            json.dumps(coverage_rows, indent=2, sort_keys=True, default=str),
        )
        if stale_marks:
            raise SystemExit(
                "Bitget live mark feed is still missing the required completed bar "
                f"{required_last} for {len(stale_marks)} symbol(s): "
                + ", ".join(stale_marks[:10])
            )
    try:
        existing_coverage = json.loads(
            (output_dir / "coverage.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        existing_coverage = []
    coverage_rows = _merge_coverage_rows(existing_coverage, coverage_rows)
    coverage = pd.DataFrame(coverage_rows)
    _write_csv_atomic(coverage, output_dir / "coverage.csv")
    atomic_write_text(
        output_dir / "coverage.json",
        json.dumps(coverage_rows, indent=2, sort_keys=True, default=str),
    )
    print(f"wrote {output_dir} ({len(selected)} symbols, {client.request_count} requests)")


if __name__ == "__main__":
    main()
