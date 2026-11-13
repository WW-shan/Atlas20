"""Combine LS57 and LS74 under LS57's residual gross budget."""

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

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

LS57_DIR = Path("reports/ls57_target_gross_2022_2026")
LS74_DIR = Path("reports/top20_churn_fullgross_2026")
ALLOCATIONS = (0.10, 0.20, 0.25)
GROSS_CAP = 1.50
SAMPLE_WINDOWS: dict[str, tuple[str, str]] = {
    "full": ("2022-01-01", "2026-09-20"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-20"),
}


def load_return_series(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    date_column = frame.columns[0]
    value_column = frame.columns[-1]
    index = pd.DatetimeIndex(pd.to_datetime(frame[date_column], utc=True)).sort_values()
    values = pd.to_numeric(frame[value_column], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index)
    if series.isna().any() or not np.isfinite(series.to_numpy(dtype=float)).all():
        raise ValueError(f"{path}: return series is not finite")
    return series[~series.index.duplicated(keep="last")].sort_index()


def load_target_gross(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    index = pd.DatetimeIndex(pd.to_datetime(frame["date"], utc=True)).sort_values()
    values = pd.to_numeric(frame["total_gross"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index)
    if series.isna().any() or not np.isfinite(series.to_numpy(dtype=float)).all():
        raise ValueError(f"{path}: target gross is not finite")
    return series[~series.index.duplicated(keep="last")].sort_index()


def scale_sleeve_to_residual_gross(
    *,
    ls57_gross: pd.Series,
    sleeve_gross: pd.Series,
    allocation: float,
    gross_cap: float = GROSS_CAP,
) -> pd.DataFrame:
    """Scale each day's sleeve so combined gross never exceeds the cap."""
    if allocation < 0.0 or gross_cap <= 0.0:
        raise ValueError("allocation must be non-negative and gross_cap positive")
    index = ls57_gross.index.union(sleeve_gross.index).sort_values()
    base_gross = ls57_gross.reindex(index).ffill().fillna(0.0).clip(lower=0.0)
    sleeve = sleeve_gross.reindex(index).fillna(0.0).clip(lower=0.0)
    residual = (float(gross_cap) - base_gross).clip(lower=0.0)
    scale = pd.Series(0.0, index=index, dtype=float)
    active = sleeve > 0.0
    scale.loc[active] = np.minimum(
        float(allocation),
        residual.loc[active] / sleeve.loc[active],
    )
    combined_gross = base_gross + scale * sleeve
    return pd.DataFrame(
        {
            "ls57_gross": base_gross,
            "sleeve_gross": sleeve,
            "residual_gross": residual,
            "sleeve_scale": scale,
            "combined_gross": combined_gross,
        },
        index=index,
    )


def _sample_metrics(series: pd.Series, sample: str) -> dict[str, float]:
    start, end = SAMPLE_WINDOWS[sample]
    segment = series.loc[
        (series.index >= pd.Timestamp(start, tz="UTC"))
        & (series.index <= pd.Timestamp(end, tz="UTC"))
    ]
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def select_allocation(summary: pd.DataFrame) -> float | None:
    passing = summary.loc[summary["passes_all"]].copy()
    if passing.empty:
        return None
    passing = passing.sort_values("allocation", ascending=False, kind="stable")
    return float(passing.iloc[0]["allocation"])


def _report(summary: pd.DataFrame, selected: float | None, baseline: dict[str, float]) -> str:
    lines = [
        "# LS57 + residual-gross Top20 churn overlay",
        "",
        f"- baseline LS57 full: {baseline['multiple']:.4f}x / Sharpe {baseline['sharpe']:.4f} / MDD {baseline['max_drawdown']:.4%}",
        "- all allocations are pre-registered: 10% / 20% / 25% NAV",
        f"- hard combined gross cap: {GROSS_CAP:.2f}x",
        "- return-space diagnostic only; funding is not included",
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
                    "mean_sleeve_scale",
                    "residual_scaled_days",
                    "passes_all",
                ]
            ].reset_index(drop=True)
        ),
        "",
    ]
    if selected is None:
        lines.extend(["## Decision", "", "No allocation passed all frozen overlay gates.", ""])
    else:
        lines.extend(
            [
                "## Decision",
                "",
                f"Selected largest passing allocation: **{selected:.0%} NAV**.",
                "This only earns a real funding/mark/fill merge study; it is not a live approval.",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-20")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date != "2022-01-01" or args.end_date != "2026-09-20":
        parser.error("LS75 is frozen to 2022-01-01 -> 2026-09-20")

    ls57_returns = load_return_series(LS57_DIR / "daily_returns.csv")
    ls57_gross = load_target_gross(LS57_DIR / "target_gross.csv")
    sleeve_returns = load_return_series(LS74_DIR / "daily_returns_20bps.csv")
    sleeve_gross = load_return_series(LS74_DIR / "gross_exposure_20bps.csv").clip(lower=0.0)

    lower = pd.Timestamp(args.start_date, tz="UTC")
    upper = pd.Timestamp(args.end_date, tz="UTC")
    ls57_returns = ls57_returns.loc[(ls57_returns.index >= lower) & (ls57_returns.index <= upper)]
    ls57_gross = ls57_gross.loc[(ls57_gross.index >= lower) & (ls57_gross.index <= upper)]
    base_gross = ls57_gross.reindex(ls57_returns.index).ffill().fillna(0.0)
    sleeve_returns = sleeve_returns.reindex(ls57_returns.index).fillna(0.0)
    sleeve_gross = sleeve_gross.reindex(ls57_returns.index).fillna(0.0)
    baseline = _sample_metrics(ls57_returns, "full")

    rows: list[dict[str, Any]] = []
    daily_frames: dict[float, pd.Series] = {}
    for allocation in ALLOCATIONS:
        scale_frame = scale_sleeve_to_residual_gross(
            ls57_gross=base_gross,
            sleeve_gross=sleeve_gross,
            allocation=allocation,
        ).reindex(ls57_returns.index)
        combined = ls57_returns + scale_frame["sleeve_scale"] * sleeve_returns
        daily_frames[allocation] = combined
        full = _sample_metrics(combined, "full")
        discovery = _sample_metrics(combined, "discovery")
        validation = _sample_metrics(combined, "validation")
        base_validation = _sample_metrics(ls57_returns, "validation")
        residual_scaled = (
            (scale_frame["sleeve_gross"] > 0.0)
            & (scale_frame["sleeve_scale"] + 1e-12 < allocation)
        )
        passes = (
            full["multiple"] > baseline["multiple"]
            and full["sharpe"] > baseline["sharpe"]
            and full["max_drawdown"] >= baseline["max_drawdown"] - 0.01
            and validation["multiple"] > base_validation["multiple"]
            and validation["sharpe"] > base_validation["sharpe"]
            and float(scale_frame["combined_gross"].max()) <= GROSS_CAP + 1e-10
        )
        rows.append(
            {
                "allocation": allocation,
                "full_multiple": full["multiple"],
                "full_sharpe": full["sharpe"],
                "full_max_drawdown": full["max_drawdown"],
                "discovery_multiple": discovery["multiple"],
                "discovery_sharpe": discovery["sharpe"],
                "validation_multiple": validation["multiple"],
                "validation_sharpe": validation["sharpe"],
                "mean_combined_gross": float(scale_frame["combined_gross"].mean()),
                "max_combined_gross": float(scale_frame["combined_gross"].max()),
                "mean_sleeve_scale": float(scale_frame["sleeve_scale"].mean()),
                "residual_scaled_days": int(residual_scaled.sum()),
                "passes_all": bool(passes),
            }
        )

    summary = pd.DataFrame(rows)
    selected = select_allocation(summary)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "overlay_summary.csv",
        "daily": output_dir / "overlay_daily_returns.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    if selected is not None:
        daily_frames[selected].rename("combined_return").to_csv(files["daily"])
    files["report"].write_text(_report(summary, selected, baseline), encoding="utf-8")
    manifest = {
        "candidate_id": "PR2026-11-LS75-LS57-CHURN-RESIDUAL-GROSS",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "allocations": list(ALLOCATIONS),
        "gross_cap": GROSS_CAP,
        "selected_allocation": selected,
        "baseline": baseline,
        "funding_included": False,
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_dir}; selected={selected}")


if __name__ == "__main__":
    main()
