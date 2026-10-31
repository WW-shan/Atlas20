from __future__ import annotations

from typing import Any

import pytest

from atlas20.derivatives.bitget import BitgetAPIError
from atlas20.derivatives.execution import (
    AccountState,
    ContractSpec,
    PositionState,
    build_execution_plan,
)
from atlas20.derivatives.live_executor import (
    ExecutionReport,
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
    ) -> None:
        self.hold_mode_value = hold_mode
        self.assets = assets or {"usdtEquity": "100", "assets": [{"coin": "USDT", "available": "25.0"}]}
        self.positions = positions or []
        self.order_infos = order_infos or {}
        self.reject_isolated_orders = reject_isolated_orders
        self.reject_isolated_leverage = reject_isolated_leverage
        self.crossed_leverage_error = crossed_leverage_error
        self.margin_error = margin_error
        self.place_error = place_error
        self.placed: list[dict[str, Any]] = []
        self.leverage_calls: list[dict[str, Any]] = []
        self.margin_calls: list[dict[str, Any]] = []
        self._next_id = 1000

    # -- protocol -----------------------------------------------------
    def account_assets(self) -> dict[str, Any]:
        return self.assets

    def current_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list(self.positions)

    def hold_mode(self) -> str:
        return self.hold_mode_value

    def set_leverage(self, symbol: str, leverage: float, **kwargs: Any) -> Any:
        self.leverage_calls.append({"symbol": symbol, "leverage": leverage, **kwargs})
        if kwargs.get("margin_mode") == "crossed" and self.crossed_leverage_error:
            raise BitgetAPIError(self.crossed_leverage_error)
        if kwargs.get("margin_mode") == "isolated" and self.reject_isolated_leverage:
            raise BitgetAPIError("Bitget set-leverage HTTP 400: 25200 fixedMargin not support")
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
                "orderStatus": "filled",
                "cumExecQty": str(kwargs["qty"]),
                "cumExecValue": str(round(float(kwargs["qty"]) * 5.0, 4)),
                "avgPrice": "5.0",
                "feeDetail": [{"feeCoin": "USDT", "fee": "0.03"}],
                "marginMode": "crossed" if kwargs.get("margin_mode") is None else "isolated",
            },
        )
        return {"orderId": order_id, "clientOid": kwargs.get("client_oid")}

    def order_info(self, **kwargs: Any) -> dict[str, Any]:
        return dict(self.order_infos.get(str(kwargs.get("order_id")), {}))


def _run(client: _FakeLiveClient, plan, **kwargs: Any) -> ExecutionReport:
    return execute_plan(
        client,
        plan,
        signal_date="2026-10-08",
        sleep=lambda _: None,
        clock=lambda: 0.0,
        **kwargs,
    )


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


def test_an_unfilled_order_is_a_failure_and_must_not_mark_the_run_ok() -> None:
    client = _FakeLiveClient(
        reject_isolated_orders=False,
        order_infos={"1001": {"orderStatus": "live", "cumExecQty": "0"}},
    )

    report = _run(client, _plan(), fill_timeout_seconds=0)

    assert report.fills[0].status == "live"
    assert report.fills[0].filled_size == 0.0
    assert len(report.failures) == 1
    assert "not filled" in report.failures[0]["error"]


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
    assert "NEAR 14 枚 · 74.54 USDT" in message
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
