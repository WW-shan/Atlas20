"""Half-sample rank consistency for fixed phase-momentum candidates.

This is an in-sample diagnostic, not an out-of-sample test.  CSCV enumerates
every half of the blocks as a training set, so every "test" half is also some
split's training half and the two percentile distributions are identical by
construction.  The runner therefore reports one distribution: how often a
fixed candidate ranks in the bottom half of its own family across half-samples.
It cannot correct for a candidate having been chosen on the full sample; the
selection-bias statistics (PBO, Deflated Sharpe, Reality Check) live in
``scripts/run_phase_momentum_multiple_testing.py``.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from itertools import combinations
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

from scripts.run_phase_momentum_multiple_testing import (  # noqa: E402
    _block_sharpes,
    _cscv_blocks,
    _dedupe_identical_columns,
    _require_common_sample,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-returns",
        type=Path,
        default=Path("reports/phase_momentum_multiple_testing_2022/candidate_returns.csv"),
    )
    parser.add_argument("--cscv-blocks", type=int, default=12)
    parser.add_argument(
        "--candidates",
        default="primary,parameter_ensemble_20bps",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_fixed_cscv_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    returns = pd.read_csv(args.candidate_returns, parse_dates=["date"]).set_index("date").sort_index()
    returns = _require_common_sample(returns.apply(pd.to_numeric, errors="coerce"))
    candidates = [item.strip() for item in args.candidates.split(",") if item.strip()]
    missing = [candidate for candidate in candidates if candidate not in returns.columns]
    if missing:
        raise ValueError(f"Missing candidates: {missing}")
    # Identical return series are one trial; rank each requested candidate
    # through the column that represents it.
    returns, duplicates = _dedupe_identical_columns(returns)
    column_for = {candidate: duplicates.get(candidate, candidate) for candidate in candidates}
    blocks = _cscv_blocks(returns, args.cscv_blocks)
    half = args.cscv_blocks // 2
    rows: list[dict[str, object]] = []
    # Each half-sample appears exactly once here; its complement is another
    # iteration of the same loop, so there is no separate "test" side.
    for half_indices in combinations(range(args.cscv_blocks), half):
        sample = pd.concat([blocks[index] for index in half_indices], axis=0)
        performance = _block_sharpes(sample)
        # Relative rank r / (N + 1), the CSCV paper's convention.
        percentiles = performance.rank(method="average") / (len(performance) + 1.0)
        for candidate in candidates:
            column = column_for[candidate]
            rows.append(
                {
                    "candidate": candidate,
                    "half_sample_blocks": "-".join(str(index) for index in half_indices),
                    "half_sample_percentile": float(percentiles.loc[column]),
                    "half_sample_sharpe": float(performance.loc[column]),
                }
            )
    splits = pd.DataFrame(rows)
    summary = (
        splits.groupby("candidate")
        .agg(
            splits=("half_sample_percentile", "size"),
            half_sample_percentile_median=("half_sample_percentile", "median"),
            half_sample_percentile_mean=("half_sample_percentile", "mean"),
            below_median_rate=("half_sample_percentile", lambda values: float((values <= 0.5).mean())),
        )
        .reset_index()
    )
    output_dir = ensure_dir(args.output_dir)
    splits.to_csv(output_dir / "fixed_cscv_splits.csv", index=False)
    summary.to_csv(output_dir / "summary.csv", index=False)
    manifest = {
        "candidate_returns": str(args.candidate_returns),
        "cscv_blocks": args.cscv_blocks,
        "half_samples": len(splits) // len(candidates),
        "candidates": candidates,
        "family_size": int(len(returns.columns)),
        "identical_candidates": duplicates,
        "interpretation": "in-sample half-sample rank consistency; not out-of-sample evidence",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                "# Fixed-Candidate Half-Sample Rank Consistency",
                "",
                "This is an in-sample diagnostic and is not out-of-sample evidence. CSCV",
                "enumerates every half of the blocks, so each candidate's percentile over the",
                "\"test\" halves is the same distribution as over the \"training\" halves. The",
                "table shows how consistently each fixed candidate ranks within its own family",
                f"of {len(returns.columns)} distinct candidates across half-samples. It cannot",
                "correct for a candidate having been chosen with the full sample in view; see",
                "the PBO, Deflated Sharpe and Reality Check in",
                "`reports/phase_momentum_multiple_testing_2022/` for that.",
                "",
                "## Summary",
                "",
                dataframe_to_markdown(summary),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"Wrote fixed CSCV report to {output_dir}")


if __name__ == "__main__":
    main()
