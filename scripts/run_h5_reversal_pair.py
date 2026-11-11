"""Run the pre-registered LS19 H5 + 28D reversal-pair research trial.

Research only. This script never routes orders and never changes the live book.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.derivatives.signals import (  # noqa: E402
    build_cross_sectional_reversal_pair_schedule,
    combine_sleeve_targets_by_total_gross_with_audit,
    scale_long_targets,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
    _short_mark_available,
)
from scripts.run_h5_exit_short import _as_utc  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

BASELINE_ID = "PR2026-10-D-L125"
LS19_ID = "PR2026-11-LS19-H5-REVERSAL-PAIR"
SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-reversal-pair-design.md"
LS19_CONFIG: dict[str, Any] = {
    "h5_leverage": 1.25,
    "max_total_gross": 1.50,
    "long_buffer": 0.50,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
    "lookback_days": 28,
    "rebalance_days": 28,
    "count": 4,
    "per_asset_weight": 0.025,
    "min_assets": 8,
}
CONSTRUCTION = (
    "H5 1.25x long book plus a market-neutral 28D reversal sleeve: long the "
    "four weakest PIT Top20 non-H5 assets and short the four strongest, each "
    "at 2.5% NAV; monthly rebalance; total gross <=1.50x"
)


def _write_signed_schedule(path: Path, schedule: Mapping[pd.Timestamp, pd.Series]) -> None:
    rows = [
        {"date": date, "asset": str(asset), "weight": float(weight)}
        for date, target in sorted(schedule.items())
        for asset, weight in target.items()
        if abs(float(weight)) > 1e-15
    ]
    pd.DataFrame(rows, columns=["date", "asset", "weight"]).to_csv(path, index=False)


def build_reversal_targets(
    *,
    market: Any,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    h5_targets: Mapping[pd.Timestamp, pd.Series],
    available: set[str],
    mark_candles: dict[str, pd.DataFrame],
    start_date: str,
) -> tuple[dict[pd.Timestamp, pd.Series], dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Build the signed reversal sleeve and combine it with the H5 book."""
    factor = build_cross_sectional_reversal_pair_schedule(
        market.price,
        universe,
        h5_targets,
        calendar=index,
        eligible=available,
        trade_available=lambda asset, date: _short_mark_available(mark_candles, asset, date),
        lookback=int(LS19_CONFIG["lookback_days"]),
        rebalance_days=int(LS19_CONFIG["rebalance_days"]),
        count=int(LS19_CONFIG["count"]),
        per_asset_weight=float(LS19_CONFIG["per_asset_weight"]),
        min_assets=int(LS19_CONFIG["min_assets"]),
        anchor=start_date,
    )
    combined, audit = combine_sleeve_targets_by_total_gross_with_audit(
        {"h5": (h5_targets, 1.0), "reversal": (factor, 1.0)},
        max_gross=float(LS19_CONFIG["max_total_gross"]),
    )
    return factor, combined, audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", choices=(BASELINE_ID, LS19_ID), required=True)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_20261009"))
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--funding-source", choices=("zero", "binance-proxy", "bitget-exact"), default="binance-proxy")
    parser.add_argument("--funding-stress", choices=("none", "long-adverse", "short-adverse"), default="none")
    parser.add_argument("--funding-multiplier", type=float, default=1.0)
    parser.add_argument("--funding-missing-policy", choices=("error", "skip", "carry_last", "stress_median"), default="skip")
    parser.add_argument("--missing-mark-policy", choices=("error", "carry", "exit_last"), default="carry")
    parser.add_argument("--missing-mark-max-carry-hours", type=int, default=3)
    args = parser.parse_args()
    configure_logging("ERROR")

    _, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_raw = _long_targets_from_build(built, index)
    symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, symbol_map)
    available = set(mark_candles)
    restricted, dropped = _restrict_targets(long_raw, available, mark_candles)
    long_targets = scale_long_targets(
        restricted,
        leverage=float(LS19_CONFIG["h5_leverage"]),
        max_gross=float(LS19_CONFIG["h5_leverage"]),
    )
    funding = _funding_for_source(
        args.funding_source,
        raw_dir=args.raw_dir,
        binance_dir=args.binance_funding_dir,
        symbol_map=symbol_map,
        coins=set(market.price.columns),
    )
    if not funding.empty:
        funding = funding.dropna(how="all").loc[:, funding.notna().any(axis=0)]
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in symbol_map.columns:
        for record in symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)

    factor_schedule: dict[pd.Timestamp, pd.Series] = {}
    target_audit = pd.DataFrame()
    if args.trial_id == LS19_ID:
        factor_schedule, combined, target_audit = build_reversal_targets(
            market=market,
            universe=universe,
            index=index,
            h5_targets=long_targets,
            available=available,
            mark_candles=mark_candles,
            start_date=args.start_date,
        )
    else:
        combined = long_targets
        target_audit = pd.DataFrame(
            [
                {
                    "date": date,
                    "long_gross": float(target.sum()),
                    "short_gross": 0.0,
                    "total_gross": float(target.sum()),
                    "net_gross": float(target.sum()),
                    "scale": 1.0,
                    "scaled_total_gross": float(target.sum()),
                    "scaled_net_gross": float(target.sum()),
                }
                for date, target in long_targets.items()
            ]
        ).set_index("date")

    cfg = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(LS19_CONFIG["long_buffer"]),
        short_buffer=float(LS19_CONFIG["short_buffer"]),
        short_stop_loss_pct=float(LS19_CONFIG["short_stop_loss_pct"]),
        max_gross_exposure=float(LS19_CONFIG["max_total_gross"]),
        funding_missing_policy=args.funding_missing_policy,
        funding_stress=args.funding_stress,
        funding_multiplier=float(args.funding_multiplier),
        missing_mark_policy=args.missing_mark_policy,
        missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
    )
    result = run_derivative_backtest(
        mark_candles,
        combined,
        funding_rates=funding if not funding.empty else None,
        funding_intervals_hours=funding_intervals if not funding.empty else None,
        config=cfg,
        start_time=pd.Timestamp(args.start_date, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )
    metrics = _metrics_from_returns(result.daily_returns)
    trades = result.trades
    short_side = trades.get("side", pd.Series(dtype=object)) == "short"
    stop_reason = trades.get("reason", pd.Series(dtype=object)) == "stop_loss"
    target_total = (
        target_audit["scaled_total_gross"]
        if not target_audit.empty
        else pd.Series(dtype=float)
    )
    summary = {
        "trial_id": args.trial_id,
        "baseline": args.trial_id == BASELINE_ID,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": float(args.cost_bps),
        "funding_source": args.funding_source,
        "funding_stress": args.funding_stress,
        "funding_multiplier": float(args.funding_multiplier),
        "funding_missing_policy": args.funding_missing_policy,
        "mark_source": "bitget_mark",
        "missing_mark_policy": args.missing_mark_policy,
        "missing_mark_max_carry_hours": int(args.missing_mark_max_carry_hours),
        "h5_leverage": float(LS19_CONFIG["h5_leverage"]),
        "max_total_gross": float(LS19_CONFIG["max_total_gross"]),
        "reversal_lookback_days": int(LS19_CONFIG["lookback_days"]),
        "reversal_rebalance_days": int(LS19_CONFIG["rebalance_days"]),
        "reversal_count": int(LS19_CONFIG["count"]),
        "reversal_per_asset_weight": float(LS19_CONFIG["per_asset_weight"]),
        "factor_event_count": int(len(factor_schedule)),
        "max_requested_short_gross": (
            float(target_audit["short_gross"].max()) if not target_audit.empty else 0.0
        ),
        "max_target_total_gross": float(target_total.max()) if not target_total.empty else 0.0,
        "max_observed_gross": float(result.gross_exposure.max()) if not result.gross_exposure.empty else 0.0,
        "gross_breach_hours": int((result.gross_exposure > float(LS19_CONFIG["max_total_gross"]) + 1e-12).sum()),
        "short_open_count": int((short_side & (trades.get("action") == "open")).sum()) if not trades.empty else 0,
        "stop_loss_count": int((short_side & stop_reason).sum()) if not trades.empty else 0,
        "liquidation_count": int(len(result.liquidations)),
        "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
        "fees_total": float(trades["fee"].sum()) if not trades.empty else 0.0,
        "dropped_target_rows": int(len(dropped)),
        "available_mark_count": int(len(mark_candles)),
        **metrics,
    }
    output_dir = ensure_dir(Path(args.output_dir) / args.trial_id)
    result.equity_curve.to_csv(output_dir / "equity_curve.csv", header=True)
    result.daily_returns.to_csv(output_dir / "daily_returns.csv", header=True)
    result.trades.to_csv(output_dir / "trades.csv", index=False)
    result.funding.to_csv(output_dir / "funding.csv", index=False)
    result.liquidations.to_csv(output_dir / "liquidations.csv", index=False)
    result.positions.to_csv(output_dir / "positions.csv", index=False)
    result.gross_exposure.to_csv(output_dir / "gross_exposure.csv", header=True)
    target_audit.to_csv(output_dir / "target_gross.csv", index=True)
    _write_signed_schedule(output_dir / "reversal_schedule.csv", factor_schedule)
    dropped.to_csv(output_dir / "dropped_targets.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "trial_id": args.trial_id,
                "window": "main",
                "fill": "lag0",
                "cost_bps": float(args.cost_bps),
                "sharpe": metrics["sharpe"],
                "multiple": metrics["multiple"],
                "max_drawdown": metrics["max_drawdown"],
                "source": str(output_dir / "summary.json"),
            }
        ]
    ).to_csv(output_dir / "trial_results.csv", index=False)
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "candidate_id": args.trial_id,
                "baseline": args.trial_id == BASELINE_ID,
                "spec": SPEC_PATH if args.trial_id == LS19_ID else "",
                "construction": "H5 1.25x long-only" if args.trial_id == BASELINE_ID else CONSTRUCTION,
                "frozen_config": LS19_CONFIG,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "cost_bps": float(args.cost_bps),
                "funding_source": args.funding_source,
                "funding_stress": args.funding_stress,
                "funding_multiplier": float(args.funding_multiplier),
                "mark_source": "bitget_mark",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                f"# {args.trial_id}",
                "",
                f"- Window: {args.start_date} to {args.end_date}",
                f"- Cost: {float(args.cost_bps):g} bps",
                f"- Terminal multiple: {metrics['multiple']:.4f}x",
                f"- Sharpe: {metrics['sharpe']:.4f}",
                f"- Max drawdown: {metrics['max_drawdown']:.4%}",
                f"- Max requested short gross: {summary['max_requested_short_gross']:.6f}x",
                f"- Max target total gross: {summary['max_target_total_gross']:.6f}x",
                f"- Max observed gross: {summary['max_observed_gross']:.6f}x",
                f"- Gross breach hours: {summary['gross_breach_hours']}",
                f"- Liquidations: {summary['liquidation_count']}",
                f"- Short stop-losses: {summary['stop_loss_count']}",
                "",
                "Research output only; not an order or a live approval.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    print(f"Wrote H5 reversal-pair research output to {output_dir}")


if __name__ == "__main__":
    main()
