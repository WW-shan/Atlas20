"""Run the pre-registered H5 + H4 cash-sleeve minus sector short research trial.

This is a research runner only. It never writes live targets, never changes the
H5 ledger, and never routes orders. The exact candidate is defined in
``docs/superpowers/specs/2026-11-11-long-short-cash-sleeve-design.md``.
"""

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
from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.derivatives.signals import build_cash_sleeve_targets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.signals.regime import build_regime_frame  # noqa: E402
from atlas20.signals.risk import absolute_trend_mask  # noqa: E402
from atlas20.strategies.overlays import apply_daily_asset_stop_overlay  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _has_execution_mark,
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_no_leverage_ablation import BaseSpec, build_base_targets  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

CANDIDATE_ID = "PR2026-11-LS1-H5-H4-SECTOR20"
BASELINE_ID = "PR2026-11-LS1-H5-BASELINE"
FROZEN_CONFIG: dict[str, Any] = {
    "h4_weight": 0.20,
    "sector_short_weight": 0.20,
    "max_gross": 0.95,
    "hard_gross": 1.00,
    "long_buffer": 0.75,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
}
SECTOR_SPEC = BaseSpec(
    "SECTOR_LEAD_top2",
    "sector_lead",
    "sector_lead",
    "14D",
    "bull_only",
    top_n=2,
    concentrated=True,
)


def _build_sector_targets(
    config: Any,
    market: Any,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
) -> dict[pd.Timestamp, pd.Series]:
    """Build the failed long-only sector strategy used as a short basket."""
    regime = build_regime_frame(market.price, market.market_cap, config)
    targets = build_base_targets(SECTOR_SPEC, market, universe, regime, config)
    trend = absolute_trend_mask(market.price, ma_window=50)
    adjusted = apply_daily_asset_stop_overlay(targets, trend)
    return {
        pd.Timestamp(date): pd.to_numeric(target, errors="coerce").fillna(0.0)
        for date, target in adjusted.items()
    }


