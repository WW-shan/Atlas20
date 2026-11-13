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
import hashlib
from math import isfinite
import time
from typing import Any, Callable, Protocol

from atlas20.derivatives.account import UTA_CATEGORY
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

    def account_settings(self) -> dict[str, Any]: ...

    def set_leverage(self, symbol: str, leverage: float, **kwargs: Any) -> Any: ...

    def set_margin(self, symbol: str, amount: float, **kwargs: Any) -> Any: ...

    def place_order(self, **kwargs: Any) -> dict[str, Any]: ...

    def order_info(self, **kwargs: Any) -> dict[str, Any]: ...

    def unfilled_orders(self, **kwargs: Any) -> list[dict[str, Any]]: ...

    def cancel_order(self, **kwargs: Any) -> dict[str, Any]: ...

    def unfilled_strategy_orders(self, **kwargs: Any) -> list[dict[str, Any]]: ...

    def order_history(self, **kwargs: Any) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class OrderFill:
    """One order as the venue reported it back."""

    asset: str
    symbol: str
    action: str
    side: str
    stop_loss: float | None
    requested_size: float
    filled_size: float
    avg_price: float
    notional: float
    fee: float
    fee_coin: str
    order_id: str
    status: str
    position_side: str = ""
    client_oid: str = ""
    requested_stop_loss: float | None = None
    stop_trigger_by: str = ""
    stop_order_type: str = ""

    @property
    def is_partial(self) -> bool:
        return self.status != _FILLED

    @property
    def short_stop_confirmed(self) -> bool:
        """Whether this fill is a short entry with the required venue stop."""

        if (
            self.position_side != "short"
            or self.stop_loss is None
            or self.requested_stop_loss is None
        ):
            return False
        tolerance = max(1e-9, abs(float(self.requested_stop_loss)) * 1e-8)
        return (
            self.stop_loss > 0.0
            and abs(self.stop_loss - self.requested_stop_loss) <= tolerance
            and self.stop_trigger_by.lower() == "mark_price"
            and self.stop_order_type.lower() == "market"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "symbol": self.symbol,
            "action": self.action,
            "side": self.side,
            "stop_loss": self.stop_loss,
            "requested_size": self.requested_size,
            "filled_size": self.filled_size,
            "avg_price": self.avg_price,
            "notional": self.notional,
            "fee": self.fee,
            "fee_coin": self.fee_coin,
            "order_id": self.order_id,
            "status": self.status,
            "position_side": self.position_side,
            "client_oid": self.client_oid,
            "requested_stop_loss": self.requested_stop_loss,
            "stop_trigger_by": self.stop_trigger_by,
            "stop_order_type": self.stop_order_type,
        }


@dataclass
class ExecutionReport:
    """What the venue did, plus the real book afterwards."""

    signal_date: str
    equity_before: float = 0.0
    equity_after: float | None = None
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
    def position_value(self) -> float:
        return sum(
            abs(_to_float(row.get("total")))
            * _to_float(row.get("markPrice") or row.get("avgPrice"))
            for row in self.positions_after
        )

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
            "position_value": self.position_value,
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


def _required_float(value: Any, field: str, *, positive: bool = False) -> float:
    """Parse one required exchange field; invalid data must stop trading."""

    if value is None or value == "":
        raise ValueError(f"{field} is missing")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} is not numeric: {value!r}") from exc
    if not isfinite(number):
        raise ValueError(f"{field} is not finite: {value!r}")
    if positive and number <= 0.0:
        raise ValueError(f"{field} must be positive, got {number!r}")
    return number


def _account_equity(assets: dict[str, Any]) -> float:
    """Read equity with explicit precedence; zero must not fall through."""

    if assets.get("usdtEquity") is not None:
        return _required_float(assets.get("usdtEquity"), "account usdtEquity", positive=True)
    if assets.get("accountEquity") is not None:
        return _required_float(assets.get("accountEquity"), "account accountEquity", positive=True)
    raise ValueError("account assets contain neither usdtEquity nor accountEquity")


def _signed_position_qty(row: dict[str, Any]) -> float:
    """Signed quantity from hedge and one-way position payloads."""

    total = _required_float(
        row.get("total"),
        f"{str(row.get('symbol') or '<unknown>')} position total",
    )
    if abs(total) <= 1e-12:
        return 0.0
    pos_side = str(row.get("posSide") or "").strip().lower()
    if pos_side not in {"", "long", "short", "net"}:
        raise ValueError(
            f"{str(row.get('symbol') or '<unknown>')} posSide is invalid: {pos_side!r}"
        )
    short = pos_side == "short" or (pos_side in {"", "net"} and total < 0.0)
    return -abs(total) if short else abs(total)


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


