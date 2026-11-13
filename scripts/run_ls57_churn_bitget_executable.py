"""Audit whether the LS79 churn ensemble is executable on Bitget."""

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

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.diagnose_top20_membership_events import membership_matrix  # noqa: E402
from scripts.run_daily_btc_shock_continuation import backtest_continuation  # noqa: E402
from scripts.run_ls57_churn_multiphase_ensemble import (  # noqa: E402
    COSTS_BPS,
    FUNDING_MULTIPLIERS,
    VARIANTS,
    average_active_variant_weights,
    backtest_ensemble_weights,
)
from scripts.run_ls57_churn_overlay import (  # noqa: E402
    ALLOCATIONS,
    GROSS_CAP,
    LS57_DIR,
    _sample_metrics,
    load_return_series,
    load_target_gross,
    scale_sleeve_to_residual_gross,
)
from scripts.run_ls57_churn_spot_btc_short_alt import (  # noqa: E402
    MIN_FUNDING_COVERAGE,
    _short_funding_return,
    build_cross_venue_funding_panels,
    restrict_targets_to_executable_shorts,
    short_funding_coverage,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_top20_churn_gated import build_gate_series  # noqa: E402
from scripts.run_top20_churn_short import build_churn_targets  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-09-20"
BITGET_RAW_DIR = Path("data/raw/bitget_derivatives/merged_market_20261009")
MARK_LOOKBACK_DAYS = 3
FUNDING_LOOKBACK_DAYS = 7


def bitget_mark_availability(
    marks: dict[str, pd.DataFrame],
    *,
    index: pd.DatetimeIndex,
    assets: list[str],
    lookback_days: int = MARK_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Mark an asset available when Bitget had a market mark in the recent past."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    trading_days = pd.DatetimeIndex(index.normalize().unique()).sort_values()
    available = pd.DataFrame(False, index=index, columns=assets, dtype=bool)
    for asset in assets:
        frame = marks.get(asset)
        if frame is None or frame.empty:
            continue
        daily = frame["close"].groupby(frame.index.normalize()).last()
        observed = pd.Series(1.0, index=daily.index).reindex(trading_days).fillna(0.0)
        observed = observed.rolling(lookback_days, min_periods=1).max().fillna(0.0) > 0.0
        available[asset] = observed.reindex(index.normalize()).to_numpy(dtype=bool)
    return available


def funding_availability(
    funding_rates: pd.DataFrame,
    *,
    lookback_days: int = FUNDING_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Mark an asset available when a settlement was observed recently."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    return (
        funding_rates.notna()
        .astype(float)
        .rolling(lookback_days, min_periods=1)
        .max()
        .fillna(0.0)
        .astype(bool)
    )


def weighted_mask_coverage(weights: pd.DataFrame, mask: pd.DataFrame) -> float:
    """Coverage of the absolute short weights by a boolean availability mask."""
    shorts = weights.clip(upper=0.0).abs()
    aligned = mask.reindex(index=weights.index, columns=weights.columns).fillna(False).astype(bool)
    denominator = float(shorts.to_numpy().sum())
    if denominator <= 0.0:
        return 1.0
    return float(shorts.where(aligned, 0.0).to_numpy().sum()) / denominator


def coverage_breakdown(
    *,
    original_weights: pd.DataFrame,
    rebuilt_weights: pd.DataFrame,
    marks: pd.DataFrame,
    funding: pd.DataFrame,
) -> dict[str, float]:
    """Separate original strict coverage from rebuilt funding coverage."""
    strict = marks & funding
    return {
        "original_mark_weighted_coverage": weighted_mask_coverage(original_weights, marks),
        "original_funding_weighted_coverage": weighted_mask_coverage(original_weights, funding),
        "original_strict_weighted_coverage": weighted_mask_coverage(original_weights, strict),
        "rebuilt_strict_weighted_coverage": weighted_mask_coverage(rebuilt_weights, strict),
        "rebuilt_funding_coverage": weighted_mask_coverage(rebuilt_weights, funding),
    }


def eligibility_audit(
    original_weights: pd.DataFrame,
    marks: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Per-asset coverage for the short legs in the original LS79 ensemble."""
    original_weights = original_weights.reindex(index).fillna(0.0)
    marks = marks.reindex(index=index, columns=original_weights.columns).fillna(False)
    funding = funding.reindex(index=index, columns=original_weights.columns).fillna(False)
    short = original_weights.clip(upper=0.0).abs()
    total = short.sum(axis=0)
    rows: list[dict[str, Any]] = []
    for asset in short.columns:
        weight = float(total.get(asset, 0.0))
        if weight <= 0.0:
            continue
        rows.append(
            {
                "asset": asset,
                "short_weight": weight,
                "mark_coverage": float(short[asset].where(marks[asset], 0.0).sum() / weight),
                "funding_coverage": float(short[asset].where(funding[asset], 0.0).sum() / weight),
                "strict_coverage": float(
                    short[asset].where(marks[asset] & funding[asset], 0.0).sum() / weight
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("short_weight", ascending=False, kind="stable").reset_index(drop=True)


def build_ensemble(
    *,
    index: pd.DatetimeIndex,
    returns: pd.DataFrame,
    assets: list[str],
    present: pd.DataFrame,
    gate: pd.Series,
    available: pd.DataFrame,
) -> tuple[dict[float, Any], pd.DataFrame, pd.DataFrame]:
    variant_weights: dict[tuple[int, int], pd.DataFrame] = {}
    active_counts: dict[tuple[int, int], pd.Series] = {}
    rows: list[dict[str, Any]] = []
    for confirmation_days in sorted({label[0] for label in VARIANTS}):
        targets = build_churn_targets(
            present=present,
            confirmation_days=confirmation_days,
            assets=assets,
        )
        targets.loc[~gate.reindex(targets.index, fill_value=False).astype(bool), :] = 0.0
        targets = restrict_targets_to_executable_shorts(targets, available)
        for hold_days in sorted({label[1] for label in VARIANTS if label[0] == confirmation_days}):
            label = (confirmation_days, hold_days)
            result = backtest_continuation(
                index=index,
                returns=returns[["bitcoin", *assets]],
                targets=targets,
                horizon=hold_days,
                cost_bps=20.0,
                normalize_gross=True,
            )
            variant_weights[label] = result.weights
            active_counts[label] = (result.weights.abs().sum(axis=1) > 0.0).astype(int)
            full = _sample_metrics(result.daily_returns, "full")
            validation = _sample_metrics(result.daily_returns, "validation")
            rows.append(
                {
                    "variant_id": f"m{confirmation_days}_h{hold_days}",
                    "full_multiple_20bps": full["multiple"],
                    "full_sharpe_20bps": full["sharpe"],
                    "full_max_drawdown_20bps": full["max_drawdown"],
                    "validation_multiple_20bps": validation["multiple"],
                    "validation_sharpe_20bps": validation["sharpe"],
                    "active_days": int((result.gross_exposure > 0.0).sum()),
                }
            )
    ensemble_weights, ensemble_active = average_active_variant_weights(variant_weights)
    standalone = {
        cost: backtest_ensemble_weights(
            index=index,
            returns=returns[["bitcoin", *assets]],
            weights=ensemble_weights,
            active_variant_count=ensemble_active,
            cost_bps=cost,
        )
        for cost in COSTS_BPS
    }
    return standalone, ensemble_weights, pd.DataFrame(rows)


def _report(
    summary: pd.DataFrame,
    standalone: dict[float, Any],
    coverage: dict[str, float],
    audit: pd.DataFrame,
    baseline: dict[str, float],
    baseline_validation: dict[str, float],
) -> str:
    strict_missing = audit.loc[audit["strict_coverage"] < 1.0, "asset"].tolist()
    lines = [
        "# LS79 churn ensemble: Bitget executable audit",
        "",
        f"- LS57 baseline: {baseline['multiple']:.4f}x / Sharpe {baseline['sharpe']:.4f} / MDD {baseline['max_drawdown']:.4%}",
        f"- LS57 validation: {baseline_validation['multiple']:.4f}x / Sharpe {baseline_validation['sharpe']:.4f}",
        "- original LS79 strict Bitget mark+funding weighted short coverage: "
        f"{coverage['original_strict_weighted_coverage']:.4%}",
        "- rebuilt strict ensemble mark+funding weighted short coverage: "
        f"{coverage['rebuilt_strict_weighted_coverage']:.4%}",
        "- rebuilt strict ensemble funding weighted short coverage: "
        f"{coverage['rebuilt_funding_coverage']:.4%}",
        f"- names with incomplete strict coverage: {', '.join(strict_missing) if strict_missing else 'none'}",
        "- mark availability: Bitget market mark observed within the prior 3 calendar days",
        "- funding availability: Binance/Bybit/Bitget settlement observed within the prior 7 days",
        "- a non-available alt short is removed and the remaining event legs are reweighted",
        "",
        "## Standalone ensemble",
        "",
        dataframe_to_markdown(
            pd.DataFrame(
                [
                    {
                        "cost_bps": cost,
                        **_sample_metrics(result.daily_returns, "full"),
                        "validation_multiple": _sample_metrics(result.daily_returns, "validation")["multiple"],
                        "validation_sharpe": _sample_metrics(result.daily_returns, "validation")["sharpe"],
                        "mean_gross": float(result.gross_exposure.mean()),
                        "turnover": float(result.turnover.sum()),
                    }
                    for cost, result in standalone.items()
                ]
            )
        ),
        "",
        "## LS57 overlay",
        "",
        dataframe_to_markdown(
            summary[
                [
                    "allocation",
                    "sleeve_cost_bps",
                    "funding_scenario",
                    "full_multiple",
                    "full_sharpe",
                    "full_max_drawdown",
                    "validation_multiple",
                    "validation_sharpe",
                    "max_combined_gross",
                    "passes",
                ]
            ].reset_index(drop=True)
        ),
        "",
        "## Per-asset coverage",
        "",
        dataframe_to_markdown(audit.head(40).reset_index(drop=True)),
        "",
        "## Decision",
        "",
    ]
    passed = summary.loc[
        (summary["sleeve_cost_bps"] == 20.0)
        & summary["funding_scenario"].isin(["normal", "adverse_1x"])
        & summary["passes"]
    ]
    if passed.empty:
        lines.append(
            "No allocation passed the strict Bitget mark+funding + 1x-adverse gate. "
            "LS79 is not Bitget-executable and its conditional promotion is withdrawn."
        )
    else:
        counts = passed.groupby("allocation")["funding_scenario"].nunique()
        allocations = counts.loc[counts == 2]
        if allocations.empty:
            lines.append(
                "No allocation passed both the normal and 1x-adverse strict Bitget gates. "
                "LS79 is not Bitget-executable and its conditional promotion is withdrawn."
            )
        else:
            lines.append(
                f"Largest allocation passing strict Bitget normal + 1x adverse: {float(allocations.index.max()):.0%} NAV. "
                "Still research-only; mark/fill/margin engine verification is required."
            )
    lines.extend(
        [
            "",
            "The audit deliberately does not add a coin whitelist or change allocation after seeing the result.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date != DEFAULT_START or args.end_date != DEFAULT_END:
        parser.error("LS80 is frozen to 2022-01-01 -> 2026-09-20")

    lower = pd.Timestamp(args.start_date, tz="UTC")
    upper = pd.Timestamp(args.end_date, tz="UTC")
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
    gate = build_gate_series(price=price, returns=returns, present=present, assets=assets)["alt_rel_60"]

    symbol_map = pd.read_csv(BITGET_RAW_DIR / "symbol_map.csv")
    marks = load_mark_candles(BITGET_RAW_DIR, symbol_map, candle_type="market")
    mark_available = bitget_mark_availability(marks, index=index, assets=assets)
    normal_rates, adverse_rates = build_cross_venue_funding_panels(coins=assets, index=index)
    funding_available = funding_availability(normal_rates)
    available = mark_available & funding_available

    original = pd.read_csv(
        "reports/ls57_churn_multiphase_ensemble_2026/ensemble_weights.csv",
        index_col=0,
    )
    original.index = pd.DatetimeIndex(pd.to_datetime(original.index, utc=True)).sort_values()
    original = original.reindex(index=index).fillna(0.0)
    audit = eligibility_audit(
        original,
        mark_available,
        funding_available,
        index=index,
    )

    standalone, ensemble_weights, variant_table = build_ensemble(
        index=index,
        returns=returns,
        assets=assets,
        present=present,
        gate=gate,
        available=available,
    )
    ensemble_20 = standalone[20.0]
    coverage = coverage_breakdown(
        original_weights=original,
        rebuilt_weights=ensemble_weights,
        marks=mark_available,
        funding=funding_available,
    )
    rebuilt_funding_coverage = short_funding_coverage(ensemble_weights, normal_rates)
    if abs(coverage["rebuilt_funding_coverage"] - rebuilt_funding_coverage) > 1e-12:
        raise ValueError("rebuilt funding coverage disagrees with short_funding_coverage")
    funding_by_scenario = {
        scenario: _short_funding_return(
            ensemble_weights,
            normal_rates,
            adverse_rates,
            multiplier=multiplier,
        )
        for scenario, multiplier in FUNDING_MULTIPLIERS.items()
    }

    ls57_returns = load_return_series(LS57_DIR / "daily_returns.csv")
    ls57_returns = ls57_returns.loc[(ls57_returns.index >= lower) & (ls57_returns.index <= upper)]
    ls57_gross = load_target_gross(LS57_DIR / "target_gross.csv")
    ls57_gross = ls57_gross.loc[(ls57_gross.index >= lower) & (ls57_gross.index <= upper)]
    base_gross = ls57_gross.reindex(ls57_returns.index).ffill().fillna(0.0)
    baseline = _sample_metrics(ls57_returns, "full")
    baseline_validation = _sample_metrics(ls57_returns, "validation")

    rows: list[dict[str, Any]] = []
    for allocation in ALLOCATIONS:
        scale_frame = scale_sleeve_to_residual_gross(
            ls57_gross=base_gross,
            sleeve_gross=ensemble_20.gross_exposure,
            allocation=allocation,
        ).reindex(ls57_returns.index)
        scale_delta = scale_frame["sleeve_scale"].diff().abs().fillna(
            scale_frame["sleeve_scale"].abs()
        )
        for cost, result in standalone.items():
            scale_cost = (
                scale_delta
                * result.gross_exposure.reindex(ls57_returns.index).shift(1).fillna(
                    result.gross_exposure.reindex(ls57_returns.index)
                )
                * float(cost)
                / 10_000.0
            )
            for scenario, funding in funding_by_scenario.items():
                funding_aligned = funding.reindex(ls57_returns.index).fillna(0.0)
                combined = (
                    ls57_returns
                    + scale_frame["sleeve_scale"]
                    * (result.daily_returns.reindex(ls57_returns.index).fillna(0.0) + funding_aligned)
                    - scale_cost
                )
                full = _sample_metrics(combined, "full")
                validation = _sample_metrics(combined, "validation")
                passes = (
                    full["multiple"] > baseline["multiple"]
                    and full["sharpe"] > baseline["sharpe"]
                    and full["max_drawdown"] >= baseline["max_drawdown"] - 0.01
                    and validation["multiple"] > baseline_validation["multiple"]
                    and validation["sharpe"] > baseline_validation["sharpe"]
                    and float(scale_frame["combined_gross"].max()) <= GROSS_CAP + 1e-10
                    and coverage["rebuilt_funding_coverage"] >= MIN_FUNDING_COVERAGE
                )
                rows.append(
                    {
                        "allocation": allocation,
                        "sleeve_cost_bps": cost,
                        "funding_scenario": scenario,
                        "full_multiple": full["multiple"],
                        "full_sharpe": full["sharpe"],
                        "full_max_drawdown": full["max_drawdown"],
                        "validation_multiple": validation["multiple"],
                        "validation_sharpe": validation["sharpe"],
                        "max_combined_gross": float(scale_frame["combined_gross"].max()),
                        "funding_sum": float((scale_frame["sleeve_scale"] * funding_aligned).sum()),
                        "passes": bool(passes),
                    }
                )
    summary = pd.DataFrame(rows)
    primary = summary.loc[
        (summary["sleeve_cost_bps"] == 20.0)
        & summary["funding_scenario"].isin(["normal", "adverse_1x"])
        & summary["passes"]
    ]
    selected_allocation = None
    if not primary.empty:
        counts = primary.groupby("allocation")["funding_scenario"].nunique()
        allocations = counts.loc[counts == 2]
        if not allocations.empty:
            selected_allocation = float(allocations.index.max())

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "overlay_summary.csv",
        "variants": output_dir / "variant_metrics.csv",
        "audit": output_dir / "eligibility_audit.csv",
        "weights": output_dir / "strict_ensemble_weights.csv",
        "funding": output_dir / "sleeve_funding.csv",
        "daily_20": output_dir / "strict_daily_20bps.csv",
        "daily_50": output_dir / "strict_daily_50bps.csv",
        "daily_100": output_dir / "strict_daily_100bps.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    variant_table.to_csv(files["variants"], index=False)
    audit.to_csv(files["audit"], index=False)
    ensemble_weights.to_csv(files["weights"])
    pd.DataFrame(funding_by_scenario).to_csv(files["funding"])
    standalone[20.0].daily_returns.to_csv(files["daily_20"])
    standalone[50.0].daily_returns.to_csv(files["daily_50"])
    standalone[100.0].daily_returns.to_csv(files["daily_100"])
    files["report"].write_text(
        _report(summary, standalone, coverage, audit, baseline, baseline_validation),
        encoding="utf-8",
    )
    manifest = {
        "audit_id": "PR2026-11-LS80-BITGET-EXECUTABLE-CHURN-ENSEMBLE",
        "audited_candidate": "PR2026-11-LS79-LS57-CHURN-MULTIPHASE-ENSEMBLE",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "mark_lookback_days": MARK_LOOKBACK_DAYS,
        "funding_lookback_days": FUNDING_LOOKBACK_DAYS,
        "coverage": coverage,
        "allocations": list(ALLOCATIONS),
        "costs_bps": list(COSTS_BPS),
        "funding_scenarios": list(FUNDING_MULTIPLIERS),
        "strict_incomplete_assets": audit.loc[audit["strict_coverage"] < 1.0, "asset"].tolist(),
        "selected_allocation": selected_allocation,
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {output_dir}; original_strict={coverage['original_strict_weighted_coverage']:.4f}; "
        f"rebuilt_funding={coverage['rebuilt_funding_coverage']:.4f}"
    )


if __name__ == "__main__":
    main()
