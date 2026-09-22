"""Walk-forward validation for the volatility-target candidate family.

The candidate parameters (rebalance cycle and target volatility) are selected
only from trailing returns and then held out of sample for the next test
window.  This avoids the common mistake of choosing the best full-sample
variant and calling its in-sample multiple a live expectation.
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


def _parse_ints(value: str) -> tuple[int, ...]:
    parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 1 for item in parsed):
        raise ValueError("Expected a non-empty list of positive integers")
    return parsed


def _parse_floats(value: str) -> tuple[float, ...]:
    parsed = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 0.0 for item in parsed):
        raise ValueError("Expected a non-empty list of non-negative numbers")
    return parsed


def _candidate_columns(summary: pd.DataFrame, returns: pd.DataFrame, cost_bps: float) -> list[str]:
    """Map summary rows to the matching return columns."""
    cost_matches = summary[summary["cost_bps"].astype(float).round(6) == round(cost_bps, 6)]
    columns: list[str] = []
    for _, row in cost_matches.iterrows():
        column = (
            f"c{int(row['cycle_days'])}_tv{float(row['target_volatility']):g}_"
            f"vw{int(row['vol_window'])}_{row['stop_mode']}_{row['gate_mode']}_"
            f"{int(round(float(row['cost_bps'])))}bps"
        )
        if column in returns.columns:
            columns.append(column)
    if not columns:
        raise ValueError(f"No candidate return columns found for cost_bps={cost_bps}")
    return list(dict.fromkeys(columns))


def _metric_value(returns: pd.Series, metric: str) -> float:
    metrics = _metrics_from_returns(returns)
    if metric == "sharpe":
        return metrics["sharpe"]
    if metric == "cagr":
        return metrics["cagr"]
    if metric == "multiple":
        return metrics["multiple"]
    raise ValueError(f"Unsupported selection metric: {metric}")


def _select_candidate(
    train_returns: pd.DataFrame,
    candidates: list[str],
    metric: str,
) -> tuple[str, dict[str, float]]:
    """Select the best candidate using trailing data only."""
    scores = {candidate: _metric_value(train_returns[candidate], metric) for candidate in candidates}
    # ``max`` preserves the first candidate on ties, which keeps selection
    # deterministic across runs.
    selected = max(candidates, key=lambda candidate: scores[candidate])
    return selected, scores


def _apply_switch_cost(returns: pd.Series, switch_cost_bps: float) -> pd.Series:
    """Charge a conservative full-switch cost on the first test day."""
    if switch_cost_bps <= 0.0 or returns.empty:
        return returns
    adjusted = returns.copy()
    adjusted.iloc[0] = (1.0 - switch_cost_bps / 10_000.0) * (1.0 + float(adjusted.iloc[0])) - 1.0
    return adjusted


def _walk_forward(
    returns: pd.DataFrame,
    candidates: list[str],
    *,
    train_days: int,
    test_days: int,
    selection_metric: str,
    switch_cost_bps: float,
) -> tuple[pd.Series, pd.DataFrame]:
    """Run rolling train/test selection and return chained OOS returns."""
    if train_days < 1 or test_days < 1:
        raise ValueError("train_days and test_days must be positive")
    if len(returns) <= train_days:
        raise ValueError("Not enough return history for the requested training window")

    chained: list[pd.Series] = []
    selection_rows: list[dict[str, object]] = []
    previous_candidate: str | None = None
    train_start = 0
    while train_start + train_days < len(returns):
        train_end = train_start + train_days
        test_start = train_end
        test_end = min(test_start + test_days, len(returns))
        train_slice = returns.iloc[train_start:train_end]
        selected, scores = _select_candidate(train_slice, candidates, selection_metric)
        test_slice = returns[selected].iloc[test_start:test_end].copy()
        switched = previous_candidate is not None and selected != previous_candidate
        if switched:
            test_slice = _apply_switch_cost(test_slice, switch_cost_bps)
        chained.append(test_slice)
        selection_rows.append(
            {
                "train_start": returns.index[train_start],
                "train_end": returns.index[train_end - 1],
                "test_start": returns.index[test_start],
                "test_end": returns.index[test_end - 1],
                "selected_candidate": selected,
                "previous_candidate": previous_candidate,
                "switched": switched,
                "train_metric": scores[selected],
                **{f"train_{candidate}": value for candidate, value in scores.items()},
            }
        )
        previous_candidate = selected
        train_start += test_days
    return pd.concat(chained).sort_index(), pd.DataFrame(selection_rows)


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
    config = load_config(config_path).model_copy(deep=True)
    panel = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "panel_daily.csv")
    metadata = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "metadata.csv").set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    return market.returns["bitcoin"].loc[start_date:].dropna()


def _write_report(
    output_dir: Path,
    summary: pd.DataFrame,
    selections: pd.DataFrame,
    *,
    selection_metric: str,
    switch_cost_bps: float,
) -> None:
    lines = [
        "# Volatility-Target Walk-Forward Validation",
        "",
        f"Parameter selection uses trailing returns only; selection metric: `{selection_metric}`.",
        f"Each strategy switch is charged `{switch_cost_bps:g}` bps on the first test day.",
        "",
        "## Out-of-sample summary",
        "",
        dataframe_to_markdown(summary.sort_values("multiple", ascending=False)),
        "",
        "## Selection history",
        "",
        dataframe_to_markdown(selections),
        "",
        "## Guardrail",
        "",
        "This is a meta-selection test over already constructed return paths. It does",
        "not validate the underlying CTREND factor, point-in-time data quality, or",
        "capacity; those require separate audits.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--returns-file", default="reports/vol_target_cost_rolling_2022/basket_returns.csv")
    parser.add_argument("--variant-summary", default="reports/vol_target_cost_rolling_2022/variant_summary.csv")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--train-days", default="365")
    parser.add_argument("--test-days", default="90")
    parser.add_argument("--selection-metric", default="sharpe", choices=("sharpe", "cagr", "multiple"))
    parser.add_argument("--switch-cost-bps", default="0,40")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/vol_target_walk_forward_2022"))
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    returns_path = Path(args.returns_file)
    summary_path = Path(args.variant_summary)
    returns = pd.read_csv(returns_path, parse_dates=["date"]).set_index("date").sort_index()
    variant_summary = pd.read_csv(summary_path)
    candidates = _candidate_columns(variant_summary, returns, args.cost_bps)

    train_days = _parse_ints(args.train_days)
    test_days = _parse_ints(args.test_days)
    switch_costs = _parse_floats(args.switch_cost_bps)
    if len(train_days) != 1 or len(test_days) != 1:
        raise ValueError("This runner currently expects one train_days and one test_days value")

    output_dir = ensure_dir(args.output_dir)
    summary_rows: list[dict[str, object]] = []
    selection_frames: list[pd.DataFrame] = []
    return_columns: dict[str, pd.Series] = {}
    first_test_start: pd.Timestamp | None = None
    for switch_cost_bps in switch_costs:
        chained, selections = _walk_forward(
            returns,
            candidates,
            train_days=train_days[0],
            test_days=test_days[0],
            selection_metric=args.selection_metric,
            switch_cost_bps=switch_cost_bps,
        )
        label = f"walk_forward_switch{switch_cost_bps:g}bps"
        return_columns[label] = chained
        summary_rows.append(_summary_row(label, chained))
        selection_frames.append(selections.assign(switch_cost_bps=switch_cost_bps))
        if first_test_start is None:
            first_test_start = pd.Timestamp(selections["test_start"].iloc[0])

    assert first_test_start is not None
    oos_index = returns.loc[first_test_start:].index
    for candidate in candidates:
        summary_rows.append(_summary_row(candidate, returns.loc[oos_index, candidate]))
    equal_weight = returns.loc[oos_index, candidates].mean(axis=1)
    return_columns["equal_weight_candidates"] = equal_weight
    summary_rows.append(_summary_row("equal_weight_candidates", equal_weight))

    btc = _load_btc_returns(args.config, first_test_start)
    btc = btc.reindex(oos_index).fillna(0.0)
    return_columns["BTC"] = btc
    summary_rows.append(_summary_row("BTC", btc))

    summary = pd.DataFrame(summary_rows)
    selections = pd.concat(selection_frames, ignore_index=True)
    summary.to_csv(output_dir / "summary.csv", index=False)
    selections.to_csv(output_dir / "selections.csv", index=False)
    pd.DataFrame(return_columns).to_csv(output_dir / "walk_forward_returns.csv", index_label="date")
    manifest = {
        "returns_file": str(returns_path),
        "variant_summary": str(summary_path),
        "cost_bps": args.cost_bps,
        "train_days": train_days[0],
        "test_days": test_days[0],
        "selection_metric": args.selection_metric,
        "switch_cost_bps": list(switch_costs),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "first_test_start": first_test_start.date().isoformat(),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_report(
        output_dir,
        summary,
        selections,
        selection_metric=args.selection_metric,
        switch_cost_bps=switch_costs[0],
    )
    print(summary.to_string(index=False))
    print(f"Wrote walk-forward validation to {output_dir}")


if __name__ == "__main__":
    main()
