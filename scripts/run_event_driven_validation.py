"""Validate daily event-driven leader rotation against fixed calendars.

This script deliberately separates two questions:

1. Does checking the ranking every day help once turnover and costs are paid?
2. Which combination of minimum holding, hold-rank band, score gap, and
   confirmation is stable across rolling starts rather than only at the
   2022-01-01 starting point?

The final candidate is still expected to be reproduced with the general
backtest engine.  The fast single-asset simulator is used only to make the
large parameter grid computationally tractable.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.backtest.single_asset import simulate_single_asset_targets  # noqa: E402
from atlas20.config import load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import btc_above_trailing_price  # noqa: E402
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


DEFAULT_COSTS: tuple[float, ...] = (2.0, 5.0, 10.0, 20.0, 50.0)
FIXED_FREQUENCIES: tuple[str, ...] = ("1D", "3D", "7D", "14D", "21D", "28D", "42D", "63D")
MIN_HOLD_DAYS: tuple[int, ...] = (0, 3, 5, 10, 20)
HOLD_RANKS: tuple[int, ...] = (1, 2, 3, 5)
SCORE_GAPS: tuple[float, ...] = (0.0, 0.02, 0.05, 0.10)
CONFIRM_DAYS: tuple[int, ...] = (1, 2)


@dataclass(frozen=True)
class Variant:
    variant_id: str
    kind: str
    frequency: str | None = None
    immediate_reentry: bool = False
    min_hold_days: int | None = None
    hold_rank: int | None = None
    switch_score_gap: float | None = None
    confirm_days: int | None = None


def _parse_costs(value: str) -> tuple[float, ...]:
    costs = tuple(float(item) for item in value.split(",") if item.strip())
    if not costs:
        raise ValueError("At least one cost must be supplied")
    if any(cost < 0 for cost in costs):
        raise ValueError("Costs must be non-negative")
    return costs


def _path_metrics(returns: pd.Series, turnover: pd.Series, annualization_days: int = 365) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    clean_turnover = pd.to_numeric(turnover, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    periods = max(len(clean) - 1, 1)
    multiple = float((1.0 + clean).prod())
    total_return = multiple - 1.0
    cagr = multiple ** (annualization_days / periods) - 1.0 if multiple > 0 else -1.0
    volatility = float(clean.std(ddof=0) * math.sqrt(annualization_days))
    sharpe = float(clean.mean() * annualization_days / volatility) if volatility > 0 else 0.0
    equity = (1.0 + clean).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0
    annualized_turnover = float(clean_turnover.sum() * annualization_days / periods)
    return {
        "multiple": multiple,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "annualized_turnover": annualized_turnover,
    }


def _cost_adjusted_returns(gross_returns: pd.Series, turnover: pd.Series, total_cost_bps: float) -> pd.Series:
    fee_rate = float(total_cost_bps) / 10_000.0
    return (1.0 - turnover.astype(float) * fee_rate) * (1.0 + gross_returns.astype(float)) - 1.0


def _target_series_from_targets(
    targets: dict[pd.Timestamp, pd.Series],
    index: pd.DatetimeIndex,
) -> pd.Series:
    values: list[str] = []
    for date in index:
        target = targets.get(pd.Timestamp(date))
        if target is None or target.empty:
            values.append("")
            continue
        positive = target[target > 0.0]
        values.append(str(positive.idxmax()) if not positive.empty else "")
    return pd.Series(values, index=index, dtype="object")


def _scheduled_asset_series(
    score_panel: pd.DataFrame,
    schedule_dates: list[pd.Timestamp],
    index: pd.DatetimeIndex,
) -> pd.Series:
    schedule = {pd.Timestamp(date) for date in schedule_dates}
    current = ""
    values: list[str] = []
    for date in index:
        signal_date = pd.Timestamp(date)
        if signal_date in schedule:
            if signal_date in score_panel.index:
                scores = score_panel.loc[signal_date].dropna().sort_values(ascending=False)
                current = str(scores.index[0]) if not scores.empty else ""
            else:
                current = ""
        values.append(current)
    return pd.Series(values, index=index, dtype="object")


def _rank_stop_asset_series(
    base_assets: pd.Series,
    score_panel: pd.DataFrame,
    schedule_dates: set[pd.Timestamp],
    *,
    hold_rank: int,
    confirm_days: int,
    min_hold_days: int,
) -> pd.Series:
    """Apply a daily rank stop to a scheduled single-asset selection."""
    current = ""
    weak_days = 0
    held_days = 0
    values: list[str] = []
    for date in base_assets.index:
        signal_date = pd.Timestamp(date)
        if signal_date in schedule_dates:
            current = str(base_assets.loc[signal_date])
            weak_days = 0
            held_days = 0
        elif current:
            if signal_date in score_panel.index:
                scores = score_panel.loc[signal_date].dropna().sort_values(ascending=False)
                if current in scores.index:
                    rank = int(scores.index.get_loc(current)) + 1
                    weak = rank > hold_rank
                else:
                    weak = True
            else:
                weak = True
            weak_days = weak_days + 1 if weak else 0
            if weak_days >= confirm_days and held_days >= min_hold_days:
                current = ""
                weak_days = 0
        values.append(current)
        if current:
            held_days += 1
    return pd.Series(values, index=base_assets.index, dtype="object")


def _risk_gate_asset_series(
    base_assets: pd.Series,
    risk_on: pd.Series,
    *,
    immediate_reentry: bool,
    schedule_dates: set[pd.Timestamp] | None = None,
) -> pd.Series:
    """Apply the BTC gate to a single-asset target path.

    The original champion exits on a risk-off flip and waits for the next
    scheduled rebalance before re-entry.  ``immediate_reentry`` isolates the
    separate question of whether the daily strategy should re-enter as soon as
    the BTC gate turns back on.
    """
    effective: list[str] = []
    last_base = ""
    blocked = False
    previous_risk_on: bool | None = None
    for date in base_assets.index:
        current_date = pd.Timestamp(date)
        base = str(base_assets.loc[current_date])
        if base:
            last_base = base
        risk = bool(risk_on.get(current_date, True))
        if previous_risk_on is None:
            previous_risk_on = risk
        if not risk:
            effective.append("")
            blocked = True
        else:
            flipped_on = not bool(previous_risk_on)
            if blocked and immediate_reentry and flipped_on:
                effective.append(last_base)
                blocked = False
            elif blocked:
                # A non-immediate path can only re-enter on a base schedule
                # change.  The base series already carries the schedule state.
                effective.append("")
            else:
                effective.append(base)
        if base and (not blocked or (immediate_reentry and risk)):
            # Base changes are the only scheduled re-entry event for the
            # non-immediate path.  Clearing the block here would incorrectly
            # re-enter on a daily risk-on flip.
            pass
        previous_risk_on = risk
    result = pd.Series(effective, index=base_assets.index, dtype="object")
    if not immediate_reentry:
        # Re-enter only on an actual scheduled selection date while risk is on.
        # Comparing adjacent base values is not enough: a schedule can select
        # the same coin as the previous schedule, but it is still a valid
        # re-entry event under the original champion rule.
        schedule = {pd.Timestamp(date) for date in (schedule_dates or set())}
        current = ""
        for date in result.index:
            risk = bool(risk_on.get(date, True))
            if not risk:
                current = ""
            elif pd.Timestamp(date) in schedule and str(base_assets.loc[date]):
                current = str(base_assets.loc[date])
            result.loc[date] = current
    return result


def _build_variants() -> list[Variant]:
    variants: list[Variant] = []
    for frequency in FIXED_FREQUENCIES:
        variants.append(
            Variant(
                variant_id=f"fixed_{frequency}_wait",
                kind="fixed",
                frequency=frequency,
                immediate_reentry=False,
            )
        )
        variants.append(
            Variant(
                variant_id=f"fixed_{frequency}_immediate",
                kind="fixed",
                frequency=frequency,
                immediate_reentry=True,
            )
        )
    for min_hold in MIN_HOLD_DAYS:
        for hold_rank in HOLD_RANKS:
            for score_gap in SCORE_GAPS:
                for confirm_days in CONFIRM_DAYS:
                    gap_label = f"{score_gap:g}".replace(".", "p")
                    variants.append(
                        Variant(
                            variant_id=(
                                f"event_mh{min_hold}_hr{hold_rank}_gap{gap_label}_c{confirm_days}"
                            ),
                            kind="event",
                            min_hold_days=min_hold,
                            hold_rank=hold_rank,
                            switch_score_gap=score_gap,
                            confirm_days=confirm_days,
                            immediate_reentry=True,
                        )
                    )
    # Hybrid family: keep the 21-day selection calendar, but monitor the
    # incumbent's rank every day and exit to cash after a confirmed fall out
    # of the hold-rank band.  Re-entry waits for the next scheduled date.
    for hold_rank in HOLD_RANKS:
        for confirm_days in (1, 2, 3):
            for min_hold in (0, 5, 10):
                variants.append(
                    Variant(
                        variant_id=f"rankstop_21D_hr{hold_rank}_c{confirm_days}_mh{min_hold}",
                        kind="rank_stop",
                        frequency="21D",
                        immediate_reentry=False,
                        min_hold_days=min_hold,
                        hold_rank=hold_rank,
                        confirm_days=confirm_days,
                    )
                )
    return variants


def _variant_asset_series(
    market: MarketDataBundle,
    score_panel: pd.DataFrame,
    risk_on: pd.Series,
    config,
    variant: Variant,
) -> pd.Series:
    start = pd.Timestamp(config.start_timestamp).normalize()
    end = pd.Timestamp(config.end_timestamp).normalize()
    index = market.price.index[(market.price.index >= start) & (market.price.index <= end)]
    if index.empty:
        return pd.Series(dtype="object")

    schedule: list[pd.Timestamp] | None = None
    risk_series = risk_on.reindex(index).fillna(True)
    if variant.kind in {"fixed", "rank_stop"}:
        assert variant.frequency is not None
        schedule = get_rebalance_dates(
            market.price.index,
            start,
            variant.frequency,
            variant.frequency,
        )
        base = _scheduled_asset_series(score_panel, schedule, index)
        if variant.kind == "rank_stop":
            schedule_set = {pd.Timestamp(date) for date in schedule}
            # Apply the market gate first, then let the daily rank stop create
            # cash periods between scheduled selection dates.  Reversing this
            # order would let the scheduled calendar overwrite every daily
            # rank-stop exit.
            base = _risk_gate_asset_series(
                base,
                risk_series,
                immediate_reentry=False,
                schedule_dates=schedule_set,
            )
            base = _rank_stop_asset_series(
                base,
                score_panel,
                schedule_set,
                hold_rank=int(variant.hold_rank),
                confirm_days=int(variant.confirm_days),
                min_hold_days=int(variant.min_hold_days),
            )
            return base
    elif variant.kind == "event":
        spec = DailyEventSpec(
            min_hold_days=int(variant.min_hold_days),
            hold_rank=int(variant.hold_rank),
            switch_score_gap=float(variant.switch_score_gap),
            confirm_days=int(variant.confirm_days),
        )
        built = build_daily_event_targets_from_scores(market, score_panel, config, spec)
        base = _target_series_from_targets(built.targets, index)
    else:
        raise ValueError(f"Unknown variant kind: {variant.kind}")

    return _risk_gate_asset_series(
        base,
        risk_series,
        immediate_reentry=variant.immediate_reentry,
        schedule_dates={pd.Timestamp(date) for date in schedule} if schedule else None,
    )


def _simulate_variant(
    market: MarketDataBundle,
    score_panel: pd.DataFrame,
    risk_on: pd.Series,
    config,
    variant: Variant,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    assets = _variant_asset_series(market, score_panel, risk_on, config, variant)
    returns = market.returns.reindex(index=assets.index)
    simulation = simulate_single_asset_targets(
        returns,
        assets,
        total_cost_bps=0.0,
        missing_return_policy="fill",
        missing_return_fill=0.0,
    )
    return assets, simulation.daily_returns, simulation.turnover


def _monthly_start_dates(index: pd.DatetimeIndex, start: pd.Timestamp, min_days_after_start: int = 365) -> list[pd.Timestamp]:
    if index.empty:
        return []
    max_date = pd.Timestamp(index.max())
    max_start = max_date - pd.Timedelta(days=min_days_after_start)
    starts = pd.date_range(start, max_start, freq="MS")
    aligned: list[pd.Timestamp] = []
    for candidate in starts:
        usable = index[index >= candidate]
        if not usable.empty and usable[0] <= max_start:
            aligned.append(pd.Timestamp(usable[0]))
    return list(dict.fromkeys(aligned))


def _rolling_summary_multi(
    market: MarketDataBundle,
    score_panel: pd.DataFrame,
    risk_on: pd.Series,
    base_config,
    variant: Variant,
    *,
    cost_bps_values: tuple[float, ...],
) -> dict[str, float]:
    start_dates = _monthly_start_dates(
        market.price.index,
        pd.Timestamp(base_config.start_timestamp),
        min_days_after_start=365,
    )
    rows_by_cost: dict[float, list[dict[str, float]]] = {cost: [] for cost in cost_bps_values}
    for start_date in start_dates:
        local = base_config.model_copy(deep=True)
        local.start_date = start_date.date().isoformat()
        _, gross, turnover = _simulate_variant(market, score_panel, risk_on, local, variant)
        for cost in cost_bps_values:
            rows_by_cost[cost].append(
                _path_metrics(_cost_adjusted_returns(gross, turnover, cost), turnover)
            )

    output: dict[str, float] = {}
    for cost, rows in rows_by_cost.items():
        prefix = f"rolling{cost:g}"
        if not rows:
            output.update(
                {
                    f"{prefix}_rolling_start_count": 0.0,
                    f"{prefix}_median_rolling_start_multiple": 0.0,
                    f"{prefix}_worst_rolling_start_multiple": 0.0,
                    f"{prefix}_best_rolling_start_multiple": 0.0,
                    f"{prefix}_median_rolling_start_drawdown": 0.0,
                    f"{prefix}_worst_rolling_start_drawdown": 0.0,
                }
            )
            continue
        frame = pd.DataFrame(rows)
        output.update(
            {
                f"{prefix}_rolling_start_count": float(len(frame)),
                f"{prefix}_median_rolling_start_multiple": float(frame["multiple"].median()),
                f"{prefix}_worst_rolling_start_multiple": float(frame["multiple"].min()),
                f"{prefix}_best_rolling_start_multiple": float(frame["multiple"].max()),
                f"{prefix}_median_rolling_start_drawdown": float(frame["max_drawdown"].median()),
                f"{prefix}_worst_rolling_start_drawdown": float(frame["max_drawdown"].min()),
            }
        )
    return output


def _variant_row(
    variant: Variant,
    metrics_by_cost: dict[float, dict[str, float]],
    screen_stats: dict[str, float],
) -> dict[str, object]:
    row: dict[str, object] = {
        **asdict(variant),
        "full_multiple_2bps": metrics_by_cost[2.0]["multiple"],
        "full_cagr_2bps": metrics_by_cost[2.0]["cagr"],
        "full_sharpe_2bps": metrics_by_cost[2.0]["sharpe"],
        "full_max_drawdown_2bps": metrics_by_cost[2.0]["max_drawdown"],
        "full_multiple_20bps": metrics_by_cost[20.0]["multiple"],
        "full_cagr_20bps": metrics_by_cost[20.0]["cagr"],
        "full_sharpe_20bps": metrics_by_cost[20.0]["sharpe"],
        "full_max_drawdown_20bps": metrics_by_cost[20.0]["max_drawdown"],
        "full_annualized_turnover": metrics_by_cost[2.0]["annualized_turnover"],
        **screen_stats,
    }
    for cost in (5.0, 10.0, 50.0):
        row[f"full_multiple_{cost:g}bps"] = metrics_by_cost[cost]["multiple"]
    return row


def _rolling_window_screen(returns: pd.Series, window_days: int = 365) -> dict[str, float]:
    """Cheap all-start screen using overlapping 1-year windows of the full path."""
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if clean.empty or len(clean) < window_days:
        return {
            "rolling_1y_window_count": 0.0,
            "rolling_1y_median_multiple": 0.0,
            "rolling_1y_worst_multiple": 0.0,
            "rolling_1y_best_multiple": 0.0,
        }
    gross = 1.0 + clean
    multiples = gross.rolling(window_days).apply(np.prod, raw=True).dropna()
    return {
        "rolling_1y_window_count": float(len(multiples)),
        "rolling_1y_median_multiple": float(multiples.median()),
        "rolling_1y_worst_multiple": float(multiples.min()),
        "rolling_1y_best_multiple": float(multiples.max()),
    }


def _yearly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).resample("YE").prod() - 1.0


def _write_report(
    output_dir: Path,
    summary: pd.DataFrame,
    btc_metrics: dict[str, float],
    yearly: pd.DataFrame,
    best_variant: Variant,
    best_assets: pd.Series,
    best_history: pd.DataFrame | None,
) -> None:
    fixed = summary[summary["kind"] == "fixed"].sort_values("rolling_1y_median_multiple", ascending=False)
    event = summary[summary["kind"] == "event"].sort_values("rolling_1y_median_multiple", ascending=False)
    rank_stop = summary[summary["kind"] == "rank_stop"].sort_values(
        "rolling_1y_median_multiple", ascending=False
    )
    top_event = event.head(20)
    fixed_table = fixed[
        [
            "variant_id",
            "full_multiple_2bps",
            "full_multiple_20bps",
            "full_cagr_20bps",
            "full_sharpe_20bps",
            "full_max_drawdown_20bps",
            "full_annualized_turnover",
            "rolling20_median_rolling_start_multiple",
            "rolling20_worst_rolling_start_multiple",
        ]
    ]
    table_columns = [
        "variant_id",
        "full_multiple_2bps",
        "full_multiple_20bps",
        "full_cagr_20bps",
        "full_sharpe_20bps",
        "full_max_drawdown_20bps",
        "full_annualized_turnover",
        "rolling_1y_median_multiple",
        "rolling_1y_worst_multiple",
        "rolling20_median_rolling_start_multiple",
        "rolling20_worst_rolling_start_multiple",
        "rolling20_worst_rolling_start_drawdown",
    ]
    event_table = top_event[table_columns]
    rank_stop_table = rank_stop.head(20)[table_columns]
    lines = [
        "# Daily Event-Driven Rotation Validation",
        "",
        "## Research question",
        "",
        "The previous champion only asked for a new leader every 21 days. This run tests daily",
        "ranking with hysteresis: the incumbent is kept while it stays inside a hold-rank band,",
        "and a switch requires either a confirmed rank deterioration or a challenger score gap.",
        "",
        "All results are long-only, no leverage, T+1 execution, point-in-time Top-20, and use the",
        "same BTC 11-day trailing gate with two-day confirmation as the champion.",
        "",
        "## External evidence used to set the research direction",
        "",
        "- Han, Kang, Ryu, *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market*:",
        "  after realistic costs and daily marking, cross-sectional momentum is weak, time-series",
        "  momentum is stronger, and momentum profits concentrate in large winners.",
        "  <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>",
        "- Yang, *Cryptocurrency market risk-managed momentum strategies*: risk scaling improved",
        "  weekly return and Sharpe in crypto, with return enhancement rather than only downside protection.",
        "  <https://doi.org/10.1016/j.frl.2025.107879>",
        "- Kaya and Mostowfi, *Low-volatility strategies for highly liquid cryptocurrencies*: a simple",
        "  stop-loss rule materially reduced downside risk and improved Sharpe.",
        "  <https://doi.org/10.1016/j.frl.2021.102422>",
        "- Alpha Architect tolerance-band research: reviewing more often is not the same as trading",
        "  more often; a no-trade band reduced unnecessary trades.",
        "  <https://alphaarchitect.com/destabilizing-rebalancing>",
        "- Industry hysteresis implementation notes: enter above a high threshold, exit below a lower",
        "  one, so small rank wobbles do not flip the portfolio.",
        "  <https://aligrithm.com/percentile-rank-momentum-with-hysteresis-low-churn-signals>",
        "",
        "## Method",
        "",
        "- Daily point-in-time Top-20 snapshots are rebuilt from CMC market-cap data.",
        "- CTREND-breakout scores are computed daily for the eligible universe.",
        "- Fixed calendars are compared at 1/3/7/14/21/28/42/63 days.",
        "- Event variants sweep minimum holding days, hold-rank bands, score gaps, and confirmation days.",
        "- Costs are charged on actual target changes; a full switch has turnover 2.",
        "- Rolling starts are monthly, with at least one year of remaining history.",
        "",
        "## Fixed-calendar comparison",
        "",
        dataframe_to_markdown(fixed_table),
        "",
        "## Top daily-event variants by rolling-start median",
        "",
        dataframe_to_markdown(event_table),
        "",
        "## Hybrid 21-day selection + daily rank-stop exits",
        "",
        dataframe_to_markdown(rank_stop_table),
        "",
        "## Selected event candidate",
        "",
        f"- Variant: `{best_variant.variant_id}`",
        f"- Minimum hold: {best_variant.min_hold_days} days",
        f"- Hold-rank band: top {best_variant.hold_rank}",
        f"- Score gap: {best_variant.switch_score_gap:.2%}",
        f"- Confirmation: {best_variant.confirm_days} day(s)",
        f"- Latest target: `{best_assets.iloc[-1] if not best_assets.empty else ''}`",
        "",
        "## Yearly returns for selected candidate",
        "",
        dataframe_to_markdown(yearly.reset_index()),
        "",
        "## BTC benchmark",
        "",
        f"- BTC 2bps multiple: {btc_metrics['multiple']:.2f}x",
        f"- BTC CAGR: {btc_metrics['cagr']:.2%}",
        f"- BTC Sharpe: {btc_metrics['sharpe']:.3f}",
        f"- BTC max drawdown: {btc_metrics['max_drawdown']:.2%}",
        "",
        "## Interpretation guardrails",
        "",
        "- A higher full-window multiple is not sufficient; the rolling-start median and worst",
        "  start must improve together with cost survival.",
        "- Daily checking is not automatically better. It is only useful if the trigger avoids",
        "  noise trades and the added reaction speed compensates for the extra turnover.",
        "- These results are historical simulations, not a live-trading guarantee.",
    ]
    (output_dir / "event_driven_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if best_history is not None:
        best_history.to_csv(output_dir / "selected_event_selection_history.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output-dir", default="reports/event_driven_validation_2022")
    parser.add_argument("--score-family", default="ctrend_lite_breakout")
    parser.add_argument("--costs", default="2,5,10,20,50")
    parser.add_argument("--quick", action="store_true", help="Run a smaller event grid for smoke testing")
    parser.add_argument(
        "--rebuild-data",
        action="store_true",
        help="Rebuild the in-memory panel from raw caches instead of using data/processed",
    )
    args = parser.parse_args()

    config = load_config(args.config).model_copy(deep=True)
    config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    configure_logging(config.logging.level)
    costs = _parse_costs(args.costs)

    if args.rebuild_data:
        sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
        panel, metadata = build_processed_datasets(config, sector_config, persist=False)
    else:
        panel = pd.read_csv(config.resolve_path(config.paths.processed_dir) / "panel_daily.csv")
        metadata = pd.read_csv(
            config.resolve_path(config.paths.processed_dir) / "metadata.csv"
        ).set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)

    daily_dates = market.price.index[
        (market.price.index >= config.start_timestamp) & (market.price.index <= config.end_timestamp)
    ]
    daily_universe = build_rebalance_universe(market, list(daily_dates), config)
    score_panel = compute_daily_score_panel(
        market,
        daily_universe,
        score_family=args.score_family,
        include_btc=False,
    )
    risk_on = btc_above_trailing_price(market.price, lookback_days=11, confirm_days=2)

    variants = _build_variants()
    if args.quick:
        variants = [
            variant
            for variant in variants
            if variant.kind == "fixed" and variant.frequency in {"1D", "7D", "21D", "28D"}
            or variant.kind == "event" and variant.min_hold_days in {0, 5, 10} and variant.hold_rank in {1, 3} and variant.switch_score_gap in {0.0, 0.05} and variant.confirm_days in {1, 2}
            or variant.kind == "rank_stop" and variant.hold_rank in {1, 2, 3} and variant.confirm_days in {1, 2} and variant.min_hold_days in {0, 5}
        ]

    rows: list[dict[str, object]] = []
    full_paths: dict[str, tuple[pd.Series, pd.Series, pd.Series]] = {}
    for index, variant in enumerate(variants, start=1):
        assets, gross, turnover = _simulate_variant(market, score_panel, risk_on, config, variant)
        metrics_by_cost = {
            cost: _path_metrics(_cost_adjusted_returns(gross, turnover, cost), turnover)
            for cost in costs
        }
        screen_stats = _rolling_window_screen(_cost_adjusted_returns(gross, turnover, 20.0))
        rows.append(_variant_row(variant, metrics_by_cost, screen_stats))
        full_paths[variant.variant_id] = (assets, gross, turnover)
        if index % 20 == 0 or index == len(variants):
            print(f"completed full-path {index}/{len(variants)} variants", flush=True)

    summary = pd.DataFrame(rows)
    output_dir = ensure_dir(Path(args.output_dir))
    summary.to_csv(output_dir / "event_variant_summary_full_path.csv", index=False)

    btc_assets = pd.Series("bitcoin", index=market.price.loc[config.start_timestamp:config.end_timestamp].index, dtype="object")
    btc_sim = simulate_single_asset_targets(
        market.returns.loc[btc_assets.index],
        btc_assets,
        total_cost_bps=0.0,
    )
    btc_returns = _cost_adjusted_returns(btc_sim.daily_returns, btc_sim.turnover, 2.0)
    btc_metrics = _path_metrics(btc_returns, btc_sim.turnover)
    pd.DataFrame({"btc": btc_returns}).to_csv(output_dir / "btc_returns.csv")

    eligible = summary[
        (summary["full_multiple_20bps"] > btc_metrics["multiple"])
        & (summary["rolling_1y_median_multiple"] > 1.0)
    ].copy()
    if eligible.empty:
        eligible = summary.copy()
    # First screen on the distribution of overlapping one-year windows.  Then
    # spend the expensive fresh-start rebuild only on the strongest plateau.
    rolling_limit = 1 if args.quick else 3
    rolling_ids = eligible.sort_values(
        ["rolling_1y_median_multiple", "full_multiple_20bps"],
        ascending=False,
    ).head(rolling_limit)["variant_id"].tolist()
    rolling_rows: list[dict[str, object]] = []
    for index, variant_id in enumerate(rolling_ids, start=1):
        variant = next(item for item in variants if item.variant_id == variant_id)
        rolling_metrics = _rolling_summary_multi(
            market,
            score_panel,
            risk_on,
            config,
            variant,
            cost_bps_values=(2.0, 20.0),
        )
        rolling_rows.append({"variant_id": variant_id, **rolling_metrics})
        print(f"completed fresh-start rolling {index}/{len(rolling_ids)} candidates", flush=True)

    summary = summary.merge(pd.DataFrame(rolling_rows), on="variant_id", how="left")
    summary.to_csv(output_dir / "event_variant_summary.csv", index=False)

    stable = summary.dropna(subset=["rolling20_median_rolling_start_multiple"])
    stable = stable[
        (stable["full_multiple_20bps"] > btc_metrics["multiple"])
        & (stable["rolling20_median_rolling_start_multiple"] > btc_metrics["multiple"])
    ]
    if stable.empty:
        stable = summary.dropna(subset=["rolling20_median_rolling_start_multiple"])
    best_row = stable.sort_values(
        ["rolling20_median_rolling_start_multiple", "full_multiple_20bps"],
        ascending=False,
    ).iloc[0]
    best_variant = next(variant for variant in variants if variant.variant_id == best_row["variant_id"])
    best_assets, best_gross, best_turnover = full_paths[best_variant.variant_id]
    best_returns = _cost_adjusted_returns(best_gross, best_turnover, 20.0)
    yearly = _yearly_returns(best_returns).rename("strategy").to_frame()
    yearly["btc"] = _yearly_returns(btc_returns)
    yearly.index = yearly.index.year
    yearly.index.name = "year"
    yearly.to_csv(output_dir / "selected_yearly_returns.csv")

    best_history = None
    if best_variant.kind == "event":
        best_history = build_daily_event_targets_from_scores(
            market,
            score_panel,
            config,
            DailyEventSpec(
                min_hold_days=int(best_variant.min_hold_days),
                hold_rank=int(best_variant.hold_rank),
                switch_score_gap=float(best_variant.switch_score_gap),
                confirm_days=int(best_variant.confirm_days),
            ),
        ).selection_history
    _write_report(output_dir, summary, btc_metrics, yearly, best_variant, best_assets, best_history)

    manifest = {
        "config": args.config,
        "score_family": args.score_family,
        "start_date": str(config.start_timestamp.date()),
        "end_date": str(config.end_timestamp.date()),
        "costs": list(costs),
        "variants": len(variants),
        "rolling_start_rule": "monthly starts with at least 365 days remaining",
        "maximum_gross_exposure": 1.0,
        "data": "data/processed/panel_daily.csv",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(summary.sort_values("rolling20_median_rolling_start_multiple", ascending=False).head(20).to_string(index=False))
    print(f"Wrote event-driven validation to {output_dir}")


if __name__ == "__main__":
    main()
