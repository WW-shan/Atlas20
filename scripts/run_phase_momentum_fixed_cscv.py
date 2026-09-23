"""CSCV stability check for the fixed primary and parameter-ensemble strategies."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_phase_momentum_multiple_testing import _block_sharpes  # noqa: E402


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
    candidates = [item.strip() for item in args.candidates.split(",") if item.strip()]
    missing = [candidate for candidate in candidates if candidate not in returns.columns]
    if missing:
        raise ValueError(f"Missing candidates: {missing}")
    if args.cscv_blocks < 4 or args.cscv_blocks % 2 != 0:
        raise ValueError("cscv-blocks must be an even integer >= 4")
    block_size = len(returns) // args.cscv_blocks
    blocks = [
        frame
        for _, frame in returns.groupby(np.arange(len(returns)) // block_size)
    ][: args.cscv_blocks]
    half = args.cscv_blocks // 2
    rows: list[dict[str, object]] = []
    for train_indices in combinations(range(args.cscv_blocks), half):
        train_set = set(train_indices)
        test_indices = [index for index in range(args.cscv_blocks) if index not in train_set]
        train = pd.concat([blocks[index] for index in train_indices], axis=0)
        test = pd.concat([blocks[index] for index in test_indices], axis=0)
        train_perf = _block_sharpes(train)
        test_perf = _block_sharpes(test)
        for candidate in candidates:
            rows.append(
                {
                    "candidate": candidate,
                    "train_percentile": float(train_perf.rank(pct=True).loc[candidate]),
                    "test_percentile": float(test_perf.rank(pct=True).loc[candidate]),
                    "train_sharpe": float(train_perf.loc[candidate]),
                    "test_sharpe": float(test_perf.loc[candidate]),
                }
            )
    splits = pd.DataFrame(rows)
    summary = (
        splits.groupby("candidate")
        .agg(
            splits=("test_percentile", "size"),
            test_percentile_median=("test_percentile", "median"),
            test_percentile_mean=("test_percentile", "mean"),
            below_median_rate=("test_percentile", lambda values: float((values <= 0.5).mean())),
            train_percentile_median=("train_percentile", "median"),
        )
        .reset_index()
    )
    output_dir = ensure_dir(args.output_dir)
    splits.to_csv(output_dir / "fixed_cscv_splits.csv", index=False)
    summary.to_csv(output_dir / "summary.csv", index=False)
    manifest = {
        "candidate_returns": str(args.candidate_returns),
        "cscv_blocks": args.cscv_blocks,
        "cscv_combinations": len(splits) // len(candidates),
        "candidates": candidates,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                "# Fixed-Strategy CSCV Stability",
                "",
                "This test does not select the best in-sample parameter. It measures how often each fixed candidate ranks below the median out of sample across CSCV splits.",
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
