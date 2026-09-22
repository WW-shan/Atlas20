"""Evaluate an equal-weight ensemble of the volatility-target parameter grid.

The ensemble is deliberately simple: every pre-specified rebalance-cycle and
target-volatility variant gets the same capital.  It avoids choosing the
single best full-sample parameter and is therefore a more honest baseline than
the fixed 50% or 80% target-vol variants.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.config import load_config
from atlas20.logging_utils import configure_logging, ensure_dir
from atlas20.reporting.report import dataframe_to_markdown
from atlas20.universe.builder import prepare_market_data

from scripts.run_strategy_evidence_audit import _metrics_from_returns
from scripts.run_vol_target_walk_forward import _candidate_columns


def _parse_floats(value: str) -> tuple[float, ...]:
    parsed = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 0.0 for item in parsed):
        raise ValueError("Expected a non-empty list of non-negative numbers")
    return parsed


def _period_metrics(returns: pd.Series, period: str) -> dict[str, object]:
    metrics = _metrics_from_returns(returns)
    return {
        "period": period,
        "start": returns.index.min(),
        "end": returns.index.max(),
        "days": len(returns),
        **metrics,
    }


def _summary_row(name: str, returns: pd.Series, period: str, cost_bps: float) -> dict[str, object]:
    return {
        "strategy": name,
        "cost_bps": cost_bps,
        **_period_metrics(returns, period),
    }


def _load_btc_returns(config_path: str, start_date: pd.Timestamp) -> pd.Series:
    config = load_config(config_path).model_copy(deep=True)
    panel = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "panel_daily.csv")
    metadata = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "metadata.csv").set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    return market.returns["bitcoin"].loc[start_date:].dropna()


def _write_report(output_dir: Path, summary: pd.DataFrame) -> None:
    lines = [
        "# Volatility-Target Parameter Ensemble",
        "",
        "This report averages every pre-specified parameter variant rather than",
        "selecting the best full-sample parameter. The full period starts at the",
        "beginning of the return file; the out-of-sample period starts after the",
        "initial walk-forward training window.",
        "",
        "## Summary",
        "",
        dataframe_to_markdown(summary.sort_values(["period", "cost_bps", "strategy"])),
        "",
        "## Interpretation",
        "",
        "The ensemble is a diversification device: it spreads capital across",
        "rebalance phases and target-volatility levels, reducing the dependence on",
        "one exact parameter choice. It does not remove market, factor, capacity,",
        "or data-quality risk.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--returns-file", default="reports/vol_target_cost_rolling_2022/basket_returns.csv")
    parser.add_argument("--variant-summary", default="reports/vol_target_cost_rolling_2022/variant_summary.csv")
    parser.add_argument("--cost-bps", default="2,20,100")
    parser.add_argument("--oos-start", default="2023-01-01")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/vol_target_ensemble_2022"))
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    returns = pd.read_csv(args.returns_file, parse_dates=["date"]).set_index("date").sort_index()
    variant_summary = pd.read_csv(args.variant_summary)
    costs = _parse_floats(args.cost_bps)
    oos_start = pd.Timestamp(args.oos_start).normalize()
    if oos_start not in returns.index:
        raise ValueError(f"oos-start {oos_start.date()} is not present in the return file")

    output_dir = ensure_dir(args.output_dir)
    summary_rows: list[dict[str, object]] = []
    ensemble_columns: dict[str, pd.Series] = {}
    for cost_bps in costs:
        candidates = _candidate_columns(variant_summary, returns, cost_bps)
        ensemble = returns[candidates].mean(axis=1)
        ensemble_columns[f"ensemble_{cost_bps:g}bps"] = ensemble
        full_returns = ensemble
        oos_returns = ensemble.loc[oos_start:]
        summary_rows.append(_summary_row("ensemble", full_returns, "full", cost_bps))
        summary_rows.append(_summary_row("ensemble", oos_returns, "oos_2023_plus", cost_bps))
        # Fixed 14D 50% and 80% references make the ensemble's trade-off visible.
        for target_vol in (0.5, 0.8):
            matches = [
                candidate
                for candidate in candidates
                if candidate.startswith("c14_") and f"_tv{target_vol:g}_" in candidate
            ]
            if len(matches) == 1:
                fixed = returns[matches[0]]
                summary_rows.append(
                    _summary_row(f"fixed_c14_tv{target_vol:g}", fixed, "full", cost_bps)
                )
                summary_rows.append(
                    _summary_row(f"fixed_c14_tv{target_vol:g}", fixed.loc[oos_start:], "oos_2023_plus", cost_bps)
                )

    oos_index = returns.loc[oos_start:].index
    btc = _load_btc_returns(args.config, oos_start).reindex(oos_index).fillna(0.0)
    summary_rows.append(_summary_row("BTC", btc, "oos_2023_plus", 0.0))
    btc_full = _load_btc_returns(args.config, returns.index.min()).reindex(returns.index).fillna(0.0)
    summary_rows.append(_summary_row("BTC", btc_full, "full", 0.0))

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "summary.csv", index=False)
    pd.DataFrame(ensemble_columns).to_csv(output_dir / "ensemble_returns.csv", index_label="date")
    manifest = {
        "returns_file": args.returns_file,
        "variant_summary": args.variant_summary,
        "cost_bps": list(costs),
        "oos_start": oos_start.date().isoformat(),
        "candidate_scope": "all rows in the variant summary at each cost",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_report(output_dir, summary)
    print(summary.to_string(index=False))
    print(f"Wrote parameter-ensemble report to {output_dir}")


if __name__ == "__main__":
    main()
