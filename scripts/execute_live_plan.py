"""Execute a frozen daily plan on a real Bitget account and report it.

This is the automated arm of the derivatives track: it reads the latest frozen
target book, sizes it from the *real* account equity, places the resulting
market orders on Bitget, and pushes one Telegram message built from what the
venue actually did - fills, fees, and the position book read back afterwards.

Safety rails (all on by default):

* ``--live`` is required to send orders; without it the run is a dry run that
  still reads the real account and prints the message you would get.
* a kill-switch file (``--kill-switch``) stops everything if it exists,
* the target data/manifest must be fresh (``--max-mark-staleness-hours``,
  default 30) unless ``--allow-stale-signal`` is passed,
* the account equity must clear ``--equity-floor``,
* one execution per signal date (recorded in ``--state-file``); a run that
  ended with failures may retry once the next timer fires, and the retry
  re-reads the account so it self-corrects;
* ``--protect-only`` runs risk-reducing maintenance only (open/increase are
  structurally disabled), while ``--reconcile-only`` writes journal/state from
  exchange stop history and never enters the order planner.

``--margin-mode auto`` tries isolated margin first (the frozen spec) and falls
back to the venue's cross default when the key/account refuses isolated
futures; the fallback is printed in the message, never hidden.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
from math import isfinite
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, TextIO

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.account import (  # noqa: E402
    BitgetCredentials,
    BitgetPrivateClient,
    account_fingerprint,
    account_state_binding_issue,
)
from atlas20.derivatives.bitget import BitgetAPIError  # noqa: E402
from atlas20.derivatives.data_audit import audit_derivatives_data  # noqa: E402
from atlas20.derivatives.execution import ContractSpec, build_execution_plan  # noqa: E402
from atlas20.derivatives.live_chain import (  # noqa: E402
    live_execution_hint_for_signal,
    live_track_profile,
    manifest_spec_issues,
    manifest_staleness_hours,
    manifest_targets_hash_issue,
)
from atlas20.derivatives.live_executor import (  # noqa: E402
    ExecutionReport,
    OrderFill,
    _fee_from_detail,
    execute_plan,
    format_execution_report,
    match_venue_stop_fills,
)
from atlas20.derivatives.live_journal import (  # noqa: E402
    DEFAULT_CAPITAL_FLOWS_FILE,
    JournalEntry,
    effective_event_target_quantities,
    latest_row,
    latest_short_quantities,
    load_journal,
    net_capital_flow,
    previous_row,
    protected_short_stops,
    upsert_entry,
)
from atlas20.derivatives.quotes import (  # noqa: E402
    ExecutionQuote,
    QuoteError,
    fetch_execution_quotes,
    orderbook_warnings,
    quote_warnings,
    require_fresh_quotes,
)
from atlas20.logging_utils import atomic_write_text, ensure_dir  # noqa: E402

from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    DEFAULT_TARGETS_FILE,
    TRACKED_SPEC,
    account_state_from_bitget,
    fetch_public_instruments,
    load_symbol_map,
    missing_asset_mappings,
    missing_contract_specs,
    spec_symbol_universe,
    specs_from_instruments,
    symbol_to_asset_index,
    target_weights_from_book,
    target_gross_weight,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, send_telegram_message  # noqa: E402

DEFAULT_STATE_FILE = Path("data/ls45_g125_execution_state.json")
DEFAULT_JOURNAL_FILE = Path("reports/ls45_live_g125_live/journal.csv")
DEFAULT_MANIFEST_FILE = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_KILL_SWITCH = Path("data/ls45_g125_execution.KILL")
DEFAULT_JSON_OUT = Path("reports/ls45_live_g125_live/latest.json")
DEFAULT_LOCK_FILE = Path("data/ls45_g125_execution.lock")
DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_oos_20261112")
DEFAULT_PANEL_FILE = Path("data/processed/panel_daily.csv")


def _read_state(path: Path) -> dict[str, Any]:
    """Read execution state strictly; corruption must never look like an empty run."""

    state_path = Path(path)
    if not state_path.exists():
        return {}
    try:
        raw = state_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"execution state is unreadable: {state_path}: {exc}") from exc
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"execution state is invalid JSON: {state_path}: {exc}") from exc
    if not isinstance(state, dict):
        raise ValueError(f"execution state is not a JSON object: {state_path}")
    return state


def _state_track_issue(state: Mapping[str, Any], spec: str) -> str | None:
    """Reject a state file whose persisted key belongs to another track."""

    if not state:
        return None
    last_key = str(state.get("last_key") or "").strip()
    if not last_key:
        return "execution state is non-empty but has no track key"
    stored_track = last_key.split("|", 1)[0]
    if stored_track != str(spec):
        return (
            "execution state belongs to another track: "
            f"stored={stored_track!r}, expected={str(spec)!r}"
        )
    return None


def _require_state_track(state: Mapping[str, Any], spec_or_name: str) -> None:
    """Fail closed unless state belongs to the selected frozen live track."""

    try:
        profile = live_track_profile(str(spec_or_name))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    issue = _state_track_issue(state, profile.spec)
    if issue is not None:
        raise SystemExit(issue)


def _require_existing_state_payload(state: Mapping[str, Any], path: Path) -> None:
    """An existing state file may be absent, but it may not silently be `{}`."""

    state_path = Path(path)
    if state_path.exists() and not state:
        raise SystemExit(f"execution state is empty: {state_path}")


def _live_quote_snapshot(
    session: requests.Session,
    symbols: set[str],
    *,
    required_symbols: set[str] | None = None,
    max_age_seconds: float = 120.0,
    spread_warning_bps: float = 50.0,
    mark_deviation_warning_bps: float = 100.0,
) -> tuple[dict[str, float], dict[str, ExecutionQuote], list[str]]:
    """Fetch fresh ticker quotes and return prices, snapshots, and warnings."""

    quotes = fetch_execution_quotes(session, symbols)
    required = set(symbols) if required_symbols is None else set(required_symbols)
    require_fresh_quotes(quotes, required, max_age_seconds=max_age_seconds)
    prices = {symbol: quote.last_price for symbol, quote in quotes.items()}
    warnings = quote_warnings(
        quotes,
        required,
        spread_warning_bps=spread_warning_bps,
        mark_deviation_warning_bps=mark_deviation_warning_bps,
    )
    return prices, quotes, warnings


def _held_position_price(
    symbol: str,
    *,
    venue_mark: float,
    quotes: Mapping[str, ExecutionQuote],
    max_age_seconds: float,
) -> tuple[float, str | None]:
    """Choose a close-sizing price without requiring a fresh quote for an exit."""

    if not isfinite(float(max_age_seconds)) or float(max_age_seconds) < 0.0:
        raise ValueError("max quote age must be finite and non-negative")
    upper = str(symbol).strip().upper()
    quote = quotes.get(upper)
    if quote is not None and quote.age_seconds <= float(max_age_seconds):
        return float(quote.last_price), None
    mark = float(venue_mark)
    if not isfinite(mark) or mark <= 0.0:
        raise ValueError(f"held position {upper} has no usable venue mark")
    reason = "missing" if quote is None else "stale"
    return mark, (
        f"{upper}: {reason} public quote; using venue mark {mark:.8g} "
        "for close sizing"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--live", action="store_true", help="actually place the orders")
    parser.add_argument("--notify", action="store_true", help="send the report to Telegram")
    parser.add_argument("--force", action="store_true", help="ignore same-day idempotency")
    parser.add_argument(
        "--reconcile-only",
        action="store_true",
        help=(
            "read exchange stop/order history and repair the journal/state only; "
            "never plan or place an order"
        ),
    )
    parser.add_argument(
        "--protect-only",
        action="store_true",
        help=(
            "reconcile stops and run risk-reducing maintenance only; opens and "
            "increases are structurally disabled"
        ),
    )
    parser.add_argument("--allow-stale-signal", action="store_true")
    parser.add_argument(
        "--bootstrap-track",
        action="store_true",
        help=(
            "one-time activation for an empty track state/journal: apply the "
            "current frozen book even when its event row predates the latest data day"
        ),
    )
    parser.add_argument(
        "--allow-late-execution",
        action="store_true",
        help="allow a manual catch-up after the normal execution window",
    )
    parser.add_argument(
        "--catchup-hours",
        type=float,
        default=6.0,
        help="hours after execution_hint during which a normal run is allowed",
    )
    parser.add_argument("--manifest-file", type=Path, default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL_FILE)
    parser.add_argument(
        "--require-data-audit",
        action="store_true",
        help="also enforce the data audit during a dry run (live runs always enforce it)",
    )
    parser.add_argument(
        "--max-mark-staleness-hours",
        type=float,
        default=30.0,
        help="refuse to trade when the frozen mark tree is older than this",
    )
    parser.add_argument(
        "--max-event-age-days",
        type=float,
        default=7.0,
        help="warn (do not block) when the newest book change is older than this",
    )
    parser.add_argument("--equity-floor", type=float, default=20.0)
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--short-buffer", type=float, default=0.50)
    parser.add_argument("--short-stop-loss-pct", type=float, default=0.20)
    parser.add_argument("--max-gross-multiple", type=float, default=1.25)
    parser.add_argument("--max-margin-utilization", type=float, default=0.85)
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--min-rebalance-usdt", type=float, default=5.0)
    parser.add_argument(
        "--max-quote-age-seconds",
        type=float,
        default=120.0,
        help="refuse to trade when Bitget's ticker timestamp is older than this",
    )
    parser.add_argument(
        "--spread-warning-bps",
        type=float,
        default=50.0,
        help="warn when the live bid/ask spread exceeds this threshold",
    )
    parser.add_argument(
        "--mark-deviation-warning-bps",
        type=float,
        default=100.0,
        help="warn when last and mark price diverge beyond this threshold",
    )
    parser.add_argument(
        "--margin-mode",
        choices=("auto", "isolated", "crossed"),
        default="auto",
        help="auto = try isolated, fall back to crossed; require-isolated makes that fatal",
    )
    parser.add_argument("--require-isolated", action="store_true")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--capital-flows-file", type=Path, default=DEFAULT_CAPITAL_FLOWS_FILE)
    parser.add_argument("--kill-switch", type=Path, default=DEFAULT_KILL_SWITCH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK_FILE)
    parser.add_argument("--instruments-file", type=Path, default=None)
    parser.add_argument("--prices-file", type=Path, default=None)
    return parser.parse_args(argv)


def _attempt_client_oid_prefix(
    key: str, state: dict[str, Any], *, account_fp: str = ""
) -> str:
    """Fresh clientOid namespace only after a completed attempt was persisted.

    A crash before the state write must reuse the deterministic prefix so the
    next process can recover fills from order history.  Once a partial attempt
    has been recorded, however, reusing the same venue idempotency keys can
    prevent the scheduled retry from placing the missing order.
    """

    runs = state.get("runs")
    prior_attempts = (
        sum(
            1
            for row in runs
            if isinstance(row, dict) and str(row.get("key") or "") == key
        )
        if isinstance(runs, list)
        else 0
    )
    seed = key if prior_attempts == 0 else f"{key}|attempt={prior_attempts + 1}"
    if account_fp:
        seed = f"{account_fp}|{seed}"
    return "a20" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _execution_key(
    spec: str,
    signal_date: str,
    run_day: str,
    target_identity: str,
) -> str:
    """Idempotency key bound to both the execution day and exact target book."""

    identity = str(target_identity or "").strip() or "no-target-manifest"
    return f"{spec}|{signal_date}|{identity}|{run_day}"


def _apply_equity_floor(
    plan: Any,
    *,
    floor_usdt: float,
) -> tuple[Any, list[Any]]:
    """Keep exits enabled but suppress new/increased exposure below the floor."""

    blocked = [order for order in plan.orders if not order.reduce_only]
    if plan.equity >= floor_usdt or not blocked:
        return plan, []
    filtered = replace(
        plan,
        orders=[order for order in plan.orders if order.reduce_only],
        margin_intents=[],
        warnings=[
            *plan.warnings,
            (
                f"account equity {plan.equity:.2f} USDT is below the "
                f"{floor_usdt:.2f} USDT floor; only risk-reducing orders are allowed"
            ),
        ],
    )
    return filtered, blocked


def _execution_window_error(
    *,
    execution_hint: datetime | pd.Timestamp,
    now: datetime | pd.Timestamp,
    catchup_hours: float,
    allow_late: bool,
) -> str | None:
    """Return why the plan may not execute now, or ``None`` when allowed."""

    hint = pd.Timestamp(execution_hint)
    current = pd.Timestamp(now)
    if hint.tzinfo is None:
        hint = hint.tz_localize("UTC")
    else:
        hint = hint.tz_convert("UTC")
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    else:
        current = current.tz_convert("UTC")
    if catchup_hours < 0.0:
        raise ValueError("catchup_hours must be non-negative")
    if current < hint:
        return (
            f"target execution time {hint.isoformat()} is not due yet "
            f"(now {current.isoformat()})"
        )
    late_after = hint + pd.Timedelta(hours=float(catchup_hours))
    if current > late_after and not allow_late:
        return (
            f"target execution time {hint.isoformat()} is more than "
            f"{catchup_hours:g}h old (now {current.isoformat()}); use an explicit "
            "manual late catch-up only after reviewing the venue state"
        )
    return None


def _effective_execution_hint(
    *,
    signal_end_date: object,
    event_execution_hint: pd.Timestamp,
) -> pd.Timestamp:
    """Daily execution time for an event book whose latest row may be old."""

    if signal_end_date in (None, ""):
        return pd.Timestamp(event_execution_hint)
    try:
        normalized = pd.Timestamp(signal_end_date)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"manifest signal_end_date is invalid: {signal_end_date!r}") from exc
    if pd.isna(normalized):
        raise ValueError(f"manifest signal_end_date is invalid: {signal_end_date!r}")
    if normalized.tzinfo is None:
        normalized = normalized.tz_localize("UTC")
    else:
        normalized = normalized.tz_convert("UTC")
    return pd.Timestamp(live_execution_hint_for_signal(normalized.normalize()))


def _target_event_is_fresh(
    signal_date: pd.Timestamp, manifest: dict[str, Any]
) -> bool:
    """Whether the latest target row was produced for today's execution cycle.

    The frozen ledger is an event series.  A missing daily row means "keep the
    current book", not "trade the old book back to its original weights".  Only
    equality between the event date and the latest evaluated data date authorizes
    a fresh target rebalance.
    """

    signal_end = manifest.get("signal_end_date")
    if signal_end in (None, ""):
        return False
    try:
        event_day = pd.Timestamp(signal_date).date()
        data_day = pd.Timestamp(signal_end).date()
    except (TypeError, ValueError):
        return False
    return event_day == data_day


def _event_plan_mode(
    *,
    fresh_target_event: bool,
    active_event: dict[str, Any] | None,
    bootstrap_track: bool = False,
) -> str:
    """Choose how a run may use the target book.

    ``fresh`` is the first application of a new event and is sized from the
    event's weights and current equity.  ``complete`` resumes an event that was
    persisted as partial and must use its frozen quantities.  ``maintain`` keeps
    same-side drift and permits only risk-reducing/account-maintenance work.
    """

    if not isinstance(active_event, dict):
        return "fresh" if fresh_target_event or bootstrap_track else "maintain"
    if str(active_event.get("position_status") or "") != "ok":
        return "complete"
    return "maintain"


def _bootstrap_track_issues(
    *,
    requested: bool,
    state: Mapping[str, Any],
    journal: pd.DataFrame,
    manifest: Mapping[str, Any] | None,
) -> list[str]:
    """Return why a one-time track bootstrap is unsafe, or an empty list."""

    if not requested:
        return []
    issues: list[str] = []
    if any(
        key in state for key in ("active_event", "last_key", "last_status", "runs")
    ):
        issues.append("execution state already contains track history")
    if not journal.empty:
        issues.append("track journal is not empty")
    if not manifest or not str(manifest.get("targets_sha256") or ""):
        issues.append("manifest has no targets_sha256")
    return issues


def _signed_event_target_quantities(
    active_event: dict[str, Any],
    symbols_by_asset: dict[str, str],
    stopped_symbols: Mapping[str, object],
) -> dict[str, float]:
    """Turn frozen event quantities back into signed per-asset quantities."""

    weights = active_event.get("target_weights")
    quantities = effective_event_target_quantities(active_event)
    if isinstance(weights, dict) and not weights and not quantities:
        return {}
    if not isinstance(weights, dict) or not quantities:
        raise ValueError("active target event lacks weights or quantities")
    by_symbol = {str(symbol).upper(): str(asset) for asset, symbol in symbols_by_asset.items()}
    by_asset: dict[str, tuple[str, float]] = {}
    for raw_symbol, raw_quantity in quantities.items():
        symbol = str(raw_symbol).upper()
        quantity = float(raw_quantity)
        if not isfinite(quantity):
            raise ValueError(f"active event quantity for {symbol} is not finite")
        asset = by_symbol.get(symbol)
        if asset is None:
            raise ValueError(f"active event quantity symbol {symbol} has no asset mapping")
        if asset in by_asset:
            raise ValueError(f"active event maps multiple quantities to asset {asset}")
        by_asset[asset] = (symbol, abs(quantity))
    stopped = {str(symbol).upper() for symbol in stopped_symbols}
    result: dict[str, float] = {}
    for raw_asset, raw_weight in weights.items():
        asset = str(raw_asset)
        weight = float(raw_weight)
        if not isfinite(weight):
            raise ValueError(f"active event weight for {asset} is not finite")
        if abs(weight) <= 1e-15:
            continue
        frozen = by_asset.get(asset)
        if frozen is None:
            raise ValueError(f"active event weight for {asset} has no frozen quantity")
        symbol, quantity = frozen
        result[asset] = 0.0 if symbol in stopped else math.copysign(quantity, weight)
    return result


def _risk_cap_was_scaled(warnings: list[str]) -> bool:
    """Whether the planner had to shrink the requested book for a hard cap."""

    prefixes = (
        "gross exposure scaled to",
        "gross margin scaled to",
        "actual gross risk reduced to the",
    )
    return any(str(warning).startswith(prefixes) for warning in warnings)


def _risk_overlay_quantities(
    active_event: dict[str, Any],
    *,
    positions: list[dict[str, Any]],
    symbol_assets: Mapping[str, str],
) -> dict[str, float]:
    """Snapshot the effective quantities after a hard-risk-cap reduction."""

    weights = active_event.get("target_weights")
    if not isinstance(weights, dict):
        raise ValueError("active target event has no target weights")
    assets_by_symbol = {
        str(symbol).upper(): str(asset) for symbol, asset in symbol_assets.items()
    }
    actual_by_symbol: dict[str, float] = {}
    for row in positions:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        total = float(row.get("total") or 0.0)
        if not isfinite(total):
            raise ValueError(f"risk overlay position {symbol} is not finite")
        pos_side = str(row.get("posSide") or "").lower()
        signed = total if pos_side == "long" or (pos_side in {"", "net"} and total > 0.0) else -abs(total)
        actual_by_symbol[symbol] = actual_by_symbol.get(symbol, 0.0) + signed
    quantities: dict[str, float] = {}
    for raw_asset in weights:
        asset = str(raw_asset)
        symbols = [
            symbol
            for symbol, mapped_asset in assets_by_symbol.items()
            if mapped_asset == asset
        ]
        if len(symbols) != 1:
            raise ValueError(f"risk overlay cannot uniquely map asset {asset}")
        symbol = symbols[0]
        quantities[symbol] = abs(actual_by_symbol.get(symbol, 0.0))
    return quantities


def _event_completion_issues(
    active_event: dict[str, Any],
    *,
    positions: list[dict[str, Any]],
    symbol_assets: Mapping[str, str],
    specs_by_symbol: Mapping[str, ContractSpec],
) -> list[str]:
    """Check the live book against the event's frozen quantity invariant."""

    from scripts.audit_live_track import _event_quantity_issues  # noqa: PLC0415

    target_quantities = effective_event_target_quantities(active_event)
    target_weights = active_event.get("target_weights")
    prices = active_event.get("prices")
    stopped = active_event.get("stopped_symbols")
    if not isinstance(target_weights, dict):
        return ["active target event lacks frozen quantities or directions"]
    if not target_weights and not target_quantities:
        return []
    if not target_quantities:
        return ["active target event lacks frozen quantities or directions"]
    return _event_quantity_issues(
        target_quantities=target_quantities,
        target_weights=target_weights,
        symbol_assets=symbol_assets,
        positions=positions,
        specs_by_symbol=specs_by_symbol,
        event_prices=prices if isinstance(prices, dict) else {},
        stopped_symbols=stopped if isinstance(stopped, dict) else {},
    )


