from __future__ import annotations

from typing import Any

import pytest

from atlas20.derivatives.bitget import BitgetAPIError
from atlas20.derivatives.execution import (
    AccountState,
    ContractSpec,
    ExecutionPlan,
    OrderIntent,
    PositionState,
    build_execution_plan,
)
from atlas20.derivatives.live_executor import (
    ExecutionReport,
    OrderFill,
    execute_plan,
    format_execution_report,
    is_isolated_unsupported,
    wait_for_fill,
)


def _spec(symbol: str = "NEARUSDT", **kwargs: Any) -> ContractSpec:
    payload = {
        "min_order_qty": 1.0,
        "quantity_multiplier": 1.0,
        "min_order_usdt": 5.0,
        "quantity_precision": 0,
    }
    payload.update(kwargs)
    return ContractSpec(symbol=symbol, **payload)


def _plan(*, equity: float = 100.0, weight: float = 0.6, price: float = 5.0, position: PositionState | None = None):
    account = AccountState(
        equity=equity,
        available_margin=equity,
        positions={} if position is None else {position.asset: position},
    )
    return build_execution_plan(
        account,
        {"near": weight},
        {"near": _spec()},
        {"near": price},
    )


class _FakeLiveClient:
    """Records calls and replays canned venue answers."""

    def __init__(
        self,
        *,
        hold_mode: str = "hedge_mode",
        assets: dict[str, Any] | None = None,
        positions: list[dict[str, Any]] | None = None,
        order_infos: dict[str, dict[str, Any]] | None = None,
        reject_isolated_orders: bool = True,
        reject_isolated_leverage: bool = False,
        crossed_leverage_error: str | None = None,
        margin_error: str | None = None,
        place_error: str | None = None,
        echo_stop_loss: bool = True,
        stop_loss_override: float | None = None,
        stop_trigger_by_override: str | None = None,
        stop_order_type_override: str | None = None,
        unfilled: list[dict[str, Any]] | None = None,
        cancel_error: str | None = None,
        strategy_orders: list[dict[str, Any]] | None = None,
        order_history_rows: list[dict[str, Any]] | None = None,
        account_info_value: dict[str, Any] | None = None,
    ) -> None:
        self.hold_mode_value = hold_mode
        self.assets = assets or {
            "usdtEquity": "100",
            "assets": [{"coin": "USDT", "available": "25.0", "balance": "100"}],
        }
        self.positions = positions or []
        self.order_infos = order_infos or {}
        self.reject_isolated_orders = reject_isolated_orders
        self.reject_isolated_leverage = reject_isolated_leverage
        self.crossed_leverage_error = crossed_leverage_error
        self.margin_error = margin_error
        self.place_error = place_error
        self.echo_stop_loss = echo_stop_loss
        self.stop_loss_override = stop_loss_override
        self.stop_trigger_by_override = stop_trigger_by_override
        self.stop_order_type_override = stop_order_type_override
        self.pending_orders = list(unfilled or [])
        self.cancel_error = cancel_error
        self.strategy_orders = list(strategy_orders or [])
        self.order_history_rows = list(order_history_rows or [])
        self.account_info_value = account_info_value or {
            "permType": "read_and_write",
            "permissions": ["uta_trade", "uta_mgt"],
            "traderType": "user",
        }
        self.placed: list[dict[str, Any]] = []
        self.cancelled: list[dict[str, Any]] = []
        self.symbol_configs: dict[tuple[str, str], dict[str, Any]] = {}
        self.leverage_calls: list[dict[str, Any]] = []
        self.margin_calls: list[dict[str, Any]] = []
        self._next_id = 1000

    # -- protocol -----------------------------------------------------
    def account_assets(self) -> dict[str, Any]:
        return self.assets

    def account_info(self) -> dict[str, Any]:
        return dict(self.account_info_value)

    def current_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list(self.positions)

    def hold_mode(self) -> str:
        return self.hold_mode_value

    def account_settings(self) -> dict[str, Any]:
        return {
            "holdMode": self.hold_mode_value,
            "symbolConfigList": [dict(row) for row in self.symbol_configs.values()],
        }

    def set_leverage(self, symbol: str, leverage: float, **kwargs: Any) -> Any:
        self.leverage_calls.append({"symbol": symbol, "leverage": leverage, **kwargs})
        if kwargs.get("margin_mode") == "crossed" and self.crossed_leverage_error:
            raise BitgetAPIError(self.crossed_leverage_error)
        if kwargs.get("margin_mode") == "isolated" and self.reject_isolated_leverage:
            raise BitgetAPIError("Bitget set-leverage HTTP 400: 25200 fixedMargin not support")
        mode = str(kwargs.get("margin_mode") or "crossed")
        self.symbol_configs[(symbol, mode)] = {
            "category": "USDT-FUTURES",
            "symbol": symbol,
            "marginMode": mode,
            "leverage": str(leverage),
            "longLeverage": str(leverage) if mode == "isolated" else None,
            "shortLeverage": str(leverage) if mode == "isolated" else None,
        }
        return "success"

    def set_margin(self, symbol: str, amount: float, **kwargs: Any) -> Any:
        self.margin_calls.append({"symbol": symbol, "amount": amount, **kwargs})
        if self.margin_error:
            raise BitgetAPIError(self.margin_error)
        return "success"

    def place_order(self, **kwargs: Any) -> dict[str, Any]:
        if self.place_error:
            raise BitgetAPIError(self.place_error)
        if kwargs.get("margin_mode") == "isolated" and self.reject_isolated_orders:
            raise BitgetAPIError(
                "Bitget /api/v3/trade/place-order HTTP 400: "
                '{"code":"25200","msg":"fixedMargin not support  validation error"}'
            )
        self._next_id += 1
        order_id = str(self._next_id)
        self.placed.append({**kwargs, "orderId": order_id})
        self.order_infos.setdefault(
            order_id,
            {
                "orderId": order_id,
                "symbol": kwargs["symbol"],
                "side": kwargs["side"],
                "posSide": str(kwargs.get("pos_side") or ""),
                "orderStatus": "filled",
                "cumExecQty": str(kwargs["qty"]),
                "cumExecValue": str(round(float(kwargs["qty"]) * 5.0, 4)),
                "avgPrice": "5.0",
                "feeDetail": [{"feeCoin": "USDT", "fee": "0.03"}],
                "marginMode": "crossed" if kwargs.get("margin_mode") is None else "isolated",
                "stopLoss": str(
                    self.stop_loss_override
                    if self.stop_loss_override is not None
                    else (kwargs.get("stop_loss") or "")
                )
                if self.echo_stop_loss
                else "",
                "slTriggerBy": self.stop_trigger_by_override
                if self.stop_trigger_by_override is not None
                else str(kwargs.get("sl_trigger_by") or ""),
                "slOrderType": self.stop_order_type_override
                if self.stop_order_type_override is not None
                else str(kwargs.get("sl_order_type") or ""),
            },
        )
        return {"orderId": order_id, "clientOid": kwargs.get("client_oid")}

    def unfilled_orders(self, **kwargs: Any) -> list[dict[str, Any]]:
        symbol = str(kwargs.get("symbol") or "").upper()
        return [
            dict(row)
            for row in self.pending_orders
            if not symbol or str(row.get("symbol") or "").upper() == symbol
        ]

    def unfilled_strategy_orders(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [dict(row) for row in self.strategy_orders]

    def modify_strategy_order(self, **kwargs: Any) -> dict[str, Any]:
        order_id = str(kwargs.get("order_id") or "")
        for row in self.strategy_orders:
            if str(row.get("orderId") or "") != order_id:
                continue
            if kwargs.get("qty") is not None:
                row["qty"] = f"{float(kwargs['qty']):.12g}"
            if kwargs.get("stop_loss") is not None:
                row["stopLoss"] = f"{float(kwargs['stop_loss']):.12g}"
            row["slTriggerBy"] = str(kwargs.get("sl_trigger_by") or row.get("slTriggerBy") or "")
            row["slOrderType"] = str(kwargs.get("sl_order_type") or row.get("slOrderType") or "")
            return {"orderId": order_id}
        raise BitgetAPIError(f"strategy order {order_id} not found")

    def cancel_strategy_order(self, **kwargs: Any) -> dict[str, Any]:
        order_id = str(kwargs.get("order_id") or "")
        for index, row in enumerate(self.strategy_orders):
            if str(row.get("orderId") or "") == order_id:
                self.strategy_orders.pop(index)
                return {"orderId": order_id}
        raise BitgetAPIError(f"strategy order {order_id} not found")

    def order_history(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [dict(row) for row in self.order_history_rows]

    def cancel_order(self, **kwargs: Any) -> dict[str, Any]:
        if self.cancel_error:
            raise BitgetAPIError(self.cancel_error)
        self.cancelled.append(dict(kwargs))
        order_id = str(kwargs.get("order_id") or "")
        for index, row in enumerate(self.pending_orders):
            if str(row.get("orderId") or "") == order_id:
                cancelled = self.pending_orders.pop(index)
                self.order_infos.setdefault(order_id, dict(cancelled))
                break
        if order_id in self.order_infos:
            self.order_infos[order_id]["orderStatus"] = "cancelled"
        return {"orderId": order_id, "status": "cancelled"}

    def order_info(self, **kwargs: Any) -> dict[str, Any]:
        order_id = str(kwargs.get("order_id") or "")
        if order_id:
            return dict(self.order_infos.get(order_id, {}))
        client_oid = str(kwargs.get("client_oid") or "")
        for placed in reversed(self.placed):
            if str(placed.get("client_oid") or "") == client_oid:
                return dict(self.order_infos.get(str(placed["orderId"]), {}))
        return {}


def _run(client: _FakeLiveClient, plan, **kwargs: Any) -> ExecutionReport:
    return execute_plan(
        client,
        plan,
        signal_date="2026-10-08",
        sleep=lambda _: None,
        clock=lambda: 0.0,
        **kwargs,
    )


def test_require_isolated_blocks_an_elite_copy_trader_before_placing_an_open() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        account_info_value={
            "permType": "read_and_write",
            "permissions": [
                "copy_futures_order",
                "copy_futures_position",
                "uta_trade",
                "uta_mgt",
            ],
            "traderType": "trader",
        },
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.4),
        require_isolated=True,
        margin_mode="isolated",
    )

    assert client.placed == []
    assert any("copy-trading/elite" in row["error"] for row in report.failures)


