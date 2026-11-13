"""LS57 + LS74 residual-gross overlay with Binance funding proxy."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.data import load_binance_funding  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_daily_btc_shock_continuation import held_phase_weights  # noqa: E402
from scripts.run_ls57_churn_overlay import (  # noqa: E402
    ALLOCATIONS,
    GROSS_CAP,
    LS57_DIR,
    LS74_DIR,
    _sample_metrics,
    load_return_series,
    load_target_gross,
    scale_sleeve_to_residual_gross,
)
def funding_pnl(weights: pd.DataFrame, funding_rates: pd.DataFrame) -> pd.Series:
    """Return funding PnL where positive rates are paid by longs and received by shorts."""
    aligned = funding_rates.reindex(index=weights.index, columns=weights.columns)
    contribution = -(weights * aligned.fillna(0.0)).sum(axis=1)
    return contribution.astype(float)


def daily_funding_rates(funding: pd.DataFrame) -> pd.DataFrame:
    """Aggregate settlement rates into UTC calendar-day sums."""
    if funding.empty:
        return funding
    grouped = funding.groupby(funding.index.normalize()).sum(min_count=1)
    grouped.index = pd.DatetimeIndex(grouped.index)
    return grouped.sort_index()


def _report(summary: pd.DataFrame, baseline: dict[str, float], coverage: dict[str, float]) -> str:
    return "\n".join(
        [
            "# LS57 + residual-gross churn overlay with funding",
            "",
            f"- baseline LS57 full: {baseline['multiple']:.4f}x / Sharpe {baseline['sharpe']:.4f} / MDD {baseline['max_drawdown']:.4%}",
            "- sleeve funding: Binance 8h settlement proxy, UTC daily sum; missing rates are skipped",
            f"- weighted funding coverage: {coverage['weighted_coverage']:.4%}",
            f"- missing held-weight observations: {coverage['missing_weight_observations']:.6f}",
            "- return-space diagnostic; Bitget mark/fill and liquidation are not included",
            "",
            "## Allocation results",
            "",
            dataframe_to_markdown(
                summary[
                    [
                        "allocation",
                        "full_multiple",
                        "full_sharpe",
                        "full_max_drawdown",
                        "validation_multiple",
                        "validation_sharpe",
                        "mean_combined_gross",
                        "max_combined_gross",
                        "funding_sum",
                        "scale_change_cost_sum",
                        "funding_coverage",
                        "passes_all",
                    ]
                ].reset_index(drop=True)
            ),
            "",
            "## Decision",
            "",
            "A pass is only a funding-aware overlay candidate; it still requires Bitget exact funding, mark/fill, margin and forward OOS verification.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-20")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date != "2022-01-01" or args.end_date != "2026-09-20":
        parser.error("LS76 is frozen to 2022-01-01 -> 2026-09-20")

    ls57_returns = load_return_series(LS57_DIR / "daily_returns.csv")
    ls57_gross = load_target_gross(LS57_DIR / "target_gross.csv")
    sleeve_returns = load_return_series(LS74_DIR / "daily_returns_20bps.csv")
    sleeve_gross = load_return_series(LS74_DIR / "gross_exposure_20bps.csv").clip(lower=0.0)
    targets = pd.read_csv(LS74_DIR / "targets.csv", index_col=0)
    targets.index = pd.DatetimeIndex(pd.to_datetime(targets.index, utc=True)).sort_values()
    targets = targets.reindex(columns=targets.columns.astype(str)).sort_index()

    lower = pd.Timestamp(args.start_date, tz="UTC")
    upper = pd.Timestamp(args.end_date, tz="UTC")
    ls57_returns = ls57_returns.loc[(ls57_returns.index >= lower) & (ls57_returns.index <= upper)]
    ls57_gross = ls57_gross.loc[(ls57_gross.index >= lower) & (ls57_gross.index <= upper)]
    base_gross = ls57_gross.reindex(ls57_returns.index).ffill().fillna(0.0)
    sleeve_returns = sleeve_returns.reindex(ls57_returns.index).fillna(0.0)
    sleeve_gross = sleeve_gross.reindex(ls57_returns.index).fillna(0.0)

    held = held_phase_weights(ls57_returns.index, targets, horizon=28)
    held_gross = held.abs().sum(axis=1)
    held = held.div(held_gross.replace(0.0, np.nan), axis=0).fillna(0.0)
    funding = load_binance_funding(Path("data/raw/binance_funding"), coins=held.columns)
    funding_daily = daily_funding_rates(funding).reindex(ls57_returns.index)
    funding_missing = held.abs().where(funding_daily.isna()).sum(axis=1)
    held_weight_total = held.abs().sum(axis=1)
    missing_weight = float(funding_missing.sum())
    total_weight = float(held_weight_total.sum())
    weighted_coverage = 1.0 - missing_weight / total_weight if total_weight > 0.0 else 1.0
    sleeve_funding = funding_pnl(held, funding_daily)

    baseline = _sample_metrics(ls57_returns, "full")
    rows: list[dict[str, Any]] = []
    selected_daily: pd.Series | None = None
    selected_allocation: float | None = None
    for allocation in ALLOCATIONS:
        scale_frame = scale_sleeve_to_residual_gross(
            ls57_gross=base_gross,
            sleeve_gross=sleeve_gross,
            allocation=allocation,
        ).reindex(ls57_returns.index)
        sleeve_total = sleeve_returns + sleeve_funding
        scale_delta = scale_frame["sleeve_scale"].diff().abs().fillna(
            scale_frame["sleeve_scale"].abs()
        )
        scale_cost = scale_delta * sleeve_gross.shift(1).fillna(sleeve_gross) * 20.0 / 10_000.0
        combined = ls57_returns + scale_frame["sleeve_scale"] * sleeve_total - scale_cost
        full = _sample_metrics(combined, "full")
        validation = _sample_metrics(combined, "validation")
        baseline_validation = _sample_metrics(ls57_returns, "validation")
        coverage = weighted_coverage
        passes = (
            full["multiple"] > baseline["multiple"]
            and full["sharpe"] > baseline["sharpe"]
            and full["max_drawdown"] >= baseline["max_drawdown"] - 0.01
            and validation["multiple"] > baseline_validation["multiple"]
            and validation["sharpe"] > baseline_validation["sharpe"]
            and float(scale_frame["combined_gross"].max()) <= GROSS_CAP + 1e-10
            and coverage >= 0.90
        )
        rows.append(
            {
                "allocation": allocation,
                "full_multiple": full["multiple"],
                "full_sharpe": full["sharpe"],
                "full_max_drawdown": full["max_drawdown"],
                "discovery_multiple": _sample_metrics(combined, "discovery")["multiple"],
                "discovery_sharpe": _sample_metrics(combined, "discovery")["sharpe"],
                "validation_multiple": validation["multiple"],
                "validation_sharpe": validation["sharpe"],
                "mean_combined_gross": float(scale_frame["combined_gross"].mean()),
                "max_combined_gross": float(scale_frame["combined_gross"].max()),
                "mean_sleeve_scale": float(scale_frame["sleeve_scale"].mean()),
                "funding_sum": float((scale_frame["sleeve_scale"] * sleeve_funding).sum()),
                "scale_change_cost_sum": float(scale_cost.sum()),
                "funding_coverage": coverage,
                "passes_all": bool(passes),
            }
        )
        if passes:
            selected_daily = combined
            selected_allocation = allocation

    summary = pd.DataFrame(rows)
    passing = summary.loc[summary["passes_all"]].sort_values("allocation", ascending=False)
    if not passing.empty:
        selected_allocation = float(passing.iloc[0]["allocation"])
        selected_daily = None
        # Rebuild the selected series deterministically from its row.
        allocation = selected_allocation
        scale_frame = scale_sleeve_to_residual_gross(
            ls57_gross=base_gross,
            sleeve_gross=sleeve_gross,
            allocation=allocation,
        ).reindex(ls57_returns.index)
        selected_daily = ls57_returns + scale_frame["sleeve_scale"] * (sleeve_returns + sleeve_funding)
    else:
        selected_allocation = None

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "overlay_summary.csv",
        "daily": output_dir / "selected_daily_returns.csv",
        "funding": output_dir / "sleeve_funding.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    sleeve_funding.rename("funding_return").to_csv(files["funding"])
    if selected_daily is not None:
        selected_daily.rename("combined_return").to_csv(files["daily"])
    coverage = {"weighted_coverage": weighted_coverage, "missing_weight_observations": missing_weight}
    files["report"].write_text(_report(summary, baseline, coverage), encoding="utf-8")
    manifest = {
        "candidate_id": "PR2026-11-LS76-LS57-CHURN-RESIDUAL-GROSS-FUNDING",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "allocations": list(ALLOCATIONS),
        "gross_cap": GROSS_CAP,
        "selected_allocation": selected_allocation,
        "baseline": baseline,
        "funding_source": "binance-proxy",
        "funding_weighted_coverage": weighted_coverage,
        "funding_missing_weight": missing_weight,
        "funding_stress": "none",
        "funding_included": True,
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_dir}; selected={selected_allocation}")


if __name__ == "__main__":
    main()
