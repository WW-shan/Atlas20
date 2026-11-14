"""Cross-check the live derivatives track against the venue, end to end.

Answers one question: *can every number in the daily report be reproduced
from an independent source?*  It re-reads the exchange, the frozen target
book and the local ledger, then checks

1. the account identity ``usdtEquity == USDT-equivalent collateral + isolated margin + unrealisedPnl``,
2. account-level ``positionValue`` is reconciled with open legs, using the
   isolated ``current-position`` rows when Bitget exposes zero there,
3. every trade in the ledger exists in the venue's order history with the
   same quantity, average price and fee,
4. the current book matches the frozen target book (within one contract lot),
5. the ledger's PnL chain adds up after excluding external capital flows,
6. nothing is held that the frozen book does not ask for,
7. the gross notional, venue leverage and isolated-margin utilization respect
   the selected frozen track profile.

Exit code 0 when every hard check passes, 1 otherwise.  Read-only: it never
places or cancels an order.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from math import ceil, isfinite
import json
from pathlib import Path
import sys

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.account import (
    MARK_PRICE_TRIGGER,
    BitgetCredentials,
    BitgetPrivateClient,
    account_fingerprint,
    account_state_binding_issue,
    isolated_margin_capability_error,
)  # noqa: E402
from atlas20.derivatives.bitget import BitgetAPIError  # noqa: E402
from atlas20.derivatives.data_audit import audit_derivatives_data  # noqa: E402
from atlas20.derivatives.execution import ContractSpec  # noqa: E402
from atlas20.derivatives.live_chain import (  # noqa: E402
    live_track_profile,
    manifest_spec_issues,
    manifest_staleness_hours,
    manifest_targets_hash_issue,
)
from atlas20.derivatives.live_executor import short_stop_symbol_issue  # noqa: E402
from atlas20.derivatives.live_journal import (  # noqa: E402
    DEFAULT_CAPITAL_FLOWS_FILE,
    effective_event_target_quantities,
    load_journal,
    net_capital_flow,
    protected_short_stops,
    protected_short_symbols,
)
from atlas20.logging_utils import atomic_write_text, ensure_dir  # noqa: E402

from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    DEFAULT_TARGETS_FILE,
    TRACKED_SPEC,
    fetch_public_instruments,
    load_symbol_map,
    missing_asset_mappings,
    spec_symbol_universe,
    specs_from_instruments,
    symbol_to_asset_index,
    target_weights_from_book,
    target_gross_weight,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402

DEFAULT_JOURNAL_FILE = Path("reports/ls45_live_g125_live/journal.csv")
DEFAULT_MANIFEST_FILE = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_JSON_OUT = Path("reports/ls45_live_g125_live/audit.json")
DEFAULT_DRILL_REGISTRY = Path("reports/ls45_live_g125_live/venue_drill_order_registry.json")
DEFAULT_STATE_FILE = Path("data/ls45_g125_execution_state.json")
DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_oos_20261112")
DEFAULT_PANEL_FILE = Path("data/processed/panel_daily.csv")
SPEC_VENUE_LEVERAGE = 2.0
SPEC_MIN_MARGIN_RATIO = 0.45
EXECUTION_FLOOR_USDT = 20.0


def _execution_floor_issue(equity: float, *, floor_usdt: float) -> str | None:
    """Explain why the executor would refuse to add new risk."""

    if equity < float(floor_usdt):
        return f"权益 {equity:.2f} USDT 低于执行下限 {float(floor_usdt):.2f} USDT"
    return None


def _num(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _unknown_position_symbols(
    positions: list[dict],
    symbols_by_asset: dict[str, str],
) -> list[str]:
    index = symbol_to_asset_index(symbols_by_asset)
    return sorted(
        {
            str(row.get("symbol") or "").upper()
            for row in positions
            if str(row.get("symbol") or "").upper() not in index
        }
    )


def _position_risk_issues(
    positions: list[dict],
    *,
    expected_leverage: float = SPEC_VENUE_LEVERAGE,
    min_margin_ratio: float = SPEC_MIN_MARGIN_RATIO,
) -> list[str]:
    """Check venue margin mode, leverage and the per-leg initial buffer."""

    issues: list[str] = []
    for row in positions:
        qty = _position_signed_qty(row)
        if abs(qty) <= 1e-12:
            continue
        symbol = str(row.get("symbol") or "").upper() or "<missing-symbol>"
        mode = str(row.get("marginMode") or "").strip().lower()
        if mode != "isolated":
            issues.append(f"{symbol}: marginMode={mode or 'missing'}，要求 isolated")

        pos_side = str(row.get("posSide") or "").lower()
        raw_leverage = row.get("leverage")
        if raw_leverage in (None, ""):
            raw_leverage = (
                row.get("shortLeverage")
                if pos_side == "short"
                else row.get("longLeverage")
            )
        leverage = _num(raw_leverage)
        if leverage <= 0.0:
            issues.append(f"{symbol}: leverage 缺失或非法 ({raw_leverage!r})")
        elif abs(leverage - expected_leverage) > 1e-9:
            issues.append(
                f"{symbol}: leverage={leverage:g}，要求 {expected_leverage:g}x"
            )

        mark = _num(row.get("markPrice") or row.get("avgPrice"))
        notional = abs(qty) * mark
        raw_margin = row.get("positionBalance")
        if raw_margin in (None, ""):
            raw_margin = row.get("marginSize")
        if raw_margin in (None, ""):
            raw_margin = row.get("isolatedMargin")
        margin = _num(raw_margin)
        if notional <= 0.0:
            issues.append(f"{symbol}: 无法计算名义价值 (qty={qty:g}, mark={mark:g})")
        elif margin <= 0.0:
            issues.append(f"{symbol}: positionBalance 缺失或为零")
        else:
            ratio = margin / notional
            if ratio + 1e-9 < min_margin_ratio:
                issues.append(
                    f"{symbol}: margin buffer {ratio:.3%} < {min_margin_ratio:.0%}"
                )
    return issues


def _finite_number_issue(value: object, field: str) -> str | None:
    if value is None or value == "":
        return f"{field} 缺失"
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return f"{field} 非法 ({value!r})"
    if not isfinite(number):
        return f"{field} 非有限值 ({value!r})"
    return None


def _account_data_issues(assets: dict) -> list[str]:
    issues: list[str] = []
    for key in ("usdtEquity", "usdtUnrealisedPnl", "positionValue"):
        issue = _finite_number_issue(assets.get(key), key)
        if issue:
            issues.append(issue)
    rows = assets.get("assets")
    if not isinstance(rows, list):
        issues.append("assets rows 缺失或不是数组")
        rows = []
    usdt_row = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and str(row.get("coin", "")).upper() == "USDT"
        ),
        None,
    )
    if usdt_row is None:
        issues.append("USDT asset row 缺失")
    else:
        for key in ("balance", "available"):
            issue = _finite_number_issue(usdt_row.get(key), f"USDT {key}")
            if issue:
                issues.append(issue)
    for row in rows:
        if not isinstance(row, dict):
            issues.append("asset row is not an object")
            continue
        coin = str(row.get("coin") or "").strip().upper() or "<missing-coin>"
        if coin == "USDT":
            continue
        issue = _finite_number_issue(row.get("usdValue"), f"{coin} usdValue")
        if issue:
            issues.append(issue)
    return issues


def _usdt_equivalent_balance(assets: dict) -> float:
    """Collateral expressed in the account's USDT-equity convention.

    Unified multi-assets accounts can hold BGB or another coin alongside USDT.
    USDT rows contribute their ``equity`` one-for-one; other coins contribute
    their venue-provided ``usdValue``.  Treating only the USDT row as the whole
    balance produces a false identity failure on an otherwise valid account.
    """

    total = 0.0
    for row in assets.get("assets") or []:
        if not isinstance(row, dict):
            continue
        coin = str(row.get("coin") or "").upper()
        if coin == "USDT":
            total += _num(row.get("equity"))
            if row.get("equity") in (None, ""):
                total += _num(row.get("balance"))
        else:
            total += _num(row.get("usdValue"))
    return total


def _isolated_margin_balance(positions: list[dict]) -> float:
    """Sum the margin held inside open isolated position legs."""

    return sum(
        _num(row.get("positionBalance"))
        for row in positions
        if abs(_num(row.get("total"))) > 1e-12
    )


def _account_identity_components(
    assets: dict,
    positions: list[dict],
) -> tuple[float, float, float, float]:
    """Return the four values used by the UTA account identity check."""

    return (
        _num(assets.get("usdtEquity")),
        _usdt_equivalent_balance(assets),
        _isolated_margin_balance(positions),
        _num(assets.get("usdtUnrealisedPnl")),
    )


def _position_value_reconciliation(
    reported_position_value: float,
    mark_notional: float,
    positions: list[dict],
) -> tuple[bool, str]:
    """Reconcile the account-level value with the independent position rows.

    Bitget's UTA ``assets.positionValue`` is zero for isolated futures while
    ``current-position`` still carries the open legs.  In that specific shape,
    use the position rows and require every open leg to be isolated with a
    positive ``positionBalance``; a zero account-level value without that
    evidence remains a hard failure.
    """

    tolerance = max(0.05, 0.003 * abs(mark_notional))
    if abs(reported_position_value - mark_notional) <= tolerance:
        return (
            True,
            f"交易所 {reported_position_value:.4f} vs 重算 {mark_notional:.4f}",
        )

    active = [
        row for row in positions if abs(_num(row.get("total"))) > 1e-12
    ]
    isolated_zero = (
        abs(reported_position_value) <= 1e-12
        and bool(active)
        and all(str(row.get("marginMode") or "").lower() == "isolated" for row in active)
        and all(_num(row.get("positionBalance")) > 0.0 for row in active)
    )
    if isolated_zero:
        return (
            True,
            "Bitget assets.positionValue=0 for isolated legs; "
            f"current-position 重算 {mark_notional:.4f}",
        )

    return (
        False,
        f"交易所 {reported_position_value:.4f} vs 重算 {mark_notional:.4f}；"
        "positionValue=0 回退需要所有持仓均为 isolated 且 positionBalance>0",
    )


def _position_data_issues(positions: list[dict]) -> list[str]:
    issues: list[str] = []
    for row in positions:
        symbol = str(row.get("symbol") or "").upper() or "<missing-symbol>"
        issue = _finite_number_issue(row.get("total"), f"{symbol} total")
        if issue:
            issues.append(issue)
            continue
        total = float(row.get("total"))
        if abs(total) <= 1e-12:
            continue
        pos_side = str(row.get("posSide") or "").strip().lower()
        if pos_side not in {"", "long", "short", "net"}:
            issues.append(f"{symbol} posSide 非法 ({pos_side!r})")
        entry_value = row.get("avgPrice")
        issue = _finite_number_issue(entry_value, f"{symbol} avgPrice")
        if issue:
            issues.append(issue)
        elif float(entry_value) <= 0.0:
            issues.append(f"{symbol} avgPrice must be positive ({entry_value!r})")
        mark_value = row.get("markPrice", row.get("avgPrice"))
        issue = _finite_number_issue(mark_value, f"{symbol} markPrice")
        if issue:
            issues.append(issue)
        elif float(mark_value) <= 0.0:
            issues.append(f"{symbol} markPrice must be positive ({mark_value!r})")
    return issues


def _position_side_issues(positions: list[dict]) -> list[str]:
    """Reject duplicate or opposite hedge legs for one frozen-book asset."""

    sides_by_symbol: dict[str, list[str]] = {}
    for row in positions:
        symbol = str(row.get("symbol") or "").upper() or "<missing-symbol>"
        try:
            total = float(row.get("total"))
        except (TypeError, ValueError):
            continue
        if not isfinite(total) or abs(total) <= 1e-12:
            continue
        pos_side = str(row.get("posSide") or "").strip().lower()
        if pos_side == "long":
            side = "long"
        elif pos_side == "short":
            side = "short"
        elif pos_side in {"", "net"}:
            side = "short" if total < 0.0 else "long"
        else:
            side = "unknown"
        sides_by_symbol.setdefault(symbol, []).append(side)

    issues: list[str] = []
    for symbol, sides in sorted(sides_by_symbol.items()):
        unique = set(sides)
        if len(sides) > 1:
            if unique == {"long", "short"}:
                issues.append(f"{symbol}:long+short")
            else:
                issues.append(f"{symbol}:duplicate-{sides[0]}")
    return issues


def _fees(row: dict) -> float:
    total = 0.0
    for item in row.get("feeDetail") or []:
        if isinstance(item, dict):
            total += _num(item.get("fee"))
    return total


def _journal_trade_rows(raw: object) -> list[dict]:
    """Decode one journal trades cell, preserving malformed data as an error."""

    try:
        rows = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("trades must be an array of objects")
    return [dict(row) for row in rows]


def _position_signed_qty(row: dict) -> float:
    """Signed quantity from both hedge and one-way position payloads."""

    total = _num(row.get("total"))
    if abs(total) <= 1e-12:
        return 0.0
    pos_side = str(row.get("posSide") or "").lower()
    short = pos_side == "short" or (pos_side in {"", "net"} and total < 0.0)
    return -abs(total) if short else abs(total)


def _position_signed_notional(row: dict) -> float:
    """Signed mark notional, negative for each short leg."""

    mark = _num(row.get("markPrice") or row.get("avgPrice"))
    return _position_signed_qty(row) * mark


def _position_short_stop_expectations(
    positions: list[dict],
    *,
    specs_by_symbol: Mapping[str, ContractSpec],
    short_stop_loss_pct: float,
) -> dict[str, float]:
    """Recompute each live short's 20% stop from venue entry and price grid."""

    if not isfinite(short_stop_loss_pct) or not 0.0 < short_stop_loss_pct < 1.0:
        return {}
    expected: dict[str, float] = {}
    for row in positions:
        if _position_signed_qty(row) >= 0.0:
            continue
        symbol = str(row.get("symbol") or "").upper()
        spec = specs_by_symbol.get(symbol)
        avg_price = _num(row.get("avgPrice"))
        if not symbol or spec is None or not isfinite(avg_price) or avg_price <= 0.0:
            continue
        expected[symbol] = float(
            spec.round_up_price(avg_price * (1.0 + float(short_stop_loss_pct)))
        )
    return expected


