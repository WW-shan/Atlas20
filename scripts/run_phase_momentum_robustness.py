"""Robustness supplements for the phase-momentum champion.

Reproduces ``reports/phase_momentum_robustness_2022/``: best-year removal,
the 2020-10 to 2021-12 stress window (outside the 2022+ headline sample), and
the one-year rolling worst case, for the fixed primary strategy and the fixed
equal-weight parameter ensemble.  Multiple-testing statistics live in
``scripts/run_phase_momentum_multiple_testing.py``.
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

from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PhaseMomentumSpec,
    build_parameter_ensemble_targets,
    build_phase_momentum_targets,
)

from scripts.run_phase_momentum import (  # noqa: E402
    _load_market,
    _parse_floats,
    _production_result,
    _rolling_worst,
    _summary_row,
)
from scripts.run_phase_momentum_candidates import PARAMETER_ENSEMBLE_COLUMN  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def _best_year_removal(returns: dict[str, pd.Series]) -> pd.DataFrame:
    """Metrics after deleting each calendar year's days from the sample."""
    rows: list[dict[str, object]] = []
    for strategy, series in returns.items():
        for year in sorted(set(series.index.year)):
            remaining = series[series.index.year != year]
            rows.append(
                {
                    "strategy": strategy,
                    "removed_year": int(year),
                    "days": int(len(remaining)),
                    **_metrics_from_returns(remaining),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--candidate-returns",
        type=Path,
        default=Path("reports/phase_momentum_multiple_testing_2022/candidate_returns.csv"),
    )
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--stress-start-date", default="2020-10-03")
    parser.add_argument("--stress-end-date", default="2021-12-31")
    parser.add_argument("--stress-cost-bps", default="2,20,50,100")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_robustness_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    candidates = (
        pd.read_csv(args.candidate_returns, parse_dates=["date"]).set_index("date").sort_index()
    )
    window = (candidates.index >= pd.Timestamp(args.start_date)) & (
        candidates.index <= pd.Timestamp(args.end_date)
    )
    candidates = candidates.loc[window]
    _config, market, _universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    if not candidates.index.equals(index):
        raise ValueError("candidate returns do not cover the requested window day by day")
    headline = {
        "primary": candidates["primary"],
        PARAMETER_ENSEMBLE_COLUMN: candidates[PARAMETER_ENSEMBLE_COLUMN],
        "BTC": market.returns["bitcoin"].reindex(index).fillna(0.0),
    }
    best_year = _best_year_removal(headline)
    rolling = pd.DataFrame(
        [{"strategy": name, **_rolling_worst(series)} for name, series in headline.items()]
    )

    stress_costs = _parse_floats(args.stress_cost_bps)
    stress_config, stress_market, stress_universe, stress_index = _load_market(
        args.config,
        start_date=args.stress_start_date,
        end_date=args.stress_end_date,
    )
    stress_builds = {
        "primary": build_phase_momentum_targets(
            stress_market, stress_universe, stress_index, spec=PhaseMomentumSpec()
        ),
        "parameter_ensemble": build_parameter_ensemble_targets(
            stress_market, stress_universe, stress_index
        ),
    }
    period = f"stress_{args.stress_start_date}_to_{args.stress_end_date}"
    stress_rows: list[dict[str, object]] = []
    stress_returns: dict[str, pd.Series] = {}
    for name, built in stress_builds.items():
        for cost in stress_costs:
            result = _production_result(
                stress_config, stress_market, built, stress_index, cost_bps=cost
            )
            stress_returns[f"{name}_{cost:g}bps"] = result.daily_returns
            stress_rows.append(_summary_row(name, result.daily_returns, cost_bps=cost, period=period))
    stress_btc = stress_market.returns["bitcoin"].reindex(stress_index).fillna(0.0)
    stress_returns["BTC"] = stress_btc
    stress_rows.append(_summary_row("BTC", stress_btc, cost_bps=0.0, period=period))
    stress = pd.DataFrame(stress_rows)

    output_dir = ensure_dir(args.output_dir)
    best_year.to_csv(output_dir / "best_year_removal.csv", index=False)
    rolling.to_csv(output_dir / "rolling_worst.csv", index=False)
    stress.to_csv(output_dir / "pre_2022_stress.csv", index=False)
    pd.DataFrame(stress_returns).to_csv(output_dir / "pre_2022_stress_returns.csv", index_label="date")
    manifest = {
        "config": args.config,
        "candidate_returns": str(args.candidate_returns),
        "window": [args.start_date, args.end_date],
        "stress_window": [args.stress_start_date, args.stress_end_date],
        "stress_cost_bps": list(stress_costs),
        "primary": "PhaseMomentumSpec() with PRIMARY_SIGNAL_SPECS",
        "parameter_ensemble": "fixed equal-weight CORE_PARAMETER_SPECS",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = "\n".join(
        [
            "# Phase-Momentum Robustness Supplements",
            "",
            "Headline-window rows use the 20 bps candidate matrix. The stress window is",
            "outside the 2022+ sample and is rebuilt from scratch, so the strategy starts in",
            "cash until its signal windows fill.",
            "",
            "## Best-year removal",
            "",
            dataframe_to_markdown(best_year),
            "",
            "## One-year rolling worst case",
            "",
            dataframe_to_markdown(rolling),
            "",
            f"## Stress window {args.stress_start_date} to {args.stress_end_date}",
            "",
            dataframe_to_markdown(stress),
            "",
        ]
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(stress.to_string(index=False))
    print(f"Wrote robustness supplements to {output_dir}")


if __name__ == "__main__":
    main()
