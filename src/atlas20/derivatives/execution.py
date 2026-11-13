"""Live execution planning for the frozen derivatives specification.

The research engine trades ideal notionals on mark candles.  A real Bitget
account differs in three ways that this module makes explicit:

1. the balance is whatever the account holds today, so every target is sized
   from live equity (1000 USDT is only the research reference);
2. orders must be a multiple of the contract's ``quantityMultiplier`` and at
   least ``minOrderQty`` / ``minOrderAmount``;
3. isolated margin is posted by the exchange from the leverage, so reaching
   the specification's 51.5% margin ratio needs an explicit
   ``add``/``remove`` margin adjustment afterwards.

``build_execution_plan`` mirrors the engine's rebalance semantics exactly -
reduce/close before open/increase, cap gross margin at
``max_margin_utilization`` of equity, and scale an order down rather than
attempting to post margin the account does not have.  The replay harness
(``scripts/replay_live_execution.py``) checks the planner against the engine's
full historical trade ledger; the failure drills live in
``tests/test_derivatives_execution.py``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from atlas20.derivatives.margin import initial_margin_ratio

_EPS = 1e-12


@dataclass(frozen=True)
class ContractSpec:
    """The Bitget instrument fields the order planner rounds against."""

    symbol: str
    min_order_qty: float = 0.0
    quantity_multiplier: float = 0.0
    min_order_usdt: float = 0.0
    quantity_precision: int | None = None
    price_multiplier: float = 0.0
    price_precision: int | None = None

    @classmethod
    def from_bitget_instrument(cls, row: Mapping[str, Any]) -> "ContractSpec":
        def _float(key: str) -> float:
            value = row.get(key, 0.0)
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        precision_value = row.get("quantityPrecision")
        try:
            precision = int(precision_value) if precision_value not in (None, "") else None
        except (TypeError, ValueError):
            precision = None
        price_precision_value = row.get("pricePrecision")
        try:
            price_precision = (
                int(price_precision_value)
                if price_precision_value not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            price_precision = None
        return cls(
            symbol=str(row.get("symbol", "")),
            min_order_qty=_float("minOrderQty"),
            quantity_multiplier=_float("quantityMultiplier"),
            min_order_usdt=_float("minOrderAmount"),
            quantity_precision=precision,
            price_multiplier=_float("priceMultiplier"),
            price_precision=price_precision,
        )

    def round_down_qty(self, qty: float) -> float:
        """Floor a quantity to the exchange step and decimal precision."""

        if qty <= 0.0:
            return 0.0
        step = self.quantity_multiplier
        if step > 0.0:
            qty = math.floor(qty / step + 1e-9) * step
        if self.quantity_precision is not None:
            scale = 10**self.quantity_precision
            qty = math.floor(qty * scale + 1e-9) / scale
        return max(0.0, qty)

    def round_up_price(self, price: float) -> float:
        """Round an adverse stop trigger up to the venue price grid."""

        if price <= 0.0:
            return 0.0
        step = self.price_multiplier
        if step > 0.0:
            price = math.ceil(price / step - 1e-9) * step
        if self.price_precision is not None:
            scale = 10**self.price_precision
            price = math.ceil(price * scale - 1e-9) / scale
        return price

    def minimum_notional(self, *, floor_usdt: float = 0.0) -> float:
        """Smallest order the venue accepts, expressed in USDT."""

        return max(self.min_order_usdt, floor_usdt)

    def is_tradeable(self, qty: float, price: float, *, floor_usdt: float = 0.0) -> bool:
        if qty <= 0.0 or price <= 0.0:
            return False
        if self.min_order_qty > 0.0 and qty + 1e-12 < self.min_order_qty:
            return False
        return qty * price + 1e-9 >= self.minimum_notional(floor_usdt=floor_usdt)


@dataclass(frozen=True)
class PositionState:
    """One live leg as the exchange reports it."""

    asset: str
    symbol: str
    side: str
    size: float
    entry_price: float
    mark_price: float
    margin: float

    @property
    def notional(self) -> float:
        return self.size * self.mark_price

    @property
    def margin_ratio(self) -> float:
        notional = self.notional
        return self.margin / notional if notional > 0.0 else 0.0


@dataclass(frozen=True)
class AccountState:
    """Live account snapshot used for one daily rebalance plan."""

    equity: float
    available_margin: float
    positions: Mapping[str, PositionState] = field(default_factory=dict)
    as_of: pd.Timestamp | None = None


@dataclass(frozen=True)
class OrderIntent:
    asset: str
    symbol: str
    action: str  # OPEN / INCREASE / REDUCE / CLOSE
    side: str  # buy / sell
    size: float
    price: float
    notional: float
    reduce_only: bool
    reason: str
    pos_side: str = "long"
    stop_loss: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "symbol": self.symbol,
            "action": self.action,
            "side": self.side,
            "size": self.size,
            "price": self.price,
            "notional": self.notional,
            "reduce_only": self.reduce_only,
            "reason": self.reason,
            "pos_side": self.pos_side,
            "stop_loss": self.stop_loss,
        }


@dataclass(frozen=True)
class MarginIntent:
    asset: str
    symbol: str
    pos_side: str
    operation: str  # add / remove
    amount: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "symbol": self.symbol,
            "pos_side": self.pos_side,
            "operation": self.operation,
            "amount": self.amount,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExecutionPlan:
    equity: float
    leverage: float
    target_margin_ratio: float
    orders: list[OrderIntent]
    margin_intents: list[MarginIntent]
    warnings: list[str]
    target_notional: dict[str, float]
    expected_gross_notional: float
    expected_margin: float
    signed_target_notional: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "equity": self.equity,
            "leverage": self.leverage,
            "target_margin_ratio": self.target_margin_ratio,
            "orders": [order.as_dict() for order in self.orders],
            "margin_intents": [intent.as_dict() for intent in self.margin_intents],
            "warnings": list(self.warnings),
            "target_notional": dict(self.target_notional),
            "signed_target_notional": dict(self.signed_target_notional),
            "expected_gross_notional": self.expected_gross_notional,
            "expected_margin": self.expected_margin,
        }


def build_execution_plan(
    account: AccountState,
    targets: Mapping[str, float],
    specs: Mapping[str, ContractSpec],
    prices: Mapping[str, float],
    *,
    leverage: float = 2.0,
    long_buffer: float = 0.50,
    short_buffer: float = 0.50,
    fee_buffer: float = 0.005,
    maintenance_margin_rate: float = 0.01,
    max_margin_utilization: float = 0.85,
    max_gross_exposure: float | None = None,
    short_stop_loss_pct: float | None = None,
    taker_fee_rate: float = 0.0006,
    min_rebalance_usdt: float = 0.0,
    min_margin_delta: float = 0.01,
    mirror_engine: bool = False,
) -> ExecutionPlan:
    """Build signed long/short orders that move the account to the target.

    Target weights are signed relative to account equity.  Positive weights
    open or increase longs; negative weights open or increase shorts.  A
    direction flip is always expressed as close-first, then open, so the
    planner never relies on a venue's netting behaviour.

    ``mirror_engine=True`` reproduces the research engine's exact behaviour
    (no venue minimums, no rounding floor beyond the step) and is what the
    replay harness compares against the historical trade ledger.
    """

    if not math.isfinite(account.equity):
        raise ValueError("account equity must be finite")
    if leverage <= 0.0:
        raise ValueError("leverage must be positive")
    if max_gross_exposure is not None and max_gross_exposure < 0.0:
        raise ValueError("max_gross_exposure must be non-negative when set")
    if short_stop_loss_pct is not None and not 0.0 < short_stop_loss_pct < 1.0:
        raise ValueError("short_stop_loss_pct must be in (0, 1) when set")

    warnings: list[str] = []
    risk_reducing_only = account.equity <= 0.0
    if risk_reducing_only:
        warnings.append(
            "account equity is non-positive: new target exposure is suppressed; "
            "risk-reducing closes remain enabled"
        )
    long_margin_ratio = initial_margin_ratio(
        "long",
        maintenance_margin_rate=maintenance_margin_rate,
        fee_buffer=fee_buffer,
        long_buffer=long_buffer,
    )
    short_margin_ratio = initial_margin_ratio(
        "short",
        maintenance_margin_rate=maintenance_margin_rate,
        fee_buffer=fee_buffer,
        short_buffer=short_buffer,
    )
    exchange_margin_ratio = 1.0 / leverage

    def margin_ratio_for_side(side: str) -> float:
        return long_margin_ratio if side == "long" else short_margin_ratio

    desired_signed: dict[str, float] = {}
    for asset, raw_weight in targets.items():
        if risk_reducing_only:
            break
        weight = float(raw_weight)
        if abs(weight) <= _EPS:
            continue
        if asset not in prices or not (float(prices[asset]) > 0.0):
            warnings.append(f"{asset}: no usable price; target dropped")
            continue
        if asset not in specs and not mirror_engine:
            warnings.append(f"{asset}: no contract spec; target dropped")
            continue
        desired_signed[str(asset)] = weight * account.equity

    gross_requested = sum(abs(value) for value in desired_signed.values())
    gross_scale = 1.0
    if max_gross_exposure is not None and gross_requested > float(max_gross_exposure) + _EPS:
        gross_scale = float(max_gross_exposure) / gross_requested
        warnings.append(
            f"gross exposure scaled to {gross_scale:.4f}x by the "
            f"{float(max_gross_exposure):,.2f} USDT cap"
        )

    desired_signed = {asset: value * gross_scale for asset, value in desired_signed.items()}
    required_margin = sum(
        abs(value) * margin_ratio_for_side("long" if value > 0.0 else "short")
        for value in desired_signed.values()
    )
    margin_scale = 1.0
    if required_margin > max_margin_utilization * account.equity:
        margin_scale = (max_margin_utilization * account.equity) / required_margin
        warnings.append(
            f"gross margin scaled to {margin_scale:.4f}x by the "
            f"{max_margin_utilization:.0%} margin-utilization cap"
        )

    desired_signed = {asset: value * margin_scale for asset, value in desired_signed.items()}
    desired_abs = {asset: abs(value) for asset, value in desired_signed.items()}

    positions = dict(account.positions)
    prices_all: dict[str, float] = {asset: float(price) for asset, price in prices.items()}
    for asset, position in positions.items():
        prices_all.setdefault(asset, float(position.mark_price))

    def _spec(asset: str) -> ContractSpec:
        if asset in specs:
            return specs[asset]
        if mirror_engine:
            return ContractSpec(symbol=str(asset).upper())
        raise KeyError(asset)

    def _side(position: PositionState) -> str:
        return "short" if str(position.side).lower() == "short" else "long"

    orders: list[OrderIntent] = []
    available = float(account.available_margin)
    final_sizes: dict[str, float] = {
        asset: position.size for asset, position in positions.items()
    }
    final_sides: dict[str, str | None] = {
        asset: _side(position) for asset, position in positions.items()
    }

    def _register_trade(
        *,
        asset: str,
        price: float,
        size_delta: float,
        margin_delta: float,
        fee: float,
        pnl: float,
    ) -> None:
        nonlocal available
        available += margin_delta + pnl - fee
        final_sizes[asset] = max(0.0, final_sizes.get(asset, 0.0) + size_delta)

    # Reduce / close first so released margin can fund opposite-side opens.
    # The iteration order mirrors the engine: positions in open order.
    for asset, position in positions.items():
        price = prices_all.get(asset)
        if price is None or price <= 0.0:
            warnings.append(f"{asset}: held leg has no price; left untouched")
            continue
        target_signed = float(desired_signed.get(asset, 0.0))
        current_side = _side(position)
        same_side = (
            abs(target_signed) > _EPS
            and ((target_signed > 0.0) == (current_side == "long"))
        )
        if same_side and abs(target_signed) / price >= position.size - 1e-12:
            continue
        action = "REDUCE" if same_side else "CLOSE"
        size = (
            position.size - abs(target_signed) / price
            if same_side
            else position.size
        )
        if size <= _EPS:
            continue
        spec = _spec(asset)
        if not mirror_engine:
            size = spec.round_down_qty(size)
            if action == "REDUCE" and not spec.is_tradeable(
                size, price, floor_usdt=min_rebalance_usdt
            ):
                warnings.append(
                    f"{asset}: reduce of {size:.8g} below venue minimum; kept for now"
                )
                continue
            if size <= 0.0:
                continue
        side = "sell" if current_side == "long" else "buy"
        fee = size * price * taker_fee_rate
        margin_delta = (
            position.margin * (size / position.size)
            if position.size > 0.0
            else position.margin
        )
        pnl = (
            size * (price - position.entry_price)
            if current_side == "long"
            else size * (position.entry_price - price)
        )
        settlement = margin_delta + pnl - fee
        cash_delta = max(0.0, settlement) - settlement if action == "CLOSE" else 0.0
        orders.append(
            OrderIntent(
                asset=asset,
                symbol=spec.symbol,
                action=action,
                side=side,
                size=size,
                price=price,
                notional=size * price,
                reduce_only=True,
                reason=(
                    "not in target book" if action == "CLOSE" else "rebalance to target"
                ),
                pos_side=current_side,
            )
        )
        _register_trade(
            asset=asset,
            price=price,
            size_delta=-size,
            margin_delta=margin_delta,
            fee=fee,
            pnl=pnl,
        )
        if action == "CLOSE":
            final_sides[asset] = None
        if action == "CLOSE" and cash_delta:
            available += cash_delta

    # Open or increase only after reductions have settled.  A flip is already
    # represented as CLOSE then OPEN, never as a negative-size order.
    for asset, target_signed in desired_signed.items():
        price = prices_all.get(asset)
        if price is None or price <= 0.0:
            continue
        target_side = "long" if target_signed > 0.0 else "short"
        current_side = final_sides.get(asset)
        current_size = final_sizes.get(asset, 0.0) if current_side == target_side else 0.0
        target_size = abs(target_signed) / price
        if target_size - current_size <= _EPS:
            continue
        action = "OPEN" if current_size <= _EPS else "INCREASE"
        raw_size = target_size - current_size
        spec = _spec(asset)
        size = raw_size if mirror_engine else spec.round_down_qty(raw_size)
        if not mirror_engine:
            if size <= 0.0:
                continue
            if not spec.is_tradeable(size, price, floor_usdt=min_rebalance_usdt):
                warnings.append(
                    f"{asset}: {action.lower()} of {size:.8g} below venue minimum "
                    f"({size * price:.2f} USDT); skipped"
                )
                continue
        notional = size * price
        side_margin_ratio = margin_ratio_for_side(target_side)
        margin_needed = notional * side_margin_ratio
        fee = notional * taker_fee_rate
        if margin_needed + fee > available + _EPS:
            allowed = max(0.0, available)
            if allowed <= 0.0:
                warnings.append(f"{asset}: no available margin; {action.lower()} skipped")
                continue
            shrink = allowed / (margin_needed + fee)
            raw_size *= shrink
            size = raw_size if mirror_engine else spec.round_down_qty(raw_size)
            if size <= 0.0:
                warnings.append(f"{asset}: no available margin; {action.lower()} skipped")
                continue
            warnings.append(
                f"{asset}: {action.lower()} scaled to {size:.8g} by available margin"
            )
            notional = size * price
            margin_needed = notional * side_margin_ratio
            fee = notional * taker_fee_rate
        stop_loss: float | None = None
        if target_side == "short" and short_stop_loss_pct is not None:
            existing = positions.get(asset)
            existing_size = (
                existing.size
                if existing is not None and _side(existing) == "short"
                else 0.0
            )
            existing_entry = existing.entry_price if existing_size > 0.0 else 0.0
            projected_size = existing_size + size
            projected_entry = (
                (existing_size * existing_entry + size * price) / projected_size
                if projected_size > _EPS
                else price
            )
            stop_loss = spec.round_up_price(
                projected_entry * (1.0 + float(short_stop_loss_pct))
            )
        orders.append(
            OrderIntent(
                asset=asset,
                symbol=spec.symbol,
                action=action,
                side="buy" if target_side == "long" else "sell",
                size=size,
                price=price,
                notional=notional,
                reduce_only=False,
                reason="rebalance to target",
                pos_side=target_side,
                stop_loss=stop_loss,
            )
        )
        _register_trade(
            asset=asset,
            price=price,
            size_delta=size,
            margin_delta=-(margin_needed + fee),
            fee=0.0,
            pnl=0.0,
        )
        final_sides[asset] = target_side

    # Isolated-margin top-ups: the exchange posts notional / leverage, while
    # the track wants the side-specific buffer (51.5% by default for both sides).
    margin_intents: list[MarginIntent] = []
    expected_gross = 0.0
    expected_margin = 0.0
    for asset, target_signed in desired_signed.items():
        price = float(prices_all.get(asset, 0.0))
        if price <= 0.0:
            continue
        final_size = final_sizes.get(asset, 0.0)
        final_notional = final_size * price
        if final_notional <= _EPS:
            continue
        target_side = "long" if target_signed > 0.0 else "short"
        side_margin_ratio = margin_ratio_for_side(target_side)
        target_margin = final_notional * side_margin_ratio
        position = positions.get(asset)
        position_side = _side(position) if position is not None else None
        if position is None or position_side != target_side:
            projected_margin = final_notional * exchange_margin_ratio
        else:
            increase = max(0.0, final_notional - position.notional)
            decrease = max(0.0, position.notional - final_notional)
            projected_margin = (
                position.margin
                + increase * exchange_margin_ratio
                - decrease * position.margin_ratio
            )
        delta = target_margin - projected_margin
        expected_gross += final_notional
        expected_margin += target_margin
        if abs(delta) <= min_margin_delta:
            continue
        margin_intents.append(
            MarginIntent(
                asset=asset,
                symbol=specs[asset].symbol if asset in specs else str(asset).upper(),
                pos_side=target_side,
                operation="add" if delta > 0.0 else "remove",
                amount=abs(delta),
                reason=(
                    f"isolated margin to {side_margin_ratio:.1%} of "
                    f"{final_notional:,.2f} USDT notional"
                ),
            )
        )

    return ExecutionPlan(
        equity=float(account.equity),
        leverage=float(leverage),
        target_margin_ratio=float(max(long_margin_ratio, short_margin_ratio)),
        orders=orders,
        margin_intents=margin_intents,
        warnings=warnings,
        target_notional={asset: float(value) for asset, value in desired_abs.items()},
        expected_gross_notional=float(expected_gross),
        expected_margin=float(expected_margin),
        signed_target_notional={asset: float(value) for asset, value in desired_signed.items()},
    )


__all__ = [
    "AccountState",
    "ContractSpec",
    "ExecutionPlan",
    "MarginIntent",
    "OrderIntent",
    "PositionState",
    "build_execution_plan",
]
