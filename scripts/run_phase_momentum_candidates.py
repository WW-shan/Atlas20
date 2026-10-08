"""Build the 32-candidate phase-momentum return matrix used by the validation runners.

``reports/phase_momentum_multiple_testing_2022/candidate_returns.csv`` feeds the
Deflated Sharpe, Reality Check, CSCV, walk-forward, regime and robustness
runners.  It holds every pre-specified neighbourhood variant from
``scripts/run_phase_momentum.py`` plus two trend-filter combinations and the
fixed equal-weight parameter ensemble, all through the production engine at
the same total cost.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
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
from atlas20.strategies.phase_momentum import (  # noqa: E402
    CORE_PARAMETER_SPECS,
    PhaseMomentumSpec,
    build_parameter_ensemble_targets,
    build_phase_momentum_targets,
)

from scripts.run_phase_momentum import _load_market, _production_result, _variant_specs  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def candidate_specs() -> dict[str, PhaseMomentumSpec]:
    """Every single-spec candidate, keyed by its column name in the matrix."""
    specs = {
        name.replace("asset_trend_", "trend_"): spec for name, spec in _variant_specs().items()
    }
    trend_100 = specs["trend_100"]
    specs["trend_100_trailing_stop_20"] = replace(
        trend_100, stop_loss_kind="trailing", stop_loss_pct=0.20
    )
    specs["trend_100_target_vol_0.7"] = replace(trend_100, target_volatility=0.7)
    return specs


PARAMETER_ENSEMBLE_COLUMN = "parameter_ensemble_20bps"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_multiple_testing_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    columns: dict[str, pd.Series] = {}
    specs = candidate_specs()
    for name, spec in specs.items():
        built = build_phase_momentum_targets(market, universe, index, spec=spec)
        result = _production_result(config, market, built, index, cost_bps=args.cost_bps)
        columns[name] = result.daily_returns.rename(name)
    ensemble = build_parameter_ensemble_targets(market, universe, index)
    columns[PARAMETER_ENSEMBLE_COLUMN] = _production_result(
        config, market, ensemble, index, cost_bps=args.cost_bps
    ).daily_returns.rename(PARAMETER_ENSEMBLE_COLUMN)

    output_dir = ensure_dir(args.output_dir)
    frame = pd.DataFrame(columns)
    frame.to_csv(output_dir / "candidate_returns.csv", index_label="date")
    pd.DataFrame(
        [
            {"candidate": name, "cost_bps": args.cost_bps, **_metrics_from_returns(series)}
            for name, series in frame.items()
        ]
    ).to_csv(output_dir / "candidate_summary.csv", index=False)
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": args.cost_bps,
        "candidates": {
            **{name: asdict(spec) for name, spec in specs.items()},
            PARAMETER_ENSEMBLE_COLUMN: [asdict(spec) for spec in CORE_PARAMETER_SPECS],
        },
    }
    (output_dir / "candidate_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(columns)} candidate return series to {output_dir / 'candidate_returns.csv'}")


if __name__ == "__main__":
    main()
