"""Production-engine validation for the phase-invariant Top20 momentum ensemble.

The strategy is intentionally constrained to the point-in-time Top20.  It
combines four transparent trailing-return signals with three calendar phases
per signal, keeps an incumbent while it remains in the Top2, and scales each
single-asset sleeve toward a target volatility without ever exceeding gross
exposure 1.0.  The report uses the production ``run_backtest`` engine rather
than a sleeve-return shortcut so execution timing, turnover, drift, and
missing-return handling match the rest of Atlas20.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.backtest.engine import BacktestResult, run_backtest  # noqa: E402
from atlas20.backtest.single_asset import simulate_single_asset_weight_targets  # noqa: E402
from atlas20.config import ResearchConfig, load_config  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    MomentumSignalSpec,
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    PRIMARY_SIGNAL_SPECS,
    build_phase_momentum_targets,
)
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)

from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def _parse_floats(value: str) -> tuple[float, ...]:
    parsed = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 0.0 for item in parsed):
        raise ValueError("Expected a non-empty list of non-negative numbers")
    return parsed


def _load_market(
    config_path: str,
    *,
    start_date: str,
    end_date: str,
) -> tuple[ResearchConfig, MarketDataBundle, pd.DataFrame, pd.DatetimeIndex]:
    config = load_config(config_path).model_copy(deep=True)
    config.start_date = start_date
    config.end_date = end_date
    # The Top20-only universe is a hard project constraint, not a tunable
    # research parameter.
    config.universe.universe_size = 20
    config.universe.min_history_days = 90
    config.universe.min_daily_dollar_volume = 25_000_000.0

    processed_dir = config.resolve_path(config.paths.processed_dir)
    panel = pd.read_csv(processed_dir / "panel_daily.csv")
    metadata = pd.read_csv(processed_dir / "metadata.csv").set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    index = market.price.index[
        (market.price.index >= pd.Timestamp(start_date).normalize())
        & (market.price.index <= pd.Timestamp(end_date).normalize())
    ]
    universe = build_rebalance_universe(market, list(index), config)
    return config, market, universe, index


def _production_result(
    config: ResearchConfig,
    market: MarketDataBundle,
    built: PhaseMomentumBuildResult,
    index: pd.DatetimeIndex,
    *,
    cost_bps: float,
) -> BacktestResult:
    """Run one candidate through the production engine at a total cost."""
    friction = config.frictions.model_copy(
        update={
            "fee_bps": float(cost_bps),
            "slippage_bps": 0.0,
            # The aggregate target already has gross exposure <= 1.0.  Raising
            # the per-coin cap avoids the engine's normalisation turning a
            # deliberate single-asset sleeve into a silent 35% cash position.
            "max_weight_per_coin": 1.0,
            "max_weight_per_sector": 1.0,
        }
    )
    sectors = market.metadata["sector"].reindex(market.returns.columns).fillna("Other")
    return run_backtest(
        f"phase_momentum_{cost_bps:g}bps",
        market.returns.loc[index],
        built.targets,
        sectors,
        friction,
        initial_capital=1.0,
        gross_target_exposure=1.0,
        leverage_by_date=built.exposures,
        max_gross_exposure=1.0,
    )


def _summary_row(
    strategy: str,
    returns: pd.Series,
    *,
    cost_bps: float,
    period: str,
) -> dict[str, object]:
    metrics = _metrics_from_returns(returns)
    return {
        "strategy": strategy,
        "cost_bps": float(cost_bps),
        "period": period,
        "start": returns.index.min(),
        "end": returns.index.max(),
        "days": len(returns),
        **metrics,
    }


def _rolling_worst(returns: pd.Series, window_days: int = 365) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if len(clean) < window_days:
        return {
            "rolling_1y_median_multiple": float("nan"),
            "rolling_1y_worst_multiple": float("nan"),
        }
    multiples = (1.0 + clean).rolling(window_days).apply(np.prod, raw=True).dropna()
    return {
        "rolling_1y_median_multiple": float(multiples.median()),
        "rolling_1y_worst_multiple": float(multiples.min()),
    }


def _yearly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).resample("YE").prod() - 1.0


def _variant_specs() -> dict[str, PhaseMomentumSpec]:
    base = PhaseMomentumSpec()
    return {
        "primary": base,
        "rebalance_1d": replace(base, rebalance_days=1, phase_offsets=(0,)),
        "rebalance_2d": replace(base, rebalance_days=2, phase_offsets=(0, 1)),
        "rebalance_5d": replace(base, rebalance_days=5, phase_offsets=(0, 1, 2, 3, 4)),
        "hold_rank_1": replace(base, hold_rank=1),
        "hold_rank_3": replace(base, hold_rank=3),
        "target_vol_0.6": replace(base, target_volatility=0.6),
        "target_vol_0.7": replace(base, target_volatility=0.7),
        "target_vol_0.9": replace(base, target_volatility=0.9),
        "target_vol_1.0": replace(base, target_volatility=1.0),
        "btc_ma_50": replace(base, btc_ma_window=50),
        "btc_ma_150": replace(base, btc_ma_window=150),
        "btc_ma_200": replace(base, btc_ma_window=200),
        "no_btc_gate": replace(base, use_btc_gate=False),
        "no_vol_target": replace(base, use_volatility_target=False),
        "fixed_stop_15": replace(base, stop_loss_kind="fixed", stop_loss_pct=0.15),
        "fixed_stop_20": replace(base, stop_loss_kind="fixed", stop_loss_pct=0.20),
        "fixed_stop_25": replace(base, stop_loss_kind="fixed", stop_loss_pct=0.25),
        "fixed_stop_30": replace(base, stop_loss_kind="fixed", stop_loss_pct=0.30),
        "fixed_stop_40": replace(base, stop_loss_kind="fixed", stop_loss_pct=0.40),
        "trailing_stop_15": replace(base, stop_loss_kind="trailing", stop_loss_pct=0.15),
        "trailing_stop_20": replace(base, stop_loss_kind="trailing", stop_loss_pct=0.20),
        "trailing_stop_25": replace(base, stop_loss_kind="trailing", stop_loss_pct=0.25),
        "trailing_stop_30": replace(base, stop_loss_kind="trailing", stop_loss_pct=0.30),
        "trailing_stop_40": replace(base, stop_loss_kind="trailing", stop_loss_pct=0.40),
        "asset_trend_50": replace(base, use_asset_trend_filter=True, asset_ma_window=50),
        "asset_trend_100": replace(base, use_asset_trend_filter=True, asset_ma_window=100),
        "asset_trend_150": replace(base, use_asset_trend_filter=True, asset_ma_window=150),
        "asset_trend_200": replace(base, use_asset_trend_filter=True, asset_ma_window=200),
    }


def _signal_variants() -> dict[str, tuple[MomentumSignalSpec, ...]]:
    return {
        "all_signals": PRIMARY_SIGNAL_SPECS,
        "weighted_multi_horizon": (PRIMARY_SIGNAL_SPECS[0],),
        "ret21": (PRIMARY_SIGNAL_SPECS[1],),
        "equal_7_14_28_60": (PRIMARY_SIGNAL_SPECS[2],),
        "equal_14_21_28": (PRIMARY_SIGNAL_SPECS[3],),
    }


def _parameter_sensitivity(
    config: ResearchConfig,
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    cost_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    return_columns: dict[str, pd.Series] = {}
    for name, spec in _variant_specs().items():
        built = build_phase_momentum_targets(market, universe, index, spec=spec)
        result = _production_result(config, market, built, index, cost_bps=cost_bps)
        rows.append(
            _summary_row(
                f"param_{name}",
                result.daily_returns,
                cost_bps=cost_bps,
                period="full_2022_plus",
            )
        )
        return_columns[name] = result.daily_returns.rename(name)
    return pd.DataFrame(rows), pd.DataFrame(return_columns)


def _signal_ablation(
    config: ResearchConfig,
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    *,
    cost_bps: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for name, signals in _signal_variants().items():
        built = build_phase_momentum_targets(
            market,
            universe,
            index,
            signal_specs=signals,
            spec=PhaseMomentumSpec(),
        )
        result = _production_result(config, market, built, index, cost_bps=cost_bps)
        rows.append(
            _summary_row(
                f"signal_{name}",
                result.daily_returns,
                cost_bps=cost_bps,
                period="full_2022_plus",
            )
        )
    return pd.DataFrame(rows)


def _monthly_start_sensitivity(
    config: ResearchConfig,
    market: MarketDataBundle,
    built: PhaseMomentumBuildResult,
    index: pd.DatetimeIndex,
    *,
    cost_bps: float,
) -> pd.DataFrame:
    starts = pd.date_range(index.min().normalize(), index.max().normalize(), freq="MS")
    rows: list[dict[str, object]] = []
    for start in starts:
        if start < index.min():
            continue
        sliced_index = index[index >= start]
        if len(sliced_index) < 90:
            continue
        result = _production_result(config, market, built, sliced_index, cost_bps=cost_bps)
        rows.append(
            {
                "start": sliced_index[0],
                **_metrics_from_returns(result.daily_returns),
            }
        )
    return pd.DataFrame(rows)


def _sleeve_metrics(
    market: MarketDataBundle,
    built: PhaseMomentumBuildResult,
    index: pd.DatetimeIndex,
    *,
    cost_bps: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sleeve in built.sleeve_targets:
        simulation = simulate_single_asset_weight_targets(
            market.returns.reindex(index),
            sleeve.assets,
            sleeve.weights,
            total_cost_bps=0.0,
            missing_return_policy="error",
        )
        net = (1.0 - simulation.turnover * float(cost_bps) / 10_000.0) * (
            1.0 + simulation.daily_returns
        ) - 1.0
        rows.append(
            {
                "signal_name": sleeve.signal_name,
                "phase_offset": sleeve.phase_offset,
                "cost_bps": float(cost_bps),
                **_metrics_from_returns(net),
            }
        )
    return pd.DataFrame(rows)


def _selection_summary(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame(columns=["signal_name", "phase_offset", "selected_asset", "days"])
    selected = history[history["selected_asset"].astype(str).ne("")].copy()
    if selected.empty:
        return pd.DataFrame(columns=["signal_name", "phase_offset", "selected_asset", "days"])
    return (
        selected.groupby(["signal_name", "phase_offset", "selected_asset"], dropna=False)
        .size()
        .rename("days")
        .reset_index()
        .sort_values(["signal_name", "phase_offset", "days"], ascending=[True, True, False])
    )


def _write_report(
    output_dir: Path,
    *,
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    rolling: pd.DataFrame,
    parameter: pd.DataFrame,
    signals: pd.DataFrame,
    monthly: pd.DataFrame,
    sleeve_metrics: pd.DataFrame,
    selection_summary: pd.DataFrame,
) -> None:
    primary = summary[summary["strategy"] == "phase_momentum"].copy()
    lines = [
        "# Phase-Invariant Top20 Momentum Ensemble",
        "",
        "## Design",
        "",
        "Strict point-in-time Top20, long-only spot, no leverage, gross exposure <= 1.0,",
        "close signal and T+1 execution. Four transparent trailing-return signals are",
        "each run in three calendar phases; the twelve sleeves are equal-weighted.",
        "An incumbent is held while it remains in the Top2 of its sleeve and is replaced",
        "only on that sleeve's scheduled check. If it leaves the current Top20, it exits",
        "immediately. BTC must be above its 100D moving average with two-day confirmation.",
        "Each sleeve is scaled to 80% annualized trailing volatility and capped at 1.0.",
        "The primary specification has no stop-loss or asset-level trend overlay; fixed stops,",
        "trailing stops, and absolute-trend filters are reported in the parameter neighborhood",
        "because the external evidence is strong but their incremental value must be",
        "established on this data before adoption.",
        "",
        "## Cost and benchmark summary",
        "",
        dataframe_to_markdown(primary.sort_values("cost_bps")),
        "",
        "## Yearly returns",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## Rolling one-year worst case",
        "",
        dataframe_to_markdown(rolling),
        "",
        "## Parameter neighborhood",
        "",
        dataframe_to_markdown(parameter.sort_values("multiple", ascending=False)),
        "",
        "## Signal-family ablation",
        "",
        dataframe_to_markdown(signals.sort_values("multiple", ascending=False)),
        "",
        "## Monthly start sensitivity",
        "",
        dataframe_to_markdown(
            monthly[
                [
                    "start",
                    "multiple",
                    "cagr",
                    "sharpe",
                    "max_drawdown",
                ]
            ]
            if not monthly.empty
            else monthly
        ),
        "",
        "## Sleeve contribution",
        "",
        dataframe_to_markdown(
            sleeve_metrics.sort_values(["multiple", "signal_name", "phase_offset"], ascending=[False, True, True])
        ),
        "",
        "## Most frequently selected assets",
        "",
        dataframe_to_markdown(selection_summary.head(40)),
        "",
        "## External evidence",
        "",
        "- Grobys et al. (2025), *Cryptocurrency momentum has (not) its moments*:",
        "  large-cap crypto momentum is crash-prone; volatility management mitigates",
        "  crashes but does not eliminate tail risk.",
        "  <https://osuva.uwasa.fi/bitstream/handle/10024/20018/Osuva_Grobys_Kolari_Sandretto_Shahzad_%C3%84ij%C3%B6_2025.pdf?sequence=2>",
        "- Sadaqat and Butt (2023), *Stop-loss rules and momentum payoffs in cryptocurrencies*:",
        "  stop-loss momentum outperformed benchmark momentum rules and improved risk",
        "  across market states in a 147-coin sample from 2015-2022.",
        "  <https://doi.org/10.1016/j.jbef.2023.100833>",
        "- Han, Kang, and Ryu, *Time-Series and Cross-Sectional Momentum in the",
        "  Cryptocurrency Market*: time-series momentum evidence is stronger than",
        "  cross-sectional momentum, and many momentum portfolios fail after realistic",
        "  costs and daily fluctuations. <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>",
        "- Gbadebo (2026), *Momentum Trading in Cryptocurrencies*: in a large-cap sample,",
        "  time-series momentum delivered a higher annual return and better risk-adjusted",
        "  performance than cross-sectional momentum. <https://doi.org/10.15388/batp.2026.1>",
        "",
        "## Guardrails",
        "",
        "- The 80% target volatility and 100D BTC gate are selected parameters; the",
        "  neighborhood table is part of the result, not a footnote.",
        "- The monthly-start table is an in-sample sensitivity check, not a substitute",
        "  for nested walk-forward validation.",
        "- This report does not yet establish capacity, delisting, exchange-outage, or",
        "  live execution safety. Those checks remain mandatory before production.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", default="2,20,50,100")
    parser.add_argument("--sensitivity-cost-bps", type=float, default=20.0)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_2022"))
    args = parser.parse_args()

    configure_logging("ERROR")
    costs = _parse_floats(args.cost_bps)
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    base_spec = PhaseMomentumSpec()
    built = build_phase_momentum_targets(market, universe, index, spec=base_spec)
    output_dir = ensure_dir(args.output_dir)

    summary_rows: list[dict[str, object]] = []
    yearly_frames: list[pd.DataFrame] = []
    rolling_rows: list[dict[str, object]] = []
    for cost in costs:
        result = _production_result(config, market, built, index, cost_bps=cost)
        summary_rows.append(
            _summary_row(
                "phase_momentum",
                result.daily_returns,
                cost_bps=cost,
                period="full_2022_plus",
            )
        )
        yearly = _yearly_returns(result.daily_returns).rename(f"phase_{cost:g}bps").to_frame()
        yearly_frames.append(yearly)
        rolling_rows.append(
            {
                "strategy": "phase_momentum",
                "cost_bps": float(cost),
                **_rolling_worst(result.daily_returns),
            }
        )

    btc_returns = market.returns["bitcoin"].reindex(index).fillna(0.0)
    summary_rows.append(
        _summary_row("BTC", btc_returns, cost_bps=0.0, period="full_2022_plus")
    )
    yearly_frames.append(_yearly_returns(btc_returns).rename("BTC").to_frame())
    rolling_rows.append({"strategy": "BTC", "cost_bps": 0.0, **_rolling_worst(btc_returns)})

    summary = pd.DataFrame(summary_rows)
    yearly = pd.concat(yearly_frames, axis=1)
    rolling = pd.DataFrame(rolling_rows)

    parameter, parameter_returns = _parameter_sensitivity(
        config,
        market,
        universe,
        index,
        cost_bps=args.sensitivity_cost_bps,
    )
    signals = _signal_ablation(
        config,
        market,
        universe,
        index,
        cost_bps=args.sensitivity_cost_bps,
    )
    monthly = _monthly_start_sensitivity(
        config,
        market,
        built,
        index,
        cost_bps=args.sensitivity_cost_bps,
    )
    sleeve_metrics = _sleeve_metrics(
        market,
        built,
        index,
        cost_bps=args.sensitivity_cost_bps,
    )
    selection_summary = _selection_summary(built.selection_history)

    summary.to_csv(output_dir / "summary.csv", index=False)
    yearly.to_csv(output_dir / "yearly.csv", index_label="date")
    rolling.to_csv(output_dir / "rolling_worst.csv", index=False)
    parameter.to_csv(output_dir / "parameter_neighborhood.csv", index=False)
    parameter_returns.to_csv(output_dir / "parameter_returns.csv", index_label="date")
    signals.to_csv(output_dir / "signal_ablation.csv", index=False)
    monthly.to_csv(output_dir / "monthly_start.csv", index=False)
    sleeve_metrics.to_csv(output_dir / "sleeve_metrics.csv", index=False)
    built.selection_history.to_csv(output_dir / "selection_history.csv", index=False)
    selection_summary.to_csv(output_dir / "selection_summary.csv", index=False)

    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "universe": "strict point-in-time Top20",
        "portfolio": "long-only spot, no leverage, gross exposure <= 1.0",
        "execution": "close signal, T+1 execution",
        "cost_bps": list(costs),
        "sensitivity_cost_bps": args.sensitivity_cost_bps,
        "primary_spec": {
            "rebalance_days": base_spec.rebalance_days,
            "phase_offsets": list(base_spec.phase_offsets),
            "hold_rank": base_spec.hold_rank,
            "btc_ma_window": base_spec.btc_ma_window,
            "btc_confirm_days": base_spec.btc_confirm_days,
            "target_volatility": base_spec.target_volatility,
            "vol_window": base_spec.vol_window,
            "use_btc_gate": base_spec.use_btc_gate,
            "use_volatility_target": base_spec.use_volatility_target,
            "stop_loss_kind": base_spec.stop_loss_kind,
            "stop_loss_pct": base_spec.stop_loss_pct,
            "use_asset_trend_filter": base_spec.use_asset_trend_filter,
            "asset_ma_window": base_spec.asset_ma_window,
        },
        "signal_names": [spec.name for spec in PRIMARY_SIGNAL_SPECS],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    _write_report(
        output_dir,
        summary=summary,
        yearly=yearly.reset_index(),
        rolling=rolling,
        parameter=parameter,
        signals=signals,
        monthly=monthly,
        sleeve_metrics=sleeve_metrics,
        selection_summary=selection_summary,
    )
    print(summary.to_string(index=False))
    print(f"Wrote phase-momentum report to {output_dir}")


if __name__ == "__main__":
    main()
