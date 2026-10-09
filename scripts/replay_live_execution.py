"""Live-fire replay: run the live planner against the engine's real ledger.

This is the logic-level "does the thing we will run every day actually
implement the frozen specification?" test.  It does not compare code paths to
each other in the abstract; it replays every rebalance the research engine
executed over the full 2022-01-01 -> 2026-09-21 window:

1. rebuild the frozen targets with the production strategy code and run the
   real isolated-margin engine (same code path as the research report);
2. walk the engine's own trade ledger hour by hour, maintaining the account
   state (cash, per-leg quantity, entry, isolated margin) from the ledger;
3. at every rebalance timestamp, feed that state to the *live* planner
   (``atlas20.derivatives.execution.build_execution_plan``) with the same
   targets and fill prices, and compare the orders it emits with what the
   engine actually did;
4. repeat with the real Bitget contract specs (quantity step, minimum order)
   to measure how much venue quantization distorts the ideal orders.

The output is a JSON + markdown report: match counts, mismatches, and the
quantization error distribution.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.derivatives.execution import (  # noqa: E402
    AccountState,
    ContractSpec,
    PositionState,
    build_execution_plan,
)
from atlas20.derivatives.signals import build_derivative_targets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402

_ACTION_MAP = {
    "open": "OPEN",
    "increase": "INCREASE",
    "reduce": "REDUCE",
    "close": "CLOSE",
}


class _LedgerState:
    """Account state reconstructed from the engine's trade ledger.

    The engine runs at ``initial_capital = 1.0``; ``scale`` lifts the ledger to
    a realistic reference equity (1000 USDT) so the venue minimums are applied
    at the size the live account will actually trade.
    """

    def __init__(self, initial_cash: float = 1.0, scale: float = 1.0) -> None:
        self.scale = float(scale)
        self.cash = float(initial_cash) * self.scale
        self.positions: dict[str, dict[str, float]] = {}

    def apply(self, trade: pd.Series) -> None:
        asset = str(trade["asset"])
        action = str(trade["action"])
        quantity = float(trade["quantity"]) * self.scale
        price = float(trade["price"])
        margin = float(trade["margin"]) * self.scale
        fee = float(trade["fee"]) * self.scale
        if action in {"open", "increase"}:
            entry = self.positions.get(asset)
            if entry is None:
                self.positions[asset] = {
                    "size": quantity,
                    "entry": price,
                    "margin": margin,
                    "mark": price,
                }
            else:
                total = entry["size"] + quantity
                entry["entry"] = (entry["size"] * entry["entry"] + quantity * price) / total
                entry["size"] = total
                entry["margin"] += margin
                entry["mark"] = price
            self.cash -= margin + fee
        elif action in {"reduce", "close"}:
            entry = self.positions.get(asset)
            if entry is None:
                raise ValueError(f"ledger reduce/close without position for {asset}")
            if action == "close":
                self.cash += max(0.0, margin + quantity * (price - entry["entry"]) - fee)
                self.positions.pop(asset)
            else:
                self.cash += margin + quantity * (price - entry["entry"]) - fee
                entry["size"] -= quantity
                entry["margin"] -= margin
                entry["mark"] = price
        else:
            raise ValueError(f"unexpected ledger action {action!r}")

    def snapshot(self, prices: dict[str, float]) -> AccountState:
        positions: dict[str, PositionState] = {}
        equity = self.cash
        for asset, entry in self.positions.items():
            price = float(prices.get(asset, entry["mark"]))
            equity += entry["margin"] + entry["size"] * (price - entry["entry"])
            positions[asset] = PositionState(
                asset=asset,
                symbol=asset.upper(),
                side="long",
                size=entry["size"],
                entry_price=entry["entry"],
                mark_price=price,
                margin=entry["margin"],
            )
        return AccountState(equity=equity, available_margin=self.cash, positions=positions)


def _fill_prices(trades: pd.DataFrame, timestamp: pd.Timestamp) -> dict[str, float]:
    group = trades.loc[trades["timestamp"] == timestamp]
    return {str(row["asset"]): float(row["price"]) for _, row in group.iterrows()}


def _compare(
    plan, actual: pd.DataFrame, *, tolerance: float
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    matches: list[dict[str, object]] = []
    mismatches: list[dict[str, object]] = []
    planned = {order.asset: order for order in plan.orders}
    seen: set[str] = set()
    for _, trade in actual.iterrows():
        asset = str(trade["asset"])
        seen.add(asset)
        order = planned.get(asset)
        expected = _ACTION_MAP[str(trade["action"])]
        quantity = float(trade["quantity"])
        entry = {
            "asset": asset,
            "expected_action": expected,
            "expected_size": quantity,
            "planned_action": order.action if order else None,
            "planned_size": order.size if order else None,
        }
        if order is None:
            mismatches.append({**entry, "issue": "missing planned order"})
            continue
        if order.action != expected:
            mismatches.append({**entry, "issue": "action mismatch"})
            continue
        if abs(order.size - quantity) > max(tolerance, 1e-9 * abs(quantity)):
            mismatches.append({**entry, "issue": "size mismatch"})
            continue
        matches.append(entry)
    for asset, order in planned.items():
        if asset not in seen:
            mismatches.append(
                {
                    "asset": asset,
                    "expected_action": None,
                    "planned_action": order.action,
                    "planned_size": order.size,
                    "issue": "unexpected planned order",
                }
            )
    return matches, mismatches


def _apply_plan_order(
    state: _LedgerState,
    order,
    *,
    margin_ratio: float,
    fee_rate: float,
) -> None:
    """Apply one planned order to a paper account at the planner's own margin."""

    asset = order.asset
    if order.side == "buy":
        margin_add = order.notional * margin_ratio
        fee = order.notional * fee_rate
        entry = state.positions.get(asset)
        if entry is None:
            state.positions[asset] = {
                "size": order.size,
                "entry": order.price,
                "margin": margin_add,
                "mark": order.price,
            }
        else:
            total = entry["size"] + order.size
            entry["entry"] = (entry["size"] * entry["entry"] + order.size * order.price) / total
            entry["size"] = total
            entry["margin"] += margin_add
            entry["mark"] = order.price
        state.cash -= margin_add + fee
        return
    entry = state.positions.get(asset)
    if entry is None:
        raise ValueError(f"planned sell without position for {asset}")
    fraction = order.size / entry["size"] if entry["size"] > 0.0 else 1.0
    released = entry["margin"] * fraction
    pnl = order.size * (order.price - entry["entry"])
    fee = order.notional * fee_rate
    state.cash += released + pnl - fee
    entry["size"] -= order.size
    entry["margin"] -= released
    entry["mark"] = order.price
    if entry["size"] <= 1e-12 or order.action == "CLOSE":
        state.positions.pop(asset, None)


