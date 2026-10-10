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
    equity_reference: float | None = None,
    lot_notional: dict[str, float] | None = None,
    planned_orders: list[Any] | None = None,
    warnings: list[str] | None = None,
) -> str:
    """Render the daily message.  Every number is a venue number."""

    positions = [
        row
        for row in report.positions_after
        if abs(_to_float(row.get("total"))) > 0.0
    ]
    notional_by_symbol: dict[str, float] = {}
    lines = [
        f"Atlas20 自动调仓报告 · {spec}",
        f"信号日 {signal_date}（UTC）" + (f" · 执行点 {execution_hint}" if execution_hint else ""),
    ]
    for row in positions:
        symbol = str(row.get("symbol") or "")
        notional_by_symbol[symbol] = abs(_to_float(row.get("total"))) * _to_float(
            row.get("markPrice") or row.get("avgPrice")
        )

    lines += [
        "",
        f"账户权益 {_money(report.equity_after)} USDT"
        f"（执行前 {_money(report.equity_before)}，"
        f"权益变动 {report.equity_after - report.equity_before:+.2f}）",
        f"可用保证金 {_money(report.available_after)} USDT",
        "",
        "今日成交:",
    ]
    if not report.fills:
        lines.append("  无（已与目标一致或无信号变化）")
    for fill in report.fills:
        verb = "买入" if fill.side == "buy" else "卖出"
        note = "" if fill.status == _FILLED else f"（{fill.status}）"
        lines.append(
            f"  {verb} {fill.asset.upper()} {_qty(fill.filled_size)} 枚"
            f" @ 均价 {fill.avg_price:.8g} → {_money(fill.notional)} USDT"
            f" · 手续费 {fill.fee:.4f} {fill.fee_coin or 'USDT'}{note}"
        )
    if report.fee_total:
        lines.append(f"  手续费合计 {report.fee_total:.4f} USDT")
    if planned_orders:
        lines.append("  [未执行] 今日计划:")
        for order in planned_orders:
            verb = {
                "OPEN": "开仓",
                "INCREASE": "加仓",
                "REDUCE": "减仓",
                "CLOSE": "平仓",
            }.get(str(order.action), str(order.action))
            lines.append(
                f"    {verb} {str(order.asset).upper()} {order.side} {order.size:.8g} 枚"
                f"（名义 {_money(order.notional)} USDT）"
            )

    lines += ["", "当前真实持仓:"]
    if not positions:
        lines.append("  空仓（现金 100%）")
    total_notional = sum(notional_by_symbol.values())
    equity = report.equity_after if report.equity_after > 0 else (equity_reference or 0.0)
    for row in positions:
        symbol = str(row.get("symbol") or "")
        size = abs(_to_float(row.get("total")))
        entry = _to_float(row.get("avgPrice"))
        mark = _to_float(row.get("markPrice") or row.get("avgPrice"))
        share = (notional_by_symbol[symbol] / equity) if equity > 0 else 0.0
        pnl = (mark - entry) * size
        side = str(row.get("posSide") or "long")
        lines.append(
            f"  {symbol}（{side}）{_qty(size)} 枚 · 名义 {_money(notional_by_symbol[symbol])} USDT"
            f" · 占权益 {share:.2%} · 浮盈 {pnl:+.2f}"
        )
    if equity > 0:
        lines.append(f"  合约名义合计 {_money(total_notional)} USDT（{total_notional / equity:.2%} 权益）")
        if positions:
            lines.append(
                f"  可用保证金 {_money(report.available_after)} USDT（交易所口径）"
            )
        else:
            lines.append(
                f"  现金/可用 {_money(report.available_after)} USDT"
                f"（{report.available_after / equity:.2%} 权益）"
            )

    if targets:
        lines += ["", "目标 vs 实际（名义 USDT）:"]
        for asset in sorted(set(targets) | {str(r.get("symbol", "")).rstrip("USDT").lower() for r in positions}):
            target_weight = float(targets.get(asset, 0.0))
            target_notional = target_weight * equity if equity > 0 else 0.0
            symbol = f"{asset.upper()}USDT"
            actual = notional_by_symbol.get(symbol, 0.0)
            gap = actual - target_notional
            lot = float((lot_notional or {}).get(asset, 0.0))
            tolerance = max(1.0, 0.01 * target_notional, 1.5 * lot)
            flag = "✓" if abs(gap) <= tolerance else "⚠️"
            if abs(gap) <= tolerance and abs(gap) > max(1.0, 0.01 * target_notional):
                flag = "✓（受合约最小下单量/步长限制）"
            lines.append(
                f"  {asset.upper()}: 目标 {_money(target_notional)} / 实际 {_money(actual)}"
                f"（差 {gap:+.2f}）{flag}"
            )

    mode_label = {
        "isolated": "逐仓（isolated）",
        "crossed": "全仓（crossed）",
    }.get(report.margin_mode, report.margin_mode or "未知")
    lines += ["", f"保证金模式: {mode_label}"]
    if report.margin_mode and report.margin_mode != "isolated":
        lines.append("  ⚠️ 规格要求逐仓；本账户/key 当前只能全仓，逐腿 -51% 强平线不适用。")

    if report.failures:
        lines += ["", "未完成:"]
        for failure in report.failures:
            lines.append(
                f"  ⚠️ {failure['symbol']} {failure['action']} {failure['side']}"
                f" {failure['size']}: {failure['error'][:120]}"
            )
    if report.margin_notes:
        lines += ["", "保证金备注:"]
        lines += [f"  - {note[:160]}" for note in report.margin_notes]
    if warnings:
        lines += ["", "提示:"]
        lines += [f"  - {warning}" for warning in warnings]
    lines += ["", "本消息由自动执行器发出；成交与持仓均为交易所回读值。"]
    return "\n".join(lines)
