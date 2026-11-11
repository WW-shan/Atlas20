"""Run the pre-registered H5 relative-momentum risk-budget short trial.

LS10 keeps the LS9 funding-constrained H5 exit shorts and continuous unused
risk budget, but requires the exited asset to be weaker than BTC over 14 days
at the signal close.  Research only; this runner never routes orders.
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
    build_exit_short_schedule,
    funding_rank_percentile,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_h5_exit_short import (  # noqa: E402
    _as_utc,
    _available_mark_assets,
    _eligible_members_by_date,
    _funding_tag,
    _run_one,
)
from scripts.run_h5_riskbudget_funding_exit_short import (  # noqa: E402
    _long_gross_series,
    _scale_schedule_by_long_gross,
    _write_schedule,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402

CANDIDATE_ID = "PR2026-11-LS10-H5-RELMOM14-RISKBUDGET-FUNDING-EXIT"
BASELINE_ID = "PR2026-11-LS10-H5-BASELINE"
SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-relative-momentum-riskbudget-design.md"
FROZEN_CONFIG: dict[str, Any] = {
    "exit_short_holding_days": EXIT_SHORT_HOLDING_DAYS,
    "base_short_per_asset_weight_at_zero_long": 0.05,
    "max_total_gross": 0.95,
    "hard_gross": 1.00,
    "long_buffer": 0.75,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
    "funding_lookback_days": 7,
    "funding_rank_min": 2.0 / 3.0,
    "funding_min_assets": 5,
    "relative_lookback_days": 14,
    "relative_benchmark": "bitcoin",
}
CONSTRUCTION = (
    "H5 1.0x + 7D funding-top-tercile 21-day exit shorts only when the "
    "asset 14D return is below BTC's 14D return; per-leg weight 5% * "
    "max(0, 1 - post-exit H5 target long gross), funded only by unused gross"
)


def _normalized_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Return a numeric price frame with a sorted, unique UTC index."""
    frame = prices.copy()
    frame.index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame.apply(pd.to_numeric, errors="coerce")


def _relative_momentum_allows(
    prices: pd.DataFrame,
    asset: str,
    as_of: pd.Timestamp,
    *,
    lookback_days: int,
    benchmark: str,
) -> bool:
    """Whether ``asset`` underperformed ``benchmark`` over the prior window."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    if asset == benchmark:
        return False
    frame = prices
    if frame.index.tz is None:
        frame = _normalized_prices(frame)
    requested = _as_utc(as_of)
    if asset not in frame.columns or benchmark not in frame.columns:
        return False
    if requested not in frame.index:
        return False
    base_date = requested - pd.Timedelta(days=lookback_days)
    history = frame.loc[frame.index <= base_date, [asset, benchmark]].dropna()
    if history.empty:
        return False
    base = history.iloc[-1]
    current = frame.loc[requested, [asset, benchmark]]
    if current.isna().any() or (base <= 0.0).any():
        return False
    asset_return = float(current[asset] / base[asset] - 1.0)
    benchmark_return = float(current[benchmark] / base[benchmark] - 1.0)
    return asset_return < benchmark_return


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
        default=Path("reports/derivatives_track_h5_relmom_riskbudget_funding_exit"),
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

    _, market, universe, index = _load_market(
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
    h5_long_gross = _long_gross_series(h5_raw, index)
    relative_prices = _normalized_prices(market.price)

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

    unfiltered_short: dict[pd.Timestamp, pd.Series] = {}
    funding_short: dict[pd.Timestamp, pd.Series] = {}
    short_targets: dict[pd.Timestamp, pd.Series] = {}
    if not args.baseline:
        eligible = _eligible_members_by_date(universe, list(h5_raw))
        unfiltered_raw = build_exit_short_schedule(
            h5_raw,
            holding_days=int(FROZEN_CONFIG["exit_short_holding_days"]),
            eligible_by_date=eligible,
            per_asset_weight=float(FROZEN_CONFIG["base_short_per_asset_weight_at_zero_long"]),
        )
        unfiltered_short, _ = _restrict_targets(
            unfiltered_raw, available, mark_candles
        )

        def funding_allowed(asset: str, date: pd.Timestamp) -> bool:
            rank = funding_rank_percentile(
                funding if not funding.empty else None,
                universe,
                asset,
                as_of=date,
                eligible=available,
                lookback_days=int(FROZEN_CONFIG["funding_lookback_days"]),
                min_assets=int(FROZEN_CONFIG["funding_min_assets"]),
            )
            return rank is not None and rank >= float(
                FROZEN_CONFIG["funding_rank_min"]
            )

        funding_raw = build_exit_short_schedule(
            h5_raw,
            holding_days=int(FROZEN_CONFIG["exit_short_holding_days"]),
            eligible_by_date=eligible,
            per_asset_weight=float(FROZEN_CONFIG["base_short_per_asset_weight_at_zero_long"]),
            entry_allowed=funding_allowed,
        )
        funding_short, _ = _restrict_targets(
            funding_raw, available, mark_candles
        )

        def entry_allowed(asset: str, date: pd.Timestamp) -> bool:
            return funding_allowed(asset, date) and _relative_momentum_allows(
                relative_prices,
                asset,
                date,
                lookback_days=int(FROZEN_CONFIG["relative_lookback_days"]),
                benchmark=str(FROZEN_CONFIG["relative_benchmark"]),
            )

        filtered_raw = build_exit_short_schedule(
            h5_raw,
            holding_days=int(FROZEN_CONFIG["exit_short_holding_days"]),
            eligible_by_date=eligible,
            per_asset_weight=float(FROZEN_CONFIG["base_short_per_asset_weight_at_zero_long"]),
            entry_allowed=entry_allowed,
        )
        short_targets, _ = _restrict_targets(
            filtered_raw, available, mark_candles
        )
        short_targets = _scale_schedule_by_long_gross(short_targets, h5_long_gross)

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
        _write_schedule(run_dir / "unfiltered_exit_short_schedule.csv", unfiltered_short)
        _write_schedule(run_dir / "funding_filtered_exit_short_schedule.csv", funding_short)
        _write_schedule(
            run_dir / "relmom_riskbudget_filtered_exit_short_schedule.csv",
            short_targets,
        )
        audit = {
            "unfiltered_active_dates": len(unfiltered_short),
            "funding_active_dates": len(funding_short),
            "relmom_active_dates": len(short_targets),
            "unfiltered_leg_dates": int(sum(len(target) for target in unfiltered_short.values())),
            "funding_leg_dates": int(sum(len(target) for target in funding_short.values())),
            "relmom_leg_dates": int(sum(len(target) for target in short_targets.values())),
            "funding_lookback_days": int(FROZEN_CONFIG["funding_lookback_days"]),
            "funding_rank_min": float(FROZEN_CONFIG["funding_rank_min"]),
            "funding_min_assets": int(FROZEN_CONFIG["funding_min_assets"]),
            "relative_lookback_days": int(FROZEN_CONFIG["relative_lookback_days"]),
            "relative_benchmark": str(FROZEN_CONFIG["relative_benchmark"]),
            "relative_rule": "asset_14d_return < btc_14d_return",
        }
        (run_dir / "relative_momentum_filter_audit.json").write_text(
            json.dumps(audit, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