def test_elite_copy_trader_block_does_not_prevent_a_risk_reducing_close() -> None:
    position = PositionState(
        asset="near",
        symbol="NEARUSDT",
        side="long",
        size=20.0,
        entry_price=5.0,
        mark_price=5.0,
        margin=51.5,
    )
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        account_info_value={
            "permType": "read_and_write",
            "permissions": ["copy_futures_order", "uta_trade", "uta_mgt"],
            "traderType": "trader",
        },
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "long",
                "marginMode": "isolated",
                "avgPrice": "5",
                "markPrice": "5",
                "positionBalance": "51.5",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.0, position=position),
        require_isolated=True,
        margin_mode="isolated",
    )

    assert report.failures == []
    assert len(client.placed) == 1
    assert client.placed[0]["side"] == "sell"


def test_execute_plan_reports_the_venue_fill_and_the_real_book() -> None:
    client = _FakeLiveClient(
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "long",
                "marginMode": "crossed",
                "total": "12",
                "avgPrice": "5.0",
                "markPrice": "5.1",
                "positionBalance": "3.0",
            }
        ]
    )
    plan = _plan()

    report = _run(client, plan)

    assert len(client.placed) == 1
    order = client.placed[0]
    assert order["pos_side"] == "long"  # hedge mode
    assert order["reduce_only"] is False
    assert len(report.fills) == 1
    fill = report.fills[0]
    assert fill.filled_size == pytest.approx(12.0)
    assert fill.notional == pytest.approx(60.0)
    assert fill.fee == pytest.approx(0.03)
    assert report.positions_after[0]["symbol"] == "NEARUSDT"
    assert report.available_after == pytest.approx(25.0)
    assert report.margin_mode == "crossed"


def test_isolated_rejection_falls_back_to_cross_and_says_so() -> None:
    client = _FakeLiveClient()
    plan = _plan()

    report = _run(client, plan)

    assert len(client.placed) == 1
    assert "margin_mode" not in client.placed[0]
    assert any("逐仓" in note for note in report.margin_notes)
    assert report.fills[0].status == "filled"


def test_leverage_is_capped_in_crossed_mode_even_when_isolated_is_accepted() -> None:
    client = _FakeLiveClient(reject_isolated_orders=False)
    plan = _plan()

    _run(client, plan)

    modes = [call["margin_mode"] for call in client.leverage_calls]
    assert modes[0] == "crossed"
    assert "isolated" in modes
    assert all(call["long_leverage"] == 2.0 for call in client.leverage_calls)


def test_one_way_accounts_close_with_reduce_only_and_no_pos_side() -> None:
    position = PositionState(
        asset="near",
        symbol="NEARUSDT",
        side="long",
        size=10.0,
        entry_price=5.0,
        mark_price=5.0,
        margin=2.5,
    )
    client = _FakeLiveClient(hold_mode="one_way_mode")
    plan = _plan(weight=0.0, position=position)

    _run(client, plan)

    order = client.placed[0]
    assert order["pos_side"] is None
    assert order["reduce_only"] is True


def test_margin_failure_becomes_a_note_not_a_crash() -> None:
    client = _FakeLiveClient(
        margin_error='Bitget HTTP 400: {"code":"40731","msg":"This product does not support copy trading"}'
    )
    plan = _plan()

    report = _run(client, plan)

    assert report.fills  # trading still happened
    assert any("40731" in note for note in report.margin_notes)


