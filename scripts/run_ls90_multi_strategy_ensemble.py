"""Equal-capital, no-rebalance ensemble of four real-engine research candidates."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

ENSEMBLE_ID = "PR2026-11-LS90-REAL-ENGINE-FUND-OF-FUNDS"
VALIDATION_START = pd.Timestamp("2024-01-01", tz="UTC")
VALIDATION_END = pd.Timestamp("2026-09-20", tz="UTC")
STRATEGY_NAMES = ("LS57", "LS82_CARRY", "LS88_LONG_CARRY", "LS89_MA21")

SOURCES: dict[float, dict[str, Path]] = {
    13.0164: {
        "LS57": Path("reports/ls92_ls57_maker13_2026/daily_base_normal_13.0164.csv"),
        "LS82_CARRY": Path("reports/ls92_ls82_maker13_2026/daily_normal_13.0164_0.25.csv"),
        "LS88_LONG_CARRY": Path("reports/ls92_ls88_maker13_2026/daily_normal_13.0164_0.10.csv"),
        "LS89_MA21": Path("reports/ls92_ls57_maker13_2026/daily_filtered_normal_13.0164.csv"),
    },
    20.0: {
        "LS57": Path("reports/ls89_asset_ma21_exit_2026/daily_base_normal_20.csv"),
        "LS82_CARRY": Path("reports/ls82_core8_carry_risk_2026/daily_normal_20_0.25.csv"),
        "LS88_LONG_CARRY": Path("reports/ls88_lowfunding_long_2026/daily_normal_20_0.10.csv"),
        "LS89_MA21": Path("reports/ls89_asset_ma21_exit_2026/daily_filtered_normal_20.csv"),
    },
    50.0: {
        "LS57": Path("reports/ls89_asset_ma21_exit_2026/daily_base_normal_50.csv"),
        "LS82_CARRY": Path("reports/ls82_core8_carry_risk_2026_cost50_100/daily_normal_50_0.25.csv"),
        "LS88_LONG_CARRY": Path("reports/ls88_lowfunding_long_2026_cost50_100/daily_normal_50_0.10.csv"),
        "LS89_MA21": Path("reports/ls89_asset_ma21_exit_2026/daily_filtered_normal_50.csv"),
    },
    100.0: {
        "LS57": Path("reports/ls89_asset_ma21_exit_2026/daily_base_normal_100.csv"),
        "LS82_CARRY": Path("reports/ls82_core8_carry_risk_2026_cost50_100/daily_normal_100_0.25.csv"),
        "LS88_LONG_CARRY": Path("reports/ls88_lowfunding_long_2026_cost50_100/daily_normal_100_0.10.csv"),
        "LS89_MA21": Path("reports/ls89_asset_ma21_exit_2026/daily_filtered_normal_100.csv"),
    },
}


def load_return_series(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    if frame.empty or "date" not in frame.columns or "daily_return" not in frame.columns:
        raise ValueError(f"invalid return series: {path}")
    index = pd.DatetimeIndex(pd.to_datetime(frame["date"], utc=True))
    values = pd.to_numeric(frame["daily_return"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index, name=path.stem)
    if series.isna().any() or not np.isfinite(series.to_numpy(dtype=float)).all():
        raise ValueError(f"return series contains missing/non-finite values: {path}")
    return series[~series.index.duplicated(keep="last")].sort_index()


def combine_no_rebalance(
    returns: pd.DataFrame,
    *,
    weights: Mapping[str, float],
) -> pd.Series:
    """Combine subaccounts using fixed initial-capital weights and no rebalancing."""
    missing = set(weights).difference(returns.columns)
    if missing:
        raise ValueError(f"weights reference missing return columns: {sorted(missing)}")
    if any(not np.isfinite(float(weight)) or float(weight) < 0.0 for weight in weights.values()):
        raise ValueError("weights must be finite and non-negative")
    total_weight = float(sum(weights.values()))
    if abs(total_weight - 1.0) > 1e-12:
        raise ValueError("weights must sum to one")
    frame = returns.loc[:, list(weights)].dropna()
    if frame.empty:
        raise ValueError("no common return observations")
    equities = (1.0 + frame).cumprod()
    total_equity = sum(
        equities.loc[:, name] * float(weight) for name, weight in weights.items()
    )
    portfolio = total_equity.pct_change().fillna(0.0)
    portfolio.name = "portfolio_return"
    return portfolio


def _sample_metrics(series: pd.Series, *, validation: bool = False) -> dict[str, float]:
    segment = series
    if validation:
        segment = series.loc[
            (series.index >= VALIDATION_START) & (series.index <= VALIDATION_END)
        ]
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def _report(
    summary: pd.DataFrame,
    subaccounts: pd.DataFrame,
    correlations: pd.DataFrame,
    *,
    trial_id: str,
) -> str:
    lines = [
        f"# {trial_id}",
        "",
        "- Equal initial capital: 25% to each real-engine subaccount",
        "- No cross-account rebalancing; each subaccount compounds independently",
        "- 20bps is primary; 50/100bps use their corresponding saved engine returns",
        "",
        "## Portfolio results",
        "",
        dataframe_to_markdown(summary.reset_index(drop=True)),
        "",
        "## Subaccounts (20bps)",
        "",
        dataframe_to_markdown(subaccounts.reset_index(drop=True)),
        "",
        "## Return correlations (20bps)",
        "",
        dataframe_to_markdown(correlations.reset_index()),
        "",
        "## Decision",
        "",
    ]
    base20 = summary.loc[(summary["portfolio"] == "LS57") & (summary["cost_bps"] == 20.0)]
    ensemble20 = summary.loc[
        (summary["portfolio"] == trial_id) & (summary["cost_bps"] == 20.0)
    ]
    if base20.empty or ensemble20.empty:
        lines.append("20bps portfolio comparison is incomplete.")
    else:
        base = base20.iloc[0]
        candidate = ensemble20.iloc[0]
        passed = (
            candidate["full_multiple"] >= base["full_multiple"]
            and candidate["full_sharpe"] > base["full_sharpe"]
            and candidate["full_max_drawdown"] >= base["full_max_drawdown"] - 0.01
            and candidate["validation_multiple"] >= base["validation_multiple"]
            and candidate["validation_sharpe"] >= base["validation_sharpe"]
        )
        lines.append(
            f"20bps LS57: {base['full_multiple']:.4f}x / {base['full_sharpe']:.4f} / "
            f"{base['full_max_drawdown']:.4%}; {trial_id}: {candidate['full_multiple']:.4f}x / "
            f"{candidate['full_sharpe']:.4f} / {candidate['full_max_drawdown']:.4%}."
        )
        lines.append("Primary ensemble gate: **PASS**." if passed else "Primary ensemble gate: **FAIL**.")
        if passed:
            lines.append("This is a portfolio candidate only; no live promotion.")
    lines.extend(["", "Research output only; no orders sent.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-id", default=ENSEMBLE_ID)
    parser.add_argument("--weights", default="0.25,0.25,0.25,0.25")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cost_bps not in SOURCES:
        raise SystemExit(f"unsupported cost: {args.cost_bps}")
    source_paths = SOURCES[args.cost_bps]
    series = {name: load_return_series(path) for name, path in source_paths.items()}
    common_index = None
    for name, values in series.items():
        common_index = values.index if common_index is None else common_index.intersection(values.index)
    if common_index is None or len(common_index) < 100:
        raise SystemExit("insufficient common observations")
    returns = pd.DataFrame({name: values.reindex(common_index) for name, values in series.items()})
    returns = returns.dropna()
    raw_weights = [float(value) for value in args.weights.split(",") if value.strip()]
    if len(raw_weights) != len(STRATEGY_NAMES):
        parser.error("weights must contain four comma-separated values")
    weights = dict(zip(STRATEGY_NAMES, raw_weights, strict=True))
    portfolio = combine_no_rebalance(returns, weights=weights)

    rows: list[dict[str, object]] = []
    for name in STRATEGY_NAMES:
        full = _sample_metrics(returns[name])
        validation = _sample_metrics(returns[name], validation=True)
        rows.append(
            {
                "portfolio": name,
                "cost_bps": args.cost_bps,
                "full_multiple": full["multiple"],
                "full_sharpe": full["sharpe"],
                "full_max_drawdown": full["max_drawdown"],
                "validation_multiple": validation["multiple"],
                "validation_sharpe": validation["sharpe"],
            }
        )
    full = _sample_metrics(portfolio)
    validation = _sample_metrics(portfolio, validation=True)
    rows.append(
        {
            "portfolio": args.trial_id,
            "cost_bps": args.cost_bps,
            "full_multiple": full["multiple"],
            "full_sharpe": full["sharpe"],
            "full_max_drawdown": full["max_drawdown"],
            "validation_multiple": validation["multiple"],
            "validation_sharpe": validation["sharpe"],
        }
    )
    summary = pd.DataFrame(rows)
    subaccounts = summary.loc[summary["portfolio"].isin(STRATEGY_NAMES)].reset_index(drop=True)
    correlations = returns.corr()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "run_summary.csv", index=False)
    subaccounts.to_csv(output_dir / "subaccount_summary.csv", index=False)
    correlations.to_csv(output_dir / "correlations.csv", index_label="strategy")
    portfolio.to_csv(output_dir / "portfolio_daily_returns.csv", header=True)
    manifest = {
        "ensemble_id": args.trial_id,
        "cost_bps": args.cost_bps,
        "weights": weights,
        "rebalance": "none",
        "common_start": str(returns.index.min()),
        "common_end": str(returns.index.max()),
        "sources": {name: str(path) for name, path in source_paths.items()},
        "orders_sent": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        _report(summary, subaccounts, correlations, trial_id=args.trial_id),
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