def _short_stop_expectation_gaps(
    positions: list[dict],
    *,
    expected_stops: Mapping[str, float],
) -> list[str]:
    """Open shorts whose stop cannot be independently recomputed."""

    expected = {str(symbol).upper() for symbol in expected_stops}
    open_shorts = {
        str(row.get("symbol") or "").upper()
        for row in positions
        if _position_signed_qty(row) < 0.0
    }
    return sorted(symbol for symbol in open_shorts if symbol and symbol not in expected)


def _short_stop_liquidation_issues(
    positions: list[dict],
    *,
    expected_stops: Mapping[str, float],
) -> list[str]:
    """Open shorts whose stop is not strictly before venue liquidation."""

    issues: list[str] = []
    for row in positions:
        if _position_signed_qty(row) >= 0.0:
            continue
        symbol = str(row.get("symbol") or "").upper()
        stop = _num(expected_stops.get(symbol))
        liquidation = _num(row.get("liquidationPrice"))
        if not symbol or stop <= 0.0 or liquidation <= 0.0 or stop >= liquidation:
            issues.append(symbol or "<missing-symbol>")
    return sorted(set(issues))


def _minimum_tradeable_qty(spec: ContractSpec, price: float) -> float | None:
    """Smallest exchange-step quantity that also clears the venue's USDT floor."""

    if not isfinite(price) or price <= 0.0:
        return None
    step = max(float(spec.quantity_multiplier), float(spec.min_order_qty), 0.0)
    if not isfinite(step) or step <= 0.0:
        return None
    required = max(float(spec.minimum_notional()), step * price) / price
    steps = max(1, int(ceil(required / step - 1e-12)))
    qty = spec.round_down_qty(float(steps) * step)
    if qty <= 0.0 or not spec.is_tradeable(qty, price):
        qty = spec.round_down_qty(qty + step)
    return qty if qty > 0.0 and spec.is_tradeable(qty, price) else None


