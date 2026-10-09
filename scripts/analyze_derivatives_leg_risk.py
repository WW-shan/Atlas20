"""Per-leg adverse-excursion and liquidation-headroom analysis.

The zero-liquidation counts in the matrix reports say *that* nothing
liquidated; this script answers *how close* the frozen long book came.  For
every opened leg it walks the Bitget mark low path between entry and exit
and reports the maximum adverse excursion (MAE) next to the leg's own
liquidation price, so the 50% long buffer can be judged on evidence rather
than on the absence of an event.
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
from atlas20.derivatives.engine import (  # noqa: E402
    DerivativeBacktestConfig,
    run_derivative_backtest,
)
from atlas20.derivatives.signals import scale_long_targets  # noqa: E402
from atlas20.logging_utils import ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_derivatives_backtest import _long_targets_from_build, _restrict_targets  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def _leg_intervals(trades: pd.DataFrame) -> list[dict[str, object]]:
    """Rebuild (entry_time, exit_time) per leg from the trade ledger."""

    intervals: list[dict[str, object]] = []
    open_legs: dict[str, dict[str, object]] = {}
    for row in trades.sort_values("timestamp").to_dict("records"):
        asset = str(row["asset"])
        action = str(row["action"])
        timestamp = pd.Timestamp(row["timestamp"])
        if action == "open" or (action == "increase" and asset not in open_legs):
            open_legs[asset] = {
                "asset": asset,
                "entry_time": timestamp,
                "entry_price": float(row["price"]),
                "side": str(row["side"]),
            }
        elif action == "close":
            leg = open_legs.pop(asset, None)
            if leg is not None:
                leg["exit_time"] = timestamp
                intervals.append(leg)
    for leg in open_legs.values():
        leg["exit_time"] = None
        intervals.append(leg)
    return intervals


def _asset_pnl(trades: pd.DataFrame) -> pd.DataFrame:
    """Realised P&L per asset from the trade ledger (average cost, fees included)."""

    state: dict[str, dict[str, float]] = {}
    pnl: dict[str, float] = {}
    for row in trades.sort_values("timestamp").to_dict("records"):
        asset = str(row["asset"])
        side = 1.0 if str(row["side"]) == "long" else -1.0
        quantity = float(row["quantity"])
        price = float(row["price"])
        fee = float(row["fee"])
        book = state.setdefault(asset, {"quantity": 0.0, "cost": 0.0})
        pnl.setdefault(asset, 0.0)
        action = str(row["action"])
        if action in {"open", "increase"}:
            book["cost"] += quantity * price
            book["quantity"] += quantity
        else:
            average = book["cost"] / book["quantity"] if book["quantity"] else price
            closed = min(quantity, book["quantity"])
            pnl[asset] += side * closed * (price - average)
            book["cost"] -= closed * average
            book["quantity"] -= closed
        pnl[asset] -= fee
    frame = pd.DataFrame(
        [{"asset": asset, "realised_pnl": value} for asset, value in pnl.items()]
    ).sort_values("realised_pnl", ascending=False)
    total = float(frame["realised_pnl"].sum())
    frame["share_of_total"] = frame["realised_pnl"] / total if total else 0.0
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_20261009"))
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--leverage", type=float, action="append", default=None)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--missing-mark-max-carry-hours", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    leverages = args.leverage or [1.25, 1.5, 2.0]
    config, market, universe, index = _load_market(
        args.config, start_date=args.start_date, end_date=args.end_date
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_targets = _long_targets_from_build(built, index)
    symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, symbol_map)
    available_marks = set(mark_candles)
    restricted, _ = _restrict_targets(long_targets, available_marks, mark_candles)

    leg_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for leverage in leverages:
        scaled = scale_long_targets(restricted, leverage=leverage, max_gross=leverage)
        result = run_derivative_backtest(
            mark_candles,
            scaled,
            funding_rates=None,
            funding_intervals_hours=None,
            config=DerivativeBacktestConfig(
                initial_capital=1.0,
                taker_fee_bps=float(args.cost_bps),
                slippage_bps=0.0,
                liquidation_slippage_bps=5.0,
                long_buffer=float(args.long_buffer),
                short_buffer=0.50,
                fee_buffer=0.005,
                maintenance_margin_rate=0.01,
                max_margin_utilization=0.85,
                max_gross_exposure=leverage,
                funding_missing_policy="error",
                missing_mark_policy="carry",
                missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
            ),
            start_time=pd.Timestamp(args.start_date, tz="UTC"),
            end_time=pd.Timestamp(args.end_date, tz="UTC"),
        )
        liquidation_prices = {
            (str(row["asset"]), pd.Timestamp(row["timestamp"])): float(row["liquidation_price"])
            for row in result.positions.to_dict("records")
        }
        worst_mae = 0.0
        for leg in _leg_intervals(result.trades):
            asset = str(leg["asset"])
            frame = mark_candles.get(asset)
            if frame is None or str(leg["side"]) != "long":
                continue
            entry_time = pd.Timestamp(leg["entry_time"])
            exit_time = leg.get("exit_time")
            window = frame.loc[frame.index >= entry_time]
            if exit_time is not None:
                window = window.loc[window.index <= pd.Timestamp(exit_time)]
            if window.empty:
                continue
            low = float(window["low"].min())
            entry_price = float(leg["entry_price"])
            mae = low / entry_price - 1.0
            liquidation_price = liquidation_prices.get((asset, entry_time))
            headroom = (
                None
                if liquidation_price is None or entry_price <= 0.0
                else float(liquidation_price / entry_price - 1.0)
            )
            leg_rows.append(
                {
                    "leverage": leverage,
                    "asset": asset,
                    "entry_time": entry_time,
                    "exit_time": exit_time,
                    "entry_price": entry_price,
                    "worst_mark_low": low,
                    "max_adverse_excursion": mae,
                    "liquidation_price": liquidation_price,
                    "liquidation_distance": headroom,
                }
            )
            worst_mae = min(worst_mae, mae)
        metrics = _metrics_from_returns(result.daily_returns)
        summary_rows.append(
            {
                "leverage": leverage,
                "legs": int(sum(1 for row in leg_rows if row["leverage"] == leverage)),
                "liquidations": int(len(result.liquidations)),
                "mark_carries": int(len(result.mark_carries)),
                "max_mark_carry_hours": (
                    float(result.mark_carries["hours"].max()) if len(result.mark_carries) else 0.0
                ),
                "worst_leg_mae": worst_mae,
                **metrics,
            }
        )

    legs = pd.DataFrame(leg_rows)
    summary = pd.DataFrame(summary_rows)
    pnl = _asset_pnl(result.trades)
    output_dir = ensure_dir(args.output_dir)
    legs.to_csv(output_dir / "leg_adverse_excursions.csv", index=False)
    summary.to_csv(output_dir / "summary.csv", index=False)
    pnl.to_csv(output_dir / "asset_pnl.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(summary_rows, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    worst = legs.sort_values("max_adverse_excursion").head(15)
    lines = [
        "# Derivatives Leg Risk",
        "",
        f"- window: {args.start_date} → {args.end_date} (exclusive), cost {args.cost_bps} bps, long buffer {args.long_buffer}",
        "- `max_adverse_excursion` = worst mark low while the leg was open / entry price − 1",
        "- `liquidation_distance` = liquidation price / entry price − 1 (isolated margin)",
        "",
        "## Per leverage",
        "",
        dataframe_to_markdown(summary),
        "",
        "## Worst 15 legs",
        "",
        dataframe_to_markdown(worst),
        "",
        "## Realised P&L by asset (last leverage run)",
        "",
        dataframe_to_markdown(pnl.head(15)),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(summary.to_string(index=False))
    print(pnl.head(10).to_string(index=False))
    print(f"Wrote leg risk diagnostics to {output_dir}")


if __name__ == "__main__":
    main()
