"""Reproduce the daily own-trend-stop champion.

Final candidate from the 2022-start research:

* point-in-time Top20, exclude BTC;
* CTREND-breakout top-1 selection on a 21-day calendar;
* monitor the holding against its own 75-day moving average every day;
* after three consecutive closes below that average, exit to cash;
* re-enter only on the next scheduled decision when the base selection still
  chooses the coin and its trend filter is back on;
* BTC 11-day trailing gate with two-day confirmation;
* no leverage and no shorting, T+1 execution.

This is a deliberately modest daily use of information: the coin ranking stays
on its 21-day schedule, while the daily data controls risk.  The accompanying
validation report shows why daily leader rotation was not adopted: its best
fixed-start result was an isolated parameter spike and did not survive the
neighbourhood check.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.analytics.metrics import compute_summary_metrics  # noqa: E402
from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.backtest.engine import BacktestResult, run_backtest  # noqa: E402
from atlas20.config import load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import btc_above_trailing_price  # noqa: E402
from atlas20.strategies.convex_leader import build_ctrend_lite_targets  # noqa: E402
from atlas20.strategies.overlays import (  # noqa: E402
    apply_daily_asset_stop_overlay,
    apply_daily_risk_overlay,
)
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)

from scripts.run_ctrend_champion import (  # noqa: E402
    _btc_benchmark,
    _friction,
    _latest_signal_payload,
    _subperiod_rows,
)


@dataclass(frozen=True)
class TrendStopChampionSpec:
    top_n: int = 1
    frequency: str = "21D"
    score_family: str = "ctrend_lite_breakout"
    include_btc: bool = False
    ma_window: int = 75
    confirm_days: int = 3
    btc_stop_lookback: int = 11
    btc_stop_confirm_days: int = 2


def confirmed_above_ma(price: pd.DataFrame, window: int, confirm_days: int) -> pd.DataFrame:
    """Return a daily trend-on mask with a confirmed downside exit."""
    moving_average = price.rolling(window, min_periods=window).mean()
    below = price < moving_average
    if confirm_days <= 1:
        return ~below
    return ~(below.rolling(confirm_days, min_periods=confirm_days).sum() >= confirm_days)


def build_trend_stop_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    config,
    spec: TrendStopChampionSpec,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame, pd.Series, pd.DataFrame]:
    built = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=spec.top_n,
        frequency=spec.frequency,
        score_family=spec.score_family,
        include_btc=spec.include_btc,
    )
    trend_on = confirmed_above_ma(market.price, spec.ma_window, spec.confirm_days)
    stopped = apply_daily_asset_stop_overlay(built.targets, trend_on)
    risk_on = btc_above_trailing_price(
        market.price,
        lookback_days=spec.btc_stop_lookback,
        confirm_days=spec.btc_stop_confirm_days,
    )
    targets = apply_daily_risk_overlay(
        stopped,
        risk_on,
        risk_off_target=None,
        initial_target=None,
    )

    history = built.selection_history.copy()
    if not history.empty:
        history["rebalance_date"] = pd.to_datetime(history["rebalance_date"])
        history["btc_gate_open"] = history["rebalance_date"].map(risk_on).fillna(False)
        history["own_trend_on"] = history["rebalance_date"].map(
            lambda date: bool(trend_on.loc[date, history.loc[history["rebalance_date"] == date, "coin_id"].iloc[0]])
            if date in trend_on.index
            else False
        )
    target_rows: list[dict[str, object]] = []
    current = ""
    for date in market.price.index:
        if date in targets:
            target = targets[date]
            positive = target[target > 0.0]
            current = str(positive.idxmax()) if not positive.empty else ""
        target_rows.append({"date": date, "target_asset": current, "btc_gate_open": bool(risk_on.get(date, True))})
    target_history = pd.DataFrame(target_rows)
    return targets, history, risk_on, target_history


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--cost-bps", default="2,5,10,20,50,100")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/trend_stop_champion_2022"))
    parser.add_argument("--rebuild-data", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config).model_copy(deep=True)
    config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    config.universe.universe_size = 20
    config.universe.min_history_days = 90
    config.universe.min_daily_dollar_volume = 25_000_000.0
    configure_logging(config.logging.level)

    if args.rebuild_data:
        panel, metadata = build_processed_datasets(
            config,
            load_sector_config(config.resolve_path("config/sectors.yaml")),
            persist=False,
        )
    else:
        panel = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "panel_daily.csv")
        metadata = pd.read_csv(
            config.resolve_path(config.paths.processed_dir) / "metadata.csv"
        ).set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    schedule = get_rebalance_dates(market.price.index, config.start_timestamp, "21D", "21D")
    universe = build_rebalance_universe(market, schedule, config)
    spec = TrendStopChampionSpec()
    targets, history, risk_on, target_history = build_trend_stop_targets(market, universe, config, spec)

    output_dir = ensure_dir(args.output_dir)
    results: dict[float, BacktestResult] = {}
    rows: list[dict[str, object]] = []
    for cost_bps in [float(item) for item in args.cost_bps.split(",") if item.strip()]:
        result = run_backtest(
            name=f"CTREND_TREND_STOP_{cost_bps:g}bps",
            asset_returns=market.returns.loc[config.start_timestamp : config.end_timestamp],
            rebalance_targets=targets,
            sector_by_coin=market.metadata["sector"],
            friction=_friction(config, cost_bps),
            initial_capital=config.initial_capital,
            gross_target_exposure=1.0,
            max_gross_exposure=1.0,
        )
        results[cost_bps] = result
        metrics = compute_summary_metrics(result, config.annualization_days)
        rows.append(
            {
                "candidate_id": result.name,
                "total_cost_bps": cost_bps,
                "leverage": 1.0,
                **metrics,
                "multiple": float(metrics["total_return"]) + 1.0,
            }
        )
    benchmark = _btc_benchmark(market, config, total_cost_bps=2.0)
    benchmark_metrics = compute_summary_metrics(benchmark, config.annualization_days)
    rows.append(
        {
            "candidate_id": "BTC_BH_2bps",
            "total_cost_bps": 2.0,
            "leverage": 1.0,
            **benchmark_metrics,
            "multiple": float(benchmark_metrics["total_return"]) + 1.0,
        }
    )
    summary = pd.DataFrame(rows)
    summary.to_csv(output_dir / "performance_summary.csv", index=False)

    primary = results[float(args.cost_bps.split(",")[0])]
    primary.daily_returns.to_csv(output_dir / "daily_returns.csv", header=["daily_return"])
    primary.weights.to_csv(output_dir / "weights.csv")
    yearly = (1.0 + primary.daily_returns).resample("YE").prod() - 1.0
    yearly.index.name = "year"
    yearly.to_csv(output_dir / "yearly_returns.csv")
    subperiod = _subperiod_rows(primary, config)
    subperiod.to_csv(output_dir / "subperiod_summary.csv", index=False)
    history.to_csv(output_dir / "selection_history.csv", index=False)
    target_history.to_csv(output_dir / "target_history.csv", index=False)

    latest = _latest_signal_payload(targets, risk_on, market, config)
    latest["rule"] = (
        "Top20 ex-BTC CTREND-breakout top1, 21D; daily own 75d MA confirm3 cash stop; "
        "BTC 11d trailing confirm2 cash gate; no leverage"
    )
    (output_dir / "latest_signal.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")
    (output_dir / "latest_signal.md").write_text(
        "\n".join(
            [
                "# Latest Trend-Stop Champion Signal",
                "",
                f"- As of: {latest['as_of']}",
                f"- Latest target date: {latest['latest_target_date']}",
                f"- BTC gate open: {latest['btc_gate_open']}",
                f"- Gross exposure: {latest['gross_exposure']:.4f}",
                f"- Next scheduled rebalance: {latest['next_scheduled_rebalance']}",
                f"- Targets: {latest['targets']}",
                f"- Rule: {latest['rule']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "spec": asdict(spec),
                "window": {
                    "start": config.start_timestamp.date().isoformat(),
                    "end": config.end_timestamp.date().isoformat(),
                },
                "universe_size": config.universe.universe_size,
                "maximum_gross_exposure": 1.0,
                "cost_bps": [float(item) for item in args.cost_bps.split(",") if item.strip()],
                "data": "data/processed/panel_daily.csv",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report_lines = [
        "# CTREND Top20 + Daily Own-Trend Stop — 2022 Start",
        "",
        "> **Research upper tail, not production-ready.** The headline result is tied to the",
        "> 2022-01-01 rebalance phase, and the inherited 11-day/two-day BTC gate is a local",
        "> parameter spike. See `PHASE_WARNING.md` and",
        "> `reports/decision_point_ablation_2022/` before using these numbers.",
        "",
        "This is the final candidate from the daily-rebalancing research. The coin ranking remains",
        "on the original 21-day schedule; the daily check is used to exit the holding after three",
        "consecutive closes below its own 75-day moving average. Re-entry waits for the next",
        "scheduled decision.",
        "",
        "## Summary",
        "",
        dataframe_to_markdown(summary.reset_index(drop=True)),
        "",
        "## Yearly Returns",
        "",
        dataframe_to_markdown(yearly.reset_index()),
        "",
        "## Subperiods",
        "",
        dataframe_to_markdown(subperiod.reset_index(drop=True)),
        "",
        "The daily leader-rotation alternatives were not adopted: the highest fixed-start result",
        "was a narrow parameter spike, and the more stable event variants did not improve the",
        "rolling-start distribution enough to justify their much higher turnover.",
        "",
    ]
    (output_dir / "champion_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Wrote trend-stop champion to {output_dir}")


if __name__ == "__main__":
    main()