def test_a_rejected_order_is_recorded_and_does_not_stop_the_run() -> None:
    client = _FakeLiveClient(place_error="Bitget HTTP 400: insufficient funds")
    plan = _plan()

    report = _run(client, plan)

    assert not report.fills
    assert len(report.failures) == 1
    assert "insufficient funds" in report.failures[0]["error"]


def test_an_accepted_order_with_a_lost_response_is_reconciled_by_client_oid() -> None:
    class _AcceptedButTimedOut(_FakeLiveClient):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.timed_out = False

        def place_order(self, **kwargs: Any) -> dict[str, Any]:
            result = super().place_order(**kwargs)
            if not self.timed_out:
                self.timed_out = True
                raise BitgetAPIError("request timed out after submission")
            return result

    client = _AcceptedButTimedOut(reject_isolated_orders=False)
    plan = _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20)

    report = _run(client, plan, client_oid_prefix="a20stable")

    assert not report.failures
    assert len(report.fills) == 1
    assert report.fills[0].client_oid == client.placed[0]["client_oid"]
    assert report.fills[0].client_oid.startswith("a20stableo")
    assert any("clientOid" in note for note in report.margin_notes)


def test_a_stable_client_oid_prefix_makes_retries_venue_idempotent() -> None:
    plan = _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20)
    first = _FakeLiveClient(reject_isolated_orders=False)
    second = _FakeLiveClient(reject_isolated_orders=False)

    _run(first, plan, client_oid_prefix="a20daily")
    _run(second, plan, client_oid_prefix="a20daily")

    assert first.placed[0]["client_oid"] == second.placed[0]["client_oid"]


def test_recovered_client_oid_order_must_match_the_current_order_size() -> None:
    class _StaleRecoveredOrder(_FakeLiveClient):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.timed_out = False

        def place_order(self, **kwargs: Any) -> dict[str, Any]:
            result = super().place_order(**kwargs)
            if not self.timed_out:
                self.timed_out = True
                order = self.order_infos[str(result["orderId"])]
                order["cumExecQty"] = "7"
                raise BitgetAPIError("request timed out after submission")
            return result

    client = _StaleRecoveredOrder(reject_isolated_orders=False)

    report = _run(
        client,
        _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20),
        client_oid_prefix="a20stale",
    )

    assert any("different quantity" in item["error"] for item in report.failures)


def test_recovered_client_oid_order_must_match_the_current_side() -> None:
    class _WrongSideRecoveredOrder(_FakeLiveClient):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.timed_out = False

        def place_order(self, **kwargs: Any) -> dict[str, Any]:
            result = super().place_order(**kwargs)
            if not self.timed_out:
                self.timed_out = True
                order = self.order_infos[str(result["orderId"])]
                order["side"] = "buy"
                raise BitgetAPIError("request timed out after submission")
            return result

    client = _WrongSideRecoveredOrder(reject_isolated_orders=False)

    report = _run(
        client,
        _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20),
        client_oid_prefix="a20wrongside",
    )

    assert not report.fills
    assert any("timed out" in item["error"] for item in report.failures)


def test_an_unfilled_order_is_a_failure_and_must_not_mark_the_run_ok() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        order_infos={"1001": {"orderStatus": "live", "cumExecQty": "0"}},
    )

    report = _run(client, _plan(), fill_timeout_seconds=0)

    assert report.fills[0].status == "cancelled"
    assert report.fills[0].filled_size == 0.0
    assert len(report.failures) == 1
    assert "cancelled" in report.failures[0]["error"]


def test_a_missing_order_id_is_a_failure_without_a_fake_fill() -> None:
    class _MissingOrderId(_FakeLiveClient):
        def place_order(self, **kwargs: Any) -> dict[str, Any]:
            return {}

    client = _MissingOrderId(reject_isolated_orders=False)

    report = _run(client, _plan())

    assert report.fills == []
    assert len(report.failures) == 1
    assert "orderId" in report.failures[0]["error"]


def test_crossed_leverage_failure_blocks_the_order() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        crossed_leverage_error="Bitget set-leverage HTTP 400: permission denied",
    )

    report = _run(client, _plan())

    assert client.placed == []
    assert len(report.failures) == 1
    assert "leverage" in report.failures[0]["error"].lower()


def test_is_isolated_unsupported_matches_the_live_error_shapes() -> None:
    assert is_isolated_unsupported(BitgetAPIError("... 25200 fixedMargin not support ..."))
    assert is_isolated_unsupported(BitgetAPIError("... 40731 This product does not support copy trading"))
    assert is_isolated_unsupported(BitgetAPIError("... 25200 FIXEDMARGIN NOT SUPPORT ..."))
    assert not is_isolated_unsupported(BitgetAPIError("... 25238 posSide and reduceOnly ..."))


def test_wait_for_fill_polls_until_the_order_is_filled() -> None:
    class _Polling:
        def __init__(self) -> None:
            self.calls = 0

        def order_info(self, **kwargs: Any) -> dict[str, Any]:
            self.calls += 1
            if self.calls < 3:
                return {"orderStatus": "live", "cumExecQty": "0"}
            return {"orderStatus": "filled", "cumExecQty": "2", "avgPrice": "5", "feeDetail": []}

    client = _Polling()
    waited: list[float] = []
    payload = wait_for_fill(
        client,  # type: ignore[arg-type]
        order_id="1",
        timeout_seconds=10.0,
        poll_interval_seconds=1.0,
        sleep=waited.append,
        clock=lambda: float(len(waited)),
    )

    assert payload["orderStatus"] == "filled"
    assert waited == [1.0, 1.0]


def test_report_message_shows_real_positions_and_the_cross_warning() -> None:
    report = ExecutionReport(
        signal_date="2026-10-08",
        equity_before=100.0,
        equity_after=99.91,
        available_after=25.4,
        positions_after=[
            {
                "asset": "near",
                "symbol": "NEARUSDT",
                "posSide": "long",
                "marginMode": "crossed",
                "total": "14",
                "avgPrice": "5.3239",
                "markPrice": "5.3241",
                "unrealisedPnl": "0.01",
            }
        ],
        margin_mode="crossed",
    )

    message = format_execution_report(
        report,
        signal_date="2026-10-08",
        spec="PR2026-10-D-L125-V2",
        targets={"near": 0.7768},
        lot_notional={"near": 5.32},
        prev_equity=99.80,
        prev_day_pnl=0.42,
    )

    assert "总权益 99.91 USDT" in message
    assert "仓位价值 74.54 USDT" in message
    assert "今日盈亏 +0.11 USDT（+0.11%）" in message
    assert "昨日盈亏 +0.42 USDT" in message
    assert "NEAR LONG 14 枚 · 74.54 USDT" in message
    assert "NEAR 目标 77.61 / 实际 74.54" in message
    # concise: no margin-mode lecture, no filler
    assert "规格要求逐仓" not in message
    assert "保证金" not in message
    assert len(message.splitlines()) <= 14