def _minimum_trade_would_improve(
    actual_qty: float,
    target_qty: float,
    minimum_qty: float,
) -> bool:
    """Whether one venue-minimum order strictly reduces the target gap."""

    actual_gap = abs(actual_qty - target_qty)
    if target_qty > actual_qty:
        proposed = actual_qty + minimum_qty
    else:
        proposed = max(0.0, actual_qty - minimum_qty)
    return abs(proposed - target_qty) < actual_gap - 1e-12


def _active_event_state_issues(
    state: Mapping[str, object],
    *,
    signal_date: pd.Timestamp,
    journal: pd.DataFrame,
    expected_targets_sha256: str | None = None,
) -> list[str]:
    """Verify the persisted active event and its strategy-stop provenance."""

    issues: list[str] = []
    last_status = str(state.get("last_status") or "")
    if last_status != "ok":
        issues.append(f"execution state last_status={last_status or '<missing>'}, expected ok")
    event = state.get("active_event")
    if not isinstance(event, dict):
        return [*issues, "execution state has no active target event"]
    expected_signal = str(pd.Timestamp(signal_date).date())
    event_signal = str(event.get("signal_date") or "")
    if event_signal != expected_signal:
        issues.append(
            f"active event signal_date {event_signal or '<missing>'} != {expected_signal}"
        )
    if expected_targets_sha256 is not None:
        stored_hash = str(event.get("targets_sha256") or "")
        if stored_hash != str(expected_targets_sha256):
            issues.append(
                "active event targets_sha256 does not match the current target book"
            )
    position_status = str(event.get("position_status") or "")
    if position_status != "ok":
        issues.append(
            "active target event position application is incomplete "
            f"(status={position_status or '<missing>'})"
        )
    if event.get("applied_at"):
        try:
            applied_at = pd.Timestamp(event["applied_at"])
            if applied_at.tzinfo is None:
                applied_at = applied_at.tz_localize("UTC")
            else:
                applied_at = applied_at.tz_convert("UTC")
        except (TypeError, ValueError):
            issues.append("active event applied_at is invalid")
        else:
            raw_high_water = state.get("stop_reconciliation_through")
            try:
                high_water = pd.Timestamp(raw_high_water)
                if high_water.tzinfo is None:
                    high_water = high_water.tz_localize("UTC")
                else:
                    high_water = high_water.tz_convert("UTC")
            except (TypeError, ValueError):
                high_water = None
            if high_water is None or high_water < applied_at:
                issues.append(
                    "stop history high-water mark does not cover the active event"
                )

    journal_trades: dict[str, dict] = {}
    if not journal.empty:
        for value in journal["trades"]:
            try:
                rows = _journal_trade_rows(value)
            except ValueError:
                continue
            for trade in rows:
                order_id = str(trade.get("order_id") or "")
                if order_id:
                    journal_trades[order_id] = trade

    risk_overlay = event.get("risk_overlay")
    if risk_overlay is not None:
        if not isinstance(risk_overlay, dict):
            issues.append("active event risk_overlay is not an object")
        else:
            if str(risk_overlay.get("reason") or "") != "risk_cap_scaled":
                issues.append("active event risk_overlay reason is invalid")
            try:
                overlay_at = pd.Timestamp(risk_overlay.get("applied_at"))
                if overlay_at.tzinfo is None:
                    overlay_at = overlay_at.tz_localize("UTC")
                else:
                    overlay_at = overlay_at.tz_convert("UTC")
            except (TypeError, ValueError):
                issues.append("active event risk_overlay applied_at is invalid")
            overlay_quantities = risk_overlay.get("target_quantities")
            if not isinstance(overlay_quantities, dict) or not overlay_quantities:
                issues.append("active event risk_overlay target_quantities is invalid")
            else:
                for symbol, value in overlay_quantities.items():
                    try:
                        quantity = float(value)
                    except (TypeError, ValueError):
                        quantity = float("nan")
                    if not str(symbol).strip() or not isfinite(quantity) or quantity < 0.0:
                        issues.append("active event risk_overlay has an invalid quantity")
                        break

    stopped = event.get("stopped_symbols")
    if isinstance(stopped, dict):
        for raw_symbol, raw_record in stopped.items():
            symbol = str(raw_symbol).upper()
            if not isinstance(raw_record, dict):
                issues.append(f"{symbol}: stopped_symbols record is invalid")
                continue
            order_id = str(raw_record.get("order_id") or "")
            strategy_id = str(raw_record.get("strategy_order_id") or "")
            trade = journal_trades.get(order_id)
            expected_qty = _num(raw_record.get("quantity"))
            if (
                trade is None
                or str(trade.get("reason") or "") != "venue_strategy_stop"
                or str(trade.get("strategy_order_id") or "") != strategy_id
                or str(trade.get("symbol") or "").upper() != symbol
                or str(trade.get("action") or "").upper() != "CLOSE"
                or str(trade.get("side") or "").lower() != "buy"
                or str(trade.get("status") or "filled").lower() != "filled"
                or abs(_num(trade.get("qty")) - expected_qty)
                > max(1e-9, expected_qty * 1e-8)
            ):
                issues.append(
                    f"{symbol}: stopped event is not backed by its journal stop trade"
                )
    return issues


def _event_quantity_issues(
    *,
    target_quantities: Mapping[str, float],
    target_weights: Mapping[str, float],
    symbol_assets: Mapping[str, str],
    positions: list[dict],
    specs_by_symbol: Mapping[str, ContractSpec],
    event_prices: Mapping[str, float],
    stopped_symbols: Mapping[str, object],
) -> list[str]:
    """Compare live quantities with the quantity frozen at the target event.

    Event-driven strategies let USD weight drift between target rows.  The
    stable invariant is the coin quantity set at the last event, not today's
    ``target weight × equity``.  A venue-triggered stop is the only accepted
    reason for that leg to be flat before the next target event.
    """

    actual: dict[str, float] = {}
    for row in positions:
        symbol = str(row.get("symbol") or "").upper()
        if symbol:
            actual[symbol] = actual.get(symbol, 0.0) + _position_signed_qty(row)

    issues: list[str] = []
    stopped = {str(symbol).upper() for symbol in stopped_symbols}
    for symbol, raw_target_qty in target_quantities.items():
        upper = str(symbol).upper()
        target_qty = abs(_num(raw_target_qty))
        if target_qty <= 0.0:
            continue
        asset = str(symbol_assets.get(upper, upper.removesuffix("USDT").lower())).lower()
        target_weight = _num(target_weights.get(asset))
        if target_weight == 0.0:
            issues.append(f"{upper} 缺少事件目标方向")
            continue
        expected = target_qty if target_weight > 0.0 else -target_qty
        got = actual.get(upper, 0.0)
        price = _num(event_prices.get(asset))
        spec = specs_by_symbol.get(upper)
        minimum_qty = _minimum_tradeable_qty(spec, price) if spec is not None else None
        lot_qty = max(
            float(spec.min_order_qty or 0.0) if spec is not None else 0.0,
            float(spec.quantity_multiplier or 0.0) if spec is not None else 0.0,
        )
        tolerance = max(
            1.0 / price if price > 0.0 else 0.0,
            0.01 * target_qty,
            1.5 * lot_qty,
        )
        if upper in stopped:
            if abs(got) <= tolerance:
                continue
            issues.append(
                f"{upper} 已在旧事件中止损，下一目标事件前不得重开"
            )
            continue
        if abs(got - expected) <= tolerance:
            continue
        same_side = got != 0.0 and (got > 0.0) == (expected > 0.0)
        if (
            same_side
            and minimum_qty is not None
            and not _minimum_trade_would_improve(
                abs(got), target_qty, minimum_qty
            )
        ):
            continue
        if (
            abs(got) <= 1e-12
            and minimum_qty is not None
            and not _minimum_trade_would_improve(0.0, target_qty, minimum_qty)
        ):
            continue
        issues.append(
            f"{upper} 目标数量 {target_qty:.8g} vs 实际 {got:.8g}"
        )
    return issues