def _lookup_order_by_client_oid(
    client: LiveTradingClient,
    client_oid: str,
) -> dict[str, Any]:
    """Best-effort recovery after an ambiguous placement response."""

    if not client_oid:
        return {}
    try:
        payload = client.order_info(client_oid=client_oid)
    except (BitgetAPIError, ValueError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _recovered_order_matches(
    payload: dict[str, Any],
    *,
    symbol: str,
    side: str,
    pos_side: str,
) -> bool:
    if not payload:
        return False
    payload_symbol = str(payload.get("symbol") or "").upper()
    payload_side = str(payload.get("side") or "").lower()
    payload_pos_side = str(payload.get("posSide") or "").lower()
    if payload_symbol and payload_symbol != symbol.upper():
        return False
    if payload_side and payload_side != side.lower():
        return False
    if payload_pos_side and payload_pos_side not in {pos_side.lower(), "net"}:
        return False
    return True


def _invalid_margin_modes(positions: list[dict[str, Any]]) -> list[str]:
    modes = {
        str(row.get("marginMode") or "").strip().lower() or "<missing>"
        for row in positions
        if abs(_signed_position_qty(row)) > 1e-12
    }
    return sorted(mode for mode in modes if mode != MARGIN_MODE_ISOLATED)


def _is_terminal_order_status(status: str) -> bool:
    return status.lower() in {_FILLED, _CANCELLED, "canceled"}


def _client_oid(
    prefix: str,
    *,
    purpose: str,
    symbol: str,
    action: str,
    side: str,
    pos_side: str,
    reduce_only: bool,
) -> str:
    """Stable, compact idempotency key for one logical order."""

    tag = {
        "order": "o",
        "fallback": "f",
        "stop-close": "r",
        "gap-close": "u",
    }[purpose]
    identity = "|".join(
        (
            purpose,
            symbol.upper(),
            action.upper(),
            side.lower(),
            pos_side.lower(),
            "reduce" if reduce_only else "open",
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{tag}{digest}"


def _history_fill_action(row: dict[str, Any], positions: list[dict[str, Any]]) -> str:
    side = str(row.get("side") or "").lower()
    pos_side = str(row.get("posSide") or "").lower()
    if pos_side == "long":
        return "OPEN" if side == "buy" else "REDUCE"
    if pos_side == "short":
        return "OPEN" if side == "sell" else "REDUCE"
    reduce_only = str(row.get("reduceOnly") or "").upper() in {"YES", "TRUE", "1"}
    if reduce_only:
        return "REDUCE"
    symbol = str(row.get("symbol") or "").upper()
    current = next(
        (
            item
            for item in positions
            if str(item.get("symbol") or "").upper() == symbol
            and abs(_signed_position_qty(item)) > 1e-12
        ),
        None,
    )
    if current is not None:
        current_short = _signed_position_qty(current) < 0.0
        if side == "buy":
            return "REDUCE" if current_short else "OPEN"
        if side == "sell":
            return "OPEN" if current_short else "REDUCE"
    return "OPEN" if side in {"buy", "sell"} else "UNKNOWN"


def _recover_fills_from_order_history(
    client: LiveTradingClient,
    *,
    client_oid_prefix: str,
    report: ExecutionReport,
    positions: list[dict[str, Any]],
) -> None:
    """Recover fills that landed before a crash or lost response reached the CSV."""

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=2)
    try:
        rows = client.order_history(
            start_time_ms=int(start.timestamp() * 1000),
            end_time_ms=int(end.timestamp() * 1000),
            limit=100,
        )
    except (BitgetAPIError, ValueError) as exc:
        report.failures.append(
            {
                "symbol": "*",
                "action": "VERIFY",
                "side": "-",
                "size": "-",
                "error": f"could not recover current-run fills from order history: {_error_text(exc)}",
            }
        )
        return

    known_order_ids = {fill.order_id for fill in report.fills if fill.order_id}
    for row in rows:
        client_oid = str(row.get("clientOid") or "")
        if not client_oid.startswith(client_oid_prefix):
            continue
        order_id = str(row.get("orderId") or "")
        if not order_id or order_id in known_order_ids:
            continue
        try:
            filled = _required_float(row.get("cumExecQty"), "recovered cumExecQty")
        except ValueError as exc:
            report.failures.append(
                {
                    "symbol": str(row.get("symbol") or "*"),
                    "action": "VERIFY",
                    "side": str(row.get("side") or "-"),
                    "size": str(row.get("qty") or "-"),
                    "error": f"order-history fill could not be recovered: {exc}",
                }
            )
            continue
        if filled <= 0.0:
            continue
        symbol = str(row.get("symbol") or "").upper()
        try:
            avg_price = _required_float(row.get("avgPrice"), "recovered avgPrice", positive=True)
        except ValueError as exc:
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": "VERIFY",
                    "side": str(row.get("side") or "-"),
                    "size": f"{filled:.12g}",
                    "error": f"order-history fill could not be recovered: {exc}",
                }
            )
            continue
        try:
            notional = _required_float(
                row.get("cumExecValue"),
                "recovered cumExecValue",
                positive=True,
            )
        except ValueError:
            notional = filled * avg_price
        fee, fee_coin = _fee_from_detail(row)
        status = str(row.get("orderStatus") or "unknown")
        action = _history_fill_action(row, positions)
        requested_raw = row.get("qty")
        try:
            requested = _required_float(requested_raw, "recovered requested qty", positive=True)
        except ValueError:
            requested = filled
        stop = _to_float(row.get("stopLoss"))
        report.fills.append(
            OrderFill(
                asset=symbol.removesuffix("USDT").lower(),
                symbol=symbol,
                action=action,
                side=str(row.get("side") or "").lower(),
                stop_loss=stop if stop > 0.0 else None,
                requested_size=requested,
                filled_size=filled,
                avg_price=avg_price,
                notional=notional,
                fee=fee,
                fee_coin=fee_coin,
                order_id=order_id,
                status=status,
                position_side=str(row.get("posSide") or "").lower(),
                client_oid=client_oid,
                requested_stop_loss=stop if stop > 0.0 else None,
                stop_trigger_by=str(row.get("slTriggerBy") or ""),
                stop_order_type=str(row.get("slOrderType") or ""),
            )
        )
        known_order_ids.add(order_id)
        report.traded = True
        report.margin_notes.append(
            f"{symbol}: 已从交易所订单历史恢复本次未落账成交 {order_id}"
        )
        if status != _FILLED or filled + 1e-12 < requested:
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": action,
                    "side": str(row.get("side") or "-"),
                    "size": f"{requested:.12g}",
                    "error": (
                        "recovered order did not fully fill "
                        f"(status={status}, filled {filled:.8g}/{requested:.8g})"
                    ),
                }
            )


