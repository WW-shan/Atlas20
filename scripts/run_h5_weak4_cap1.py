"""Run the pre-registered H5 0.8x + weak-four 0.25x no-leverage trial."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

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
from atlas20.derivatives.signals import (  # noqa: E402
    build_cross_sectional_weak_short_schedule,
    combine_sleeve_targets_by_total_gross_with_audit,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
    _short_mark_available,
)
from scripts.run_h5_exit_short import (  # noqa: E402
    _available_mark_assets,
    _funding_tag,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

CANDIDATE_ID = "PR2026-11-LS7-H5-WEAK4-CAP1"
BASELINE_ID = "PR2026-11-LS7-H5-BASELINE"
SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-weak4-cap1-design.md"
FROZEN_CONFIG: dict[str, Any] = {
    "h5_long_weight": 0.80,
    "short_total_weight": 0.25,
    "short_per_asset_weight": 0.0625,
    "cross_sectional_lookback": 14,
    "cross_sectional_rebalance_days": 7,
    "cross_sectional_short_count": 4,
    "cross_sectional_funding_threshold": -0.0002,
    "cross_sectional_funding_lookback": 3,
    "short_stop_loss_pct": 0.20,
    "max_total_gross": 0.95,
    "hard_gross": 1.00,
    "long_buffer": 0.75,
    "short_buffer": 0.50,
}
CONSTRUCTION = (
    "H5 0.8x long + 0.25x weekly 14D weakest-four short basket, total gross "
    "capped at 0.95 before broker netting"
)


def _write_schedule(path: Path, schedule: dict[pd.Timestamp, pd.Series]) -> None:
    rows = [
        {"date": date, "asset": str(asset), "weight": float(weight)}
        for date, target in sorted(schedule.items())
        for asset, weight in target.items()
        if abs(float(weight)) > 1e-15
    ]
    pd.DataFrame(rows, columns=["date", "asset", "weight"]).to_csv(
        path, index=False
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/derivatives_track_h5_weak4_cap1"),
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/bitget_derivatives/merged_20261009"),
    )
    parser.add_argument(
        "--binance-funding-dir",
        type=Path,
        default=Path("data/raw/binance_funding"),
    )
    parser.add_argument(
        "--funding-source",
        choices=("zero", "binance-proxy", "bitget-exact"),
        default="binance-proxy",
    )
    parser.add_argument(
        "--funding-stress",
        choices=("none", "long-adverse", "short-adverse"),
        default="none",
    )
    parser.add_argument("--funding-multiplier", type=float, default=1.0)
    parser.add_argument(
        "--funding-missing-policy",
        choices=("error", "skip", "carry_last", "stress_median"),
        default="skip",
    )
    parser.add_argument(
        "--missing-mark-policy",
        choices=("error", "carry", "exit_last"),
        default="carry",
    )
    parser.add_argument("--missing-mark-max-carry-hours", type=int, default=3)
    args = parser.parse_args()

    configure_logging("ERROR")
    trial_id = BASELINE_ID if args.baseline else CANDIDATE_ID
    args.trial_id = trial_id
    args.construction = CONSTRUCTION

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    raw_dir = Path(args.raw_dir)
    symbol_map = pd.read_csv(raw_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(raw_dir, symbol_map)
    available = _available_mark_assets(mark_candles)

    h5_built = build_trial(trial_by_id("PR2026-10-H5"), market, universe, index)
    h5_raw = _long_targets_from_build(h5_built, index)
    h5_targets, _ = _restrict_targets(h5_raw, available, mark_candles)

    funding = _funding_for_source(
        args.funding_source,
        raw_dir=raw_dir,
        binance_dir=Path(args.binance_funding_dir),
        symbol_map=symbol_map,
        coins=set(market.price.columns),
    )
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in symbol_map.columns:
        for record in symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)

    if args.baseline:
        weak_short: dict[pd.Timestamp, pd.Series] = {}
        combined_targets, target_audit = (
            combine_sleeve_targets_by_total_gross_with_audit(
                {"h5": (h5_targets, 1.0)},
                max_gross=float(FROZEN_CONFIG["max_total_gross"]),
            )
        )
    else:
        weak_short = build_cross_sectional_weak_short_schedule(
            market.price,
            universe,
            h5_targets,
            calendar=index,
            funding_rates=funding if not funding.empty else None,
            eligible=available,
            short_available=lambda asset, date: _short_mark_available(
                mark_candles, asset, date
            ),
            lookback=int(FROZEN_CONFIG["cross_sectional_lookback"]),
            rebalance_days=int(FROZEN_CONFIG["cross_sectional_rebalance_days"]),
            short_count=int(FROZEN_CONFIG["cross_sectional_short_count"]),
            per_asset_weight=float(FROZEN_CONFIG["short_per_asset_weight"]),
            funding_threshold=float(
                FROZEN_CONFIG["cross_sectional_funding_threshold"]
            ),
            funding_lookback=int(
                FROZEN_CONFIG["cross_sectional_funding_lookback"]
            ),
            anchor=args.start_date,
        )
        combined_targets, target_audit = (
            combine_sleeve_targets_by_total_gross_with_audit(
                {
                    "h5": (
                        h5_targets,
                        float(FROZEN_CONFIG["h5_long_weight"]),
                    ),
                    "weak4": (weak_short, -1.0),
                },
                max_gross=float(FROZEN_CONFIG["max_total_gross"]),
            )
        )

    max_target_total = float(target_audit["scaled_total_gross"].max())
    if max_target_total > float(FROZEN_CONFIG["hard_gross"]) + 1e-12:
        raise ValueError(
            f"target total gross {max_target_total:.12f} exceeds hard cap"
        )

    cfg = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(FROZEN_CONFIG["long_buffer"]),
        short_buffer=float(FROZEN_CONFIG["short_buffer"]),
        short_stop_loss_pct=float(FROZEN_CONFIG["short_stop_loss_pct"]),
        max_gross_exposure=float(FROZEN_CONFIG["max_total_gross"]),
        hard_gross_exposure=float(FROZEN_CONFIG["hard_gross"]),
        max_margin_utilization=0.85,
        funding_missing_policy=args.funding_missing_policy,
        funding_stress=args.funding_stress,
        funding_multiplier=float(args.funding_multiplier),
        missing_mark_policy=args.missing_mark_policy,
        missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
    )
    result = run_derivative_backtest(
        mark_candles,
        combined_targets,
        funding_rates=funding if not funding.empty else None,
        funding_intervals_hours=funding_intervals,
        config=cfg,
        start_time=pd.Timestamp(args.start_date, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )
    metrics = _metrics_from_returns(result.daily_returns)
    observed_gross = result.gross_exposure.astype(float)
    trades = result.trades
    stop_losses = (
        int((trades.get("reason") == "stop_loss").sum())
        if not trades.empty
        else 0
    )
    guard_reductions = (
        int((trades.get("reason") == "gross_guard").sum())
        if not trades.empty
        else 0
    )
    short_opens = (
        int(
            (
                (trades.get("side") == "short")
                & (trades.get("action") == "open")
            ).sum()
        )
        if not trades.empty
        else 0
    )
    summary = {
        "trial_id": trial_id,
        "baseline": args.baseline,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": float(args.cost_bps),
        "funding_source": args.funding_source,
        "funding_stress": args.funding_stress,
        "funding_multiplier": float(args.funding_multiplier),
        "funding_missing_policy": args.funding_missing_policy,
        "mark_source": "bitget_mark",
        "h5_long_weight": 1.0
        if args.baseline
        else float(FROZEN_CONFIG["h5_long_weight"]),
        "short_total_weight": 0.0
        if args.baseline
        else float(FROZEN_CONFIG["short_total_weight"]),
        "max_total_gross_cap": float(FROZEN_CONFIG["max_total_gross"]),
        "hard_total_gross_cap": float(FROZEN_CONFIG["hard_gross"]),
        "target_event_count": int(len(combined_targets)),
        "max_target_long_gross": float(target_audit["long_gross"].max()),
        "max_target_short_gross": float(target_audit["short_gross"].max()),
        "max_target_total_gross": max_target_total,
        "avg_target_total_gross": float(target_audit["total_gross"].mean()),
        "max_gross_exposure": float(observed_gross.max())
        if not observed_gross.empty
        else 0.0,
        "avg_gross_exposure": float(observed_gross.mean())
        if not observed_gross.empty
        else 0.0,
        "observed_gross_over_one": bool(
            (
                observed_gross
                > float(FROZEN_CONFIG["hard_gross"]) + 1e-12
            ).any()
        ),
        "observed_gross_breach_hours": int(
            (
                observed_gross
                > float(FROZEN_CONFIG["hard_gross"]) + 1e-12
            ).sum()
        ),
        "gross_guard_reduction_count": guard_reductions,
        "target_scale_count": int(
            (target_audit["scale"] < 1.0 - 1e-12).sum()
        ),
        "short_open_count": short_opens,
        "liquidation_count": int(len(result.liquidations)),
        "stop_loss_count": stop_losses,
        "funding_total": float(result.funding["amount"].sum())
        if not result.funding.empty
        else 0.0,
        "fees_total": float(trades["fee"].sum()) if not trades.empty else 0.0,
        "available_mark_count": int(len(mark_candles)),
        **metrics,
    }

    tag = _funding_tag(
        args.funding_source,
        args.funding_stress,
        float(args.funding_multiplier),
    )
    run_dir = ensure_dir(
        Path(args.output_dir)
        / f"{trial_id}_cost{float(args.cost_bps):g}_{tag}"
    )
    result.equity_curve.to_csv(run_dir / "equity_curve.csv", header=True)
    result.daily_returns.to_csv(run_dir / "daily_returns.csv", header=True)
    result.gross_exposure.to_csv(run_dir / "gross_exposure.csv", header=True)
    result.trades.to_csv(run_dir / "trades.csv", index=False)
    result.funding.to_csv(run_dir / "funding.csv", index=False)
    result.liquidations.to_csv(run_dir / "liquidations.csv", index=False)
    result.positions.to_csv(run_dir / "positions.csv", index=False)
    result.mark_carries.to_csv(run_dir / "mark_carries.csv", index=False)
    result.fill_downgrades.to_csv(run_dir / "fill_downgrades.csv", index=False)
    target_audit.to_csv(run_dir / "target_gross.csv", index_label="date")
    _write_schedule(run_dir / "combined_targets.csv", combined_targets)
    if not args.baseline:
        _write_schedule(run_dir / "weak4_short_schedule.csv", weak_short)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "trial_id": trial_id,
                "window": "main",
                "fill": "lag0",
                "cost_bps": float(args.cost_bps),
                "sharpe": metrics["sharpe"],
                "multiple": metrics["multiple"],
                "max_drawdown": metrics["max_drawdown"],
                "source": str(run_dir / "summary.json"),
            }
        ]
    ).to_csv(run_dir / "trial_results.csv", index=False)
    manifest = {
        "candidate_id": trial_id,
        "baseline": args.baseline,
        "spec": SPEC_PATH,
        "construction": "H5 1.0x" if args.baseline else CONSTRUCTION,
        "frozen_config": FROZEN_CONFIG,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": float(args.cost_bps),
        "funding_source": args.funding_source,
        "funding_stress": args.funding_stress,
        "funding_multiplier": float(args.funding_multiplier),
        "funding_missing_policy": args.funding_missing_policy,
        "mark_source": "bitget_mark",
        "target_events": int(len(combined_targets)),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text(
        "\n".join(
            [
                f"# {trial_id}",
                "",
                f"- Window: {args.start_date} to {args.end_date}",
                f"- Cost: {float(args.cost_bps):g} bps",
                f"- Funding: `{args.funding_source}`, stress "
                f"`{args.funding_stress}` x {float(args.funding_multiplier):g}",
                f"- Terminal multiple: {metrics['multiple']:.4f}x",
                f"- Sharpe: {metrics['sharpe']:.4f}",
                f"- Max drawdown: {metrics['max_drawdown']:.4%}",
                f"- Max target total gross: {max_target_total:.6f}x",
                f"- Max observed gross: {summary['max_gross_exposure']:.6f}x",
                f"- Observed gross breach hours: {summary['observed_gross_breach_hours']}",
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


if __name__ == "__main__":
    main()
