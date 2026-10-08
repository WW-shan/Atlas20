"""Compare the champion against the pre-registered variants at the live fill.

The frozen champion (BTC MA100 gate), H2 (gate-window ensemble), H3 (Top20
breadth co-gate) and H3's pre-declared neighbourhood (thresholds 0.45/0.55) were
all registered and run under the 2026-10 protocol. This tool puts them side by
side on the same harness - every cost, every fill timing, both missing-candle
policies - so the choice between them is made on one table instead of on
different reports.

It runs no new hypothesis: the specs are exactly the registered ones, the
windows and costs are the protocol's, and the Deflated Sharpe uses the
project's real trial count. Nothing is selected here.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.backtest.intraday import (  # noqa: E402
    MISSING_FILL_POLICIES,
    load_hourly_bars,
    observed_fill_mask,
    pre_fill_returns,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_execution_lag import _observed_weight_share  # noqa: E402
from scripts.run_phase_momentum_hypotheses import (  # noqa: E402
    COSTS,
    MAIN_WINDOW,
    build_trial,
    run_metrics,
    trial_by_id,
)
from scripts.run_phase_momentum_multiple_testing import (  # noqa: E402
    _deflated_sharpe,
    _expected_max_sharpe,
)

# The registered specs under comparison, and the one a decision would replace.
DEFAULT_TRIALS = (
    "PR2026-10-B",
    "PR2026-10-H2",
    "PR2026-10-H3",
    "PR2026-10-H3-T45",
    "PR2026-10-H3-T55",
)
FILL_HOURS = (1, 3)
DECISION_COST = 20.0


def _fill_specs(hourly: dict[str, pd.DataFrame], daily: pd.DataFrame, closes: pd.DataFrame) -> dict[str, object]:
    """Every fill the protocol evaluates: close, +1h, +3h (both policies), +1 day."""
    specs: dict[str, object] = {"close": (0, None)}
    for hours in FILL_HOURS:
        for policy in MISSING_FILL_POLICIES:
            specs[f"h{hours}_{policy}"] = (
                0,
                pre_fill_returns(
                    daily, hourly, fill_hours=hours, missing_fill=policy, reference_close=closes
                ),
            )
    specs["lag1"] = (1, None)
    return specs


def _trial_dsr(returns: pd.Series, scope: dict[str, object]) -> dict[str, float]:
    expected = _expected_max_sharpe(
        int(scope["n_trials"]), float(scope["sharpe_std_per_period"])
    )
    return _deflated_sharpe(returns, expected_max_sharpe=expected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--hourly-dir", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--trial-ids", default=",".join(DEFAULT_TRIALS))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_candidate_eval"))
    parser.add_argument(
        "--inventory-summary",
        type=Path,
        default=Path("reports/research_trial_inventory/summary.json"),
    )
    args = parser.parse_args()

    trial_ids = tuple(part.strip() for part in args.trial_ids.split(",") if part.strip())
    scope = json.loads(args.inventory_summary.read_text(encoding="utf-8"))["top20_2022_trials"]

    configure_logging("ERROR")
    config, market, universe, index = _load_market(
        args.config, start_date=MAIN_WINDOW[0], end_date=MAIN_WINDOW[1]
    )
    daily = market.returns.loc[index]
    closes = market.raw_price.reindex(index=index, columns=daily.columns)
    hourly = load_hourly_bars(args.hourly_dir)
    observed = observed_fill_mask(daily, hourly, fill_hours=3, reference_close=closes)
    fills = _fill_specs(hourly, daily, closes)

    rows: list[dict[str, object]] = []
    for trial_id in trial_ids:
        built = build_trial(trial_by_id(trial_id), market, universe, index)
        for fill, (lag, pre_fill) in fills.items():
            for cost in COSTS:
                result = _production_result(
                    config,
                    market,
                    built,
                    index,
                    cost_bps=cost,
                    execution_lag_days=lag,
                    pre_fill=pre_fill,
                )
                returns = result.daily_returns
                rows.append(
                    {
                        "trial_id": trial_id,
                        "fill": fill,
                        "cost_bps": float(cost),
                        **run_metrics(returns, result),
                        "observed_weight_share": _observed_weight_share(result, observed)
                        if fill.startswith("h")
                        else 1.0,
                    }
                )
        print(f"ran {trial_id}", flush=True)

    frame = pd.DataFrame(rows)
    output_dir = ensure_dir(args.output_dir)
    frame.to_csv(output_dir / "candidate_metrics.csv", index=False)

    # The decision table: the live fill at the primary cost, both +3h policies
    # collapsed to the worse one per trial, and the +1h alternative.
    decision_rows: list[dict[str, object]] = []
    for trial_id in trial_ids:
        subset = frame[frame["trial_id"] == trial_id]
        for hours in FILL_HOURS:
            policies = subset[
                (subset["fill"].str.startswith(f"h{hours}_"))
                & (subset["cost_bps"] == DECISION_COST)
            ]
            worst = policies.sort_values("multiple").iloc[0]
            decision_rows.append(
                {
                    "trial_id": trial_id,
                    "fill_hours": hours,
                    "worse_policy": worst["fill"],
                    "multiple": worst["multiple"],
                    "sharpe": worst["sharpe"],
                    "max_drawdown": worst["max_drawdown"],
                    "rolling_1y_worst": worst["rolling_1y_worst_multiple"],
                    "best_year_removed": worst["best_year_removed_multiple"],
                    "turnover_annual": worst["turnover_annual"],
                    "avg_gross_exposure": worst["avg_gross_exposure"],
                    "observed_weight_share": worst["observed_weight_share"],
                }
            )
    decision = pd.DataFrame(decision_rows)
    decision.to_csv(output_dir / "decision_table.csv", index=False)

    # Deflated Sharpe at 20 bps, per fill timing, on the worse missing-candle
    # policy - the champion and the variants judged on the same return series.
    dsr_rows: list[dict[str, object]] = []
    for trial_id in trial_ids:
        built = build_trial(trial_by_id(trial_id), market, universe, index)
        series: dict[str, pd.Series] = {
            "close": _production_result(
                config, market, built, index, cost_bps=DECISION_COST
            ).daily_returns
        }
        for hours in FILL_HOURS:
            for policy in MISSING_FILL_POLICIES:
                series[f"h{hours}_{policy}"] = _production_result(
                    config,
                    market,
                    built,
                    index,
                    cost_bps=DECISION_COST,
                    pre_fill=pre_fill_returns(
                        daily,
                        hourly,
                        fill_hours=hours,
                        missing_fill=policy,
                        reference_close=closes,
                    ),
                ).daily_returns
        for hours in FILL_HOURS:
            candidates = {key: value for key, value in series.items() if key.startswith(f"h{hours}_")}
            worst_policy = min(
                candidates, key=lambda key: float((1.0 + candidates[key].fillna(0.0)).prod())
            )
            for label, returns in (("close", series["close"]), (worst_policy, candidates[worst_policy])):
                stats = _trial_dsr(returns, scope)
                dsr_rows.append(
                    {
                        "trial_id": trial_id,
                        "fill": label,
                        "fill_hours": 0 if label == "close" else hours,
                        "deflated_sharpe_probability": stats["deflated_sharpe_probability"],
                        "observed_sharpe": stats["observed_sharpe"],
                        "expected_max_sharpe": stats["expected_max_sharpe"],
                        "n_trials": int(scope["n_trials"]),
                    }
                )
    dsr = pd.DataFrame(dsr_rows)
    dsr.to_csv(output_dir / "deflated_sharpe.csv", index=False)

    report = "\n".join(
        [
            "# Phase-momentum candidates: one evaluation table",
            "",
            f"Window `{MAIN_WINDOW[0]}` .. `{MAIN_WINDOW[1]}`, strict point-in-time Top20, "
            "long-only spot, gross exposure <= 1. All specs are the registered ones; "
            "this tool selects nothing and registers no new trial.",
            "",
            "## Decision table (20 bps, worse missing-candle policy per fill)",
            "",
            dataframe_to_markdown(decision),
            "",
            "## Deflated Sharpe (20 bps, worse missing-candle policy per timing)",
            "",
            dataframe_to_markdown(dsr),
            "",
            "## Full metrics",
            "",
            f"`{output_dir.name}/candidate_metrics.csv` holds every trial x fill x cost row.",
            "",
        ]
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(decision.to_string(index=False))
    print(dsr.to_string(index=False))
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
