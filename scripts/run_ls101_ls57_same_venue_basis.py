"""LS101: LS57 residual-gross integration of the LS100 same-venue basis sleeve."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
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
from scripts.run_ls99_ls57_basis_residual import (  # noqa: E402
    ALLOCATIONS,
    GROSS_CAP,
    PRIMARY_COST_BPS,
    STRESS_COST_BPS,
    _load_series,
    _load_target_gross,
    _sample_metrics,
    classify_integration,
)

TRIAL_ID = "PR2026-11-LS101-LS57-SAME-VENUE-BASIS"
START = pd.Timestamp("2022-01-01", tz="UTC")
END = pd.Timestamp("2026-09-20", tz="UTC")
VALIDATION_START = pd.Timestamp("2024-01-01", tz="UTC")
SLEEVE_GROSS = 1.0
DEFAULT_LS57_DIR = PROJECT_ROOT / "reports/ls57_target_gross_2022_2026"
DEFAULT_LS100_DIR = PROJECT_ROOT / "reports/ls100_same_venue_basis_2026"


def combine_ls57_same_venue_basis(
    *,
    ls57_returns: pd.Series,
    ls57_gross: pd.Series,
    basis_returns: pd.Series,
    basis_active: pd.Series,
    allocation: float,
    gross_cap: float = GROSS_CAP,
    sleeve_gross: float = SLEEVE_GROSS,
    scale_cost_bps: float = PRIMARY_COST_BPS,
) -> pd.DataFrame:
    """Combine LS57 with LS100 while charging both entry and final exit.

    LS100 starts on 2022-01-02.  The base LS57 series starts on 2022-01-01;
    the inactive first day is represented by ``basis_active=False`` rather
    than a future-filled basis return.
    """
    if not np.isfinite(allocation) or allocation < 0.0:
        raise ValueError("allocation must be finite and non-negative")
    if not np.isfinite(gross_cap) or gross_cap <= 0.0:
        raise ValueError("gross_cap must be finite and positive")
    if not np.isfinite(sleeve_gross) or sleeve_gross <= 0.0:
        raise ValueError("sleeve_gross must be finite and positive")
    if not np.isfinite(scale_cost_bps) or scale_cost_bps < 0.0:
        raise ValueError("scale_cost_bps must be finite and non-negative")
    base = _load_or_validate_series(ls57_returns, "ls57_returns")
    gross = _load_or_validate_series(ls57_gross, "ls57_gross")
    basis = _load_or_validate_series(basis_returns, "basis_returns")
    active = pd.Series(basis_active, index=base.index, dtype=bool)
    if not (base.index.equals(gross.index) and base.index.equals(basis.index)):
        raise ValueError("LS57, gross and basis returns must be aligned on the same dates")
    if not np.isfinite(active.astype(int).to_numpy()).all():
        raise ValueError("basis_active contains non-finite values")
    if float(gross.max()) > float(gross_cap) + 1e-12:
        raise ValueError("LS57 gross exceeds the hard cap")
    residual = (float(gross_cap) - gross).clip(lower=0.0)
    requested = np.minimum(float(allocation), residual.to_numpy() / float(sleeve_gross))
    scale = pd.Series(np.where(active.to_numpy(), requested, 0.0), index=base.index, dtype=float)
    scale_delta = scale.diff().abs()
    if not scale_delta.empty:
        scale_delta.iloc[0] = abs(float(scale.iloc[0]))
        # The sleeve is assumed liquidated at the final observation.  The
        # diff only captures an in-sample drop to zero; add the terminal exit
        # explicitly when the final scale is still positive.
        scale_delta.iloc[-1] += abs(float(scale.iloc[-1]))
    scale_delta = scale_delta.fillna(0.0)
    cost = scale_delta * float(sleeve_gross) * float(scale_cost_bps) / 10_000.0
    combined_return = base + scale * basis - cost
    combined_gross = gross + scale * float(sleeve_gross)
    if float(combined_gross.max()) > float(gross_cap) + 1e-12:
        raise ValueError("combined gross exceeds the hard cap")
    return pd.DataFrame(
        {
            "ls57_return": base,
            "basis_return": basis,
            "scale": scale,
            "basis_contribution": scale * basis,
            "scale_cost": cost,
            "combined_return": combined_return,
            "ls57_gross": gross,
            "combined_gross": combined_gross,
        },
        index=base.index,
    )


def _load_or_validate_series(values: pd.Series, name: str) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce").astype(float).sort_index()
    if series.isna().any() or not np.isfinite(series.to_numpy()).all():
        raise ValueError(f"{name} contains missing or non-finite values")
    return series


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(
    *,
    summary: pd.DataFrame,
    baseline: dict[str, float],
    classification: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    rows: int,
) -> str:
    decision = {
        "pass": "PASS (research integration only; not live approval)",
        "partial": "PARTIAL (gross-budget candidate; not live approval)",
        "fail": "FAIL (keep LS57 and the live track unchanged)",
    }[classification]
    lines = [
        f"# {TRIAL_ID}",
        "",
        "LS101 integrates the LS100 Bitget same-venue price proxy into LS57 residual gross.",
        "Full-history funding remains a Binance proxy and exact Bitget funding is only a recent",
        "reconciliation window. It is a research result, not a live signal.",
        "",
        f"- Sample: {start} → {end} ({rows} daily observations)",
        f"- LS57 baseline: {baseline['full_multiple']:.4f}x / Sharpe {baseline['full_sharpe']:.4f} / MDD {baseline['full_max_drawdown']:.4%}",
        f"- LS100 sleeve actual gross: {SLEEVE_GROSS:.2f}x; combined hard cap: {GROSS_CAP:.2f}x",
        "- LS100 has no position on 2022-01-01; its first complete return is 2022-01-02",
        "- Costs are charged on LS100 scale entry, changes and final exit at 10bps or 20bps per leg per side",
        "",
        "## Results",
        "",
        dataframe_to_markdown(summary.round(6)),
        "",
        "## Decision",
        "",
        f"**{decision}**",
        "",
        "A pass only earns same-venue execution, funding settlement, margin and small-order",
        "research. It does not change `PR2026-10-D-L125-V2`.",
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
    gross = _load_target_gross(gross_path)
    gross = gross.loc[(gross.index >= START) & (gross.index <= END)].reindex(ls57.index).ffill().fillna(0.0)
    basis = _load_series(basis_path, value_column="daily_return")
    basis = basis.loc[(basis.index >= START) & (basis.index <= END)]
    if not basis.index.equals(ls57.index[1:]):
        missing = ls57.index.difference(basis.index)
        extra = basis.index.difference(ls57.index)
        raise ValueError(f"LS100 dates do not align with LS57: missing={missing[:3].tolist()} extra={extra[:3].tolist()}")
    active = pd.Series(False, index=ls57.index)
    active.loc[basis.index] = True
    basis = basis.reindex(ls57.index).fillna(0.0)

    basis_manifest = json.loads(basis_manifest_path.read_text(encoding="utf-8"))
    if basis_manifest.get("classification") != "pass":
        raise ValueError(f"LS100 is not classified pass: {basis_manifest.get('classification')}")
    if not basis_manifest.get("proxy_match"):
        raise ValueError("LS100 funding proxy did not match the exact subset")

    baseline_full = _sample_metrics(ls57)
    baseline_validation = _sample_metrics(ls57, validation=True)
    baseline = {
        "full_multiple": baseline_full["multiple"],
        "full_sharpe": baseline_full["sharpe"],
        "full_max_drawdown": baseline_full["max_drawdown"],
        "validation_multiple": baseline_validation["multiple"],
        "validation_sharpe": baseline_validation["sharpe"],
    }

    summary_rows: list[dict[str, Any]] = []
    daily_columns: dict[str, pd.Series] = {}
    for cost in (PRIMARY_COST_BPS, STRESS_COST_BPS):
        for allocation in ALLOCATIONS:
            combined = combine_ls57_same_venue_basis(
                ls57_returns=ls57,
                ls57_gross=gross,
                basis_returns=basis,
                basis_active=active,
                allocation=allocation,
                gross_cap=GROSS_CAP,
                sleeve_gross=SLEEVE_GROSS,
                scale_cost_bps=cost,
            )
            full = _sample_metrics(combined["combined_return"])
            validation = _sample_metrics(combined["combined_return"], validation=True)
            label = f"alloc_{int(round(allocation * 100)):03d}_cost_{int(round(cost)):03d}"
            daily_columns[f"{label}_return"] = combined["combined_return"]
            daily_columns[f"{label}_gross"] = combined["combined_gross"]
            summary_rows.append(
                {
                    "allocation": float(allocation),
                    "basis_cost_bps": float(cost),
                    "full_multiple": full["multiple"],
                    "full_sharpe": full["sharpe"],
                    "full_max_drawdown": full["max_drawdown"],
                    "validation_multiple": validation["multiple"],
                    "validation_sharpe": validation["sharpe"],
                    "mean_combined_gross": float(combined["combined_gross"].mean()),
                    "max_combined_gross": float(combined["combined_gross"].max()),
                    "mean_scale": float(combined["scale"].mean()),
                    "scale_change_days": int((combined["scale"].diff().abs() > 1e-12).sum()),
                    "total_scale_cost": float(combined["scale_cost"].sum()),
                }
            )
    summary = pd.DataFrame(summary_rows)
    classification = classify_integration(summary, baseline)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "overlay_summary.csv",
        "daily": output_dir / "daily_returns.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    pd.DataFrame(daily_columns, index=ls57.index).to_csv(files["daily"], index_label="date")
    files["report"].write_text(
        _report(
            summary=summary,
            baseline=baseline,
            classification=classification,
            start=ls57.index.min(),
            end=ls57.index.max(),
            rows=len(ls57),
        ),
        encoding="utf-8",
    )
    manifest = {
        "trial_id": TRIAL_ID,
        "classification": classification,
        "start": str(ls57.index.min()),
        "end": str(ls57.index.max()),
        "rows": int(len(ls57)),
        "allocations": list(ALLOCATIONS),
        "basis_cost_bps": [PRIMARY_COST_BPS, STRESS_COST_BPS],
        "gross_cap": GROSS_CAP,
        "sleeve_gross": SLEEVE_GROSS,
        "baseline": baseline,
        "ls57_daily_returns": str(ls57_path),
        "ls57_target_gross": str(gross_path),
        "ls100_daily_returns": str(basis_path),
        "ls100_manifest": str(basis_manifest_path),
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
