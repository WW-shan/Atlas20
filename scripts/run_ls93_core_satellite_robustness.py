"""LS93: robustness and attribution audit for the LS92 core-satellite portfolio.

This is a diagnostic over already-saved real-engine return series.  It does not
re-fit weights, scan parameters, send orders, or alter the live track.
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
from scripts.run_ls90_multi_strategy_ensemble import combine_no_rebalance  # noqa: E402
from scripts.run_phase_momentum_multiple_testing import (  # noqa: E402
    _daily_sharpe,
    _dedupe_identical_columns,
    _deflated_sharpe,
    _excess_over,
    _expected_max_sharpe,
    _pbo_cscv,
    _project_scopes,
    _reality_check,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

TRIAL_ID = "PR2026-11-LS93-LS92-ROBUSTNESS"
VALIDATION_START = pd.Timestamp("2024-01-01", tz="UTC")
VALIDATION_END = pd.Timestamp("2026-09-20", tz="UTC")
MIN_COMMON_OBSERVATIONS = 100

SLEEVE_NAMES = ("LS57", "LS82_CARRY", "LS88_LONG_CARRY", "LS89_MA21")
WEIGHTS: dict[str, float] = {
    "LS57": 0.50,
    "LS82_CARRY": 0.25,
    "LS88_LONG_CARRY": 0.25,
    "LS89_MA21": 0.00,
}

SCENARIOS: dict[float, dict[str, Any]] = {
    13.0164: {
        "label": "LS92",
        "portfolio": Path("reports/ls92_core_satellite_maker_shadow_2026/portfolio_daily_returns.csv"),
        "sleeves": {
            "LS57": Path("reports/ls92_ls57_maker13_2026/daily_base_normal_13.0164.csv"),
            "LS82_CARRY": Path("reports/ls92_ls82_maker13_2026/daily_normal_13.0164_0.25.csv"),
            "LS88_LONG_CARRY": Path("reports/ls92_ls88_maker13_2026/daily_normal_13.0164_0.10.csv"),
            "LS89_MA21": Path("reports/ls92_ls57_maker13_2026/daily_filtered_normal_13.0164.csv"),
        },
    },
    20.0: {
        "label": "LS91",
        "portfolio": Path("reports/ls91_core_satellite_ensemble_2026/portfolio_daily_returns.csv"),
        "sleeves": {
            "LS57": Path("reports/ls89_asset_ma21_exit_2026/daily_base_normal_20.csv"),
            "LS82_CARRY": Path("reports/ls82_core8_carry_risk_2026/daily_normal_20_0.25.csv"),
            "LS88_LONG_CARRY": Path("reports/ls88_lowfunding_long_2026/daily_normal_20_0.10.csv"),
            "LS89_MA21": Path("reports/ls89_asset_ma21_exit_2026/daily_filtered_normal_20.csv"),
        },
    },
}


def load_return_series(path: Path, *, value_column: str = "daily_return") -> pd.Series:
    """Load one finite, uniquely dated return series without filling gaps."""
    frame = pd.read_csv(path)
    if frame.empty or "date" not in frame.columns:
        raise ValueError(f"{path}: expected a non-empty date column")
    if value_column not in frame.columns:
        raise ValueError(f"{path}: missing return column {value_column!r}")
    index = pd.DatetimeIndex(pd.to_datetime(frame["date"], errors="coerce", utc=True))
    if index.isna().any():
        raise ValueError(f"{path}: return dates are not parseable")
    if index.duplicated().any():
        duplicates = sorted({str(day.date()) for day in index[index.duplicated()]})
        raise ValueError(f"{path}: duplicate date(s) {duplicates[:5]}")
    values = pd.to_numeric(frame[value_column], errors="coerce").to_numpy(dtype=float)
    series = pd.Series(values, index=index, name=path.stem)
    if not np.isfinite(series.to_numpy(dtype=float)).all():
        raise ValueError(f"{path}: return series contains missing or non-finite values")
    return series.sort_index()


def align_return_series(
    series: Mapping[str, pd.Series],
    *,
    min_observations: int = 2,
) -> pd.DataFrame:
    """Align a scenario on the intersection of dates and refuse any gap."""
    if not series:
        raise ValueError("at least one return series is required")
    common_index: pd.DatetimeIndex | None = None
    for name, values in series.items():
        if values.empty:
            raise ValueError(f"return series {name!r} is empty")
        if values.index.duplicated().any():
            raise ValueError(f"return series {name!r} has duplicate dates")
        numeric = pd.to_numeric(values, errors="coerce")
        if not np.isfinite(numeric.to_numpy(dtype=float)).all():
            raise ValueError(f"return series {name!r} contains missing or non-finite values")
        common_index = numeric.index if common_index is None else common_index.intersection(numeric.index)
    if common_index is None or len(common_index) < min_observations:
        raise ValueError(
            f"common sample has {0 if common_index is None else len(common_index)} observations; "
            f"at least {min_observations} required"
        )
    frame = pd.concat(
        {name: pd.to_numeric(values, errors="coerce").reindex(common_index) for name, values in series.items()},
        axis=1,
    ).sort_index()
    if frame.isna().to_numpy().any() or not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("common sample contains missing or non-finite values after alignment")
    return frame


def assert_matches_saved_portfolio(
    computed: pd.Series,
    saved: pd.Series,
    *,
    label: str,
    tolerance: float = 1e-10,
) -> None:
    """Verify that a recomputed portfolio is the saved engine output."""
    aligned_saved = saved.reindex(computed.index)
    if aligned_saved.isna().any() or not np.isfinite(aligned_saved.to_numpy(dtype=float)).all():
        raise ValueError(f"{label} portfolio integrity check failed: saved dates do not match")
    difference = np.abs(computed.to_numpy(dtype=float) - aligned_saved.to_numpy(dtype=float))
    if difference.size == 0 or float(difference.max()) > tolerance:
        maximum = float(difference.max()) if difference.size else float("nan")
        raise ValueError(f"{label} portfolio integrity check failed: max difference {maximum:.3e}")


def sleeve_contributions(
    returns: pd.DataFrame,
    *,
    weights: Mapping[str, float],
    baseline: str,
) -> pd.DataFrame:
    """Terminal wealth shares and additive excess contribution versus a baseline sleeve."""
    missing = set(weights).difference(returns.columns)
    if missing:
        raise ValueError(f"weights reference missing sleeves: {sorted(missing)}")
    if baseline not in weights:
        raise ValueError(f"baseline {baseline!r} must have a weight")
    total_weight = float(sum(weights.values()))
    if abs(total_weight - 1.0) > 1e-12:
        raise ValueError("weights must sum to one")
    frame = returns.loc[:, list(weights)].dropna()
    if frame.empty:
        raise ValueError("no common observations for sleeve contributions")
    terminal = (1.0 + frame).cumprod().iloc[-1]
    contribution = pd.Series(
        {name: float(weight) * float(terminal[name]) for name, weight in weights.items()},
        dtype=float,
    )
    portfolio_multiple = float(contribution.sum())
    baseline_multiple = float(terminal[baseline])
    excess = pd.Series(
        {name: float(weight) * (float(terminal[name]) - baseline_multiple) for name, weight in weights.items()},
        dtype=float,
    )
    total_excess = float(excess.sum())
    table = pd.DataFrame(
        {
            "sleeve": list(weights),
            "weight": [float(weight) for weight in weights.values()],
            "terminal_multiple": [float(terminal[name]) for name in weights],
            "terminal_multiple_contribution": contribution.to_numpy(dtype=float),
            "wealth_share": (contribution / portfolio_multiple).to_numpy(dtype=float),
            "excess_vs_baseline": excess.to_numpy(dtype=float),
            "excess_share": (
                excess / total_excess if abs(total_excess) > 1e-15 else pd.Series(0.0, index=excess.index)
            ).to_numpy(dtype=float),
        }
    )
    return table


def _sample_metrics(series: pd.Series, *, validation: bool = False) -> dict[str, float]:
    segment = series
    if validation:
        segment = series.loc[(series.index >= VALIDATION_START) & (series.index <= VALIDATION_END)]
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def _scenario_summary(
    *,
    cost_bps: float,
    label: str,
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
        "candidate": label,
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


def _normalise_robustness_tables(
    yearly: pd.DataFrame,
    leave_one_out: pd.DataFrame,
    rolling: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    yearly = yearly.rename(
        columns={
            "overlay_multiple": "candidate_multiple",
            "overlay_cagr": "candidate_cagr",
            "overlay_sharpe": "candidate_sharpe",
            "overlay_max_drawdown": "candidate_max_drawdown",
            "baseline_multiple": "baseline_multiple",
            "baseline_sharpe": "baseline_sharpe",
            "baseline_max_drawdown": "baseline_max_drawdown",
            "excess_multiple": "excess_multiple",
            "excess_sharpe": "excess_sharpe",
        }
    )
    leave_one_out = leave_one_out.rename(
        columns={
            "overlay_multiple": "candidate_multiple",
            "overlay_sharpe": "candidate_sharpe",
            "overlay_max_drawdown": "candidate_max_drawdown",
            "baseline_multiple": "baseline_multiple",
            "baseline_sharpe": "baseline_sharpe",
            "baseline_max_drawdown": "baseline_max_drawdown",
            "excess_multiple": "excess_multiple",
            "excess_sharpe": "excess_sharpe",
        }
    )
    rolling = rolling.rename(
        columns={
            "overlay_|_rolling_multiple_365d": "candidate_rolling_multiple_365d",
            "overlay_|_rolling_sharpe_365d": "candidate_rolling_sharpe_365d",
            "baseline_|_rolling_multiple_365d": "baseline_rolling_multiple_365d",
            "baseline_|_rolling_sharpe_365d": "baseline_rolling_sharpe_365d",
        }
    )
    return yearly, leave_one_out, rolling


def _rolling_summary(rolling: pd.DataFrame, *, cost_bps: float) -> dict[str, Any]:
    return {
        "cost_bps": float(cost_bps),
        "rolling_365_windows": int(len(rolling)),
        "rolling_365_outperform_share": float((rolling["excess_multiple_365d"] > 0.0).mean()),
        "worst_rolling_365_excess_multiple": float(rolling["excess_multiple_365d"].min()),
        "median_rolling_365_excess_multiple": float(rolling["excess_multiple_365d"].median()),
        "worst_rolling_365_excess_sharpe": float(rolling["excess_sharpe_365d"].min()),
        "median_rolling_365_excess_sharpe": float(rolling["excess_sharpe_365d"].median()),
    }


def _multiple_testing(
    returns: pd.DataFrame,
    *,
    cost_bps: float,
    candidate: str,
    trial_summary: Path,
    bootstrap_count: int,
    block_length: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    unique, _duplicates = _dedupe_identical_columns(returns)
    sharpes = unique.apply(_daily_sharpe)
    scopes = [("family", int(len(unique.columns)), float(sharpes.std(ddof=1)))]
    scopes.extend(_project_scopes(trial_summary))
    dsr_rows: list[dict[str, Any]] = []
    for name in dict.fromkeys((candidate, "LS57")):
        for scope, count, sharpe_std in scopes:
            dsr_rows.append(
                {
                    "cost_bps": float(cost_bps),
                    "candidate": name,
                    "scope": scope,
                    "trial_count": int(count),
                    "trial_sharpe_std_annualized": float(sharpe_std * np.sqrt(365.0)),
                    **_deflated_sharpe(
                        unique[name],
                        expected_max_sharpe=_expected_max_sharpe(count, sharpe_std),
                    ),
                }
            )
    pbo, splits = _pbo_cscv(unique, n_blocks=12)
    pbo_table = pd.DataFrame([{"cost_bps": float(cost_bps), **pbo}])
    reality = pd.DataFrame(
        [
            {
                "cost_bps": float(cost_bps),
                "benchmark": "zero",
                **_reality_check(
                    unique,
                    n_bootstrap=bootstrap_count,
                    block_length=block_length,
                    seed=seed,
                ),
            },
            {
                "cost_bps": float(cost_bps),
                "benchmark": "LS57 excess",
                **_reality_check(
                    _excess_over(unique, unique["LS57"]),
                    n_bootstrap=bootstrap_count,
                    block_length=block_length,
                    seed=seed + 1,
                ),
            },
        ]
    )
    splits.insert(0, "cost_bps", float(cost_bps))
    return pd.DataFrame(dsr_rows), pbo_table, reality, splits


def classify_evidence(summary: Mapping[float, Mapping[str, float]], *, concentration: float) -> str:
    """Classify the frozen LS92 result without changing the research agenda."""
    def improves(cost: float) -> bool:
        row = summary[cost]
        return (
            float(row["candidate_multiple"]) > float(row["baseline_multiple"])
            and float(row["candidate_sharpe"]) > float(row["baseline_sharpe"])
            and float(row["candidate_mdd"]) >= float(row["baseline_mdd"]) - 0.01
        )

    if 13.0164 in summary and 20.0 in summary and improves(13.0164) and not improves(20.0):
        return "cost-fragile"
    if concentration >= 0.80:
        return "sleeve-concentrated"
    if all(improves(cost) for cost in (13.0164, 20.0)):
        robust = all(
            float(summary[cost]["bootstrap_ci_2_5"]) > 0.0
            and float(summary[cost]["years_outperforming"]) > float(summary[cost]["years_total"]) / 2.0
            and float(summary[cost]["worst_leave_one_year_excess_multiple"]) > 0.0
            for cost in (13.0164, 20.0)
        )
        if robust:
            return "robust-shadow"
    return "inconclusive"


def evidence_reasons(
    summary: Mapping[float, Mapping[str, float]],
    *,
    concentration: float,
) -> list[str]:
    """Human-readable reasons behind the evidence label."""
    lines: list[str] = []
    for cost in sorted(summary):
        row = summary[cost]
        lines.append(
            f"- {cost:g}bps: candidate {float(row['candidate_multiple']):.4f}x vs "
            f"baseline {float(row['baseline_multiple']):.4f}x; bootstrap 2.5% "
            f"{float(row['bootstrap_ci_2_5']):.2%}; years "
            f"{int(float(row['years_outperforming']))}/{int(float(row['years_total']))}; "
            f"worst leave-one-year excess {float(row['worst_leave_one_year_excess_multiple']):+.4f}x"
        )
    lines.append(
        f"- incremental concentration {concentration:.1%}; the remaining evidence is evaluated in "
        "the PBO, Reality Check and project-wide DSR tables above."
    )
    return lines


def _write_report(
    *,
    scenario_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    leave_one_out: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    daily_excess: pd.DataFrame,
    contributions: pd.DataFrame,
    correlations: pd.DataFrame,
    dsr: pd.DataFrame,
    pbo: pd.DataFrame,
    reality: pd.DataFrame,
    classification: str,
    reasons: list[str],
) -> str:
    lines = [
        f"# {TRIAL_ID}",
        "",
        "LS93 is a frozen robustness and attribution audit of LS92. It does not re-fit weights,",
        "scan parameters, change the live track, or send orders.",
        "",
        "## Scenario summary",
        "",
        dataframe_to_markdown(scenario_summary),
        "",
        "## Daily excess diagnostics",
        "",
        dataframe_to_markdown(daily_excess),
        "",
        "## Rolling 365D diagnostics",
        "",
        dataframe_to_markdown(rolling_summary),
        "",
        "## Yearly comparison",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## Leave-one-year-out",
        "",
        dataframe_to_markdown(leave_one_out),
        "",
        "## Sleeve contributions",
        "",
        dataframe_to_markdown(contributions),
        "",
        "## Correlations",
        "",
        dataframe_to_markdown(correlations),
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
        "The label describes the frozen evidence only. It does not promote LS92 or change the live",
        "track; the next research branch continues regardless of the label.",
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
    parser.add_argument("--seed", type=int, default=93)
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
    contribution_rows: list[pd.DataFrame] = []
    correlation_rows: list[pd.DataFrame] = []
    dsr_rows: list[pd.DataFrame] = []
    pbo_rows: list[pd.DataFrame] = []
    reality_rows: list[pd.DataFrame] = []
    splits_by_cost: dict[float, pd.DataFrame] = {}
    scenario_evidence: dict[float, dict[str, float]] = {}
    common_indices: dict[float, pd.DatetimeIndex] = {}

    for cost_bps, spec in SCENARIOS.items():
        sleeve_series = {
            name: load_return_series(path) for name, path in spec["sleeves"].items()
        }
        returns = align_return_series(sleeve_series, min_observations=MIN_COMMON_OBSERVATIONS)
        portfolio = combine_no_rebalance(returns, weights=WEIGHTS)
        saved = load_return_series(spec["portfolio"], value_column="portfolio_return")
        assert_matches_saved_portfolio(portfolio, saved, label=str(spec["label"]))
        common_indices[cost_bps] = returns.index
        all_returns = returns.copy()
        all_returns[str(spec["label"])] = portfolio
        baseline = returns["LS57"]
        summary_row = _scenario_summary(
            cost_bps=cost_bps,
            label=str(spec["label"]),
            returns=returns,
            candidate=portfolio,
            baseline=baseline,
        )
        scenario_rows.append(summary_row)
        robust_summary, yearly, leave_one_out, rolling = robustness_diagnostics(
            portfolio,
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

        contributions = sleeve_contributions(returns, weights=WEIGHTS, baseline="LS57")
        contributions.insert(0, "cost_bps", float(cost_bps))
        contributions.insert(1, "candidate", str(spec["label"]))
        contribution_rows.append(contributions)
        corr = returns.corr().stack().rename("correlation").reset_index()
        corr.columns = ["strategy_left", "strategy_right", "correlation"]
        corr.insert(0, "cost_bps", float(cost_bps))
        correlation_rows.append(corr)

        dsr, pbo, reality, splits = _multiple_testing(
            all_returns,
            cost_bps=cost_bps,
            candidate=str(spec["label"]),
            trial_summary=args.trial_summary,
            bootstrap_count=args.bootstrap_count,
            block_length=args.bootstrap_block_length,
            seed=args.seed,
        )
        dsr_rows.append(dsr)
        pbo_rows.append(pbo)
        reality_rows.append(reality)
        splits_by_cost[cost_bps] = splits
        excess = pd.Series(robust_summary)
        scenario_evidence[cost_bps] = {
            "candidate_multiple": float(summary_row["candidate_full_multiple"]),
            "baseline_multiple": float(summary_row["baseline_full_multiple"]),
            "candidate_sharpe": float(summary_row["candidate_full_sharpe"]),
            "baseline_sharpe": float(summary_row["baseline_full_sharpe"]),
            "candidate_mdd": float(summary_row["candidate_full_max_drawdown"]),
            "baseline_mdd": float(summary_row["baseline_full_max_drawdown"]),
            "bootstrap_ci_2_5": float(excess["bootstrap_total_log_excess_ci_2_5"]),
            "years_outperforming": float(excess["years_outperforming"]),
            "years_total": float(excess["years_total"]),
            "worst_leave_one_year_excess_multiple": float(excess["worst_leave_one_year_excess_multiple"]),
        }

    if len(common_indices) == 2:
        first, second = common_indices.values()
        if not first.equals(second):
            raise ValueError("the 13.0164bps and 20bps scenarios have different common samples")

    scenario_summary = pd.DataFrame(scenario_rows)
    yearly_table = pd.concat(yearly_rows, ignore_index=True)
    leave_table = pd.concat(leave_rows, ignore_index=True)
    rolling_table = pd.DataFrame(rolling_rows)
    daily_excess = pd.DataFrame(excess_rows)
    contributions_table = pd.concat(contribution_rows, ignore_index=True)
    correlations_table = pd.concat(correlation_rows, ignore_index=True)
    dsr_table = pd.concat(dsr_rows, ignore_index=True)
    pbo_table = pd.concat(pbo_rows, ignore_index=True)
    reality_table = pd.concat(reality_rows, ignore_index=True)
    contribution_13 = contributions_table.loc[contributions_table["cost_bps"] == 13.0164]
    concentration = float(contribution_13["excess_share"].clip(lower=0.0).max())
    classification = classify_evidence(scenario_evidence, concentration=concentration)
    reasons = evidence_reasons(scenario_evidence, concentration=concentration)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario_summary.to_csv(output_dir / "scenario_summary.csv", index=False)
    yearly_table.to_csv(output_dir / "yearly.csv", index=False)
    leave_table.to_csv(output_dir / "leave_one_year_out.csv", index=False)
    rolling_table.to_csv(output_dir / "rolling_365_summary.csv", index=False)
    daily_excess.to_csv(output_dir / "daily_excess.csv", index=False)
    contributions_table.to_csv(output_dir / "sleeve_contributions.csv", index=False)
    correlations_table.to_csv(output_dir / "correlations.csv", index=False)
    dsr_table.to_csv(output_dir / "deflated_sharpe.csv", index=False)
    pbo_table.to_csv(output_dir / "pbo.csv", index=False)
    reality_table.to_csv(output_dir / "reality_check.csv", index=False)
    for cost_bps, splits in splits_by_cost.items():
        splits.to_csv(output_dir / f"cscv_splits_{cost_bps:g}bps.csv", index=False)
    manifest = {
        "trial_id": TRIAL_ID,
        "weights": WEIGHTS,
        "scenarios": {
            str(cost): {
                "label": spec["label"],
                "portfolio": str(spec["portfolio"]),
                "sleeves": {name: str(path) for name, path in spec["sleeves"].items()},
            }
            for cost, spec in SCENARIOS.items()
        },
        "common_start": str(scenario_summary["common_start"].iloc[0]),
        "common_end": str(scenario_summary["common_end"].iloc[0]),
        "common_rows": int(scenario_summary["common_rows"].iloc[0]),
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
    report = _write_report(
        scenario_summary=scenario_summary,
        yearly=yearly_table,
        leave_one_out=leave_table,
        rolling_summary=rolling_table,
        daily_excess=daily_excess,
        contributions=contributions_table,
        correlations=correlations_table,
        dsr=dsr_table,
        pbo=pbo_table,
        reality=reality_table,
        classification=classification,
        reasons=reasons,
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(scenario_summary.to_string(index=False))
    print(rolling_table.to_string(index=False))
    print(pbo_table.to_string(index=False))
    print(f"classification: {classification}")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
