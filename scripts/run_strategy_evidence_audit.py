"""Audit schedule-phase sensitivity and staggered-rebalance robustness.

The fixed-calendar champion can look strong on one start date while depending
on that exact calendar phase.  This script keeps every strategy rule fixed and
only shifts the rebalance schedule by 0..20 days, then compares:

* the original single-tranche strategy;
* equal-weight baskets of 3, 7, and 21 staggered tranches.

The fully staggered 21-tranche basket is phase invariant by construction: each
day of the 21-day cycle owns one tranche.  The other basket sizes show the
trade-off between phase diversification and return concentration.

All results are long-only, no leverage, T+1 execution, and use the processed
point-in-time panel.  The script does not rewrite canonical data.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.backtest.single_asset import simulate_single_asset_targets
from atlas20.config import ResearchConfig, load_config
from atlas20.logging_utils import configure_logging, ensure_dir
from atlas20.reporting.report import dataframe_to_markdown
from atlas20.signals.risk import btc_above_trailing_price
from atlas20.strategies.convex_leader import build_ctrend_lite_targets
from atlas20.strategies.overlays import (
    apply_daily_asset_stop_overlay,
    apply_daily_risk_overlay,
)
from atlas20.universe.builder import (
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)
from scripts.run_trend_stop_champion import confirmed_above_ma


DEFAULT_CYCLE_DAYS = 21
DEFAULT_TRANCHE_COUNTS = (1, 3, 7, 21)


@dataclass(frozen=True)
class AuditSpec:
    """Signal rules held fixed while only the calendar phase changes."""

    frequency: str = "21D"
    ma_window: int = 75
    confirm_days: int = 3
    btc_stop_lookback: int = 11
    btc_stop_confirm_days: int = 2
    score_family: str = "ctrend_lite_breakout"
    top_n: int = 1


def _parse_ints(value: str) -> tuple[int, ...]:
    parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 1 for item in parsed):
        raise ValueError("Expected a non-empty list of positive integers")
    return parsed


def _metrics_from_returns(returns: pd.Series, annualization_days: int = 365) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    periods = max(len(clean) - 1, 1)
    equity = (1.0 + clean).cumprod()
    multiple = float(equity.iloc[-1]) if not equity.empty else 1.0
    cagr = multiple ** (annualization_days / periods) - 1.0 if multiple > 0 else -1.0
    volatility = float(clean.std(ddof=0) * math.sqrt(annualization_days))
    sharpe = float(clean.mean() * annualization_days / volatility) if volatility > 0.0 else 0.0
    drawdown = equity / equity.cummax() - 1.0
    return {
        "multiple": multiple,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else 0.0,
    }


def _phase_offsets(tranche_count: int, shift: int, cycle_days: int = DEFAULT_CYCLE_DAYS) -> list[int]:
    """Return the phase offsets used by one staggered basket."""
    if tranche_count < 1:
        raise ValueError("tranche_count must be positive")
    if cycle_days < 1:
        raise ValueError("cycle_days must be positive")
    if tranche_count == 1:
        return [shift % cycle_days]
    return [
        (shift + round(index * cycle_days / tranche_count)) % cycle_days
        for index in range(tranche_count)
    ]


def _combine_tranches(paths: dict[int, pd.Series], offsets: list[int]) -> pd.Series:
    if not offsets:
        raise ValueError("offsets must be non-empty")
    frame = pd.concat([paths[offset].rename(offset) for offset in offsets], axis=1, sort=True)
    return frame.mean(axis=1)


def _target_asset_series(targets: dict[pd.Timestamp, pd.Series], index: pd.DatetimeIndex) -> pd.Series:
    assets = pd.Series(pd.NA, index=index, dtype="object")
    for date, target in targets.items():
        timestamp = pd.Timestamp(date)
        if timestamp not in assets.index:
            continue
        positive = target[target > 0.0]
        assets.loc[timestamp] = str(positive.idxmax()) if not positive.empty else "__cash__"
    return assets.ffill().fillna("__cash__")


def _build_phase_path(
    market: MarketDataBundle,
    base_config: ResearchConfig,
    spec: AuditSpec,
    *,
    schedule_start: pd.Timestamp,
    evaluation_start: pd.Timestamp,
    end_date: pd.Timestamp | None,
    cost_bps: float,
) -> pd.Series:
    local_config = base_config.model_copy(deep=True)
    local_config.start_date = schedule_start.date().isoformat()
    if end_date is not None:
        local_config.end_date = end_date.date().isoformat()

    schedule = get_rebalance_dates(
        market.price.index,
        schedule_start,
        spec.frequency,
        spec.frequency,
    )
    universe = build_rebalance_universe(market, schedule, local_config)
    built = build_ctrend_lite_targets(
        market,
        universe,
        local_config,
        top_n=spec.top_n,
        frequency=spec.frequency,
        score_family=spec.score_family,
        include_btc=False,
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
    returns = market.returns.loc[evaluation_start:end_date]
    assets = _target_asset_series(targets, market.price.index).reindex(returns.index)
    simulation = simulate_single_asset_targets(
        returns,
        assets,
        total_cost_bps=cost_bps,
    )
    return simulation.daily_returns


def _load_market(config: ResearchConfig) -> MarketDataBundle:
    panel = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "panel_daily.csv")
    metadata = pd.read_csv(
        config.resolve_path(config.paths.processed_dir) / "metadata.csv"
    ).set_index("coin_id")
    return prepare_market_data(panel, metadata, config)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--cost-bps", default="2,20")
    parser.add_argument("--tranche-counts", default="1,3,7,21")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/strategy_evidence_audit_2022"))
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
    market = _load_market(config)
    end_date = (
        pd.Timestamp(args.end_date).normalize()
        if args.end_date
        else pd.Timestamp(market.price.index.max()).normalize()
    )
    costs = tuple(float(item.strip()) for item in args.cost_bps.split(",") if item.strip())
    tranche_counts = _parse_ints(args.tranche_counts)
    spec = AuditSpec()

    phase_rows: list[dict[str, object]] = []
    path_by_cost_and_offset: dict[tuple[float, int], pd.Series] = {}
    for cost_bps in costs:
        for offset in range(DEFAULT_CYCLE_DAYS):
            local_start = start_date + pd.Timedelta(days=offset)
            path = _build_phase_path(
                market,
                config,
                spec,
                schedule_start=local_start,
                evaluation_start=start_date,
                end_date=end_date,
                cost_bps=cost_bps,
            )
            path_by_cost_and_offset[(cost_bps, offset)] = path
            metrics = _metrics_from_returns(path, config.annualization_days)
            phase_rows.append(
                {
                    "offset_days": offset,
                    "cost_bps": cost_bps,
                    **metrics,
                }
            )

    staggered_rows: list[dict[str, object]] = []
    for cost_bps in costs:
        paths = {
            offset: path_by_cost_and_offset[(cost_bps, offset)]
            for offset in range(DEFAULT_CYCLE_DAYS)
        }
        for tranche_count in tranche_counts:
            for shift in range(DEFAULT_CYCLE_DAYS):
                offsets = _phase_offsets(tranche_count, shift)
                combined = _combine_tranches(paths, offsets)
                staggered_rows.append(
                    {
                        "tranches": tranche_count,
                        "shift_days": shift,
                        "offsets": ",".join(map(str, offsets)),
                        "cost_bps": cost_bps,
                        **_metrics_from_returns(combined, config.annualization_days),
                    }
                )

    output_dir = ensure_dir(args.output_dir)
    phase_frame = pd.DataFrame(phase_rows)
    staggered_frame = pd.DataFrame(staggered_rows)
    phase_frame.to_csv(output_dir / "phase_scan.csv", index=False)
    staggered_frame.to_csv(output_dir / "staggered_robustness.csv", index=False)

    phase_summary = (
        phase_frame.groupby("cost_bps")["multiple"]
        .agg(["median", "min", "max"])
        .reset_index()
        .rename(columns={"median": "median_multiple", "min": "min_multiple", "max": "max_multiple"})
    )
    staggered_summary = (
        staggered_frame.groupby(["cost_bps", "tranches"])[["multiple", "sharpe", "max_drawdown"]]
        .agg(["median", "min", "max"])
        .reset_index()
    )
    staggered_summary.columns = [
        "_".join(str(part) for part in column if str(part))
        for column in staggered_summary.columns
    ]

    manifest = {
        "spec": asdict(spec),
        "window": {
            "start": start_date.date().isoformat(),
            "end": end_date.date().isoformat(),
        },
        "cost_bps": list(costs),
        "tranche_counts": list(tranche_counts),
        "cycle_days": DEFAULT_CYCLE_DAYS,
        "data": "data/processed/panel_daily.csv",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = "\n".join(
        [
            "# Strategy Evidence Audit — Rebalance Phase Sensitivity",
            "",
            "This report keeps the current signal, stop, BTC gate, universe, and costs fixed,",
            "and changes only the calendar phase. A robust 21-day rule should not depend on",
            "which day of the 21-day cycle starts the schedule.",
            "",
            "## Single-tranche phase scan",
            "",
            dataframe_to_markdown(phase_frame.sort_values(["cost_bps", "offset_days"])),
            "",
            "## Phase summary",
            "",
            dataframe_to_markdown(phase_summary),
            "",
            "## Staggered-basket robustness",
            "",
            dataframe_to_markdown(staggered_summary),
            "",
            "## Interpretation guardrail",
            "",
            "The best single phase is not the strategy. The median and worst phase are the",
            "decision-relevant statistics. The 21-tranche basket is phase invariant because",
            "every phase owns one equal-weight tranche; it is the honest robustness benchmark.",
            "",
        ]
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(phase_summary.to_string(index=False))
    print(staggered_summary.to_string(index=False))
    print(f"Wrote strategy evidence audit to {output_dir}")


if __name__ == "__main__":
    main()
