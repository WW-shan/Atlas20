from __future__ import annotations

import pytest

from atlas20.derivatives.execution import (
    AccountState,
    ContractSpec,
    PositionState,
    build_execution_plan,
)

DEFAULT_MARGIN = 0.515


def _spec(symbol: str = "NEARUSDT", **kwargs) -> ContractSpec:
    payload = {
        "min_order_qty": 1.0,
        "quantity_multiplier": 1.0,
        "min_order_usdt": 5.0,
        "quantity_precision": 0,
        "price_multiplier": 0.01,
        "price_precision": 2,
    }
    payload.update(kwargs)
    return ContractSpec(symbol=symbol, **payload)


def _position(asset: str = "near", *, size: float, entry: float, mark: float, margin: float) -> PositionState:
    return PositionState(
        asset=asset,
        symbol=f"{asset.upper()}USDT",
        side="long",
        size=size,
        entry_price=entry,
        mark_price=mark,
        margin=margin,
    )


def test_empty_account_opens_the_target_sized_from_live_equity() -> None:
    plan = build_execution_plan(
        AccountState(equity=500.0, available_margin=500.0),
        {"near": 1.25 * 0.4},
        {"near": _spec()},
        {"near": 2.0},
    )

    assert len(plan.orders) == 1
    order = plan.orders[0]
    assert order.action == "OPEN"
    assert order.size == 125.0  # 0.5 weight x 500 equity / 2.0 price
    assert plan.expected_gross_notional == pytest.approx(250.0)
    assert plan.expected_margin == pytest.approx(250.0 * DEFAULT_MARGIN)


def test_dynamic_balance_halves_the_order_when_equity_halves() -> None:
    spec, price = {"near": _spec()}, {"near": 2.0}
    rich = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0), {"near": 0.5}, spec, price
    )
    poor = build_execution_plan(
        AccountState(equity=500.0, available_margin=500.0), {"near": 0.5}, spec, price
    )

    assert rich.orders[0].size == pytest.approx(2.0 * poor.orders[0].size)


def test_quantity_is_floored_to_the_contract_step() -> None:
    plan = build_execution_plan(
        AccountState(equity=100.0, available_margin=100.0),
        {"doge": 0.5},
        {"doge": _spec("DOGEUSDT", quantity_multiplier=10.0, min_order_qty=10.0, quantity_precision=0)},
        {"doge": 0.1234},
    )

    order = plan.orders[0]
    assert order.size % 10.0 == 0.0
    assert order.size * 0.1234 <= 100.0 * 0.5


def test_order_below_venue_minimum_is_skipped_with_a_warning() -> None:
    plan = build_execution_plan(
        AccountState(equity=100.0, available_margin=100.0),
        {"near": 0.02},
        {"near": _spec(min_order_usdt=50.0)},
        {"near": 2.0},
    )

    assert plan.orders == []
    assert any("below venue minimum" in warning for warning in plan.warnings)


def test_reduce_below_venue_minimum_keeps_the_position() -> None:
    position = _position(size=100.0, entry=2.0, mark=2.0, margin=100.0 * 2.0 * DEFAULT_MARGIN)
    plan = build_execution_plan(
        AccountState(equity=200.0, available_margin=0.0, positions={"near": position}),
        {"near": 0.999},
        {"near": _spec(min_order_usdt=5.0)},
        {"near": 2.0},
    )

    assert plan.orders == []
    assert any("kept for now" in warning for warning in plan.warnings)


def test_drift_position_outside_the_target_book_is_closed() -> None:
    position = _position("cardano", size=100.0, entry=0.5, mark=0.6, margin=100.0 * 0.6 * DEFAULT_MARGIN)
    plan = build_execution_plan(
        AccountState(equity=200.0, available_margin=0.0, positions={"cardano": position}),
        {"near": 0.5},
        {"near": _spec(), "cardano": _spec("ADAUSDT")},
        {"near": 2.0, "cardano": 0.6},
    )

    close = next(order for order in plan.orders if order.asset == "cardano")
    assert close.action == "CLOSE"
    assert close.side == "sell"
    assert close.reduce_only is True


