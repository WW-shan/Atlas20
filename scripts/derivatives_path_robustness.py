# ruff: noqa: E402
"""Monthly-start path slices for saved derivatives candidate returns.

The script re-slices an already aligned daily-return matrix. It does not rerun
the strategy or select a parameter. The first column is the baseline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas20.reporting.report import dataframe_to_markdown
from scripts.run_strategy_evidence_audit import _metrics_from_returns


def _load_returns(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0)
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True))
    frame = frame.apply(pd.to_numeric, errors="coerce").sort_index()
    if frame.empty or frame.isna().any().any():
        raise ValueError(f"{path}: expected a complete numeric return matrix")
    return frame


def _monthly_starts(index: pd.DatetimeIndex, *, min_days: int) -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    end = pd.Timestamp(index.max())
    for period in pd.period_range(index.min().to_period("M"), index.max().to_period("M"), freq="M"):
        month_start = period.start_time.tz_localize("UTC")
        candidates = index[index >= month_start]
        if candidates.empty:
            continue
        start = pd.Timestamp(candidates[0])
        if (end - start).days >= min_days:
            starts.append(start)
    return starts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--returns", type=Path, required=True)
    parser.add_argument("--min-days", type=int, default=365)
    parser.add_argument("--mdd-tolerance", type=float, default=0.05)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    returns = _load_returns(args.returns)
    if len(returns.columns) < 2:
        raise ValueError("return matrix needs a baseline and at least one candidate")
    baseline = str(returns.columns[0])
    rows: list[dict[str, object]] = []
    for start in _monthly_starts(returns.index, min_days=args.min_days):
        window = returns.loc[start:]
        base_metrics = _metrics_from_returns(window[baseline])
        for candidate in map(str, returns.columns[1:]):
            metrics = _metrics_from_returns(window[candidate])
            rows.append(
                {
                    "start": start,
                    "candidate": candidate,
                    "days": len(window),
                    "base_multiple": base_metrics["multiple"],
                    "candidate_multiple": metrics["multiple"],
                    "base_sharpe": base_metrics["sharpe"],
                    "candidate_sharpe": metrics["sharpe"],
                    "base_mdd": base_metrics["max_drawdown"],
                    "candidate_mdd": metrics["max_drawdown"],
                    "multiple_pass": metrics["multiple"] > base_metrics["multiple"],
                    "sharpe_pass": metrics["sharpe"] >= base_metrics["sharpe"],
                    "mdd_pass": metrics["max_drawdown"]
                    >= base_metrics["max_drawdown"] - args.mdd_tolerance,
                }
            )
    detail = pd.DataFrame(rows)
    if detail.empty:
        raise ValueError("no monthly path slices satisfy the minimum remaining days")
    detail["all_pass"] = detail[["multiple_pass", "sharpe_pass", "mdd_pass"]].all(axis=1)
    summary = (
        detail.groupby("candidate")
        .agg(
            slices=("start", "count"),
            multiple_pass=("multiple_pass", "sum"),
            sharpe_pass=("sharpe_pass", "sum"),
            mdd_pass=("mdd_pass", "sum"),
            all_pass=("all_pass", "sum"),
            worst_candidate_mdd=("candidate_mdd", "min"),
            worst_relative_mdd=(
                "candidate_mdd",
                lambda values: float(values.min()),
            ),
        )
        .reset_index()
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.output_dir / "monthly_start_slices.csv", index=False)
    summary.to_csv(args.output_dir / "summary.csv", index=False)
    (args.output_dir / "summary.json").write_text(
        json.dumps(
            {
                "baseline": baseline,
                "candidates": list(map(str, returns.columns[1:])),
                "starts": int(detail["start"].nunique()),
                "min_days": int(args.min_days),
                "mdd_tolerance": float(args.mdd_tolerance),
                "summary": summary.to_dict("records"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    report = [
        "# Derivatives Monthly-Start Path Slices",
        "",
        f"- baseline: `{baseline}`",
        f"- starts with at least {args.min_days} remaining days: {detail['start'].nunique()}",
        f"- MDD tolerance: {args.mdd_tolerance:.2%}",
        "",
        "## Summary",
        "",
        dataframe_to_markdown(summary),
        "",
        "## Details",
        "",
        dataframe_to_markdown(detail),
        "",
    ]
    (args.output_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Wrote monthly path robustness to {args.output_dir}")


if __name__ == "__main__":
    main()