def _preflight_unfilled_orders(
    client: LiveTradingClient,
    *,
    report: ExecutionReport,
) -> bool:
    """Cancel Atlas20's stale zero-fill orders; block on anything else.

    The query is account-wide, not limited to today's target symbols: a stale
    order from an older plan can still fill after that asset has left the new
    book.  Unknown/manual open orders are never cancelled.  A partially filled
    stale order is cancelled when possible but still blocks the plan because
    its economic effect must be reconciled first.
    """

    blocked = False
    try:
        rows = client.unfilled_orders(category=UTA_CATEGORY)
    except (BitgetAPIError, ValueError) as exc:
        report.failures.append(
            {
                "symbol": "*",
                "action": "VERIFY",
                "side": "-",
                "size": "-",
                "error": f"could not query unfilled orders before trading: {_error_text(exc)}",
            }
        )
        return False
    for row in rows:
        symbol = str(row.get("symbol") or "").upper() or "<missing-symbol>"
        order_id = str(row.get("orderId") or "")
        client_oid = str(row.get("clientOid") or "")
        try:
            filled = _required_float(row.get("cumExecQty"), "unfilled order cumExecQty")
            fill_error = ""
        except ValueError as exc:
            filled = float("nan")
            fill_error = str(exc)
        own_order = bool(client_oid) and client_oid.startswith(("a20", "atlas20"))
        if not own_order:
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": "VERIFY",
                    "side": str(row.get("side") or "-"),
                    "size": str(row.get("qty") or "-"),
                    "error": (
                        "an unrelated unfilled order exists on this symbol; "
                        f"clientOid={client_oid or '<missing>'}, orderId={order_id or '<missing>'}"
                    ),
                }
            )
            blocked = True
            continue

        cancel_error = ""
        if order_id or client_oid:
            try:
                client.cancel_order(
                    category=UTA_CATEGORY,
                    order_id=order_id or None,
                    client_oid=None if order_id else client_oid,
                )
            except (BitgetAPIError, ValueError) as exc:
                cancel_error = _error_text(exc)
        else:
            cancel_error = "unfilled order has neither orderId nor clientOid"

        final_status = str(row.get("orderStatus") or "")
        if order_id:
            try:
                after = client.order_info(order_id=order_id)
                final_status = str(after.get("orderStatus") or final_status)
                if after.get("cumExecQty") not in (None, ""):
                    filled = _required_float(after.get("cumExecQty"), "unfilled order cumExecQty")
                    fill_error = ""
            except (BitgetAPIError, ValueError) as exc:
                cancel_error = f"{cancel_error}; {_error_text(exc)}".strip("; ")
        fill_unknown = not isfinite(filled)
        if (
            cancel_error
            or fill_unknown
            or filled > 1e-12
            or not _is_terminal_order_status(final_status)
        ):
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": "VERIFY",
                    "side": str(row.get("side") or "-"),
                    "size": str(row.get("qty") or "-"),
                    "error": (
                        "stale run order could not be proven flat"
                        f" (status={final_status or 'unknown'}, "
                        f"filled={'unknown' if fill_unknown else f'{filled:.8g}'}"
                        + (f", fill error={fill_error}" if fill_error else "")
                        + (f", cancel error={cancel_error}" if cancel_error else "")
                        + "); new orders are blocked until reconciliation"
                    ),
                }
            )
            blocked = True
        else:
            report.margin_notes.append(
                f"{symbol}: 已撤销上次遗留的零成交订单 {order_id or client_oid}"
            )
    return not blocked


def _leverage_readback_error(
    client: LiveTradingClient,
    *,
    symbol: str,
    pos_side: str,
    leverage: float,
    margin_mode: str = MARGIN_MODE_ISOLATED,
) -> str | None:
    """Verify the venue's symbol config actually contains the requested setup."""

    try:
        settings = client.account_settings()
    except (BitgetAPIError, ValueError) as exc:
        return f"leverage readback failed: {_error_text(exc)}"
    rows = settings.get("symbolConfigList") or []
    if not isinstance(rows, list):
        return "leverage readback symbolConfigList is not an array"
    candidates = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("symbol") or "").upper() == symbol.upper()
        and str(row.get("marginMode") or "").lower() == margin_mode
    ]
    if not candidates:
        return f"leverage readback has no {margin_mode} config for {symbol}"
    side_key = "shortLeverage" if pos_side.lower() == "short" else "longLeverage"
    observed: list[float] = []
    for row in candidates:
        raw = row.get(side_key)
        if raw in (None, ""):
            raw = row.get("leverage")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if isfinite(value):
            observed.append(value)
    if not observed:
        return f"leverage readback has no numeric leverage for {symbol}"
    if any(abs(value - float(leverage)) <= 1e-9 for value in observed):
        return None
    return (
        f"leverage readback mismatch for {symbol}: "
        f"expected {leverage:g}x, observed {', '.join(f'{value:g}' for value in observed)}x"
    )


