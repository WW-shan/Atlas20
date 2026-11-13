"""Stress-test the LS57 + residual-gross churn overlay."""

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
from scripts.run_ls57_churn_overlay_funding import (  # noqa: E402
    daily_funding_rates,
    funding_pnl,
)

COST_FILES = {
    20.0: "daily_returns_20bps.csv",
    50.0: "daily_returns_50bps.csv",
    100.0: "daily_returns_100bps.csv",
}
FUNDING_SCENARIOS = ("normal", "3x_adverse")


def adverse_funding_pnl(
    weights: pd.DataFrame,
    funding_rates: pd.DataFrame,
    *,
    multiplier: float = 3.0,
) -> pd.Series:
    """Charge every position the adverse absolute rate with a multiplier."""
    adverse_rates = funding_rates.abs().mul(np.sign(weights), fill_value=0.0)
    return float(multiplier) * funding_pnl(weights, adverse_rates)


def _report(summary: pd.DataFrame, selected: float | None) -> str:
    lines = [
        "# LS57 + churn overlay stress matrix",
        "",
        "- sleeve cost: 20/50/100bps per side",
        "- funding: Binance proxy normal or 3x adverse absolute-rate stress",
        "- LS57 leg remains at 20bps; this tests the overlay, not a full 100bps LS57 rerun",
        "- residual gross cap: 1.50x",
        "",
        "## Stress results",
        "",
        dataframe_to_markdown(summary.reset_index(drop=True)),
        "",
        "## Decision",
        "",
    ]
    if selected is None:
        lines.append("No allocation passed the 100bps + 3x-adverse worst-case gate.")
    else:
        lines.append(
            f"Largest allocation passing the worst case: **{selected:.0%} NAV**; "
            "still requires a real combined Bitget engine before shadow promotion."
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-20")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date != "2022-01-01" or args.end_date != "2026-09-20":
        parser.error("LS77 is frozen to 2022-01-01 -> 2026-09-20")

    ls57_returns = load_return_series(LS57_DIR / "daily_returns.csv")
    ls57_gross = load_target_gross(LS57_DIR / "target_gross.csv")
    sleeve_gross = load_return_series(LS74_DIR / "gross_exposure_20bps.csv").clip(lower=0.0)
    targets = pd.read_csv(LS74_DIR / "targets.csv", index_col=0)
    targets.index = pd.DatetimeIndex(pd.to_datetime(targets.index, utc=True)).sort_values()

    lower = pd.Timestamp(args.start_date, tz="UTC")
    upper = pd.Timestamp(args.end_date, tz="UTC")
    ls57_returns = ls57_returns.loc[(ls57_returns.index >= lower) & (ls57_returns.index <= upper)]
    ls57_gross = ls57_gross.loc[(ls57_gross.index >= lower) & (ls57_gross.index <= upper)]
    base_gross = ls57_gross.reindex(ls57_returns.index).ffill().fillna(0.0)
    sleeve_gross = sleeve_gross.reindex(ls57_returns.index).fillna(0.0)

    held = held_phase_weights(ls57_returns.index, targets, horizon=28)
    held = held.div(held.abs().sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    funding = load_binance_funding(Path("data/raw/binance_funding"), coins=held.columns)
    funding_daily = daily_funding_rates(funding).reindex(ls57_returns.index)
    normal_funding = funding_pnl(held, funding_daily)
    stressed_funding = adverse_funding_pnl(held, funding_daily, multiplier=3.0)
    funding_by_scenario = {"normal": normal_funding, "3x_adverse": stressed_funding}

    base_full = _sample_metrics(ls57_returns, "full")
    base_validation = _sample_metrics(ls57_returns, "validation")
    rows: list[dict[str, Any]] = []
    for allocation in ALLOCATIONS:
        for cost, filename in COST_FILES.items():
            sleeve_returns = load_return_series(LS74_DIR / filename).reindex(ls57_returns.index).fillna(0.0)
            for funding_scenario in FUNDING_SCENARIOS:
                scale_frame = scale_sleeve_to_residual_gross(
                    ls57_gross=base_gross,
                    sleeve_gross=sleeve_gross,
                    allocation=allocation,
                ).reindex(ls57_returns.index)
                scale_delta = scale_frame["sleeve_scale"].diff().abs().fillna(
                    scale_frame["sleeve_scale"].abs()
                )
                scale_cost = scale_delta * sleeve_gross.shift(1).fillna(sleeve_gross) * cost / 10_000.0
                sleeve_total = sleeve_returns + funding_by_scenario[funding_scenario]
                combined = ls57_returns + scale_frame["sleeve_scale"] * sleeve_total - scale_cost
                full = _sample_metrics(combined, "full")
                validation = _sample_metrics(combined, "validation")
                passes = (
                    full["multiple"] > base_full["multiple"]
                    and full["sharpe"] > base_full["sharpe"]
                    and full["max_drawdown"] >= base_full["max_drawdown"] - 0.01
                    and validation["multiple"] > base_validation["multiple"]
                    and validation["sharpe"] > base_validation["sharpe"]
                    and float(scale_frame["combined_gross"].max()) <= GROSS_CAP + 1e-10
                )
                rows.append(
                    {
                        "allocation": allocation,
                        "sleeve_cost_bps": cost,
                        "funding_scenario": funding_scenario,
                        "full_multiple": full["multiple"],
                        "full_sharpe": full["sharpe"],
                        "full_max_drawdown": full["max_drawdown"],
                        "validation_multiple": validation["multiple"],
                        "validation_sharpe": validation["sharpe"],
                        "max_combined_gross": float(scale_frame["combined_gross"].max()),
                        "funding_sum": float((scale_frame["sleeve_scale"] * funding_by_scenario[funding_scenario]).sum()),
                        "scale_change_cost_sum": float(scale_cost.sum()),
                        "passes_all": bool(passes),
                    }
                )

    summary = pd.DataFrame(rows)
    worst = summary.loc[(summary["sleeve_cost_bps"] == 100.0) & (summary["funding_scenario"] == "3x_adverse")]
    passing = worst.loc[worst["passes_all"]].sort_values("allocation", ascending=False)
    selected = None if passing.empty else float(passing.iloc[0]["allocation"])

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "stress_summary.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    files["report"].write_text(_report(summary, selected), encoding="utf-8")
    manifest = {
        "candidate_id": "PR2026-11-LS77-LS57-CHURN-OVERLAY-STRESS",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "allocations": list(ALLOCATIONS),
        "costs_bps": list(COST_FILES),
        "funding_scenarios": list(FUNDING_SCENARIOS),
        "selected_allocation_worst_case": selected,
        "funding_included": True,
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_dir}; selected={selected}")


if __name__ == "__main__":
    main()