def test_report_marks_the_first_day_and_empty_book() -> None:
    report = ExecutionReport(signal_date="2026-10-08", equity_before=100.0, equity_after=100.0)

    message = format_execution_report(report, signal_date="2026-10-08", spec="SPEC")

    assert "总权益 100.00 USDT" in message
    assert "仓位价值 0.00 USDT" in message
    assert "今日盈亏 —（首个记录日）" in message
    assert "昨日盈亏 —" in message
    assert "空仓" in message


def test_report_shows_the_attached_short_stop_price() -> None:
    report = ExecutionReport(
        signal_date="2026-11-13",
        equity_before=100.0,
        equity_after=100.0,
        fills=[
            OrderFill(
                asset="near",
                symbol="NEARUSDT",
                action="OPEN",
                side="sell",
                stop_loss=6.0,
                requested_size=10.0,
                filled_size=10.0,
                avg_price=5.0,
                notional=50.0,
                fee=0.03,
                fee_coin="USDT",
                order_id="1",
                status="filled",
            )
        ],
    )

    message = format_execution_report(report, signal_date="2026-11-13", spec="SPEC")

    assert "止损 6" in message


def test_report_matches_a_signed_short_target_and_marks_short_pnl() -> None:
    report = ExecutionReport(
        signal_date="2026-11-13",
        equity_before=250.0,
        equity_after=250.0,
        positions_after=[
            {
                "asset": "near",
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "avgPrice": "5",
                "markPrice": "5.5",
            }
        ],
    )

    message = format_execution_report(
        report,
        signal_date="2026-11-13",
        spec="SPEC",
        targets={"near": -0.4},
    )

    assert "目标 -100.00 / 实际 -110.00" in message
    assert "SHORT" in message
    assert "浮盈 -10.00" in message


def test_execution_report_serializes_actual_gross_position_value() -> None:
    report = ExecutionReport(
        signal_date="2026-11-13",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
    )

    assert report.as_dict()["position_value"] == pytest.approx(100.0)


def test_report_does_not_replace_zero_equity_with_the_before_value() -> None:
    report = ExecutionReport(
        signal_date="2026-11-13",
        equity_before=100.0,
        equity_after=0.0,
    )

    message = format_execution_report(report, signal_date="2026-11-13", spec="SPEC")

    assert "总权益 0.00 USDT" in message
    assert "总权益 100.00 USDT" not in message


def test_report_shows_margin_and_capability_notes() -> None:
    report = ExecutionReport(
        signal_date="2026-11-13",
        equity_before=499.64,
        equity_after=499.64,
        margin_notes=[
            "the API key belongs to a copy-trading/elite trader; "
            "risk-reducing close remains allowed"
        ],
    )

    message = format_execution_report(report, signal_date="2026-11-13", spec="SPEC")

    assert "提示:" in message
    assert "copy-trading/elite trader" in message


def test_report_flags_an_orphan_position() -> None:
    report = ExecutionReport(
        signal_date="2026-10-08",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {"asset": "zcash", "symbol": "ZECUSDT", "total": "1", "markPrice": "100"}
        ],
    )

    message = format_execution_report(
        report, signal_date="2026-10-08", spec="SPEC", targets={"near": 0.5}
    )

    assert "计划外持仓: ZEC" in message


def test_report_matches_aliased_contract_by_stamped_asset() -> None:
    report = ExecutionReport(
        signal_date="2026-10-25",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {
                "asset": "tron",
                "symbol": "TRXUSDT",
                "total": "0.25",
                "avgPrice": "100",
                "markPrice": "100",
                "unrealisedPnl": "0",
            }
        ],
    )

    message = format_execution_report(
        report,
        signal_date="2026-10-25",
        spec="SPEC",
        targets={"tron": 0.25},
    )

    assert "TRON 目标 25.00 / 实际 25.00" in message
    assert "计划外持仓" not in message


def test_report_flags_a_residual_position_when_the_target_is_cash() -> None:
    report = ExecutionReport(
        signal_date="2026-10-30",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {
                "asset": "tron",
                "symbol": "TRXUSDT",
                "total": "10",
                "avgPrice": "1",
                "markPrice": "1",
            }
        ],
    )

    message = format_execution_report(
        report,
        signal_date="2026-10-30",
        spec="SPEC",
        targets={},
    )

    assert "计划外持仓: TRX" in message


def test_report_excludes_external_deposit_from_daily_pnl() -> None:
    report = ExecutionReport(
        signal_date="2026-11-03",
        equity_before=501.0,
        equity_after=501.0,
        balance_after=501.0,
    )

    message = format_execution_report(
        report,
        signal_date="2026-11-03",
        spec="SPEC",
        prev_equity=100.0,
        capital_flow=400.0,
    )

    assert "今日盈亏 +1.00 USDT（+0.20%）" in message


def test_signal_line_says_how_old_the_last_change_is() -> None:
    report = ExecutionReport(
        signal_date="2026-10-08",
        equity_before=100.0,
        equity_after=100.0,
        positions_after=[
            {"asset": "near", "symbol": "NEARUSDT", "total": "14", "markPrice": "5.0"}
        ],
    )

    message = format_execution_report(
        report,
        signal_date="2026-10-08",
        spec="SPEC",
        targets={"near": 0.75},
        event_age_days=3,
    )

    assert "信号 2026-10-08（3 天前的最近变化）" in message

    today = format_execution_report(
        report,
        signal_date="2026-10-08",
        spec="SPEC",
        targets={"near": 0.75},
        event_age_days=0,
    )
    assert "（今天的变化）" in today


def _short_position(size: float = 20.0) -> PositionState:
    return PositionState(
        asset="near",
        symbol="NEARUSDT",
        side="short",
        size=size,
        entry_price=5.0,
        mark_price=5.0,
        margin=size * 5.0 * 0.515,
    )


def _signed_plan(
    *,
    target_weight: float,
    position: PositionState | None = None,
    short_stop_loss_pct: float | None = None,
):
    account = AccountState(
        equity=100.0,
        available_margin=100.0,
        positions={} if position is None else {position.asset: position},
    )
    return build_execution_plan(
        account,
        {"near": target_weight},
        {"near": _spec()},
        {"near": 5.0},
        short_stop_loss_pct=short_stop_loss_pct,
    )


def test_hedge_mode_short_open_uses_sell_and_short_position_side() -> None:
    client = _FakeLiveClient(reject_isolated_orders=False)

    report = _run(client, _signed_plan(target_weight=-0.4))

    assert len(report.fills) == 1
    order = client.placed[0]
    assert order["side"] == "sell"
    assert order["pos_side"] == "short"
    assert order["reduce_only"] is False