def _venue_stop_protected_symbols(
    strategy_orders: list[dict[str, Any]],
    short_symbols: set[str],
) -> set[str]:
    protected: set[str] = set()
    for row in strategy_orders:
        symbol = str(row.get("symbol") or "").upper()
        if symbol not in short_symbols:
            continue
        if str(row.get("posSide") or "").lower() not in {"", "short"}:
            continue
        status = str(row.get("orderStatus") or row.get("status") or "").lower()
        if status in {"cancelled", "canceled", "filled", "triggered", "failed"}:
            continue
        try:
            stop = float(
                row.get("stopLoss")
                or row.get("slTriggerPrice")
                or row.get("triggerPrice")
                or 0.0
            )
        except (TypeError, ValueError):
            continue
        trigger = str(row.get("slTriggerBy") or row.get("triggerBy") or "").lower()
        order_type = str(
            row.get("slOrderType") or row.get("orderType") or row.get("type") or ""
        ).lower()
        if isfinite(stop) and stop > 0.0 and trigger == "mark_price" and order_type == "market":
            protected.add(symbol)
    return protected


def _short_stop_confirmed(requested: float | None, payload: dict[str, Any]) -> bool:
    if requested is None:
        return False
    attached = _to_float(payload.get("stopLoss"))
    trigger = str(payload.get("slTriggerBy") or "").lower()
    order_type = str(payload.get("slOrderType") or "").lower()
    tolerance = max(1e-9, abs(float(requested)) * 1e-8)
    return (
        attached > 0.0
        and abs(attached - float(requested)) <= tolerance
        and trigger == "mark_price"
        and order_type == "market"
    )


