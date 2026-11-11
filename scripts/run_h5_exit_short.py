"""Run the pre-registered H5 exit-short research trial.

This is a research-only runner. It uses only H5's unused gross budget for
21-day shorts of assets that H5 has just exited, and never routes orders.
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
from atlas20.derivatives.signals import (  # noqa: E402
    EXIT_SHORT_HOLDING_DAYS,
    build_exit_short_schedule,
    combine_long_with_cash_budgeted_short,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

CANDIDATE_ID = "PR2026-11-LS3-H5-EXIT-SHORT21"
BASELINE_ID = "PR2026-11-LS3-H5-BASELINE"
FROZEN_CONFIG: dict[str, Any] = {
    "exit_short_holding_days": EXIT_SHORT_HOLDING_DAYS,
    "max_total_gross": 0.95,
    "hard_gross": 1.00,
    "long_buffer": 0.75,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
}


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _eligible_members_by_date(
    universe: pd.DataFrame,
    dates: list[pd.Timestamp],
) -> dict[pd.Timestamp, set[str]]:
    """Return the latest point-in-time Top20 membership at each requested date."""
    frame = universe.loc[:, ["rebalance_date", "coin_id"]].copy()
    frame["rebalance_date"] = pd.DatetimeIndex(
        [_as_utc(value) for value in frame["rebalance_date"]]
    )
    frame["coin_id"] = frame["coin_id"].astype(str)
    member_dates = pd.DatetimeIndex(sorted(frame["rebalance_date"].unique()))
    members = {
        date: set(group["coin_id"])
        for date, group in frame.groupby("rebalance_date")
    }
    eligible: dict[pd.Timestamp, set[str]] = {}
    for raw_date in dates:
        date = _as_utc(raw_date)
        position = member_dates.searchsorted(date, side="right") - 1
        if position < 0:
            eligible[date] = set()
        else:
            eligible[date] = members[pd.Timestamp(member_dates[position])]
    return eligible


def _available_mark_assets(mark_candles: dict[str, pd.DataFrame]) -> set[str]:
    """Return coin ids for which a mark frame was loaded."""
    return set(mark_candles)


def _funding_tag(source: str, stress: str, multiplier: float) -> str:
    if source == "zero":
        return "zero"
    if stress == "none" and multiplier == 1.0:
        return "proxy"
    return f"{stress}_x{multiplier:g}".replace("-", "_")


def _run_one(
    *,
    args: argparse.Namespace,
    mark_candles: dict[str, pd.DataFrame],
    funding: pd.DataFrame | None,
    funding_intervals: dict[str, float],
    h5_targets: dict[pd.Timestamp, pd.Series],
    short_targets: dict[pd.Timestamp, pd.Series],
    trial_id: str,
    baseline: bool,
) -> dict[str, Any]:
    """Run one candidate or baseline and write its complete research output."""
    combined, target_audit = combine_long_with_cash_budgeted_short(
        h5_targets,
        {} if baseline else short_targets,
        max_total_gross=float(FROZEN_CONFIG["max_total_gross"]),
    )
    max_target_total = float(target_audit["total_gross"].max())
    if max_target_total > float(FROZEN_CONFIG["hard_gross"]) + 1e-12:
        raise ValueError(
            f"target total gross {max_target_total:.12f} exceeds hard cap"
        )

    config = DerivativeBacktestConfig(
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
        combined,
        funding_rates=funding,
        funding_intervals_hours=funding_intervals,
        config=config,
        start_time=pd.Timestamp(args.start_date, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )
    metrics = _metrics_from_returns(result.daily_returns)
    observed_gross = result.gross_exposure.astype(float)
    trades = result.trades
    stop_losses = int((trades.get("reason") == "stop_loss").sum()) if not trades.empty else 0
    guard_reductions = (
        int((trades.get("reason") == "gross_guard").sum()) if not trades.empty else 0
    )
    short_opens = (
        int(((trades.get("side") == "short") & (trades.get("action") == "open")).sum())
        if not trades.empty
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
        "exit_short_holding_days": 0
        if baseline
        else int(FROZEN_CONFIG["exit_short_holding_days"]),
        "target_total_gross_cap": float(FROZEN_CONFIG["max_total_gross"]),
        "hard_total_gross_cap": float(FROZEN_CONFIG["hard_gross"]),
        "target_event_count": int(len(combined)),
        "max_target_long_gross": float(target_audit["long_gross"].max()),
        "max_scaled_target_long_gross": float(target_audit["scaled_long_gross"].max()),
        "max_requested_short_gross": float(target_audit["requested_short_gross"].max()),
        "max_funded_short_gross": float(target_audit["funded_short_gross"].max()),
        "max_target_total_gross": max_target_total,
        "max_target_net_gross": float(target_audit["net_gross"].max()),
        "avg_target_total_gross": float(target_audit["total_gross"].mean()),
        "avg_target_net_gross": float(target_audit["net_gross"].mean()),
        "short_funding_scale_count": int(
            (target_audit["short_scale"] < 1.0 - 1e-12).sum()
        ),
        "long_scale_count": int((target_audit["long_scale"] < 1.0 - 1e-12).sum()),
        "max_gross_exposure": float(observed_gross.max()) if not observed_gross.empty else 0.0,
        "avg_gross_exposure": float(observed_gross.mean()) if not observed_gross.empty else 0.0,
        "observed_gross_over_one": bool(
            (observed_gross > float(FROZEN_CONFIG["hard_gross"]) + 1e-12).any()
        ),
        "observed_gross_breach_hours": int(
            (observed_gross > float(FROZEN_CONFIG["hard_gross"]) + 1e-12).sum()
        ),
        "gross_guard_reduction_count": guard_reductions,
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
        Path(args.output_dir) / f"{trial_id}_cost{float(args.cost_bps):g}_{tag}"
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
        "baseline": baseline,
        "spec": "docs/superpowers/specs/2026-11-11-h5-exit-short-design.md",
        "construction": "H5 1.0x long + 21-day equal-weight short of H5 exits, funded only by unused gross"
        if not baseline
        else "H5 1.0x",
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
                f"- Funding: `{args.funding_source}`, stress "
                f"`{args.funding_stress}` x {float(args.funding_multiplier):g}",
                f"- Terminal multiple: {metrics['multiple']:.4f}x",
                f"- Sharpe: {metrics['sharpe']:.4f}",
                f"- Max drawdown: {metrics['max_drawdown']:.4%}",
                f"- Max target total gross: {max_target_total:.6f}x",
                f"- Max observed Broker gross: {summary['max_gross_exposure']:.6f}x",
                f"- Observed gross breach hours: {summary['observed_gross_breach_hours']}",
                f"- Gross-guard reductions: {summary['gross_guard_reduction_count']}",
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
        default=Path("reports/derivatives_track_h5_exit_short"),
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
    if args.baseline:
        short_targets: dict[pd.Timestamp, pd.Series] = {}
    else:
        eligible = _eligible_members_by_date(universe, list(h5_raw))
        short_raw = build_exit_short_schedule(
            h5_raw,
            holding_days=int(FROZEN_CONFIG["exit_short_holding_days"]),
            eligible_by_date=eligible,
        )
        short_targets, _ = _restrict_targets(short_raw, available, mark_candles)

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
        mark_candles=mark_candles,
        funding=funding if not funding.empty else None,
        funding_intervals=funding_intervals,
        h5_targets=h5_targets,
        short_targets=short_targets,
        trial_id=trial_id,
        baseline=bool(args.baseline),
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
