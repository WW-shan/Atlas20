"""LS99: integrate the LS98 BTC/ETH basis sleeve into LS57 residual gross.

Research-only.  LS57 target gross is treated as the priority book; the basis
sleeve may use only the unused gross below the frozen 1.45x cap.  The basis
leg is a cross-venue spot/perp proxy, so a passing result still requires a
same-venue execution study before it can influence the live track.
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
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

TRIAL_ID = "PR2026-11-LS99-LS57-BASIS-RESIDUAL"
START = pd.Timestamp("2022-01-01", tz="UTC")
END = pd.Timestamp("2026-09-20", tz="UTC")
VALIDATION_START = pd.Timestamp("2024-01-01", tz="UTC")
ALLOCATIONS = (0.25, 0.50, 1.00)
BASIS_COSTS_BPS = (10.0, 20.0)
PRIMARY_COST_BPS = 10.0
STRESS_COST_BPS = 20.0
GROSS_CAP = 1.45
SLEEVE_GROSS = 1.0
DEFAULT_LS57_DIR = PROJECT_ROOT / "reports/ls57_target_gross_2022_2026"
DEFAULT_BASIS_DIR = PROJECT_ROOT / "reports/ls98_cross_venue_basis_2026"


def _as_finite_series(values: pd.Series, *, name: str) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce").astype(float)
    if series.isna().any() or not np.isfinite(series.to_numpy()).all():
        raise ValueError(f"{name} contains missing or non-finite values")
    return series.astype(float)


def residual_scale(
    gross: pd.Series,
    *,
    allocation: float = 1.0,
    gross_cap: float = GROSS_CAP,
    sleeve_gross: float = SLEEVE_GROSS,
) -> pd.Series:
    """Scale the full basis sleeve into LS57's unused gross.

    The returned scale is the fraction of the sleeve's normal 1.0x gross.  It
    is capped by both the requested allocation and the residual budget.
    """
    if not np.isfinite(allocation) or allocation < 0.0:
        raise ValueError("allocation must be finite and non-negative")
    if not np.isfinite(gross_cap) or gross_cap <= 0.0:
        raise ValueError("gross_cap must be finite and positive")
    if not np.isfinite(sleeve_gross) or sleeve_gross <= 0.0:
        raise ValueError("sleeve_gross must be finite and positive")
    base = _as_finite_series(gross, name="gross")
    if (base < 0.0).any():
        raise ValueError("gross must be non-negative")
    residual = (float(gross_cap) - base).clip(lower=0.0)
    scale = np.minimum(float(allocation), residual.to_numpy() / float(sleeve_gross))
    return pd.Series(scale, index=base.index, name="scale", dtype=float)


def combine_residual_basis(
    *,
    ls57_returns: pd.Series,
    ls57_gross: pd.Series,
    basis_returns: pd.Series,
    allocation: float,
    gross_cap: float = GROSS_CAP,
    sleeve_gross: float = SLEEVE_GROSS,
    scale_cost_bps: float = PRIMARY_COST_BPS,
) -> pd.DataFrame:
    """Combine LS57 and the scaled basis sleeve without look-ahead fills.

    LS98's net return already pays the basis sleeve's entry/exit costs at full
    gross.  This function therefore charges only *scale changes*: the first
    day is not charged twice.  Missing dates are refused rather than filled.
    """
    if not np.isfinite(scale_cost_bps) or scale_cost_bps < 0.0:
        raise ValueError("scale_cost_bps must be finite and non-negative")
    base = _as_finite_series(ls57_returns, name="ls57_returns").sort_index()
    gross = _as_finite_series(ls57_gross, name="ls57_gross").sort_index()
    sleeve = _as_finite_series(basis_returns, name="basis_returns").sort_index()
    if not (base.index.equals(gross.index) and base.index.equals(sleeve.index)):
        raise ValueError("LS57, gross and basis returns must be aligned on the same dates")
    if (gross < 0.0).any():
        raise ValueError("ls57_gross must be non-negative")
    scale = residual_scale(
        gross,
        allocation=allocation,
        gross_cap=gross_cap,
        sleeve_gross=sleeve_gross,
    )
    scale_delta = scale.diff().abs()
    if not scale_delta.empty:
        scale_delta.iloc[0] = abs(float(scale.iloc[0]))
    scale_delta = scale_delta.fillna(0.0)
    scale_cost = scale_delta * float(sleeve_gross) * float(scale_cost_bps) / 10_000.0
    basis_contribution = scale * sleeve
    combined_return = base + basis_contribution - scale_cost
    combined_gross = gross + scale * float(sleeve_gross)
    if float(combined_gross.max()) > float(gross_cap) + 1e-12:
        raise ValueError("combined gross exceeds the hard cap")
    return pd.DataFrame(
        {
            "ls57_return": base,
            "basis_return": sleeve,
            "scale": scale,
            "basis_contribution": basis_contribution,
            "scale_cost": scale_cost,
            "combined_return": combined_return,
            "ls57_gross": gross,
            "combined_gross": combined_gross,
        },
        index=base.index,
    )


def _passes_integration_gate(row: Mapping[str, Any], baseline: Mapping[str, float]) -> bool:
    values = {key: float(row[key]) for key in (
        "full_multiple",
        "full_sharpe",
        "full_max_drawdown",
        "validation_multiple",
        "validation_sharpe",
    )}
    if not all(np.isfinite(value) for value in values.values()):
        return False
    return (
        values["full_multiple"] >= float(baseline["full_multiple"]) - 1e-12
        and values["full_sharpe"] >= float(baseline["full_sharpe"]) - 1e-12
        and values["full_max_drawdown"] >= float(baseline["full_max_drawdown"]) - 0.01 - 1e-12
        and values["validation_multiple"] >= float(baseline["validation_multiple"]) - 1e-12
        and values["validation_sharpe"] >= float(baseline["validation_sharpe"]) - 1e-12
    )


def classify_integration(rows: pd.DataFrame, baseline: Mapping[str, float]) -> str:
    """Return pass / partial / fail under the frozen LS99 acceptance rules.

    ``pass`` requires all three pre-registered primary allocations to clear
    the full and validation gates and the 20bps 100% stress row (when present)
    to remain at least equal to LS57's full multiple and Sharpe.  A successful
    100% row with a weaker smaller allocation is a ``partial`` gross-budget
    candidate, not a pass across the pre-registered allocation set.
    """
    required = {
        "allocation",
        "basis_cost_bps",
        "full_multiple",
        "full_sharpe",
        "full_max_drawdown",
        "validation_multiple",
        "validation_sharpe",
    }
    missing = sorted(required.difference(rows.columns))
    if missing:
        raise ValueError(f"integration rows missing columns: {missing}")
    primary = rows.loc[np.isclose(rows["basis_cost_bps"].astype(float), PRIMARY_COST_BPS)].copy()
    if primary.empty:
        return "fail"
    primary["allocation"] = primary["allocation"].astype(float).round(8)
    if primary["allocation"].duplicated().any():
        raise ValueError("primary integration rows contain duplicate allocations")
    by_allocation = {float(row["allocation"]): row for _, row in primary.iterrows()}
    full_100 = by_allocation.get(1.0)
    if full_100 is None or not _passes_integration_gate(full_100, baseline):
        return "fail"

    stress = rows.loc[
        np.isclose(rows["basis_cost_bps"].astype(float), STRESS_COST_BPS)
        & np.isclose(rows["allocation"].astype(float), 1.0)
    ]
    if not stress.empty:
        stress_row = stress.iloc[-1]
        if (
            float(stress_row["full_multiple"]) < float(baseline["full_multiple"]) - 1e-12
            or float(stress_row["full_sharpe"]) < float(baseline["full_sharpe"]) - 1e-12
        ):
            return "fail"

    all_primary = all(
        allocation in by_allocation
        and _passes_integration_gate(by_allocation[allocation], baseline)
        for allocation in ALLOCATIONS
    )
    return "pass" if all_primary else "partial"


def _load_series(path: Path, *, value_column: str | None = None) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"{path}: empty CSV")
    date_column = frame.columns[0]
    if value_column is None:
        value_column = frame.columns[-1]
    if value_column not in frame.columns:
        raise ValueError(f"{path}: missing value column {value_column!r}")
    dates = pd.DatetimeIndex(pd.to_datetime(frame[date_column], utc=True))
    values = pd.to_numeric(frame[value_column], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=dates).sort_index()
    if series.index.duplicated().any():
        raise ValueError(f"{path}: duplicate dates")
    if series.isna().any() or not np.isfinite(series.to_numpy()).all():
        raise ValueError(f"{path}: non-finite values")
    return series.astype(float)


def _load_target_gross(path: Path) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if "date" not in frame.columns or "total_gross" not in frame.columns:
        raise ValueError(f"{path}: expected date and total_gross columns")
    dates = pd.DatetimeIndex(pd.to_datetime(frame["date"], utc=True))
    values = pd.to_numeric(frame["total_gross"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=dates).sort_index()
    if series.index.duplicated().any():
        raise ValueError(f"{path}: duplicate dates")
    if series.isna().any() or not np.isfinite(series.to_numpy()).all():
        raise ValueError(f"{path}: non-finite target gross")
    if (series < 0.0).any():
        raise ValueError(f"{path}: negative target gross")
    return series.astype(float)


def _sample_metrics(series: pd.Series, *, validation: bool = False) -> dict[str, float]:
    segment = series.loc[
        (series.index >= (VALIDATION_START if validation else START))
        & (series.index <= END)
    ]
    if segment.empty:
        raise ValueError("requested sample is empty")
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def _load_basis_gross_returns(path: Path) -> pd.Series:
    """Load LS98 pre-cost basis/funding returns and validate its 10bps net.

    The returned series excludes LS98 turnover costs.  LS99 charges costs on
    the actual scaled entry/exit/rebalance instead, which avoids charging the
    full-sleeve cost at a fractional scale and then scaling it again.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    date_column = frame.columns[0]
    if "daily_return" not in frame.columns or "turnover" not in frame.columns:
        raise ValueError(f"{path}: expected daily_return and turnover columns")
    dates = pd.DatetimeIndex(pd.to_datetime(frame[date_column], utc=True))
    daily = pd.Series(pd.to_numeric(frame["daily_return"], errors="coerce").to_numpy(), index=dates)
    turnover = pd.Series(pd.to_numeric(frame["turnover"], errors="coerce").to_numpy(), index=dates)
    daily = daily.sort_index()
    turnover = turnover.sort_index()
    if daily.index.duplicated().any() or turnover.index.duplicated().any():
        raise ValueError(f"{path}: duplicate dates")
    if daily.isna().any() or turnover.isna().any():
        raise ValueError(f"{path}: missing basis values")
    if (turnover < 0.0).any():
        raise ValueError(f"{path}: negative turnover")
    expected_10bps = daily - turnover * PRIMARY_COST_BPS / 10_000.0
    if "net_return" in frame.columns:
        reported = pd.Series(
            pd.to_numeric(frame["net_return"], errors="coerce").to_numpy(dtype=float),
            index=dates,
        ).sort_index()
        if reported.isna().any() or not np.allclose(
            expected_10bps, reported, atol=1e-12, rtol=0.0
        ):
            raise ValueError(f"{path}: reported 10bps net_return does not match turnover accounting")
    return daily.astype(float)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(
    *,
    summary: pd.DataFrame,
    baseline: Mapping[str, float],
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
        "LS99 integrates the LS98 BTC/ETH long-spot / short-perp research proxy into",
        "the residual gross of frozen LS57. It is not a live signal and does not prove",
        "same-venue Bitget spot execution, funding, margin or settlement.",
        "",
        f"- Sample: {start} → {end} ({rows} daily observations)",
        f"- LS57 baseline: {baseline['full_multiple']:.4f}x / Sharpe {baseline['full_sharpe']:.4f} / MDD {baseline['full_max_drawdown']:.4%}",
        f"- Combined gross cap: {GROSS_CAP:.2f}x; basis sleeve full gross: {SLEEVE_GROSS:.2f}x",
        "- Primary basis cost: 10bps per leg per side; 20bps is the stress row",
        "- Allocations are fixed at 25% / 50% / 100% of the residual-gross sleeve",
        "",
        "## Results",
        "",
        dataframe_to_markdown(summary.round(6)),
        "",
        "## Decision",
        "",
        f"**{decision}**",
        "",
        "A pass only earns same-venue spot/perp data, funding, margin and small-order",
        "execution research. It does not change `PR2026-10-D-L125-V2` or place orders.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ls57-dir", type=Path, default=DEFAULT_LS57_DIR)
    parser.add_argument("--basis-dir", type=Path, default=DEFAULT_BASIS_DIR)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    ls57_path = args.ls57_dir / "daily_returns.csv"
    ls57_gross_path = args.ls57_dir / "target_gross.csv"
    basis_path = args.basis_dir / "daily_returns.csv"
    basis_manifest_path = args.basis_dir / "manifest.json"
    if not basis_manifest_path.exists():
        raise FileNotFoundError(basis_manifest_path)

    ls57 = _load_series(ls57_path, value_column="equity")
    ls57_gross = _load_target_gross(ls57_gross_path)
    ls57 = ls57.loc[(ls57.index >= START) & (ls57.index <= END)]
    ls57_gross = ls57_gross.loc[(ls57_gross.index >= START) & (ls57_gross.index <= END)]
    expected_index = ls57.index
    if not expected_index.equals(ls57_gross.index.union(expected_index)):
        raise ValueError("LS57 returns and target gross do not share the requested calendar")
    gross = ls57_gross.reindex(expected_index).ffill().fillna(0.0)
    if not np.isfinite(gross.to_numpy()).all():
        raise ValueError("LS57 target gross could not be aligned")

    basis_gross = _load_basis_gross_returns(basis_path)
    basis_gross = basis_gross.loc[(basis_gross.index >= START) & (basis_gross.index <= END)]
    if not basis_gross.index.equals(expected_index):
        raise ValueError("basis dates do not match LS57")

    baseline = _sample_metrics(ls57)
    baseline_validation = _sample_metrics(ls57, validation=True)
    baseline_report = {
        "full_multiple": baseline["multiple"],
        "full_sharpe": baseline["sharpe"],
        "full_max_drawdown": baseline["max_drawdown"],
        "validation_multiple": baseline_validation["multiple"],
        "validation_sharpe": baseline_validation["sharpe"],
    }

    summary_rows: list[dict[str, Any]] = []
    daily_columns: dict[str, pd.Series] = {}
    for cost in BASIS_COSTS_BPS:
        for allocation in ALLOCATIONS:
            combined = combine_residual_basis(
                ls57_returns=ls57,
                ls57_gross=gross,
                basis_returns=basis_gross,
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
            residual_scaled = (
                (combined["combined_gross"] > combined["ls57_gross"] + 1e-12)
                & (combined["scale"] < allocation - 1e-12)
            )
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
                    "residual_scaled_days": int(residual_scaled.sum()),
                    "scale_change_days": int((combined["scale"].diff().abs() > 1e-12).sum()),
                    "total_scale_cost": float(combined["scale_cost"].sum()),
                }
            )

    summary = pd.DataFrame(summary_rows)
    classification = classify_integration(summary, baseline_report)
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
    pd.DataFrame(daily_columns, index=expected_index).to_csv(files["daily"], index_label="date")
    files["report"].write_text(
        _report(
            summary=summary,
            baseline=baseline_report,
            classification=classification,
            start=expected_index.min(),
            end=expected_index.max(),
            rows=len(expected_index),
        ),
        encoding="utf-8",
    )
    manifest = {
        "trial_id": TRIAL_ID,
        "classification": classification,
        "start": str(expected_index.min()),
        "end": str(expected_index.max()),
        "rows": int(len(expected_index)),
        "allocations": list(ALLOCATIONS),
        "basis_costs_bps": list(BASIS_COSTS_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "stress_cost_bps": STRESS_COST_BPS,
        "gross_cap": GROSS_CAP,
        "sleeve_gross": SLEEVE_GROSS,
        "baseline": baseline_report,
        "ls57_daily_returns": str(ls57_path),
        "ls57_target_gross": str(ls57_gross_path),
        "basis_daily_returns": str(basis_path),
        "basis_manifest": str(basis_manifest_path),
        "ls57_daily_returns_sha256": _sha256(ls57_path),
        "ls57_target_gross_sha256": _sha256(ls57_gross_path),
        "basis_daily_returns_sha256": _sha256(basis_path),
        "basis_manifest_sha256": _sha256(basis_manifest_path),
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"classification: {classification}")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