def _position_target_issues(
    *,
    targets: Mapping[str, float],
    signed_notional_by_asset: Mapping[str, float],
    equity: float,
    lot_notional_by_asset: Mapping[str, float],
    prices_by_asset: Mapping[str, float],
    contract_specs_by_asset: Mapping[str, ContractSpec],
) -> list[str]:
    """Report target drift that is material and operationally correctable.

    The declared 1 USDT / 1% / 1.5-lot tolerance remains the first gate.  A
    slightly larger residual is accepted only when both sides have the same
    sign and the smallest order the venue accepts would move the position
    farther from target.  Without that feasibility exception a $5 venue
    minimum can make every possible order worsen a small residual, leaving the
    live audit permanently red even though the planner correctly skips it.
    """

    issues: list[str] = []
    for asset, weight in targets.items():
        want = float(weight) * equity
        got = float(signed_notional_by_asset.get(asset, 0.0))
        tolerance = max(
            1.0,
            0.01 * abs(want),
            1.5 * float(lot_notional_by_asset.get(asset, 0.0)),
        )
        if abs(got - want) <= tolerance:
            continue

        price = float(prices_by_asset.get(asset, 0.0))
        spec = contract_specs_by_asset.get(asset)
        minimum_qty = _minimum_tradeable_qty(spec, price) if spec is not None else None
        same_side = got != 0.0 and want != 0.0 and (got > 0.0) == (want > 0.0)
        untradeable = (
            same_side
            and minimum_qty is not None
            and not _minimum_trade_would_improve(
                abs(got) / price,
                abs(want) / price,
                minimum_qty,
            )
        )
        if not untradeable:
            issues.append(f"{asset.upper()} 目标 {want:.2f} vs 实际 {got:.2f}")
    return issues


def _trade_mismatch(trade: dict, venue: dict) -> str | None:
    """Return the first reproducibility mismatch for one journaled fill."""

    same_qty = abs(_num(venue.get("cumExecQty")) - _num(trade.get("qty"))) <= 1e-9
    same_price = abs(_num(venue.get("avgPrice")) - _num(trade.get("avg_price"))) <= 1e-6
    same_fee = abs(_fees(venue) - _num(trade.get("fee"))) <= 1e-6
    if not (same_qty and same_price and same_fee):
        return (
            f"台账 {trade.get('qty')}/{trade.get('avg_price')}/{trade.get('fee')} "
            f"vs 交易所 {venue.get('cumExecQty')}/{venue.get('avgPrice')}/{_fees(venue):.8f}"
        )
    recorded_stop = trade.get("stop_loss")
    if (
        recorded_stop is not None
        and str(trade.get("reason") or "") != "venue_strategy_stop"
    ):
        venue_stop = _num(venue.get("stopLoss"))
        trigger = str(venue.get("slTriggerBy") or "").lower()
        order_type = str(venue.get("slOrderType") or "").lower()
        if (
            abs(venue_stop - _num(recorded_stop)) > 1e-6
            or trigger != MARK_PRICE_TRIGGER
            or order_type != "market"
        ):
            return (
                f"止损台账 {_num(recorded_stop):.8g}/mark/market vs 交易所 "
                f"{venue_stop:.8g}/{trigger or 'missing'}/{order_type or 'missing'}"
            )
    return None


def _short_stop_gaps(journal: pd.DataFrame, positions: list[dict]) -> list[str]:
    """Open short symbols with no journaled entry that carried a stop."""

    protected = protected_short_symbols(journal)
    gaps: list[str] = []
    for row in positions:
        if _position_signed_qty(row) >= 0.0:
            continue
        symbol = str(row.get("symbol") or "").upper()
        if symbol and symbol not in protected:
            gaps.append(symbol)
    return sorted(set(gaps))


def _terminal_strategy_order(row: dict) -> bool:
    status = str(row.get("orderStatus") or row.get("status") or "").lower()
    return status in {"cancelled", "canceled", "filled", "triggered", "failed"}


def _venue_short_stop_gaps(
    positions: list[dict],
    strategy_orders: list[dict],
    *,
    expected_stops: dict[str, float] | None = None,
) -> list[str]:
    """Open shorts without the expected visible mark-price market stop order."""

    wanted = {
        str(symbol).upper(): float(stop)
        for symbol, stop in (expected_stops or {}).items()
    }
    gaps: list[str] = []
    for position in positions:
        if _position_signed_qty(position) >= 0.0:
            continue
        symbol = str(position.get("symbol") or "").upper()
        if not symbol:
            continue
        issue = short_stop_symbol_issue(
            position,
            strategy_orders,
            expected_stop=wanted.get(symbol),
        )
        if issue is not None:
            gaps.append(symbol)
    return sorted(set(gaps))


def _short_stop_duplicate_issues(
    positions: list[dict],
    strategy_orders: list[dict],
) -> list[str]:
    """Open shorts with more than one active strategy stop."""

    open_shorts = {
        str(row.get("symbol") or "").upper()
        for row in positions
        if _position_signed_qty(row) < 0.0
    }
    counts: dict[str, int] = {}
    for row in strategy_orders:
        if _terminal_strategy_order(row):
            continue
        symbol = str(row.get("symbol") or "").upper()
        if symbol in open_shorts:
            counts[symbol] = counts.get(symbol, 0) + 1
    return sorted(symbol for symbol, count in counts.items() if count > 1)


def _strategy_stop_history_issues(
    stopped_symbols: Mapping[str, object],
    strategy_history: list[dict],
) -> list[str]:
    """Verify every imported stop in the venue's closed strategy history."""

    by_id = {
        str(row.get("orderId") or ""): row
        for row in strategy_history
        if str(row.get("orderId") or "")
    }
    issues: list[str] = []
    for raw_symbol, raw_record in stopped_symbols.items():
        symbol = str(raw_symbol).upper()
        if not isinstance(raw_record, dict):
            issues.append(f"{symbol}: stopped record is invalid")
            continue
        strategy_id = str(raw_record.get("strategy_order_id") or "")
        row = by_id.get(strategy_id)
        if row is None:
            issues.append(f"{symbol}: strategy stop {strategy_id or '<missing>'} not found")
            continue
        try:
            qty = _num(raw_record.get("quantity"))
            requested_qty = _num(raw_record.get("requested_quantity")) or qty
            stop = _num(raw_record.get("stop_loss"))
            venue_qty = _num(row.get("qty"))
            venue_stop = _num(row.get("stopLoss"))
        except (TypeError, ValueError):
            issues.append(f"{symbol}: stop history values are invalid")
            continue
        tolerance = max(1e-9, abs(stop) * 1e-8)
        if (
            str(row.get("symbol") or "").upper() != symbol
            or str(row.get("status") or "").lower() != "success"
            or str(row.get("posSide") or "").lower() not in {"", "short", "net"}
            or str(row.get("side") or "").lower() != "buy"
            or abs(venue_qty - requested_qty)
            > max(1e-9, abs(requested_qty) * 1e-8)
            or abs(venue_stop - stop) > tolerance
            or str(row.get("slTriggerBy") or "").lower() != MARK_PRICE_TRIGGER
            or str(row.get("slOrderType") or "").lower() != "market"
        ):
            issues.append(f"{symbol}: strategy stop history does not match the journal")
            continue
        try:
            venue_time = pd.to_datetime(
                int(row.get("updatedTime")), unit="ms", utc=True, errors="raise"
            )
            stored_time = pd.Timestamp(raw_record.get("triggered_at"))
            if stored_time.tzinfo is None:
                stored_time = stored_time.tz_localize("UTC")
            else:
                stored_time = stored_time.tz_convert("UTC")
        except (TypeError, ValueError, OverflowError):
            issues.append(f"{symbol}: strategy stop trigger timestamp is invalid")
            continue
        if abs((stored_time - venue_time).total_seconds()) > 1.0:
            issues.append(f"{symbol}: strategy stop trigger timestamp differs from venue")
    return issues


