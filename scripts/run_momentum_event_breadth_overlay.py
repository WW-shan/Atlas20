"""Evaluate a Top20 market-breadth overlay on the daily momentum-event ensemble.

The base strategy is the strict point-in-time Top20 momentum-event ensemble:
three CTREND-lite families (balanced, relative-strength, breakout), a daily
hysteresis rule, immediate exit when the incumbent leaves the current Top20,
a BTC 100-day moving-average gate, and 60-day volatility-target sizing.

This study adds a breadth regime filter computed only from the current Top20:
the fraction of constituents above their own 50-day moving average.  The
filter is used as a risk gate, not as a new selection universe.  The primary
comparison is:

* baseline: BTC 100D MA gate only;
* breadth: BTC 100D MA gate and breadth >= 50%;
* blend: equal-weight baseline and breadth sleeves.

The report also tests breadth thresholds, cost stress, yearly returns, and a
pre-2022 stress period.
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

from atlas20.backtest.single_asset import SingleAssetWeightBacktestResult  # noqa: E402
from atlas20.config import ResearchConfig  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import btc_above_moving_average  # noqa: E402
from atlas20.universe.builder import MarketDataBundle  # noqa: E402

from scripts.run_momentum_event_ensemble import (  # noqa: E402
    MOMENTUM_FAMILIES,
    PRIMARY_SPEC,
    _load_market,
    _net_returns,
    _score_panels,
    _simulate_sleeve,
    _summary_row,
    _target_assets_from_scores,
    _yearly_returns,
)


def _parse_floats(value: str) -> tuple[float, ...]:
    parsed = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 0.0 for item in parsed):
        raise ValueError("Expected a non-empty list of non-negative numbers")
    return parsed


def _breadth_signal(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    ma_window: int = 50,
) -> pd.Series:
    """Return the fraction of current Top20 coins above their own moving average."""
    if ma_window < 2:
        raise ValueError("ma_window must be at least 2")
    moving_average = market.price.rolling(ma_window, min_periods=ma_window).mean()
    above = market.price > moving_average
    by_date = {pd.Timestamp(date): group for date, group in universe.groupby("rebalance_date")}
    values: dict[pd.Timestamp, float] = {}
    for date in index:
        snapshot = by_date.get(pd.Timestamp(date))
        if snapshot is None or snapshot.empty:
            values[pd.Timestamp(date)] = float("nan")
            continue
        coin_ids = snapshot["coin_id"].astype(str).tolist()
        usable = above.loc[pd.Timestamp(date), coin_ids].dropna()
        values[pd.Timestamp(date)] = float(usable.mean()) if not usable.empty else float("nan")
    return pd.Series(values, dtype=float).sort_index()


def _build_sleeve_results(
    market: MarketDataBundle,
    score_panels: dict[str, pd.DataFrame],
    config: ResearchConfig,
    index: pd.DatetimeIndex,
    *,
    risk_on: pd.Series,
    target_vols: tuple[float, ...],
    vol_window: int,
) -> dict[str, SingleAssetWeightBacktestResult]:
    results: dict[str, SingleAssetWeightBacktestResult] = {}
    for family, score_panel in score_panels.items():
        target_assets = _target_assets_from_scores(
            market,
            score_panel,
            config,
            PRIMARY_SPEC,
            index,
        )
        for target_vol in target_vols:
            key = f"{family}|tv{target_vol:.1f}"
            results[key] = _simulate_sleeve(
                market,
                target_assets,
                risk_on,
                target_volatility=target_vol,
                vol_window=vol_window,
            )
    return results


def _ensemble_returns(
    sleeve_results: dict[str, SingleAssetWeightBacktestResult],
    *,
    target_vols: tuple[float, ...],
    cost_bps: float,
) -> pd.Series:
    columns = [
        _net_returns(sleeve_results[f"{family}|tv{target_vol:.1f}"], cost_bps)
        for family in MOMENTUM_FAMILIES
        for target_vol in target_vols
    ]
    return pd.concat(columns, axis=1).mean(axis=1)


def _period_metrics(returns: pd.Series, start: str, end: str | None = None) -> dict[str, float]:
    from scripts.run_strategy_evidence_audit import _metrics_from_returns

    sliced = returns.loc[start:end]
    return _metrics_from_returns(sliced)


def _write_report(
    output_dir: Path,
    *,
    summary: pd.DataFrame,
    threshold_sensitivity: pd.DataFrame,
    blend_sensitivity: pd.DataFrame,
    stress: pd.DataFrame,
    yearly: pd.DataFrame,
) -> None:
    lines = [
        "# Top20 Market-Breadth Overlay on the Momentum-Event Ensemble",
        "",
        "## Design",
        "",
        "- Selection remains strictly inside the point-in-time Top20.",
        "- Base event rule: three CTREND-lite families, min hold 5 days, hold-rank 2,",
        "  10% score gap, 1-day confirmation, immediate exit if the incumbent leaves Top20.",
        "- BTC 100-day MA gate with 2-day confirmation.",
        "- Breadth is the fraction of the current Top20 above its own 50-day MA.",
        "- The breadth sleeve requires BTC risk-on and breadth >= 50%.",
        "- The blend is the daily equal-weight portfolio of baseline and breadth sleeves.",
        "- 60-day realized-volatility target; 70% and 80% sleeves are equal-weighted.",
        "- No leverage, no shorting, gross exposure capped at 1.0, T+1 execution.",
        "",
        "## Primary comparison",
        "",
        dataframe_to_markdown(summary.sort_values(["cost_bps", "period", "strategy"])),
        "",
        "## Breadth-threshold sensitivity",
        "",
        dataframe_to_markdown(threshold_sensitivity.sort_values(["cost_bps", "post_2024_multiple"], ascending=[True, False])),
        "",
        "## Baseline / breadth blend sensitivity",
        "",
        dataframe_to_markdown(blend_sensitivity.sort_values(["cost_bps", "post_2024_multiple"], ascending=[True, False])),
        "",
        "## Pre-2022 stress check",
        "",
        dataframe_to_markdown(stress.sort_values(["cost_bps", "strategy"])),
        "",
        "## Yearly returns",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## Evidence and interpretation",
        "",
        "- Fieberg, Liedtke, Poddig, Walker, and Zaremba, *A Trend Factor for the Cross",
        "  Section of Cryptocurrency Returns*: a price/volume trend signal predicts returns",
        "  and persists in big and liquid coins, supporting the CTREND direction.",
        "  <https://doi.org/10.1017/S0022109024000747>",
        "- Ficura, *Impact of size and volume on cryptocurrency momentum and reversal*:",
        "  large and liquid coins exhibit weekly momentum, while small and illiquid coins",
        "  exhibit reversal; proximity to a recent high predicts positively for large/liquid coins.",
        "  <https://quantitative.cz/wp-content/uploads/2023/09/impact_of_size_and_volume_on_cryptocurrency_momentum_and_reversal.pdf>",
        "- Kurihara and Matsumoto, *Price Transmission from Bitcoin to Altcoins*: BTC",
        "  leads altcoins, with the strongest delayed response in small, less-liquid coins.",
        "  This motivates using BTC as a regime input rather than as a selection candidate.",
        "  <https://doi.org/10.1007/s10690-026-09589-z>",
        "- The breadth filter is primarily a risk-management overlay in this study. Its",
        "  improvement in the post-2024 period is project evidence, not yet an established",
        "  academic crypto anomaly.",
        "",
        "## Guardrails",
        "",
        "- The 50% breadth threshold is economically natural (majority of the current Top20)",
        "  but remains a selected parameter; the 45% and 55% neighbors must stay in the report.",
        "- The blend improves drawdown and post-2024 performance but lowers the full-period",
        "  multiple versus the baseline; it is a risk-return tradeoff, not a free improvement.",
        "- Capacity, data revisions, delistings, exchange outages, and regime changes remain.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--stress-start", default="2020-10-03")
    parser.add_argument("--stress-end", default="2021-12-31")
    parser.add_argument("--target-vols", default="0.7,0.8")
    parser.add_argument("--vol-window", type=int, default=60)
    parser.add_argument("--breadth-window", type=int, default=50)
    parser.add_argument("--cost-bps", default="2,20,50,100")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/momentum_event_breadth_overlay_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    costs = _parse_floats(args.cost_bps)
    target_vols = _parse_floats(args.target_vols)

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.stress_start,
        end_date=args.end_date,
    )
    score_panels = _score_panels(market, universe)
    btc_gate = btc_above_moving_average(
        market.price,
        ma_window=100,
        confirm_days=2,
    ).reindex(index).fillna(False)
    breadth = _breadth_signal(
        market,
        universe,
        index,
        ma_window=args.breadth_window,
    )

    threshold_values = (0.40, 0.45, 0.50, 0.55, 0.60)
    threshold_results: dict[float, dict[str, SingleAssetWeightBacktestResult]] = {}
    for threshold in threshold_values:
        risk_on = btc_gate & (breadth >= threshold).fillna(False)
        threshold_results[threshold] = _build_sleeve_results(
            market,
            score_panels,
            config,
            index,
            risk_on=risk_on,
            target_vols=target_vols,
            vol_window=args.vol_window,
        )

    baseline_results = _build_sleeve_results(
        market,
        score_panels,
        config,
        index,
        risk_on=btc_gate,
        target_vols=target_vols,
        vol_window=args.vol_window,
    )

    output_dir = ensure_dir(args.output_dir)
    summary_rows: list[dict[str, object]] = []
    primary_returns: dict[str, dict[float, pd.Series]] = {
        "baseline": {},
        "breadth50": {},
        "blend50": {},
        "blend25": {},
        "blend75": {},
    }
    for cost_bps in costs:
        baseline = _ensemble_returns(
            baseline_results,
            target_vols=target_vols,
            cost_bps=cost_bps,
        )
        breadth50 = _ensemble_returns(
            threshold_results[0.50],
            target_vols=target_vols,
            cost_bps=cost_bps,
        )
        blends = {
            "blend25": 0.25 * baseline + 0.75 * breadth50,
            "blend50": 0.50 * baseline + 0.50 * breadth50,
            "blend75": 0.75 * baseline + 0.25 * breadth50,
        }
        for strategy, returns in (
            ("baseline", baseline),
            ("breadth50", breadth50),
            *blends.items(),
        ):
            primary_returns[strategy][cost_bps] = returns
            for period_name, start in (
                ("full_2022_plus", args.start_date),
                ("post_2023", "2023-01-01"),
                ("post_2024", "2024-01-01"),
            ):
                summary_rows.append(
                    _summary_row(
                        strategy,
                        returns.loc[pd.Timestamp(start) :],
                        cost_bps=cost_bps,
                        period=period_name,
                    )
                )

    threshold_rows: list[dict[str, object]] = []
    for threshold, results in threshold_results.items():
        for cost_bps in costs:
            returns = _ensemble_returns(
                results,
                target_vols=target_vols,
                cost_bps=cost_bps,
            )
            full = _period_metrics(returns, args.start_date)
            post_2024 = _period_metrics(returns, "2024-01-01")
            threshold_rows.append(
                {
                    "breadth_threshold": threshold,
                    "cost_bps": cost_bps,
                    "full_multiple": full["multiple"],
                    "full_sharpe": full["sharpe"],
                    "full_max_drawdown": full["max_drawdown"],
                    "post_2024_multiple": post_2024["multiple"],
                    "post_2024_sharpe": post_2024["sharpe"],
                    "post_2024_max_drawdown": post_2024["max_drawdown"],
                }
            )
    threshold_sensitivity = pd.DataFrame(threshold_rows)

    blend_rows: list[dict[str, object]] = []
    for cost_bps in costs:
        baseline = primary_returns["baseline"][cost_bps]
        breadth50 = primary_returns["breadth50"][cost_bps]
        for baseline_weight in (0.0, 0.25, 0.50, 0.75, 1.0):
            returns = baseline_weight * baseline + (1.0 - baseline_weight) * breadth50
            full = _period_metrics(returns, args.start_date)
            post_2024 = _period_metrics(returns, "2024-01-01")
            blend_rows.append(
                {
                    "baseline_weight": baseline_weight,
                    "breadth50_weight": 1.0 - baseline_weight,
                    "cost_bps": cost_bps,
                    "full_multiple": full["multiple"],
                    "full_sharpe": full["sharpe"],
                    "full_max_drawdown": full["max_drawdown"],
                    "post_2024_multiple": post_2024["multiple"],
                    "post_2024_sharpe": post_2024["sharpe"],
                    "post_2024_max_drawdown": post_2024["max_drawdown"],
                }
            )
    blend_sensitivity = pd.DataFrame(blend_rows)

    stress_rows: list[dict[str, object]] = []
    for cost_bps in costs:
        for strategy in ("baseline", "breadth50", "blend50"):
            returns = primary_returns[strategy][cost_bps].loc[
                pd.Timestamp(args.stress_start) : pd.Timestamp(args.stress_end)
            ]
            stress_rows.append(
                _summary_row(
                    strategy,
                    returns,
                    cost_bps=cost_bps,
                    period="stress_2020_10_to_2021_12",
                )
            )
    stress = pd.DataFrame(stress_rows)

    yearly = pd.DataFrame(
        {
            f"{strategy}_{cost_bps:g}bps": _yearly_returns(
                primary_returns[strategy][cost_bps].loc[pd.Timestamp(args.start_date) :]
            )
            for strategy in ("baseline", "breadth50", "blend50")
            for cost_bps in (2.0, 20.0)
        }
    )
    yearly.index.name = "year_end"

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "summary.csv", index=False)
    threshold_sensitivity.to_csv(output_dir / "breadth_threshold_sensitivity.csv", index=False)
    blend_sensitivity.to_csv(output_dir / "blend_sensitivity.csv", index=False)
    stress.to_csv(output_dir / "stress_test.csv", index=False)
    yearly.to_csv(output_dir / "yearly_returns.csv", index_label="year_end")
    for strategy, by_cost in primary_returns.items():
        for cost_bps, returns in by_cost.items():
            returns.rename(f"{strategy}_{cost_bps:g}bps").to_frame().to_csv(
                output_dir / f"{strategy}_{cost_bps:g}bps.csv",
                index_label="date",
            )

    manifest = {
        "data": "data/processed/panel_daily.csv",
        "universe": "point-in-time Top20",
        "start": args.start_date,
        "end": args.end_date,
        "stress": [args.stress_start, args.stress_end],
        "families": list(MOMENTUM_FAMILIES),
        "breadth_window": args.breadth_window,
        "breadth_thresholds": list(threshold_values),
        "primary_breadth_threshold": 0.50,
        "target_vols": list(target_vols),
        "vol_window": args.vol_window,
        "cost_bps": list(costs),
        "gate": "BTC 100D MA confirm2; breadth sleeve also requires Top20 breadth >= 50%",
        "execution": "signal close, T+1",
        "leverage": "none; gross exposure cap 1.0",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    _write_report(
        output_dir,
        summary=summary,
        threshold_sensitivity=threshold_sensitivity,
        blend_sensitivity=blend_sensitivity,
        stress=stress,
        yearly=yearly,
    )
    print(
        summary[
            (summary["strategy"].isin(["baseline", "breadth50", "blend50"]))
            & (summary["cost_bps"].isin([2.0, 20.0]))
        ].to_string(index=False)
    )
    print(f"Wrote breadth-overlay research to {output_dir}")


if __name__ == "__main__":
    main()
