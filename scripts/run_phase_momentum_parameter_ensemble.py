"""Cost sweep for the fixed phase-momentum parameter ensemble.

Every parameter set in ``CORE_PARAMETER_SPECS`` runs the four primary signals
in its own phases, and each set gets the same share of the book.  The
ensemble is a risk-diversification reference, not the champion.
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
    CORE_PARAMETER_SPECS,
    PRIMARY_SIGNAL_SPECS,
    build_parameter_ensemble_targets,
)

from scripts.run_phase_momentum import (  # noqa: E402
    _load_market,
    _parse_floats,
    _production_result,
    _summary_row,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", default="2,20,50,100")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_parameter_ensemble_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    costs = _parse_floats(args.cost_bps)
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    built = build_parameter_ensemble_targets(market, universe, index)
    rows: list[dict[str, object]] = []
    returns: dict[str, pd.Series] = {}
    for cost in costs:
        result = _production_result(config, market, built, index, cost_bps=cost)
        returns[f"{cost:g}bps"] = result.daily_returns
        rows.append(
            _summary_row("parameter_ensemble", result.daily_returns, cost_bps=cost, period="full_2022_plus")
        )
    summary = pd.DataFrame(rows)

    output_dir = ensure_dir(args.output_dir)
    summary.to_csv(output_dir / "summary.csv", index=False)
    pd.DataFrame(returns).to_csv(output_dir / "returns.csv", index_label="date")
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "universe": "strict point-in-time Top20",
        "parameter_specs": len(CORE_PARAMETER_SPECS),
        "signal_specs": len(PRIMARY_SIGNAL_SPECS),
        "sleeves": len(built.sleeve_targets),
        "weighting": "equal weight per parameter set",
        "cost_bps": list(costs),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                "# Phase-Momentum Parameter Ensemble",
                "",
                f"{len(CORE_PARAMETER_SPECS)} pre-specified parameter sets x {len(PRIMARY_SIGNAL_SPECS)} signals,",
                f"{len(built.sleeve_targets)} sleeves in total; every parameter set carries the same share",
                "of the book however many phase sleeves it has. Strict point-in-time Top20,",
                "long-only, gross exposure <= 1.0, production engine.",
                "",
                dataframe_to_markdown(summary),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"Wrote parameter-ensemble cost sweep to {output_dir}")


if __name__ == "__main__":
    main()
