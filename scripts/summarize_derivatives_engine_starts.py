# ruff: noqa: E402
"""Summarize true cash-start derivatives engine runs by quarter."""

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


def _read_summary(path: Path) -> dict[str, object]:
    matches = sorted(path.glob("*/summary.json"))
    if len(matches) != 1:
        raise ValueError(f"{path}: expected exactly one */summary.json, found {len(matches)}")
    return json.loads(matches[0].read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mdd-tolerance", type=float, default=0.05)
    parser.add_argument("--max-gross", type=float, default=1.50)
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for start_dir in sorted(path for path in args.root.iterdir() if path.is_dir()):
        if not (start_dir / "baseline").exists() or not (start_dir / "candidate").exists():
            continue
        baseline = _read_summary(start_dir / "baseline")
        candidate = _read_summary(start_dir / "candidate")
        candidate_mdd = float(candidate["max_drawdown"])
        baseline_mdd = float(baseline["max_drawdown"])
        rows.append(
            {
                "start": start_dir.name,
                "baseline_multiple": float(baseline["multiple"]),
                "candidate_multiple": float(candidate["multiple"]),
                "multiple_ratio": float(candidate["multiple"]) / float(baseline["multiple"]),
                "baseline_sharpe": float(baseline["sharpe"]),
                "candidate_sharpe": float(candidate["sharpe"]),
                "sharpe_delta": float(candidate["sharpe"]) - float(baseline["sharpe"]),
                "baseline_mdd": baseline_mdd,
                "candidate_mdd": candidate_mdd,
                "mdd_delta_pp": (candidate_mdd - baseline_mdd) * 100.0,
                "candidate_liquidations": int(candidate["liquidation_count"]),
                "candidate_max_gross": float(candidate["max_observed_gross"]),
                "candidate_gross_breach_hours": int(candidate["gross_breach_hours"]),
                "multiple_win": float(candidate["multiple"]) > float(baseline["multiple"]),
                "sharpe_win": float(candidate["sharpe"]) > float(baseline["sharpe"]),
                "mdd_pass_5pp": candidate_mdd >= baseline_mdd - args.mdd_tolerance,
            }
        )
    detail = pd.DataFrame(rows)
    if detail.empty:
        raise ValueError(f"{args.root}: no completed baseline/candidate pairs")
    detail["all_risk_checks"] = (
        (detail["candidate_liquidations"] == 0)
        & (detail["candidate_max_gross"] <= args.max_gross + 1e-12)
        & (detail["candidate_gross_breach_hours"] == 0)
    )
    summary = {
        "start_count": int(len(detail)),
        "multiple_wins": int(detail["multiple_win"].sum()),
        "sharpe_wins": int(detail["sharpe_win"].sum()),
        "mdd_pass_5pp": int(detail["mdd_pass_5pp"].sum()),
        "all_risk_checks": bool(detail["all_risk_checks"].all()),
        "multiple_gate_10_of_12": bool(detail["multiple_win"].sum() >= min(10, len(detail))),
        "sharpe_gate_10_of_12": bool(detail["sharpe_win"].sum() >= min(10, len(detail))),
        "mdd_gate_all": bool(detail["mdd_pass_5pp"].all()),
        "engine_monthly_start_gate_passed": bool(
            detail["multiple_win"].sum() >= min(10, len(detail))
            and detail["sharpe_win"].sum() >= min(10, len(detail))
            and detail["mdd_pass_5pp"].all()
            and detail["all_risk_checks"].all()
        ),
    }
    args.root.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.root / "summary.csv", index=False)
    (args.root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = [
        "# Derivatives True Cash-Start Engine Runs",
        "",
        f"- quarterly starts completed: {len(detail)}",
        f"- candidate multiple wins: {summary['multiple_wins']}/{len(detail)}",
        f"- candidate Sharpe wins: {summary['sharpe_wins']}/{len(detail)}",
        f"- candidate MDD within {args.mdd_tolerance:.2%}: {summary['mdd_pass_5pp']}/{len(detail)}",
        f"- zero liquidation / gross cap / breach checks: {summary['all_risk_checks']}",
        f"- gate passed: {summary['engine_monthly_start_gate_passed']}",
        "",
        dataframe_to_markdown(detail),
        "",
    ]
    (args.root / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote engine-start summary to {args.root}")


if __name__ == "__main__":
    main()