def test_manual_close_is_reopened_by_the_next_plan() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": 0.6},
        {"near": _spec()},
        {"near": 2.0},
    )

    assert [order.action for order in plan.orders] == ["OPEN"]


def test_missing_price_drops_the_target_and_warns() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": 0.6, "sol": 0.4},
        {"near": _spec(), "sol": _spec("SOLUSDT")},
        {"near": 2.0},
    )

    assert [order.asset for order in plan.orders] == ["near"]
    assert any("sol" in warning and "no usable price" in warning for warning in plan.warnings)


def test_missing_contract_spec_drops_the_target_and_warns() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": 0.6},
        {},
        {"near": 2.0},
    )

    assert plan.orders == []
    assert any("no contract spec" in warning for warning in plan.warnings)


def test_margin_intent_tops_up_to_51_5_percent_of_notional() -> None:
    # A 2x isolated position posts 50%; the spec wants 51.5%.
    position = _position(size=500.0, entry=2.0, mark=2.0, margin=1000.0 * 0.50)
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=100.0, positions={"near": position}),
        {"near": 1.0},
        {"near": _spec()},
        {"near": 2.0},
    )

    assert plan.orders == []  # already at target size
    intent = next(item for item in plan.margin_intents if item.asset == "near")
    assert intent.operation == "add"
    assert intent.amount == pytest.approx(1000.0 * (0.515 - 0.50))


def test_margin_intent_removes_excess_margin_after_a_reduce() -> None:
    # Over-margined leg: 60% posted, target notional cuts the leg by a third.
    position = _position(size=300.0, entry=2.0, mark=2.0, margin=600.0 * 0.60)
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=0.0, positions={"near": position}),
        {"near": 0.4},
        {"near": _spec()},
        {"near": 2.0},
    )

    reduce = next(order for order in plan.orders if order.action == "REDUCE")
    assert reduce.size == pytest.approx(300.0 - 1000.0 * 0.4 / 2.0)
    intent = next(item for item in plan.margin_intents if item.asset == "near")
    assert intent.operation == "remove"
    # 400 USDT final notional wants 206 of margin; the reduce releases
    # margin proportionally, leaving 240.
    assert intent.amount == pytest.approx(240.0 - 400.0 * 0.515)


def test_available_margin_shrinks_an_open_instead_of_failing() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=60.0),
        {"near": 1.0},
        {"near": _spec()},
        {"near": 2.0},
    )

    order = plan.orders[0]
    assert order.notional <= 60.0 / (DEFAULT_MARGIN + 0.0006) + 2.0
    assert order.notional >= 100.0
    assert any("scaled" in warning for warning in plan.warnings)


def test_no_available_margin_skips_the_open() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=0.0),
        {"near": 1.0},
        {"near": _spec()},
        {"near": 2.0},
    )

    assert plan.orders == []
    assert any("no available margin" in warning for warning in plan.warnings)


def test_margin_utilization_cap_scales_the_whole_book() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": 1.25},
        {"near": _spec()},
        {"near": 2.0},
        leverage=2.0,
        max_margin_utilization=0.60,
    )

    capped = 0.60 * 1000.0 / DEFAULT_MARGIN
    # Flooring to the quantity step can only pull the book slightly below the cap.
    assert capped - 2.0 <= plan.expected_gross_notional <= capped + 1e-9
    assert any("margin-utilization cap" in warning for warning in plan.warnings)


def test_all_cash_target_closes_every_leg() -> None:
    positions = {
        "near": _position(size=100.0, entry=2.0, mark=2.0, margin=103.0),
        "sol": _position("sol", size=10.0, entry=100.0, mark=90.0, margin=515.0),
    }
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=100.0, positions=positions),
        {},
        {"near": _spec(), "sol": _spec("SOLUSDT")},
        {"near": 2.0, "sol": 90.0},
    )

    assert {order.action for order in plan.orders} == {"CLOSE"}
    assert len(plan.orders) == 2


