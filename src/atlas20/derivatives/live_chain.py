"""Preflight gates for the daily live derivatives chain.

``ops/run_derivatives_daily.sh`` runs the panel refresh, the Bitget mark
refresh, the frozen target book and the real order placement in one launchd
job, because the executor refuses to trade when the book was not evaluated
through the newest completed day.  That guard is correct, but on its own it
turns two ordinary events into a silently skipped rebalance:

* a shutdown or reboot in the middle of the panel refresh leaves
  ``data/processed/panel_daily.csv`` a day behind while the Bitget marks keep
  moving (this happened on 2026-10-16: the machine went down at 10:34, the
  panel stayed on 10-14, and the legacy 11:05 trade job failed closed);
* the machine can simply be off at the scheduled fire time, so the day is
  never attempted at all.

This module holds the two decisions the wrapper needs, as pure functions so
they can be tested without launchd, a network, or an account:

1. :func:`panel_lags_last_completed_day` - is the panel the strategy reads
   still missing the last completed UTC day?  If so the wrapper refreshes it
   once before spending money.
2. :func:`within_run_window` plus :func:`run_day_already_done` - should the
   chain run at all right now?  This lets the job be loaded at boot
   (``RunAtLoad``) without either trading twice or trading outside the
   bounded catch-up window after the model's T+1 fill point.

Nothing here weakens the executor's own guards: they remain the final
backstop and still fail closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

import pandas as pd

from atlas20.data.completeness import assess_last_day

#: The single LS45 execution clock, in UTC: 09:05 Beijing.  Signal ledgers,
#: backtests, preflight and the live executor all target this same minute.
LIVE_EXECUTION_UTC = time(1, 5)
DEFAULT_SCHEDULED_UTC = LIVE_EXECUTION_UTC

#: How long after the fill point a missed run may still be caught up.  Beyond
#: this the rebalance is skipped and the 19:00 monitor reports the gap, because
#: executing a daily signal many hours late is a different trade.
DEFAULT_CATCHUP_HOURS = 6.0

PANEL_FILENAME = "panel_daily.csv"
# The live universe is a point-in-time Top20; a panel with only the old
# calibration minimum of ten names must not be accepted as an executable panel.
LIVE_PANEL_MIN_ASSETS = 20

# This is deliberately a pin, not a second source of strategy parameters.  The
# research wrapper writes the same values into its manifest; a mismatch means
# the live executor is looking at a different frozen book and must fail closed.
LS45_G125_SPEC = "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
LS45_G125_FROZEN_CONFIG: dict[str, Any] = {
    "bear_funding_lookback_settlements": 3,
    "bear_funding_threshold": -0.0002,
    "bear_lookback_days": 14,
    "bear_per_asset_weight": 0.0625,
    "bear_rebalance_days": 7,
    "bear_short_count": 4,
    "btc_ma_window": 200,
    "exit_funding_lookback_days": 7,
    "exit_funding_min_assets": 5,
    "exit_funding_rank_min": 2.0 / 3.0,
    "exit_holding_days": 21,
    "exit_per_asset_weight": 0.025,
    "h5_leverage": 1.25,
    "long_buffer": 0.50,
    "max_total_gross": 1.25,
    "profit_lock_redistribution": {
        "lookback_days": 21,
        "max_asset_weight": 0.60,
        "recipient_confirmation_days": 21,
        "scale": 0.50,
        "threshold": 1.0,
    },
    "rebalance_no_trade_band": 0.0,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
}
LS45_G125_MANIFEST_TOP_LEVEL: dict[str, Any] = {
    "allow_incomplete_marks": False,
    "cost_bps": 20.0,
    "data_audit_required": True,
    "execution_price_model": "mark_1h_open_floor",
    "execution_utc": "01:05",
    "funding_source": "bitget-exact",
    "max_total_gross": 1.25,
    "research_only": True,
}


def as_utc(moment: datetime) -> datetime:
    """Return ``moment`` in UTC, treating a naive value as already UTC."""

    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def last_completed_utc_day(now: datetime) -> date:
    """The newest day whose UTC bar has closed."""

    return as_utc(now).date() - timedelta(days=1)


def execution_utc_text() -> str:
    """Return the canonical ``HH:MM`` execution clock used in manifests."""

    return LIVE_EXECUTION_UTC.strftime("%H:%M")


def live_execution_hint_for_signal(
    signal_date: date | datetime,
    *,
    scheduled_utc: time = DEFAULT_SCHEDULED_UTC,
) -> datetime:
    """The UTC timestamp the automated live executor aims at for a signal day.

    The frozen target ledger and live execution share the same T+1 09:05
    Beijing (01:05 UTC) clock.  The schedule remains injectable for legacy
    reproductions, but new LS45 artifacts must use the canonical default.
    """

    day = signal_date.date() if isinstance(signal_date, datetime) else signal_date
    return datetime.combine(day + timedelta(days=1), scheduled_utc, tzinfo=timezone.utc)


_MISSING = object()


def _config_value_equal(actual: object, expected: object) -> bool:
    """Compare frozen JSON config values without hiding numeric type drift."""

    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        actual_number = float(actual)
        expected_number = float(expected)
        return (
            math.isfinite(actual_number)
            and math.isfinite(expected_number)
            and math.isclose(actual_number, expected_number, rel_tol=1e-12, abs_tol=1e-12)
        )
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        if set(actual) != set(expected):
            return False
        return all(
            _config_value_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(
            _config_value_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def manifest_spec_issues(
    manifest: Mapping[str, Any],
    *,
    expected_spec: str,
    expected_frozen_config: Mapping[str, Any],
    expected_top_level: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return every manifest field that does not match the live specification.

    The target ledger and manifest are written by the research wrapper.  A
    live run must never infer that a file belongs to the current track merely
    because it sits at the expected path: a stale L125 manifest, a changed
    profit-lock horizon, or a different gross cap must fail closed.
    """

    issues: list[str] = []
    actual_spec = str(manifest.get("tracked_spec") or "")
    if actual_spec != expected_spec:
        issues.append(
            f"tracked_spec={actual_spec!r}, expected {expected_spec!r}"
        )

    actual_config = manifest.get("frozen_config")
    if not isinstance(actual_config, Mapping):
        issues.append("frozen_config is missing or is not an object")
    else:
        for key, expected in expected_frozen_config.items():
            actual = actual_config.get(key, _MISSING)
            if actual is _MISSING:
                issues.append(f"frozen_config.{key} is missing")
            elif not _config_value_equal(actual, expected):
                issues.append(
                    f"frozen_config.{key}={actual!r}, expected {expected!r}"
                )

    for key, expected in (expected_top_level or {}).items():
        actual = manifest.get(key, _MISSING)
        if actual is _MISSING:
            issues.append(f"{key} is missing")
        elif not _config_value_equal(actual, expected):
            issues.append(f"{key}={actual!r}, expected {expected!r}")
    return issues


