"""Validate a point-in-time Top20 daily momentum-event ensemble.

The ensemble combines three momentum-like CTREND-lite score families:
balanced, relative-strength, and breakout.  Every sleeve uses the same daily
event rule:

* score the point-in-time Top20 every day;
* keep the incumbent while it stays in the hold-rank band;
* switch only after the incumbent loses the band for one day, or when the
  challenger leads by at least the no-trade score gap;
* exit immediately if the incumbent leaves the current Top20;
* go to cash while BTC is below its 100-day moving average (confirmed for two
  days);
* scale the selected asset to a target volatility using trailing 60-day
  realized volatility, with gross exposure capped at 1.0.

The primary research candidate equal-weights the three score families and the
70% / 80% target-volatility sleeves.  It is intentionally reported alongside
parameter-sensitivity, membership, cost, yearly, and pre-2022 stress tables so
that a high full-sample return is not mistaken for a robust live strategy.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
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

from atlas20.backtest.single_asset import (  # noqa: E402
    SingleAssetWeightBacktestResult,
    simulate_single_asset_weight_targets,
)
from atlas20.config import ResearchConfig, load_config  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import (  # noqa: E402
    btc_above_moving_average,
    realized_volatility,
)
from atlas20.strategies.event_driven import (  # noqa: E402
    DailyEventSpec,
    build_daily_event_targets_from_scores,
    compute_daily_score_panel,
)
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)

from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


MOMENTUM_FAMILIES: tuple[str, ...] = (
    "ctrend_lite_balanced",
    "ctrend_lite_relative_strength",
    "ctrend_lite_breakout",
)
PRIMARY_SPEC = DailyEventSpec(
    min_hold_days=5,
    hold_rank=2,
    switch_score_gap=0.10,
    confirm_days=1,
    exit_on_universe_drop=True,
)
SENSITIVITY_SPECS: dict[str, DailyEventSpec] = {
    "primary_mh5_hr2_g10_c1": PRIMARY_SPEC,
    "loose_gap_mh5_hr2_g05_c1": DailyEventSpec(
        min_hold_days=5,
        hold_rank=2,
        switch_score_gap=0.05,
        confirm_days=1,
        exit_on_universe_drop=True,
    ),
    "wide_band_mh5_hr3_g05_c1": DailyEventSpec(
        min_hold_days=5,
        hold_rank=3,
        switch_score_gap=0.05,
        confirm_days=1,
        exit_on_universe_drop=True,
    ),
    "slow_mh10_hr2_g10_c1": DailyEventSpec(
        min_hold_days=10,
        hold_rank=2,
        switch_score_gap=0.10,
        confirm_days=1,
        exit_on_universe_drop=True,
    ),
}


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
    # The user's hard constraint is point-in-time Top20.  Do not expose this
    # as a tunable research parameter in this runner.
    config.universe.universe_size = 20
    config.universe.min_history_days = 90
    config.universe.min_daily_dollar_volume = 25_000_000.0

    panel = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "panel_daily.csv")
    metadata = pd.read_csv(
        config.resolve_path(config.paths.processed_dir) / "metadata.csv"
    ).set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    index = market.price.index[
        (market.price.index >= pd.Timestamp(start_date).normalize())
        & (market.price.index <= pd.Timestamp(end_date).normalize())
    ]
    universe = build_rebalance_universe(market, list(index), config)
    return config, market, universe, index


def _score_panels(
    market: MarketDataBundle,
    universe: pd.DataFrame,
    families: tuple[str, ...] = MOMENTUM_FAMILIES,
) -> dict[str, pd.DataFrame]:
    return {
        family: compute_daily_score_panel(
            market,
            universe,
            score_family=family,
            include_btc=False,
        )
        for family in families
    }


def _target_assets_from_scores(
    market: MarketDataBundle,
    score_panel: pd.DataFrame,
    config: ResearchConfig,
    spec: DailyEventSpec,
    index: pd.DatetimeIndex,
) -> pd.Series:
    built = build_daily_event_targets_from_scores(market, score_panel, config, spec)
    assets = pd.Series(pd.NA, index=index, dtype="object")
    for raw_date, target in built.targets.items():
        date = pd.Timestamp(raw_date)
        if date not in assets.index:
            continue
        positive = target[target > 0.0]
        assets.loc[date] = str(positive.idxmax()) if not positive.empty else "__cash__"
    return assets


def _vol_target_events(
    market: MarketDataBundle,
    target_assets: pd.Series,
    risk_on: pd.Series,
    *,
    target_volatility: float,
    vol_window: int,
) -> tuple[pd.Series, pd.Series]:
    """Create sparse target events for the drift-aware single-asset simulator.

    Exposure is set when the selected asset changes or when the BTC gate flips.
    Between those events the position is allowed to drift with price; the
    sleeve is not silently rebalanced back to target for free every day.
    """
    if target_volatility <= 0.0:
        raise ValueError("target_volatility must be positive")
    if vol_window < 2:
        raise ValueError("vol_window must be at least 2")

    volatility = realized_volatility(market.price, window=vol_window)
    assets = pd.Series(pd.NA, index=target_assets.index, dtype="object")
    weights = pd.Series(float("nan"), index=target_assets.index, dtype=float)
    current_asset: str | None = None

    for date in target_assets.index:
        raw_asset = target_assets.get(date, "")
        raw_asset = "" if pd.isna(raw_asset) else str(raw_asset)
        desired = raw_asset if bool(risk_on.get(date, True)) else ""
        if desired == (current_asset or ""):
            continue

        current_asset = desired or None
        assets.loc[date] = current_asset if current_asset is not None else "__cash__"
        if current_asset is None:
            weights.loc[date] = 0.0
            continue

        if current_asset in volatility.columns and date in volatility.index:
            daily_vol = float(volatility.at[date, current_asset])
        else:
            daily_vol = float("nan")
        weights.loc[date] = (
            min(1.0, target_volatility / daily_vol)
            if np.isfinite(daily_vol) and daily_vol > 0.0
            else 1.0
        )
    return assets, weights


def _simulate_sleeve(
    market: MarketDataBundle,
    target_assets: pd.Series,
    risk_on: pd.Series,
    *,
    target_volatility: float,
    vol_window: int,
) -> SingleAssetWeightBacktestResult:
    events_assets, events_weights = _vol_target_events(
        market,
        target_assets,
        risk_on,
        target_volatility=target_volatility,
        vol_window=vol_window,
    )
    return simulate_single_asset_weight_targets(
        market.returns.reindex(target_assets.index),
        events_assets,
        events_weights,
        total_cost_bps=0.0,
        missing_return_policy="error",
    )


def _net_returns(
    simulation: SingleAssetWeightBacktestResult,
    cost_bps: float,
) -> pd.Series:
    fee_rate = float(cost_bps) / 10_000.0
    return (1.0 - simulation.turnover * fee_rate) * (1.0 + simulation.daily_returns) - 1.0


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


def _build_sleeve_returns(
    market: MarketDataBundle,
    score_panels: dict[str, pd.DataFrame],
    config: ResearchConfig,
    index: pd.DatetimeIndex,
    *,
    specs: dict[str, DailyEventSpec],
    target_vols: tuple[float, ...],
    vol_window: int,
) -> dict[str, SingleAssetWeightBacktestResult]:
    risk_on = btc_above_moving_average(
        market.price,
        ma_window=100,
        confirm_days=2,
    ).reindex(index).fillna(True)
    results: dict[str, SingleAssetWeightBacktestResult] = {}
    for spec_name, spec in specs.items():
        for family, score_panel in score_panels.items():
            target_assets = _target_assets_from_scores(
                market,
                score_panel,
                config,
                spec,
                index,
            )
            for target_vol in target_vols:
                key = f"{spec_name}|{family}|tv{target_vol:.1f}"
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
    spec_name: str,
    families: tuple[str, ...] = MOMENTUM_FAMILIES,
    target_vols: tuple[float, ...] = (0.7, 0.8),
    cost_bps: float,
) -> pd.Series:
    columns = []
    for family in families:
        for target_vol in target_vols:
            key = f"{spec_name}|{family}|tv{target_vol:.1f}"
            columns.append(_net_returns(sleeve_results[key], cost_bps))
    return pd.concat(columns, axis=1).mean(axis=1)


def _write_report(
    output_dir: Path,
    *,
    summary: pd.DataFrame,
    spec_sensitivity: pd.DataFrame,
    membership_sensitivity: pd.DataFrame,
    stress: pd.DataFrame,
    yearly: pd.DataFrame,
) -> None:
    primary = summary[
        (summary["strategy"] == "momentum3_event_ensemble")
        & (summary["period"].isin(["full_2022_plus", "post_2023", "post_2024"]))
    ].copy()
    lines = [
        "# Point-in-Time Top20 Daily Momentum-Event Ensemble",
        "",
        "## Structure",
        "",
        "- Daily point-in-time Top20 universe; no Top50/Top100 expansion.",
        "- Three momentum-like CTREND-lite score families: balanced, relative strength, breakout.",
        "- Daily event rule: min hold 5 days, hold-rank band 2, 10% score gap, 1-day confirmation.",
        "- The incumbent is exited immediately if it leaves the current Top20.",
        "- BTC 100-day moving-average gate with 2-day confirmation.",
        "- 60-day realized-volatility target; primary sleeves use 70% and 80% target volatility.",
        "- Gross exposure is capped at 1.0; no shorting and no leverage.",
        "- Signals are generated at close and executed T+1.",
        "",
        "## Primary summary",
        "",
        dataframe_to_markdown(primary.sort_values(["period", "cost_bps"])),
        "",
        "## Event-spec sensitivity",
        "",
        dataframe_to_markdown(spec_sensitivity.sort_values(["cost_bps", "post_2024_multiple"], ascending=[True, False])),
        "",
        "## Strict Top20 membership sensitivity",
        "",
        dataframe_to_markdown(membership_sensitivity.sort_values(["cost_bps", "post_2024_multiple"], ascending=[True, False])),
        "",
        "## Pre-2022 stress check",
        "",
        dataframe_to_markdown(stress.sort_values(["cost_bps", "period"])),
        "",
        "## Yearly returns",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## External evidence",
        "",
        "- Han, Kang, Ryu, *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market*:",
        "  cross-sectional momentum is weak after realistic costs, while time-series momentum",
        "  is stronger and profits concentrate in large winners.",
        "  <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>",
        "- Yang, *Cryptocurrency market risk-managed momentum strategies*: volatility scaling",
        "  improved crypto momentum returns and Sharpe.",
        "  <https://doi.org/10.1016/j.frl.2025.107879>",
        "- Alpha Architect, *Destabilizing Rebalancing*: reviewing more often is not the same as",
        "  trading more often; no-trade bands reduce unnecessary turnover.",
        "  <https://alphaarchitect.com/destabilizing-rebalancing>",
        "- Man Group, *In Crypto We Trend*: volatility scaling can reduce pressure-period turnover",
        "  while preserving trend exposure.",
        "  <https://www.man.com/insights/in-crypto-we-trend>",
        "- Grobys et al., *Cryptocurrency momentum has (not) its moments*: large-cap momentum",
        "  can crash severely, and volatility management helps mitigate the crash risk.",
        "  <https://osuva.uwasa.fi/bitstream/handle/10024/20018/Osuva_Grobys_Kolari_Sandretto_Shahzad_%C3%84ij%C3%B6_2025.pdf?sequence=2>",
        "",
        "## Guardrails",
        "",
        "- The event-spec parameters were selected after a broad research sweep. The high",
        "  full-sample return is therefore not proof of a stable live edge.",
        "- The neighboring-spec table is mandatory: if only one exact parameter survives,",
        "  the candidate remains research-only.",
        "- The 100bps cost column is a stress test, not the user's expected cost.",
        "- Capacity, exchange outage, delisting, and regime-change risks remain.",
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
    parser.add_argument("--cost-bps", default="2,20,50,100")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/momentum_event_ensemble_2022"),
    )
    args = parser.parse_args()

    configure_logging("INFO")
    costs = _parse_floats(args.cost_bps)
    target_vols = _parse_floats(args.target_vols)

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.stress_start,
        end_date=args.end_date,
    )
    score_panels = _score_panels(market, universe)
    sleeve_results = _build_sleeve_returns(
        market,
        score_panels,
        config,
        index,
        specs=SENSITIVITY_SPECS,
        target_vols=target_vols,
        vol_window=args.vol_window,
    )

    output_dir = ensure_dir(args.output_dir)
    summary_rows: list[dict[str, object]] = []
    primary_returns: dict[float, pd.Series] = {}
    for cost_bps in costs:
        ensemble = _ensemble_returns(
            sleeve_results,
            spec_name="primary_mh5_hr2_g10_c1",
            target_vols=target_vols,
            cost_bps=cost_bps,
        )
        primary_returns[cost_bps] = ensemble
        for period_name, period_returns in (
            ("full_2022_plus", ensemble.loc[pd.Timestamp(args.start_date) :]),
            ("post_2023", ensemble.loc["2023-01-01":]),
            ("post_2024", ensemble.loc["2024-01-01":]),
        ):
            summary_rows.append(
                _summary_row(
                    "momentum3_event_ensemble",
                    period_returns,
                    cost_bps=cost_bps,
                    period=period_name,
                )
            )

    spec_rows: list[dict[str, object]] = []
    for spec_name in SENSITIVITY_SPECS:
        for cost_bps in costs:
            returns = _ensemble_returns(
                sleeve_results,
                spec_name=spec_name,
                target_vols=target_vols,
                cost_bps=cost_bps,
            )
            spec_rows.append(
                {
                    "spec": spec_name,
                    "cost_bps": cost_bps,
                    "full_multiple": _metrics_from_returns(
                        returns.loc[pd.Timestamp(args.start_date) :]
                    )["multiple"],
                    "post_2024_multiple": _metrics_from_returns(
                        returns.loc["2024-01-01":]
                    )["multiple"],
                }
            )
    spec_sensitivity = pd.DataFrame(spec_rows)

    # Rebuild only the primary spec with and without strict membership exit.
    membership_rows: list[dict[str, object]] = []
    risk_on = btc_above_moving_average(
        market.price,
        ma_window=100,
        confirm_days=2,
    ).reindex(index).fillna(True)
    for strict in (True, False):
        spec = DailyEventSpec(
            min_hold_days=5,
            hold_rank=2,
            switch_score_gap=0.10,
            confirm_days=1,
            exit_on_universe_drop=strict,
        )
        results: dict[str, SingleAssetWeightBacktestResult] = {}
        for family, score_panel in score_panels.items():
            target_assets = _target_assets_from_scores(
                market,
                score_panel,
                config,
                spec,
                index,
            )
            for target_vol in target_vols:
                results[f"{family}|tv{target_vol:.1f}"] = _simulate_sleeve(
                    market,
                    target_assets,
                    risk_on,
                    target_volatility=target_vol,
                    vol_window=args.vol_window,
                )
        for cost_bps in costs:
            columns = [
                _net_returns(results[f"{family}|tv{target_vol:.1f}"], cost_bps)
                for family in MOMENTUM_FAMILIES
                for target_vol in target_vols
            ]
            returns = pd.concat(columns, axis=1).mean(axis=1)
            membership_rows.append(
                {
                    "strict_top20_exit": strict,
                    "cost_bps": cost_bps,
                    "full_multiple": _metrics_from_returns(
                        returns.loc[pd.Timestamp(args.start_date) :]
                    )["multiple"],
                    "post_2024_multiple": _metrics_from_returns(
                        returns.loc["2024-01-01":]
                    )["multiple"],
                }
            )
    membership_sensitivity = pd.DataFrame(membership_rows)

    # Pre-2022 stress check: the same fixed rule, no parameter re-selection.
    stress_rows: list[dict[str, object]] = []
    stress_config = config.model_copy(deep=True)
    stress_config.start_date = args.stress_start
    stress_config.end_date = args.stress_end
    for cost_bps in costs:
        ensemble = _ensemble_returns(
            sleeve_results,
            spec_name="primary_mh5_hr2_g10_c1",
            target_vols=target_vols,
            cost_bps=cost_bps,
        ).loc[pd.Timestamp(args.stress_start) : pd.Timestamp(args.stress_end)]
        stress_rows.append(
            _summary_row(
                "momentum3_event_ensemble",
                ensemble,
                cost_bps=cost_bps,
                period="stress_2020_10_to_2021_12",
            )
        )
    stress = pd.DataFrame(stress_rows)

    yearly = pd.DataFrame(
        {
            f"{cost_bps:g}bps": _yearly_returns(primary_returns[cost_bps].loc[pd.Timestamp(args.start_date) :])
            for cost_bps in costs
        }
    )
    yearly.index.name = "year_end"

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "summary.csv", index=False)
    spec_sensitivity.to_csv(output_dir / "spec_sensitivity.csv", index=False)
    membership_sensitivity.to_csv(output_dir / "membership_sensitivity.csv", index=False)
    stress.to_csv(output_dir / "stress_test.csv", index=False)
    yearly.to_csv(output_dir / "yearly_returns.csv", index_label="year")
    for cost_bps in costs:
        primary_returns[cost_bps].rename(f"return_{cost_bps:g}bps").to_frame().to_csv(
            output_dir / f"returns_{cost_bps:g}bps.csv",
            index_label="date",
        )

    manifest = {
        "data": "data/processed/panel_daily.csv",
        "universe": "point-in-time Top20",
        "start": args.start_date,
        "end": args.end_date,
        "stress": [args.stress_start, args.stress_end],
        "families": list(MOMENTUM_FAMILIES),
        "event_spec": {
            "min_hold_days": PRIMARY_SPEC.min_hold_days,
            "hold_rank": PRIMARY_SPEC.hold_rank,
            "switch_score_gap": PRIMARY_SPEC.switch_score_gap,
            "confirm_days": PRIMARY_SPEC.confirm_days,
            "exit_on_universe_drop": PRIMARY_SPEC.exit_on_universe_drop,
        },
        "target_vols": list(target_vols),
        "vol_window": args.vol_window,
        "cost_bps": list(costs),
        "gate": "BTC >= 100D MA, confirm 2 days",
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
        spec_sensitivity=spec_sensitivity,
        membership_sensitivity=membership_sensitivity,
        stress=stress,
        yearly=yearly,
    )
    print(summary.to_string(index=False))
    print(f"Wrote momentum-event ensemble research to {output_dir}")


if __name__ == "__main__":
    main()
