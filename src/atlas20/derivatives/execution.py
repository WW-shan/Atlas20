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
        return cls(
            symbol=str(row.get("symbol", "")),
            min_order_qty=_float("minOrderQty"),
            quantity_multiplier=_float("quantityMultiplier"),
            min_order_usdt=_float("minOrderAmount"),
            quantity_precision=precision,
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "equity": self.equity,
            "leverage": self.leverage,
            "target_margin_ratio": self.target_margin_ratio,
            "orders": [order.as_dict() for order in self.orders],
            "margin_intents": [intent.as_dict() for intent in self.margin_intents],
            "warnings": list(self.warnings),
            "target_notional": dict(self.target_notional),
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
    fee_buffer: float = 0.005,
    maintenance_margin_rate: float = 0.01,
    max_margin_utilization: float = 0.85,
    taker_fee_rate: float = 0.0006,
    min_rebalance_usdt: float = 0.0,
    min_margin_delta: float = 0.01,
    mirror_engine: bool = False,
) -> ExecutionPlan:
    """Build the orders and margin adjustments that move the account to target.

    ``mirror_engine=True`` reproduces the research engine's exact behaviour
    (no venue minimums, no rounding floor beyond the step) and is what the
    replay harness compares against the historical trade ledger.
    """

    if account.equity <= 0.0:
        raise ValueError("account equity must be positive")
    if leverage <= 0.0:
        raise ValueError("leverage must be positive")

    warnings: list[str] = []
    margin_ratio = initial_margin_ratio(
        "long",
        maintenance_margin_rate=maintenance_margin_rate,
        fee_buffer=fee_buffer,
        long_buffer=long_buffer,
    )
    exchange_margin_ratio = 1.0 / leverage

    desired: dict[str, float] = {}
    for asset, weight in targets.items():
        weight = float(weight)
        if abs(weight) <= _EPS:
            continue
        if asset not in prices or not (float(prices[asset]) > 0.0):
            warnings.append(f"{asset}: no usable price; target dropped")
            continue
        if asset not in specs and not mirror_engine:
            warnings.append(f"{asset}: no contract spec; target dropped")
            continue
        desired[str(asset)] = abs(weight) * account.equity

    required_margin = sum(notional * margin_ratio for notional in desired.values())
    scale = 1.0
    if required_margin > max_margin_utilization * account.equity:
        scale = (max_margin_utilization * account.equity) / required_margin
        warnings.append(
            f"gross margin scaled to {scale:.4f}x by the {max_margin_utilization:.0%} "
            "margin-utilization cap"
        )
    desired = {asset: notional * scale for asset, notional in desired.items()}

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

    orders: list[OrderIntent] = []
    available = float(account.available_margin)
    final_sizes: dict[str, float] = {
        asset: position.size for asset, position in positions.items()
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

    # Reduce / close first so the released margin can fund increases.  The
    # iteration order mirrors the engine: positions in open order.
    for asset in positions:
        position = positions[asset]
        price = prices_all.get(asset)
        if price is None or price <= 0.0:
            warnings.append(f"{asset}: held leg has no price; left untouched")
            continue
        target_notional = desired.get(asset)
        if target_notional is None or target_notional <= _EPS:
            action, size = "CLOSE", position.size
            reason = "not in target book"
        elif target_notional / price < position.size - 1e-12:
            # Quantity-space comparison, exactly like the research engine.
            size = position.size - target_notional / price
            action, reason = "REDUCE", "rebalance to target"
        else:
            continue
        cash_delta = 0.0
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
            if action == "REDUCE" and size <= 0.0:
                continue
        if action == "CLOSE":
            margin_delta = position.margin
            pnl = position.size * (price - position.entry_price)
            fee = position.size * price * taker_fee_rate
            # Mirror the engine: a blown-up leg settles at zero, not negative.
            cash_delta = max(0.0, margin_delta + pnl - fee) - (margin_delta + pnl - fee)
        else:
            fraction = size / position.size if position.size > 0.0 else 0.0
            margin_delta = position.margin * fraction
            pnl = size * (price - position.entry_price)
            fee = size * price * taker_fee_rate
        orders.append(
            OrderIntent(
                asset=asset,
                symbol=position.symbol,
                action=action,
                side="sell",
                size=size,
                price=price,
                notional=size * price,
                reduce_only=True,
                reason=reason,
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
        if action == "CLOSE" and cash_delta:
            available += cash_delta

    # Open or increase only after reductions have settled.
    for asset, target_notional in desired.items():
        price = prices_all.get(asset)
        if price is None or price <= 0.0:
            continue
        position = positions.get(asset)
        current_notional = position.size * price if position is not None else 0.0
        if target_notional - current_notional <= _EPS:
            continue
        action = "OPEN" if position is None else "INCREASE"
        raw_size = (target_notional - current_notional) / price
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
        margin_needed = notional * margin_ratio
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
            margin_needed = notional * margin_ratio
            fee = notional * taker_fee_rate
        orders.append(
            OrderIntent(
                asset=asset,
                symbol=spec.symbol,
                action=action,
                side="buy",
                size=size,
                price=price,
                notional=notional,
                reduce_only=False,
                reason="rebalance to target",
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

    # Isolated-margin top-ups: the exchange only posts notional / leverage, the
    # specification wants notional x 51.5% (50% buffer + 1% MMR + 0.5% fees).
    margin_intents: list[MarginIntent] = []
    expected_gross = 0.0
    expected_margin = 0.0
    for asset, target_notional in desired.items():
        price = float(prices_all.get(asset, 0.0))
        if price <= 0.0:
            continue
        final_size = final_sizes.get(asset, 0.0)
        final_notional = final_size * price
        if final_notional <= _EPS:
            continue
        position = positions.get(asset)
        target_margin = final_notional * margin_ratio
        if position is None:
            projected_margin = final_notional * exchange_margin_ratio
        else:
            increase = max(0.0, final_notional - position.notional)
            decrease = max(0.0, position.notional - final_notional)
            projected_margin = (
                position.margin + increase * exchange_margin_ratio - decrease * position.margin_ratio
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
                pos_side="long",
                operation="add" if delta > 0.0 else "remove",
                amount=abs(delta),
                reason=(
                    f"isolated margin to {margin_ratio:.1%} of "
                    f"{final_notional:,.2f} USDT notional"
                ),
            )
        )

    return ExecutionPlan(
        equity=float(account.equity),
        leverage=float(leverage),
        target_margin_ratio=float(margin_ratio),
        orders=orders,
        margin_intents=margin_intents,
        warnings=warnings,
        target_notional={asset: float(value) for asset, value in desired.items()},
        expected_gross_notional=float(expected_gross),
        expected_margin=float(expected_margin),
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
