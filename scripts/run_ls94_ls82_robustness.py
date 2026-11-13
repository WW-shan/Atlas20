"""LS94: independent robustness audit of the LS82 carry-core candidate.

The rules, allocation, funding and execution assumptions are frozen.  This
script only measures whether LS82's saved real-engine return advantage over
LS57 survives year, path, bootstrap and multiple-testing diagnostics.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.run_ls57_churn_multiphase_ensemble import robustness_diagnostics  # noqa: E402
from scripts.run_ls93_core_satellite_robustness import (  # noqa: E402
    _multiple_testing,
    _normalise_robustness_tables,
    _rolling_summary,
    _sample_metrics,
    align_return_series,
    load_return_series,
)

TRIAL_ID = "PR2026-11-LS94-LS82-ROBUSTNESS"
SCENARIOS: dict[float, dict[str, Path]] = {
    13.0164: {
        "candidate": Path("reports/ls92_ls82_maker13_2026/daily_normal_13.0164_0.25.csv"),
        "baseline": Path("reports/ls92_ls57_maker13_2026/daily_base_normal_13.0164.csv"),
    },
    20.0: {
        "candidate": Path("reports/ls82_core8_carry_risk_2026/daily_normal_20_0.25.csv"),
        "baseline": Path("reports/ls89_asset_ma21_exit_2026/daily_base_normal_20.csv"),
    },
}


def _scenario_row(
    *,
    cost_bps: float,
    returns: pd.DataFrame,
    candidate: pd.Series,
    baseline: pd.Series,
) -> dict[str, Any]:
    full_candidate = _sample_metrics(candidate)
    full_baseline = _sample_metrics(baseline)
    validation_candidate = _sample_metrics(candidate, validation=True)
    validation_baseline = _sample_metrics(baseline, validation=True)
    return {
        "cost_bps": float(cost_bps),
        "candidate": "LS82",
        "baseline": "LS57",
        "common_start": str(returns.index.min()),
        "common_end": str(returns.index.max()),
        "common_rows": int(len(returns)),
        "candidate_full_multiple": full_candidate["multiple"],
        "baseline_full_multiple": full_baseline["multiple"],
        "candidate_full_sharpe": full_candidate["sharpe"],
        "baseline_full_sharpe": full_baseline["sharpe"],
        "candidate_full_max_drawdown": full_candidate["max_drawdown"],
        "baseline_full_max_drawdown": full_baseline["max_drawdown"],
        "candidate_validation_multiple": validation_candidate["multiple"],
        "baseline_validation_multiple": validation_baseline["multiple"],
        "candidate_validation_sharpe": validation_candidate["sharpe"],
        "baseline_validation_sharpe": validation_baseline["sharpe"],
        "candidate_validation_max_drawdown": validation_candidate["max_drawdown"],
        "baseline_validation_max_drawdown": validation_baseline["max_drawdown"],
    }


def classify_ls82_evidence(
    summary: Mapping[float, Mapping[str, float]],
    *,
    pbo_by_cost: Mapping[float, float],
    reality_p_by_cost: Mapping[float, float],
) -> str:
    """Classify the frozen LS82 evidence against the pre-registered labels."""
    def improves(cost: float) -> bool:
        row = summary[cost]
        return (
            float(row["candidate_multiple"]) > float(row["baseline_multiple"])
            and float(row["candidate_sharpe"]) > float(row["baseline_sharpe"])
            and float(row["candidate_mdd"]) >= float(row["baseline_mdd"]) - 0.01
        )

    if 13.0164 in summary and 20.0 in summary and improves(13.0164) and not improves(20.0):
        return "cost-fragile"
    if all(improves(cost) for cost in (13.0164, 20.0)):
        bootstrap_or_path_fail = any(
            float(summary[cost]["bootstrap_ci_2_5"]) <= 0.0
            or float(summary[cost]["worst_leave_one_year_excess_multiple"]) <= 0.0
            for cost in (13.0164, 20.0)
        )
        if bootstrap_or_path_fail:
            return "year-concentrated"
        robust = all(
            float(pbo_by_cost[cost]) <= 0.50
            and float(reality_p_by_cost[cost]) < 0.05
            for cost in (13.0164, 20.0)
        )
        if robust:
            return "robust-shadow"
    return "inconclusive"


def _reasons(
    summary: Mapping[float, Mapping[str, float]],
    *,
    pbo_by_cost: Mapping[float, float],
    reality_p_by_cost: Mapping[float, float],
) -> list[str]:
    lines: list[str] = []
    for cost in sorted(summary):
        row = summary[cost]
        lines.append(
            f"- {cost:g}bps: LS82 {float(row['candidate_multiple']):.4f}x vs LS57 "
            f"{float(row['baseline_multiple']):.4f}x; bootstrap 2.5% "
            f"{float(row['bootstrap_ci_2_5']):.2%}; years "
            f"{int(float(row['years_outperforming']))}/{int(float(row['years_total']))}; "
            f"worst leave-one-year excess {float(row['worst_leave_one_year_excess_multiple']):+.4f}x; "
            f"PBO {float(pbo_by_cost[cost]):.4f}; RC vs LS57 p={float(reality_p_by_cost[cost]):.4f}"
        )
    return lines


def _write_report(
    *,
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    leave_one_out: pd.DataFrame,
    rolling: pd.DataFrame,
    daily_excess: pd.DataFrame,
    dsr: pd.DataFrame,
    pbo: pd.DataFrame,
    reality: pd.DataFrame,
    classification: str,
    reasons: list[str],
) -> str:
    lines = [
        f"# {TRIAL_ID}",
        "",
        "LS94 is a frozen robustness audit of LS82. It does not change the carry rules, allocation,",
        "funding, execution, live track, or send orders.",
        "",
        "## Scenario summary",
        "",
        dataframe_to_markdown(summary),
        "",
        "## Daily excess diagnostics",
        "",
        dataframe_to_markdown(daily_excess),
        "",
        "## Rolling 365D diagnostics",
        "",
        dataframe_to_markdown(rolling),
        "",
        "## Yearly comparison",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## Leave-one-year-out",
        "",
        dataframe_to_markdown(leave_one_out),
        "",
        "## Multiple-testing diagnostics",
        "",
        "### Deflated Sharpe",
        "",
        dataframe_to_markdown(dsr),
        "",
        "### CSCV / PBO",
        "",
        dataframe_to_markdown(pbo),
        "",
        "### Reality Check",
        "",
        dataframe_to_markdown(reality),
        "",
        "## Evidence classification",
        "",
        f"**{classification}**",
        "",
        *reasons,
        "",
        "The label describes frozen evidence only. It does not promote LS82 or change the live track;",
        "the next research branch continues regardless of the label.",
        "",
        "Research output only; no orders sent.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-count", type=int, default=5000)
    parser.add_argument("--bootstrap-block-length", type=int, default=63)
    parser.add_argument("--seed", type=int, default=94)
    parser.add_argument(
        "--trial-summary",
        type=Path,
        default=Path("reports/research_trial_inventory/summary.json"),
    )
    args = parser.parse_args(argv)

    scenario_rows: list[dict[str, Any]] = []
    yearly_rows: list[pd.DataFrame] = []
    leave_rows: list[pd.DataFrame] = []
    rolling_rows: list[dict[str, Any]] = []
    excess_rows: list[dict[str, Any]] = []
    dsr_rows: list[pd.DataFrame] = []
    pbo_rows: list[pd.DataFrame] = []
    reality_rows: list[pd.DataFrame] = []
    splits_by_cost: dict[float, pd.DataFrame] = {}
    scenario_evidence: dict[float, dict[str, float]] = {}
    pbo_by_cost: dict[float, float] = {}
    reality_p_by_cost: dict[float, float] = {}
    common_indices: dict[float, pd.DatetimeIndex] = {}

    for cost_bps, paths in SCENARIOS.items():
        candidate = load_return_series(paths["candidate"])
        baseline = load_return_series(paths["baseline"])
        returns = align_return_series({"LS57": baseline, "LS82": candidate}, min_observations=100)
        baseline = returns["LS57"]
        candidate = returns["LS82"]
        common_indices[cost_bps] = returns.index
        row = _scenario_row(
            cost_bps=cost_bps,
            returns=returns,
            candidate=candidate,
            baseline=baseline,
        )
        scenario_rows.append(row)
        robust_summary, yearly, leave_one_out, rolling = robustness_diagnostics(
            candidate,
            baseline,
            scenario=f"{cost_bps:g}bps",
        )
        yearly, leave_one_out, rolling = _normalise_robustness_tables(
            yearly, leave_one_out, rolling
        )
        yearly.insert(0, "cost_bps", float(cost_bps))
        leave_one_out.insert(0, "cost_bps", float(cost_bps))
        yearly_rows.append(yearly)
        leave_rows.append(leave_one_out)
        rolling_rows.append(_rolling_summary(rolling, cost_bps=cost_bps))
        excess_rows.append({"cost_bps": float(cost_bps), **robust_summary})

        dsr, pbo, reality, splits = _multiple_testing(
            returns,
            cost_bps=cost_bps,
            candidate="LS82",
            trial_summary=args.trial_summary,
            bootstrap_count=args.bootstrap_count,
            block_length=args.bootstrap_block_length,
            seed=args.seed,
        )
        dsr_rows.append(dsr)
        pbo_rows.append(pbo)
        reality_rows.append(reality)
        splits_by_cost[cost_bps] = splits
        pbo_by_cost[cost_bps] = float(pbo["pbo"].iloc[0])
        ls57_excess = reality.loc[reality["benchmark"] == "LS57 excess"]
        if ls57_excess.empty:
            raise ValueError(f"{cost_bps:g}bps: missing LS57 excess Reality Check row")
        reality_p_by_cost[cost_bps] = float(ls57_excess["reality_check_p_value"].iloc[0])
        scenario_evidence[cost_bps] = {
            "candidate_multiple": float(row["candidate_full_multiple"]),
            "baseline_multiple": float(row["baseline_full_multiple"]),
            "candidate_sharpe": float(row["candidate_full_sharpe"]),
            "baseline_sharpe": float(row["baseline_full_sharpe"]),
            "candidate_mdd": float(row["candidate_full_max_drawdown"]),
            "baseline_mdd": float(row["baseline_full_max_drawdown"]),
            "bootstrap_ci_2_5": float(robust_summary["bootstrap_total_log_excess_ci_2_5"]),
            "years_outperforming": float(robust_summary["years_outperforming"]),
            "years_total": float(robust_summary["years_total"]),
            "worst_leave_one_year_excess_multiple": float(
                robust_summary["worst_leave_one_year_excess_multiple"]
            ),
        }

    if len(common_indices) == 2:
        first, second = common_indices.values()
        if not first.equals(second):
            raise ValueError("the 13.0164bps and 20bps scenarios have different common samples")

    summary_table = pd.DataFrame(scenario_rows)
    yearly_table = pd.concat(yearly_rows, ignore_index=True)
    leave_table = pd.concat(leave_rows, ignore_index=True)
    rolling_table = pd.DataFrame(rolling_rows)
    daily_excess = pd.DataFrame(excess_rows)
    dsr_table = pd.concat(dsr_rows, ignore_index=True)
    pbo_table = pd.concat(pbo_rows, ignore_index=True)
    reality_table = pd.concat(reality_rows, ignore_index=True)
    classification = classify_ls82_evidence(
        scenario_evidence,
        pbo_by_cost=pbo_by_cost,
        reality_p_by_cost=reality_p_by_cost,
    )
    reasons = _reasons(
        scenario_evidence,
        pbo_by_cost=pbo_by_cost,
        reality_p_by_cost=reality_p_by_cost,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_table.to_csv(output_dir / "scenario_summary.csv", index=False)
    yearly_table.to_csv(output_dir / "yearly.csv", index=False)
    leave_table.to_csv(output_dir / "leave_one_year_out.csv", index=False)
    rolling_table.to_csv(output_dir / "rolling_365_summary.csv", index=False)
    daily_excess.to_csv(output_dir / "daily_excess.csv", index=False)
    dsr_table.to_csv(output_dir / "deflated_sharpe.csv", index=False)
    pbo_table.to_csv(output_dir / "pbo.csv", index=False)
    reality_table.to_csv(output_dir / "reality_check.csv", index=False)
    for cost_bps, splits in splits_by_cost.items():
        splits.to_csv(output_dir / f"cscv_splits_{cost_bps:g}bps.csv", index=False)
    manifest = {
        "trial_id": TRIAL_ID,
        "scenarios": {
            str(cost): {
                "candidate": str(paths["candidate"]),
                "baseline": str(paths["baseline"]),
            }
            for cost, paths in SCENARIOS.items()
        },
        "common_start": str(summary_table["common_start"].iloc[0]),
        "common_end": str(summary_table["common_end"].iloc[0]),
        "common_rows": int(summary_table["common_rows"].iloc[0]),
        "trial_summary": str(args.trial_summary),
        "trial_summary_sha256": hashlib.sha256(args.trial_summary.read_bytes()).hexdigest(),
        "bootstrap_count": int(args.bootstrap_count),
        "bootstrap_block_length": int(args.bootstrap_block_length),
        "seed": int(args.seed),
        "classification": classification,
        "reasons": reasons,
        "orders_sent": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        _write_report(
            summary=summary_table,
            yearly=yearly_table,
            leave_one_out=leave_table,
            rolling=rolling_table,
            daily_excess=daily_excess,
            dsr=dsr_table,
            pbo=pbo_table,
            reality=reality_table,
            classification=classification,
            reasons=reasons,
        ),
        encoding="utf-8",
    )
    print(summary_table.to_string(index=False))
    print(rolling_table.to_string(index=False))
    print(pbo_table.to_string(index=False))
    print(f"classification: {classification}")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
