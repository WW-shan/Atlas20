"""Run the pre-registered H5 exit + weak-four fixed-risk short trial.

This is a research-only runner. It combines two short sleeves with the frozen
H5 long book, uses only unused gross, and never routes orders.
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
from atlas20.derivatives.signals import (  # noqa: E402
    EXIT_SHORT_HOLDING_DAYS,
    build_cross_sectional_weak_short_schedule,
    build_exit_short_schedule,
    combine_fixed_risk_short_schedules,
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
    _eligible_members_by_date,
    _funding_tag,
    _run_one,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402

CANDIDATE_ID = "PR2026-11-LS5-H5-EXIT-WEAK4-RISK05"
BASELINE_ID = "PR2026-11-LS5-H5-BASELINE"
SPEC_PATH = (
    "docs/superpowers/specs/2026-11-11-h5-exit-weak4-risk-combo-design.md"
)
FROZEN_CONFIG: dict[str, Any] = {
    "exit_short_holding_days": EXIT_SHORT_HOLDING_DAYS,
    "max_total_gross": 0.95,
    "hard_gross": 1.00,
    "long_buffer": 0.75,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
    "short_risk_per_trade": 0.005,
    "short_per_asset_weight": 0.025,
    "cross_sectional_lookback": 14,
    "cross_sectional_rebalance_days": 7,
    "cross_sectional_short_count": 4,
    "cross_sectional_funding_threshold": -0.0002,
    "cross_sectional_funding_lookback": 3,
}
CONSTRUCTION = (
    "H5 1.0x + fixed-risk 21-day exit shorts + weekly 14D weakest-four "
    "shorts, union by asset, funded only by unused gross"
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
        default=Path("reports/derivatives_track_h5_exit_weak4_risk"),
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
        exit_short: dict[pd.Timestamp, pd.Series] = {}
        weak_short: dict[pd.Timestamp, pd.Series] = {}
        short_targets: dict[pd.Timestamp, pd.Series] = {}
    else:
        eligible = _eligible_members_by_date(universe, list(h5_raw))
        exit_raw = build_exit_short_schedule(
            h5_raw,
            holding_days=int(FROZEN_CONFIG["exit_short_holding_days"]),
            eligible_by_date=eligible,
            per_asset_weight=float(FROZEN_CONFIG["short_per_asset_weight"]),
        )
        exit_short, _ = _restrict_targets(exit_raw, available, mark_candles)
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
        short_targets = combine_fixed_risk_short_schedules(
            {"exit": exit_short, "weak4": weak_short},
            per_asset_weight=float(FROZEN_CONFIG["short_per_asset_weight"]),
        )

    summary = _run_one(
        args=args,
        mark_candles=mark_candles,
        funding=funding if not funding.empty else None,
        funding_intervals=funding_intervals,
        h5_targets=h5_targets,
        short_targets=short_targets,
        trial_id=trial_id,
        baseline=bool(args.baseline),
        frozen_config=FROZEN_CONFIG,
        spec_path=SPEC_PATH,
    )

    if not args.baseline:
        tag = _funding_tag(
            args.funding_source,
            args.funding_stress,
            float(args.funding_multiplier),
        )
        run_dir = ensure_dir(
            Path(args.output_dir)
            / f"{trial_id}_cost{float(args.cost_bps):g}_{tag}"
        )
        _write_schedule(run_dir / "exit_short_schedule.csv", exit_short)
        _write_schedule(run_dir / "weak4_short_schedule.csv", weak_short)
        _write_schedule(run_dir / "combined_short_schedule.csv", short_targets)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
