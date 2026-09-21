"""Daily data-refresh freshness checks and heartbeat state.

The refresh worker writes a small heartbeat after every attempt.  The API can
then answer a different question from "did a process return 200?": did a
successful refresh actually arrive before today's deadline, and did the primary
provider's latest date advance?
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
import logging
from math import ceil
from pathlib import Path
from typing import Any

from atlas20.api._time import utc_now
from atlas20.api.settings import Settings, get_settings

logger = logging.getLogger(__name__)

FRESHNESS_FILENAME = "data_freshness.json"
BAD_STATUSES = {"stale", "missing", "failed", "stalled"}


def _iso(value: datetime) -> str:
    return _ensure_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_datetime(value: object) -> datetime | None:
    if value is None or not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_date(value: object) -> date | None:
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_int(value: object, *, default: int = 0) -> int:
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (ValueError, OverflowError):
            return default
    return default


def _state_source_dates(state: dict[str, Any] | None) -> dict[str, date | None]:
    keys = ("coinmarketcap", "gateio", "binance", "coingecko", "coinpaprika")
    raw = state.get("source_dates") if state else None
    if not isinstance(raw, dict):
        return {key: None for key in keys}
    return {key: _parse_date(raw.get(key)) for key in keys}


def _same_primary_success_dates(previous: dict[str, Any], primary: date) -> set[date]:
    """UTC dates on which a successful refresh reported the same primary date."""
    dates: set[date] = set()
    history = previous.get("history")
    if isinstance(history, list):
        for entry in history:
            if not isinstance(entry, dict) or entry.get("status") != "completed":
                continue
            if _parse_date(entry.get("latest_primary_date")) != primary:
                continue
            checked_at = _parse_datetime(entry.get("checked_at"))
            if checked_at is not None:
                dates.add(checked_at.date())

    previous_primary = _parse_date(previous.get("latest_primary_date"))
    previous_success_at = _parse_datetime(previous.get("last_success_at"))
    if previous_primary == primary and previous_success_at is not None:
        dates.add(previous_success_at.date())
    return dates


def primary_lags_last_completed_day(settings: Settings) -> bool:
    """True when the primary feed has not yet landed the last completed day.

    CMC finalises day D's close somewhere after 00:00 UTC on D+1 and is
    occasionally still publishing when the daily job fires. A single miss
    therefore used to mean a full day of trading on stale ranks, because the
    next scheduled opportunity was 24 hours away. Asking the question directly -
    "is yesterday's close on disk yet?" - is what lets the scheduler try again
    the same day.
    """
    state = read_refresh_state(settings)
    primary = _parse_date(state.get("latest_primary_date")) if state else None
    if primary is None:
        primary = _latest_cmc_date(_raw_dir(settings))
    if primary is None:
        return True
    return primary < (utc_now().date() - timedelta(days=1))


def freshness_path(settings: Settings) -> Path:
    return Path(settings.data_root) / FRESHNESS_FILENAME


def _raw_dir(settings: Settings) -> Path:
    return Path(settings.data_root) / "raw"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_refresh_state(settings: Settings) -> dict[str, Any] | None:
    payload = _read_json(freshness_path(settings))
    return payload if isinstance(payload, dict) else None


def _latest_cmc_date(raw_dir: Path, *, min_coverage: float = 0.9) -> date | None:
    directory = raw_dir / "coinmarketcap" / "history"
    dates_by_coin: dict[str, set[date]] = {}
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        payload = _read_json(path)
        if not isinstance(payload, list):
            continue
        coin_id = path.stem.split("_", 1)[0]
        coin_dates = dates_by_coin.setdefault(coin_id, set())
        for row in payload:
            if not isinstance(row, dict):
                continue
            opened = row.get("timeOpen")
            parsed = _parse_date(opened)
            if parsed is not None:
                coin_dates.add(parsed)
    if not dates_by_coin:
        return None
    all_dates = sorted(set().union(*dates_by_coin.values()))
    required = max(1, ceil(len(dates_by_coin) * min_coverage))
    for candidate in reversed(all_dates):
        covered = sum(candidate in dates for dates in dates_by_coin.values())
        if covered >= required:
            return candidate
    return None


def _latest_exchange_date(raw_dir: Path, venue: str, *, milliseconds: bool) -> date | None:
    """Newest day carried by an exchange-candle cache.

    Both venues cache daily candles as a list of arrays whose first element is
    the candle's open time; they only differ in units (Gate.io reports seconds,
    Binance milliseconds), so one reader covers both.
    """
    directory = raw_dir / venue / "candles"
    scale = 1000.0 if milliseconds else 1.0
    latest: date | None = None
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        payload = _read_json(path)
        if not isinstance(payload, list):
            continue
        for row in payload:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            try:
                parsed = datetime.fromtimestamp(int(float(row[0])) / scale, tz=timezone.utc).date()
            except (TypeError, ValueError, OverflowError):
                continue
            if latest is None or parsed > latest:
                latest = parsed
    return latest


def _latest_coingecko_date(raw_dir: Path) -> date | None:
    directory = raw_dir / "coingecko" / "market_chart"
    latest: date | None = None
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        payload = _read_json(path)
        prices = payload.get("prices") if isinstance(payload, dict) else None
        if not isinstance(prices, list):
            continue
        for row in prices:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            try:
                parsed = datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc).date()
            except (TypeError, ValueError, OverflowError):
                continue
            if latest is None or parsed > latest:
                latest = parsed
    return latest


def _latest_coinpaprika_date(raw_dir: Path) -> date | None:
    directory = raw_dir / "coinpaprika" / "history"
    latest: date | None = None
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        payload = _read_json(path)
        if not isinstance(payload, list):
            continue
        for row in payload:
            if not isinstance(row, dict):
                continue
            parsed = _parse_date(row.get("timestamp"))
            if parsed is not None and (latest is None or parsed > latest):
                latest = parsed
    return latest


def _source_dates(raw_dir: Path, *, min_primary_coverage: float = 0.9) -> dict[str, date | None]:
    return {
        "coinmarketcap": _latest_cmc_date(raw_dir, min_coverage=min_primary_coverage),
        "gateio": _latest_exchange_date(raw_dir, "gateio", milliseconds=False),
        "binance": _latest_exchange_date(raw_dir, "binance", milliseconds=True),
        "coingecko": _latest_coingecko_date(raw_dir),
        "coinpaprika": _latest_coinpaprika_date(raw_dir),
    }


def write_refresh_state(
    settings: Settings,
    *,
    run_id: str,
    status: str,
    error: str | None = None,
    now: datetime | None = None,
) -> Path:
    """Persist the result of one refresh attempt atomically."""
    now = _ensure_utc(now or utc_now())
    previous = read_refresh_state(settings) or {}
    raw_dir = _raw_dir(settings)
    source_dates = _source_dates(
        raw_dir,
        min_primary_coverage=settings.data_freshness_min_primary_coverage,
    )
    primary = source_dates["coinmarketcap"]
    independent_dates = [value for key, value in source_dates.items() if key != "coinmarketcap" and value is not None]
    independent = max(independent_dates) if independent_dates else None
    previous_primary = _parse_date(previous.get("latest_primary_date"))
    if previous_primary is None:
        previous_primary = _state_source_dates(previous)["coinmarketcap"]

    last_success_at: str | None
    last_success_date: str | None
    no_advance_since: date | None
    if status == "completed":
        same_primary = previous_primary is not None and primary is not None and primary == previous_primary
        if same_primary:
            # Count calendar days, not refresh attempts. A same-day catch-up
            # retry that still sees the same CMC date must not turn a healthy
            # feed into "stalled" simply because it ran twice. The explicit
            # since-date also repairs legacy states whose counter double-counted
            # same-day retries before this field existed.
            no_advance_since = _parse_date(previous.get("no_advance_since"))
            if no_advance_since is None:
                assert primary is not None
                prior_dates = _same_primary_success_dates(previous, primary)
                no_advance_since = min(prior_dates) if prior_dates else now.date()
        else:
            no_advance_since = now.date()
        no_advance_days = max(0, (now.date() - no_advance_since).days)
        last_success_at = _iso(now)
        last_success_date = _iso_date(primary)
    else:
        no_advance_days = _parse_int(previous.get("no_advance_days"))
        no_advance_since = _parse_date(previous.get("no_advance_since"))
        previous_last_success = _parse_datetime(previous.get("last_success_at"))
        previous_last_success_date = _parse_date(previous.get("last_success_date"))
        last_success_at = _iso(previous_last_success) if previous_last_success is not None else None
        last_success_date = _iso_date(previous_last_success_date)

    previous_history = previous.get("history")
    history = list(previous_history) if isinstance(previous_history, list) else []
    history.append(
        {
            "checked_at": _iso(now),
            "status": status,
            "run_id": run_id,
            "latest_primary_date": _iso_date(primary),
            "no_advance_days": no_advance_days,
            "error": error,
        }
    )
    payload = {
        "checked_at": _iso(now),
        "status": status,
        "run_id": run_id,
        "error": error,
        "latest_primary_date": _iso_date(primary),
        "latest_independent_date": _iso_date(independent),
        "source_dates": {key: _iso_date(value) for key, value in source_dates.items()},
        "last_success_at": last_success_at,
        "last_success_date": last_success_date,
        "no_advance_days": no_advance_days,
        "no_advance_since": _iso_date(no_advance_since),
        "history": history[-7:],
    }
    path = freshness_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path


def _scheduled_for(settings: Settings, now: datetime) -> datetime:
    return datetime.combine(
        now.date(),
        time(hour=settings.daily_refresh_hour_utc, minute=settings.daily_refresh_minute_utc),
        tzinfo=timezone.utc,
    )


def evaluate_data_freshness(settings: Settings, *, now: datetime | None = None) -> dict[str, Any]:
    """Return the current daily-data freshness state without raising."""
    now = _ensure_utc(now or utc_now())
    state = read_refresh_state(settings)
    source_dates = _state_source_dates(state)
    primary = _parse_date(state.get("latest_primary_date")) if state else None
    if primary is None:
        primary = source_dates["coinmarketcap"]
    independent = _parse_date(state.get("latest_independent_date")) if state else None
    if independent is None:
        independent_dates = [
            value for key, value in source_dates.items() if key != "coinmarketcap" and value is not None
        ]
        independent = max(independent_dates) if independent_dates else None

    scheduled_for = _scheduled_for(settings, now)
    deadline = scheduled_for + timedelta(minutes=settings.daily_refresh_grace_minutes)
    checked_at = _parse_datetime(state.get("checked_at")) if state else None
    last_success_at = _parse_datetime(state.get("last_success_at")) if state else None
    no_advance_days = _parse_int(state.get("no_advance_days")) if state else 0
    state_status = str(state.get("status") or "") if state else ""
    state_error = str(state.get("error") or "") if state else ""

    status: str
    reason: str
    if not settings.daily_refresh_enabled:
        status, reason = "disabled", "daily refresh is disabled"
    elif primary is not None and primary > now.date():
        status = "stale"
        reason = f"primary data date {primary.isoformat()} is in the future"
    elif primary is not None and (now.date() - primary).days > settings.data_freshness_max_primary_lag_days:
        status = "stale"
        reason = (
            f"primary data lag {(now.date() - primary).days}d exceeds "
            f"{settings.data_freshness_max_primary_lag_days}d"
        )
    elif state_status == "failed" and checked_at is not None and checked_at.date() == now.date():
        status, reason = "failed", state_error or "today's refresh failed"
    elif last_success_at is not None and last_success_at.date() == now.date():
        if no_advance_days >= settings.data_freshness_max_no_advance_days:
            status = "stalled"
            reason = f"primary date did not advance for {no_advance_days} calendar day(s)"
        elif primary is None:
            status, reason = "stale", "refresh completed without a primary date"
        else:
            status, reason = "ok", "today's refresh completed"
    elif now < deadline:
        status = "running" if state_status == "running" else "pending"
        reason = f"waiting for today's refresh deadline {_iso(deadline)}"
    else:
        status = "missing" if state is None else "stale"
        reason = f"no successful refresh by {_iso(deadline)}"

    return {
        "status": status,
        "reason": reason,
        "checked_at": _iso(now),
        "last_success_at": _iso(last_success_at) if last_success_at is not None else None,
        "last_success_date": _iso_date(primary),
        "latest_primary_date": _iso_date(primary),
        "latest_independent_date": _iso_date(independent),
        "scheduled_for": _iso(scheduled_for),
        "deadline": _iso(deadline),
        "no_advance_days": no_advance_days,
        "source_dates": {key: _iso_date(value) for key, value in source_dates.items()},
    }


def freshness_alert(settings: Settings, *, now: datetime | None = None) -> dict[str, Any] | None:
    """Return a DataAlert-shaped payload when daily data is not healthy."""
    status = evaluate_data_freshness(settings, now=now)
    if status["status"] not in BAD_STATUSES:
        return None
    title_by_status = {
        "stale": "data feed stale",
        "missing": "daily refresh missing",
        "failed": "daily refresh failed",
        "stalled": "data feed stalled",
    }
    return {
        "id": "data_freshness",
        "severity": "rose",
        "title": title_by_status.get(status["status"], "data freshness alert"),
        "meta": status["reason"],
        "ts": status["checked_at"],
        "icon": "alert-triangle",
        "source": "real",
    }


def log_data_freshness(settings: Settings | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    status = evaluate_data_freshness(settings, now=now)
    extra = {"data_freshness": status}
    if status["status"] in BAD_STATUSES:
        logger.error("data freshness alert: %s", status["status"], extra=extra)
    else:
        logger.info("data freshness: %s", status["status"], extra=extra)
    return status