def test_hedge_mode_short_open_attaches_a_mark_price_stop() -> None:
    client = _FakeLiveClient(reject_isolated_orders=False)

    report = _run(
        client,
        _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20),
    )

    order = client.placed[0]
    assert order["stop_loss"] == pytest.approx(6.0)
    assert order["sl_trigger_by"] == "mark"
    assert order["sl_order_type"] == "market"
    assert report.fills[0].stop_loss == pytest.approx(6.0)


def test_new_short_requires_a_live_venue_strategy_order_not_only_order_echo() -> None:
    class _ShortPositionAfterFill(_FakeLiveClient):
        def place_order(self, **kwargs: Any) -> dict[str, Any]:
            result = super().place_order(**kwargs)
            if kwargs.get("side") == "sell":
                self.positions = [
                    {
                        "symbol": kwargs["symbol"],
                        "total": str(kwargs["qty"]),
                        "posSide": "short",
                        "marginMode": "isolated",
                        "avgPrice": "5",
                        "markPrice": "5",
                    }
                ]
            elif kwargs.get("side") == "buy":
                self.positions = []
            return result

    client = _ShortPositionAfterFill(
        reject_isolated_orders=False,
        strategy_orders=[],
    )

    report = _run(
        client,
        _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20),
    )

    assert [fill.action for fill in report.fills] == ["OPEN", "EMERGENCY_CLOSE"]
    assert any("no live venue stop" in item["error"] for item in report.failures)


def test_one_way_short_open_keeps_the_stop_while_omitting_position_side() -> None:
    client = _FakeLiveClient(hold_mode="one_way_mode", reject_isolated_orders=False)

    _run(client, _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20))

    order = client.placed[0]
    assert order["pos_side"] is None
    assert order["stop_loss"] == pytest.approx(6.0)


def test_require_isolated_skips_orders_when_leverage_setup_is_rejected() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        reject_isolated_leverage=True,
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.4),
        require_isolated=True,
    )

    assert client.placed == []
    assert report.traded is False
    assert any("isolated" in item["error"] for item in report.failures)


def test_require_isolated_does_not_let_a_later_symbol_fall_back_to_crossed() -> None:
    plan = build_execution_plan(
        AccountState(equity=100.0, available_margin=100.0),
        {"near": 0.2, "sol": 0.2},
        {"near": _spec(), "sol": _spec("SOLUSDT")},
        {"near": 5.0, "sol": 5.0},
    )
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        reject_isolated_leverage=True,
    )

    report = _run(client, plan, require_isolated=True)

    assert client.placed == []
    assert len(report.failures) == 2
    isolated_attempts = [
        call for call in client.leverage_calls if call.get("margin_mode") == "isolated"
    ]
    assert {call["symbol"] for call in isolated_attempts} == {"NEARUSDT", "SOLUSDT"}


def test_require_isolated_never_retries_the_order_as_crossed() -> None:
    client = _FakeLiveClient(reject_isolated_orders=True)

    report = _run(
        client,
        _signed_plan(target_weight=0.4),
        require_isolated=True,
    )

    assert client.placed == []
    assert report.traded is False
    assert any("isolated" in item["error"] for item in report.failures)


def test_require_isolated_rejects_a_crossed_position_readback() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "4",
                "posSide": "long",
                "marginMode": "crossed",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.0),
        require_isolated=True,
    )

    assert any("venue reports crossed" in item["error"] for item in report.failures)


def test_require_isolated_rejects_mixed_position_margin_modes() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "4",
                "posSide": "long",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            },
            {
                "symbol": "SOLUSDT",
                "total": "4",
                "posSide": "long",
                "marginMode": "crossed",
                "markPrice": "5",
                "avgPrice": "5",
            },
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.0),
        require_isolated=True,
    )

    assert any("isolated" in item["error"] for item in report.failures)


def test_require_isolated_blocks_an_increase_on_a_crossed_position() -> None:
    position = PositionState(
        asset="near",
        symbol="NEARUSDT",
        side="long",
        size=20.0,
        entry_price=5.0,
        mark_price=5.0,
        margin=51.5,
    )
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "long",
                "marginMode": "crossed",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=1.2, position=position),
        require_isolated=True,
    )

    assert client.placed == []
    assert any("crossed" in item["error"] for item in report.failures)
    assert any("blocked" in item["error"] for item in report.failures)


def test_require_isolated_still_allows_a_risk_reducing_close() -> None:
    position = PositionState(
        asset="near",
        symbol="NEARUSDT",
        side="long",
        size=20.0,
        entry_price=5.0,
        mark_price=5.0,
        margin=51.5,
    )
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "long",
                "marginMode": "crossed",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.0, position=position),
        require_isolated=True,
    )

    assert len(client.placed) == 1
    assert client.placed[0]["side"] == "sell"
    assert report.fills[0].action == "CLOSE"


def test_require_isolated_never_needs_a_crossed_leverage_setup() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        crossed_leverage_error="crossed setup unavailable",
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.4),
        require_isolated=True,
    )

    assert len(client.placed) == 1
    assert not report.failures
    assert all(call.get("margin_mode") != "crossed" for call in client.leverage_calls)


def test_margin_adjustments_are_skipped_after_an_order_failure() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        place_error="venue rejected open",
    )

    report = _run(
        client,
        _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20),
    )

    assert report.failures
    assert client.margin_calls == []


def test_existing_short_without_a_recorded_stop_is_emergency_closed() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.0),
        known_protected_short_symbols=set(),
    )

    assert client.placed[0]["side"] == "buy"
    assert report.fills[-1].action == "EMERGENCY_CLOSE"
    assert any("no live venue stop" in item["error"] for item in report.failures)


def test_emergency_close_with_a_non_positive_average_price_reports_failure() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
        order_infos={
            "1001": {
                "orderStatus": "filled",
                "cumExecQty": "20",
                "avgPrice": "0",
                "cumExecValue": "100",
                "feeDetail": [],
            }
        },
    )

    report = _run(
        client,
        _signed_plan(target_weight=0.0),
        known_protected_short_symbols=set(),
    )

    assert report.fills[-1].action == "EMERGENCY_CLOSE"
    assert any("avgPrice" in item["error"] for item in report.failures)


def test_executor_rejects_an_unknown_position_side() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "side_typo",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
    )

    with pytest.raises(ValueError, match="posSide"):
        _run(client, _plan())


def test_short_order_reports_an_unconfirmed_stop_as_a_failure() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        echo_stop_loss=False,
    )

    report = _run(
        client,
        _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20),
    )

    assert report.fills[0].stop_loss is None
    assert any("stop loss was not confirmed" in item["error"] for item in report.failures)
    emergency = client.placed[1]
    assert emergency["side"] == "buy"
    assert emergency["pos_side"] == "short"
    assert report.fills[-1].action == "EMERGENCY_CLOSE"


def test_short_order_with_the_wrong_stop_trigger_is_emergency_closed() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        stop_trigger_by_override="last_price",
    )

    report = _run(
        client,
        _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20),
    )

    assert report.fills[0].short_stop_confirmed is False
    assert any("stop loss was not confirmed" in item["error"] for item in report.failures)
    assert client.placed[-1]["side"] == "buy"
    assert report.fills[-1].action == "EMERGENCY_CLOSE"