def test_zero_equity_suppresses_new_targets_and_closes_the_held_leg() -> None:
    position = _position(size=100.0, entry=2.0, mark=2.0, margin=100.0)
    plan = build_execution_plan(
        AccountState(equity=0.0, available_margin=0.0, positions={"near": position}),
        {"near": 0.5},
        {"near": _spec()},
        {"near": 2.0},
    )

    assert [(order.action, order.reduce_only) for order in plan.orders] == [("CLOSE", True)]
    assert plan.signed_target_notional == {}
    assert any("risk-reducing" in warning.lower() for warning in plan.warnings)


def test_non_finite_equity_is_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        build_execution_plan(
            AccountState(equity=float("nan"), available_margin=0.0), {}, {}, {}
        )


def test_non_finite_available_margin_is_rejected() -> None:
    with pytest.raises(ValueError, match="available margin"):
        build_execution_plan(
            AccountState(equity=100.0, available_margin=float("nan")), {}, {}, {}
        )


def test_non_finite_leverage_is_rejected() -> None:
    with pytest.raises(ValueError, match="leverage"):
        build_execution_plan(
            AccountState(equity=100.0, available_margin=100.0),
            {},
            {},
            {},
            leverage=float("nan"),
        )


def test_non_finite_max_gross_exposure_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_gross_exposure"):
        build_execution_plan(
            AccountState(equity=100.0, available_margin=100.0),
            {},
            {},
            {},
            max_gross_exposure=float("nan"),
        )


def test_negative_fee_and_minimum_rebalance_are_rejected() -> None:
    with pytest.raises(ValueError, match="taker_fee_rate"):
        build_execution_plan(
            AccountState(equity=100.0, available_margin=100.0),
            {},
            {},
            {},
            taker_fee_rate=-0.001,
        )
    with pytest.raises(ValueError, match="min_rebalance_usdt"):
        build_execution_plan(
            AccountState(equity=100.0, available_margin=100.0),
            {},
            {},
            {},
            min_rebalance_usdt=-1.0,
        )


def test_mirror_engine_reproduces_an_engine_style_rebalance() -> None:
    # Engine-style state: 1.0 equity, one leg at 0.5 weight, price 2.0.
    position = _position(size=0.5, entry=2.0, mark=2.0, margin=1.0 * DEFAULT_MARGIN)
    plan = build_execution_plan(
        AccountState(equity=1.0, available_margin=1.0 - position.margin, positions={"near": position}),
        {"near": 0.25},
        {},
        {"near": 2.0},
        mirror_engine=True,
    )

    reduce = plan.orders[0]
    assert reduce.action == "REDUCE"
    assert reduce.size == pytest.approx(0.5 - 0.25 * 1.0 / 2.0)


def _short_position(
    asset: str = "near",
    *,
    size: float,
    entry: float,
    mark: float,
    margin: float,
) -> PositionState:
    return PositionState(
        asset=asset,
        symbol=f"{asset.upper()}USDT",
        side="short",
        size=size,
        entry_price=entry,
        mark_price=mark,
        margin=margin,
    )


def test_empty_account_opens_a_signed_short_with_short_side() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": -0.25},
        {"near": _spec()},
        {"near": 2.0},
    )

    assert len(plan.orders) == 1
    order = plan.orders[0]
    assert order.action == "OPEN"
    assert order.side == "sell"
    assert order.pos_side == "short"
    assert order.size == 125.0
    assert plan.signed_target_notional["near"] == pytest.approx(-250.0)
    assert plan.target_notional["near"] == pytest.approx(250.0)
    assert plan.expected_gross_notional == pytest.approx(250.0)


def test_all_cash_target_closes_a_short_with_a_buy_and_short_position_side() -> None:
    position = _short_position(size=100.0, entry=2.0, mark=2.0, margin=103.0)
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=100.0, positions={"near": position}),
        {},
        {"near": _spec()},
        {"near": 2.0},
    )

    assert len(plan.orders) == 1
    order = plan.orders[0]
    assert order.action == "CLOSE"
    assert order.side == "buy"
    assert order.pos_side == "short"
    assert order.size == 100.0
    assert order.reduce_only is True