def _restrict_mark_targets(
    targets: dict[pd.Timestamp, pd.Series],
    *,
    available: set[str],
    mark_candles: dict[str, pd.DataFrame],
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Drop assets whose Bitget execution mark is unavailable, without renormalising."""
    return _restrict_targets(targets, available, mark_candles)


def _funding_tag(source: str, stress: str, multiplier: float) -> str:
    if source == "zero":
        return "zero"
    if stress == "none" and multiplier == 1.0:
        return "proxy"
    return f"{stress}_x{multiplier:g}".replace("-", "_")


def _run_one(
    *,
    args: argparse.Namespace,
    market: Any,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    mark_candles: dict[str, pd.DataFrame],
    funding: pd.DataFrame | None,
    funding_intervals: dict[str, float],
    h5_targets: dict[pd.Timestamp, pd.Series],
    h4_targets: dict[pd.Timestamp, pd.Series],
    sector_targets: dict[pd.Timestamp, pd.Series],
    trial_id: str,
    baseline: bool,
) -> dict[str, Any]:
    """Run one candidate or baseline and write its complete research output."""
    if baseline:
        combined = build_cash_sleeve_targets(h5_targets, {}, {})
        h4_weight = 0.0
        sector_short_weight = 0.0
    else:
        combined = build_cash_sleeve_targets(h5_targets, h4_targets, sector_targets)
        h4_weight = float(FROZEN_CONFIG["h4_weight"])
        sector_short_weight = float(FROZEN_CONFIG["sector_short_weight"])

    config = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(FROZEN_CONFIG["long_buffer"]),
        short_buffer=float(FROZEN_CONFIG["short_buffer"]),
        short_stop_loss_pct=float(FROZEN_CONFIG["short_stop_loss_pct"]),
        max_gross_exposure=float(FROZEN_CONFIG["max_gross"]),
        max_margin_utilization=0.85,
        funding_missing_policy=args.funding_missing_policy,
        funding_stress=args.funding_stress,
        funding_multiplier=float(args.funding_multiplier),
        missing_mark_policy=args.missing_mark_policy,
        missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
    )
    result = run_derivative_backtest(
        mark_candles,
        combined,
        funding_rates=funding,
        funding_intervals_hours=funding_intervals,
        config=config,
        start_time=pd.Timestamp(args.start_date, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )
    metrics = _metrics_from_returns(result.daily_returns)
    target_gross = pd.Series(
        {
            str(date): float(target.abs().sum())
            for date, target in combined.items()
        },
        dtype=float,
    )
    observed_gross = result.gross_exposure.astype(float)
    stop_losses = (
        int((result.trades.get("reason") == "stop_loss").sum())
        if not result.trades.empty
        else 0
    )
    summary = {
        "trial_id": trial_id,
        "baseline": baseline,
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
        "h5_weight": 1.0,
        "h4_weight": h4_weight,
        "sector_short_weight": sector_short_weight,
        "target_gross_cap": float(FROZEN_CONFIG["max_gross"]),
        "hard_gross_cap": float(FROZEN_CONFIG["hard_gross"]),
        "target_event_count": int(len(combined)),
        "max_target_gross": float(target_gross.max()) if not target_gross.empty else 0.0,
        "avg_target_gross": float(target_gross.mean()) if not target_gross.empty else 0.0,
        "max_gross_exposure": float(observed_gross.max()) if not observed_gross.empty else 0.0,
        "avg_gross_exposure": float(observed_gross.mean()) if not observed_gross.empty else 0.0,
        "observed_gross_over_one": bool((observed_gross > 1.0 + 1e-12).any()),
        "liquidation_count": int(len(result.liquidations)),
        "stop_loss_count": stop_losses,
        "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
        "fees_total": float(result.trades["fee"].sum()) if not result.trades.empty else 0.0,
        "available_mark_count": int(len(mark_candles)),
        **metrics,
    }

    tag = _funding_tag(args.funding_source, args.funding_stress, float(args.funding_multiplier))
    run_dir = ensure_dir(
        Path(args.output_dir) / f"{trial_id}_cost{float(args.cost_bps):g}_{tag}"
    )
    result.equity_curve.to_csv(run_dir / "equity_curve.csv", header=True)
    result.daily_returns.to_csv(run_dir / "daily_returns.csv", header=True)
    result.gross_exposure.to_csv(run_dir / "gross_exposure.csv", header=True)
    result.trades.to_csv(run_dir / "trades.csv", index=False)
    result.funding.to_csv(run_dir / "funding.csv", index=False)
    result.liquidations.to_csv(run_dir / "liquidations.csv", index=False)
    target_gross.to_csv(run_dir / "target_gross.csv", header=True)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    trial_results = pd.DataFrame(
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
    )
    trial_results.to_csv(run_dir / "trial_results.csv", index=False)
    manifest = {
        "candidate_id": trial_id,
        "baseline": baseline,
        "spec": "docs/superpowers/specs/2026-11-11-long-short-cash-sleeve-design.md",
        "construction": "1.0*w_H5 + 0.2*w_H4 - 0.2*w_SECTOR_LEAD_top2__asset_ma50"
        if not baseline
        else "1.0*w_H5",
        "frozen_config": FROZEN_CONFIG,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": float(args.cost_bps),
        "funding_source": args.funding_source,
        "funding_stress": args.funding_stress,
        "funding_multiplier": float(args.funding_multiplier),
        "funding_missing_policy": args.funding_missing_policy,
        "mark_source": "bitget_mark",
        "target_events": int(len(combined)),
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
                f"- Funding: `{args.funding_source}`, stress `{args.funding_stress}` x {float(args.funding_multiplier):g}",
                f"- Terminal multiple: {metrics['multiple']:.4f}x",
                f"- Sharpe: {metrics['sharpe']:.4f}",
                f"- Max drawdown: {metrics['max_drawdown']:.4%}",
                f"- Max observed gross: {summary['max_gross_exposure']:.6f}x",
                f"- Liquidations: {summary['liquidation_count']}",
                f"- Short stop-losses: {summary['stop_loss_count']}",
                f"- Funding total: {summary['funding_total']:.6f}",
                f"- Fees total: {summary['fees_total']:.6f}",
                "",
                "Research output only; not an order or a live approval.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/derivatives_track_long_short_cash_sleeve"),
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/bitget_derivatives/merged_20261009"),
    )
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
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
    if args.baseline:
        trial_id = BASELINE_ID
    else:
        trial_id = CANDIDATE_ID

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    raw_dir = Path(args.raw_dir)
    symbol_map = pd.read_csv(raw_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(raw_dir, symbol_map)
    available = set(mark_candles)

    h5_built = build_trial(trial_by_id("PR2026-10-H5"), market, universe, index)
    h5_raw = _long_targets_from_build(h5_built, index)
    h5_targets, _ = _restrict_mark_targets(h5_raw, available=available, mark_candles=mark_candles)

    if args.baseline:
        h4_targets = {}
        sector_targets = {}
    else:
        h4_built = build_trial(trial_by_id("PR2026-10-H4"), market, universe, index)
        h4_raw = _long_targets_from_build(h4_built, index)
        h4_targets, _ = _restrict_mark_targets(
            h4_raw, available=available, mark_candles=mark_candles
        )
        sector_raw = _build_sector_targets(config, market, universe, index)
        sector_targets, _ = _restrict_mark_targets(
            sector_raw, available=available, mark_candles=mark_candles
        )

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

    summary = _run_one(
        args=args,
        market=market,
        universe=universe,
        index=index,
        mark_candles=mark_candles,
        funding=funding if not funding.empty else None,
        funding_intervals=funding_intervals,
        h5_targets=h5_targets,
        h4_targets=h4_targets,
        sector_targets=sector_targets,
        trial_id=trial_id,
        baseline=bool(args.baseline),
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
