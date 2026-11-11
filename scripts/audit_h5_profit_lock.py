# ruff: noqa: E402
"""Audit the pre-registered H5 single-leader extreme-run profit lock.

Read-only diagnostic: no engine run, no order, and no live-book change.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas20.derivatives.data import load_mark_candles
from atlas20.derivatives.signals import scale_long_targets, trim_extreme_run_single_leader
from scripts.run_derivatives_backtest import _long_targets_from_build, _restrict_targets
from scripts.run_phase_momentum import _load_market
from scripts.run_phase_momentum_live_signal import _resolve_build

DEFAULT_OUTPUT_DIR = Path(
    "reports/derivatives_track_h5_regime_short_router/profit_lock_audit"
)
DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_20261009")
CONFIG = {"lookback_days": 21, "threshold": 1.0, "scale": 0.5}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--h5-leverage", type=float, default=1.25)
    args = parser.parse_args()

    _, market, universe, index = _load_market(
        "config/base.yaml",
        start_date=args.start_date,
        end_date=args.end_date,
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_raw = _long_targets_from_build(built, index)
    symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, symbol_map)
    restricted, _dropped = _restrict_targets(long_raw, set(mark_candles), mark_candles)
    scaled = scale_long_targets(
        restricted,
        leverage=float(args.h5_leverage),
        max_gross=float(args.h5_leverage),
    )
    _, audit = trim_extreme_run_single_leader(scaled, prices=market.price, **CONFIG)

    audit["year"] = pd.to_datetime(audit["date"], utc=True).dt.year
    trimmed = audit.loc[audit["trimmed"].astype(bool)].copy()
    leader_counts = (
        trimmed.groupby("leader")["trimmed"]
        .agg(["count"])
        .sort_values("count", ascending=False)
        .reset_index()
    )
    yearly = (
        trimmed.groupby("year")
        .agg(
            trimmed_events=("trimmed", "sum"),
            gross_released=("gross_before", "sum"),
        )
        .reset_index()
    )
    summary = pd.DataFrame(
        [
            {
                "target_events": len(audit),
                "trimmed_events": len(trimmed),
                "trimmed_share": len(trimmed) / len(audit) if len(audit) else 0.0,
                "gross_before_total": float(audit["gross_before"].sum()),
                "gross_after_total": float(audit["gross_after"].sum()),
                "cash_release_total": float(
                    (audit["gross_before"] - audit["gross_after"]).sum()
                ),
                "cash_release_median_on_trim": (
                    float((trimmed["gross_before"] - trimmed["gross_after"]).median())
                    if not trimmed.empty
                    else 0.0
                ),
                "cash_release_max_on_trim": (
                    float((trimmed["gross_before"] - trimmed["gross_after"]).max())
                    if not trimmed.empty
                    else 0.0
                ),
            }
        ]
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit.to_csv(args.output_dir / "event_audit.csv", index=False)
    leader_counts.to_csv(args.output_dir / "leader_counts.csv", index=False)
    yearly.to_csv(args.output_dir / "yearly_trimmed_events.csv", index=False)
    summary.to_csv(args.output_dir / "summary.csv", index=False)
    (args.output_dir / "README.md").write_text(
        "\n".join(
            [
                "# H5 single-leader extreme-run profit-lock audit",
                "",
                "Read-only diagnostic; no strategy trial is run here and the live book is unchanged.",
                "",
                f"- H5 target events: {int(summary.iloc[0]['target_events'])}",
                f"- Trim events: {int(summary.iloc[0]['trimmed_events'])}",
                f"- Trim share: {summary.iloc[0]['trimmed_share']:.2%}",
                f"- Median cash released on trim: {summary.iloc[0]['cash_release_median_on_trim']:.4f} NAV",
                f"- Maximum cash released on trim: {summary.iloc[0]['cash_release_max_on_trim']:.4f} NAV",
                "",
                "A trim fires when the largest H5 long leg has a 21-day trailing return of at least 100%;",
                "only that leg is halved and the freed weight stays in cash.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"Wrote profit-lock audit to {args.output_dir}")


if __name__ == "__main__":
    main()