def test_short_order_with_the_wrong_stop_price_is_emergency_closed() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        stop_loss_override=6.5,
    )

    report = _run(
        client,
        _signed_plan(target_weight=-0.4, short_stop_loss_pct=0.20),
    )

    assert report.fills[0].short_stop_confirmed is False
    assert any("stop loss was not confirmed" in item["error"] for item in report.failures)
    assert report.fills[-1].action == "EMERGENCY_CLOSE"


def test_unconfirmed_stop_on_a_short_increase_closes_the_whole_short_leg() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        echo_stop_loss=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(
            target_weight=-1.2,
            position=_short_position(),
            short_stop_loss_pct=0.20,
        ),
    )

    assert report.fills[0].action == "INCREASE"
    emergency = client.placed[-1]
    assert emergency["side"] == "buy"
    assert emergency["qty"] == pytest.approx(24.0)
    assert report.fills[-1].action == "EMERGENCY_CLOSE"


def test_long_to_short_flip_configures_the_new_short_side() -> None:
    long_position = PositionState(
        asset="near",
        symbol="NEARUSDT",
        side="long",
        size=20.0,
        entry_price=5.0,
        mark_price=5.0,
        margin=51.5,
    )
    plan = _signed_plan(target_weight=-0.4, position=long_position)
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "long",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
    )

    _run(client, plan)

    isolated_sides = {
        call["pos_side"]
        for call in client.leverage_calls
        if call.get("margin_mode") == "isolated"
    }
    assert isolated_sides == {"short"}


def test_close_does_not_get_blocked_by_a_leverage_setup_failure() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        crossed_leverage_error="leverage unavailable",
    )
    plan = _signed_plan(target_weight=0.0, position=_short_position())

    report = _run(client, plan)

    assert len(client.placed) == 1
    assert client.placed[0]["side"] == "buy"
    assert report.fills[0].action == "CLOSE"


def test_failed_close_blocks_the_opposite_side_open() -> None:
    class _FailShortClose(_FakeLiveClient):
        def place_order(self, **kwargs: Any) -> dict[str, Any]:
            if kwargs.get("pos_side") == "short" and kwargs.get("side") == "buy":
                raise BitgetAPIError("close rejected")
            return super().place_order(**kwargs)

    client = _FailShortClose(reject_isolated_orders=False)
    plan = _signed_plan(target_weight=0.4, position=_short_position())

    report = _run(client, plan)

    assert client.placed == []
    assert any("opposite-side open was blocked" in item["error"] for item in report.failures)


def test_hedge_mode_short_close_uses_buy_and_short_position_side() -> None:
    client = _FakeLiveClient(reject_isolated_orders=False)
    plan = _signed_plan(target_weight=0.0, position=_short_position())

    report = _run(client, plan)

    assert len(report.fills) == 1
    order = client.placed[0]
    assert order["side"] == "buy"
    assert order["pos_side"] == "short"
    assert order["reduce_only"] is False


def test_one_way_short_close_uses_reduce_only_without_position_side() -> None:
    client = _FakeLiveClient(hold_mode="one_way_mode", reject_isolated_orders=False)
    plan = _signed_plan(target_weight=0.0, position=_short_position())

    _run(client, plan)

    order = client.placed[0]
    assert order["side"] == "buy"
    assert order["pos_side"] is None
    assert order["reduce_only"] is True


def test_plan_execution_never_turns_zero_equity_into_another_field() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        assets={
            "usdtEquity": 0,
            "accountEquity": 100,
            "assets": [{"coin": "USDT", "available": "0", "balance": "0"}],
        },
    )

    report = _run(client, _plan())

    assert client.placed == []
    assert report.equity_before == 0.0
    assert any("non-positive" in item["error"] for item in report.failures)


def test_final_account_snapshot_rejects_a_missing_balance() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        assets={
            "usdtEquity": "100",
            "assets": [{"coin": "USDT", "available": "10"}],
        },
    )

    with pytest.raises(ValueError, match="balance"):
        _run(client, _plan())


def test_a_manual_unfilled_order_on_a_planned_symbol_blocks_new_orders() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        unfilled=[
            {
                "orderId": "9001",
                "clientOid": "manual-risk-order",
                "symbol": "NEARUSDT",
                "orderStatus": "live",
            }
        ],
    )

    report = _run(client, _plan(), client_oid_prefix="a20current")

    assert client.placed == []
    assert any("unfilled" in item["error"].lower() for item in report.failures)


def test_a_stale_zero_fill_run_order_is_cancelled_before_retrying() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        unfilled=[
            {
                "orderId": "9002",
                "clientOid": "a20current00",
                "symbol": "NEARUSDT",
                "orderStatus": "live",
                "cumExecQty": "0",
            }
        ],
    )

    report = _run(client, _plan(), client_oid_prefix="a20current")

    assert [row["order_id"] for row in client.cancelled] == ["9002"]
    assert len(client.placed) == 1
    assert report.fills[0].status == "filled"


def test_a_live_order_that_times_out_is_cancelled_and_reported() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        order_infos={"1001": {"orderStatus": "live", "cumExecQty": "0"}},
    )

    report = _run(client, _plan(), fill_timeout_seconds=0)

    assert [row["order_id"] for row in client.cancelled] == ["1001"]
    assert report.fills[0].status == "cancelled"
    assert len(report.failures) == 1


def test_a_filled_order_without_a_fill_quantity_is_not_treated_as_zero() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        order_infos={
            "1001": {
                "orderStatus": "filled",
                "avgPrice": "5",
                "cumExecValue": "60",
                "feeDetail": [],
            }
        },
    )

    report = _run(client, _plan())

    assert report.fills == []
    assert any("cumExecQty" in item["error"] for item in report.failures)


def test_a_filled_order_with_a_non_positive_average_price_halts_safely() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        order_infos={
            "1001": {
                "orderStatus": "filled",
                "cumExecQty": "12",
                "avgPrice": "0",
                "cumExecValue": "60",
                "feeDetail": [],
            }
        },
    )

    report = _run(client, _plan())

    assert report.fills == []
    assert any("avgPrice" in item["error"] for item in report.failures)


def test_a_filled_order_with_a_non_positive_execution_value_halts_safely() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        order_infos={
            "1001": {
                "orderStatus": "filled",
                "cumExecQty": "12",
                "avgPrice": "5",
                "cumExecValue": "0",
                "feeDetail": [],
            }
        },
    )

    report = _run(client, _plan())

    assert report.fills == []
    assert any("cumExecValue" in item["error"] for item in report.failures)


