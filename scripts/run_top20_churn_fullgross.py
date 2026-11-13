"""Backtest LS74: LS73 churn with active-day gross normalized to one."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.diagnose_top20_membership_events import membership_matrix  # noqa: E402
from scripts.run_daily_btc_shock_continuation import backtest_continuation  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402
from scripts.run_top20_churn_gated import (  # noqa: E402
    CONFIRMATION_DAYS,
    DEFAULT_END,
    DEFAULT_START,
    HOLD_DAYS,
    build_gate_series,
    build_gated_targets,
)
from scripts.run_top20_churn_short import load_ls57_returns  # noqa: E402

COSTS_BPS = (2.0, 20.0, 50.0, 100.0)
LS73_FULL_MULTIPLE_20 = 1.060753931953299
SAMPLE_WINDOWS: dict[str, tuple[str, str]] = {
    "full": (DEFAULT_START, DEFAULT_END),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", DEFAULT_END),
    "pre2022": ("2021-01-01", "2021-12-31"),
}


def _sample_metrics(series: pd.Series, sample: str) -> dict[str, float]:
    start, end = SAMPLE_WINDOWS[sample]
    segment = series.loc[
        (series.index >= pd.Timestamp(start, tz="UTC"))
        & (series.index <= pd.Timestamp(end, tz="UTC"))
    ]
    if segment.empty:
        return {"multiple": float("nan"), "cagr": float("nan"), "sharpe": float("nan"), "max_drawdown": float("nan")}
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def acceptance_checks(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "discovery_sharpe_20_positive": float(row["discovery_sharpe_20"]) > 0.0,
        "validation_sharpe_20_positive": float(row["validation_sharpe_20"]) > 0.0,
        "pre2022_multiple_at_least_0_92": float(row["pre2022_multiple_20"]) >= 0.92,
        "full_multiple_20_above_one": float(row["full_multiple_20"]) > 1.0,
        "full_multiple_50_above_one": float(row["full_multiple_50"]) > 1.0,
        "full_sharpe_20_above_0_5": float(row["full_sharpe_20"]) > 0.5,
        "full_mdd_20_no_worse_than_minus_30pct": float(row["full_max_drawdown_20"]) >= -0.30,
        "full_multiple_at_least_1_10x_ls73": float(row["full_multiple_20"]) >= 1.10 * LS73_FULL_MULTIPLE_20,
    }


def _report(
    row: dict[str, Any],
    metrics: pd.DataFrame,
    checks: dict[str, bool],
    overlay: pd.DataFrame,
    contributions: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# Top20 churn short with full-gross event tranches",
            "",
            "- frozen LS73 event rule: m=7, h=28, alt_rel_60 gate, BTC-hedged entry+exit churn",
            "- only change: normalize each active day to gross 1.0; no events means cash",
            "- total gross remains <=1.0; no added leverage",
            "- costs: 2/20/50/100bps per side; funding excluded",
            "",
            "## Selected scenario",
            "",
            dataframe_to_markdown(
                pd.DataFrame([row]).T.reset_index().rename(columns={"index": "field", 0: "value"})
            ),
            "",
            "## Acceptance checks",
            "",
            *[f"- [{'x' if passed else ' '}] `{name}`" for name, passed in checks.items()],
            "",
            "## Sample metrics",
            "",
            dataframe_to_markdown(metrics),
            "",
            "## Asset contribution before costs",
            "",
            dataframe_to_markdown(contributions),
            "",
            "## Return-space LS57 overlay",
            "",
            dataframe_to_markdown(overlay),
            "",
            "## Guardrail",
            "",
            "Full-gross normalization increases per-event concentration relative to LS73. The result is not live-ready without funding, Bitget mark/fill, per-coin caps and forward OOS verification.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date != DEFAULT_START or args.end_date != DEFAULT_END:
        parser.error("LS74 is frozen to 2021-01-01 -> 2026-11-12; register another family for another window")

    _, market, universe, raw_index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    index = pd.DatetimeIndex(pd.to_datetime(raw_index, utc=True)).sort_values()
    price = market.price.copy()
    price.index = pd.DatetimeIndex(pd.to_datetime(price.index, utc=True)).sort_values()
    price = price.reindex(index).sort_index()
    returns = market.returns.copy()
    returns.index = pd.DatetimeIndex(pd.to_datetime(returns.index, utc=True)).sort_values()
    returns = returns.reindex(index).sort_index()
    assets = sorted(
        [str(asset) for asset in price.columns if str(asset) != "bitcoin" and str(asset) in returns.columns],
        key=str.casefold,
    )
    present = membership_matrix(universe, index=index)
    gates = build_gate_series(price=price, returns=returns, present=present, assets=assets)
    targets = build_gated_targets(present=present, gate=gates["alt_rel_60"], assets=assets)

    results: dict[float, Any] = {}
    for cost in COSTS_BPS:
        results[cost] = backtest_continuation(
            index=index,
            returns=returns[["bitcoin", *assets]],
            targets=targets,
            horizon=HOLD_DAYS,
            cost_bps=cost,
            normalize_gross=True,
        )
    result_20 = results[20.0]
    row: dict[str, Any] = {
        "variant_id": "CHURN_FULLGROSS_m7_h28_alt_rel_60",
        "confirmation_days": CONFIRMATION_DAYS,
        "hold_days": HOLD_DAYS,
        "turnover_20": float(result_20.turnover.sum()),
        "average_active_gross_20": float(result_20.gross_exposure.mean()),
        "max_gross_20": float(result_20.gross_exposure.max()),
        "missing_20": int(result_20.missing_return_observations),
    }
    for sample in SAMPLE_WINDOWS:
        m20 = _sample_metrics(result_20.daily_returns, sample)
        m50 = _sample_metrics(results[50.0].daily_returns, sample)
        for key, value in m20.items():
            row[f"{sample}_{key}_20"] = value
        row[f"{sample}_multiple_50"] = m50["multiple"]
        row[f"{sample}_sharpe_50"] = m50["sharpe"]
    checks = acceptance_checks(row)
    metrics = pd.DataFrame(
        [
            {"series": "churn_fullgross_20bps", "sample": sample, **_sample_metrics(result_20.daily_returns, sample)}
            for sample in SAMPLE_WINDOWS
        ]
    )
    aligned_returns = returns[["bitcoin", *assets]].reindex(
        index=result_20.weights.index,
        columns=result_20.weights.columns,
    )
    pnl = (result_20.weights * aligned_returns.fillna(0.0)).sum(axis=0)
    contributions = (
        pnl.rename("pnl_before_costs").sort_values(ascending=False).rename_axis("asset").reset_index().head(20)
    )

    ls57 = load_ls57_returns()
    start = max(ls57.index.min(), result_20.daily_returns.index.min())
    end = min(ls57.index.max(), result_20.daily_returns.index.max())
    base = ls57.loc[(ls57.index >= start) & (ls57.index <= end)]
    sleeve = result_20.daily_returns.reindex(base.index).fillna(0.0)
    overlay_rows: list[dict[str, Any]] = []
    for allocation in (0.10, 0.20):
        combined = base + allocation * sleeve
        for sample in ("full", "discovery", "validation"):
            overlay_rows.append(
                {"series": f"ls57_plus_{int(round(allocation * 100)):02d}pct_fullgross", "sample": sample, **_sample_metrics(combined, sample)}
            )
    overlay = pd.DataFrame(overlay_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "trial_summary.csv",
        "daily": output_dir / "daily_returns_20bps.csv",
        "gross": output_dir / "gross_exposure_20bps.csv",
        "targets": output_dir / "targets.csv",
        "metrics": output_dir / "selected_metrics.csv",
        "contributions": output_dir / "asset_contributions.csv",
        "overlay": output_dir / "ls57_overlay.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    pd.DataFrame([row]).to_csv(files["summary"], index=False)
    result_20.daily_returns.to_csv(files["daily"])
    result_20.gross_exposure.to_csv(files["gross"])
    targets.to_csv(files["targets"])
    metrics.to_csv(files["metrics"], index=False)
    contributions.to_csv(files["contributions"], index=False)
    overlay.to_csv(files["overlay"], index=False)
    files["report"].write_text(
        _report(row, metrics, checks, overlay, contributions),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS74-TOP20-CHURN-ALT-WEAK-FULLGROSS",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "confirmation_days": CONFIRMATION_DAYS,
        "hold_days": HOLD_DAYS,
        "gate": "alt_rel_60",
        "costs_bps": list(COSTS_BPS),
        "gross_policy": "active-day normalization to 1.0; cash when no active event",
        "max_gross": float(result_20.gross_exposure.max()),
        "acceptance_checks": checks,
        "acceptance_verdict": "pass" if all(checks.values()) else "fail",
        "funding_included": False,
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_dir}; verdict={manifest['acceptance_verdict']}")


if __name__ == "__main__":
    main()