def _position_application_failures(
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Failures that can leave an event's position book incomplete.

    Isolated-margin adjustments are account maintenance rather than a change
    in the signed target book; they can retry on later daily runs without
    authorizing a stale target rebalance.
    """

    return [
        dict(failure)
        for failure in failures
        if str(failure.get("action") or "").upper() != "MARGIN"
    ]


def _active_event_record(
    plan: Any,
    targets: dict[str, float],
    specs_by_asset: dict[str, Any],
    prices_by_asset: dict[str, float],
    *,
    signal_date: pd.Timestamp,
    target_identity: str,
    execution_hint: pd.Timestamp,
    applied_at: str,
    failures: list[dict[str, Any]],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze the applied target event and its event-time position sizes."""

    position_failures = _position_application_failures(failures)
    same_event = (
        isinstance(previous, dict)
        and str(previous.get("signal_date") or "")
        == str(pd.Timestamp(signal_date).date())
        and str(previous.get("targets_sha256") or "") == str(target_identity)
    )
    event_applied_at = (
        str(previous.get("applied_at") or applied_at)
        if same_event and previous is not None and previous.get("applied_at")
        else applied_at
    )
    stopped_symbols = (
        dict(previous.get("stopped_symbols") or {})
        if same_event
        and previous is not None
        and isinstance(previous.get("stopped_symbols"), dict)
        else {}
    )
    return {
        "signal_date": str(pd.Timestamp(signal_date).date()),
        "targets_sha256": str(target_identity),
        "execution_hint": pd.Timestamp(execution_hint).isoformat(),
        "applied_at": event_applied_at,
        "equity_at_execution": float(getattr(plan, "equity", 0.0)),
        "target_weights": {
            str(asset): float(weight) for asset, weight in targets.items()
        },
        "prices": {
            str(asset): float(price) for asset, price in prices_by_asset.items()
        },
        "target_quantities": _event_target_quantities(
            plan, targets, specs_by_asset, prices_by_asset
        ),
        "position_status": "ok" if not position_failures else "partial",
        "position_failures": position_failures,
        "stopped_symbols": stopped_symbols,
    }


def _event_target_quantities(
    plan: Any,
    targets: dict[str, float],
    specs_by_asset: dict[str, Any],
    prices_by_asset: dict[str, float],
) -> dict[str, float]:
    """Freeze an event's target size in coin quantity, not today's USD weight.

    The research engine rebalances only when the target event changes.  Its
    position quantities then drift with price.  Comparing a live account to
    ``target_weight * today's equity`` would silently demand a daily rebalance
    the strategy never performs.  This event-time quantity becomes the stable
    audit anchor until the next target event.
    """

    quantities: dict[str, float] = {}
    signed_targets = getattr(plan, "signed_target_notional", {}) or {}
    for asset, weight in targets.items():
        if abs(float(weight)) <= 1e-15:
            continue
        spec = specs_by_asset.get(asset)
        price = float(prices_by_asset.get(asset, 0.0))
        if spec is None or not isfinite(price) or price <= 0.0:
            continue
        notional = abs(float(signed_targets.get(asset, 0.0)))
        if notional <= 0.0:
            notional = abs(float(weight)) * float(getattr(plan, "equity", 0.0))
        if notional <= 0.0:
            continue
        quantities[str(spec.symbol).upper()] = notional / price
    return quantities


def _profile_argument_issues(
    args: argparse.Namespace, *, profile: Any | None = None
) -> list[str]:
    """Reject CLI values that drift from the selected frozen live profile."""

    if profile is None:
        try:
            profile = live_track_profile(str(args.spec))
        except ValueError as exc:
            return [str(exc)]
    expected_config = dict(profile.frozen_config)
    expected_top_level = dict(profile.manifest_top_level)
    issues: list[str] = []
    if str(args.spec) != profile.spec:
        issues.append(f"live --spec={args.spec!r}, expected {profile.spec!r}")
    expected_args = {
        "leverage": profile.venue_leverage,
        "max_margin_utilization": profile.max_margin_utilization,
        "max_gross_multiple": float(expected_config["max_total_gross"]),
        "long_buffer": float(expected_config["long_buffer"]),
        "short_buffer": float(expected_config["short_buffer"]),
        "short_stop_loss_pct": float(expected_config["short_stop_loss_pct"]),
        "cost_bps": float(expected_top_level["cost_bps"]),
    }
    for name, expected_value in expected_args.items():
        raw_actual = getattr(args, name, None)
        try:
            actual_value = float(raw_actual)
        except (TypeError, ValueError):
            issues.append(
                f"live {name}={raw_actual!r}, expected {float(expected_value):g}"
            )
            continue
        if not isfinite(actual_value) or abs(
            actual_value - float(expected_value)
        ) > 1e-9:
            issues.append(
                f"live {name}={actual_value:g}, expected {float(expected_value):g}"
            )
    return issues


def _manifest_spec_issues(
    manifest: dict[str, Any], args: argparse.Namespace
) -> list[str]:
    """Check that the manifest and live CLI describe the same frozen book."""

    try:
        profile = live_track_profile(str(args.spec))
    except ValueError as exc:
        return [str(exc)]
    expected_config = dict(profile.frozen_config)
    expected_top_level = dict(profile.manifest_top_level)
    issues = _profile_argument_issues(args, profile=profile)
    issues.extend(
        manifest_spec_issues(
            manifest,
            expected_spec=profile.spec,
            expected_frozen_config=expected_config,
            expected_top_level=expected_top_level,
        )
    )
    return issues


def _stamp_assets(rows: list[dict], symbols_by_asset: dict[str, str]) -> list[dict]:
    """Add the model's asset id to each venue position row."""

    by_symbol = symbol_to_asset_index(symbols_by_asset)
    stamped: list[dict] = []
    for row in rows:
        record = dict(row)
        symbol = str(record.get("symbol") or "").upper()
        record["asset"] = by_symbol.get(symbol, symbol.replace("USDT", "")).lower()
        stamped.append(record)
    return stamped


def _closed_funding_from_history(
    history: list[dict[str, Any]],
    *,
    previous: dict[str, Any] | None,
    current_positions: list[dict[str, Any]],
    fills: list[Any],
    previous_run_at: datetime | str,
    run_at: datetime | str,
) -> tuple[dict[str, float], list[str]]:
    """Match closed cycles to their final cumulative funding.

    The current-position payload only covers legs that still exist.  When a
    cycle disappears (or flips side), its final ``totalFunding`` is available
    from position history.  Only cycles whose close falls in the daily window
    are attributed here.
    """

    if previous is None:
        return {}, []
    try:
        prior_positions = json.loads(previous.get("positions") or "[]")
    except (TypeError, json.JSONDecodeError):
        prior_positions = []
    if not isinstance(prior_positions, list):
        return {}, ["资金费归因不完整：上一行 positions 不是数组"]

    current_by_symbol: dict[str, str] = {}
    for row in current_positions:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        pos_side = str(row.get("posSide") or "").lower()
        raw_total = row.get("total")
        try:
            total = float(raw_total)
        except (TypeError, ValueError):
            total = 0.0
        if abs(total) <= 1e-12:
            continue
        current_by_symbol[symbol] = (
            "short" if pos_side == "short" or (pos_side in {"", "net"} and total < 0) else "long"
        )

    previous_by_symbol: dict[str, dict[str, Any]] = {}
    for row in prior_positions:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        previous_by_symbol[symbol] = row
    candidates: set[str] = set()
    for symbol, row in previous_by_symbol.items():
        prior_side = str(row.get("side") or "").lower()
        if symbol not in current_by_symbol or current_by_symbol[symbol] != prior_side:
            candidates.add(symbol)
    for fill in fills:
        action = str(
            getattr(fill, "action", "") if not isinstance(fill, dict) else fill.get("action") or ""
        ).upper()
        if action not in {"CLOSE", "EXTERNAL_CLOSE"}:
            continue
        symbol = str(
            getattr(fill, "symbol", "") if not isinstance(fill, dict) else fill.get("symbol") or ""
        ).upper()
        if symbol:
            candidates.add(symbol)
    if not candidates:
        return {}, []

    start = pd.Timestamp(previous_run_at)
    end = pd.Timestamp(run_at)
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    else:
        end = end.tz_convert("UTC")

    # An external close can arrive between the last journal snapshot and the
    # current reconciliation run.  The same-day snapshot may already describe
    # the reopened book, so the journal timestamp alone is not a sufficient
    # lower bound for finding the closed position-history cycle.
    for fill in fills:
        action = str(
            getattr(fill, "action", "") if not isinstance(fill, dict) else fill.get("action") or ""
        ).upper()
        if action not in {"CLOSE", "EXTERNAL_CLOSE"}:
            continue
        raw_triggered = (
            getattr(fill, "triggered_at", "")
            if not isinstance(fill, dict)
            else fill.get("triggered_at") or ""
        )
        if not raw_triggered:
            continue
        try:
            triggered = pd.Timestamp(raw_triggered)
        except (TypeError, ValueError):
            continue
        if triggered.tzinfo is None:
            triggered = triggered.tz_localize("UTC")
        else:
            triggered = triggered.tz_convert("UTC")
        if triggered < start:
            start = triggered - pd.Timedelta(seconds=1)

    funding: dict[str, float] = {}
    matched: set[str] = set()
    notes: list[str] = []
    seen_positions: set[str] = set()
    for row in history:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        position_id = str(row.get("positionId") or "")
        identity = position_id or "|".join(
            str(row.get(key) or "")
            for key in ("symbol", "posSide", "createdTime", "updatedTime", "totalFunding")
        )
        if identity in seen_positions:
            continue
        seen_positions.add(identity)
        try:
            updated_ms = int(row.get("updatedTime"))
        except (TypeError, ValueError):
            updated = pd.NaT
        else:
            updated = pd.to_datetime(updated_ms, unit="ms", utc=True, errors="coerce")
        if pd.isna(updated) or not (start < updated <= end):
            continue
        try:
            amount = float(row.get("totalFunding"))
        except (TypeError, ValueError):
            amount = float("nan")
        if not isfinite(amount):
            notes.append(f"资金费归因不完整：{symbol} 平仓历史 totalFunding 非法")
            continue
        prior = previous_by_symbol.get(symbol)
        carries_previous_cycle = False
        prior_funding: float | None = None
        if prior is not None:
            prior_side = str(prior.get("side") or "").lower()
            row_side = str(row.get("posSide") or "").lower()
            try:
                created_ms = int(row.get("createdTime"))
            except (TypeError, ValueError):
                created_ms = -1
            try:
                candidate_funding = float(prior.get("funding_cumulative"))
            except (TypeError, ValueError):
                candidate_funding = float("nan")
            if isfinite(candidate_funding):
                prior_funding = candidate_funding
            carries_previous_cycle = (
                prior_side == row_side
                and created_ms >= 0
                and created_ms <= int(start.timestamp() * 1000)
            )
        contribution = amount
        if carries_previous_cycle:
            if prior_funding is None:
                notes.append(
                    f"资金费归因不完整：{symbol} 跨日周期缺少上次累计基线，已按完整累计值计入"
                )
            else:
                contribution = amount - prior_funding
        funding[symbol] = funding.get(symbol, 0.0) + contribution
        matched.add(symbol)

    for symbol in sorted(candidates - matched):
        notes.append(f"资金费归因不完整：{symbol} 当日平仓周期未在持仓历史中匹配到")
    return funding, notes


def _record_stopped_fills(
    active_event: dict[str, Any],
    fills: list[Any],
    *,
    include_before_application: bool = False,
) -> dict[str, Any]:
    """Attach confirmed stop closures to the event whose target leg stopped."""

    record = dict(active_event)
    stopped = record.get("stopped_symbols")
    stopped_map = dict(stopped) if isinstance(stopped, dict) else {}
    applied_at: pd.Timestamp | None = None
    if record.get("applied_at"):
        try:
            applied_at = pd.Timestamp(record["applied_at"])
            if applied_at.tzinfo is None:
                applied_at = applied_at.tz_localize("UTC")
            else:
                applied_at = applied_at.tz_convert("UTC")
        except (TypeError, ValueError):
            applied_at = None
    for fill in fills:
        if str(getattr(fill, "reason", "")) != "venue_strategy_stop":
            continue
        symbol = str(getattr(fill, "symbol", "") or "").upper()
        if not symbol:
            continue
        if applied_at is not None:
            try:
                triggered_at = pd.Timestamp(getattr(fill, "triggered_at", ""))
                if triggered_at.tzinfo is None:
                    triggered_at = triggered_at.tz_localize("UTC")
                else:
                    triggered_at = triggered_at.tz_convert("UTC")
            except (TypeError, ValueError):
                triggered_at = None
            if (
                triggered_at is not None
                and triggered_at < applied_at
                and not include_before_application
            ):
                continue
        stopped_map[symbol] = {
            "order_id": str(getattr(fill, "order_id", "") or ""),
            "strategy_order_id": str(
                getattr(fill, "strategy_order_id", "") or ""
            ),
            "triggered_at": str(getattr(fill, "triggered_at", "") or ""),
            "quantity": float(getattr(fill, "filled_size", 0.0)),
            "requested_quantity": float(getattr(fill, "requested_size", 0.0) or 0.0),
            "stop_loss": float(getattr(fill, "stop_loss", 0.0) or 0.0),
            "stop_trigger_by": str(getattr(fill, "stop_trigger_by", "") or ""),
            "stop_order_type": str(getattr(fill, "stop_order_type", "") or ""),
        }
    record["stopped_symbols"] = stopped_map
    return record


def _external_order_fills(
    order_rows: list[dict[str, Any]],
    *,
    known_order_ids: set[str],
    matched_order_ids: set[str],
    symbol_assets: Mapping[str, str],
) -> list[OrderFill]:
    """Import venue fills that did not come from the Atlas20 executor.

    The exchange can close or change a leg from its UI, a risk process, or a
    manual order.  Those fills must enter the same journal as executor fills;
    otherwise the ledger silently drifts from the venue.  Orders carrying an
    Atlas20 clientOid are deliberately left to the crash-recovery path, which
    validates their clientOid and intent before accepting them.
    """

    assets_by_symbol = {
        str(symbol).upper(): str(asset).lower()
        for symbol, asset in symbol_assets.items()
    }
    fills: list[OrderFill] = []
    for row in order_rows:
        order_id = str(row.get("orderId") or "").strip()
        client_oid = str(row.get("clientOid") or "").strip()
        if (
            not order_id
            or order_id in known_order_ids
            or order_id in matched_order_ids
            or client_oid.startswith(("a20", "atlas20"))
        ):
            continue
        if str(row.get("orderStatus") or row.get("status") or "").lower() != "filled":
            continue
        try:
            filled_size = float(row.get("cumExecQty") or row.get("qty") or 0.0)
            avg_price = float(row.get("avgPrice") or row.get("price") or 0.0)
        except (TypeError, ValueError):
            continue
        if not (isfinite(filled_size) and isfinite(avg_price)):
            continue
        if filled_size <= 1e-12 or avg_price <= 0.0:
            continue
        symbol = str(row.get("symbol") or "").upper()
        asset = assets_by_symbol.get(symbol)
        if asset is None:
            continue
        side = str(row.get("side") or "").lower()
        if side not in {"buy", "sell"}:
            continue
        reduce_only = str(row.get("reduceOnly") or "").lower() in {"yes", "true", "1"}
        pos_side = str(row.get("posSide") or "").lower()
        if pos_side in {"long", "short"}:
            position_side = pos_side
        elif reduce_only:
            position_side = "short" if side == "buy" else "long"
        else:
            position_side = "long" if side == "buy" else "short"
        closes_position = (
            reduce_only
            or (side == "buy" and position_side == "short")
            or (side == "sell" and position_side == "long")
        )
        try:
            fee, fee_coin = _fee_from_detail(row)
        except (TypeError, ValueError):
            fee, fee_coin = 0.0, "USDT"
        notional_raw = row.get("cumExecValue")
        try:
            notional = float(notional_raw) if notional_raw not in (None, "") else 0.0
        except (TypeError, ValueError):
            notional = 0.0
        if not isfinite(notional) or notional <= 0.0:
            notional = filled_size * avg_price
        updated_raw = row.get("updatedTime") or row.get("createdTime")
        try:
            updated_ms = int(updated_raw)
        except (TypeError, ValueError):
            updated_ms = 0
        triggered_at = (
            pd.to_datetime(updated_ms, unit="ms", utc=True).isoformat()
            if updated_ms > 0
            else ""
        )
        fills.append(
            OrderFill(
                asset=asset,
                symbol=symbol,
                action="EXTERNAL_CLOSE" if closes_position else "EXTERNAL_OPEN",
                side=side,
                stop_loss=None,
                requested_size=filled_size,
                filled_size=filled_size,
                avg_price=avg_price,
                notional=notional,
                fee=fee,
                fee_coin=fee_coin,
                order_id=order_id,
                status="filled",
                position_side=position_side,
                client_oid=client_oid,
                reason="external_venue_order",
                triggered_at=triggered_at,
            )
        )
    return fills


def _recover_venue_stop_fills(
    client: Any,
    *,
    journal: pd.DataFrame,
    state: dict[str, Any],
    symbol_assets: dict[str, str],
    run_at: datetime,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Import venue-triggered short stops that happened since the last run."""

    previous_at: pd.Timestamp | None = None
    raw_previous = state.get("stop_reconciliation_through")
    if raw_previous in (None, ""):
        raw_previous = state.get("last_run_at")
    if raw_previous not in (None, ""):
        previous_at = pd.Timestamp(raw_previous)
    elif not journal.empty:
        latest = latest_row(journal)
        if latest and latest.get("run_at_utc"):
            previous_at = pd.Timestamp(latest["run_at_utc"])
    if previous_at is None:
        previous_at = pd.Timestamp(run_at) - pd.Timedelta(days=1)
    if previous_at.tzinfo is None:
        previous_at = previous_at.tz_localize("UTC")
    else:
        previous_at = previous_at.tz_convert("UTC")
    current = pd.Timestamp(run_at)
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    else:
        current = current.tz_convert("UTC")
    if previous_at > current:
        raise ValueError("execution state last_run_at is later than the current run")
    # Re-scan a full day and rely on journal order ids for deduplication.  A
    # venue history row can arrive late; a one-hour overlap can permanently
    # miss it once the high-water mark has advanced.
    start_ms = int((previous_at - pd.Timedelta(hours=24)).timestamp() * 1000)
    end_ms = int((current + pd.Timedelta(minutes=5)).timestamp() * 1000)

    strategy_rows = client.strategy_order_history(
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        limit=100,
    )
    order_rows = client.order_history_all(
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        limit=100,
    )
    known_order_ids: set[str] = set()
    if not journal.empty:
        for raw in journal["trades"]:
            try:
                trades = json.loads(raw or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(trades, list):
                continue
            for trade in trades:
                if isinstance(trade, dict) and trade.get("order_id"):
                    known_order_ids.add(str(trade["order_id"]))
    fills, errors = match_venue_stop_fills(
        strategy_rows,
        order_rows,
        known_order_ids=known_order_ids,
        symbol_assets=symbol_assets,
    )
    fills.extend(
        _external_order_fills(
            order_rows,
            known_order_ids=known_order_ids,
            matched_order_ids={
                str(getattr(fill, "order_id", "") or "") for fill in fills
            },
            symbol_assets=symbol_assets,
        )
    )
    errors.extend(
        _venue_stop_reconciliation_errors(
            fills,
            expected_stops=protected_short_stops(journal),
            expected_short_qty=latest_short_quantities(journal),
        )
    )
    return fills, errors


def _closed_funding_for_report(
    client: Any,
    *,
    previous: dict[str, Any] | None,
    report: ExecutionReport,
    run_at: datetime,
) -> tuple[dict[str, float], list[str]]:
    """Attribute the final funding of every cycle closed by this report."""

    if previous is None or not previous.get("run_at_utc"):
        return {}, []
    try:
        prior_positions = json.loads(previous.get("positions") or "[]")
    except (TypeError, json.JSONDecodeError):
        prior_positions = []
    current_sides = {
        str(row.get("symbol") or "").upper(): (
            "short"
            if str(row.get("posSide") or "").lower() == "short"
            or (
                str(row.get("posSide") or "").lower() in {"", "net"}
                and float(row.get("total") or 0.0) < 0.0
            )
            else "long"
        )
        for row in report.positions_after
        if str(row.get("symbol") or "")
        and abs(float(row.get("total") or 0.0)) > 1e-12
    }
    needs_closed_funding = any(
        isinstance(prior, dict)
        and str(prior.get("symbol") or "")
        and current_sides.get(str(prior.get("symbol") or "").upper())
        != str(prior.get("side") or "").lower()
        for prior in (prior_positions if isinstance(prior_positions, list) else [])
    ) or any(
        str(fill.action).upper() in {"CLOSE", "EXTERNAL_CLOSE"}
        for fill in report.fills
    )
    if not needs_closed_funding:
        return {}, []
    try:
        previous_at = pd.Timestamp(previous["run_at_utc"])
        start_ms = int((previous_at - pd.Timedelta(hours=1)).timestamp() * 1000)
        end_ms = int((pd.Timestamp(run_at) + pd.Timedelta(hours=1)).timestamp() * 1000)
        history = client.position_history(
            start_time_ms=start_ms,
            end_time_ms=end_ms,
        )
        return _closed_funding_from_history(
            history,
            previous=previous,
            current_positions=report.positions_after,
            fills=report.fills,
            previous_run_at=previous_at,
            run_at=run_at,
        )
    except (BitgetAPIError, ValueError, OSError) as exc:
        return {}, [f"资金费归因不完整：读取平仓持仓历史失败（{exc}）"]


def _reconcile_only_status(
    *,
    previous_status: object,
    active_event: dict[str, Any],
    stop_errors: list[dict[str, Any]],
) -> str:
    """A read-only reconciliation may preserve but never upgrade run status."""

    if (
        stop_errors
        or str(previous_status or "") != "ok"
        or str(active_event.get("position_status") or "") != "ok"
    ):
        return "partial"
    return "ok"


def _reconcile_live_stops_from_context(
    args: argparse.Namespace,
    *,
    client: Any,
    state: dict[str, Any],
    symbol_assets: Mapping[str, str],
    account_fp: str,
    run_at: datetime,
) -> int:
    """Repair journal/state for venue stops without planning any new risk."""

    _require_state_track(state, args.spec)
    binding_issue = account_state_binding_issue(state, account_fp)
    if binding_issue is not None:
        raise SystemExit(binding_issue)
    active_event = state.get("active_event")
    if not isinstance(active_event, dict):
        raise SystemExit("reconcile-only requires an active target event in execution state")
    key = str(state.get("last_key") or "")
    if not key:
        raise SystemExit("reconcile-only requires the last persisted execution key")

    journal = load_journal(args.journal_file)
    stop_fills, stop_errors = _recover_venue_stop_fills(
        client,
        journal=journal,
        state=state,
        symbol_assets=dict(symbol_assets),
        run_at=run_at,
    )
    positions = _stamp_assets(
        client.current_positions(),
        {asset: symbol for symbol, asset in symbol_assets.items()},
    )
    assets = client.account_assets()
    usdt = next(
        (
            row
            for row in assets.get("assets") or []
            if isinstance(row, dict) and str(row.get("coin") or "").upper() == "USDT"
        ),
        {},
    )
    equity_value = assets.get("usdtEquity", assets.get("accountEquity"))
    try:
        equity = float(equity_value)
        available = float(usdt.get("available"))
        balance = float(usdt.get("balance"))
    except (TypeError, ValueError) as exc:
        raise ValueError("reconcile-only account snapshot has invalid equity/margin") from exc
    if not all(isfinite(value) for value in (equity, available, balance)):
        raise ValueError("reconcile-only account snapshot is not finite")

    report = ExecutionReport(
        signal_date=str(active_event.get("signal_date") or ""),
        equity_before=equity,
        equity_after=equity,
        available_after=available,
        balance_after=balance,
        fills=list(stop_fills),
        failures=list(stop_errors),
        positions_after=positions,
        traded=bool(stop_fills),
    )
    report.margin_mode = next(
        (str(row.get("marginMode") or "") for row in positions if row.get("marginMode")),
        "",
    )
    open_short_symbols = {
        str(row.get("symbol") or "").upper()
        for row in positions
        if str(row.get("symbol") or "")
        and (
            str(row.get("posSide") or "").lower() == "short"
            or (
                str(row.get("posSide") or "").lower() in {"", "net"}
                and float(row.get("total") or 0.0) < 0.0
            )
        )
    }
    report.normalized_short_stops = {
        symbol: stop
        for symbol, stop in protected_short_stops(journal).items()
        if symbol in open_short_symbols
    }
    reconciled_event = _record_stopped_fills(
        dict(active_event),
        stop_fills,
        include_before_application=True,
    )
    stop_high_water = run_at.isoformat() if not stop_errors else None

    previous = previous_row(journal, run_at.strftime("%Y-%m-%d"))
    funding_previous = _same_day_row(journal, run_at) or previous
    prev_equity = (
        float(previous["equity"])
        if previous is not None and previous.get("equity") is not None
        else None
    )
    capital_flow = _capital_flow_for_run(
        journal,
        args.capital_flows_file,
        run_at=run_at,
    )
    closed_funding, funding_notes = _closed_funding_for_report(
        client,
        previous=funding_previous,
        report=report,
        run_at=run_at,
    )
    notes = [
        "只读止损对账：本次没有生成交易计划，也没有下任何新订单",
        *funding_notes,
    ]
    entry = _journal_entry(
        report,
        signal_date=str(active_event.get("signal_date") or ""),
        run_at=run_at,
        prev_equity=prev_equity,
        capital_flow=capital_flow,
        warnings=notes,
        previous=previous,
        closed_position_funding=closed_funding,
    )
    status = _reconcile_only_status(
        previous_status=state.get("last_status"),
        active_event=active_event,
        stop_errors=stop_errors,
    )
    message = format_execution_report(
        report,
        signal_date=str(active_event.get("signal_date") or ""),
        spec=args.spec,
        execution_hint=str(active_event.get("execution_hint") or ""),
        targets=None,
        planned_orders=[],
        warnings=notes,
        prev_equity=prev_equity,
        capital_flow=capital_flow,
        run_at=run_at,
        target_rebalance_enabled=False,
    )

    def notify_reconcile() -> None:
        token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN")
        if not token:
            raise SystemExit("ATLAS20_TELEGRAM_BOT_TOKEN is not set")
        chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
        if not chat_ids:
            raise SystemExit("ATLAS20_TELEGRAM_CHAT_ID is not set")
        api_base = os.environ.get("ATLAS20_TELEGRAM_API_BASE", "https://api.telegram.org")
        for chat_id in chat_ids:
            send_telegram_message(message, token=token, chat_id=chat_id, api_base=api_base)

    _persist_run_result(
        json_out=args.json_out,
        payload={
            "spec": args.spec,
            "mode": "reconcile_only",
            "signal_date": str(active_event.get("signal_date") or ""),
            "report": report.as_dict(),
            "status": status,
        },
        journal_file=args.journal_file,
        entry=entry,
        state_file=args.state_file,
        key=key,
        status=status,
        report=report,
        account_fp=account_fp,
        active_event=reconciled_event,
        stop_reconciliation_through=stop_high_water,
        mode="reconcile_only",
        notify=(
            notify_reconcile
            if args.notify and (stop_fills or stop_errors)
            else None
        ),
    )
    if stop_fills or stop_errors:
        print(message)
    else:
        print(f"reconcile-only: no new venue stop; high-water {run_at.isoformat()}")
    return 1 if status != "ok" else 0


def _venue_stop_reconciliation_errors(
    fills: list[Any],
    *,
    expected_stops: dict[str, float],
    expected_short_qty: dict[str, float],
) -> list[dict[str, Any]]:
    """Require every imported stop close to belong to the open journal cycle."""

    errors: list[dict[str, Any]] = []
    for fill in fills:
        if str(getattr(fill, "reason", "")) != "venue_strategy_stop":
            continue
        symbol = str(getattr(fill, "symbol", "") or "").upper()
        size = float(getattr(fill, "filled_size", 0.0))
        expected_qty = float(expected_short_qty.get(symbol, 0.0))
        expected_stop = float(expected_stops.get(symbol, 0.0))
        if expected_qty <= 0.0 or expected_stop <= 0.0:
            errors.append(
                {
                    "symbol": symbol or "*",
                    "action": "VERIFY",
                    "side": "buy",
                    "size": f"{size:.12g}",
                    "error": (
                        "venue strategy stop has no open journal short cycle "
                        "with a confirmed stop"
                    ),
                }
            )
            continue
        if abs(size - expected_qty) > max(1e-9, expected_qty * 1e-8):
            errors.append(
                {
                    "symbol": symbol,
                    "action": "VERIFY",
                    "side": "buy",
                    "size": f"{size:.12g}",
                    "error": (
                        "venue strategy stop quantity differs from the open journal "
                        f"short ({size:.8g} vs {expected_qty:.8g})"
                    ),
                }
            )
        fill_stop = float(getattr(fill, "stop_loss", 0.0) or 0.0)
        requested_stop = float(
            getattr(fill, "requested_stop_loss", 0.0) or 0.0
        )
        tolerance = max(1e-9, abs(expected_stop) * 1e-8)
        if (
            fill_stop <= 0.0
            or requested_stop <= 0.0
            or abs(fill_stop - expected_stop) > tolerance
            or abs(requested_stop - expected_stop) > tolerance
            or str(getattr(fill, "stop_trigger_by", "")).lower()
            != "mark"
            or str(getattr(fill, "stop_order_type", "")).lower()
            != "market"
        ):
            errors.append(
                {
                    "symbol": symbol,
                    "action": "VERIFY",
                    "side": "buy",
                    "size": f"{size:.12g}",
                    "error": (
                        "venue strategy stop contract differs from the journaled "
                        f"stop ({fill_stop:.8g}/{expected_stop:.8g})"
                    ),
                }
            )
    return errors


def _journal_entry(
    report: ExecutionReport,
    *,
    signal_date: str,
    run_at: datetime,
    prev_equity: float | None,
    capital_flow: float,
    warnings: list[str],
    previous: dict[str, Any] | None = None,
    closed_position_funding: dict[str, float] | None = None,
    bootstrap_track: bool = False,
) -> JournalEntry:
    equity = (
        report.equity_after
        if report.equity_after is not None
        else report.equity_before
    )
    positions: list[dict] = []
    position_value = 0.0
    unrealised = 0.0
    funding = 0.0
    funding_notes: list[str] = []
    previous_by_symbol: dict[str, dict[str, Any]] = {}
    if previous is not None:
        try:
            parsed_previous = json.loads(previous.get("positions") or "[]")
        except (TypeError, json.JSONDecodeError):
            parsed_previous = []
        if isinstance(parsed_previous, list):
            previous_by_symbol = {
                str(item.get("symbol") or "").upper(): item
                for item in parsed_previous
                if isinstance(item, dict) and item.get("symbol")
            }
    reset_symbols = {
        str(fill.symbol).upper()
        for fill in report.fills
        if str(fill.action).upper() in {"CLOSE", "EXTERNAL_CLOSE"}
    }
    for row in report.positions_after:
        try:
            raw_total = float(row.get("total"))
        except (TypeError, ValueError):
            funding_notes.append(
                f"资金费归因不完整：{row.get('symbol') or '<unknown>'} 的持仓数量非法"
            )
            continue
        size = abs(raw_total)
        if size <= 0.0:
            continue
        reported_side = str(row.get("posSide") or "").lower()
        side = (
            "short"
            if reported_side == "short"
            or (reported_side in {"", "net"} and raw_total < 0.0)
            else "long"
        )
        mark = float(row.get("markPrice") or row.get("avgPrice") or 0.0)
        notional = size * mark
        position_value += notional
        unrealised += float(row.get("unrealisedPnl") or 0.0)
        symbol = str(row.get("symbol") or "").upper()
        funding_cumulative: float | None = None
        raw_funding = row.get("totalFunding")
        if raw_funding not in (None, ""):
            try:
                parsed_funding = float(raw_funding)
            except (TypeError, ValueError):
                parsed_funding = float("nan")
            if isfinite(parsed_funding):
                funding_cumulative = parsed_funding
            else:
                funding_notes.append(f"资金费归因不完整：{symbol} totalFunding 非法")
        else:
            funding_notes.append(f"资金费归因不完整：{symbol} 缺少 totalFunding")

        funding_delta = 0.0
        if funding_cumulative is not None:
            prior = previous_by_symbol.get(symbol)
            same_cycle = (
                prior is not None
                and str(prior.get("side") or "").lower() == side
                and symbol not in reset_symbols
            )
            prior_funding: float | None = None
            if same_cycle:
                try:
                    candidate = float(prior.get("funding_cumulative"))
                except (TypeError, ValueError):
                    candidate = float("nan")
                if isfinite(candidate):
                    prior_funding = candidate
            if bootstrap_track and previous is None:
                # A new track inherits the venue positions, not the previous
                # track's funding history.  Keep the cumulative value as the
                # next-run baseline without counting it in this track's PnL.
                funding_delta = 0.0
            elif same_cycle and prior_funding is not None:
                funding_delta = funding_cumulative - prior_funding
            else:
                funding_delta = funding_cumulative
                if same_cycle:
                    funding_notes.append(
                        f"资金费基线未知：{symbol} 首次记录累计值 {funding_cumulative:+.8f}"
                    )
            funding += funding_delta
        positions.append(
            {
                "asset": str(row.get("asset") or "").lower(),
                "symbol": str(row.get("symbol") or ""),
                "side": side,
                "qty": size,
                "avg_price": float(row.get("avgPrice") or 0.0),
                "mark_price": mark,
                "notional": round(notional, 6),
                "weight": (
                    round((notional if side == "long" else -notional) / equity, 6)
                    if equity > 0
                    else 0.0
                ),
                "unrealised_pnl": round(float(row.get("unrealisedPnl") or 0.0), 6),
                "normalized_stop_loss": report.normalized_short_stops.get(symbol),
                "funding_cumulative": (
                    round(funding_cumulative, 8)
                    if funding_cumulative is not None
                    else None
                ),
            }
        )
    if closed_position_funding:
        for symbol, amount in sorted(closed_position_funding.items()):
            try:
                daily_amount = float(amount)
            except (TypeError, ValueError):
                funding_notes.append(f"资金费归因不完整：{symbol} 平仓资金费非法")
                continue
            if not isfinite(daily_amount):
                funding_notes.append(f"资金费归因不完整：{symbol} 平仓资金费非有限值")
                continue
            funding += daily_amount
    day_pnl = (
        None
        if prev_equity is None
        else round(equity - float(prev_equity) - float(capital_flow), 6)
    )
    capital_base = (
        None if prev_equity is None else float(prev_equity) + float(capital_flow)
    )
    day_return = (
        None
        if not capital_base or capital_base <= 0 or day_pnl is None
        else round(day_pnl / capital_base, 8)
    )
    return JournalEntry(
        date=run_at.strftime("%Y-%m-%d"),
        run_at_utc=run_at.isoformat(),
        signal_date=signal_date,
        equity=round(equity, 6),
        position_value=round(position_value, 6),
        cash=round(report.balance_after, 6),
        day_pnl=day_pnl,
        day_return=day_return,
        fees_today=round(report.fee_total, 8),
        funding_total=round(funding, 8),
        unrealised_pnl=round(unrealised, 6),
        capital_flow=round(float(capital_flow), 6),
        positions=positions,
        trades=[
            {
                "order_id": fill.order_id,
                "symbol": fill.symbol,
                "side": fill.side,
                "action": fill.action,
                "qty": fill.filled_size,
                "avg_price": fill.avg_price,
                "notional": round(fill.notional, 6),
                "fee": round(fill.fee, 8),
                "status": fill.status,
                "stop_loss": fill.stop_loss,
                "requested_stop_loss": fill.requested_stop_loss,
                "position_side": fill.position_side,
                "client_oid": fill.client_oid,
                "stop_trigger_by": fill.stop_trigger_by,
                "stop_order_type": fill.stop_order_type,
                "normalized_stop_loss": fill.normalized_stop_loss,
                "reason": fill.reason,
                "strategy_order_id": fill.strategy_order_id,
                "triggered_at": fill.triggered_at,
            }
            for fill in report.fills
        ],
        notes=[*report.margin_notes, *warnings, *funding_notes],
    )


def _write_state(
    path: Path,
    key: str,
    status: str,
    report: ExecutionReport,
    *,
    account_fp: str = "",
    active_event: dict[str, Any] | None = None,
    stop_reconciliation_through: str | None = None,
    mode: str = "execution",
) -> None:
    state = _read_state(path)
    expected_track = key.split("|", 1)[0]
    track_issue = _state_track_issue(state, expected_track)
    if track_issue is not None:
        raise ValueError(track_issue)
    if account_fp:
        state["account_fingerprint"] = account_fp
    state["last_key"] = key
    state["last_status"] = status
    state["last_run_mode"] = mode
    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    if active_event is not None:
        state["active_event"] = active_event
    if stop_reconciliation_through is not None:
        state["stop_reconciliation_through"] = stop_reconciliation_through
    runs = state.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(
        {
            "key": key,
            "status": status,
            "mode": mode,
            "ran_at": state["last_run_at"],
            "fills": [fill.as_dict() for fill in report.fills],
            "failures": list(report.failures),
        }
    )
    state["runs"] = runs[-40:]
    atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True))


def _decoded_trade_rows(raw: Any, *, field: str) -> list[dict[str, Any]]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    try:
        rows = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"journal {field} is not valid JSON") from exc
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"journal {field} is not an array of objects")
    return [dict(row) for row in rows]


def _decoded_notes(raw: Any) -> list[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    try:
        notes = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("journal notes is not valid JSON") from exc
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise ValueError("journal notes is not an array of strings")
    return notes


def _capital_flow_for_run(
    journal: pd.DataFrame,
    capital_flows_file: Path,
    *,
    run_at: datetime,
) -> float:
    """Total external flow for a run day, including an earlier same-day retry.

    A retry replaces the day's journal row, so it must not re-add deposits that
    the first row already accounted for.  The first same-day run carries the
    flow since the previous daily row; later runs carry that amount plus only
    the new flow after their predecessor's ``run_at_utc``.
    """

    day = run_at.date().isoformat()
    same_day = journal.loc[journal["date"].astype(str) == day] if not journal.empty else journal
    carried = 0.0
    after: datetime | str | None = None
    if not same_day.empty:
        prior = same_day.sort_values("run_at_utc").iloc[-1].to_dict()
        carried = float(prior.get("capital_flow") or 0.0)
        after = prior.get("run_at_utc")
    else:
        prior_day = previous_row(journal, day)
        if prior_day is not None:
            after = prior_day.get("run_at_utc")
    return carried + net_capital_flow(
        capital_flows_file,
        after=after,
        through=run_at,
    )


def _same_day_row(journal: pd.DataFrame, run_at: datetime) -> dict[str, Any] | None:
    """Latest already-written row for the current UTC day, if one exists."""

    if journal.empty:
        return None
    day = run_at.date().isoformat()
    same_day = journal.loc[journal["date"].astype(str) == day]
    if same_day.empty:
        return None
    return same_day.sort_values("run_at_utc").iloc[-1].to_dict()


def _merge_same_day_entry(previous: dict[str, Any], current: JournalEntry) -> JournalEntry:
    """Keep every same-day execution while refreshing the end-of-day snapshot."""

    prior_trades = _decoded_trade_rows(previous.get("trades"), field="trades")
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    for trade in [*prior_trades, *current.trades]:
        order_id = str(trade.get("order_id") or "")
        client_oid = str(trade.get("client_oid") or "")
        if order_id:
            merged[("order", order_id)] = trade
        elif client_oid:
            merged[("client", client_oid)] = trade
        else:
            anonymous.append(trade)
    trades = [*merged.values(), *anonymous]
    fees = 0.0
    for trade in trades:
        try:
            fee = float(trade.get("fee") or 0.0)
        except (TypeError, ValueError) as exc:
            raise ValueError("journal trade fee is not numeric") from exc
        if not isfinite(fee):
            raise ValueError("journal trade fee is not finite")
        fees += fee
    funding_total = float(current.funding_total)
    try:
        prior_funding = float(previous.get("funding_total") or 0.0)
    except (TypeError, ValueError) as exc:
        raise ValueError("journal funding_total is not numeric") from exc
    if not isfinite(funding_total) or not isfinite(prior_funding):
        raise ValueError("journal funding_total is not finite")
    # A later same-day reconciliation can observe a flat/reopened book and
    # therefore have no current cumulative funding to subtract.  That is not
    # evidence that earlier same-day funding disappeared.
    if abs(funding_total) <= 1e-12 and abs(prior_funding) > 1e-12:
        funding_total = prior_funding

    prior_notes = _decoded_notes(previous.get("notes"))
    # A retry refreshes volatile run facts instead of appending every observed
    # value.  Keeping both old and new capital-flow/freshness notes makes the
    # row look as if cash was deposited twice or the data moved backwards.
    volatile_prefixes = ("外部资金流 ", "数据管线:", "最新信号事件在 ")
    stable_prior = [
        note for note in prior_notes if not any(note.startswith(prefix) for prefix in volatile_prefixes)
    ]
    notes = list(dict.fromkeys([*stable_prior, *current.notes]))
    return replace(
        current,
        fees_today=round(fees, 8),
        funding_total=round(funding_total, 8),
        trades=trades,
        notes=notes,
    )


def _persist_run_result(
    *,
    json_out: Path,
    payload: dict[str, Any],
    journal_file: Path,
    entry: JournalEntry,
    state_file: Path,
    key: str,
    status: str,
    report: ExecutionReport,
    account_fp: str = "",
    active_event: dict[str, Any] | None = None,
    stop_reconciliation_through: str | None = None,
    mode: str = "execution",
    notify: Callable[[], None] | None = None,
) -> None:
    """Persist artifacts in an order that never marks an unwritten run as done."""

    # Validate the state before writing the journal or latest report.  A corrupt
    # file must not be silently replaced with a fresh state after an execution.
    state = _read_state(state_file)
    if state_file.exists() and not state:
        raise ValueError(f"execution state is empty: {state_file}")
    track_issue = _state_track_issue(state, key.split("|", 1)[0])
    if track_issue is not None:
        raise ValueError(track_issue)
    journal = load_journal(journal_file)
    same_day = journal.loc[journal["date"].astype(str) == entry.date]
    if not same_day.empty:
        entry = _merge_same_day_entry(same_day.iloc[-1].to_dict(), entry)
    ensure_dir(json_out.parent)
    atomic_write_text(
        json_out,
        json.dumps(payload, indent=2, sort_keys=True, default=str),
    )
    upsert_entry(journal_file, entry)
    if notify is not None:
        notify()
    _write_state(
        state_file,
        key,
        status,
        report,
        account_fp=account_fp,
        active_event=active_event,
        stop_reconciliation_through=stop_reconciliation_through,
        mode=mode,
    )


def _acquire_execution_lock(path: Path) -> TextIO | None:
    """Take a non-blocking process lock; the OS releases it on process death."""

    ensure_dir(path.parent)
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    os.fsync(handle.fileno())
    return handle


def _release_execution_lock(handle: TextIO) -> None:
    with suppress(OSError):
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    handle.close()


def _protect_only_main(args: argparse.Namespace) -> int:
    """Normalize stops and enforce risk reductions without opening risk."""

    if not args.live:
        raise SystemExit("--protect-only requires --live")
    profile_issues = _profile_argument_issues(args)
    if profile_issues:
        raise SystemExit(
            "protect-only profile parameters do not match the frozen live track: "
            + "; ".join(profile_issues)
        )
    state = _read_state(args.state_file)
    if not state:
        raise SystemExit("protect-only requires an existing execution state")
    _require_state_track(state, args.spec)
    active_event = state.get("active_event")
    if not isinstance(active_event, dict):
        raise SystemExit("protect-only requires an active target event")
    key = str(state.get("last_key") or "")
    if not key:
        raise SystemExit("protect-only requires the last execution key")

    symbols_by_asset = load_symbol_map(args.symbol_map)
    relevant_symbols = spec_symbol_universe(symbols_by_asset)
    session = requests.Session()
    rows = fetch_public_instruments(session)
    specs = specs_from_instruments(rows, relevant_symbols)
    client = BitgetPrivateClient(BitgetCredentials.from_env())
    account_fp = account_fingerprint(client.account_info())
    binding_issue = account_state_binding_issue(state, account_fp)
    if binding_issue is not None:
        raise SystemExit(binding_issue)
    account = account_state_from_bitget(client, relevant_symbols)
    missing_specs = missing_contract_specs(specs, set(account.positions))
    if missing_specs:
        raise SystemExit(
            "protect-only has no contract spec for " + ", ".join(missing_specs)
        )

    run_at = datetime.now(timezone.utc)
    journal = load_journal(args.journal_file)
    try:
        stop_fills, stop_errors = _recover_venue_stop_fills(
            client,
            journal=journal,
            state=state,
            symbol_assets=symbol_to_asset_index(relevant_symbols),
            run_at=run_at,
        )
    except (BitgetAPIError, ValueError, OSError) as exc:
        stop_fills = []
        stop_errors = [
            {
                "symbol": "*",
                "action": "VERIFY",
                "side": "short",
                "size": "-",
                "error": f"protect-only could not reconcile stop history ({exc})",
            }
        ]
    if stop_fills:
        account = account_state_from_bitget(client, relevant_symbols)

    weights = active_event.get("target_weights")
    weights = dict(weights) if isinstance(weights, dict) else {}
    required_assets = set(account.positions)
    try:
        _prices, quotes, warnings = _live_quote_snapshot(
            session,
            set(relevant_symbols.values()),
            # Protect-only never opens risk.  A held leg must still be closable
            # when the public ticker is missing or stale, so use the venue's
            # authoritative mark as the fallback below instead of failing before
            # stop normalization or a risk-reducing exit can run.
            required_symbols=set(),
            max_age_seconds=float(args.max_quote_age_seconds),
            spread_warning_bps=float(args.spread_warning_bps),
            mark_deviation_warning_bps=float(args.mark_deviation_warning_bps),
        )
    except QuoteError as exc:
        _prices, quotes = {}, {}
        warnings = [f"protect-only public ticker unavailable; using venue marks: {exc}"]
    prices_by_asset: dict[str, float] = {}
    for asset in required_assets:
        position = account.positions[asset]
        price, price_warning = _held_position_price(
            position.symbol,
            venue_mark=position.mark_price,
            quotes=quotes,
            max_age_seconds=float(args.max_quote_age_seconds),
        )
        prices_by_asset[asset] = price
        if price_warning is not None:
            warnings.append(price_warning)

    stopped_symbols = (
        dict(active_event.get("stopped_symbols") or {})
        if isinstance(active_event.get("stopped_symbols"), dict)
        else {}
    )
    stop_scope = _record_stopped_fills(
        dict(active_event),
        stop_fills,
        include_before_application=True,
    )
    if isinstance(stop_scope.get("stopped_symbols"), dict):
        stopped_symbols = stop_scope["stopped_symbols"]
    plan_quantities = _signed_event_target_quantities(
        active_event,
        relevant_symbols,
        stopped_symbols,
    )
    plan = build_execution_plan(
        account,
        weights,
        specs,
        prices_by_asset,
        leverage=float(args.leverage),
        long_buffer=float(args.long_buffer),
        short_buffer=float(args.short_buffer),
        short_stop_loss_pct=float(args.short_stop_loss_pct),
        max_gross_exposure=(
            float(args.max_gross_multiple) * account.equity
            if account.equity > 0.0
            else None
        ),
        max_margin_utilization=float(args.max_margin_utilization),
        taker_fee_rate=max(float(args.cost_bps), 0.0) / 10_000.0,
        min_rebalance_usdt=float(args.min_rebalance_usdt),
        rebalance_to_target=False,
        target_quantities=plan_quantities,
    )
    plan, floor_blocked_orders = _apply_equity_floor(
        plan,
        floor_usdt=float(args.equity_floor),
    )
    if any(not order.reduce_only for order in plan.orders):
        raise RuntimeError("protect-only planner produced a non-reducing order")
    if quotes:
        warnings.extend(
            orderbook_warnings(
                quotes,
                [(order.symbol, order.side, order.notional) for order in plan.orders],
            )
        )

    requested = {
        "auto": "isolated",
        "isolated": "isolated",
        "crossed": "crossed",
    }[args.margin_mode]
    hold_mode = client.hold_mode()
    journal_stops = protected_short_stops(journal)
    for fill in stop_fills:
        journal_stops.pop(fill.symbol.upper(), None)
    report = execute_plan(
        client,
        plan,
        signal_date=str(active_event.get("signal_date") or ""),
        leverage=float(args.leverage),
        margin_mode=requested,
        require_isolated=bool(args.require_isolated),
        known_protected_short_stops=journal_stops,
        symbol_assets=symbol_to_asset_index(relevant_symbols),
        short_stop_loss_pct=float(args.short_stop_loss_pct),
        contract_specs_by_symbol={
            spec.symbol.upper(): spec for spec in specs.values()
        },
        hold_mode=hold_mode,
        client_oid_prefix=_attempt_client_oid_prefix(
            key,
            state,
            account_fp=account_fp,
        ),
    )
    report.fills = [*stop_fills, *report.fills]
    report.failures.extend(stop_errors)
    report.positions_after = _stamp_assets(report.positions_after, relevant_symbols)
    for order in floor_blocked_orders:
        report.failures.append(
            {
                "symbol": order.symbol,
                "action": order.action,
                "side": order.side,
                "size": f"{order.size:.12g}",
                "error": "protect-only blocked a non-reducing order",
            }
        )

    protected_event = _record_stopped_fills(
        dict(active_event),
        stop_fills,
        include_before_application=True,
    )
    if (
        _risk_cap_was_scaled(plan.warnings)
        and not _position_application_failures(report.failures)
    ):
        protected_event["risk_overlay"] = {
            "reason": "risk_cap_scaled",
            "applied_at": run_at.isoformat(),
            "target_quantities": _risk_overlay_quantities(
                protected_event,
                positions=report.positions_after,
                symbol_assets=symbol_to_asset_index(relevant_symbols),
            ),
        }
    completion_issues = _event_completion_issues(
        protected_event,
        positions=report.positions_after,
        symbol_assets=symbol_to_asset_index(relevant_symbols),
        specs_by_symbol={spec.symbol.upper(): spec for spec in specs.values()},
    )
    for issue in completion_issues:
        report.failures.append(
            {
                "symbol": "*",
                "action": "VERIFY",
                "side": "-",
                "size": "-",
                "error": f"protect-only position completion failed: {issue}",
            }
        )
    position_failures = _position_application_failures(report.failures)
    protected_event["position_status"] = "ok" if not position_failures else "partial"
    protected_event["position_failures"] = position_failures
    status = "ok" if not report.failures else "partial"
    stop_high_water = run_at.isoformat() if not stop_errors else None

    previous = previous_row(journal, run_at.strftime("%Y-%m-%d"))
    funding_previous = _same_day_row(journal, run_at) or previous
    prev_equity = (
        float(previous["equity"])
        if previous is not None and previous.get("equity") is not None
        else None
    )
    prev_day_pnl = (
        float(previous["day_pnl"])
        if previous is not None and previous.get("day_pnl") is not None
        else None
    )
    capital_flow = _capital_flow_for_run(
        journal,
        args.capital_flows_file,
        run_at=run_at,
    )
    closed_funding, funding_notes = _closed_funding_for_report(
        client,
        previous=funding_previous,
        report=report,
        run_at=run_at,
    )
    notes = [
        "protect-only：只允许 reduce/close、止损归一和保证金维护；没有 OPEN/INCREASE",
        *plan.warnings,
        *warnings,
        *funding_notes,
    ]
    entry = _journal_entry(
        report,
        signal_date=str(active_event.get("signal_date") or ""),
        run_at=run_at,
        prev_equity=prev_equity,
        capital_flow=capital_flow,
        warnings=notes,
        previous=previous,
        closed_position_funding=closed_funding,
    )
    message = format_execution_report(
        report,
        signal_date=str(active_event.get("signal_date") or ""),
        spec=args.spec,
        execution_hint=str(active_event.get("execution_hint") or ""),
        targets=weights,
        lot_notional={
            asset: float(spec.min_order_qty or spec.quantity_multiplier)
            * prices_by_asset[asset]
            for asset, spec in specs.items()
            if asset in prices_by_asset
        },
        planned_orders=[],
        warnings=notes,
        prev_equity=prev_equity,
        prev_day_pnl=prev_day_pnl,
        capital_flow=capital_flow,
        run_at=run_at,
        target_rebalance_enabled=False,
        target_status_note="保护性维护：只降低风险并维护止损，不开仓",
    )

    def notify_protection() -> None:
        token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN")
        if not token:
            raise SystemExit("ATLAS20_TELEGRAM_BOT_TOKEN is not set")
        chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
        if not chat_ids:
            raise SystemExit("ATLAS20_TELEGRAM_CHAT_ID is not set")
        api_base = os.environ.get("ATLAS20_TELEGRAM_API_BASE", "https://api.telegram.org")
        for chat_id in chat_ids:
            send_telegram_message(message, token=token, chat_id=chat_id, api_base=api_base)

    _persist_run_result(
        json_out=args.json_out,
        payload={
            "spec": args.spec,
            "mode": "protect_only",
            "signal_date": str(active_event.get("signal_date") or ""),
            "plan": plan.as_dict(),
            "report": report.as_dict(),
            "status": status,
        },
        journal_file=args.journal_file,
        entry=entry,
        state_file=args.state_file,
        key=key,
        status=status,
        report=report,
        account_fp=account_fp,
        active_event=protected_event,
        stop_reconciliation_through=stop_high_water,
        mode="protect_only",
        notify=(
            notify_protection
            if args.notify and (report.fills or report.failures)
            else None
        ),
    )
    if report.fills or report.failures:
        print(message)
    else:
        print("protect-only: stops and risk book already correct; no order placed")
    return 1 if report.failures else 0


def _reconcile_only_main(args: argparse.Namespace) -> int:
    """Load the account context for a no-order stop reconciliation."""

    if not args.live:
        raise SystemExit("--reconcile-only requires --live to read the real account")
    state = _read_state(args.state_file)
    if not state:
        raise SystemExit("reconcile-only requires an existing execution state")
    _require_state_track(state, args.spec)
    symbols_by_asset = load_symbol_map(args.symbol_map)
    relevant_symbols = spec_symbol_universe(symbols_by_asset)
    client = BitgetPrivateClient(BitgetCredentials.from_env())
    account_fp = account_fingerprint(client.account_info())
    binding_issue = account_state_binding_issue(state, account_fp)
    if binding_issue is not None:
        raise SystemExit(binding_issue)
    # Validate that every venue position has a canonical asset mapping before
    # writing a new journal snapshot.  This path never uses a contract spec or
    # plans an order.
    account_state_from_bitget(client, relevant_symbols)
    return _reconcile_live_stops_from_context(
        args,
        client=client,
        state=state,
        symbol_assets=symbol_to_asset_index(relevant_symbols),
        account_fp=account_fp,
        run_at=datetime.now(timezone.utc),
    )


def _main(args: argparse.Namespace) -> int:
    if args.reconcile_only and args.protect_only:
        raise SystemExit("--reconcile-only and --protect-only are mutually exclusive")
    if args.reconcile_only:
        return _reconcile_only_main(args)
    if args.kill_switch.exists():
        raise SystemExit(
            f"kill switch present at {args.kill_switch}; refusing to trade "
            "(delete the file to resume)"
        )
    if args.protect_only:
        return _protect_only_main(args)
    state = _read_state(args.state_file)
    _require_existing_state_payload(state, args.state_file)
    _require_state_track(state, args.spec)

    signal_date, event_execution_hint, book = load_latest_targets(args.targets_file)
    manifest: dict[str, Any] | None = None
    if args.manifest_file.exists():
        payload = json.loads(args.manifest_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit(f"manifest {args.manifest_file} is not a JSON object")
        manifest = payload
    if args.live and manifest is None:
        raise SystemExit(
            f"live execution requires the frozen manifest at {args.manifest_file}; "
            "refusing to trade without an evaluated-date and mark-freshness proof"
        )
    if manifest is not None:
        if args.live and not manifest.get("targets_sha256"):
            raise SystemExit(
                "live execution requires manifest targets_sha256; "
                "rebuild the selected track signal so the target file is content-addressed"
            )
        manifest_issues = _manifest_spec_issues(manifest, args)
        if manifest_issues:
            raise SystemExit(
                "frozen manifest does not match the current live track "
                "specification: " + "; ".join(manifest_issues)
            )
        targets_hash_issue = manifest_targets_hash_issue(
            manifest,
            args.targets_file,
        )
        if targets_hash_issue is not None:
            raise SystemExit(targets_hash_issue)
    if manifest is not None and (args.live or args.require_data_audit):
        required_assets = {
            str(record["asset"]) for record in book.to_dict("records")
        }
        required_short_assets = {
            str(record["asset"])
            for record in book.to_dict("records")
            if float(record["target_weight"]) < 0.0
        }
        data_audit = audit_derivatives_data(
            args.raw_dir,
            args.panel,
            args.symbol_map,
            args.manifest_file,
            required_short_assets=required_short_assets,
            required_leverage_assets=required_assets,
            required_leverage=float(args.leverage),
            require_all_funding_fresh=True,
        )
        if not data_audit.passed:
            raise SystemExit(
                "data audit failed before live execution: "
                + "; ".join(data_audit.hard_failures[:10])
            )
        expected_fingerprint = manifest.get("data_fingerprint")
        actual_fingerprint = data_audit.provenance.get("fingerprint")
        if not expected_fingerprint:
            raise SystemExit(
                "manifest is missing data_fingerprint; rebuild the selected track signal"
            )
        if expected_fingerprint != actual_fingerprint:
            raise SystemExit(
                "manifest data_fingerprint does not match the current inputs: "
                f"manifest={expected_fingerprint}, current={actual_fingerprint}"
            )
        if manifest.get("data_audit_passed") is not True:
            raise SystemExit("manifest records a failed data audit; refusing to execute")
    fresh_target_event = (
        _target_event_is_fresh(signal_date, manifest)
        if manifest is not None
        else False
    )
    try:
        execution_hint = _effective_execution_hint(
            signal_end_date=manifest.get("signal_end_date") if manifest else None,
            event_execution_hint=event_execution_hint,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    timing_error = _execution_window_error(
        execution_hint=execution_hint,
        now=datetime.now(timezone.utc),
        catchup_hours=float(args.catchup_hours),
        allow_late=bool(args.allow_late_execution),
    )
    if timing_error is not None:
        raise SystemExit(timing_error)
    event_age_days = (
        pd.Timestamp.now(tz="UTC").normalize() - pd.Timestamp(signal_date).normalize()
    ).days

    # The frozen book is an *event* series: it only gets a new row when a
    # sleeve changes its pick.  A book dated days ago is therefore normal -
    # what must be current is the data behind it.  Guard that instead.
    freshness_note: str | None = None
    if manifest is not None:
        staleness = manifest_staleness_hours(manifest, datetime.now(timezone.utc))
        index_end = str(manifest.get("index_end_date") or "")
        signal_end = str(manifest.get("signal_end_date") or "")
        if not args.allow_stale_signal:
            if staleness > args.max_mark_staleness_hours:
                raise SystemExit(
                    f"mark tree is {staleness:.1f}h old "
                    f"(> {args.max_mark_staleness_hours:g}h); "
                    "run make derivatives-live-data first"
                )
            if not index_end or not signal_end:
                raise SystemExit(
                    f"manifest {args.manifest_file} is missing index_end_date or "
                    "signal_end_date; refusing to trade without an evaluated-date proof"
                )
            if index_end != signal_end:
                raise SystemExit(
                    f"target book was only evaluated through {index_end} while data "
                    f"reaches {signal_end}; refresh the selected track signal first"
                )
        freshness_note = (
            f"数据管线: mark 最新 {manifest.get('last_mark')}（{staleness:.1f}h 前）、"
            f"账本评估到 {index_end}、信号事件 {signal_date.date()}（{event_age_days} 天前）"
        )
    elif not args.allow_stale_signal and event_age_days > 1:
        raise SystemExit(
            f"no manifest at {args.manifest_file} and the newest book row is "
            f"{event_age_days} days old; refresh the pipeline "
            "(make derivatives-live-data derivatives-ls45-signal) or pass --allow-stale-signal"
        )

    warnings: list[str] = []
    if event_age_days > args.max_event_age_days:
        warnings.append(
            f"最新信号事件在 {event_age_days} 天前（事件驱动策略，无变化＝继续持有；"
            "若与回测不一致请跑 make audit-live）"
        )

    symbols_by_asset = load_symbol_map(args.symbol_map)
    targets = target_weights_from_book(book, symbols_by_asset)
    missing_mappings = missing_asset_mappings(symbols_by_asset, targets)
    if missing_mappings:
        raise SystemExit(
            "frozen target has no normal Bitget contract mapping: "
            + ", ".join(missing_mappings)
        )
    gross_weight = target_gross_weight(targets)
    if gross_weight > float(args.max_gross_multiple) + 1e-9:
        raise SystemExit(
            f"frozen target gross {gross_weight:.6f}x exceeds the "
            f"{float(args.max_gross_multiple):g}x spec cap"
        )
    # Resolve the venue contract for every asset the account can hold, not just
    # today's targets: a "go to cash" book has no targets at all and the close
    # of the held leg still needs its contract.
    relevant_symbols = spec_symbol_universe(symbols_by_asset, targets)
    session = requests.Session()
    if args.instruments_file is not None:
        payload = json.loads(Path(args.instruments_file).read_text(encoding="utf-8"))
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    else:
        rows = fetch_public_instruments(session)
    specs = specs_from_instruments(rows, relevant_symbols)

    client = BitgetPrivateClient(BitgetCredentials.from_env())
    account_fp = account_fingerprint(client.account_info())
    account = account_state_from_bitget(client, relevant_symbols)
    missing_specs = missing_contract_specs(
        specs,
        set(targets).union(account.positions),
    )
    if missing_specs:
        raise SystemExit(
            "no Bitget contract spec for required asset(s): " + ", ".join(missing_specs)
        )
    # A held leg that is absent from the target book only needs to be closed.
    # Its venue mark is a safe size/price fallback if the public ticker is
    # unavailable; requiring a fresh public quote here could block the exit.
    required_assets = set(targets)
    required_symbols = {
        str(relevant_symbols[asset]).upper()
        for asset in required_assets
        if asset in relevant_symbols
    }
    quotes: dict[str, ExecutionQuote] = {}
    if args.prices_file is not None:
        price_payload = json.loads(Path(args.prices_file).read_text(encoding="utf-8"))
        prices = {str(key).upper(): float(value) for key, value in price_payload.items()}
    else:
        try:
            prices, quotes, live_quote_warnings = _live_quote_snapshot(
                session,
                set(relevant_symbols.values()),
                required_symbols=required_symbols,
                max_age_seconds=float(args.max_quote_age_seconds),
                spread_warning_bps=float(args.spread_warning_bps),
                mark_deviation_warning_bps=float(args.mark_deviation_warning_bps),
            )
        except QuoteError as exc:
            raise SystemExit(f"live quote check failed: {exc}") from exc
        warnings.extend(live_quote_warnings)

    prices_by_asset: dict[str, float] = {}
    for asset in targets:
        symbol = relevant_symbols[asset].upper()
        if prices.get(symbol, 0.0) <= 0.0:
            raise SystemExit(f"no usable price for {symbol}")
        prices_by_asset[asset] = prices[symbol]
    for asset, position in account.positions.items():
        if asset in prices_by_asset:
            continue
        if args.prices_file is not None and position.symbol.upper() in prices:
            prices_by_asset[asset] = prices[position.symbol.upper()]
            continue
        held_price, held_warning = _held_position_price(
            position.symbol,
            venue_mark=position.mark_price,
            quotes=quotes,
            max_age_seconds=float(args.max_quote_age_seconds),
        )
        prices_by_asset[asset] = held_price
        if held_warning is not None:
            warnings.append(held_warning)

    # Idempotency is per *run day and exact target book*.  Keying only on the
    # signal date would skip every unchanged day; keying only on the run day
    # lets a stale no-op block a later catch-up after the book is rebuilt.
    run_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target_identity = (
        str(manifest.get("targets_sha256") or "")
        if manifest is not None
        else ""
    )
    key = _execution_key(
        args.spec,
        str(signal_date.date()),
        run_day,
        target_identity,
    )
    binding_issue = account_state_binding_issue(state, account_fp)
    if binding_issue is not None:
        raise SystemExit(
            f"{binding_issue}; archive and reset the old execution state before trading"
        )
    already = state.get("last_key") == key and state.get("last_status") == "ok"
    if already and not args.force and args.live:
        # A stop can trigger after the first successful run.  Do not return
        # before the venue's closed-strategy history has been reconciled; the
        # reconcile-only path cannot plan or place any order.
        return _reconcile_live_stops_from_context(
            args,
            client=client,
            state=state,
            symbol_assets=symbol_to_asset_index(relevant_symbols),
            account_fp=account_fp,
            run_at=datetime.now(timezone.utc),
        )
    client_oid_prefix = _attempt_client_oid_prefix(key, state, account_fp=account_fp)

    lot_notional = {
        asset: float(spec.min_order_qty or spec.quantity_multiplier) * prices_by_asset[asset]
        for asset, spec in specs.items()
        if asset in prices_by_asset
    }
    run_at = datetime.now(timezone.utc)
    journal = load_journal(args.journal_file)
    bootstrap_issues = _bootstrap_track_issues(
        requested=bool(args.bootstrap_track),
        state=state,
        journal=journal,
        manifest=manifest,
    )
    if bootstrap_issues:
        raise SystemExit("track bootstrap refused: " + "; ".join(bootstrap_issues))
    bootstrap_track = bool(args.bootstrap_track)
    if bootstrap_track:
        warnings.append(
            "一次性新 track 启动：按当前冻结账本建立首个事件基线，"
            "不会重放历史盈亏或历史成交"
        )
    previous = previous_row(journal, run_at.strftime("%Y-%m-%d"))
    funding_previous = _same_day_row(journal, run_at) or previous
    prev_equity = float(previous["equity"]) if previous and previous.get("equity") is not None else None
    capital_flow = _capital_flow_for_run(
        journal,
        args.capital_flows_file,
        run_at=run_at,
    )
    if abs(capital_flow) > 0.005:
        warnings.append(f"外部资金流 {capital_flow:+.2f} USDT（已从盈亏中剔除）")
    prev_day_pnl = (
        float(previous["day_pnl"])
        if previous and previous.get("day_pnl") is not None
        else None
    )

    stop_fills: list[Any] = []
    stop_errors: list[dict[str, Any]] = []
    stop_reconciliation_through: str | None = None
    hold_mode = ""
    requested = {
        "auto": "isolated",
        "isolated": "isolated",
        "crossed": "crossed",
    }[args.margin_mode]
    if args.live:
        try:
            stop_fills, stop_errors = _recover_venue_stop_fills(
                client,
                journal=journal,
                state=state,
                symbol_assets=symbol_to_asset_index(relevant_symbols),
                run_at=run_at,
            )
        except (BitgetAPIError, ValueError, OSError) as exc:
            stop_errors = [
                {
                    "symbol": "*",
                    "action": "VERIFY",
                    "side": "short",
                    "size": "-",
                    "error": (
                        "could not reconcile venue strategy stop history; "
                        f"new risk is blocked ({exc})"
                    ),
                }
            ]
        if not stop_errors:
            stop_reconciliation_through = run_at.isoformat()
        if stop_fills:
            # The first account read can race the exchange stop.  Re-read the
            # actual book before planning so a just-closed leg cannot be sized
            # as still open.
            account = account_state_from_bitget(client, relevant_symbols)
        hold_mode = client.hold_mode()

    existing_active_event = state.get("active_event")
    existing_active_event_ok = (
        isinstance(existing_active_event, dict)
        and str(existing_active_event.get("signal_date") or "")
        == str(pd.Timestamp(signal_date).date())
        and str(existing_active_event.get("targets_sha256") or "")
        == str(target_identity)
    )
    plan_active_event = existing_active_event if existing_active_event_ok else None
    if isinstance(plan_active_event, dict):
        plan_active_event = _record_stopped_fills(plan_active_event, stop_fills)
    # Any stop found in today's reconciliation scan blocks a same-run reopen,
    # even when the process had not yet persisted the event's applied_at.  A
    # later target event can authorize the symbol again; this run cannot.
    stop_scope = dict(plan_active_event) if isinstance(plan_active_event, dict) else {
        "stopped_symbols": {}
    }
    stop_scope = _record_stopped_fills(
        stop_scope,
        stop_fills,
        include_before_application=True,
    )
    stopped_symbols = (
        stop_scope.get("stopped_symbols")
        if isinstance(stop_scope.get("stopped_symbols"), dict)
        else {}
    )
    plan_mode = _event_plan_mode(
        fresh_target_event=fresh_target_event,
        active_event=plan_active_event if isinstance(plan_active_event, dict) else None,
        bootstrap_track=bootstrap_track,
    )

    plan_quantities: dict[str, float] | None = None
    if isinstance(plan_active_event, dict) and plan_mode != "fresh":
        plan_quantities = _signed_event_target_quantities(
            plan_active_event,
            relevant_symbols,
            stopped_symbols,
        )
    stopped_assets = {
        asset
        for asset, symbol in relevant_symbols.items()
        if str(symbol).upper() in {str(symbol).upper() for symbol in stopped_symbols}
    }
    plan_targets = {
        asset: weight
        for asset, weight in targets.items()
        if asset not in stopped_assets
    }
    rebalance_to_target = plan_mode in {"fresh", "complete"} and not stop_errors
    plan = build_execution_plan(
        account,
        plan_targets,
        specs,
        prices_by_asset,
        leverage=float(args.leverage),
        long_buffer=float(args.long_buffer),
        short_buffer=float(args.short_buffer),
        short_stop_loss_pct=float(args.short_stop_loss_pct),
        max_gross_exposure=(
            float(args.max_gross_multiple) * account.equity
            if account.equity > 0.0
            else None
        ),
        max_margin_utilization=float(args.max_margin_utilization),
        taker_fee_rate=max(float(args.cost_bps), 0.0) / 10_000.0,
        min_rebalance_usdt=float(args.min_rebalance_usdt),
        rebalance_to_target=rebalance_to_target,
        target_quantities=plan_quantities,
    )
    plan, floor_blocked_orders = _apply_equity_floor(
        plan, floor_usdt=float(args.equity_floor)
    )
    if quotes:
        warnings.extend(
            orderbook_warnings(
                quotes,
                [
                    (order.symbol, order.side, order.notional)
                    for order in plan.orders
                ],
            )
        )
    warnings = [*plan.warnings, *warnings]
    if plan_mode == "complete":
        warnings.append(
            "正在按最近目标事件冻结的币数量补齐未完成的仓位；不会按今日权益重算目标"
        )
    elif plan_mode == "maintain" and not fresh_target_event:
        warnings.append(
            "今日没有新的目标事件：保留当前同向持仓漂移，不按旧事件权重日常再平衡；"
            "只执行风险降低、止损和逐仓保证金维护"
        )
    if stop_errors:
        warnings.append(
            "止损成交历史未能完整对账：本轮禁止新开/加仓，只执行风险降低和账户维护"
        )
    notes = list(warnings)
    if freshness_note:
        notes.append(freshness_note)

    planned_orders: list[Any]
    if not args.live:
        warnings.append("DRY RUN：本次没有真的下单（加 --live 才会执行）")
        report = ExecutionReport(
            signal_date=str(signal_date.date()),
            equity_before=account.equity,
            equity_after=account.equity,
            available_after=account.available_margin,
            positions_after=client.current_positions(),
        )
        report.margin_mode = next(
            (
                str(row.get("marginMode"))
                for row in report.positions_after
                if row.get("marginMode")
            ),
            "",
        )
        report.positions_after = _stamp_assets(
            report.positions_after, relevant_symbols
        )
        planned_orders = list(plan.orders)
    else:
        journal_stops = protected_short_stops(journal)
        for fill in stop_fills:
            journal_stops.pop(fill.symbol.upper(), None)
        report = execute_plan(
            client,
            plan,
            signal_date=str(signal_date.date()),
            leverage=float(args.leverage),
            margin_mode=requested,
            require_isolated=bool(args.require_isolated),
            known_protected_short_stops=journal_stops,
            symbol_assets=symbol_to_asset_index(relevant_symbols),
            short_stop_loss_pct=float(args.short_stop_loss_pct),
            contract_specs_by_symbol={
                spec.symbol.upper(): spec for spec in specs.values()
            },
            hold_mode=hold_mode,
            client_oid_prefix=client_oid_prefix,
        )
        report.fills = [*stop_fills, *report.fills]
        if stop_fills:
            report.traded = True
        report.failures.extend(stop_errors)
        report.positions_after = _stamp_assets(
            report.positions_after, relevant_symbols
        )
        for order in floor_blocked_orders:
            report.failures.append(
                {
                    "symbol": order.symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": (
                        f"new risk blocked because equity {account.equity:.2f} USDT "
                        f"is below the {float(args.equity_floor):.2f} USDT floor"
                    ),
                }
            )
        planned_orders = []
        if (
            args.require_isolated
            and report.positions_after
            and report.margin_mode != "isolated"
        ):
            warnings.append(
                "REQUIRE-ISOLATED：持仓回读不是 isolated，规格未满足；"
                "新的 open/increase 已被阻断，请复核并处理现有仓位"
            )

    if isinstance(plan_active_event, dict) and existing_active_event_ok:
        active_event = dict(plan_active_event)
    elif fresh_target_event or bootstrap_track:
        active_event = _active_event_record(
            plan,
            targets,
            specs,
            prices_by_asset,
            signal_date=signal_date,
            target_identity=target_identity,
            execution_hint=execution_hint,
            applied_at=run_at.isoformat(),
            failures=report.failures,
        )
    else:
        active_event = _active_event_record(
            plan,
            targets,
            specs,
            prices_by_asset,
            signal_date=signal_date,
            target_identity=target_identity,
            execution_hint=execution_hint,
            applied_at=str(state.get("last_run_at") or run_at.isoformat()),
            failures=report.failures,
        )
        latest_journal_signal = (
            str(latest_row(journal).get("signal_date"))
            if not journal.empty and latest_row(journal) is not None
            else ""
        )
        if state.get("last_status") != "ok" or latest_journal_signal != str(
            pd.Timestamp(signal_date).date()
        ):
            active_event["position_status"] = "partial"
    active_event = _record_stopped_fills(
        active_event,
        stop_fills,
        include_before_application=True,
    )
    if (
        _risk_cap_was_scaled(plan.warnings)
        and not _position_application_failures(report.failures)
    ):
        active_event["risk_overlay"] = {
            "reason": "risk_cap_scaled",
            "applied_at": run_at.isoformat(),
            "target_quantities": _risk_overlay_quantities(
                active_event,
                positions=report.positions_after,
                symbol_assets=symbol_to_asset_index(relevant_symbols),
            ),
        }

    completion_issues = (
        _event_completion_issues(
            active_event,
            positions=report.positions_after,
            symbol_assets=symbol_to_asset_index(relevant_symbols),
            specs_by_symbol={
                spec.symbol.upper(): spec for spec in specs.values()
            },
        )
        if args.live
        else []
    )
    for issue in completion_issues:
        report.failures.append(
            {
                "symbol": "*",
                "action": "VERIFY",
                "side": "-",
                "size": "-",
                "error": f"active event position completion failed: {issue}",
            }
        )
    position_failures = _position_application_failures(report.failures)
    active_event["position_status"] = "ok" if not position_failures else "partial"
    active_event["position_failures"] = position_failures

    status = "ok" if not report.failures else "partial"
    message = format_execution_report(
        report,
        signal_date=str(signal_date.date()),
        spec=args.spec,
        execution_hint=execution_hint.strftime("%Y-%m-%d %H:%M UTC"),
        targets=targets,
        lot_notional=lot_notional,
        planned_orders=planned_orders,
        warnings=warnings,
        prev_equity=prev_equity,
        prev_day_pnl=prev_day_pnl,
        capital_flow=capital_flow,
        run_at=run_at,
        event_age_days=event_age_days,
        target_rebalance_enabled=args.live and plan_mode == "fresh",
        target_status_note=(
            "DRY RUN：以下为按当前计划应达到的目标，未回读为已成交仓位"
            if not args.live
            else (
                "按冻结事件数量补齐未完成仓位，不按今日权益重算"
                if plan_mode == "complete"
                else (
                    "今日无新目标事件，不做权重再平衡"
                    if not fresh_target_event
                    else "最新目标事件已完整应用，不做旧权重再平衡"
                )
            )
        ),
    )
    print(message)

    def notify_report() -> None:
        token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN")
        if not token:
            raise SystemExit("ATLAS20_TELEGRAM_BOT_TOKEN is not set")
        chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
        if not chat_ids:
            raise SystemExit("ATLAS20_TELEGRAM_CHAT_ID is not set")
        api_base = os.environ.get("ATLAS20_TELEGRAM_API_BASE", "https://api.telegram.org")
        for chat_id in chat_ids:
            send_telegram_message(message, token=token, chat_id=chat_id, api_base=api_base)
            print(f"Notified execution report {key} to {chat_id}")

    if args.live:
        closed_funding, funding_notes = _closed_funding_for_report(
            client,
            previous=funding_previous,
            report=report,
            run_at=run_at,
        )
        notes.extend(funding_notes)
        entry = _journal_entry(
            report,
            signal_date=str(signal_date.date()),
            run_at=run_at,
            prev_equity=prev_equity,
            capital_flow=capital_flow,
            warnings=notes,
            previous=previous,
            closed_position_funding=closed_funding,
            bootstrap_track=bootstrap_track,
        )
        _persist_run_result(
            json_out=args.json_out,
            payload={
                "spec": args.spec,
                "mode": "execution",
                "signal_date": str(signal_date.date()),
                "execution_hint": str(execution_hint),
                "live_execution_hint": str(execution_hint),
                "event_execution_hint": str(event_execution_hint),
                "client_oid_prefix": client_oid_prefix,
                "quotes": {
                    asset: quotes[symbol].as_dict()
                    for asset, symbol in relevant_symbols.items()
                    if asset in required_assets and symbol in quotes
                },
                "plan": plan.as_dict(),
                "report": report.as_dict(),
                "status": status,
            },
            journal_file=args.journal_file,
            entry=entry,
            state_file=args.state_file,
            key=key,
            status=status,
            report=report,
            account_fp=account_fp,
            active_event=active_event,
            stop_reconciliation_through=stop_reconciliation_through,
            notify=notify_report if args.notify else None,
        )
        print(f"journal updated: {args.journal_file} ({entry.date})")
    elif args.notify:
        notify_report()

    if report.failures:
        print(f"{len(report.failures)} order(s) failed; state written as {status}")
        return 1
    return 0


def _handle_fatal_execution(args: argparse.Namespace, exc: BaseException) -> int:
    """Persist and notify a pre-report execution failure without marking done."""

    now = datetime.now(timezone.utc)
    detail = str(exc) or type(exc).__name__
    message = "\n".join(
        [
            "🚨 Atlas20 实盘执行失败",
            f"规格: {args.spec}",
            f"时间: {now.isoformat()}",
            f"错误: {type(exc).__name__}: {detail}",
            "执行状态未标记为完成；下一次窗口内重试仍可继续。",
        ]
    )
    if args.live:
        payload = {
            "spec": args.spec,
            "status": "error",
            "occurred_at": now.isoformat(),
            "error_type": type(exc).__name__,
            "error": detail,
        }
        try:
            ensure_dir(args.json_out.parent)
            atomic_write_text(
                args.json_out,
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            )
        except OSError as persist_exc:
            print(
                f"could not persist fatal execution report: {persist_exc}",
                file=sys.stderr,
            )
    print(message)
    if args.notify:
        token = os.environ.get("ATLAS20_TELEGRAM_BOT_TOKEN", "")
        chat_ids = _chat_ids(os.environ.get("ATLAS20_TELEGRAM_CHAT_ID"))
        if token and chat_ids:
            api_base = os.environ.get(
                "ATLAS20_TELEGRAM_API_BASE", "https://api.telegram.org"
            )
            for chat_id in chat_ids:
                try:
                    send_telegram_message(
                        message,
                        token=token,
                        chat_id=chat_id,
                        api_base=api_base,
                    )
                except Exception as notify_exc:
                    print(
                        f"could not send fatal Telegram alert: {notify_exc}",
                        file=sys.stderr,
                    )
        else:
            print(
                "no Telegram credentials available for fatal alert",
                file=sys.stderr,
            )
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.live and not args.reconcile_only and not args.require_isolated:
        return _handle_fatal_execution(
            args,
            SystemExit(
                "live execution requires --require-isolated for the frozen live track"
            ),
        )
    lock: TextIO | None = None
    if args.live:
        try:
            lock = _acquire_execution_lock(args.lock_file)
        except Exception as exc:
            return _handle_fatal_execution(args, exc)
        if lock is None:
            print(f"another Atlas20 execution process holds {args.lock_file}; nothing to do")
            return 0
    try:
        try:
            return _main(args)
        except SystemExit as exc:
            code = exc.code
            if code in (None, 0):
                return 0
            return _handle_fatal_execution(args, exc)
        except Exception as exc:
            return _handle_fatal_execution(args, exc)
    finally:
        if lock is not None:
            _release_execution_lock(lock)


if __name__ == "__main__":
    raise SystemExit(main())