def test_long_to_short_flip_closes_then_opens_the_opposite_side() -> None:
    position = _position(size=100.0, entry=2.0, mark=2.0, margin=103.0)
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=100.0, positions={"near": position}),
        {"near": -0.2},
        {"near": _spec()},
        {"near": 2.0},
    )

    assert [(order.action, order.side, order.pos_side) for order in plan.orders] == [
        ("CLOSE", "sell", "long"),
        ("OPEN", "sell", "short"),
    ]
    assert [order.size for order in plan.orders] == [100.0, 100.0]
    assert plan.signed_target_notional["near"] == pytest.approx(-200.0)


def test_short_open_carries_the_configured_mark_price_stop() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": -0.25},
        {"near": _spec()},
        {"near": 2.0},
        short_stop_loss_pct=0.20,
    )

    order = plan.orders[0]
    assert order.stop_loss == pytest.approx(2.40)
    assert order.as_dict()["stop_loss"] == pytest.approx(2.40)


def test_short_stop_price_is_rounded_up_to_the_instrument_tick() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": -0.25},
        {"near": _spec()},
        {"near": 2.01},
        short_stop_loss_pct=0.20,
    )

    assert plan.orders[0].stop_loss == pytest.approx(2.42)


def test_short_increase_stop_tracks_weighted_entry_price() -> None:
    position = _short_position(size=50.0, entry=1.8, mark=2.0, margin=51.5)
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0, positions={"near": position}),
        {"near": -0.25},
        {"near": _spec()},
        {"near": 2.0},
        short_stop_loss_pct=0.20,
    )

    order = next(item for item in plan.orders if item.action == "INCREASE")
    expected_entry = (50.0 * 1.8 + 75.0 * 2.0) / 125.0
    assert order.stop_loss == pytest.approx(2.31)
    assert order.stop_loss >= expected_entry * 1.20


def test_short_close_does_not_submit_a_new_stop() -> None:
    position = _short_position(size=100.0, entry=2.0, mark=2.0, margin=103.0)
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=100.0, positions={"near": position}),
        {},
        {"near": _spec()},
        {"near": 2.0},
        short_stop_loss_pct=0.20,
    )

    assert plan.orders[0].action == "CLOSE"
    assert plan.orders[0].stop_loss is None


def test_short_stop_loss_rejects_invalid_percentage() -> None:
    with pytest.raises(ValueError, match="short_stop_loss_pct"):
        build_execution_plan(
            AccountState(equity=1000.0, available_margin=1000.0),
            {"near": -0.25},
            {"near": _spec()},
            {"near": 2.0},
            short_stop_loss_pct=1.0,
        )


def test_max_gross_exposure_scales_signed_long_short_book() -> None:
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=1000.0),
        {"near": -0.8, "sol": 0.8},
        {"near": _spec(), "sol": _spec("SOLUSDT")},
        {"near": 2.0, "sol": 20.0},
        leverage=2.0,
        max_margin_utilization=1.0,
        max_gross_exposure=1250.0,
    )

    assert plan.expected_gross_notional <= 1250.0 + 1e-9
    assert plan.expected_gross_notional >= 1240.0
    assert any("gross" in warning.lower() for warning in plan.warnings)


def test_short_margin_intent_uses_short_position_side() -> None:
    position = _short_position(size=500.0, entry=2.0, mark=2.0, margin=1000.0 * 0.50)
    plan = build_execution_plan(
        AccountState(equity=1000.0, available_margin=100.0, positions={"near": position}),
        {"near": -1.0},
        {"near": _spec()},
        {"near": 2.0},
    )

    intent = next(item for item in plan.margin_intents if item.asset == "near")
    assert intent.pos_side == "short"
    assert intent.operation == "add"
    assert intent.amount == pytest.approx(1000.0 * (0.515 - 0.50))
