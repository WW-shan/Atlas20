"""Track the frozen phase-momentum champion out of sample.

The champion specification is frozen after the 2022-01-01 .. research-end
sample.  This script rebuilds the full history (so phase offsets and signals
keep their original calendar anchor), then reports only the returns on or
after the first out-of-sample day.  It is a tracking report, not a new
parameter search: the specification, universe, costs, and execution rules are
not selected or tuned here.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.backtest.engine import BacktestResult  # noqa: E402
from atlas20.backtest.intraday import (  # noqa: E402
    MISSING_FILL_POLICIES,
    load_hourly_bars,
    observed_fill_mask,
    pre_fill_returns,
)
from atlas20.config import ResearchConfig  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    build_phase_momentum_targets,
)
from atlas20.universe.builder import MarketDataBundle  # noqa: E402

from scripts.run_phase_momentum import (  # noqa: E402
    _load_market,
    _parse_floats,
    _production_result,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def _oos_index(index: pd.DatetimeIndex, research_end_date: str | pd.Timestamp) -> pd.DatetimeIndex:
    """Return the first full day after the frozen research sample."""
    end = pd.Timestamp(research_end_date).normalize()
    result = pd.DatetimeIndex(index[index > end])
    if result.empty:
        raise ValueError(
            f"no out-of-sample dates after research end {end.date()}; "
            "extend --end-date or lower --research-end-date"
        )
    return result


def _observed_weight_share(
    result: BacktestResult,
    observed: pd.DataFrame,
    oos_index: pd.DatetimeIndex,
) -> float:
    """Share of OOS traded target weight with an observed hourly fill."""
    positions = {pd.Timestamp(date): position for position, date in enumerate(result.daily_returns.index)}
    total = 0.0
    seen = 0.0
    for signal_date, target in result.rebalance_targets.iterrows():
        position = positions.get(pd.Timestamp(signal_date))
        if position is None or position + 1 >= len(result.daily_returns.index):
            continue
        execution_date = pd.Timestamp(result.daily_returns.index[position + 1])
        if execution_date not in oos_index:
            continue
        weights = target.astype(float).abs()
        shown = observed.loc[execution_date].reindex(weights.index, fill_value=False)
        total += float(weights.sum())
        seen += float(weights[shown.astype(bool)].sum())
    return seen / total if total > 0.0 else float("nan")


def _summary_row(
    returns: pd.Series,
    *,
    cost_bps: float,
    fill_policy: str,
    observed_weight_share: float,
    turnover: float,
) -> dict[str, object]:
    """One OOS metric row; the metric definitions match the main report."""
    metrics = _metrics_from_returns(returns)
    return {
        "fill_policy": fill_policy,
        "cost_bps": float(cost_bps),
        "start": returns.index.min(),
        "end": returns.index.max(),
        "days": int(len(returns)),
        "observed_weight_share": float(observed_weight_share),
        "turnover": float(turnover),
        **metrics,
    }


def _scenario_returns(
    config: ResearchConfig,
    market: MarketDataBundle,
    built: PhaseMomentumBuildResult,
    index: pd.DatetimeIndex,
    *,
    oos_index: pd.DatetimeIndex,
    hourly: dict[str, pd.DataFrame],
    costs: tuple[float, ...],
    fill_hours: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """OOS summary rows and a wide daily-return matrix for every scenario."""
    summary_rows: list[dict[str, object]] = []
    return_columns: dict[str, pd.Series] = {}

    for cost in costs:
        close_result = _production_result(config, market, built, index, cost_bps=cost)
        close_returns = close_result.daily_returns.loc[oos_index]
        close_name = f"close_{cost:g}bps"
        return_columns[close_name] = close_returns.rename(close_name)
        summary_rows.append(
            _summary_row(
                close_returns,
                cost_bps=cost,
                fill_policy="close",
                observed_weight_share=1.0,
                turnover=float(close_result.turnover.loc[oos_index].sum()),
            )
        )

        observed = observed_fill_mask(
            market.returns.loc[index],
            hourly,
            fill_hours=fill_hours,
            reference_close=market.raw_price.reindex(index=index, columns=market.returns.columns),
        )
        for policy in MISSING_FILL_POLICIES:
            pre_fill = pre_fill_returns(
                market.returns.loc[index],
                hourly,
                fill_hours=fill_hours,
                missing_fill=policy,
                reference_close=market.raw_price.reindex(index=index, columns=market.returns.columns),
            )
            result = _production_result(
                config,
                market,
                built,
                index,
                cost_bps=cost,
                pre_fill=pre_fill,
            )
            returns = result.daily_returns.loc[oos_index]
            scenario_name = f"h{fill_hours}_{policy}_{cost:g}bps"
            return_columns[scenario_name] = returns.rename(scenario_name)
            summary_rows.append(
                _summary_row(
                    returns,
                    cost_bps=cost,
                    fill_policy=f"h{fill_hours}_{policy}",
                    observed_weight_share=_observed_weight_share(result, observed, oos_index),
                    turnover=float(result.turnover.loc[oos_index].sum()),
                )
            )

    return pd.DataFrame(summary_rows), pd.DataFrame(return_columns)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--research-start-date", default="2022-01-01")
    parser.add_argument("--research-end-date", default="2026-09-21")
    parser.add_argument(
        "--end-date",
        default="2026-10-07",
        help="last verified panel date to include in this tracking snapshot",
    )
    parser.add_argument("--cost-bps", default="2,20,50,100")
    parser.add_argument("--fill-hours", type=int, default=3)
    parser.add_argument("--hourly-dir", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_oos_2026"),
    )
    args = parser.parse_args()
    if not 1 <= args.fill_hours <= 23:
        raise ValueError("--fill-hours must be within [1, 23]")

    costs = _parse_floats(args.cost_bps)
    configure_logging("ERROR")
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.research_start_date,
        end_date=args.end_date,
    )
    oos_index = _oos_index(index, args.research_end_date)
    spec = PhaseMomentumSpec()
    built = build_phase_momentum_targets(market, universe, index, spec=spec)
    hourly = load_hourly_bars(args.hourly_dir)
    summary, daily_returns = _scenario_returns(
        config,
        market,
        built,
        index,
        oos_index=oos_index,
        hourly=hourly,
        costs=costs,
        fill_hours=args.fill_hours,
    )
    benchmark = pd.DataFrame(
        [
            _summary_row(
                market.returns.loc[oos_index, "bitcoin"],
                cost_bps=0.0,
                fill_policy="btc_close",
                observed_weight_share=1.0,
                turnover=0.0,
            )
        ]
    )

    output_dir = ensure_dir(args.output_dir)
    summary.to_csv(output_dir / "oos_summary.csv", index=False)
    benchmark.to_csv(output_dir / "benchmark.csv", index=False)
    daily_returns.to_csv(output_dir / "daily_returns.csv", index_label="date")
    manifest = {
        "config": args.config,
        "research_start_date": args.research_start_date,
        "research_end_date": args.research_end_date,
        "end_date": args.end_date,
        "oos_start": oos_index.min().date().isoformat(),
        "oos_end": oos_index.max().date().isoformat(),
        "oos_days": int(len(oos_index)),
        "cost_bps": list(costs),
        "fill_hours": int(args.fill_hours),
        "missing_hourly_policies": list(MISSING_FILL_POLICIES),
        "hourly_dir": str(args.hourly_dir),
        "hourly_coins": sorted(hourly),
        "strategy": "frozen phase momentum champion (PhaseMomentumSpec defaults, PRIMARY_SIGNAL_SPECS)",
        "spec": asdict(spec),
        "interpretation": (
            "The specification was frozen before this window. These are tracking returns, "
            "not a new parameter search or a validation claim; the window is too short "
            "to overturn the DSR/PBO and parameter-neighborhood gates in RESEARCH.md section 00."
        ),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Phase-Momentum Frozen-Spec Out-of-Sample Tracking",
            "",
            f"Research sample: `{args.research_start_date}` .. `{args.research_end_date}`. ",
            f"Out-of-sample window: `{oos_index.min().date()}` .. `{oos_index.max().date()}` "
            f"({len(oos_index)} daily observations).",
            "",
            "The champion specification was frozen before this window. This report does not",
            "tune parameters, universe membership, costs, or execution timing. The window is",
            "too short to validate the strategy; it records whether the frozen rules continue",
            "to behave as expected after the research cutoff.",
            "",
            "## OOS summary",
            "",
            dataframe_to_markdown(summary),
            "",
            "`close` is the production engine's signal-close fill. `h3_day_close` and",
            "`h3_prior_close` fill three hours after the signal close and bracket coins without",
            "usable hourly candles. `observed_weight_share` is the share of OOS traded target",
            "weight with a usable hourly fill; 1.0 means every traded target is observed.",
            "Sharpe and CAGR are annualized diagnostics over a very short window and are not",
            "used as validation evidence.",
            "",
            "## BTC benchmark",
            "",
            dataframe_to_markdown(benchmark),
            "",
            "## Data and scope",
            "",
            f"- Panel end date: `{args.end_date}` (latest verified data at report time).",
            f"- OOS starts on the first daily close after the research cutoff: `{oos_index.min().date()}`.",
            "- Strict point-in-time Top20, long-only spot, no leverage, gross exposure <= 1.0.",
            "- No parameter, universe, or execution rule was changed after seeing this window.",
            "",
            "This file is a research tracking report only. It does not place orders.",
            "",
        ]
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(summary.to_string(index=False))
    print(benchmark.to_string(index=False))
    print(f"Wrote OOS tracking report to {output_dir}")


if __name__ == "__main__":
    main()
