"""Walk-forward validation for the phase-invariant Top20 momentum family.

Candidate parameters are selected only from trailing returns and then held out
for the next test window.  This is deliberately separate from the full-sample
parameter-neighborhood report: the latter answers whether performance is a
narrow spike, while this runner answers whether a plausible parameter-selection
rule survives genuinely out of sample.
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

from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402
from scripts.run_vol_target_walk_forward import _walk_forward  # noqa: E402


def _summary_row(name: str, returns: pd.Series) -> dict[str, object]:
    metrics = _metrics_from_returns(returns)
    return {
        "strategy": name,
        "start": returns.index.min(),
        "end": returns.index.max(),
        "days": len(returns),
        **metrics,
    }


def _load_btc_returns(config_path: str, start_date: pd.Timestamp) -> pd.Series:
    from atlas20.config import load_config
    from atlas20.universe.builder import prepare_market_data

    config = load_config(config_path).model_copy(deep=True)
    processed_dir = config.resolve_path(config.paths.processed_dir)
    panel = pd.read_csv(processed_dir / "panel_daily.csv")
    metadata = pd.read_csv(processed_dir / "metadata.csv").set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    return market.returns["bitcoin"].loc[start_date:].dropna()


def _write_report(
    output_dir: Path,
    *,
    summary: pd.DataFrame,
    selections: pd.DataFrame,
    selection_metric: str,
    switch_cost_bps: float,
) -> None:
    lines = [
        "# Phase-Momentum Walk-Forward Validation",
        "",
        "## Protocol",
        "",
        f"Training window: 365 calendar days. Test window: 90 calendar days. "
        f"Selection metric: trailing {selection_metric}. Switch cost: {switch_cost_bps:g} bps "
        "charged on the first test day whenever the selected candidate changes.",
        "Candidate returns already include 20 bps total trading cost.",
        "The first test window starts after the initial 365-day training period.",
        "",
        "## Summary",
        "",
        dataframe_to_markdown(summary.sort_values(["strategy"])),
        "",
        "## Selections",
        "",
        dataframe_to_markdown(selections.head(80)),
        "",
        "## Interpretation",
        "",
        "- A dynamic selection rule is not credited with alpha merely because it",
        "  selects different parameters; it must beat the fixed primary and the",
        "  fixed equal-weight candidate ensemble out of sample.",
        "- If the dynamic rule underperforms, that is evidence against repeatedly",
        "  re-optimising the strategy and in favour of a fixed, economically",
        "  pre-specified ensemble.",
        "- Walk-forward validation does not repair data-quality, capacity, or",
        "  regime-change risk.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--candidate-returns",
        type=Path,
        default=Path("reports/phase_momentum_2022/parameter_returns.csv"),
    )
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--selection-metric", default="sharpe", choices=("sharpe", "cagr", "multiple"))
    parser.add_argument("--switch-cost-bps", default="0,40")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_walk_forward_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    returns = pd.read_csv(args.candidate_returns, parse_dates=["date"]).set_index("date").sort_index()
    candidates = [column for column in returns.columns if column != "date"]
    if not candidates:
        raise ValueError("No candidate return columns found")
    switch_costs = tuple(float(item.strip()) for item in args.switch_cost_bps.split(",") if item.strip())
    if not switch_costs or any(cost < 0.0 for cost in switch_costs):
        raise ValueError("switch-cost-bps must be a non-empty list of non-negative values")

    output_dir = ensure_dir(args.output_dir)
    summary_rows: list[dict[str, object]] = []
    return_columns: dict[str, pd.Series] = {}
    selection_frames: list[pd.DataFrame] = []
    first_test_start: pd.Timestamp | None = None

    for switch_cost in switch_costs:
        chained, selections = _walk_forward(
            returns,
            candidates,
            train_days=args.train_days,
            test_days=args.test_days,
            selection_metric=args.selection_metric,
            switch_cost_bps=switch_cost,
        )
        label = f"walk_forward_{args.selection_metric}_switch{switch_cost:g}bps"
        return_columns[label] = chained
        summary_rows.append(_summary_row(label, chained))
        selection_frames.append(selections.assign(switch_cost_bps=switch_cost))
        if first_test_start is None:
            first_test_start = pd.Timestamp(selections["test_start"].iloc[0])

    assert first_test_start is not None
    oos_index = returns.loc[first_test_start:].index
    summary_rows.append(_summary_row("fixed_primary", returns.loc[oos_index, "primary"]))
    equal_weight = returns.loc[oos_index, candidates].mean(axis=1)
    return_columns["fixed_equal_weight_candidates"] = equal_weight
    summary_rows.append(_summary_row("fixed_equal_weight_candidates", equal_weight))

    btc = _load_btc_returns(args.config, first_test_start).reindex(oos_index).fillna(0.0)
    return_columns["BTC"] = btc
    summary_rows.append(_summary_row("BTC", btc))

    summary = pd.DataFrame(summary_rows)
    selections = pd.concat(selection_frames, ignore_index=True)
    summary.to_csv(output_dir / "summary.csv", index=False)
    selections.to_csv(output_dir / "selections.csv", index=False)
    pd.DataFrame(return_columns).to_csv(output_dir / "walk_forward_returns.csv", index_label="date")
    manifest = {
        "candidate_returns": str(args.candidate_returns),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "train_days": args.train_days,
        "test_days": args.test_days,
        "selection_metric": args.selection_metric,
        "switch_cost_bps": list(switch_costs),
        "first_test_start": first_test_start.date().isoformat(),
        "cost_bps_in_candidate_returns": 20.0,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_report(
        output_dir,
        summary=summary,
        selections=selections,
        selection_metric=args.selection_metric,
        switch_cost_bps=switch_costs[-1],
    )
    print(summary.to_string(index=False))
    print(f"Wrote phase-momentum walk-forward validation to {output_dir}")


if __name__ == "__main__":
    main()
