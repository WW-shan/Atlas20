"""Execute the frozen daily plan on a real Bitget account and report it.

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
  re-reads the account so it self-corrects.

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
from math import isfinite
import os
from pathlib import Path
import sys
from typing import Any, Callable, TextIO

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
from atlas20.derivatives.execution import build_execution_plan  # noqa: E402
from atlas20.derivatives.live_chain import (  # noqa: E402
    LS45_G125_FROZEN_CONFIG,
    LS45_G125_MANIFEST_TOP_LEVEL,
    LS45_G125_SPEC,
    live_execution_hint_for_signal,
    manifest_spec_issues,
    manifest_staleness_hours,
)
from atlas20.derivatives.live_executor import (  # noqa: E402
    ExecutionReport,
    execute_plan,
    format_execution_report,
)
from atlas20.derivatives.live_journal import (  # noqa: E402
    DEFAULT_CAPITAL_FLOWS_FILE,
    JournalEntry,
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
    missing_contract_specs,
    spec_symbol_universe,
    specs_from_instruments,
    symbol_to_asset_index,
    target_gross_weight,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402
from scripts.send_telegram_signal import _chat_ids, _read_state, send_telegram_message  # noqa: E402

DEFAULT_STATE_FILE = Path("data/ls45_g125_execution_state.json")
DEFAULT_JOURNAL_FILE = Path("reports/ls45_live_g125_live/journal.csv")
DEFAULT_MANIFEST_FILE = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_KILL_SWITCH = Path("data/ls45_g125_execution.KILL")
DEFAULT_JSON_OUT = Path("reports/ls45_live_g125_live/latest.json")
DEFAULT_LOCK_FILE = Path("data/ls45_g125_execution.lock")
DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_oos_20261112")
DEFAULT_PANEL_FILE = Path("data/processed/panel_daily.csv")


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
    parser.add_argument("--allow-stale-signal", action="store_true")
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


def _manifest_spec_issues(
    manifest: dict[str, Any], args: argparse.Namespace
) -> list[str]:
    """Check that the manifest and live CLI describe the same frozen book."""

    expected_config = dict(LS45_G125_FROZEN_CONFIG)
    expected_config["long_buffer"] = float(args.long_buffer)
    expected_config["short_buffer"] = float(args.short_buffer)
    expected_config["short_stop_loss_pct"] = float(args.short_stop_loss_pct)
    expected_config["max_total_gross"] = float(args.max_gross_multiple)
    expected_top_level = dict(LS45_G125_MANIFEST_TOP_LEVEL)
    expected_top_level["max_total_gross"] = float(args.max_gross_multiple)
    expected_top_level["cost_bps"] = float(args.cost_bps)

    issues = manifest_spec_issues(
        manifest,
        expected_spec=LS45_G125_SPEC,
        expected_frozen_config=expected_config,
        expected_top_level=expected_top_level,
    )
    if str(args.spec) != LS45_G125_SPEC:
        issues.append(
            f"live --spec={args.spec!r}, expected {LS45_G125_SPEC!r}"
        )
    if abs(float(args.leverage) - 2.0) > 1e-9:
        issues.append(
            f"live leverage={float(args.leverage):g}x, expected 2x isolated"
        )
    return issues


def _stamp_assets(rows: list[dict], symbols_by_asset: dict[str, str]) -> list[dict]:
    """Add the model's asset id to each venue position row."""

    by_symbol = symbol_to_asset_index(symbols_by_asset)
    stamped: list[dict] = []
    for row in rows:
        record = dict(row)
        symbol = str(record.get("symbol") or "").upper()
        record.setdefault("asset", by_symbol.get(symbol, symbol.replace("USDT", "")))
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
        if action != "CLOSE":
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
        if str(fill.action).upper() == "CLOSE"
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
            if same_cycle and prior_funding is not None:
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
) -> None:
    state = _read_state(path)
    if account_fp:
        state["account_fingerprint"] = account_fp
    state["last_key"] = key
    state["last_status"] = status
    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    runs = state.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(
        {
            "key": key,
            "status": status,
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

    prior_notes = _decoded_notes(previous.get("notes"))
    # A retry refreshes volatile run facts instead of appending every observed
    # value.  Keeping both old and new capital-flow/freshness notes makes the
    # row look as if cash was deposited twice or the data moved backwards.
    volatile_prefixes = ("外部资金流 ", "数据管线:")
    stable_prior = [
        note for note in prior_notes if not any(note.startswith(prefix) for prefix in volatile_prefixes)
    ]
    notes = list(dict.fromkeys([*stable_prior, *current.notes]))
    return replace(current, fees_today=round(fees, 8), trades=trades, notes=notes)


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
    notify: Callable[[], None] | None = None,
) -> None:
    """Persist artifacts in an order that never marks an unwritten run as done."""

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
    _write_state(state_file, key, status, report, account_fp=account_fp)


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


def _main(args: argparse.Namespace) -> int:
    if args.kill_switch.exists():
        raise SystemExit(
            f"kill switch present at {args.kill_switch}; refusing to trade "
            "(delete the file to resume)"
        )

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
        manifest_issues = _manifest_spec_issues(manifest, args)
        if manifest_issues:
            raise SystemExit(
                "frozen manifest does not match the current LS45-G125 live "
                "specification: " + "; ".join(manifest_issues)
            )
    if manifest is not None and (args.live or args.require_data_audit):
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
        )
        if not data_audit.passed:
            raise SystemExit(
                "data audit failed before live execution: "
                + "; ".join(data_audit.hard_failures[:10])
            )
        expected_fingerprint = manifest.get("data_fingerprint")
        actual_fingerprint = data_audit.provenance.get("fingerprint")
        if not expected_fingerprint:
            raise SystemExit("manifest is missing data_fingerprint; rebuild the LS45 signal")
        if expected_fingerprint != actual_fingerprint:
            raise SystemExit(
                "manifest data_fingerprint does not match the current inputs: "
                f"manifest={expected_fingerprint}, current={actual_fingerprint}"
            )
        if manifest.get("data_audit_passed") is not True:
            raise SystemExit("manifest records a failed data audit; refusing to execute")
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
                    f"reaches {signal_end}; refresh the LS45 signal first"
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

    targets = {
        str(record["asset"]): float(record["target_weight"])
        for record in book.to_dict("records")
        if abs(float(record["target_weight"])) > 0.0
    }
    gross_weight = target_gross_weight(targets)
    if gross_weight > float(args.max_gross_multiple) + 1e-9:
        raise SystemExit(
            f"frozen target gross {gross_weight:.6f}x exceeds the "
            f"{float(args.max_gross_multiple):g}x spec cap"
        )
    symbols_by_asset = load_symbol_map(args.symbol_map)
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
    account = account_state_from_bitget(client, {**symbols_by_asset, **relevant_symbols})
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
        if position.symbol.upper() in prices:
            prices_by_asset.setdefault(asset, prices[position.symbol.upper()])

    plan = build_execution_plan(
        account,
        targets,
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
        taker_fee_rate=max(float(args.cost_bps), 0.0) / 10_000.0,
        min_rebalance_usdt=float(args.min_rebalance_usdt),
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

    # Idempotency is per *run day*, not per signal date: the book only changes
    # when a sleeve changes its pick, so keying on the signal date alone would
    # silently skip every day in between - no rebalance check, no daily
    # report, no ledger row.  A second run on the same day still skips.
    run_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"{args.spec}|{signal_date.date()}|{run_day}"
    state = _read_state(args.state_file)
    binding_issue = account_state_binding_issue(state, account_fp)
    if binding_issue is not None:
        raise SystemExit(
            f"{binding_issue}; archive and reset the old execution state before trading"
        )
    already = state.get("last_key") == key and state.get("last_status") == "ok"
    if already and not args.force and args.live:
        print(f"already executed {key} (status ok); nothing to do")
        return 0
    client_oid_prefix = _attempt_client_oid_prefix(key, state, account_fp=account_fp)

    lot_notional = {
        asset: float(spec.min_order_qty or spec.quantity_multiplier) * prices_by_asset[asset]
        for asset, spec in specs.items()
        if asset in prices_by_asset
    }
    warnings = [*plan.warnings, *warnings]
    run_at = datetime.now(timezone.utc)
    journal = load_journal(args.journal_file)
    previous = previous_row(journal, run_at.strftime("%Y-%m-%d"))
    prev_equity = float(previous["equity"]) if previous and previous.get("equity") is not None else None
    capital_flow = _capital_flow_for_run(
        journal,
        args.capital_flows_file,
        run_at=run_at,
    )
    if abs(capital_flow) > 0.005:
        warnings.append(f"外部资金流 {capital_flow:+.2f} USDT（已从盈亏中剔除）")
    notes = list(warnings)
    if freshness_note:
        notes.append(freshness_note)
    prev_day_pnl = (
        float(previous["day_pnl"])
        if previous and previous.get("day_pnl") is not None
        else None
    )

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
            report.positions_after, {**symbols_by_asset, **relevant_symbols}
        )
        planned_orders = list(plan.orders)
    else:
        hold_mode = client.hold_mode()
        requested = {
            "auto": "isolated",
            "isolated": "isolated",
            "crossed": "crossed",
        }[args.margin_mode]
        report = execute_plan(
            client,
            plan,
            signal_date=str(signal_date.date()),
            leverage=float(args.leverage),
            margin_mode=requested,
            require_isolated=bool(args.require_isolated),
            known_protected_short_stops=protected_short_stops(journal),
            symbol_assets=symbol_to_asset_index({**symbols_by_asset, **relevant_symbols}),
            hold_mode=hold_mode,
            client_oid_prefix=client_oid_prefix,
        )
        report.positions_after = _stamp_assets(
            report.positions_after, {**symbols_by_asset, **relevant_symbols}
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
        closed_funding: dict[str, float] = {}
        funding_notes: list[str] = []
        needs_closed_funding = False
        if previous is not None:
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
            for prior in prior_positions if isinstance(prior_positions, list) else []:
                if not isinstance(prior, dict):
                    continue
                prior_symbol = str(prior.get("symbol") or "").upper()
                prior_side = str(prior.get("side") or "").lower()
                if prior_symbol and current_sides.get(prior_symbol) != prior_side:
                    needs_closed_funding = True
                    break
            needs_closed_funding = needs_closed_funding or any(
                str(fill.action).upper() == "CLOSE" for fill in report.fills
            )
        if needs_closed_funding and previous is not None and previous.get("run_at_utc"):
            try:
                previous_at = pd.Timestamp(previous["run_at_utc"])
                start_ms = int((previous_at - pd.Timedelta(hours=1)).timestamp() * 1000)
                end_ms = int((run_at + pd.Timedelta(hours=1)).timestamp() * 1000)
                history = client.position_history(
                    start_time_ms=start_ms,
                    end_time_ms=end_ms,
                )
                closed_funding, funding_notes = _closed_funding_from_history(
                    history,
                    previous=previous,
                    current_positions=report.positions_after,
                    fills=report.fills,
                    previous_run_at=previous_at,
                    run_at=run_at,
                )
            except (BitgetAPIError, ValueError, OSError) as exc:
                funding_notes.append(
                    f"资金费归因不完整：读取平仓持仓历史失败（{exc}）"
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
        )
        _persist_run_result(
            json_out=args.json_out,
            payload={
                "spec": args.spec,
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
