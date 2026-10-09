"""Isolated-margin liquidation math for the Bitget derivatives research track.

The formulas here are deliberately small and side-explicit.  They are the
single source of truth for both the event engine and the audit reports, so a
change to the liquidation convention cannot silently diverge between a
backtest and a live risk calculation.
"""

from __future__ import annotations

from typing import Literal

Side = Literal["long", "short"]


def _validate_side(side: str) -> Side:
    if side not in {"long", "short"}:
        raise ValueError("side must be 'long' or 'short'")
    return side  # type: ignore[return-value]


def _validate_price_and_rates(
    *,
    entry_price: float,
    margin_ratio: float,
    maintenance_margin_rate: float,
) -> None:
    if not entry_price > 0.0:
        raise ValueError("entry_price must be positive")
    if not 0.0 < margin_ratio < 1.0:
        raise ValueError("margin_ratio must be in (0, 1)")
    if not 0.0 <= maintenance_margin_rate < 1.0:
        raise ValueError("maintenance_margin_rate must be in [0, 1)")


def initial_margin_ratio(
    side: str,
    *,
    maintenance_margin_rate: float,
    fee_buffer: float = 0.005,
    long_buffer: float = 0.30,
    short_buffer: float = 0.50,
) -> float:
    """Return the isolated-margin fraction implied by the project design.

    The larger of the side-specific target liquidation distance and the
    configured floor is used.  ``fee_buffer`` is deliberately part of the
    initial margin rather than a separate cash bucket: it is what makes the
    theoretical liquidation price conservative enough for mark-price jumps,
    liquidation fees and ADL.
    """
    side = _validate_side(side)
    if not 0.0 <= maintenance_margin_rate < 1.0:
        raise ValueError("maintenance_margin_rate must be in [0, 1)")
    if fee_buffer < 0.0:
        raise ValueError("fee_buffer must be non-negative")
    if not 0.0 < long_buffer < 1.0:
        raise ValueError("long_buffer must be in (0, 1)")
    if not 0.0 < short_buffer < 1.0:
        raise ValueError("short_buffer must be in (0, 1)")
    target = long_buffer if side == "long" else short_buffer
    return max(target + maintenance_margin_rate + fee_buffer, target)


def liquidation_price(
    *,
    side: str,
    entry_price: float,
    margin_ratio: float,
    maintenance_margin_rate: float,
) -> float:
    """Return the mark price at which an isolated position hits maintenance.

    ``margin_ratio`` is isolated margin divided by entry notional.  The
    formulas assume no funding PnL; callers that have already applied funding
    should update the effective margin ratio before calling this helper.
    """
    side = _validate_side(side)
    _validate_price_and_rates(
        entry_price=entry_price,
        margin_ratio=margin_ratio,
        maintenance_margin_rate=maintenance_margin_rate,
    )
    if side == "long":
        return entry_price * (1.0 - margin_ratio) / (1.0 - maintenance_margin_rate)
    return entry_price * (1.0 + margin_ratio) / (1.0 + maintenance_margin_rate)


def liquidation_distance(
    *,
    side: str,
    entry_price: float,
    margin_ratio: float,
    maintenance_margin_rate: float,
) -> float:
    """Return the adverse fractional move from entry to liquidation."""
    side = _validate_side(side)
    price = liquidation_price(
        side=side,
        entry_price=entry_price,
        margin_ratio=margin_ratio,
        maintenance_margin_rate=maintenance_margin_rate,
    )
    if side == "long":
        return 1.0 - price / entry_price
    return price / entry_price - 1.0


__all__ = [
    "Side",
    "initial_margin_ratio",
    "liquidation_distance",
    "liquidation_price",
]
