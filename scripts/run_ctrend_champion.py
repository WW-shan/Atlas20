"""Reproduce the concentrated CTREND Top20 champion and its risk overlays.

Champion definition (2022-start research window):

* point-in-time Top20, strict liquidity/history gate
* 21-day rebalance, hold the single strongest CTREND-breakout coin
* exclude BTC from the selection pool
* BTC 11-day trailing-loss gate, confirmed for two days
* risk-off target is cash; no leverage and no shorting
* T+1 execution with explicit per-side friction

The script writes the return series, the full per-rebalance selection trace,
yearly/subperiod returns, cost stress, and contribution attribution.  It does
not make a production claim: the research note beside the report records the
rolling-start limitations.
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
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.analytics.metrics import compute_summary_metrics  # noqa: E402
from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.backtest.engine import BacktestResult, run_backtest  # noqa: E402
from atlas20.config import load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import btc_above_trailing_price  # noqa: E402
from atlas20.strategies.convex_leader import build_ctrend_lite_targets  # noqa: E402
from atlas20.strategies.overlays import apply_daily_risk_overlay  # noqa: E402
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)


@dataclass(frozen=True)
class ChampionSpec:
    top_n: int = 1
    frequency: str = "21D"
    score_family: str = "ctrend_lite_breakout"
    include_btc: bool = False
    min_history_days: int = 90
    min_daily_dollar_volume: float = 25_000_000.0
    btc_stop_lookback: int = 11
    btc_stop_confirm_days: int = 2


def _friction(config, total_cost_bps: float):
    friction = config.frictions.model_copy(deep=True)
    half = float(total_cost_bps) / 2.0
    friction.fee_bps = half
    friction.slippage_bps = half
    friction.max_weight_per_coin = 1.0
    friction.max_weight_per_sector = 1.0
    return friction


def build_champion_targets(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    config,
    spec: ChampionSpec,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame, pd.Series]:
    built = build_ctrend_lite_targets(
        market,
        universe,
        config,
        top_n=spec.top_n,
        frequency=spec.frequency,
        score_family=spec.score_family,
        include_btc=spec.include_btc,
    )
    risk_on = btc_above_trailing_price(
        market.price,
        lookback_days=spec.btc_stop_lookback,
        confirm_days=spec.btc_stop_confirm_days,
    )
    targets = apply_daily_risk_overlay(
        built.targets,
        risk_on,
        risk_off_target=None,
        initial_target=None,
    )
    history = built.selection_history.copy()
    if not history.empty:
        history["rebalance_date"] = pd.to_datetime(history["rebalance_date"])
        history["btc_gate_open"] = history["rebalance_date"].map(risk_on).fillna(False)
        history["executed_coin_id"] = history["coin_id"].where(history["btc_gate_open"], "")
        history["executed_weight"] = history["coin_weight"].where(history["btc_gate_open"], 0.0)
    return targets, history, risk_on


def _btc_benchmark(market: MarketDataBundle, config, total_cost_bps: float) -> BacktestResult:
    friction = _friction(config, total_cost_bps)
    return run_backtest(
        name="BTC_BH",
        asset_returns=market.returns.loc[
            config.start_timestamp : config.end_timestamp,
            ["bitcoin"],
        ],
        rebalance_targets={pd.Timestamp(config.start_timestamp): pd.Series({"bitcoin": 1.0})},
        sector_by_coin=market.metadata["sector"],
        friction=friction,
        initial_capital=config.initial_capital,
        gross_target_exposure=1.0,
        max_gross_exposure=1.0,
    )


def _subperiod_rows(result: BacktestResult, config) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, start, end in (
        ("2022", "2022-01-01", "2022-12-31"),
        ("2023", "2023-01-01", "2023-12-31"),
        ("2024", "2024-01-01", "2024-12-31"),
        ("2025", "2025-01-01", "2025-12-31"),
        ("2026_ytd", "2026-01-01", None),
    ):
        subset = result.daily_returns.loc[pd.Timestamp(start) :]
        if end is not None:
            subset = subset.loc[: pd.Timestamp(end)]
        if subset.empty:
            continue
        metrics = compute_summary_metrics(
            BacktestResult(
                name=result.name,
                daily_returns=subset,
                equity_curve=(1.0 + subset).cumprod(),
                drawdown=((1.0 + subset).cumprod() / (1.0 + subset).cumprod().cummax() - 1.0),
                weights=result.weights.reindex(subset.index).fillna(0.0),
                turnover=result.turnover.reindex(subset.index).fillna(0.0),
                holdings_count=result.holdings_count.reindex(subset.index).fillna(0.0),
                sector_exposure=result.sector_exposure.reindex(subset.index).fillna(0.0),
                rebalance_targets=result.rebalance_targets,
            ),
            config.annualization_days,
        )
        rows.append({"period": label, **metrics})
    return pd.DataFrame(rows)


def _latest_signal_payload(
    targets: dict[pd.Timestamp, pd.Series],
    risk_on: pd.Series,
    market: MarketDataBundle,
    config,
) -> dict[str, object]:
    as_of = pd.Timestamp(market.price.index.max())
    eligible_dates = sorted(date for date in targets if pd.Timestamp(date) <= as_of)
    if not eligible_dates:
        raise ValueError("champion strategy produced no targets")
    target_date = pd.Timestamp(eligible_dates[-1])
    target = targets[target_date]
    held = target[target > 0.0].sort_values(ascending=False)
    schedule = get_rebalance_dates(
        market.price.index,
        config.start_timestamp,
        "21D",
        "21D",
    )
    next_rebalance = next((date for date in schedule if date > as_of), None)
    if next_rebalance is None and schedule:
        next_rebalance = pd.Timestamp(schedule[-1]) + pd.Timedelta(days=21)
    return {
        "as_of": as_of.date().isoformat(),
        "latest_target_date": target_date.date().isoformat(),
        "btc_gate_open": bool(risk_on.get(as_of, True)),
        "targets": {str(coin): float(weight) for coin, weight in held.items()},
        "gross_exposure": float(held.sum()),
        "next_scheduled_rebalance": next_rebalance.date().isoformat() if next_rebalance is not None else None,
        "rule": "Top20 ex-BTC CTREND-breakout top1, 21D; BTC 11d trailing confirm2 cash gate; no leverage",
    }


def _write_report(path: Path, summary: pd.DataFrame, subperiod: pd.DataFrame, yearly: pd.DataFrame) -> None:
    lines = [
        "# CTREND Top20 Champion — 2022 Start",
        "",
        "This is a real point-in-time Top20, long-only, unlevered simulation. "
        "The primary cost case is 2bps round-trip (the desk's stated venue "
        "cost plus rebate), with 20bps shown as a conservative stress case. "
        "The strategy exits to cash when BTC loses its 11-day trailing level "
        "for two consecutive closes and only re-enters at the next 21-day "
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
        "This report deliberately does not claim that the 20x target is "
        "repeatable. The accompanying rolling-start diagnostics show a wide "
        "dispersion across entry dates.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/ctrend_champion_top20_2022"))
    parser.add_argument("--cost-bps", default="2,20")
    args = parser.parse_args()

    config = load_config(args.config).model_copy(deep=True)
    config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    config.universe.universe_size = 20
    config.universe.min_history_days = 90
    config.universe.min_daily_dollar_volume = 25_000_000.0
    configure_logging(config.logging.level)

    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    panel, metadata = build_processed_datasets(config, sector_config, persist=False)
    market = prepare_market_data(panel, metadata, config)
    rebalance_dates = get_rebalance_dates(
        market.price.index,
        config.start_timestamp,
        "21D",
        "21D",
    )
    universe = build_rebalance_universe(market, rebalance_dates, config)
    spec = ChampionSpec()
    targets, history, risk_on = build_champion_targets(market, universe, config, spec)

    output_dir = ensure_dir(args.output_dir)
    results: dict[float, BacktestResult] = {}
    summary_rows: list[dict[str, object]] = []
    for cost_bps in [float(item) for item in args.cost_bps.split(",") if item.strip()]:
        result = run_backtest(
            name=f"CTREND_TOP20_CHAMPION_{cost_bps:g}bps",
            asset_returns=market.returns.loc[
                config.start_timestamp : config.end_timestamp
            ],
            rebalance_targets=targets,
            sector_by_coin=market.metadata["sector"],
            friction=_friction(config, cost_bps),
            initial_capital=config.initial_capital,
            gross_target_exposure=1.0,
            max_gross_exposure=1.0,
        )
        results[cost_bps] = result
        metrics = compute_summary_metrics(result, config.annualization_days)
        summary_rows.append(
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
    summary_rows.append(
        {
            "candidate_id": "BTC_BH_2bps",
            "total_cost_bps": 2.0,
            "leverage": 1.0,
            **benchmark_metrics,
            "multiple": float(benchmark_metrics["total_return"]) + 1.0,
        }
    )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "performance_summary.csv", index=False)

    primary = results[float(args.cost_bps.split(",")[0])]
    primary.daily_returns.to_csv(output_dir / "daily_returns.csv", header=["daily_return"])
    yearly = (1.0 + primary.daily_returns).resample("YE").prod() - 1.0
    yearly.index.name = "year"
    yearly.to_csv(output_dir / "yearly_returns.csv")
    subperiod = _subperiod_rows(primary, config)
    subperiod.to_csv(output_dir / "subperiod_summary.csv", index=False)
    history.to_csv(output_dir / "selection_history.csv", index=False)
    latest_signal = _latest_signal_payload(targets, risk_on, market, config)
    (output_dir / "latest_signal.json").write_text(
        json.dumps(latest_signal, indent=2),
        encoding="utf-8",
    )
    (output_dir / "latest_signal.md").write_text(
        "\n".join(
            [
                "# Latest CTREND Champion Signal",
                "",
                f"- As of: {latest_signal['as_of']}",
                f"- Latest target date: {latest_signal['latest_target_date']}",
                f"- BTC gate open: {latest_signal['btc_gate_open']}",
                f"- Gross exposure: {latest_signal['gross_exposure']:.4f}",
                f"- Next scheduled rebalance: {latest_signal['next_scheduled_rebalance']}",
                f"- Targets: {latest_signal['targets']}",
                f"- Rule: {latest_signal['rule']}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    weights = primary.weights.reindex(columns=market.returns.columns).fillna(0.0)
    asset_returns = market.returns.reindex(index=weights.index, columns=weights.columns).fillna(0.0)
    contributions = weights.shift(1).fillna(0.0).mul(asset_returns).sum(axis=0)
    contribution = (
        contributions.sort_values(ascending=False)
        .rename("contribution")
        .to_frame()
        .reset_index(names="coin_id")
    )
    contribution.to_csv(output_dir / "contribution.csv", index=False)

    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "spec": asdict(spec),
                "window": {
                    "start": config.start_timestamp.date().isoformat(),
                    "end": config.end_timestamp.date().isoformat(),
                },
                "universe_size": config.universe.universe_size,
                "data": "data/processed/panel_daily.csv",
                "maximum_gross_exposure": 1.0,
                "cost_bps": [float(item) for item in args.cost_bps.split(",") if item.strip()],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_report(output_dir / "champion_report.md", summary, subperiod, yearly)
    print(summary.to_string(index=False))
    print(f"Wrote champion report to {output_dir}")


if __name__ == "__main__":
    main()
