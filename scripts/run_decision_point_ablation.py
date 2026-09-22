"""Audit individual decision points in the current crypto strategy.

The existing fixed-start champion mixes several inherited rules:

* a 75-day own-trend stop with three-day confirmation;
* an 11-day BTC trailing-price gate with two-day confirmation;
* re-entry only on the next scheduled rebalance.

This script holds the point-in-time Top20 universe and CTREND-breakout
selection fixed, then changes one decision point at a time.  Every variant is
evaluated across all 21 calendar phases and as a fully staggered 21-tranche
basket, so a single lucky start date cannot drive the conclusion.

The output is a research audit, not an automatic parameter-selection process.
The stop-grid report is intentionally presented as a distribution: choosing
75/3 because it is the sample maximum would repeat the overfitting error this
repository is trying to avoid.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Literal

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
from atlas20.signals.risk import btc_above_moving_average, btc_above_trailing_price
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

from scripts.run_strategy_evidence_audit import (
    DEFAULT_CYCLE_DAYS,
    _combine_tranches,
    _metrics_from_returns,
    _target_asset_series,
)
from scripts.run_trend_stop_champion import confirmed_above_ma


OwnReentryMode = Literal["next_rebalance", "immediate"]
BtcGateKind = Literal["none", "trailing", "ma"]
BtcReentryMode = Literal["next_rebalance", "immediate"]


@dataclass(frozen=True)
class VariantSpec:
    """One strategy variant with a single changed decision point."""

    variant_id: str
    family: str
    own_stop_ma: int | None = None
    own_stop_confirm: int = 3
    own_reentry: OwnReentryMode = "next_rebalance"
    own_reentry_confirm: int = 1
    btc_gate: BtcGateKind = "none"
    btc_gate_window: int = 11
    btc_gate_confirm: int = 2
    btc_reentry: BtcReentryMode = "next_rebalance"


def _parse_costs(value: str) -> tuple[float, ...]:
    parsed = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 0.0 for item in parsed):
        raise ValueError("Expected a non-empty list of non-negative costs")
    return parsed


def _confirmed_exit(price: pd.DataFrame, window: int, confirm_days: int) -> pd.DataFrame:
    """Return a conservative confirmed-below-MA exit mask."""
    moving_average = price.rolling(window, min_periods=window).mean()
    below = (price < moving_average).where(moving_average.notna(), True)
    if confirm_days <= 1:
        return below
    return below.rolling(confirm_days, min_periods=confirm_days).sum() >= confirm_days


def _confirmed_reentry(price: pd.DataFrame, window: int, confirm_days: int) -> pd.DataFrame:
    """Return a confirmed-above-MA re-entry mask."""
    moving_average = price.rolling(window, min_periods=window).mean()
    above = (price > moving_average).where(moving_average.notna(), False)
    if confirm_days <= 1:
        return above
    return above.rolling(confirm_days, min_periods=confirm_days).sum() >= confirm_days


def apply_immediate_asset_stop_overlay(
    base_targets: dict[pd.Timestamp, pd.Series],
    exit_confirmed: pd.DataFrame,
    reentry_confirmed: pd.DataFrame,
) -> dict[pd.Timestamp, pd.Series]:
    """Exit and re-enter the selected asset without waiting for the next rebalance.

    The state machine is intentionally simple because the base target itself
    remains fixed between scheduled decisions.  It only changes cash/asset
    exposure for the currently selected coin.
    """
    if not base_targets:
        return {}

    normalized = {
        pd.Timestamp(date): target.fillna(0.0).clip(lower=0.0)
        for date, target in sorted(base_targets.items())
    }
    assets = sorted(
        {
            str(asset)
            for target in normalized.values()
            for asset in target.index
            if float(target.loc[asset]) > 0.0
        }
    )
    missing_assets = sorted(
        asset
        for asset in assets
        if asset not in exit_confirmed.columns or asset not in reentry_confirmed.columns
    )
    if missing_assets:
        raise ValueError(f"Immediate stop signals are missing assets: {missing_assets}")

    schedule_dates = set(normalized)
    all_dates = sorted(set(exit_confirmed.index) | set(reentry_confirmed.index) | schedule_dates)
    adjusted: dict[pd.Timestamp, pd.Series] = {}
    current_target: pd.Series | None = None
    blocked: set[str] = set()
    previous: pd.Series | None = None

    for raw_date in all_dates:
        date = pd.Timestamp(raw_date)
        if date in normalized:
            current_target = normalized[date].reindex(assets).fillna(0.0)
            blocked = {
                asset
                for asset, weight in current_target.items()
                if weight > 0.0
                and (
                    date not in exit_confirmed.index
                    or bool(exit_confirmed.loc[date, asset])
                )
            }
        elif current_target is not None:
            blocked.update(
                asset
                for asset, weight in current_target.items()
                if weight > 0.0
                and (
                    date not in exit_confirmed.index
                    or bool(exit_confirmed.loc[date, asset])
                )
            )
            blocked = {
                asset
                for asset in blocked
                if not (
                    date in reentry_confirmed.index
                    and bool(reentry_confirmed.loc[date, asset])
                )
            }

        if current_target is None:
            continue

        desired = current_target.copy()
        if blocked:
            desired.loc[desired.index.intersection(sorted(blocked))] = 0.0
        if desired.sum() > 0.0:
            desired = desired / desired.sum()
        else:
            desired = pd.Series(dtype=float)

        if date in schedule_dates or not _targets_equal(desired, previous):
            adjusted[date] = desired.copy()
        previous = desired.copy()

    return dict(sorted(adjusted.items(), key=lambda item: item[0]))


def _targets_equal(left: pd.Series | None, right: pd.Series | None) -> bool:
    if left is None or right is None:
        return False
    if left.empty and right.empty:
        return True
    index = left.index.union(right.index)
    return bool(
        (left.reindex(index).fillna(0.0) - right.reindex(index).fillna(0.0))
        .abs()
        .max()
        <= 1e-12
    )


def _risk_on_series(price: pd.DataFrame, spec: VariantSpec) -> pd.Series:
    if spec.btc_gate == "none":
        return pd.Series(True, index=price.index, name="no_btc_gate")
    if spec.btc_gate == "trailing":
        return btc_above_trailing_price(
            price,
            lookback_days=spec.btc_gate_window,
            confirm_days=spec.btc_gate_confirm,
        )
    if spec.btc_gate == "ma":
        return btc_above_moving_average(
            price,
            ma_window=spec.btc_gate_window,
            confirm_days=spec.btc_gate_confirm,
        )
    raise ValueError(f"Unsupported BTC gate: {spec.btc_gate}")


def _build_variant_targets(
    base_targets: dict[pd.Timestamp, pd.Series],
    price: pd.DataFrame,
    spec: VariantSpec,
) -> dict[pd.Timestamp, pd.Series]:
    if spec.own_stop_ma is None:
        stopped_targets = base_targets
    elif spec.own_reentry == "next_rebalance":
        trend_on = confirmed_above_ma(price, spec.own_stop_ma, spec.own_stop_confirm)
        stopped_targets = apply_daily_asset_stop_overlay(base_targets, trend_on)
    elif spec.own_reentry == "immediate":
        exit_confirmed = _confirmed_exit(price, spec.own_stop_ma, spec.own_stop_confirm)
        reentry_confirmed = _confirmed_reentry(
            price,
            spec.own_stop_ma,
            spec.own_reentry_confirm,
        )
        stopped_targets = apply_immediate_asset_stop_overlay(
            base_targets,
            exit_confirmed,
            reentry_confirmed,
        )
    else:
        raise ValueError(f"Unsupported own-stop re-entry mode: {spec.own_reentry}")

    risk_on = _risk_on_series(price, spec)
    return apply_daily_risk_overlay(
        stopped_targets,
        risk_on,
        immediate_reentry=spec.btc_reentry == "immediate",
    )


def _build_base_targets(
    market: MarketDataBundle,
    base_config: ResearchConfig,
    schedule_start: pd.Timestamp,
    end_date: pd.Timestamp | None,
) -> dict[pd.Timestamp, pd.Series]:
    local_config = base_config.model_copy(deep=True)
    local_config.start_date = schedule_start.date().isoformat()
    if end_date is not None:
        local_config.end_date = end_date.date().isoformat()
    schedule = get_rebalance_dates(
        market.price.index,
        schedule_start,
        "21D",
        "21D",
    )
    universe = build_rebalance_universe(market, schedule, local_config)
    built = build_ctrend_lite_targets(
        market,
        universe,
        local_config,
        top_n=1,
        frequency="21D",
        score_family="ctrend_lite_breakout",
        include_btc=False,
    )
    return built.targets


def _simulate_metrics(
    market: MarketDataBundle,
    targets: dict[pd.Timestamp, pd.Series],
    *,
    evaluation_start: pd.Timestamp,
    end_date: pd.Timestamp | None,
    cost_bps: float,
    annualization_days: int,
) -> tuple[dict[str, float], pd.Series]:
    returns = market.returns.loc[evaluation_start:end_date]
    assets = _target_asset_series(targets, market.price.index).reindex(returns.index)
    simulation = simulate_single_asset_targets(
        returns,
        assets,
        total_cost_bps=cost_bps,
    )
    metrics = _metrics_from_returns(simulation.daily_returns, annualization_days)
    years = max(len(simulation.daily_returns) / annualization_days, 1.0 / annualization_days)
    metrics["annualized_turnover"] = float(simulation.turnover.sum() / years)
    metrics["average_holdings"] = float(simulation.holdings.mean())
    return metrics, simulation.daily_returns


def _variant_specs() -> tuple[VariantSpec, ...]:
    specs: list[VariantSpec] = [
        VariantSpec("no_overlay", "core"),
        VariantSpec(
            "own_stop_only",
            "core",
            own_stop_ma=75,
            own_stop_confirm=3,
            btc_gate="none",
        ),
        VariantSpec(
            "btc_gate_only",
            "core",
            btc_gate="trailing",
            btc_gate_window=11,
            btc_gate_confirm=2,
        ),
        VariantSpec(
            "full_current",
            "core",
            own_stop_ma=75,
            own_stop_confirm=3,
            btc_gate="trailing",
            btc_gate_window=11,
            btc_gate_confirm=2,
        ),
        VariantSpec(
            "own_stop_immediate_reentry",
            "core",
            own_stop_ma=75,
            own_stop_confirm=3,
            own_reentry="immediate",
            own_reentry_confirm=1,
            btc_gate="none",
        ),
        VariantSpec(
            "btc_gate_immediate_reentry",
            "core",
            btc_gate="trailing",
            btc_gate_window=11,
            btc_gate_confirm=2,
            btc_reentry="immediate",
        ),
        VariantSpec(
            "full_immediate_reentry",
            "core",
            own_stop_ma=75,
            own_stop_confirm=3,
            own_reentry="immediate",
            own_reentry_confirm=1,
            btc_gate="trailing",
            btc_gate_window=11,
            btc_gate_confirm=2,
            btc_reentry="immediate",
        ),
    ]

    for gate_kind, window in (
        ("trailing", 11),
        ("ma", 20),
        ("ma", 50),
        ("ma", 65),
        ("ma", 100),
        ("ma", 200),
    ):
        specs.append(
            VariantSpec(
                f"gate_{gate_kind}{window}",
                "gate",
                own_stop_ma=75,
                own_stop_confirm=3,
                btc_gate=gate_kind,  # type: ignore[arg-type]
                btc_gate_window=window,
                btc_gate_confirm=2,
            )
        )

    for ma_window in (20, 50, 65, 75, 100, 150, 200):
        for confirm_days in (1, 2, 3):
            specs.append(
                VariantSpec(
                    f"stop_ma{ma_window}_c{confirm_days}",
                    "stop_grid",
                    own_stop_ma=ma_window,
                    own_stop_confirm=confirm_days,
                    btc_gate="trailing",
                    btc_gate_window=11,
                    btc_gate_confirm=2,
                )
            )

    for lookback in (5, 7, 10, 11, 14, 20, 30, 50, 65, 100, 200):
        specs.append(
            VariantSpec(
                f"trailing_lb{lookback}_c2",
                "trailing_grid",
                own_stop_ma=75,
                own_stop_confirm=3,
                btc_gate="trailing",
                btc_gate_window=lookback,
                btc_gate_confirm=2,
            )
        )

    for confirm_days in (1, 2, 3, 5):
        specs.append(
            VariantSpec(
                f"trailing_lb11_c{confirm_days}",
                "trailing_confirm",
                own_stop_ma=75,
                own_stop_confirm=3,
                btc_gate="trailing",
                btc_gate_window=11,
                btc_gate_confirm=confirm_days,
            )
        )
    return tuple(specs)


def _summarize_phase_rows(phase_frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        phase_frame.groupby(["family", "variant_id", "cost_bps"], as_index=False)
        .agg(
            phase_median_multiple=("multiple", "median"),
            phase_min_multiple=("multiple", "min"),
            phase_max_multiple=("multiple", "max"),
            phase_median_sharpe=("sharpe", "median"),
            phase_worst_drawdown=("max_drawdown", "min"),
            phase_median_turnover=("annualized_turnover", "median"),
            phase_median_holdings=("average_holdings", "median"),
        )
        .sort_values(["family", "variant_id", "cost_bps"])
    )
    return grouped


def _write_report(
    output_dir: Path,
    summary: pd.DataFrame,
    basket_frame: pd.DataFrame,
) -> None:
    core = summary[
        (summary["family"] == "core")
        & (summary["cost_bps"] == 20.0)
    ].sort_values("phase_median_multiple", ascending=False)
    gate = summary[
        (summary["family"] == "gate")
        & (summary["cost_bps"] == 20.0)
    ].sort_values("phase_median_multiple", ascending=False)
    stop_grid = summary[
        (summary["family"] == "stop_grid")
        & (summary["cost_bps"] == 20.0)
    ].sort_values("phase_median_multiple", ascending=False)
    trailing_grid = summary[
        (summary["family"] == "trailing_grid")
        & (summary["cost_bps"] == 20.0)
    ].sort_values("phase_median_multiple", ascending=False)
    trailing_confirm = summary[
        (summary["family"] == "trailing_confirm")
        & (summary["cost_bps"] == 20.0)
    ].sort_values("phase_median_multiple", ascending=False)
    basket = basket_frame.sort_values(["cost_bps", "family", "variant_id"])

    report_lines = [
        "# Decision-Point Ablation — Stop, BTC Gate, and Re-entry",
        "",
        "This audit changes one inherited decision at a time while keeping the",
        "point-in-time Top20 universe and CTREND-breakout top-1 selection fixed.",
        "Every variant is evaluated across all 21 rebalance phases and as a",
        "fully staggered 21-tranche basket. The basket is the phase-invariant",
        "benchmark; the phase median and minimum are the robustness statistics.",
        "",
        "## External evidence used to choose what to test",
        "",
        "- Han, Kang, Ryu: cross-sectional crypto momentum weakens after realistic",
        "  costs and holding-period fluctuations; time-series evidence is stronger.",
        "  <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>",
        "- Kaminski and Lo: stop-loss policies can improve return and reduce",
        "  volatility at longer sampling frequencies, but the result is regime dependent.",
        "  <https://doi.org/10.1016/j.finmar.2013.07.001>",
        "- Sadaqat and Butt: stop-loss momentum outperformed ordinary momentum",
        "  across 147 cryptocurrencies from 2015-01 through 2022-06.",
        "  <https://doi.org/10.1016/j.jbef.2023.100833>",
        "- Le and Ruthbah: crypto trend following is sensitive to moving-average",
        "  horizon and transaction costs; BTC performed best around 65 days, while",
        "  ETH and a large-cap non-BTC index performed better around 20 days.",
        "  <https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf>",
        "- Duarte: trailing stops with explicit re-entry thresholds produced mixed",
        "  results, but reduced losses in highly volatile markets.",
        "  <https://doi.org/10.24018/ejbmr.2022.7.3.1426>",
        "",
        "## Audit conclusion",
        "",
        "- The inherited 11-day/two-day BTC gate is a local parameter spike.",
        "  The 21-tranche basket returns 5.51x at 11 days, but 3.05x at 10 days",
        "  and 1.98x at 14 days; one-day and five-day confirmation return 2.20x",
        "  and 2.30x. It must not be treated as a validated production rule.",
        "- Immediate re-entry is rejected in this sample. Requiring the next",
        "  scheduled rebalance returns 5.51x, versus 1.49x when both the own stop",
        "  and BTC gate re-enter immediately.",
        "- The 75-day/three-day own stop sits inside a broad 50-100 day and",
        "  1-3 confirmation plateau. It is acceptable as a research setting but is",
        "  not uniquely optimal.",
        "- No variant in this audit is production-ready until the BTC gate is",
        "  replaced or independently validated.",
        "",
        "## Core ablations at 20bps",
        "",
        dataframe_to_markdown(core),
        "",
        "## BTC gate variants at 20bps",
        "",
        dataframe_to_markdown(gate),
        "",
        "## Own-stop grid at 20bps",
        "",
        dataframe_to_markdown(stop_grid),
        "",
        "## BTC trailing-lookback grid at 20bps",
        "",
        dataframe_to_markdown(trailing_grid),
        "",
        "## BTC 11-day gate confirmation grid at 20bps",
        "",
        dataframe_to_markdown(trailing_confirm),
        "",
        "## Fully staggered 21-tranche results",
        "",
        dataframe_to_markdown(basket),
        "",
        "## Interpretation guardrails",
        "",
        "- A variant is not promoted because it has the largest single-phase result.",
        "- The current 75-day/3-day stop and 11-day BTC gate are inherited rules;",
        "  this report tests whether they survive when separated from each other.",
        "- Immediate re-entry is not assumed to be better. It must survive costs,",
        "  turnover, and the phase-invariant basket comparison.",
        "- The stop grid is a distribution audit. Selecting the maximum would be",
        "  an overfit unless the result is supported by a broad parameter plateau.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--cost-bps", default="2,20")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/decision_point_ablation_2022"),
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
    costs = _parse_costs(args.cost_bps)
    specs = _variant_specs()

    phase_rows: list[dict[str, object]] = []
    path_by_key: dict[tuple[str, float, int], pd.Series] = {}
    for offset in range(DEFAULT_CYCLE_DAYS):
        schedule_start = start_date + pd.Timedelta(days=offset)
        base_targets = _build_base_targets(market, config, schedule_start, end_date)
        for spec in specs:
            targets = _build_variant_targets(base_targets, market.price, spec)
            for cost_bps in costs:
                metrics, returns = _simulate_metrics(
                    market,
                    targets,
                    evaluation_start=start_date,
                    end_date=end_date,
                    cost_bps=cost_bps,
                    annualization_days=config.annualization_days,
                )
                path_by_key[(spec.variant_id, cost_bps, offset)] = returns
                phase_rows.append(
                    {
                        "family": spec.family,
                        "variant_id": spec.variant_id,
                        "offset_days": offset,
                        "cost_bps": cost_bps,
                        **metrics,
                    }
                )

    phase_frame = pd.DataFrame(phase_rows)
    summary = _summarize_phase_rows(phase_frame)

    basket_rows: list[dict[str, object]] = []
    for spec in specs:
        for cost_bps in costs:
            paths = {
                offset: path_by_key[(spec.variant_id, cost_bps, offset)]
                for offset in range(DEFAULT_CYCLE_DAYS)
            }
            basket_returns = _combine_tranches(paths, list(range(DEFAULT_CYCLE_DAYS)))
            basket_metrics = _metrics_from_returns(
                basket_returns,
                config.annualization_days,
            )
            basket_rows.append(
                {
                    "family": spec.family,
                    "variant_id": spec.variant_id,
                    "cost_bps": cost_bps,
                    **basket_metrics,
                }
            )

    basket_frame = pd.DataFrame(basket_rows)
    output_dir = ensure_dir(args.output_dir)
    phase_frame.to_csv(output_dir / "phase_metrics.csv", index=False)
    summary.to_csv(output_dir / "variant_summary.csv", index=False)
    basket_frame.to_csv(output_dir / "staggered_basket.csv", index=False)
    manifest = {
        "window": {
            "start": start_date.date().isoformat(),
            "end": end_date.date().isoformat(),
        },
        "cost_bps": list(costs),
        "cycle_days": DEFAULT_CYCLE_DAYS,
        "variants": [asdict(spec) for spec in specs],
        "data": "data/processed/panel_daily.csv",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    _write_report(output_dir, summary, basket_frame)
    print(summary.to_string(index=False))
    print(basket_frame.to_string(index=False))
    print(f"Wrote decision-point ablation to {output_dir}")


if __name__ == "__main__":
    main()