def _orphan_strategy_order_issues(
    positions: list[dict],
    strategy_orders: list[dict],
) -> list[str]:
    """Pending strategy orders that are not the expected stop for an open short."""

    open_shorts = {
        str(row.get("symbol") or "").upper()
        for row in positions
        if _position_signed_qty(row) < 0.0 and str(row.get("symbol") or "")
    }
    issues: list[str] = []
    for row in strategy_orders:
        if _terminal_strategy_order(row):
            continue
        symbol = str(row.get("symbol") or "").upper()
        if symbol in open_shorts:
            continue
        order_id = str(row.get("orderId") or row.get("clientOid") or "<unknown>")
        issues.append(f"{symbol or '<missing>'}:{order_id}")
    return sorted(issues)


def _unfilled_order_issues(rows: list[dict]) -> list[str]:
    """Every currently pending regular order, including manual orders."""

    issues: list[str] = []
    for row in rows:
        symbol = str(row.get("symbol") or "<missing>").upper()
        order_id = str(row.get("orderId") or "<missing>")
        client_oid = str(row.get("clientOid") or "<missing>")
        side = str(row.get("side") or "<missing>")
        filled = row.get("cumExecQty", "<missing>")
        quantity = row.get("qty", "<missing>")
        issues.append(
            f"{symbol}:{order_id}:{client_oid}:{side}:{filled}/{quantity}"
        )
    return issues


def _load_drill_order_ids(path: Path) -> set[str]:
    """Exact venue-drill order ids that are intentionally outside the live journal."""

    path = Path(path)
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read drill registry {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("orders"), list):
        raise ValueError(f"drill registry {path} must contain an orders array")
    ids: set[str] = set()
    for index, row in enumerate(payload["orders"]):
        if not isinstance(row, dict):
            raise ValueError(f"drill registry row {index} is not an object")
        order_id = str(row.get("order_id") or "").strip()
        purpose = str(row.get("purpose") or "").strip()
        if not order_id or not purpose:
            raise ValueError(f"drill registry row {index} needs order_id and purpose")
        ids.add(order_id)
    return ids