def test_missing_margin_mode_is_treated_as_non_isolated_and_blocks_new_risk() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "long",
                "total": "2",
                "avgPrice": "5",
                "markPrice": "5",
                "positionBalance": "5",
            }
        ],
    )

    report = _run(client, _plan(), require_isolated=True, margin_mode="isolated")

    assert client.placed == []
    assert any("preflight venue reports" in item["error"] for item in report.failures)


def test_invalid_position_quantity_blocks_execution_instead_of_becoming_flat() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "long",
                "total": "not-a-number",
                "avgPrice": "5",
                "markPrice": "5",
                "positionBalance": "5",
            }
        ],
    )

    with pytest.raises(ValueError, match="position total"):
        _run(client, _plan())

    assert client.placed == []


def test_preflight_unfilled_order_with_invalid_fill_quantity_blocks_the_plan() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        unfilled=[
            {
                "orderId": "9003",
                "clientOid": "a20current00",
                "symbol": "NEARUSDT",
                "orderStatus": "live",
                "cumExecQty": "not-a-number",
            }
        ],
    )

    report = _run(client, _plan(), client_oid_prefix="a20current")

    assert client.placed == []
    assert any("could not be proven flat" in item["error"] for item in report.failures)


def test_stale_prior_day_order_outside_todays_plan_is_still_reconciled() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        unfilled=[
            {
                "orderId": "9004",
                "clientOid": "a20oldhash00",
                "symbol": "SOLUSDT",
                "orderStatus": "live",
                "cumExecQty": "0",
            }
        ],
    )

    report = _run(client, _plan(), client_oid_prefix="a20current")

    assert [row["order_id"] for row in client.cancelled] == ["9004"]
    assert len(client.placed) == 1
    assert report.fills[0].status == "filled"


def test_manual_unfilled_order_on_any_symbol_blocks_the_whole_plan() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        unfilled=[
            {
                "orderId": "9005",
                "clientOid": "manual-risk-order",
                "symbol": "SOLUSDT",
                "orderStatus": "live",
            }
        ],
    )

    report = _run(client, _plan(), client_oid_prefix="a20current")

    assert client.placed == []
    assert any("unrelated unfilled order" in item["error"] for item in report.failures)


def test_recovered_fill_uses_the_canonical_asset_mapping() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        order_history_rows=[
            {
                "orderId": "recovered-trx",
                "clientOid": "a20dailyrecoveredtrx",
                "symbol": "TRXUSDT",
                "side": "buy",
                "posSide": "long",
                "orderStatus": "filled",
                "cumExecQty": "10",
                "avgPrice": "1",
                "cumExecValue": "10",
                "feeDetail": [{"fee": "0.01", "feeCoin": "USDT"}],
            }
        ],
    )
    empty_plan = ExecutionPlan(
        equity=100.0,
        leverage=2.0,
        target_margin_ratio=0.5,
        orders=[],
        margin_intents=[],
        warnings=[],
        target_notional={"tron": 10.0},
        expected_gross_notional=10.0,
        expected_margin=5.0,
    )

    report = _run(
        client,
        empty_plan,
        client_oid_prefix="a20daily",
        symbol_assets={"TRXUSDT": "tron"},
    )

    assert report.fills[0].asset == "tron"


def test_executor_recovers_a_fill_that_landed_before_the_journal_write() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "10",
                "posSide": "long",
                "marginMode": "isolated",
                "avgPrice": "5",
                "markPrice": "5",
            }
        ],
        order_history_rows=[
            {
                "orderId": "recovered-1",
                "clientOid": "a20dailyorecovered",
                "symbol": "NEARUSDT",
                "side": "buy",
                "posSide": "long",
                "orderStatus": "filled",
                "cumExecQty": "10",
                "avgPrice": "5",
                "cumExecValue": "50",
                "feeDetail": [{"fee": "0.03", "feeCoin": "USDT"}],
            }
        ],
    )
    empty_plan = ExecutionPlan(
        equity=100.0,
        leverage=2.0,
        target_margin_ratio=0.5,
        orders=[],
        margin_intents=[],
        warnings=[],
        target_notional={"near": 50.0},
        expected_gross_notional=50.0,
        expected_margin=25.0,
    )

    report = _run(client, empty_plan, client_oid_prefix="a20daily")

    assert len(report.fills) == 1
    assert report.fills[0].order_id == "recovered-1"
    assert report.fills[0].action == "OPEN"
    assert report.fills[0].filled_size == pytest.approx(10.0)


def test_retry_does_not_reuse_a_filled_orders_client_oid_for_another_symbol() -> None:
    class _FailSolOnce(_FakeLiveClient):
        failed = False

        def place_order(self, **kwargs: Any) -> dict[str, Any]:
            if kwargs.get("symbol") == "SOLUSDT" and not self.failed:
                self.failed = True
                raise BitgetAPIError("temporary SOL rejection")
            return super().place_order(**kwargs)

    def order(symbol: str, side: str, pos_side: str) -> OrderIntent:
        return OrderIntent(
            asset=symbol.removesuffix("USDT").lower(),
            symbol=symbol,
            action="OPEN",
            side=side,
            size=10.0,
            price=5.0,
            notional=50.0,
            reduce_only=False,
            reason="test",
            pos_side=pos_side,
        )

    def plan(orders: list[OrderIntent]) -> ExecutionPlan:
        return ExecutionPlan(
            equity=100.0,
            leverage=2.0,
            target_margin_ratio=0.5,
            orders=orders,
            margin_intents=[],
            warnings=[],
            target_notional={"near": 50.0, "sol": 50.0},
            expected_gross_notional=100.0,
            expected_margin=50.0,
        )

    near = order("NEARUSDT", "buy", "long")
    sol = order("SOLUSDT", "buy", "long")
    client = _FailSolOnce(reject_isolated_orders=False)

    _run(client, plan([near, sol]), client_oid_prefix="a20daily")
    near_oid = str(client.placed[0]["client_oid"])
    _run(client, plan([sol]), client_oid_prefix="a20daily")
    sol_oid = str(client.placed[-1]["client_oid"])

    assert sol_oid != near_oid


def test_isolated_leverage_readback_mismatch_blocks_the_order() -> None:
    class _WrongLeverageReadback(_FakeLiveClient):
        def set_leverage(self, symbol: str, leverage: float, **kwargs: Any) -> Any:
            result = super().set_leverage(symbol, leverage, **kwargs)
            if kwargs.get("margin_mode") == "isolated":
                self.symbol_configs[(symbol, "isolated")]["leverage"] = "5"
                self.symbol_configs[(symbol, "isolated")]["longLeverage"] = "5"
                self.symbol_configs[(symbol, "isolated")]["shortLeverage"] = "5"
            return result

    client = _WrongLeverageReadback(reject_isolated_orders=False)

    report = _run(client, _plan(), require_isolated=True, margin_mode="isolated")

    assert client.placed == []
    assert any("leverage readback" in item["error"] for item in report.failures)


