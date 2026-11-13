"""Cross-check the live derivatives track against the venue, end to end.

Answers one question: *can every number in the daily report be reproduced
from an independent source?*  It re-reads the exchange, the frozen target
book and the local ledger, then checks

1. the account identity ``usdtEquity == USDT-equivalent collateral + unrealisedPnl``,
2. ``positionValue == Σ |size| × markPrice`` across open legs,
3. every trade in the ledger exists in the venue's order history with the
   same quantity, average price and fee,
4. the current book matches the frozen target book (within one contract lot),
5. the ledger's PnL chain adds up after excluding external capital flows,
6. nothing is held that the frozen book does not ask for,
7. the gross notional respects the 1.25x spec cap.

Exit code 0 when every hard check passes, 1 otherwise.  Read-only: it never
places or cancels an order.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from math import isfinite
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
from atlas20.derivatives.live_chain import manifest_staleness_hours  # noqa: E402
from atlas20.derivatives.live_executor import short_stop_symbol_issue  # noqa: E402
from atlas20.derivatives.live_journal import (  # noqa: E402
    DEFAULT_CAPITAL_FLOWS_FILE,
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
    fetch_public_prices,
    load_symbol_map,
    spec_symbol_universe,
    specs_from_instruments,
    symbol_to_asset_index,
    target_gross_weight,
)
from scripts.send_derivatives_signal import load_latest_targets  # noqa: E402

DEFAULT_JOURNAL_FILE = Path("reports/ls45_live_g125_live/journal.csv")
DEFAULT_MANIFEST_FILE = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_JSON_OUT = Path("reports/ls45_live_g125_live/audit.json")
DEFAULT_DRILL_REGISTRY = Path("reports/ls45_live_g125_live/venue_drill_order_registry.json")
DEFAULT_STATE_FILE = Path("data/ls45_g125_execution_state.json")
SPEC_MAX_GROSS = 1.25
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


def _position_risk_issues(positions: list[dict]) -> list[str]:
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
        elif abs(leverage - SPEC_VENUE_LEVERAGE) > 1e-9:
            issues.append(
                f"{symbol}: leverage={leverage:g}，要求 {SPEC_VENUE_LEVERAGE:g}x"
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
            if ratio + 1e-9 < SPEC_MIN_MARGIN_RATIO:
                issues.append(
                    f"{symbol}: margin buffer {ratio:.3%} < {SPEC_MIN_MARGIN_RATIO:.0%}"
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
    usdt_row = next(
        (
            row
            for row in assets.get("assets") or []
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
        mark_value = row.get("markPrice", row.get("avgPrice"))
        issue = _finite_number_issue(mark_value, f"{symbol} markPrice")
        if issue:
            issues.append(issue)
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
    if recorded_stop is not None:
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

    ledger_positions = json.loads(last.get("positions") or "[]")
    ledger_by_symbol = {str(item.get("symbol")): item for item in ledger_positions}
    expected_equity = _num(last.get("equity")) + float(capital_flow)
    mismatches: list[str] = []
    for row in current_positions:
        symbol = str(row.get("symbol") or "")
        ledger_row = ledger_by_symbol.pop(symbol, None)
        if ledger_row is None:
            mismatches.append(f"{symbol} 不在台账里")
            continue
        ledger_side = str(ledger_row.get("side") or "").lower()
        current_side = "short" if _position_signed_qty(row) < 0.0 else "long"
        if ledger_side in {"long", "short"} and ledger_side != current_side:
            mismatches.append(
                f"{symbol} 方向变了：台账 {ledger_side} vs 当前 {current_side}"
            )
        expected_equity += _position_signed_qty(row) * (
            _num(row.get("markPrice")) - _num(ledger_row.get("mark_price"))
        )
    if ledger_by_symbol:
        mismatches.append(f"台账多了 {', '.join(sorted(ledger_by_symbol))}")
    return expected_equity, mismatches


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
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--drill-registry", type=Path, default=DEFAULT_DRILL_REGISTRY)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    args = parser.parse_args(argv)
    checked_at = datetime.now(timezone.utc)

    client = BitgetPrivateClient(BitgetCredentials.from_env())
    assets = client.account_assets()
    positions = client.current_positions()
    symbol_map = load_symbol_map(args.symbol_map)
    signal_date, execution_hint, book = load_latest_targets(args.targets_file)
    targets = {
        str(record["asset"]): float(record["target_weight"])
        for record in book.to_dict("records")
        if abs(float(record["target_weight"])) > 0.0
    }
    target_gross = target_gross_weight(targets)
    relevant = spec_symbol_universe(symbol_map, targets)
    session = requests.Session()
    prices = fetch_public_prices(session)
    specs = specs_from_instruments(fetch_public_instruments(session), relevant)

    usdt_row = next(
        (
            row
            for row in assets.get("assets") or []
            if isinstance(row, dict) and str(row.get("coin", "")).upper() == "USDT"
        ),
        {},
    )
    equity = _num(assets.get("usdtEquity"))
    balance = _usdt_equivalent_balance(assets)
    unrealised = _num(assets.get("usdtUnrealisedPnl"))
    reported_position_value = _num(assets.get("positionValue"))
    mark_notional = sum(
        abs(_num(row.get("total"))) * _num(row.get("markPrice") or row.get("avgPrice"))
        for row in positions
    )

    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str, *, hard: bool = True) -> None:
        checks.append({"check": name, "ok": bool(ok), "hard": hard, "detail": detail})

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
        "账户恒等式 equity = USDT 等值抵押品 + uPnL",
        abs(equity - (balance + unrealised)) <= 0.02,
        f"{equity:.4f} vs {balance:.4f} + {unrealised:.4f} = {balance + unrealised:.4f}",
    )
    # ``assets`` and ``current-position`` are two round trips, so their marks
    # can differ by a few bps on a moving book; the tolerance says so.
    check(
        "仓位市值 = Σ 数量 × 标记价",
        abs(reported_position_value - mark_notional) <= max(0.05, 0.003 * mark_notional),
        f"交易所 {reported_position_value:.4f} vs 重算 {mark_notional:.4f}"
        f"（两次请求的标记价差 {abs(reported_position_value - mark_notional):.4f}）",
    )

    known_symbols = symbol_to_asset_index(symbol_map)
    unknown_symbols = _unknown_position_symbols(positions, symbol_map)
    check(
        "所有持仓合约都在冻结映射中",
        not unknown_symbols,
        ", ".join(unknown_symbols) or "全部有唯一映射",
    )
    risk_issues = _position_risk_issues(positions)
    check(
        "每腿逐仓、2x 杠杆与保证金缓冲符合规格",
        not risk_issues,
        "；".join(risk_issues) or "无持仓，或全部符合",
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
        consistent = not mismatches and abs(expected_equity - equity) <= 0.05
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
            for trade in json.loads(row["trades"] or "[]"):
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

    expected_stops = protected_short_stops(journal)
    stop_gaps = _short_stop_gaps(journal, positions)
    check(
        "空头入场成交记录包含已确认止损",
        not stop_gaps,
        ", ".join(stop_gaps) or "无空头仓，或入场记录带止损",
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
        orphan_strategy_orders = _orphan_strategy_order_issues(
            positions,
            strategy_orders,
        )
        check(
            "策略单都对应预期的当前空头止损",
            not orphan_strategy_orders,
            ", ".join(orphan_strategy_orders) or "无孤立策略单",
        )

    # -- signal vs book --------------------------------------------------
    def asset_of(symbol: str) -> str:
        upper = symbol.upper()
        return known_symbols.get(upper, upper.replace("USDT", "").lower())

    notional_by_asset: dict[str, float] = {}
    signed_notional_by_asset: dict[str, float] = {}
    for row in positions:
        asset = asset_of(str(row.get("symbol") or ""))
        signed = _position_signed_notional(row)
        notional_by_asset[asset] = notional_by_asset.get(asset, 0.0) + abs(signed)
        signed_notional_by_asset[asset] = signed_notional_by_asset.get(asset, 0.0) + signed
    lot_by_asset = {
        asset: float(spec.min_order_qty or spec.quantity_multiplier)
        * _num(prices.get(relevant[asset].upper()))
        for asset, spec in specs.items()
    }
    off_target: list[str] = []
    for asset, weight in targets.items():
        want = weight * equity
        got = signed_notional_by_asset.get(asset, 0.0)
        tolerance = max(1.0, 0.01 * abs(want), 1.5 * float(lot_by_asset.get(asset, 0.0)))
        if abs(got - want) > tolerance:
            off_target.append(f"{asset.upper()} 目标 {want:.2f} vs 实际 {got:.2f}")
    check("持仓与冻结目标一致（1 个合约步长内）", not off_target, "; ".join(off_target) or "全部吻合")

    orphans = sorted(set(notional_by_asset) - set(targets))
    orphan_notional = sum(notional_by_asset[asset] for asset in orphans)
    check(
        "无计划外持仓",
        orphan_notional <= 1.0,
        ", ".join(f"{asset.upper()} {notional_by_asset[asset]:.2f}" for asset in orphans) or "无",
    )

    check(
        f"冻结目标 gross <= {SPEC_MAX_GROSS:.2f}x（规格上限）",
        target_gross <= SPEC_MAX_GROSS + 1e-9,
        f"目标 gross {target_gross:.4f}x",
    )

    gross = sum(notional_by_asset.values())
    check(
        f"总名义 <= {SPEC_MAX_GROSS:.2f}x 权益（规格上限）",
        gross <= SPEC_MAX_GROSS * equity + 1.0,
        f"gross {gross:.2f} / equity {equity:.2f} = {gross / equity:.3f}x" if equity else "equity 0",
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