def manifest_staleness_hours(manifest: dict[str, Any], now: datetime) -> float:
    """Current mark age from the manifest's timestamp, not its build-time value.

    A recorded build-time staleness cannot prove how old the mark is *now*, so
    a missing or malformed live timestamp is unknown rather than fresh.
    """

    last_mark = manifest.get("last_mark")
    if last_mark not in (None, ""):
        try:
            stamp = pd.Timestamp(last_mark)
            if stamp.tzinfo is None:
                stamp = stamp.tz_localize("UTC")
            else:
                stamp = stamp.tz_convert("UTC")
            age_seconds = (as_utc(now) - stamp.to_pydatetime()).total_seconds()
            # A small negative value is clock skew; a materially future mark is
            # corrupt data and must not be accepted as zero age.
            if age_seconds < -60.0:
                return float("inf")
            return max(0.0, age_seconds / 3600.0)
        except (TypeError, ValueError, OverflowError):
            return float("inf")
    return float("inf")


def file_sha256(path: Path) -> str:
    """Return the SHA-256 of a local artifact without loading it into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_targets_hash_issue(
    manifest: Mapping[str, Any],
    targets_file: Path,
) -> str | None:
    """Check that the target CSV is the exact file covered by its manifest.

    A killed process can leave a newly written ``oos_targets.csv`` beside an
    older manifest.  The executor must not interpret that mixed snapshot as a
    valid target book, so the manifest commits to the target bytes.
    """

    expected = str(manifest.get("targets_sha256") or "")
    if not expected:
        return None
    path = Path(targets_file)
    if not path.is_file():
        return f"targets file is missing: {path}"
    actual = file_sha256(path)
    if actual != expected:
        return (
            f"targets_sha256 mismatch: manifest={expected}, actual={actual}; "
            "rebuild the LS45 signal"
        )
    recorded_name = str(manifest.get("targets_file") or "")
    if recorded_name and Path(recorded_name).name != path.name:
        return (
            f"targets_file={path.name!r} does not match manifest "
            f"{recorded_name!r}"
        )
    return None


def panel_end_date(panel_path: Path) -> date | None:
    """Newest date in a processed panel, or ``None`` when it cannot be read."""

    path = Path(panel_path)
    if not path.is_file():
        return None
    try:
        frame = pd.read_csv(path, usecols=["date"])
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None
    if frame.empty:
        return None
    dates = pd.to_datetime(frame["date"], utc=True, format="mixed", errors="coerce").dropna()
    if dates.empty:
        return None
    return cast(date, pd.Timestamp(dates.max()).date())


def panel_lags_last_completed_day(panel_path: Path, now: datetime) -> bool:
    """True unless the panel ends exactly at the last completed UTC day.

    A future date is not treated as "ahead of schedule": it is corrupt or
    timezone-shifted data and must be rebuilt/fail closed before any trade.
    """

    end = panel_end_date(panel_path)
    if end is None:
        return True
    return end != last_completed_utc_day(now)


def panel_completeness(panel_path: Path) -> tuple[bool, str]:
    """Whether the newest panel day is finished, with a human-readable reason.

    A panel can carry the correct date and still be unsafe to trade: CMC
    publishes rows asset by asset, and a day whose volume or market-cap
    coverage is still incomplete must not move the Top20 or size an order.
    """

    path = Path(panel_path)
    if not path.is_file():
        return False, f"panel is missing: {path}"
    try:
        frame = pd.read_csv(path, usecols=["date", "coin_id", "volume_usd", "market_cap"])
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return False, f"panel could not be read: {exc}"
    try:
        verdict = assess_last_day(frame, min_assets=LIVE_PANEL_MIN_ASSETS)
    except (KeyError, ValueError, TypeError) as exc:
        return False, f"panel completeness check failed: {exc}"
    return bool(verdict.complete), verdict.describe()


def run_day_already_done(
    state_path: Path,
    run_day: date,
    *,
    target_identity: str | None = None,
) -> bool:
    """True when the executor already recorded a successful run for ``run_day``.

    The executor keys idempotency on
    ``spec|signal_date|targets_sha256|run_day``.  A successful no-op against an
    older target book must not suppress a later catch-up after the book is
    rebuilt.  Legacy three-part keys have no target identity and therefore
    cannot prove that the currently pending book was executed.
    """

    path = Path(state_path)
    if not path.is_file():
        return False
    try:
        state: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(state, dict) or state.get("last_status") != "ok":
        return False
    parts = str(state.get("last_key") or "").split("|")
    if len(parts) < 3:
        return False
    if parts[-1] != run_day.isoformat():
        return False
    if target_identity is None:
        return True
    recorded_identity = parts[-2] if len(parts) >= 4 else ""
    return recorded_identity == str(target_identity)


def within_run_window(
    now: datetime,
    *,
    scheduled_utc: time = DEFAULT_SCHEDULED_UTC,
    catchup_hours: float = DEFAULT_CATCHUP_HOURS,
) -> tuple[bool, str]:
    """Whether ``now`` is inside today's trading window, with a reason."""

    moment = as_utc(now)
    opens = datetime.combine(moment.date(), scheduled_utc, tzinfo=timezone.utc)
    if moment < opens:
        return False, f"before the {scheduled_utc:%H:%M} UTC fill window"
    closes = opens + timedelta(hours=float(catchup_hours))
    if moment > closes:
        return False, (
            f"past the {float(catchup_hours):g}h catch-up window "
            f"(it closed {closes:%Y-%m-%d %H:%M} UTC)"
        )
    return True, "inside the run window"
