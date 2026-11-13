"""LS102: frozen robustness audit of the LS101 same-venue basis overlay."""

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
from scripts.run_ls99_ls57_basis_residual import (  # noqa: E402
    GROSS_CAP,
    PRIMARY_COST_BPS,
    _load_series,
    _load_target_gross,
    _sample_metrics,
)
from scripts.run_ls101_ls57_same_venue_basis import (  # noqa: E402
    combine_ls57_same_venue_basis,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

TRIAL_ID = "PR2026-11-LS102-LS101-ROBUSTNESS"
START = pd.Timestamp("2022-01-01", tz="UTC")
END = pd.Timestamp("2026-09-20", tz="UTC")
COSTS_BPS = (10.0, 20.0, 50.0, 100.0)
ROLLING_WINDOW = 365
MIN_ROLLING_WIN_RATE = 0.75
MAX_ROLLING_TERMINAL_SHORTFALL = 0.02
MAX_MDD_DELTA = 0.02
MIN_MONTHLY_WIN_RATE = 0.75
DEFAULT_LS57_DIR = PROJECT_ROOT / "reports/ls57_target_gross_2022_2026"
DEFAULT_LS100_DIR = PROJECT_ROOT / "reports/ls100_same_venue_basis_2026"


def _mdd_from_returns(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    equity = (1.0 + clean).cumprod()
    wealth = pd.concat([pd.Series([1.0]), equity], ignore_index=True)
    return float((wealth / wealth.cummax() - 1.0).min())


def rolling_window_metrics(
    candidate: pd.Series,
    baseline: pd.Series,
    *,
    window: int,
) -> pd.DataFrame:
    """Compare overlapping fixed-length windows without claiming independence."""
    if window < 2:
        raise ValueError("window must be at least two observations")
    candidate = pd.to_numeric(candidate, errors="coerce").astype(float)
    baseline = pd.to_numeric(baseline, errors="coerce").astype(float)
    candidate, baseline = candidate.align(baseline, join="inner")
    if candidate.isna().any() or baseline.isna().any():
        raise ValueError("robustness series contain missing values")
    if len(candidate) < window:
        raise ValueError("not enough observations for the requested window")
    rows: list[dict[str, Any]] = []
    for end in range(window, len(candidate) + 1):
        cand_slice = candidate.iloc[end - window : end]
        base_slice = baseline.iloc[end - window : end]
        cand_metrics = _metrics_from_returns(cand_slice)
        base_metrics = _metrics_from_returns(base_slice)
        rows.append(
            {
                "end_date": candidate.index[end - 1],
                "candidate_multiple": cand_metrics["multiple"],
                "baseline_multiple": base_metrics["multiple"],
                "excess_multiple": cand_metrics["multiple"] - base_metrics["multiple"],
                "candidate_mdd": cand_metrics["max_drawdown"],
                "baseline_mdd": base_metrics["max_drawdown"],
                "mdd_delta": cand_metrics["max_drawdown"] - base_metrics["max_drawdown"],
            }
        )
    return pd.DataFrame(rows)


def monthly_start_metrics(candidate: pd.Series, baseline: pd.Series) -> pd.DataFrame:
    """Compare each calendar-month entry with the same final sample end."""
    candidate = pd.to_numeric(candidate, errors="coerce").astype(float)
    baseline = pd.to_numeric(baseline, errors="coerce").astype(float)
    candidate, baseline = candidate.align(baseline, join="inner")
    if candidate.isna().any() or baseline.isna().any():
        raise ValueError("robustness series contain missing values")
    period_index = pd.PeriodIndex(candidate.index.tz_localize(None), freq="M")
    periods = period_index.unique().sort_values()
    rows: list[dict[str, Any]] = []
    for period in periods:
        mask = period_index == period
        if not mask.any():
            continue
        cursor = candidate.index[mask][0]
        if len(candidate.loc[cursor:]) < 90:
            continue
        cand_metrics = _metrics_from_returns(candidate.loc[cursor:])
        base_metrics = _metrics_from_returns(baseline.loc[cursor:])
        rows.append(
            {
                "start_date": cursor,
                "candidate_multiple": cand_metrics["multiple"],
                "baseline_multiple": base_metrics["multiple"],
                "excess_multiple": cand_metrics["multiple"] - base_metrics["multiple"],
                "candidate_mdd": cand_metrics["max_drawdown"],
                "baseline_mdd": base_metrics["max_drawdown"],
                "mdd_delta": cand_metrics["max_drawdown"] - base_metrics["max_drawdown"],
            }
        )
    return pd.DataFrame(rows)


def classify_robustness(checks: Mapping[str, bool]) -> str:
    """Return pass only when every frozen audit check is true."""
    return "pass" if all(bool(value) for value in checks.values()) else "robustness-fail"


def _annual_returns(series: pd.Series) -> pd.Series:
    return series.groupby(series.index.year).apply(
        lambda values: float((1.0 + values).prod() - 1.0)
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(
    *,
    checks: pd.DataFrame,
    cost_stress: pd.DataFrame,
    yearly: pd.DataFrame,
    rolling: pd.DataFrame,
    monthly: pd.DataFrame,
    classification: str,
    baseline: Mapping[str, float],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> str:
    decision = "PASS (research robustness only; not live approval)" if classification == "pass" else "ROBUSTNESS-FAIL (not live approval)"
    lines = [
        f"# {TRIAL_ID}",
        "",
        "LS102 does not change LS101. It audits the frozen 100% residual candidate under",
        "additional basis cost, year, rolling-window and monthly-start stress.",
        "",
        f"- Sample: {start} → {end}",
        f"- LS57 baseline: {baseline['full_multiple']:.4f}x / Sharpe {baseline['full_sharpe']:.4f} / MDD {baseline['full_max_drawdown']:.4%}",
        f"- Rolling window: {ROLLING_WINDOW} daily observations; required win rate {MIN_ROLLING_WIN_RATE:.0%}",
        f"- Required worst terminal shortfall <= {MAX_ROLLING_TERMINAL_SHORTFALL:.1%}; required MDD delta <= {MAX_MDD_DELTA:.1%}",
        "",
        "## Cost stress",
        "",
        dataframe_to_markdown(cost_stress),
        "",
        "## Frozen checks",
        "",
        dataframe_to_markdown(checks),
        "",
        "## Yearly comparison",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## Rolling-window summary",
        "",
        dataframe_to_markdown(rolling),
        "",
        "## Monthly-start summary",
        "",
        dataframe_to_markdown(monthly),
        "",
        "## Decision",
        "",
        f"**{decision}**",
        "",
        "This audit still cannot close full-history Bitget funding or execution/margin/liquidation",
        "proof. It does not change `PR2026-10-D-L125-V2`.",
        "",
        "Research output only; no orders sent.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ls57-dir", type=Path, default=DEFAULT_LS57_DIR)
    parser.add_argument("--ls100-dir", type=Path, default=DEFAULT_LS100_DIR)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    ls57_path = args.ls57_dir / "daily_returns.csv"
    gross_path = args.ls57_dir / "target_gross.csv"
    basis_path = args.ls100_dir / "daily_returns.csv"
    basis_manifest_path = args.ls100_dir / "manifest.json"
    ls57 = _load_series(ls57_path, value_column="equity")
    ls57 = ls57.loc[(ls57.index >= START) & (ls57.index <= END)]
    gross = _load_target_gross(gross_path).loc[START:END].reindex(ls57.index).ffill().fillna(0.0)
    basis = _load_series(basis_path, value_column="daily_return").loc[START:END]
    if not basis.index.equals(ls57.index[1:]):
        raise ValueError("LS100 dates must be LS57 dates minus the inactive first day")
    active = pd.Series(False, index=ls57.index)
    active.loc[basis.index] = True
    basis = basis.reindex(ls57.index).fillna(0.0)
    manifest = json.loads(basis_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("classification") != "pass" or not manifest.get("proxy_match"):
        raise ValueError("LS101 input did not pass its own research gates")

    baseline_full = _sample_metrics(ls57)
    baseline = {
        "full_multiple": baseline_full["multiple"],
        "full_sharpe": baseline_full["sharpe"],
        "full_max_drawdown": baseline_full["max_drawdown"],
    }
    candidates: dict[float, pd.Series] = {}
    gross_max = 0.0
    for cost in COSTS_BPS:
        combined = combine_ls57_same_venue_basis(
            ls57_returns=ls57,
            ls57_gross=gross,
            basis_returns=basis,
            basis_active=active,
            allocation=1.0,
            gross_cap=GROSS_CAP,
            sleeve_gross=1.0,
            scale_cost_bps=cost,
        )
        candidates[cost] = combined["combined_return"]
        gross_max = max(gross_max, float(combined["combined_gross"].max()))
    candidate = candidates[PRIMARY_COST_BPS]
    baseline_annual = _annual_returns(ls57)
    candidate_annual = _annual_returns(candidate)
    yearly = pd.DataFrame(
        {
            "year": candidate_annual.index.astype(int),
            "candidate_return": candidate_annual.to_numpy(dtype=float),
            "baseline_return": baseline_annual.reindex(candidate_annual.index).to_numpy(dtype=float),
        }
    )
    yearly["excess_return"] = yearly["candidate_return"] - yearly["baseline_return"]
    yearly_wins = int((yearly["excess_return"] > 0.0).sum())

    best_year = int(yearly.loc[yearly["excess_return"].idxmax(), "year"])
    keep = candidate.index.year != best_year
    best_year_removed = _metrics_from_returns(candidate.loc[keep])
    best_year_base = _metrics_from_returns(ls57.loc[keep])
    best_year_check = best_year_removed["multiple"] > best_year_base["multiple"]

    rolling = rolling_window_metrics(candidate, ls57, window=ROLLING_WINDOW)
    rolling_win_rate = float((rolling["excess_multiple"] > 0.0).mean())
    rolling_worst = float(rolling["excess_multiple"].min())
    rolling_mdd_delta = float(rolling["mdd_delta"].max())
    monthly = monthly_start_metrics(candidate, ls57)
    monthly_win_rate = float((monthly["excess_multiple"] > 0.0).mean())
    monthly_mdd_delta = float(monthly["mdd_delta"].max())

    cost_checks: dict[str, bool] = {}
    cost_rows: list[dict[str, Any]] = []
    for cost in COSTS_BPS:
        metrics = _sample_metrics(candidates[cost])
        passes = (
            metrics["multiple"] > baseline["full_multiple"]
            and metrics["sharpe"] > baseline["full_sharpe"]
        )
        cost_checks[f"cost_{int(cost):03d}"] = passes
        cost_rows.append(
            {
                "cost_bps": cost,
                "multiple": metrics["multiple"],
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
                "baseline_multiple": baseline["full_multiple"],
                "baseline_sharpe": baseline["full_sharpe"],
                "passes": passes,
            }
        )
    cost_stress = pd.DataFrame(cost_rows)
    checks = {
        **cost_checks,
        "yearly_4_of_5": yearly_wins >= 4,
        "best_year_removed": bool(best_year_check),
        "rolling_win_rate": rolling_win_rate >= MIN_ROLLING_WIN_RATE,
        "rolling_worst_terminal": rolling_worst >= -MAX_ROLLING_TERMINAL_SHORTFALL,
        "rolling_mdd_delta": rolling_mdd_delta <= MAX_MDD_DELTA,
        "monthly_win_rate": monthly_win_rate >= MIN_MONTHLY_WIN_RATE,
        "monthly_mdd_delta": monthly_mdd_delta <= MAX_MDD_DELTA,
        "gross_cap": gross_max <= GROSS_CAP + 1e-12,
        "finite": bool(
            np.isfinite(candidate.to_numpy()).all()
            and np.isfinite(rolling.select_dtypes("number").to_numpy()).all()
            and np.isfinite(monthly.select_dtypes("number").to_numpy()).all()
        ),
    }
    classification = classify_robustness(checks)
    summary = pd.DataFrame(
        [
            {"check": key, "value": bool(value), "status": "pass" if value else "fail"}
            for key, value in checks.items()
        ]
        + [
            {"check": "yearly_wins", "value": yearly_wins, "status": "info"},
            {"check": "best_year", "value": best_year, "status": "info"},
            {"check": "rolling_win_rate", "value": rolling_win_rate, "status": "info"},
            {"check": "rolling_worst_excess", "value": rolling_worst, "status": "info"},
            {"check": "rolling_mdd_delta", "value": rolling_mdd_delta, "status": "info"},
            {"check": "monthly_win_rate", "value": monthly_win_rate, "status": "info"},
            {"check": "monthly_mdd_delta", "value": monthly_mdd_delta, "status": "info"},
            {"check": "max_gross", "value": gross_max, "status": "info"},
        ]
    )
    rolling_summary = pd.DataFrame(
        [
            {
                "window": ROLLING_WINDOW,
                "windows": len(rolling),
                "win_rate": rolling_win_rate,
                "worst_excess_multiple": rolling_worst,
                "max_mdd_delta": rolling_mdd_delta,
            }
        ]
    )
    monthly_summary = pd.DataFrame(
        [
            {
                "starts": len(monthly),
                "win_rate": monthly_win_rate,
                "worst_excess_multiple": float(monthly["excess_multiple"].min()),
                "max_mdd_delta": monthly_mdd_delta,
            }
        ]
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "summary.csv",
        "cost_stress": output_dir / "cost_stress.csv",
        "yearly": output_dir / "yearly_comparison.csv",
        "rolling": output_dir / "rolling_365d.csv",
        "monthly": output_dir / "monthly_starts.csv",
        "daily": output_dir / "daily_returns.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    cost_stress.to_csv(files["cost_stress"], index=False)
    yearly.to_csv(files["yearly"], index=False)
    rolling.to_csv(files["rolling"], index=False)
    monthly.to_csv(files["monthly"], index=False)
    pd.DataFrame(
        {
            "candidate_10bps": candidate,
            "candidate_20bps": candidates[20.0],
            "candidate_50bps": candidates[50.0],
            "candidate_100bps": candidates[100.0],
            "baseline": ls57,
        }
    ).to_csv(files["daily"], index_label="date")
    files["report"].write_text(
        _report(
            checks=summary,
            cost_stress=cost_stress,
            yearly=yearly,
            rolling=rolling_summary,
            monthly=monthly_summary,
            classification=classification,
            baseline=baseline,
            start=ls57.index.min(),
            end=ls57.index.max(),
        ),
        encoding="utf-8",
    )
    manifest = {
        "trial_id": TRIAL_ID,
        "classification": classification,
        "start": str(ls57.index.min()),
        "end": str(ls57.index.max()),
        "baseline": baseline,
        "costs_bps": list(COSTS_BPS),
        "rolling_window": ROLLING_WINDOW,
        "checks": checks,
        "yearly_wins": yearly_wins,
        "best_year": best_year,
        "max_gross": gross_max,
        "ls57_daily_returns_sha256": _sha256(ls57_path),
        "ls57_target_gross_sha256": _sha256(gross_path),
        "ls100_daily_returns_sha256": _sha256(basis_path),
        "ls100_manifest_sha256": _sha256(basis_manifest_path),
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"classification: {classification}")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
