"""Validate phase-invariant volatility-targeted exposure.

The inherited fixed-calendar champion is sensitive to its exact rebalance
phase, and its BTC gate is a local parameter spike.  This study keeps the
CTREND-lite leader selection but replaces the binary market gate with a
continuous, literature-supported risk control: exposure is scaled down toward
a target volatility and capped at 1.0.

Every cycle length is evaluated as an equal-weight basket of all calendar
phases.  The basket is invariant to the start phase.  Results are also split
into 2022-2024 and 2025-2026 to expose sample-specific performance.  The fast
single-asset simulator is drift-aware and is cross-checked against the
production engine semantics rather than assuming free daily rebalancing.
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

from atlas20.backtest.calendar import get_rebalance_dates
from atlas20.backtest.single_asset import simulate_single_asset_weight_targets
from atlas20.config import ResearchConfig, load_config
from atlas20.logging_utils import configure_logging, ensure_dir
from atlas20.reporting.report import dataframe_to_markdown
from atlas20.signals.risk import btc_above_moving_average, realized_volatility
from atlas20.strategies.convex_leader import build_ctrend_lite_targets
from atlas20.strategies.overlays import apply_daily_asset_stop_overlay, apply_daily_risk_overlay
from atlas20.universe.builder import (
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)

from scripts.run_strategy_evidence_audit import _combine_tranches, _metrics_from_returns
from scripts.run_trend_stop_champion import confirmed_above_ma


def _parse_ints(value: str) -> tuple[int, ...]:
    parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 1 for item in parsed):
        raise ValueError("Expected a non-empty list of positive integers")
    return parsed


def _parse_floats(value: str) -> tuple[float, ...]:
    parsed = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item <= 0.0 for item in parsed):
        raise ValueError("Expected a non-empty list of positive numbers")
    return parsed


def _volatility_target_variants(
    *,
    cycles: tuple[int, ...],
    target_vols: tuple[float, ...],
    vol_windows: tuple[int, ...],
    stop_modes: tuple[str, ...],
    gate_modes: tuple[str, ...] = ("none",),
) -> tuple[tuple[int, float, int, str, str], ...]:
    variants: list[tuple[int, float, int, str, str]] = []
    for cycle_days in cycles:
        for target_volatility in target_vols:
            for vol_window in vol_windows:
                for stop_mode in stop_modes:
                    for gate_mode in gate_modes:
                        variants.append(
                            (cycle_days, target_volatility, vol_window, stop_mode, gate_mode)
                        )
    return tuple(dict.fromkeys(variants))


def _apply_gate(
    targets: dict[pd.Timestamp, pd.Series],
    market: MarketDataBundle,
    gate_mode: str,
) -> dict[pd.Timestamp, pd.Series]:
    if gate_mode == "none":
        return targets
    windows = {"btc_ma50": 50, "btc_ma100": 100, "btc_ma200": 200}
    if gate_mode not in windows:
        raise ValueError(f"Unsupported gate mode: {gate_mode}")
    risk_on = btc_above_moving_average(
        market.price,
        ma_window=windows[gate_mode],
        confirm_days=2,
    )
    return apply_daily_risk_overlay(targets, risk_on)


def _exposure_series_for_targets(
    targets: dict[pd.Timestamp, pd.Series],
    price: pd.DataFrame,
    *,
    target_volatility: float,
    vol_window: int,
) -> pd.Series:
    """Return a capped exposure scalar for each scheduled target date."""
    volatility = realized_volatility(price, window=vol_window)
    exposure: dict[pd.Timestamp, float] = {}
    for raw_date, target in targets.items():
        date = pd.Timestamp(raw_date)
        positive = target[target > 0.0]
        scales: list[float] = []
        for asset in positive.index:
            asset_id = str(asset)
            if (
                asset_id in volatility.columns
                and date in volatility.index
                and pd.notna(volatility.loc[date, asset_id])
                and float(volatility.loc[date, asset_id]) > 0.0
            ):
                scales.append(target_volatility / float(volatility.loc[date, asset_id]))
        exposure[date] = min(1.0, sum(scales) / len(scales)) if scales else 1.0
    return pd.Series(exposure, dtype=float).sort_index()


def _target_event_series(
    targets: dict[pd.Timestamp, pd.Series],
    exposure: pd.Series,
    index: pd.DatetimeIndex,
) -> tuple[pd.Series, pd.Series]:
    """Return sparse target events for the drift-aware single-asset simulator.

    The old implementation forward-filled the target weight to every day.
    That made the fast simulator rebalance to a constant weight for free,
    which is not what the production engine does.  Here only signal dates are
    populated; the simulator holds and lets the weight drift between them.
    """
    assets = pd.Series(pd.NA, index=index, dtype="object")
    weights = pd.Series(float("nan"), index=index, dtype=float)
    for raw_date, target in targets.items():
        date = pd.Timestamp(raw_date)
        if date not in assets.index:
            continue
        positive = target[target > 0.0]
        if positive.empty:
            assets.loc[date] = "__cash__"
            weights.loc[date] = 0.0
        else:
            assets.loc[date] = str(positive.idxmax())
            weights.loc[date] = float(exposure.get(date, 1.0))
    return assets, weights


def _build_base_targets(
    market: MarketDataBundle,
    base_config: ResearchConfig,
    *,
    schedule_start: pd.Timestamp,
    cycle_days: int,
    end_date: pd.Timestamp | None,
    include_btc: bool,
    score_family: str,
) -> dict[pd.Timestamp, pd.Series]:
    local_config = base_config.model_copy(deep=True)
    local_config.start_date = schedule_start.date().isoformat()
    if end_date is not None:
        local_config.end_date = end_date.date().isoformat()
    frequency = f"{cycle_days}D"
    schedule = get_rebalance_dates(
        market.price.index,
        schedule_start,
        frequency,
        frequency,
    )
    universe = build_rebalance_universe(market, schedule, local_config)
    return build_ctrend_lite_targets(
        market,
        universe,
        local_config,
        top_n=1,
        frequency=frequency,
        score_family=score_family,
        include_btc=include_btc,
    ).targets


def _simulate_metrics(
    market: MarketDataBundle,
    targets: dict[pd.Timestamp, pd.Series],
    *,
    evaluation_start: pd.Timestamp,
    end_date: pd.Timestamp | None,
    target_volatility: float,
    vol_window: int,
    cost_bps: float,
    annualization_days: int,
) -> tuple[dict[str, float], pd.Series, float]:
    exposure = _exposure_series_for_targets(
        targets,
        market.price,
        target_volatility=target_volatility,
        vol_window=vol_window,
    )
    assets, weights = _target_event_series(targets, exposure, market.price.index)
    returns = market.returns.loc[evaluation_start:end_date]
    simulation = simulate_single_asset_weight_targets(
        returns,
        assets.reindex(returns.index),
        weights.reindex(returns.index),
        total_cost_bps=cost_bps,
    )
    metrics = _metrics_from_returns(simulation.daily_returns, annualization_days)
    years = max(len(simulation.daily_returns) / annualization_days, 1.0 / annualization_days)
    metrics["annualized_turnover"] = float(simulation.turnover.sum() / years)
    metrics["average_exposure"] = float(simulation.weights.mean())
    metrics["average_holdings"] = float(simulation.holdings.mean())
    return metrics, simulation.daily_returns, float(simulation.weights.mean())


def _slice_metrics(returns: pd.Series, start: str, end: str | None, annualization_days: int) -> dict[str, float]:
    sliced = returns.loc[start:end]
    return _metrics_from_returns(sliced, annualization_days)


def _rolling_window_summary(
    returns: pd.Series,
    *,
    window_days: int = 365,
    annualization_days: int = 365,
) -> dict[str, float]:
    """Summarize overlapping fixed-length windows of a daily return series."""
    clean = pd.to_numeric(returns, errors="coerce").replace([float("inf"), float("-inf")], float("nan")).fillna(0.0)
    if window_days < 1:
        raise ValueError("window_days must be positive")
    if len(clean) < window_days:
        return {
            "rolling_1y_median_multiple": float("nan"),
            "rolling_1y_worst_multiple": float("nan"),
            "rolling_1y_median_sharpe": float("nan"),
            "rolling_1y_worst_sharpe": float("nan"),
            "rolling_1y_worst_drawdown": float("nan"),
        }
    rows = [
        _metrics_from_returns(
            clean.iloc[end - window_days : end],
            annualization_days,
        )
        for end in range(window_days, len(clean) + 1)
    ]
    frame = pd.DataFrame(rows)
    return {
        "rolling_1y_median_multiple": float(frame["multiple"].median()),
        "rolling_1y_worst_multiple": float(frame["multiple"].min()),
        "rolling_1y_median_sharpe": float(frame["sharpe"].median()),
        "rolling_1y_worst_sharpe": float(frame["sharpe"].min()),
        "rolling_1y_worst_drawdown": float(frame["max_drawdown"].min()),
    }


def _write_report(output_dir: Path, summary: pd.DataFrame, score_family: str) -> None:
    score_family_label = score_family.removeprefix("ctrend_lite_")
    summary_20 = summary[summary["cost_bps"] == 20.0].copy()
    by_full = summary_20.sort_values("basket_multiple", ascending=False)
    by_test = summary_20.sort_values("test_multiple", ascending=False)
    lines = [
        "# Phase-Invariant Volatility-Target Validation",
        "",
        f"This study keeps CTREND-lite {score_family_label} top-1 selection and replaces the",
        "binary BTC gate with a capped volatility-target exposure. Every cycle is",
        "evaluated as an equal-weight basket of all calendar phases, so the result",
        "does not depend on a fixed start date. No leverage is allowed. The fast",
        "simulator lets weights drift between target events, matching the",
        "production engine instead of assuming free daily rebalancing.",
        "",
        "## External evidence",
        "",
        "- Moreira and Muir, *Volatility-Managed Portfolios*: scaling exposure by",
        "  realized volatility can improve risk-adjusted outcomes.",
        "  <https://doi.org/10.1111/jofi.12467>",
        "- Yang, *Cryptocurrency market risk-managed momentum strategies*:",
        "  volatility scaling improved crypto momentum Sharpe and returns.",
        "  <https://doi.org/10.1016/j.frl.2025.107879>",
        "- Man Group, *In Crypto We Trend*: volatility scaling can reduce",
        "  pressure-period turnover while preserving trend exposure.",
        "  <https://www.man.com/insights/in-crypto-we-trend>",
        "",
        "## Top candidates by full-period basket multiple at 20bps",
        "",
        dataframe_to_markdown(by_full.head(20)),
        "",
        "## Top candidates by 2025-2026 test multiple at 20bps",
        "",
        dataframe_to_markdown(by_test.head(20)),
        "",
        "## Interpretation guardrail",
        "",
        "A candidate is not promoted because of one phase or one full-sample",
        "maximum. The basket, train/test split, exposure level, and neighboring",
        "volatility windows must all be economically consistent.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--cycles", default="14,21")
    parser.add_argument("--target-vols", default="0.3,0.4,0.5,0.6,0.8")
    parser.add_argument("--vol-windows", default="30")
    parser.add_argument("--stop-modes", default="none,own75")
    parser.add_argument("--gate-modes", default="none")
    parser.add_argument("--cost-bps", default="2,20")
    parser.add_argument("--include-btc", action="store_true")
    parser.add_argument("--score-family", default="ctrend_lite_balanced")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_invariant_vol_target_2022"),
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
    cycles = _parse_ints(args.cycles)
    target_vols = _parse_floats(args.target_vols)
    vol_windows = _parse_ints(args.vol_windows)
    stop_modes = tuple(item.strip() for item in args.stop_modes.split(",") if item.strip())
    if any(mode not in {"none", "own75"} for mode in stop_modes):
        raise ValueError("stop-modes must be a subset of: none,own75")
    costs = _parse_floats(args.cost_bps)
    gate_modes = tuple(item.strip() for item in args.gate_modes.split(",") if item.strip())
    if any(mode not in {"none", "btc_ma50", "btc_ma100", "btc_ma200"} for mode in gate_modes):
        raise ValueError("gate-modes must be a subset of: none,btc_ma50,btc_ma100,btc_ma200")
    variants = _volatility_target_variants(
        cycles=cycles,
        target_vols=target_vols,
        vol_windows=vol_windows,
        stop_modes=stop_modes,
        gate_modes=gate_modes,
    )

    phase_rows: list[dict[str, object]] = []
    path_by_key: dict[tuple[int, float, int, str, str, float, int], pd.Series] = {}
    for cycle_days in cycles:
        for offset in range(cycle_days):
            schedule_start = start_date + pd.Timedelta(days=offset)
            base_targets = _build_base_targets(
                market,
                config,
                schedule_start=schedule_start,
                cycle_days=cycle_days,
                end_date=end_date,
                include_btc=args.include_btc,
                score_family=args.score_family,
            )
            stopped_targets = {
                "none": base_targets,
                "own75": apply_daily_asset_stop_overlay(
                    base_targets,
                    confirmed_above_ma(market.price, 75, 3),
                ),
            }
            for cycle, target_vol, vol_window, stop_mode, gate_mode in variants:
                if cycle != cycle_days:
                    continue
                gated_targets = _apply_gate(stopped_targets[stop_mode], market, gate_mode)
                for cost_bps in costs:
                    metrics, returns, _ = _simulate_metrics(
                        market,
                        gated_targets,
                        evaluation_start=start_date,
                        end_date=end_date,
                        target_volatility=target_vol,
                        vol_window=vol_window,
                        cost_bps=cost_bps,
                        annualization_days=config.annualization_days,
                    )
                    path_by_key[
                        (cycle, target_vol, vol_window, stop_mode, gate_mode, cost_bps, offset)
                    ] = returns
                    phase_rows.append(
                        {
                            "cycle_days": cycle,
                            "target_volatility": target_vol,
                            "vol_window": vol_window,
                            "stop_mode": stop_mode,
                            "gate_mode": gate_mode,
                            "offset_days": offset,
                            "cost_bps": cost_bps,
                            **metrics,
                        }
                    )

    phase_frame = pd.DataFrame(phase_rows)
    phase_summary = (
        phase_frame.groupby(
            ["cycle_days", "target_volatility", "vol_window", "stop_mode", "gate_mode", "cost_bps"],
            as_index=False,
        )
        .agg(
            phase_median_multiple=("multiple", "median"),
            phase_min_multiple=("multiple", "min"),
            phase_max_multiple=("multiple", "max"),
            phase_median_sharpe=("sharpe", "median"),
            phase_worst_drawdown=("max_drawdown", "min"),
            phase_median_exposure=("average_exposure", "median"),
            phase_median_turnover=("annualized_turnover", "median"),
        )
        .sort_values(["cost_bps", "phase_median_multiple"], ascending=[True, False])
    )

    basket_rows: list[dict[str, object]] = []
    basket_return_columns: dict[str, pd.Series] = {}
    for cycle, target_vol, vol_window, stop_mode, gate_mode in variants:
        for cost_bps in costs:
            paths = {
                offset: path_by_key[
                    (cycle, target_vol, vol_window, stop_mode, gate_mode, cost_bps, offset)
                ]
                for offset in range(cycle)
            }
            basket_returns = _combine_tranches(paths, list(range(cycle)))
            full_metrics = _metrics_from_returns(basket_returns, config.annualization_days)
            train_metrics = _slice_metrics(
                basket_returns,
                "2022-01-01",
                "2024-12-31",
                config.annualization_days,
            )
            test_metrics = _slice_metrics(
                basket_returns,
                "2025-01-01",
                end_date.date().isoformat(),
                config.annualization_days,
            )
            rolling_metrics = _rolling_window_summary(
                basket_returns,
                window_days=365,
                annualization_days=config.annualization_days,
            )
            column_name = (
                f"c{cycle}_tv{target_vol}_vw{vol_window}_{stop_mode}_{gate_mode}_"
                f"{int(cost_bps)}bps"
            )
            basket_return_columns[column_name] = basket_returns
            basket_rows.append(
                {
                    "cycle_days": cycle,
                    "target_volatility": target_vol,
                    "vol_window": vol_window,
                    "stop_mode": stop_mode,
                    "gate_mode": gate_mode,
                    "cost_bps": cost_bps,
                    "basket_multiple": full_metrics["multiple"],
                    "basket_cagr": full_metrics["cagr"],
                    "basket_sharpe": full_metrics["sharpe"],
                    "basket_max_drawdown": full_metrics["max_drawdown"],
                    "train_multiple": train_metrics["multiple"],
                    "train_sharpe": train_metrics["sharpe"],
                    "test_multiple": test_metrics["multiple"],
                    "test_sharpe": test_metrics["sharpe"],
                    "test_max_drawdown": test_metrics["max_drawdown"],
                    **rolling_metrics,
                }
            )
    basket_frame = pd.DataFrame(basket_rows)
    summary = basket_frame.merge(
        phase_summary,
        on=["cycle_days", "target_volatility", "vol_window", "stop_mode", "gate_mode", "cost_bps"],
        how="left",
    )

    output_dir = ensure_dir(args.output_dir)
    phase_frame.to_csv(output_dir / "phase_metrics.csv", index=False)
    summary.to_csv(output_dir / "variant_summary.csv", index=False)
    pd.DataFrame(basket_return_columns).to_csv(output_dir / "basket_returns.csv", index_label="date")
    manifest = {
        "window": {
            "start": start_date.date().isoformat(),
            "end": end_date.date().isoformat(),
        },
        "train_end": "2024-12-31",
        "test_start": "2025-01-01",
        "cycles": list(cycles),
        "target_vols": list(target_vols),
        "vol_windows": list(vol_windows),
        "stop_modes": list(stop_modes),
        "gate_modes": list(gate_modes),
        "cost_bps": list(costs),
        "include_btc": bool(args.include_btc),
        "score_family": args.score_family,
        "top_n": 1,
        "data": "data/processed/panel_daily.csv",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    _write_report(output_dir, summary, args.score_family)
    print(summary[summary["cost_bps"] == 20.0].to_string(index=False))
    print(f"Wrote phase-invariant volatility-target validation to {output_dir}")


if __name__ == "__main__":
    main()
