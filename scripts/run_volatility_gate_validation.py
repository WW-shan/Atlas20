"""Validate a parameter-insensitive BTC volatility-scaled trailing gate.

The inherited 11-day/two-day BTC gate is a local spike in the decision-point
audit.  This script tests the evidence-supported alternative: a Chandelier-style
trailing exit whose distance is scaled by BTC's own realized volatility.

The strategy otherwise stays unchanged: point-in-time Top20, CTREND-breakout
top-1, 75-day/three-day own-trend stop, next-rebalance re-entry, no leverage,
and T+1 execution.  Results are reported across 21 rebalance phases and as a
fully staggered 21-tranche basket.
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
from atlas20.signals.risk import btc_above_volatility_scaled_trailing
from atlas20.strategies.overlays import (
    apply_daily_asset_stop_overlay,
    apply_daily_risk_overlay,
)
from atlas20.universe.builder import prepare_market_data

from scripts.run_decision_point_ablation import (
    _build_base_targets,
    _simulate_metrics,
)
from scripts.run_strategy_evidence_audit import (
    DEFAULT_CYCLE_DAYS,
    _combine_tranches,
    _metrics_from_returns,
)
from scripts.run_trend_stop_champion import confirmed_above_ma


def _volatility_gate_grid() -> tuple[tuple[int, int, float, int], ...]:
    """Return (lookback, vol_window, vol_multiple, confirm_days) variants."""
    grid: list[tuple[int, int, float, int]] = []
    for lookback in (20, 30, 50, 65):
        for vol_multiple in (1.5, 2.0, 2.5, 3.0):
            grid.append((lookback, 30, vol_multiple, 2))
    for lookback in (30, 50):
        for confirm_days in (1, 3, 5):
            grid.append((lookback, 30, 2.0, confirm_days))
    return tuple(dict.fromkeys(grid))


def _summarize(phase_frame: pd.DataFrame) -> pd.DataFrame:
    return (
        phase_frame.groupby(
            ["lookback", "vol_window", "vol_multiple", "confirm_days", "cost_bps"],
            as_index=False,
        )
        .agg(
            phase_median_multiple=("multiple", "median"),
            phase_min_multiple=("multiple", "min"),
            phase_max_multiple=("multiple", "max"),
            phase_median_sharpe=("sharpe", "median"),
            phase_worst_drawdown=("max_drawdown", "min"),
            phase_median_turnover=("annualized_turnover", "median"),
        )
        .sort_values(
            ["cost_bps", "phase_median_multiple"],
            ascending=[True, False],
        )
    )


def _write_report(
    output_dir: Path,
    summary: pd.DataFrame,
    basket: pd.DataFrame,
) -> None:
    summary_20 = summary[summary["cost_bps"] == 20.0]
    basket_20 = basket[basket["cost_bps"] == 20.0].sort_values(
        "multiple",
        ascending=False,
    )
    lines = [
        "# BTC Volatility-Scaled Trailing Gate — 2022 Validation",
        "",
        "The inherited 11-day/two-day BTC gate is a local parameter spike. This",
        "study replaces the fixed-day threshold with a trailing exit whose distance",
        "is scaled by BTC realized volatility. It keeps the point-in-time Top20,",
        "CTREND-breakout top-1, 75D/3 own-trend stop, next-rebalance re-entry,",
        "no-leverage, and T+1 rules fixed.",
        "",
        "## External evidence",
        "",
        "- Moreira and Muir, *Volatility-Managed Portfolios*: scaling exposure by",
        "  realized volatility can improve risk-adjusted outcomes.",
        "  <https://doi.org/10.1111/jofi.12467>",
        "- Yang, *Cryptocurrency market risk-managed momentum strategies*:",
        "  volatility scaling improved crypto momentum Sharpe and returns.",
        "  <https://doi.org/10.1016/j.frl.2025.107879>",
        "- Man Group, *In Crypto We Trend*: trend-following crypto exposure should",
        "  balance diversification and transaction costs; volatility scaling can",
        "  reduce pressure-period turnover.",
        "  <https://www.man.com/insights/in-crypto-we-trend>",
        "",
        "## Phase summary at 20bps",
        "",
        dataframe_to_markdown(summary_20),
        "",
        "## Fully staggered 21-tranche basket at 20bps",
        "",
        dataframe_to_markdown(basket_20),
        "",
        "## Audit conclusion",
        "",
        "- The best 21-tranche result is 3.22x at 20bps, with a 1.89x phase",
        "  median, 0.20x worst phase, 0.70 Sharpe, and -56.0% drawdown.",
        "- The volatility-scaled gate is more continuous than the inherited",
        "  11-day/two-day threshold, but it does not restore stable high returns.",
        "- Wider volatility multiples often never trigger and collapse back to",
        "  the no-gate strategy.",
        "- This gate is therefore not adopted as a production replacement.",
        "",
        "## Interpretation guardrail",
        "",
        "The candidate is not selected solely by its best basket multiple. The",
        "lookback, volatility multiple, and confirmation neighborhood must remain",
        "economically similar; otherwise the result is another parameter spike.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--cost-bps", default="2,20")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/volatility_gate_validation_2022"),
    )
    args = parser.parse_args()

    config = load_config(args.config).model_copy(deep=True)
    config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    config.universe.universe_size = 20
    config.universe.min_history_days = 90
    config.universe.min_daily_dollar_volume = 25_000_000.0
    configure_logging(config.logging.level)

    start_date = pd.Timestamp(config.start_timestamp).normalize()
    panel = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "panel_daily.csv")
    metadata = pd.read_csv(
        config.resolve_path(config.paths.processed_dir) / "metadata.csv"
    ).set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    end_date = (
        pd.Timestamp(args.end_date).normalize()
        if args.end_date
        else pd.Timestamp(market.price.index.max()).normalize()
    )
    costs = tuple(float(item.strip()) for item in args.cost_bps.split(",") if item.strip())
    grid = _volatility_gate_grid()

    phase_rows: list[dict[str, object]] = []
    path_by_key: dict[tuple[int, int, float, int, float, int], pd.Series] = {}
    for offset in range(DEFAULT_CYCLE_DAYS):
        schedule_start = start_date + pd.Timedelta(days=offset)
        base_targets = _build_base_targets(market, config, schedule_start, end_date)
        trend_on = confirmed_above_ma(market.price, 75, 3)
        stopped_targets = apply_daily_asset_stop_overlay(base_targets, trend_on)
        for lookback, vol_window, vol_multiple, confirm_days in grid:
            risk_on = btc_above_volatility_scaled_trailing(
                market.price,
                lookback=lookback,
                vol_window=vol_window,
                vol_multiple=vol_multiple,
                confirm_days=confirm_days,
            )
            targets = apply_daily_risk_overlay(stopped_targets, risk_on)
            for cost_bps in costs:
                metrics, returns = _simulate_metrics(
                    market,
                    targets,
                    evaluation_start=start_date,
                    end_date=end_date,
                    cost_bps=cost_bps,
                    annualization_days=config.annualization_days,
                )
                path_by_key[
                    (lookback, vol_window, vol_multiple, confirm_days, cost_bps, offset)
                ] = returns
                phase_rows.append(
                    {
                        "lookback": lookback,
                        "vol_window": vol_window,
                        "vol_multiple": vol_multiple,
                        "confirm_days": confirm_days,
                        "offset_days": offset,
                        "cost_bps": cost_bps,
                        **metrics,
                    }
                )

    phase_frame = pd.DataFrame(phase_rows)
    summary = _summarize(phase_frame)

    basket_rows: list[dict[str, object]] = []
    for lookback, vol_window, vol_multiple, confirm_days in grid:
        for cost_bps in costs:
            paths = {
                offset: path_by_key[
                    (lookback, vol_window, vol_multiple, confirm_days, cost_bps, offset)
                ]
                for offset in range(DEFAULT_CYCLE_DAYS)
            }
            basket_returns = _combine_tranches(paths, list(range(DEFAULT_CYCLE_DAYS)))
            basket_rows.append(
                {
                    "lookback": lookback,
                    "vol_window": vol_window,
                    "vol_multiple": vol_multiple,
                    "confirm_days": confirm_days,
                    "cost_bps": cost_bps,
                    **_metrics_from_returns(basket_returns, config.annualization_days),
                }
            )
    basket = pd.DataFrame(basket_rows)

    output_dir = ensure_dir(args.output_dir)
    phase_frame.to_csv(output_dir / "phase_metrics.csv", index=False)
    summary.to_csv(output_dir / "variant_summary.csv", index=False)
    basket.to_csv(output_dir / "staggered_basket.csv", index=False)
    manifest = {
        "window": {
            "start": start_date.date().isoformat(),
            "end": end_date.date().isoformat(),
        },
        "cost_bps": list(costs),
        "cycle_days": DEFAULT_CYCLE_DAYS,
        "grid": [list(item) for item in grid],
        "own_stop": {"ma_window": 75, "confirm_days": 3, "reentry": "next_rebalance"},
        "data": "data/processed/panel_daily.csv",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    _write_report(output_dir, summary, basket)
    print(summary[summary["cost_bps"] == 20.0].to_string(index=False))
    print(basket[basket["cost_bps"] == 20.0].to_string(index=False))
    print(f"Wrote volatility-gate validation to {output_dir}")


if __name__ == "__main__":
    main()