def _unjournaled_order_ids(
    history: list[dict],
    journal: pd.DataFrame,
    *,
    ignored_order_ids: set[str] | None = None,
) -> list[str]:
    """Filled/partially filled Atlas20 orders missing from the local ledger."""

    journaled: set[str] = set()
    if not journal.empty:
        for value in journal["trades"]:
            try:
                trades = json.loads(value or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(trades, list):
                continue
            for trade in trades:
                if isinstance(trade, dict) and trade.get("order_id"):
                    journaled.add(str(trade["order_id"]))
    ignored = {str(value) for value in (ignored_order_ids or set())}
    missing: list[str] = []
    for row in history:
        client_oid = str(row.get("clientOid") or "")
        if not client_oid.startswith(("a20", "atlas20")):
            continue
        qty = _num(row.get("cumExecQty"))
        if qty <= 1e-12:
            continue
        order_id = str(row.get("orderId") or "")
        if order_id and order_id not in journaled and order_id not in ignored:
            missing.append(order_id)
    return sorted(set(missing))


def _ledger_expected_equity(
    last: dict,
    *,
    current_positions: list[dict],
    capital_flow: float,
) -> tuple[float, list[str]]:
    """Roll the latest ledger snapshot forward to the live venue state.

    Mark-to-market changes belong in strategy PnL. Deposits and withdrawals do
    not, so the latter are added separately from the capital-flow ledger.
    """

    expected_equity = _num(last.get("equity")) + float(capital_flow)
    mismatches: list[str] = []
    try:
        ledger_positions = json.loads(last.get("positions") or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        return expected_equity, [f"台账 positions JSON 无效: {exc}"]
    if not isinstance(ledger_positions, list):
        return expected_equity, ["台账 positions 不是数组"]

    ledger_by_symbol: dict[str, dict] = {}
    for item in ledger_positions:
        if not isinstance(item, dict):
            return expected_equity, ["台账 positions 含有非对象记录"]
        symbol = str(item.get("symbol") or "")
        if not symbol:
            return expected_equity, ["台账 positions 含有空 symbol"]
        ledger_by_symbol[symbol] = item

    for row in current_positions:
        symbol = str(row.get("symbol") or "")
        ledger_row = ledger_by_symbol.pop(symbol, None)
        if ledger_row is None:
            mismatches.append(f"{symbol} 不在台账里")
            continue
        ledger_side = str(ledger_row.get("side") or "").lower()
        try:
            current_signed = _position_signed_qty(row)
        except (TypeError, ValueError) as exc:
            mismatches.append(f"{symbol} 当前仓位无效: {exc}")
            continue
        current_side = "short" if current_signed < 0.0 else "long"
        if ledger_side in {"long", "short"} and ledger_side != current_side:
            mismatches.append(
                f"{symbol} 方向变了：台账 {ledger_side} vs 当前 {current_side}"
            )
        ledger_mark = _num(ledger_row.get("mark_price"))
        if ledger_mark <= 0.0:
            mismatches.append(f"{symbol} 台账 mark_price 无效")
            continue
        expected_equity += current_signed * (_num(row.get("markPrice")) - ledger_mark)
    if ledger_by_symbol:
        mismatches.append(f"台账多了 {', '.join(sorted(ledger_by_symbol))}")
    return expected_equity, mismatches



def _ledger_equity_tolerance(equity: float) -> float:
    """Allow for cross-request marks without hiding a material ledger break."""

    return max(0.10, 0.0002 * abs(float(equity)))


def _pnl_chain_errors(journal: pd.DataFrame) -> list[str]:
    """Return every adjacent-row break in the capital-adjusted PnL chain."""

    if len(journal) < 2:
        return []
    frame = journal.sort_values("date").reset_index(drop=True)
    errors: list[str] = []
    for index in range(1, len(frame)):
        capital_flow = _num(frame.loc[index, "capital_flow"])
        expected = (
            _num(frame.loc[index, "equity"])
            - _num(frame.loc[index - 1, "equity"])
            - capital_flow
        )
        recorded = frame.loc[index, "day_pnl"]
        if pd.isna(recorded) or abs(_num(recorded) - expected) > 0.01:
            errors.append(
                f"{frame.loc[index, 'date']}: 记录 {_num(recorded):.4f} vs 重算 {expected:.4f}"
                f"（外部资金流 {capital_flow:+.4f}）"
            )
    return errors


def _funding_delta_errors(journal: pd.DataFrame) -> list[str]:
    """Validate funding attribution on unchanged open-position cycles."""

    if len(journal) < 2:
        return []
    frame = journal.sort_values("date").reset_index(drop=True)
    errors: list[str] = []

    def positions(value: object) -> dict[str, dict] | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            parsed = json.loads(value or "[]")
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, list):
            return None
        rows: dict[str, dict] = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").upper()
            if not symbol:
                continue
            try:
                qty = abs(float(item.get("qty") or item.get("size") or 0.0))
            except (TypeError, ValueError):
                return None
            if qty > 1e-12:
                rows[symbol] = item
        return rows

    for index in range(1, len(frame)):
        previous = positions(frame.loc[index - 1, "positions"])
        current = positions(frame.loc[index, "positions"])
        if previous is None or current is None or set(previous) != set(current):
            continue
        expected = 0.0
        complete = True
        for symbol in current:
            if str(previous[symbol].get("side") or "").lower() != str(
                current[symbol].get("side") or ""
            ).lower():
                complete = False
                break
            previous_raw = previous[symbol].get("funding_cumulative")
            current_raw = current[symbol].get("funding_cumulative")
            try:
                previous_funding = float(previous_raw)
                current_funding = float(current_raw)
            except (TypeError, ValueError):
                complete = False
                break
            if not isfinite(previous_funding) or not isfinite(current_funding):
                complete = False
                break
            expected += current_funding - previous_funding
        if not complete:
            continue
        recorded = _num(frame.loc[index, "funding_total"])
        if abs(recorded - expected) > 1e-6:
            errors.append(
                f"{frame.loc[index, 'date']}: 资金费 funding_total {recorded:+.8f} "
                f"vs 累计差重算 {expected:+.8f}"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL_FILE)
    parser.add_argument("--capital-flows-file", type=Path, default=DEFAULT_CAPITAL_FLOWS_FILE)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS_FILE)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--history-days", type=int, default=7)
    parser.add_argument("--equity-floor", type=float, default=EXECUTION_FLOOR_USDT)
    parser.add_argument("--manifest-file", type=Path, default=DEFAULT_MANIFEST_FILE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL_FILE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--drill-registry", type=Path, default=DEFAULT_DRILL_REGISTRY)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    args = parser.parse_args(argv)
    checked_at = datetime.now(timezone.utc)
    try:
        profile = live_track_profile(str(args.spec))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    spec_max_gross = float(profile.manifest_top_level["max_total_gross"])

    client = BitgetPrivateClient(BitgetCredentials.from_env())
    assets = client.account_assets()
    positions = client.current_positions()
    symbol_map = load_symbol_map(args.symbol_map)
    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    targets = target_weights_from_book(book, symbol_map)
    missing_mappings = missing_asset_mappings(symbol_map, targets)
    target_gross = target_gross_weight(targets)
    relevant = spec_symbol_universe(symbol_map, targets)
    session = requests.Session()
    specs = specs_from_instruments(fetch_public_instruments(session), relevant)

    equity, balance, isolated_margin, unrealised = _account_identity_components(
        assets, positions
    )
    mark_notional = sum(
        abs(_num(row.get("total"))) * _num(row.get("markPrice") or row.get("avgPrice"))
        for row in positions
    )

    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str, *, hard: bool = True) -> None:
        checks.append({"check": name, "ok": bool(ok), "hard": hard, "detail": detail})

    check(
        "冻结目标都有唯一 Bitget 合约映射",
        not missing_mappings,
        ", ".join(missing_mappings) or "全部有唯一映射",
    )

    try:
        drill_order_ids = _load_drill_order_ids(args.drill_registry)
    except ValueError as exc:
        drill_order_ids = set()
        check("venue drill 订单登记表可读", False, str(exc))
    else:
        check(
            "venue drill 订单登记表可读",
            True,
            f"{len(drill_order_ids)} 笔已登记；仅这些精确 orderId 不进入生产台账核对",
        )

    account_issues = _account_data_issues(assets)
    check(
        "账户 API 必需字段完整且有限",
        not account_issues,
        "；".join(account_issues) or "全部有效",
    )
    floor_issue = _execution_floor_issue(equity, floor_usdt=float(args.equity_floor))
    check(
        f"账户权益 >= 执行下限 {float(args.equity_floor):.2f} USDT",
        floor_issue is None,
        floor_issue or f"权益 {equity:.2f} USDT",
    )
    position_issues = _position_data_issues(positions)
    check(
        "持仓 API 必需字段完整且有限",
        not position_issues,
        "；".join(position_issues) or "全部有效",
    )
    position_side_issues = _position_side_issues(positions)
    check(
        "同一合约没有重复或反向对冲腿",
        not position_side_issues,
        ", ".join(position_side_issues) or "无重复或反向腿",
    )
    try:
        open_orders = client.unfilled_orders()
    except (BitgetAPIError, ValueError) as exc:
        open_orders = []
        check("交易所未成交订单可查询", False, f"查询失败：{exc}")
    else:
        pending_issues = _unfilled_order_issues(open_orders)
        check(
            "当前无未成交普通订单",
            not pending_issues,
            ", ".join(pending_issues) or "0 笔",
        )
    check(
        "账户恒等式 equity = USDT 等值抵押品 + isolated margin + uPnL",
        abs(equity - (balance + isolated_margin + unrealised)) <= 0.02,
        f"{equity:.4f} vs {balance:.4f} + {isolated_margin:.4f} + "
        f"{unrealised:.4f} = {balance + isolated_margin + unrealised:.4f}",
    )
    # ``assets`` and ``current-position`` are two round trips, so their marks
    # can differ by a few bps on a moving book; the tolerance says so.
    position_value_ok, position_value_detail = _position_value_reconciliation(
        _num(assets.get("positionValue")), mark_notional, positions
    )
    check(
        "仓位市值 = Σ 数量 × 标记价",
        position_value_ok,
        position_value_detail,
    )

    known_symbols = symbol_to_asset_index(symbol_map)
    unknown_symbols = _unknown_position_symbols(positions, symbol_map)
    check(
        "所有持仓合约都在冻结映射中",
        not unknown_symbols,
        ", ".join(unknown_symbols) or "全部有唯一映射",
    )
    risk_issues = _position_risk_issues(
        positions,
        expected_leverage=profile.venue_leverage,
        min_margin_ratio=SPEC_MIN_MARGIN_RATIO,
    )
    risk_legs = sum(1 for row in positions if abs(_position_signed_qty(row)) > 1e-12)
    check(
        f"每腿逐仓、{profile.venue_leverage:g}x 杠杆与保证金缓冲符合规格",
        not risk_issues,
        "；".join(risk_issues) or f"{risk_legs} 腿全部符合" if risk_legs else "无持仓",
    )
    try:
        account_info = client.account_info()
        current_account_fingerprint = account_fingerprint(account_info)
    except (BitgetAPIError, ValueError) as exc:
        capability_error = f"查询 API key/账户分类失败：{exc}"
        current_account_fingerprint = None
    else:
        capability_error = isolated_margin_capability_error(account_info)
    check(
        "API key 具备逐仓合约交易能力（或未见已知限制）",
        capability_error is None,
        capability_error or "未发现 copy-trading/elite 或只读限制",
    )
    state: dict = {}
    if current_account_fingerprint is None:
        binding_issue = "无法从账户信息计算指纹"
    elif not args.state_file.exists():
        binding_issue = f"执行状态文件不存在：{args.state_file}"
    else:
        try:
            raw_state = json.loads(args.state_file.read_text(encoding="utf-8"))
            if not isinstance(raw_state, dict):
                raise ValueError("state is not an object")
            state = raw_state
            binding_issue = account_state_binding_issue(state, current_account_fingerprint)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            binding_issue = f"执行状态文件不可读：{exc}"
    check(
        "执行状态绑定当前 Bitget 账户",
        binding_issue is None,
        binding_issue or "账户指纹一致",
    )

    # -- ledger vs venue -------------------------------------------------
    manifest_state: dict = {}
    if args.manifest_file.exists():
        try:
            loaded_manifest = json.loads(
                args.manifest_file.read_text(encoding="utf-8")
            )
            if isinstance(loaded_manifest, dict):
                manifest_state = loaded_manifest
        except (OSError, json.JSONDecodeError):
            manifest_state = {}
    journal = load_journal(args.journal_file)
    if journal.empty:
        check("台账存在", False, f"{args.journal_file} 不存在或为空")
        last = None
    else:
        last = journal.sort_values("date").iloc[-1].to_dict()
        # The row is a snapshot from minutes ago; roll it forward with live
        # marks and external cash flows so the comparison tests the ledger,
        # not the clock or a deposit/withdrawal.
        capital_flow = net_capital_flow(
            args.capital_flows_file,
            after=last.get("run_at_utc"),
            through=checked_at,
        )
        expected_equity, mismatches = _ledger_expected_equity(
            last,
            current_positions=positions,
            capital_flow=capital_flow,
        )
        detail = f"台账 {last['date']} equity={_num(last['equity']):.4f}"
        if abs(capital_flow) > 0.005:
            detail += f"；外部资金流 {capital_flow:+.4f}"
        if mismatches:
            detail += f"；{'；'.join(mismatches)}"
        consistent = (
            not mismatches
            and abs(expected_equity - equity) <= _ledger_equity_tolerance(equity)
        )
        check(
            "台账最新一行 = 当前账户（按实时标记价折算）",
            consistent,
            detail + f"；折算后应为 {expected_equity:.4f}，交易所 {equity:.4f}",
        )
        chain_errors = _pnl_chain_errors(journal)
        chain_ok = not chain_errors
        detail = "；".join(chain_errors) or f"{max(len(journal) - 1, 0)} 个相邻日全部一致"
        check("台账 PnL 链一致", chain_ok, detail)
        funding_errors = _funding_delta_errors(journal)
        check(
            "资金费按累计差记账",
            not funding_errors,
            "；".join(funding_errors) or "持仓未变化区间全部一致",
        )

    active_event_issues = _active_event_state_issues(
        state,
        signal_date=signal_date,
        journal=journal,
        expected_targets_sha256=(
            str(manifest_state.get("targets_sha256") or "")
            if manifest_state.get("targets_sha256")
            else None
        ),
    )
    check(
        "执行状态中的目标事件和止损触发记录完整",
        not active_event_issues,
        "; ".join(active_event_issues) or "active event 与 journal 一致",
    )

    # -- trades vs venue order history -----------------------------------
    now_ms = int(checked_at.timestamp() * 1000)
    history_start_ms = now_ms - int(args.history_days) * 86_400_000
    if not journal.empty:
        journal_start = pd.to_datetime(journal["date"].min(), utc=True, errors="coerce")
        if not pd.isna(journal_start):
            history_start_ms = max(history_start_ms, int(journal_start.timestamp() * 1000))
    history = client.order_history_all(
        start_time_ms=history_start_ms,
        end_time_ms=now_ms,
        limit=100,
    )
    by_id = {str(row.get("orderId")): row for row in history}
    missing: list[str] = []
    mismatched: list[str] = []
    if not journal.empty:
        for _, row in journal.iterrows():
            try:
                trades = _journal_trade_rows(row["trades"])
            except ValueError as exc:
                mismatched.append(f"{row['date']}: 台账 trades JSON 无效（{exc}）")
                continue
            for trade in trades:
                status = str(trade.get("status") or "filled").lower()
                if status != "filled":
                    continue
                order_id = str(trade.get("order_id"))
                venue = by_id.get(order_id)
                if venue is None:
                    # older than the queried window is fine; only flag recent days
                    if str(row["date"]) >= (checked_at - timedelta(days=args.history_days - 1)).strftime("%Y-%m-%d"):
                        missing.append(order_id)
                    continue
                mismatch = _trade_mismatch(trade, venue)
                if mismatch is not None:
                    mismatched.append(f"{order_id}: {mismatch}")
    check(
        "台账成交都能在交易所订单历史里对上",
        not missing and not mismatched,
        "; ".join(missing + mismatched) or f"核对 {len(by_id)} 笔订单",
    )
    unjournaled = _unjournaled_order_ids(
        history, journal, ignored_order_ids=drill_order_ids
    )
    check(
        "交易所已成交的 Atlas20 订单都已记账",
        not unjournaled,
        ", ".join(unjournaled) or "无漏记成交",
    )

    position_expected_stops = _position_short_stop_expectations(
        positions,
        specs_by_symbol={spec.symbol.upper(): spec for spec in specs.values()},
        short_stop_loss_pct=float(profile.frozen_config["short_stop_loss_pct"]),
    )
    stop_expectation_gaps = _short_stop_expectation_gaps(
        positions,
        expected_stops=position_expected_stops,
    )
    check(
        "当前空头止损可由交易所均价与价格步长独立重算",
        not stop_expectation_gaps,
        ", ".join(stop_expectation_gaps)
        or (
            f"{len(position_expected_stops)} 条空头全部可按 avgPrice × 1.20 重算"
            if position_expected_stops
            else "无空头仓"
        ),
    )
    stop_liquidation_issues = _short_stop_liquidation_issues(
        positions,
        expected_stops=position_expected_stops,
    )
    check(
        "空头止损价格早于逐仓强平价",
        not stop_liquidation_issues,
        ", ".join(stop_liquidation_issues)
        or (
            f"{len(position_expected_stops)} 条空头全部 stop < liquidationPrice"
            if position_expected_stops
            else "无空头仓"
        ),
    )
    expected_stops = protected_short_stops(journal)
    expected_stops.update(position_expected_stops)
    stop_gaps = _short_stop_gaps(journal, positions)
    check(
        "空头入场成交记录包含已确认止损",
        not stop_gaps,
        ", ".join(stop_gaps)
        or (
            f"{len(position_expected_stops)} 条空头入场记录均带已确认止损"
            if position_expected_stops
            else "无空头仓"
        ),
    )
    try:
        strategy_orders = client.unfilled_strategy_orders()
    except (BitgetAPIError, ValueError) as exc:
        check("交易所空头止损策略单可查询", False, f"查询失败：{exc}")
    else:
        venue_stop_gaps = _venue_short_stop_gaps(
            positions,
            strategy_orders,
            expected_stops=expected_stops,
        )
        check(
            "当前空头仓位都有交易所可见的止损保护",
            not venue_stop_gaps,
            ", ".join(venue_stop_gaps)
            or f"无缺口（当前未触发策略单 {len(strategy_orders)} 笔）",
        )
        duplicate_stop_orders = _short_stop_duplicate_issues(
            positions,
            strategy_orders,
        )
        check(
            "每个空头只有一张止损策略单",
            not duplicate_stop_orders,
            ", ".join(duplicate_stop_orders) or "每条空头最多一张",
        )
        orphan_strategy_orders = _orphan_strategy_order_issues(
            positions,
            strategy_orders,
        )
        check(
            "策略单都对应预期的当前空头止损",
            not orphan_strategy_orders,
            ", ".join(orphan_strategy_orders) or "无孤立策略单",
        )

    active_event = state.get("active_event")
    stopped_symbols = (
        active_event.get("stopped_symbols")
        if isinstance(active_event, dict)
        and isinstance(active_event.get("stopped_symbols"), dict)
        else {}
    )
    try:
        strategy_history = client.strategy_order_history(
            start_time_ms=history_start_ms,
            end_time_ms=now_ms,
            limit=100,
        )
    except (BitgetAPIError, ValueError) as exc:
        check(
            "交易所已触发策略止损可查询",
            False,
            f"查询失败：{exc}",
        )
    else:
        stop_history_issues = _strategy_stop_history_issues(
            stopped_symbols, strategy_history
        )
        recorded_strategy_ids = {
            str(record.get("strategy_order_id") or "")
            for record in stopped_symbols.values()
            if isinstance(record, dict)
        }
        applied_at = None
        if isinstance(active_event, dict) and active_event.get("applied_at"):
            try:
                applied_at = pd.Timestamp(active_event["applied_at"])
                if applied_at.tzinfo is None:
                    applied_at = applied_at.tz_localize("UTC")
                else:
                    applied_at = applied_at.tz_convert("UTC")
            except (TypeError, ValueError):
                applied_at = None
        unrecorded_strategy_ids: list[str] = []
        for row in strategy_history:
            if (
                str(row.get("status") or "").lower() != "success"
                or str(row.get("posSide") or "").lower() not in {"", "short", "net"}
                or str(row.get("side") or "").lower() != "buy"
            ):
                continue
            if applied_at is not None:
                try:
                    updated = pd.to_datetime(
                        int(row.get("updatedTime")),
                        unit="ms",
                        utc=True,
                        errors="raise",
                    )
                except (TypeError, ValueError, OverflowError):
                    unrecorded_strategy_ids.append(
                        str(row.get("orderId") or "<missing>") + ":invalid-time"
                    )
                    continue
                if updated < applied_at:
                    continue
            strategy_id = str(row.get("orderId") or "")
            if strategy_id and strategy_id not in recorded_strategy_ids:
                unrecorded_strategy_ids.append(strategy_id)
        check(
            "所有已触发空头止损均进入 journal",
            not stop_history_issues and not unrecorded_strategy_ids,
            ", ".join(stop_history_issues + unrecorded_strategy_ids)
            or f"已触发止损 {len(recorded_strategy_ids)} 笔全部对账",
        )

    # -- signal vs book --------------------------------------------------
    def asset_of(symbol: str) -> str:
        upper = symbol.upper()
        return known_symbols.get(upper, upper.replace("USDT", "").lower())

    notional_by_asset: dict[str, float] = {}
    for row in positions:
        asset = asset_of(str(row.get("symbol") or ""))
        notional_by_asset[asset] = notional_by_asset.get(asset, 0.0) + abs(
            _position_signed_notional(row)
        )
    event_target_quantities = (
        effective_event_target_quantities(active_event)
        if isinstance(active_event, dict)
        else {}
    )
    event_target_weights = (
        active_event.get("target_weights")
        if isinstance(active_event, dict)
        and isinstance(active_event.get("target_weights"), dict)
        else {}
    )
    event_prices = (
        active_event.get("prices")
        if isinstance(active_event, dict) and isinstance(active_event.get("prices"), dict)
        else {}
    )
    if isinstance(active_event, dict):
        quantity_issues = _event_quantity_issues(
            target_quantities=event_target_quantities,
            target_weights=event_target_weights,
            symbol_assets=known_symbols,
            positions=positions,
            specs_by_symbol={spec.symbol.upper(): spec for spec in specs.values()},
            event_prices=event_prices,
            stopped_symbols=stopped_symbols,
        )
    else:
        quantity_issues = ["execution state has no active target event"]
    check(
        "持仓数量与最近目标事件一致（价格漂移不算偏差）",
        not quantity_issues,
        "; ".join(quantity_issues) or "每个目标事件腿数量吻合，已止损腿除外",
    )

    orphans = sorted(set(notional_by_asset) - set(targets))
    orphan_notional = sum(notional_by_asset[asset] for asset in orphans)
    check(
        "无计划外持仓",
        orphan_notional <= 1.0,
        ", ".join(f"{asset.upper()} {notional_by_asset[asset]:.2f}" for asset in orphans) or "无",
    )

    check(
        f"冻结目标 gross <= {spec_max_gross:.2f}x（规格上限）",
        target_gross <= spec_max_gross + 1e-9,
        f"目标 gross {target_gross:.4f}x",
    )

    gross = sum(notional_by_asset.values())
    check(
        f"总名义 <= {spec_max_gross:.2f}x 权益（规格上限）",
        gross <= spec_max_gross * equity + 1.0,
        f"gross {gross:.2f} / equity {equity:.2f} = {gross / equity:.3f}x" if equity else "equity 0",
    )
    margin_utilization = isolated_margin / equity if equity > 0.0 else float("inf")
    check(
        f"组合保证金占用 <= {profile.max_margin_utilization:.0%}",
        margin_utilization <= profile.max_margin_utilization + 1e-9,
        f"isolated margin {isolated_margin:.2f} / equity {equity:.2f} = "
        f"{margin_utilization:.3f}x",
    )

    # The book is an *event* series: a row dated several days ago is normal.
    # What must be current is the data the book was built from, so the hard
    # checks are about the pipeline, not about the last event's age.
    event_age_days = (
        pd.Timestamp.now(tz="UTC").normalize() - pd.Timestamp(signal_date).normalize()
    ).days
    if args.manifest_file.exists():
        manifest = json.loads(args.manifest_file.read_text(encoding="utf-8"))
        staleness = manifest_staleness_hours(manifest, checked_at)
        index_end = str(manifest.get("index_end_date") or "")
        signal_end = str(manifest.get("signal_end_date") or "")
        check(
            "mark 数据新鲜（<= 30h）",
            staleness <= 30.0,
            f"最新 mark {manifest.get('last_mark')}（{staleness:.1f}h 前）",
        )
        check(
            "账本已评估到最新可判定日（无跳过）",
            bool(index_end) and index_end == signal_end,
            f"账本评估到 {index_end or '?'} / 数据到 {signal_end or '?'}",
        )
        manifest_issues = manifest_spec_issues(
            manifest,
            expected_spec=profile.spec,
            expected_frozen_config=profile.frozen_config,
            expected_top_level=profile.manifest_top_level,
        )
        if str(args.spec) != profile.spec:
            manifest_issues.append(
                f"audit --spec={args.spec!r}, expected {profile.spec!r}"
            )
        check(
            f"manifest 与当前 {profile.spec} 冻结规格一致",
            not manifest_issues,
            "; ".join(manifest_issues) or "规格、参数与成本口径一致",
        )
        targets_hash_issue = manifest_targets_hash_issue(
            manifest,
            args.targets_file,
        )
        targets_hash_recorded = bool(manifest.get("targets_sha256"))
        check(
            "目标账本与 manifest 内容哈希一致",
            targets_hash_issue is None and targets_hash_recorded,
            targets_hash_issue
            or (
                "targets_sha256 一致"
                if targets_hash_recorded
                else "manifest 缺少 targets_sha256；请重建冻结账本"
            ),
            hard=targets_hash_recorded,
        )
        required_short_assets = {
            asset for asset, weight in targets.items() if weight < 0.0
        }
        data_audit = audit_derivatives_data(
            args.raw_dir,
            args.panel,
            args.symbol_map,
            args.manifest_file,
            now=checked_at,
            required_short_assets=required_short_assets,
            required_leverage_assets=set(targets),
            required_leverage=profile.venue_leverage,
            require_all_funding_fresh=True,
        )
        check(
            "数据可靠性审计通过",
            data_audit.passed,
            "; ".join(data_audit.hard_failures[:5]) or f"{len(data_audit.warnings)} warning(s)",
        )
        check(
            "manifest data_fingerprint = 当前输入指纹",
            bool(manifest.get("data_fingerprint"))
            and manifest.get("data_fingerprint") == data_audit.provenance.get("fingerprint"),
            f"manifest={manifest.get('data_fingerprint')} current={data_audit.provenance.get('fingerprint')}",
        )
    else:
        check("样本外 manifest 存在", False, f"{args.manifest_file} 不存在")
    check(
        "信号事件距今（事件驱动，非每日变化）",
        True,
        f"最近一次仓位变化 {pd.Timestamp(signal_date).date()}（{event_age_days} 天前；无变化＝继续持有）",
        hard=False,
    )
    if last is not None:
        check(
            "台账信号日 = 冻结账本最新信号日",
            str(last["signal_date"]) == str(pd.Timestamp(signal_date).date()),
            f"台账 {last['signal_date']} vs 账本 {pd.Timestamp(signal_date).date()}",
        )

    # -- output ----------------------------------------------------------
    hard_failures = [row for row in checks if not row["ok"] and row["hard"]]
    print(f"Atlas20 实盘全链路核对 · {args.spec} · {checked_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"交易所: 权益 {equity:.4f} USDT · 仓位 {gross:.4f} · 持仓 {len(positions)} 腿 · 未实现 {unrealised:+.4f}")
    print("")
    for row in checks:
        mark = "✅" if row["ok"] else ("❌" if row["hard"] else "⚠️")
        print(f"  {mark} {row['check']} — {row['detail']}")
    print("")
    print(f"结论: {'全部通过' if not hard_failures else f'{len(hard_failures)} 项硬校验失败'}")

    ensure_dir(args.json_out.parent)
    atomic_write_text(
        args.json_out,
        json.dumps(
            {
                "spec": args.spec,
                "checked_at": checked_at.isoformat(),
                "equity": equity,
                "position_value": gross,
                "signal_date": str(pd.Timestamp(signal_date).date()),
                "checks": checks,
                "hard_failures": len(hard_failures),
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ),
    )
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