def execute_plan(
    client: LiveTradingClient,
    plan: ExecutionPlan,
    *,
    signal_date: str,
    pos_side: str = "long",
    leverage: float = 2.0,
    margin_mode: str = MARGIN_MODE_ISOLATED,
    require_isolated: bool = False,
    known_protected_short_symbols: set[str] | None = None,
    hold_mode: str | None = None,
    fill_timeout_seconds: float = 20.0,
    poll_interval_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    client_oid_prefix: str | None = None,
) -> ExecutionReport:
    """Trade ``plan`` on the live account and report the real outcome.

    Orders are attempted in plan order (reductions first, as the planner emits
    them).  A rejected order is recorded and the remaining orders still run:
    the next daily plan re-reads the account, so a missed leg self-corrects.
    """

    if require_isolated and margin_mode != MARGIN_MODE_ISOLATED:
        raise ValueError("require_isolated conflicts with a non-isolated margin_mode")

    report = ExecutionReport(signal_date=signal_date)
    assets = client.account_assets()
    report.equity_before = _account_equity(assets)

    mode = hold_mode if hold_mode is not None else client.hold_mode()
    hedging = str(mode).lower() == "hedge_mode"

    initial_positions = [dict(row) for row in client.current_positions()]
    initial_short_qty = {
        str(row.get("symbol") or "").upper(): abs(_signed_position_qty(row))
        for row in initial_positions
        if _signed_position_qty(row) < 0.0
    }
    prefix = client_oid_prefix or f"atlas20{int(time.time() * 1000):x}"
    preflight_ok = _preflight_unfilled_orders(client, report=report)
    blocked_all_opens = False
    if require_isolated:
        initial_invalid_modes = _invalid_margin_modes(initial_positions)
        if initial_invalid_modes:
            blocked_all_opens = True
            report.failures.append(
                {
                    "symbol": "*",
                    "action": "VERIFY",
                    "side": "-",
                    "size": "-",
                    "error": (
                        "isolated margin required but preflight venue reports "
                        + ",".join(initial_invalid_modes)
                        + "; only risk-reducing orders are allowed"
                    ),
                }
            )

    isolated_ok = margin_mode == MARGIN_MODE_ISOLATED
    leverage_done: set[tuple[str, str]] = set()
    blocked_open_assets: set[str] = set()
    stop_emergency_attempted: set[str] = set()
    halt_all_orders = not preflight_ok

    for order in plan.orders:
        if halt_all_orders:
            report.failures.append(
                {
                    "symbol": order.symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": "order blocked because open-order reconciliation did not pass",
                }
            )
            continue
        symbol = order.symbol
        if blocked_all_opens and not order.reduce_only:
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": "open blocked because the account is not fully isolated",
                }
            )
            continue
        if not order.reduce_only and order.asset in blocked_open_assets:
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": (
                        "opposite-side open was blocked because the prior close failed"
                    ),
                }
            )
            continue
        order_pos_side = str(order.pos_side or pos_side).lower()
        leverage_key = (symbol, order_pos_side)
        if not order.reduce_only and leverage_key not in leverage_done:
            if require_isolated:
                try:
                    client.set_leverage(
                        symbol,
                        leverage,
                        pos_side=order_pos_side,
                        margin_mode=MARGIN_MODE_ISOLATED,
                        long_leverage=leverage,
                        short_leverage=leverage,
                    )
                except BitgetAPIError as exc:
                    report.failures.append(
                        {
                            "symbol": symbol,
                            "action": order.action,
                            "side": order.side,
                            "size": f"{order.size:.12g}",
                            "error": f"isolated margin is required but setup failed: {exc}",
                        }
                    )
                    report.margin_notes.append(
                        f"{symbol}: 逐仓杠杆设置被拒绝，规格要求逐仓，已跳过该腿（{exc}）"
                    )
                    continue
                readback_error = _leverage_readback_error(
                    client,
                    symbol=symbol,
                    pos_side=order_pos_side,
                    leverage=leverage,
                )
                if readback_error is not None:
                    report.failures.append(
                        {
                            "symbol": symbol,
                            "action": order.action,
                            "side": order.side,
                            "size": f"{order.size:.12g}",
                            "error": readback_error,
                        }
                    )
                    report.margin_notes.append(
                        f"{symbol}: 杠杆/逐仓配置回读不符，已跳过该腿"
                    )
                    continue
                leverage_done.add(leverage_key)
            else:
                # Cap the fallback configuration first: this venue can accept an
                # isolated config and still fill the order in crossed mode.
                try:
                    client.set_leverage(
                        symbol,
                        leverage,
                        pos_side=order_pos_side,
                        margin_mode=MARGIN_MODE_CROSSED,
                        long_leverage=leverage,
                        short_leverage=leverage,
                    )
                except (BitgetAPIError, ValueError) as exc:
                    report.failures.append(
                        {
                            "symbol": symbol,
                            "action": order.action,
                            "side": order.side,
                            "size": f"{order.size:.12g}",
                            "error": f"could not set crossed leverage: {exc}",
                        }
                    )
                    report.margin_notes.append(f"{symbol}: 全仓杠杆设置失败（{exc}）")
                    continue
                leverage_done.add(leverage_key)
                if isolated_ok:
                    try:
                        client.set_leverage(
                            symbol,
                            leverage,
                            pos_side=order_pos_side,
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
            "pos_side": order_pos_side if hedging else None,
            "reduce_only": order.reduce_only and not hedging,
            "client_oid": _client_oid(
                prefix,
                purpose="order",
                symbol=symbol,
                action=order.action,
                side=order.side,
                pos_side=order_pos_side,
                reduce_only=order.reduce_only,
            ),
        }
        if isolated_ok and not order.reduce_only:
            body["margin_mode"] = MARGIN_MODE_ISOLATED
        if order.stop_loss is not None and not order.reduce_only:
            body["stop_loss"] = order.stop_loss
            body["sl_trigger_by"] = "mark_price"
            body["sl_order_type"] = "market"

        try:
            try:
                placed = client.place_order(**body)
            except BitgetAPIError as exc:
                if "margin_mode" in body and is_isolated_unsupported(exc):
                    if require_isolated:
                        raise BitgetAPIError(
                            f"isolated margin is required but order setup failed: {exc}"
                        ) from exc
                    isolated_ok = False
                    report.margin_notes.append(
                        "逐仓不可用（venue 拒绝 25200 fixedMargin）→ 已按全仓执行"
                    )
                    body.pop("margin_mode", None)
                    # fresh clientOid: the rejected attempt never reached the
                    # matching engine, but a reused id would be refused
                    body["client_oid"] = _client_oid(
                        prefix,
                        purpose="fallback",
                        symbol=symbol,
                        action=order.action,
                        side=order.side,
                        pos_side=order_pos_side,
                        reduce_only=order.reduce_only,
                    )
                    try:
                        placed = client.place_order(**body)
                    except BitgetAPIError as retry_exc:
                        recovered = _lookup_order_by_client_oid(
                            client, str(body["client_oid"])
                        )
                        if not _recovered_order_matches(
                            recovered,
                            symbol=symbol,
                            side=order.side,
                            pos_side=order_pos_side,
                        ):
                            raise retry_exc
                        placed = recovered
                        report.margin_notes.append(
                            f"{symbol}: 下单响应不明确，已按 clientOid 回查确认"
                        )
                else:
                    recovered = _lookup_order_by_client_oid(
                        client, str(body["client_oid"])
                    )
                    if not _recovered_order_matches(
                        recovered,
                        symbol=symbol,
                        side=order.side,
                        pos_side=order_pos_side,
                    ):
                        raise
                    placed = recovered
                    report.margin_notes.append(
                        f"{symbol}: 下单响应不明确，已按 clientOid 回查确认"
                    )
        except (BitgetAPIError, ValueError) as exc:
            if order.action == "CLOSE":
                blocked_open_assets.add(order.asset)
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
        if not order_id:
            recovered = _lookup_order_by_client_oid(client, str(body["client_oid"]))
            if _recovered_order_matches(
                recovered,
                symbol=symbol,
                side=order.side,
                pos_side=order_pos_side,
            ):
                placed = recovered
                order_id = str(placed.get("orderId") or "")
                report.margin_notes.append(
                    f"{symbol}: 下单响应缺少 orderId，已按 clientOid 回查确认"
                )
        if not order_id:
            report.traded = True
            if order.action == "CLOSE":
                blocked_open_assets.add(order.asset)
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": "venue did not return orderId",
                }
            )
            continue
        payload = wait_for_fill(
            client,
            order_id=order_id,
            timeout_seconds=fill_timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
            clock=clock,
        )
        initial_status = str(payload.get("orderStatus") or "")
        if not _is_terminal_order_status(initial_status):
            cancel_error = ""
            try:
                client.cancel_order(category=UTA_CATEGORY, order_id=order_id)
            except (BitgetAPIError, ValueError) as exc:
                cancel_error = _error_text(exc)
            try:
                payload = wait_for_fill(
                    client,
                    order_id=order_id,
                    timeout_seconds=min(max(fill_timeout_seconds, 0.0), 5.0),
                    poll_interval_seconds=poll_interval_seconds,
                    sleep=sleep,
                    clock=clock,
                )
            except (BitgetAPIError, ValueError) as exc:
                cancel_error = f"{cancel_error}; {_error_text(exc)}".strip("; ")
            final_status = str(payload.get("orderStatus") or initial_status)
            if not _is_terminal_order_status(final_status):
                halt_all_orders = True
                report.failures.append(
                    {
                        "symbol": symbol,
                        "action": order.action,
                        "side": order.side,
                        "size": f"{order.size:.12g}",
                        "error": (
                            "order did not reach a terminal status and could not be "
                            f"proven cancelled (status={final_status or 'unknown'}"
                            + (f", cancel error={cancel_error}" if cancel_error else "")
                            + ")"
                        ),
                    }
                )
            elif cancel_error:
                halt_all_orders = True
                report.failures.append(
                    {
                        "symbol": symbol,
                        "action": order.action,
                        "side": order.side,
                        "size": f"{order.size:.12g}",
                        "error": f"order cancellation response was ambiguous: {cancel_error}",
                    }
                )
            else:
                report.margin_notes.append(
                    f"{symbol}: 市价单超时未终态，已撤单并核对"
                )
        try:
            filled = _required_float(payload.get("cumExecQty"), "order cumExecQty")
        except ValueError as exc:
            halt_all_orders = True
            if order.action == "CLOSE":
                blocked_open_assets.add(order.asset)
            report.traded = True
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": str(exc),
                }
            )
            continue
        avg_price = (
            _required_float(payload.get("avgPrice"), "order avgPrice")
            if filled > 0.0
            else 0.0
        )
        if payload.get("cumExecValue") not in (None, ""):
            notional = _required_float(payload.get("cumExecValue"), "order cumExecValue")
        else:
            notional = filled * avg_price
        fee, fee_coin = _fee_from_detail(payload)
        attached_stop = _to_float(payload.get("stopLoss"))
        status = str(payload.get("orderStatus") or "")
        stop_confirmed = _short_stop_confirmed(order.stop_loss, payload)
        report.fills.append(
            OrderFill(
                asset=order.asset,
                symbol=symbol,
                action=order.action,
                side=order.side,
                stop_loss=attached_stop if attached_stop > 0.0 else None,
                requested_size=order.size,
                filled_size=filled,
                avg_price=avg_price,
                notional=notional,
                fee=fee,
                fee_coin=fee_coin,
                order_id=order_id,
                status=status or "unknown",
                position_side=order_pos_side,
                client_oid=str(body.get("client_oid") or ""),
                requested_stop_loss=order.stop_loss,
                stop_trigger_by=str(payload.get("slTriggerBy") or ""),
                stop_order_type=str(payload.get("slOrderType") or ""),
            )
        )
        report.traded = True
        tolerance = max(1e-9, abs(order.size) * 1e-8)
        if status == _FILLED and abs(filled - order.size) > tolerance:
            halt_all_orders = True
            if order.action == "CLOSE":
                blocked_open_assets.add(order.asset)
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": (
                        "venue reported filled with a different quantity "
                        f"({filled:.8g} vs requested {order.size:.8g})"
                    ),
                }
            )
        if order.stop_loss is not None and not stop_confirmed:
            stop_emergency_attempted.add(symbol.upper())
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": "short stop loss was not confirmed by the venue",
                }
            )
            if filled > 0.0:
                close_qty = max(filled, initial_short_qty.get(symbol, 0.0) + filled)
                close_body: dict[str, Any] = {
                    "symbol": symbol,
                    "qty": close_qty,
                    "side": "buy",
                    "order_type": "market",
                    "pos_side": order_pos_side if hedging else None,
                    "reduce_only": not hedging,
                    "client_oid": _client_oid(
                        prefix,
                        purpose="stop-close",
                        symbol=symbol,
                        action="EMERGENCY_CLOSE",
                        side="buy",
                        pos_side=order_pos_side,
                        reduce_only=not hedging,
                    ),
                }
                try:
                    closed = client.place_order(**close_body)
                    close_id = str(closed.get("orderId") or "")
                    if not close_id:
                        raise BitgetAPIError("venue did not return orderId for emergency close")
                    close_payload = wait_for_fill(
                        client,
                        order_id=close_id,
                        timeout_seconds=fill_timeout_seconds,
                        poll_interval_seconds=poll_interval_seconds,
                        sleep=sleep,
                        clock=clock,
                    )
                    close_filled = _to_float(close_payload.get("cumExecQty"))
                    close_avg = _to_float(close_payload.get("avgPrice"))
                    close_notional = _to_float(close_payload.get("cumExecValue")) or (
                        close_filled * close_avg
                    )
                    close_fee, close_fee_coin = _fee_from_detail(close_payload)
                    close_status = str(close_payload.get("orderStatus") or "unknown")
                    report.fills.append(
                        OrderFill(
                            asset=order.asset,
                            symbol=symbol,
                            action="EMERGENCY_CLOSE",
                            side="buy",
                            stop_loss=None,
                            requested_size=close_qty,
                            filled_size=close_filled,
                            avg_price=close_avg,
                            notional=close_notional,
                            fee=close_fee,
                            fee_coin=close_fee_coin,
                            order_id=close_id,
                            status=close_status,
                            position_side=order_pos_side,
                            client_oid=str(close_body["client_oid"]),
                        )
                    )
                    if close_status != _FILLED or close_filled + 1e-12 < close_qty:
                        report.failures.append(
                            {
                                "symbol": symbol,
                                "action": "EMERGENCY_CLOSE",
                                "side": "buy",
                                "size": f"{close_qty:.12g}",
                                "error": (
                                    "emergency close did not fully fill "
                                    f"(status={close_status}, filled {close_filled:.8g}/{close_qty:.8g})"
                                ),
                            }
                        )
                except (BitgetAPIError, ValueError) as exc:
                    report.failures.append(
                        {
                            "symbol": symbol,
                            "action": "EMERGENCY_CLOSE",
                            "side": "buy",
                            "size": f"{close_qty:.12g}",
                            "error": f"emergency close failed: {_error_text(exc)}",
                        }
                    )
        if status != _FILLED:
            if order.action == "CLOSE":
                blocked_open_assets.add(order.asset)
            error = (
                "order cancelled by the venue"
                if status == _CANCELLED
                else f"order not filled (status={status or 'unknown'}, "
                f"filled {filled:.8g}/{order.size:.8g})"
            )
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": order.action,
                    "side": order.side,
                    "size": f"{order.size:.12g}",
                    "error": error,
                }
            )

    positions = client.current_positions()
    report.positions_after = [dict(row) for row in positions]
    _recover_fills_from_order_history(
        client,
        client_oid_prefix=prefix,
        report=report,
        positions=report.positions_after,
    )
    open_short_symbols = {
        str(row.get("symbol") or "").upper()
        for row in report.positions_after
        if _signed_position_qty(row) < 0.0
        and str(row.get("symbol") or "")
        and str(row.get("symbol") or "").upper() not in stop_emergency_attempted
    }
    if open_short_symbols:
        journal_protected = {
            str(symbol).upper()
            for symbol in (known_protected_short_symbols or set())
        }
        recent_confirmed = {
            fill.symbol.upper()
            for fill in report.fills
            if fill.short_stop_confirmed and fill.status == _FILLED
        }
        try:
            strategy_orders = client.unfilled_strategy_orders(category=UTA_CATEGORY)
        except (BitgetAPIError, ValueError) as exc:
            venue_protected: set[str] = set()
            report.failures.append(
                {
                    "symbol": "*",
                    "action": "VERIFY",
                    "side": "short",
                    "size": "-",
                    "error": f"could not verify live short stop orders: {_error_text(exc)}",
                }
            )
        else:
            venue_protected = _venue_stop_protected_symbols(
                strategy_orders,
                open_short_symbols,
            )
        protected = venue_protected & (recent_confirmed | journal_protected)
        unprotected = [
            dict(row)
            for row in report.positions_after
            if _signed_position_qty(row) < 0.0
            and str(row.get("symbol") or "").upper() not in protected
        ]
        for index, row in enumerate(unprotected):
            symbol = str(row.get("symbol") or "").upper()
            qty = abs(_signed_position_qty(row))
            report.failures.append(
                {
                    "symbol": symbol,
                    "action": "VERIFY",
                    "side": "short",
                    "size": f"{qty:.12g}",
                    "error": (
                        "existing short has no live venue stop; emergency close attempted"
                    ),
                }
            )
            if qty <= 0.0:
                continue
            try:
                closed = client.place_order(
                    symbol=symbol,
                    qty=qty,
                    side="buy",
                    order_type="market",
                    pos_side="short" if hedging else None,
                    reduce_only=not hedging,
                    client_oid=_client_oid(
                        prefix,
                        purpose="gap-close",
                        symbol=symbol,
                        action="EMERGENCY_CLOSE",
                        side="buy",
                        pos_side="short" if hedging else "",
                        reduce_only=not hedging,
                    ),
                )
                close_id = str(closed.get("orderId") or "")
                if not close_id:
                    raise BitgetAPIError("venue did not return orderId for stop-gap close")
                close_payload = wait_for_fill(
                    client,
                    order_id=close_id,
                    timeout_seconds=fill_timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                    sleep=sleep,
                    clock=clock,
                )
                close_filled = _to_float(close_payload.get("cumExecQty"))
                close_avg = _to_float(close_payload.get("avgPrice"))
                close_notional = _to_float(close_payload.get("cumExecValue")) or (
                    close_filled * close_avg
                )
                close_fee, close_fee_coin = _fee_from_detail(close_payload)
                close_status = str(close_payload.get("orderStatus") or "unknown")
                report.fills.append(
                    OrderFill(
                        asset=str(row.get("asset") or symbol.removesuffix("USDT")).lower(),
                        symbol=symbol,
                        action="EMERGENCY_CLOSE",
                        side="buy",
                        stop_loss=None,
                        requested_size=qty,
                        filled_size=close_filled,
                        avg_price=close_avg,
                        notional=close_notional,
                        fee=close_fee,
                        fee_coin=close_fee_coin,
                        order_id=close_id,
                        status=close_status,
                        position_side="short",
                        client_oid=str(
                            closed.get("clientOid")
                            or _client_oid(
                                prefix,
                                purpose="gap-close",
                                symbol=symbol,
                                action="EMERGENCY_CLOSE",
                                side="buy",
                                pos_side="short" if hedging else "",
                                reduce_only=not hedging,
                            )
                        ),
                    )
                )
                if close_status != _FILLED or close_filled + 1e-12 < qty:
                    report.failures.append(
                        {
                            "symbol": symbol,
                            "action": "EMERGENCY_CLOSE",
                            "side": "buy",
                            "size": f"{qty:.12g}",
                            "error": (
                                "stop-gap close did not fully fill "
                                f"(status={close_status}, filled {close_filled:.8g}/{qty:.8g})"
                            ),
                        }
                    )
            except (BitgetAPIError, ValueError) as exc:
                report.failures.append(
                    {
                        "symbol": symbol,
                        "action": "EMERGENCY_CLOSE",
                        "side": "buy",
                        "size": f"{qty:.12g}",
                        "error": f"stop-gap close failed: {_error_text(exc)}",
                    }
                )
        if unprotected:
            positions = client.current_positions()
            report.positions_after = [dict(item) for item in positions]
    position_modes = {
        str(row.get("marginMode") or "").strip().lower() or "<missing>"
        for row in report.positions_after
        if abs(_signed_position_qty(row)) > 1e-12
    }
    if len(position_modes) == 1:
        report.margin_mode = next(iter(position_modes))
    elif position_modes:
        report.margin_mode = "mixed:" + ",".join(sorted(position_modes))
    invalid_modes = sorted(
        mode for mode in position_modes if mode != MARGIN_MODE_ISOLATED
    )
    if require_isolated and invalid_modes:
        report.failures.append(
            {
                "symbol": "*",
                "action": "VERIFY",
                "side": "-",
                "size": "-",
                "error": (
                    "isolated margin required but venue reports "
                    + ",".join(invalid_modes)
                ),
            }
        )

    # Isolated-margin top-ups only exist for isolated legs.  On a crossed
    # account the venue answers 40731/25200 every single day, which is noise
    # rather than information - so say it once, plainly, and skip the calls.
    if plan.margin_intents:
        if report.failures:
            report.margin_notes.append(
                f"本轮回调存在失败：跳过 {len(plan.margin_intents)} 笔保证金调整"
            )
        elif report.margin_mode and report.margin_mode != MARGIN_MODE_ISOLATED:
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
    report.equity_after = _account_equity(assets_after)
    usdt_row = next(
        (
            row
            for row in assets_after.get("assets") or []
            if isinstance(row, dict) and str(row.get("coin", "")).upper() == "USDT"
        ),
        {},
    )
    report.available_after = _required_float(
        usdt_row.get("available"), "USDT available after execution"
    )
    report.balance_after = _required_float(
        usdt_row.get("balance"), "USDT balance after execution"
    )
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
    capital_flow: float = 0.0,
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
    signed_notional_by_asset: dict[str, float] = {}
    ticker_by_asset: dict[str, str] = {}
    position_notionals: list[tuple[dict[str, Any], str, float]] = []
    for row in positions:
        symbol = str(row.get("symbol") or "")
        asset = str(row.get("asset") or symbol.upper().removesuffix("USDT")).lower()
        mark = _to_float(row.get("markPrice") or row.get("avgPrice"))
        notional = abs(_to_float(row.get("total"))) * mark
        notional_by_asset[asset] = notional_by_asset.get(asset, 0.0) + notional
        signed_notional_by_asset[asset] = (
            signed_notional_by_asset.get(asset, 0.0) + _signed_position_qty(row) * mark
        )
        ticker_by_asset[asset] = symbol.upper().removesuffix("USDT") or asset.upper()
        position_notionals.append((row, asset, notional))
    total_notional = sum(notional_by_asset.values())
    equity = (
        report.equity_after
        if report.equity_after is not None
        else report.equity_before
    )
    day_pnl = (
        None
        if prev_equity is None
        else equity - float(prev_equity) - float(capital_flow)
    )

    lines = [f"Atlas20 自动调仓 · {beijing.strftime('%Y-%m-%d %H:%M')} 北京", ""]
    lines.append(f"总权益 {_money(equity)} USDT")
    share = f"（{total_notional / equity:.1%} 权益）" if equity > 0 else ""
    lines.append(f"仓位价值 {_money(total_notional)} USDT{share}")
    capital_base = None if prev_equity is None else float(prev_equity) + float(capital_flow)
    if day_pnl is None or not capital_base or capital_base <= 0:
        lines.append("今日盈亏 —（首个记录日）")
    else:
        lines.append(f"今日盈亏 {day_pnl:+.2f} USDT（{day_pnl / capital_base:+.2%}）")
    if prev_day_pnl is None:
        lines.append("昨日盈亏 —")
    else:
        lines.append(f"昨日盈亏 {float(prev_day_pnl):+.2f} USDT")
    if abs(float(capital_flow)) > 0.005:
        lines.append(f"外部资金流 {float(capital_flow):+.2f} USDT（不计入盈亏）")

    lines += ["", "今日成交:"]
    if not report.fills:
        lines.append("  无")
    for fill in report.fills:
        verb = "买入" if fill.side == "buy" else "卖出"
        note = "" if fill.status == _FILLED else f"（{fill.status}）"
        stop_note = (
            f" · 止损 {fill.stop_loss:.8g}" if fill.stop_loss is not None else ""
        )
        lines.append(
            f"  {verb} {fill.asset.upper()} {_qty(fill.filled_size)} 枚 @ {fill.avg_price:.8g}"
            f" · {_money(fill.notional)} USDT · 费 {fill.fee:.4f}{stop_note}{note}"
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
        signed_size = _signed_position_qty(row)
        size = abs(signed_size)
        entry = _to_float(row.get("avgPrice"))
        mark = _to_float(row.get("markPrice") or row.get("avgPrice"))
        upnl = _to_float(row.get("unrealisedPnl"))
        if not upnl:
            upnl = (mark - entry) * signed_size
        weight = notional / equity if equity > 0 else 0.0
        side = "SHORT" if signed_size < 0.0 else "LONG"
        lines.append(
            f"  {asset.upper()} {side} {_qty(size)} 枚 · "
            f"{_money(notional)} USDT · {weight:.1%} · 浮盈 {upnl:+.2f}"
        )

    if targets is not None:
        checks = []
        for asset in sorted(targets):
            target_weight = float(targets.get(asset, 0.0))
            target_notional = target_weight * equity
            actual = signed_notional_by_asset.get(asset.lower(), 0.0)
            gap = actual - target_notional
            lot = float((lot_notional or {}).get(asset, 0.0))
            tolerance = max(1.0, 0.01 * abs(target_notional), 1.5 * lot)
            flag = "" if abs(gap) <= tolerance else " ⚠️"
            checks.append(
                f"{asset.upper()} 目标 {_money(target_notional)} / 实际 {_money(actual)}{flag}"
            )
        orphans = sorted(set(notional_by_asset) - {asset.lower() for asset in targets})
        if orphans:
            orphan_labels = [ticker_by_asset.get(asset, asset.upper()) for asset in orphans]
            checks.append(f"⚠️ 计划外持仓: {', '.join(orphan_labels)}")
        if checks:
            age = (
                ""
                if event_age_days is None
                else (
                    "（今天的变化）"
                    if event_age_days <= 0
                    else f"（{event_age_days} 天前的最近变化）"
                )
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