def test_journal_protection_without_a_live_venue_stop_is_emergency_closed() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
        strategy_orders=[],
    )

    report = _run(
        client,
        _signed_plan(target_weight=-1.0, position=_short_position()),
        known_protected_short_symbols={"NEARUSDT"},
    )

    assert any(fill.action == "EMERGENCY_CLOSE" for fill in report.fills)
    assert any("no live venue stop" in item["error"] for item in report.failures)


def test_a_live_mark_market_strategy_stop_preserves_an_existing_short() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
        strategy_orders=[
            {
                "orderId": "stop-20",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "orderStatus": "live",
                "side": "buy",
                "qty": "20",
                "stopLoss": "6",
                "slTriggerBy": "mark",
                "slOrderType": "market",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=-1.0, position=_short_position()),
        known_protected_short_symbols={"NEARUSDT"},
    )

    assert not any(fill.action == "EMERGENCY_CLOSE" for fill in report.fills)
    assert not report.failures


def test_a_modified_live_stop_is_restored_and_duplicates_are_removed() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "20",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
        strategy_orders=[
            {
                "orderId": "stop-correct",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "orderStatus": "live",
                "side": "buy",
                "qty": "10",
                "stopLoss": "6",
                "slTriggerBy": "mark",
                "slOrderType": "market",
            },
            {
                "orderId": "stop-wrong",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "orderStatus": "live",
                "side": "buy",
                "qty": "10",
                "stopLoss": "5.5",
                "slTriggerBy": "mark",
                "slOrderType": "market",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=-1.0, position=_short_position()),
        known_protected_short_stops={"NEARUSDT": 6.0},
    )

    assert not any(fill.action == "EMERGENCY_CLOSE" for fill in report.fills)
    assert not report.failures
    assert len(client.strategy_orders) == 1
    assert client.strategy_orders[0]["qty"] == "20"
    assert client.strategy_orders[0]["stopLoss"] == "6"


def test_one_way_net_strategy_stop_preserves_an_existing_short() -> None:
    client = _FakeLiveClient(
        hold_mode="one_way_mode",
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "-20",
                "posSide": "net",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
        strategy_orders=[
            {
                "orderId": "stop-net",
                "symbol": "NEARUSDT",
                "posSide": "net",
                "orderStatus": "live",
                "side": "buy",
                "qty": "20",
                "stopLoss": "6",
                "slTriggerBy": "mark",
                "slOrderType": "market",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=-1.0, position=_short_position()),
        known_protected_short_stops={"NEARUSDT": 6.0},
    )

    assert not any(fill.action == "EMERGENCY_CLOSE" for fill in report.fills)
    assert not report.failures
    assert len(client.strategy_orders) == 1
    assert client.strategy_orders[0]["qty"] == "20"
    assert client.strategy_orders[0]["stopLoss"] == "6"


def test_multiple_stop_orders_can_cover_an_increased_short() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "4",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
        strategy_orders=[
            {
                "orderId": "stop-old",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "orderStatus": "live",
                "side": "buy",
                "qty": "2",
                "stopLoss": "6",
                "slTriggerBy": "mark",
                "slOrderType": "market",
            },
            {
                "orderId": "stop-new",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "orderStatus": "live",
                "side": "buy",
                "qty": "2",
                "stopLoss": "6.0004",
                "slTriggerBy": "mark",
                "slOrderType": "market",
            },
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=-0.2, position=_short_position(size=4.0)),
        known_protected_short_stops={"NEARUSDT": 6.0004},
    )

    assert not any(fill.action == "EMERGENCY_CLOSE" for fill in report.fills)
    assert not report.failures
    assert len(client.strategy_orders) == 1
    assert client.strategy_orders[0]["qty"] == "4"
    assert client.strategy_orders[0]["stopLoss"] == "6.0004"


def test_a_single_partial_stop_does_not_cover_an_increased_short() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "4",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
        strategy_orders=[
            {
                "orderId": "stop-partial",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "orderStatus": "live",
                "side": "buy",
                "qty": "2",
                "stopLoss": "6",
                "slTriggerBy": "mark",
                "slOrderType": "market",
            }
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=-0.2, position=_short_position(size=4.0)),
        known_protected_short_stops={"NEARUSDT": 6.0},
    )

    assert not any(fill.action == "EMERGENCY_CLOSE" for fill in report.fills)
    assert not report.failures
    assert len(client.strategy_orders) == 1
    assert client.strategy_orders[0]["qty"] == "4"
    assert client.strategy_orders[0]["stopLoss"] == "6"


def test_an_unrelated_strategy_order_blocks_normalization_and_closes_the_short() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        positions=[
            {
                "symbol": "NEARUSDT",
                "total": "4",
                "posSide": "short",
                "marginMode": "isolated",
                "markPrice": "5",
                "avgPrice": "5",
            }
        ],
        strategy_orders=[
            {
                "orderId": "stop-good",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "orderStatus": "live",
                "side": "buy",
                "qty": "4",
                "stopLoss": "6",
                "slTriggerBy": "mark",
                "slOrderType": "market",
            },
            {
                "orderId": "strategy-extra",
                "symbol": "NEARUSDT",
                "posSide": "short",
                "orderStatus": "live",
                "side": "buy",
                "qty": "4",
                "takeProfit": "4",
                "tpTriggerBy": "mark",
                "tpOrderType": "market",
            },
        ],
    )

    report = _run(
        client,
        _signed_plan(target_weight=-0.2, position=_short_position(size=4.0)),
        known_protected_short_stops={"NEARUSDT": 6.0},
    )

    assert any(fill.action == "EMERGENCY_CLOSE" for fill in report.fills)
    assert any("unexpected strategy order" in item["error"] for item in report.failures)


def test_orphan_strategy_order_blocks_a_new_open_before_money_moves() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        strategy_orders=[
            {
                "orderId": "orphan-tp",
                "symbol": "NEARUSDT",
                "posSide": "long",
                "status": "pending",
                "side": "sell",
                "qty": "4",
                "takeProfit": "6",
                "tpTriggerBy": "mark",
                "tpOrderType": "market",
            }
        ],
    )

    report = _run(client, _plan())

    assert client.placed == []
    assert any(
        "strategy order" in item["error"] and "no open" in item["error"]
        for item in report.failures
    )


def test_strategy_order_query_failure_still_allows_a_risk_reducing_close() -> None:
    class _StrategyQueryFails(_FakeLiveClient):
        def unfilled_strategy_orders(self, **kwargs: Any) -> list[dict[str, Any]]:
            raise BitgetAPIError("strategy endpoint unavailable")

    position = PositionState(
        asset="near",
        symbol="NEARUSDT",
        side="long",
        size=20.0,
        entry_price=5.0,
        mark_price=5.0,
        margin=51.5,
    )
    client = _StrategyQueryFails(reject_isolated_orders=False)

    report = _run(client, _plan(weight=0.0, position=position))

    assert [row["side"] for row in client.placed] == ["sell"]
    assert report.failures == []
    assert any("strategy" in note for note in report.margin_notes)
