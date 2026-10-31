"""Push the daily derivatives plan through a real Bitget account.

``atlas20.derivatives.execution`` answers *what* should change; this module
answers *how to get it done on a live venue* and *what actually happened*.
It is deliberately small and synchronous:

1. try to put the symbol on the intended margin mode / leverage,
2. place one market order per intent and poll the venue until it is filled,
3. try the isolated-margin top-ups,
4. hand back the venue's own numbers - filled quantity, average price, fee,
   and the position book read back after trading.

Everything the daily Telegram report shows comes from step 4, because the
owner wants *real* positions, not a recomputed model book.

Venue quirks this module absorbs (all observed live on 2026-10-10):

* ``25200 fixedMargin not support`` - the key/account cannot hold isolated
  futures.  The order is retried without ``marginMode`` (the venue default is
  crossed) and the report says so, loudly, instead of pretending.
* hedge accounts need ``posSide`` and reject ``posSide`` + ``reduceOnly``;
  one-way accounts are the mirror image.
* ``40731`` - the key is a copy-trading/elite key and refuses isolated-margin
  adjustments entirely; that becomes a report note, not a crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Callable, Protocol

from atlas20.derivatives.bitget import BitgetAPIError
from atlas20.derivatives.execution import ExecutionPlan

MARGIN_MODE_ISOLATED = "isolated"
MARGIN_MODE_CROSSED = "crossed"
_FILLED = "filled"
_CANCELLED = "cancelled"
_ISOLATED_UNSUPPORTED_MARKERS = ("fixedMargin", "40731", "not support copy trading")


class LiveTradingClient(Protocol):
    """The slice of :class:`~atlas20.derivatives.account.BitgetPrivateClient`
    the executor needs (a protocol so tests can inject a fake)."""

    def account_assets(self) -> dict[str, Any]: ...

    def current_positions(self, **kwargs: Any) -> list[dict[str, Any]]: ...

    def hold_mode(self) -> str: ...

    def set_leverage(self, symbol: str, leverage: float, **kwargs: Any) -> Any: ...

    def set_margin(self, symbol: str, amount: float, **kwargs: Any) -> Any: ...

    def place_order(self, **kwargs: Any) -> dict[str, Any]: ...

    def order_info(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class OrderFill:
    """One order as the venue reported it back."""

    asset: str
    symbol: str
    action: str
    side: str
    requested_size: float
    filled_size: float
    avg_price: float
    notional: float
    fee: float
    fee_coin: str
    order_id: str
    status: str

    @property
    def is_partial(self) -> bool:
        return self.status != _FILLED

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "symbol": self.symbol,
            "action": self.action,
            "side": self.side,
            "requested_size": self.requested_size,
            "filled_size": self.filled_size,
            "avg_price": self.avg_price,
            "notional": self.notional,
            "fee": self.fee,
            "fee_coin": self.fee_coin,
            "order_id": self.order_id,
            "status": self.status,
        }


@dataclass
class ExecutionReport:
    """What the venue did, plus the real book afterwards."""

    signal_date: str
    equity_before: float = 0.0
    equity_after: float = 0.0
    available_after: float = 0.0
    balance_after: float = 0.0
    fills: list[OrderFill] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)
    margin_notes: list[str] = field(default_factory=list)
    positions_after: list[dict[str, Any]] = field(default_factory=list)
    margin_mode: str = ""
    traded: bool = False

    @property
    def fee_total(self) -> float:
        return sum(fill.fee for fill in self.fills if fill.fee_coin.upper() == "USDT")

    @property
    def bought_notional(self) -> float:
        return sum(fill.notional for fill in self.fills if fill.side == "buy")

    @property
    def sold_notional(self) -> float:
        return sum(fill.notional for fill in self.fills if fill.side == "sell")

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_date": self.signal_date,
            "equity_before": self.equity_before,
            "equity_after": self.equity_after,
            "available_after": self.available_after,
            "balance_after": self.balance_after,
            "fills": [fill.as_dict() for fill in self.fills],
            "failures": list(self.failures),
            "margin_notes": list(self.margin_notes),
            "positions_after": list(self.positions_after),
            "margin_mode": self.margin_mode,
            "traded": self.traded,
        }


def _error_text(error: Exception) -> str:
    return str(error)


def is_isolated_unsupported(error: Exception) -> bool:
    """True when the venue says this key/account cannot hold isolated futures."""

    text = _error_text(error)
    return any(marker in text for marker in _ISOLATED_UNSUPPORTED_MARKERS)


def _fee_from_detail(payload: dict[str, Any]) -> tuple[float, str]:
    details = payload.get("feeDetail") or []
    if not isinstance(details, list):
        return 0.0, ""
    total = 0.0
    coin = ""
    for row in details:
        if not isinstance(row, dict):
            continue
        try:
            total += float(row.get("fee") or 0.0)
        except (TypeError, ValueError):
            continue
        coin = coin or str(row.get("feeCoin") or "")
    return total, coin


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def wait_for_fill(
    client: LiveTradingClient,
    *,
    order_id: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> dict[str, Any]:
    """Poll ``order-info`` until the order is filled (or time runs out)."""

    deadline = clock() + max(timeout_seconds, 0.0)
    last: dict[str, Any] = {}
    while True:
        try:
            last = client.order_info(order_id=order_id)
        except BitgetAPIError:
            last = last or {}
        status = str(last.get("orderStatus") or "")
        if status == _FILLED or status == _CANCELLED:
            return last
        if clock() >= deadline:
            return last
        sleep(poll_interval_seconds)


def execute_plan(
    client: LiveTradingClient,
    plan: ExecutionPlan,
    *,
    signal_date: str,
    pos_side: str = "long",
    leverage: float = 2.0,
    margin_mode: str = MARGIN_MODE_ISOLATED,
    hold_mode: str | None = None,
    fill_timeout_seconds: float = 20.0,
    poll_interval_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    client_oid_prefix: str = "atlas20",
) -> ExecutionReport:
    """Trade ``plan`` on the live account and report the real outcome.

    Orders are attempted in plan order (reductions first, as the planner emits
    them).  A rejected order is recorded and the remaining orders still run:
    the next daily plan re-reads the account, so a missed leg self-corrects.
    """

    report = ExecutionReport(signal_date=signal_date)
    assets = client.account_assets()
    report.equity_before = _to_float(assets.get("usdtEquity") or assets.get("accountEquity"))

    mode = hold_mode if hold_mode is not None else client.hold_mode()
    hedging = str(mode).lower() == "hedge_mode"

    isolated_ok = margin_mode == MARGIN_MODE_ISOLATED
    leverage_done: set[str] = set()
    stamp = int(time.time() * 1000)

    for index, order in enumerate(plan.orders):
        symbol = order.symbol
        if symbol not in leverage_done:
            leverage_done.add(symbol)
            # Cap leverage in the *crossed* config first: this venue happily
            # accepts an isolated leverage config and then still fills the
            # order crossed, so the fallback path must already be capped.
            try:
                client.set_leverage(
                    symbol,
                    leverage,
                    pos_side=pos_side,
                    margin_mode=MARGIN_MODE_CROSSED,
                    long_leverage=leverage,
                    short_leverage=leverage,
                )
            except BitgetAPIError as exc:
                report.margin_notes.append(f"{symbol}: 全仓杠杆设置失败（{exc}）")
            if isolated_ok:
                try:
                    client.set_leverage(
                        symbol,
                        leverage,
                        pos_side=pos_side,
                        margin_mode=MARGIN_MODE_ISOLATED,
                        long_leverage=leverage,
                        short_leverage=leverage,
                    )
                except BitgetAPIError as exc:
                    isolated_ok = False
                    report.margin_notes.append(
                        f"{symbol}: 逐仓杠杆设置被拒绝（{exc}）→ 按全仓执行"
                    )

        body: dict[str, Any] = {
            "symbol": symbol,
            "qty": order.size,
            "side": order.side,
            "order_type": "market",
            "pos_side": pos_side if hedging else None,
            "reduce_only": order.reduce_only and not hedging,
            "client_oid": f"{client_oid_prefix}{stamp}{index}",
        }
        if isolated_ok and not order.reduce_only:
            body["margin_mode"] = MARGIN_MODE_ISOLATED

        try:
            try:
                placed = client.place_order(**body)
            except BitgetAPIError as exc:
                if "margin_mode" in body and is_isolated_unsupported(exc):
                    isolated_ok = False
                    report.margin_notes.append(
                        "逐仓不可用（venue 拒绝 25200 fixedMargin）→ 已按全仓执行"
                    )
                    body.pop("margin_mode", None)
                    # fresh clientOid: the rejected attempt never reached the
                    # matching engine, but a reused id would be refused
                    body["client_oid"] = f"{client_oid_prefix}{stamp}{index}c"
                    placed = client.place_order(**body)
                else:
                    raise
        except (BitgetAPIError, ValueError) as exc:
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": _error_text(exc),
                }
            )
            if is_isolated_unsupported(exc):
                report.margin_notes.append(f"{symbol}: {exc}")
            continue

        order_id = str(placed.get("orderId") or "")
        payload = (
            wait_for_fill(
                client,
                order_id=order_id,
                timeout_seconds=fill_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
                clock=clock,
            )
            if order_id
            else {}
        )
        filled = _to_float(payload.get("cumExecQty"))
        avg_price = _to_float(payload.get("avgPrice"))
        notional = _to_float(payload.get("cumExecValue")) or filled * avg_price
        fee, fee_coin = _fee_from_detail(payload)
        status = str(payload.get("orderStatus") or ("filled" if not order_id else ""))
        report.fills.append(
            OrderFill(
                asset=order.asset,
                symbol=symbol,
                action=order.action,
                side=order.side,
                requested_size=order.size,
                filled_size=filled,
                avg_price=avg_price,
                notional=notional,
                fee=fee,
                fee_coin=fee_coin,
                order_id=order_id,
                status=status or "unknown",
            )
        )
        report.traded = True
        if status == _CANCELLED:
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": "order cancelled by the venue",
                }
            )

    positions = client.current_positions()
    report.positions_after = [dict(row) for row in positions]
    for row in report.positions_after:
        row_mode = str(row.get("marginMode") or "")
        if row_mode:
            report.margin_mode = row_mode
            break

    # Isolated-margin top-ups only exist for isolated legs.  On a crossed
    # account the venue answers 40731/25200 every single day, which is noise
    # rather than information - so say it once, plainly, and skip the calls.
    if plan.margin_intents:
        if report.margin_mode and report.margin_mode != MARGIN_MODE_ISOLATED:
            report.margin_notes.append(
                f"持仓为{report.margin_mode}：跳过 {len(plan.margin_intents)} 笔逐仓保证金调整"
            )
        else:
            for intent in plan.margin_intents:
                try:
                    client.set_margin(
                        intent.symbol,
                        intent.amount,
                        pos_side=intent.pos_side,
                        operation=intent.operation,
                    )
                except BitgetAPIError as exc:
                    report.margin_notes.append(
                        f"{intent.symbol}: 保证金{intent.operation}"
                        f" {intent.amount:.2f} USDT 失败（{exc}）"
                    )
                except ValueError as exc:
                    report.margin_notes.append(
                        f"{intent.symbol}: 保证金调整参数错误（{exc}）"
                    )

    assets_after = client.account_assets()
    report.equity_after = _to_float(
        assets_after.get("usdtEquity") or assets_after.get("accountEquity")
    )
    usdt_row = next(
        (
            row
            for row in assets_after.get("assets") or []
            if isinstance(row, dict) and str(row.get("coin", "")).upper() == "USDT"
        ),
        {},
    )
    report.available_after = _to_float(usdt_row.get("available"))
    report.balance_after = _to_float(usdt_row.get("balance"))
    return report


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _qty(value: float) -> str:
    return f"{value:.8g}"


def format_execution_report(
    report: ExecutionReport,
    *,
    signal_date: str,
    spec: str,
    execution_hint: str = "",
    targets: dict[str, float] | None = None,
    lot_notional: dict[str, float] | None = None,
    planned_orders: list[Any] | None = None,
    warnings: list[str] | None = None,
    prev_equity: float | None = None,
    prev_day_pnl: float | None = None,
    run_at: datetime | None = None,
    event_age_days: int | None = None,
) -> str:
    """Render the daily Telegram message: short, and all venue numbers.

    Total equity, position value, today's PnL (against the previous ledger
    row), yesterday's PnL, what was traded, what is held.  Anything that went
    wrong is appended; nothing else.
    """

    moment = run_at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    beijing = moment.astimezone(timezone(timedelta(hours=8)))

    positions = [
        row for row in report.positions_after if abs(_to_float(row.get("total"))) > 0.0
    ]
    # Reconcile by the stamped coin-id asset, never by rebuilding a symbol from
    # that id: CMC's ``tron`` trades as ``TRXUSDT``, not ``TRONUSDT``.
    notional_by_asset: dict[str, float] = {}
    ticker_by_asset: dict[str, str] = {}
    position_notionals: list[tuple[dict[str, Any], str, float]] = []
    for row in positions:
        symbol = str(row.get("symbol") or "")
        asset = str(row.get("asset") or symbol.upper().removesuffix("USDT")).lower()
        notional = abs(_to_float(row.get("total"))) * _to_float(
            row.get("markPrice") or row.get("avgPrice")
        )
        notional_by_asset[asset] = notional_by_asset.get(asset, 0.0) + notional
        ticker_by_asset[asset] = symbol.upper().removesuffix("USDT") or asset.upper()
        position_notionals.append((row, asset, notional))
    total_notional = sum(notional_by_asset.values())
    equity = report.equity_after or report.equity_before
    day_pnl = None if prev_equity is None else equity - float(prev_equity)

    lines = [f"Atlas20 自动调仓 · {beijing.strftime('%Y-%m-%d %H:%M')} 北京", ""]
    lines.append(f"总权益 {_money(equity)} USDT")
    share = f"（{total_notional / equity:.1%} 权益）" if equity > 0 else ""
    lines.append(f"仓位价值 {_money(total_notional)} USDT{share}")
    if day_pnl is None or not prev_equity:
        lines.append("今日盈亏 —（首个记录日）")
    else:
        lines.append(f"今日盈亏 {day_pnl:+.2f} USDT（{day_pnl / float(prev_equity):+.2%}）")
    if prev_day_pnl is None:
        lines.append("昨日盈亏 —")
    else:
        lines.append(f"昨日盈亏 {float(prev_day_pnl):+.2f} USDT")

    lines += ["", "今日成交:"]
    if not report.fills:
        lines.append("  无")
    for fill in report.fills:
        verb = "买入" if fill.side == "buy" else "卖出"
        note = "" if fill.status == _FILLED else f"（{fill.status}）"
        lines.append(
            f"  {verb} {fill.asset.upper()} {_qty(fill.filled_size)} 枚 @ {fill.avg_price:.8g}"
            f" · {_money(fill.notional)} USDT · 费 {fill.fee:.4f}{note}"
        )
    for order in planned_orders or []:
        verb = {
            "OPEN": "开仓",
            "INCREASE": "加仓",
            "REDUCE": "减仓",
            "CLOSE": "平仓",
        }.get(str(order.action), str(order.action))
        lines.append(
            f"  [未执行] {verb} {str(order.asset).upper()} {order.side} {order.size:.8g} 枚"
            f" · {_money(order.notional)} USDT"
        )

    lines += ["", "当前持仓:"]
    if not positions:
        lines.append("  空仓")
    for row, asset, notional in position_notionals:
        symbol = str(row.get("symbol") or "")
        size = abs(_to_float(row.get("total")))
        entry = _to_float(row.get("avgPrice"))
        mark = _to_float(row.get("markPrice") or row.get("avgPrice"))
        upnl = _to_float(row.get("unrealisedPnl"))
        if not upnl:
            upnl = (mark - entry) * size
        weight = notional / equity if equity > 0 else 0.0
        lines.append(
            f"  {asset.upper()} {_qty(size)} 枚 · "
            f"{_money(notional)} USDT · {weight:.1%} · 浮盈 {upnl:+.2f}"
        )

    if targets:
        checks = []
        for asset in sorted(targets):
            target_weight = float(targets.get(asset, 0.0))
            target_notional = target_weight * equity
            actual = notional_by_asset.get(asset.lower(), 0.0)
            gap = actual - target_notional
            lot = float((lot_notional or {}).get(asset, 0.0))
            tolerance = max(1.0, 0.01 * target_notional, 1.5 * lot)
            flag = "" if abs(gap) <= tolerance else " ⚠️"
            checks.append(
                f"{asset.upper()} 目标 {_money(target_notional)} / 实际 {_money(actual)}{flag}"
            )
        orphans = sorted(set(notional_by_asset) - {asset.lower() for asset in targets})
        if orphans:
            orphan_labels = [ticker_by_asset.get(asset, asset.upper()) for asset in orphans]
            checks.append(f"⚠️ 计划外持仓: {', '.join(orphan_labels)}")
        age = (
            ""
            if event_age_days is None
            else ("（今天的变化）" if event_age_days <= 0 else f"（{event_age_days} 天前的最近变化）")
        )
        lines += ["", f"信号 {signal_date}{age} · " + " · ".join(checks)]

    if report.failures:
        lines += ["", "⚠️ 未完成:"]
        for failure in report.failures:
            lines.append(
                f"  {failure['symbol']} {failure['action']} {failure['side']}"
                f" {failure['size']}: {failure['error'][:100]}"
            )
    if warnings:
        lines += ["", "提示:"]
        lines += [f"  - {warning}" for warning in warnings]
    return "\n".join(lines)