def _specs_from_instruments(
    rows: list[dict[str, object]],
    symbol_map: pd.DataFrame,
) -> dict[str, ContractSpec]:
    """Contract specs keyed by CMC asset id, resolved through the symbol map."""

    by_symbol = {str(row.get("symbol", "")).upper(): row for row in rows}
    specs: dict[str, ContractSpec] = {}
    for record in symbol_map.to_dict("records"):
        asset = str(record.get("coin_id", ""))
        symbol = str(record.get("bitget_symbol", "")).upper()
        row = by_symbol.get(symbol)
        if asset and row is not None:
            specs[asset] = ContractSpec.from_bitget_instrument(row)
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_20261009"))
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--leverage", type=float, default=1.25)
    parser.add_argument(
        "--reference-equity",
        type=float,
        default=1000.0,
        help="USDT equity the quantization pass sizes orders from",
    )
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument(
        "--instruments-file",
        type=Path,
        default=None,
        help="JSON file with Bitget v3 instruments; when absent, live public API is used",
    )
    parser.add_argument(
        "--ideal-only",
        action="store_true",
        help="skip the venue-quantization pass (engine-faithfulness replay only)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_live_replay"))
    args = parser.parse_args()
    configure_logging("ERROR")

    config, market, universe, index = _load_market(
        args.config, start_date=args.start_date, end_date=args.end_date
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_targets = _long_targets_from_build(built, index)
    symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, symbol_map)
    available = set(mark_candles)
    restricted, _ = _restrict_targets(long_targets, available, mark_candles)
    targets = build_derivative_targets(
        restricted,
        btc_close=market.price["bitcoin"],
        universe=universe,
        prices=market.price,
        funding_rates=None,
        leverage=args.leverage,
        max_gross=args.leverage,
        short_asset=None,
        short_weight=0.0,
        eligible=available,
    )

    engine_config = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(args.long_buffer),
        short_buffer=0.50,
        max_gross_exposure=args.leverage,
        funding_missing_policy="error",
        missing_mark_policy="carry",
        missing_mark_max_carry_hours=3,
    )
    result = run_derivative_backtest(
        mark_candles,
        targets,
        funding_rates=None,
        funding_intervals_hours=None,
        config=engine_config,
        start_time=pd.Timestamp(args.start_date, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )
    trades = result.trades.copy()
    trades["timestamp"] = pd.to_datetime(trades["timestamp"], utc=True, format="mixed")
    rebalance_trades = trades.loc[trades["reason"] == "rebalance"].copy()
    if rebalance_trades.empty:
        raise SystemExit("engine ledger contains no rebalance trades")

    # The engine resolves an execution time to the next available mark stamp
    # within one hour (03:00 -> 04:00 when a candle is missing), so mirror that
    # resolution here instead of assuming 03:00 always exists.
    rebalance_times = pd.DatetimeIndex(
        sorted({pd.Timestamp(value) for value in rebalance_trades["timestamp"]})
    )
    signal_for_execution: dict[pd.Timestamp, pd.Timestamp] = {}
    for signal_time in targets:
        target_time = pd.Timestamp(signal_time).normalize() + pd.Timedelta(days=1, hours=3)
        later = rebalance_times[rebalance_times >= target_time]
        if later.empty or later[0] - target_time > pd.Timedelta(hours=1):
            continue
        execution_time = pd.Timestamp(later[0])
        if execution_time in signal_for_execution:
            raise SystemExit(f"two signals resolve to execution time {execution_time}")
        signal_for_execution[execution_time] = pd.Timestamp(signal_time)

    state = _LedgerState(initial_cash=1.0)
    match_count = 0
    mismatch_rows: list[dict[str, object]] = []
    rebalance_count = 0
    quant_rows: list[dict[str, object]] = []
    specs: dict[str, ContractSpec] = {}

    grouped = list(rebalance_trades.groupby("timestamp", sort=True))
    # First pass: pure engine-faithfulness check.
    for timestamp, group in grouped:
        if timestamp not in signal_for_execution:
            raise SystemExit(f"rebalance trade at {timestamp} has no matching signal")
        prices = _fill_prices(rebalance_trades, timestamp)
        snapshot = state.snapshot(prices)
        plan = build_execution_plan(
            snapshot,
            targets[signal_for_execution[timestamp]],
            specs={},
            prices=prices,
            leverage=1.0 / 0.515,  # placeholder, mirror mode ignores venue margin
            long_buffer=float(args.long_buffer),
            mirror_engine=True,
        )
        matches, mismatches = _compare(plan, group, tolerance=1e-9)
        match_count += len(matches)
        rebalance_count += 1
        for row in mismatches:
            mismatch_rows.append({**row, "timestamp": str(timestamp)})
        for _, trade in group.iterrows():
            state.apply(trade)

    report: dict[str, object] = {
        "window": {"start": args.start_date, "end": args.end_date},
        "rebalances": rebalance_count,
        "engine_trades": int(len(rebalance_trades)),
        "matched_orders": match_count,
        "mismatched_orders": len(mismatch_rows),
        "mismatches": mismatch_rows[:20],
        "final_multiple_engine": float(result.daily_equity.iloc[-1]),
    }

    # Second pass: venue quantization with the real contract specs.
    if not args.ideal_only:
        if args.instruments_file is not None:
            payload = json.loads(Path(args.instruments_file).read_text(encoding="utf-8"))
            rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        else:
            import requests

            response = requests.get(
                "https://api.bitget.com/api/v3/market/instruments",
                params={"category": "USDT-FUTURES"},
                timeout=30,
            )
            response.raise_for_status()
            rows = response.json().get("data", [])
        specs = _specs_from_instruments(rows, symbol_map)
        state = _LedgerState(initial_cash=1.0, scale=float(args.reference_equity))
        quant_mismatch = 0
        for timestamp, group in grouped:
            if timestamp not in signal_for_execution:
                continue
            prices = _fill_prices(rebalance_trades, timestamp)
            snapshot = state.snapshot(prices)
            plan = build_execution_plan(
                snapshot,
                targets[signal_for_execution[timestamp]],
                specs=specs,
                prices=prices,
                leverage=1.0 / 0.515,
                long_buffer=float(args.long_buffer),
                min_rebalance_usdt=0.0,
            )
            planned = {order.asset: order for order in plan.orders}
            for _, trade in group.iterrows():
                asset = str(trade["asset"])
                order = planned.get(asset)
                ideal = float(trade["notional"]) * float(args.reference_equity)
                if order is None:
                    quant_mismatch += 1
                    quant_rows.append(
                        {
                            "timestamp": str(timestamp),
                            "asset": asset,
                            "ideal_notional": ideal,
                            "planned_notional": 0.0,
                            "error_pct": -100.0,
                            "note": "below venue minimum",
                        }
                    )
                else:
                    error_pct = (
                        (order.notional - ideal) / ideal * 100.0 if ideal > 0.0 else 0.0
                    )
                    quant_rows.append(
                        {
                            "timestamp": str(timestamp),
                            "asset": asset,
                            "ideal_notional": ideal,
                            "planned_notional": order.notional,
                            "error_pct": error_pct,
                            "note": "",
                        }
                    )
            for _, trade in group.iterrows():
                state.apply(trade)
        quant_frame = pd.DataFrame(quant_rows)
        if not quant_frame.empty:
            tradable = quant_frame.loc[quant_frame["planned_notional"] > 0.0]
            report["quantization"] = {
                "reference_equity": float(args.reference_equity),
                "orders_compared": int(len(quant_frame)),
                "orders_below_minimum": int(quant_mismatch),
                "abs_error_pct_mean": float(tradable["error_pct"].abs().mean())
                if not tradable.empty
                else 0.0,
                "abs_error_pct_p95": float(tradable["error_pct"].abs().quantile(0.95))
                if not tradable.empty
                else 0.0,
                "abs_error_pct_max": float(tradable["error_pct"].abs().max())
                if not tradable.empty
                else 0.0,
                "worst": (
                    tradable.loc[tradable["error_pct"].abs().idxmax()].to_dict()
                    if not tradable.empty
                    else {}
                ),
            }
        # Third pass: the account evolves under the planner's own orders, so
        # rounding and venue minimums actually compound.  Compare the final
        # marked equity with the engine at the same timestamp.
        state = _LedgerState(initial_cash=1.0, scale=float(args.reference_equity))
        plan_margin_ratio = None
        liquidation_events: list[dict[str, object]] = []
        previous_timestamp: pd.Timestamp | None = None
        for timestamp, group in grouped:
            if timestamp not in signal_for_execution:
                continue
            # Hourly liquidation path for the legs the plan-driven account held
            # since the previous rebalance (isolated long: low vs liq price).
            if previous_timestamp is not None:
                window_start = previous_timestamp + pd.Timedelta(hours=1)
                for asset, entry in list(state.positions.items()):
                    frame = mark_candles.get(asset)
                    if frame is None or entry["size"] <= 0.0:
                        continue
                    notional = entry["size"] * entry["entry"]
                    margin_ratio = entry["margin"] / notional if notional > 0.0 else 0.0
                    liq_price = (
                        entry["entry"] * (1.0 - margin_ratio) / (1.0 - 0.01)
                        if 0.0 < margin_ratio < 1.0
                        else 0.0
                    )
                    window = frame.loc[
                        (frame.index >= window_start) & (frame.index <= timestamp), "low"
                    ]
                    hit = window.loc[window <= liq_price]
                    if not hit.empty:
                        liquidation_events.append(
                            {
                                "timestamp": str(hit.index[0]),
                                "asset": asset,
                                "low": float(hit.iloc[0]),
                                "liquidation_price": float(liq_price),
                            }
                        )
            prices = _fill_prices(rebalance_trades, timestamp)
            snapshot = state.snapshot(prices)
            plan = build_execution_plan(
                snapshot,
                targets[signal_for_execution[timestamp]],
                specs=specs,
                prices=prices,
                leverage=1.0 / 0.515,
                long_buffer=float(args.long_buffer),
                taker_fee_rate=float(args.cost_bps) / 10_000.0,
            )
            plan_margin_ratio = plan.target_margin_ratio
            for order in plan.orders:
                _apply_plan_order(
                    state,
                    order,
                    margin_ratio=plan.target_margin_ratio,
                    fee_rate=float(args.cost_bps) / 10_000.0,
                )
            previous_timestamp = pd.Timestamp(timestamp)
        last_timestamp = pd.Timestamp(grouped[-1][0])
        final_prices: dict[str, float] = {}
        for asset in state.positions:
            frame = mark_candles.get(asset)
            if frame is not None:
                candidate = frame.index[frame.index <= last_timestamp]
                if len(candidate):
                    final_prices[asset] = float(frame.at[candidate[-1], "open"])
        final_plan_equity = state.snapshot(final_prices).equity
        # The engine runs at initial_capital = 1.0 and quotes multiples; the
        # paper account runs at ``reference_equity`` USDT, so normalize.
        final_plan_multiple = final_plan_equity / float(args.reference_equity)
        engine_multiple = float(result.equity_curve.loc[last_timestamp])
        report["stateful_plan"] = {
            "final_engine_multiple": engine_multiple,
            "final_plan_multiple": final_plan_multiple,
            "relative_drag_pct": (final_plan_multiple / engine_multiple - 1.0) * 100.0,
            "reference_equity": float(args.reference_equity),
            "margin_ratio": plan_margin_ratio,
            "open_legs": len(state.positions),
            "liquidation_events": len(liquidation_events),
            "first_liquidation": liquidation_events[0] if liquidation_events else None,
        }

        output_dir = ensure_dir(args.output_dir)
        quant_frame.to_csv(output_dir / "quantization_orders.csv", index=False)
    else:
        output_dir = ensure_dir(args.output_dir)

    (output_dir / "live_replay.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    lines = [
        "# Live Execution Replay",
        "",
        f"- window: {args.start_date} -> {args.end_date} (leverage {args.leverage:g}, "
        f"{args.cost_bps:g} bps)",
        f"- rebalances replayed: {rebalance_count}",
        f"- engine orders: {report['engine_trades']}, matched: {match_count}, "
        f"mismatched: {report['mismatched_orders']}",
        f"- engine final multiple: {report['final_multiple_engine']:.4f}",
    ]
    stateful = report.get("stateful_plan")
    if isinstance(stateful, dict):
        lines += [
            "",
            "## Stateful plan-driven account (rounding + venue minimums compound)",
            "",
            f"- final engine multiple {stateful['final_engine_multiple']:.6f}x vs "
            f"plan-driven {stateful['final_plan_multiple']:.6f}x",
            f"- relative drag: {stateful['relative_drag_pct']:+.4f}%",
            f"- hourly liquidation events: {stateful['liquidation_events']}",
        ]
    quant = report.get("quantization")
    if isinstance(quant, dict):
        lines += [
            "",
            "## Venue quantization (real Bitget specs)",
            "",
            f"- reference equity: {quant['reference_equity']:,.0f} USDT; orders compared: "
            f"{quant['orders_compared']}, below venue minimum: {quant['orders_below_minimum']}",
            f"- |notional error| mean {quant['abs_error_pct_mean']:.4f}%, "
            f"p95 {quant['abs_error_pct_p95']:.4f}%, max {quant['abs_error_pct_max']:.4f}%",
        ]
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
