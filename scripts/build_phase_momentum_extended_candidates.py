"""Extend the phase-momentum candidate matrix with the registered overlay families.

The CSCV / PBO gate for a frozen specification is only meaningful over the
family a selection could have picked from.  The pre-2026-10-08 matrix
(``reports/phase_momentum_multiple_testing_2022/candidate_returns.csv``) holds
the 30 unique single-spec variants the champion was selected from; the adopted
H3 blend and its pre-registered 0.45/0.55 neighbourhood, and the H5 dispersion
overlay and its 0.60/0.90 neighbourhood, were not in it.  This tool appends
those registered candidates at the same cost and fill (20 bps, signal close,
2022-01-01 .. 2026-09-21) so ``scripts/run_phase_momentum_multiple_testing.py``
can compute PBO, DSR and the Reality Check over the union.  It runs no new
hypothesis and selects nothing.
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
from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_hypotheses import (  # noqa: E402
    build_trial,
    trial_by_id,
    trial_spec,
)

# The registered H3 family: the 0.50 blend and its 0.45/0.55 neighbours.
H3_COLUMNS = {
    "h3_breadth_045": "PR2026-10-H3-T45",
    "h3_breadth_050": "PR2026-10-H3",
    "h3_breadth_055": "PR2026-10-H3-T55",
}

# The registered H5 family: the 0.75 dispersion-target blend and its neighbours.
H5_COLUMNS = {
    "h5_disp_p60": "PR2026-10-H5-T60",
    "h5_disp_p75": "PR2026-10-H5",
    "h5_disp_p90": "PR2026-10-H5-T90",
}

APPENDED_COLUMNS = {**H3_COLUMNS, **H5_COLUMNS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument(
        "--base-candidates",
        type=Path,
        default=Path("reports/phase_momentum_multiple_testing_2022/candidate_returns.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_multiple_testing_overlays"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    base = pd.read_csv(args.base_candidates, index_col=0, parse_dates=True)
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    columns: dict[str, pd.Series] = {}
    specs: dict[str, object] = {}
    for name, trial_id in APPENDED_COLUMNS.items():
        trial = trial_by_id(trial_id)
        built = build_trial(trial, market, universe, index)
        result = _production_result(config, market, built, index, cost_bps=args.cost_bps)
        columns[name] = result.daily_returns.rename(name)
        specs[name] = {"trial_id": trial_id, "trial_spec": trial_spec(trial)}

    h3 = pd.DataFrame(columns)
    # Align on the base matrix's dates so the CSCV uses one common sample.
    frame = pd.concat([base, h3.reindex(base.index)], axis=1)
    if frame.isna().any().any():
        missing = frame.columns[frame.isna().any()].tolist()
        raise ValueError(f"overlay candidates do not cover the base matrix dates: {missing}")

    output_dir = ensure_dir(args.output_dir)
    frame.to_csv(output_dir / "candidate_returns.csv", index_label="date")
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": args.cost_bps,
        "base_candidates": str(args.base_candidates),
        "base_candidate_count": int(base.shape[1]),
        "appended_candidates": specs,
        "rows": int(len(frame)),
        "primary": "h5_disp_p75",
    }
    (output_dir / "candidate_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"Wrote {frame.shape[1]} candidate return series "
        f"({base.shape[1]} base + {len(columns)} overlay) to {output_dir / 'candidate_returns.csv'}"
    )


if __name__ == "__main__":
    main()
