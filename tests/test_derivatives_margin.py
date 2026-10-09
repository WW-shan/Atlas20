from __future__ import annotations

import pytest

from atlas20.derivatives.margin import (
    initial_margin_ratio,
    liquidation_distance,
    liquidation_price,
)


def test_long_liquidation_price_matches_isolated_margin_formula() -> None:
    price = liquidation_price(
        side="long",
        entry_price=100.0,
        margin_ratio=0.31,
        maintenance_margin_rate=0.01,
    )

    assert price == pytest.approx(100.0 * (1.0 - 0.31) / (1.0 - 0.01))
    assert price < 100.0


def test_short_liquidation_price_matches_isolated_margin_formula() -> None:
    price = liquidation_price(
        side="short",
        entry_price=100.0,
        margin_ratio=0.51,
        maintenance_margin_rate=0.01,
    )

    assert price == pytest.approx(100.0 * (1.0 + 0.51) / (1.0 + 0.01))
    assert price > 100.0


def test_liquidation_distance_is_adverse_move_to_liquidation() -> None:
    assert liquidation_distance(
        side="long",
        entry_price=100.0,
        margin_ratio=0.31,
        maintenance_margin_rate=0.01,
    ) == pytest.approx(1.0 - (0.69 / 0.99))
    assert liquidation_distance(
        side="short",
        entry_price=100.0,
        margin_ratio=0.51,
        maintenance_margin_rate=0.01,
    ) == pytest.approx((1.51 / 1.01) - 1.0)


def test_initial_margin_ratio_uses_side_specific_buffers_and_floor() -> None:
    assert initial_margin_ratio("long", maintenance_margin_rate=0.01, fee_buffer=0.005) == pytest.approx(0.315)
    assert initial_margin_ratio("short", maintenance_margin_rate=0.01, fee_buffer=0.005) == pytest.approx(0.515)


def test_liquidation_price_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="side"):
        liquidation_price(side="flat", entry_price=100.0, margin_ratio=0.3, maintenance_margin_rate=0.01)
    with pytest.raises(ValueError, match="entry_price"):
        liquidation_price(side="long", entry_price=0.0, margin_ratio=0.3, maintenance_margin_rate=0.01)
    with pytest.raises(ValueError, match="margin_ratio"):
        liquidation_price(side="long", entry_price=100.0, margin_ratio=1.0, maintenance_margin_rate=0.01)
    with pytest.raises(ValueError, match="maintenance_margin_rate"):
        liquidation_price(side="long", entry_price=100.0, margin_ratio=0.3, maintenance_margin_rate=1.0)
