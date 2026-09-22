"""Validate daily own-trend stops around the 21-day concentrated leader.

The external research is consistent on one point: frequent re-selection is not
the only use of daily data.  A daily stop on the *current* holding can reduce
drawdown without forcing a new leader every day.  This script keeps the
original 21-day point-in-time Top-20 selection and only changes the exit rule.

The rule is deliberately simple and reproducible:

* select the CTREND-breakout leader on the 21-day calendar;
* monitor that leader every day against its own moving average;
* after a confirmed close below the average, sell to cash;
* re-enter only on the next scheduled selection date if the base strategy still
  chooses that coin and it is back above its trend filter.

No leverage, no shorting, T+1 execution, and the same BTC risk gate as the
champion are used throughout.
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
from atlas20.config import load_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import btc_above_trailing_price  # noqa: E402
from atlas20.strategies.event_driven import compute_daily_score_panel  # noqa: E402
from atlas20.strategies.overlays import (  # noqa: E402
    apply_daily_asset_stop_overlay,
    apply_daily_risk_overlay,
)
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)


DEFAULT_MA_WINDOWS: tuple[int, ...] = (20, 30, 40, 50, 60, 75, 100, 150, 200)
DEFAULT_CONFIRM_DAYS: tuple[int, ...] = (1, 2, 3)
DEFAULT_COSTS: tuple[float, ...] = (2.0, 5.0, 10.0, 20.0, 50.0)


@dataclass(frozen=True)
class TrendStopSpec:
    ma_window: int
    confirm_days: int


def _parse_costs(value: str) -> tuple[float, ...]:
    costs = tuple(float(item) for item in value.split(",") if item.strip())
    if not costs or any(cost < 0 for cost in costs):
        raise ValueError("Costs must be a non-empty list of non-negative numbers")
    return costs


def _target_asset_series(targets: dict[pd.Timestamp, pd.Series], index: pd.DatetimeIndex) -> pd.Series:
    """Expand signal-date targets into the actual held asset on each day."""
    values: list[str] = []
    current = ""
    for date in index:
        signal_date = pd.Timestamp(date)
        if signal_date in targets:
            target = targets[signal_date]
            positive = target[target > 0.0]
            current = str(positive.idxmax()) if not positive.empty else ""
        values.append(current)
    return pd.Series(values, index=index, dtype="object")


def _scheduled_targets(
    score_panel: pd.DataFrame,
    schedule_dates: list[pd.Timestamp],
    index: pd.DatetimeIndex,
) -> dict[pd.Timestamp, pd.Series]:
    """Return one target per scheduled date, not a pre-expanded daily path."""
    usable = set(index)
    targets: dict[pd.Timestamp, pd.Series] = {}
    for date in schedule_dates:
        signal_date = pd.Timestamp(date)
        if signal_date not in usable:
            continue
        if signal_date in score_panel.index:
            scores = score_panel.loc[signal_date].dropna().sort_values(ascending=False)
            targets[signal_date] = (
                pd.Series({str(scores.index[0]): 1.0}) if not scores.empty else pd.Series(dtype=float)
            )
        else:
            targets[signal_date] = pd.Series(dtype=float)
    return targets


def _confirmed_above_ma(price: pd.DataFrame, ma_window: int, confirm_days: int) -> pd.DataFrame:
    moving_average = price.rolling(ma_window, min_periods=ma_window).mean()
    below = price < moving_average
    if confirm_days <= 1:
        return ~below
    confirmed_below = below.rolling(confirm_days, min_periods=confirm_days).sum() >= confirm_days
    return ~confirmed_below


def _path_metrics(returns: pd.Series, turnover: pd.Series, annualization_days: int = 365) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    turnover_clean = pd.to_numeric(turnover, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    periods = max(len(clean) - 1, 1)
    multiple = float((1.0 + clean).prod())
    cagr = multiple ** (annualization_days / periods) - 1.0 if multiple > 0 else -1.0
    volatility = float(clean.std(ddof=0) * math.sqrt(annualization_days))
    sharpe = float(clean.mean() * annualization_days / volatility) if volatility > 0 else 0.0
    equity = (1.0 + clean).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return {
        "multiple": multiple,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else 0.0,
        "annualized_turnover": float(turnover_clean.sum() * annualization_days / periods),
    }


def _cost_adjusted_returns(gross: pd.Series, turnover: pd.Series, total_cost_bps: float) -> pd.Series:
    fee_rate = float(total_cost_bps) / 10_000.0
    return (1.0 - turnover.astype(float) * fee_rate) * (1.0 + gross.astype(float)) - 1.0


def _simulate_spec(
    market: MarketDataBundle,
    score_panel: pd.DataFrame,
    risk_on: pd.Series,
    config,
    spec: TrendStopSpec,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    start = pd.Timestamp(config.start_timestamp).normalize()
    end = pd.Timestamp(config.end_timestamp).normalize()
    index = market.price.index[(market.price.index >= start) & (market.price.index <= end)]
    schedule = get_rebalance_dates(market.price.index, start, "21D", "21D")
    base_targets = _scheduled_targets(score_panel, schedule, index)
    trend_on = _confirmed_above_ma(market.price, spec.ma_window, spec.confirm_days)
    stopped_targets = apply_daily_asset_stop_overlay(base_targets, trend_on)
    targets = apply_daily_risk_overlay(
        stopped_targets,
        risk_on.reindex(index).fillna(True),
        risk_off_target=None,
        initial_target=None,
    )
    assets = _target_asset_series(targets, index)
    simulation = simulate_single_asset_targets(
        market.returns.reindex(index),
        assets,
        total_cost_bps=0.0,
        missing_return_policy="fill",
        missing_return_fill=0.0,
    )
    return assets, simulation.daily_returns, simulation.turnover


def _monthly_start_dates(index: pd.DatetimeIndex, start: pd.Timestamp, min_days: int = 365) -> list[pd.Timestamp]:
    max_start = index.max() - pd.Timedelta(days=min_days)
    starts = pd.date_range(start, max_start, freq="MS")
    aligned: list[pd.Timestamp] = []
    for candidate in starts:
        usable = index[index >= candidate]
        if not usable.empty and usable[0] <= max_start:
            aligned.append(pd.Timestamp(usable[0]))
    return list(dict.fromkeys(aligned))


def _rolling_summary(
    market: MarketDataBundle,
    score_panel: pd.DataFrame,
    risk_on: pd.Series,
    base_config,
    spec: TrendStopSpec,
    *,
    costs: tuple[float, ...] = (2.0, 20.0),
) -> dict[str, float]:
    starts = _monthly_start_dates(market.price.index, pd.Timestamp(base_config.start_timestamp))
    rows: dict[float, list[dict[str, float]]] = {cost: [] for cost in costs}
    for start_date in starts:
        local = base_config.model_copy(deep=True)
        local.start_date = start_date.date().isoformat()
        _, gross, turnover = _simulate_spec(market, score_panel, risk_on, local, spec)
        for cost in costs:
            rows[cost].append(_path_metrics(_cost_adjusted_returns(gross, turnover, cost), turnover))
    output: dict[str, float] = {}
    for cost, values in rows.items():
        frame = pd.DataFrame(values)
        prefix = f"rolling{cost:g}"
        if frame.empty:
            continue
        output.update(
            {
                f"{prefix}_start_count": float(len(frame)),
                f"{prefix}_median_multiple": float(frame["multiple"].median()),
                f"{prefix}_worst_multiple": float(frame["multiple"].min()),
                f"{prefix}_best_multiple": float(frame["multiple"].max()),
                f"{prefix}_median_drawdown": float(frame["max_drawdown"].median()),
                f"{prefix}_worst_drawdown": float(frame["max_drawdown"].min()),
            }
        )
    return output


def _btc_metrics(market: MarketDataBundle, config, cost_bps: float = 2.0) -> dict[str, float]:
    index = market.price.loc[config.start_timestamp : config.end_timestamp].index
    assets = pd.Series("bitcoin", index=index, dtype="object")
    sim = simulate_single_asset_targets(market.returns.loc[index], assets, total_cost_bps=0.0)
    returns = _cost_adjusted_returns(sim.daily_returns, sim.turnover, cost_bps)
    return _path_metrics(returns, sim.turnover)


def _write_report(output_dir: Path, summary: pd.DataFrame, btc: dict[str, float], yearly: pd.DataFrame) -> None:
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
        "rolling20_median_multiple",
        "rolling20_worst_multiple",
    ]
    lines = [
        "# Daily Own-Trend Stop Validation",
        "",
        "## Question",
        "",
        "The fixed 21-day strategy already checks the BTC market gate every day. This study asks",
        "whether daily monitoring of the *selected coin's own trend* can improve the strategy",
        "without turning the leader selection into a noisy daily rotation.",
        "",
        "## Rule",
        "",
        "- Point-in-time Top-20, exclude BTC, CTREND-breakout top-1 on a 21-day calendar.",
        "- Monitor the holding against its own moving average every day.",
        "- After a confirmed close below the moving average, sell to cash.",
        "- Re-enter only on the next scheduled selection date when the base strategy still",
        "  chooses that coin and it is back above the trend filter.",
        "- Keep the BTC 11-day trailing gate with two-day confirmation.",
        "- No leverage and no shorting; T+1 execution.",
        "",
        "## External evidence",
        "",
        "- Han et al. find stronger evidence for time-series momentum than cross-sectional",
        "  momentum once realistic costs and daily fluctuations are included.",
        "  <https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf>",
        "- Kaya and Mostowfi find that a simple stop-loss rule materially reduces downside risk",
        "  and improves Sharpe for concentrated crypto portfolios.",
        "  <https://doi.org/10.1016/j.frl.2021.102422>",
        "- Yang finds risk-managed crypto momentum improves returns and Sharpe after costs.",
        "  <https://doi.org/10.1016/j.frl.2025.107879>",
        "",
        "## Results",
        "",
        dataframe_to_markdown(summary.sort_values("full_multiple_20bps", ascending=False)[table_columns]),
        "",
        "## BTC benchmark at 2bps",
        "",
        f"- Multiple: {btc['multiple']:.2f}x",
        f"- CAGR: {btc['cagr']:.2%}",
        f"- Sharpe: {btc['sharpe']:.3f}",
        f"- Max drawdown: {btc['max_drawdown']:.2%}",
        "",
        "## Selected candidate yearly returns (2bps)",
        "",
        dataframe_to_markdown(yearly.reset_index()),
        "",
        "## Guardrail",
        "",
        "A daily stop is useful only if it improves the rolling-start distribution and cost",
        "survival, not merely the fixed 2022-start multiple. The parameter neighborhood and",
        "out-of-sample subperiods are therefore part of the decision.",
    ]
    (output_dir / "trend_stop_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output-dir", default="reports/trend_stop_validation_2022")
    parser.add_argument("--costs", default="2,5,10,20,50")
    parser.add_argument("--rebuild-data", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config).model_copy(deep=True)
    config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    configure_logging(config.logging.level)
    costs = _parse_costs(args.costs)

    if args.rebuild_data:
        from atlas20.config import load_sector_config

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
    daily_dates = market.price.index[
        (market.price.index >= config.start_timestamp) & (market.price.index <= config.end_timestamp)
    ]
    daily_universe = build_rebalance_universe(market, list(daily_dates), config)
    score_panel = compute_daily_score_panel(market, daily_universe, include_btc=False)
    risk_on = btc_above_trailing_price(market.price, lookback_days=11, confirm_days=2)

    rows: list[dict[str, object]] = []
    paths: dict[str, tuple[pd.Series, pd.Series, pd.Series]] = {}
    specs: list[TrendStopSpec] = [
        TrendStopSpec(ma_window=window, confirm_days=confirm)
        for window in DEFAULT_MA_WINDOWS
        for confirm in DEFAULT_CONFIRM_DAYS
    ]
    for index, spec in enumerate(specs, start=1):
        assets, gross, turnover = _simulate_spec(market, score_panel, risk_on, config, spec)
        metrics_by_cost = {
            cost: _path_metrics(_cost_adjusted_returns(gross, turnover, cost), turnover)
            for cost in costs
        }
        # Cheap overlapping one-year screen before expensive fresh-start rebuilds.
        gross_20 = _cost_adjusted_returns(gross, turnover, 20.0)
        rolling_1y = (1.0 + gross_20).rolling(365).apply(np.prod, raw=True).dropna()
        row = {
            "variant_id": f"ma{spec.ma_window}_confirm{spec.confirm_days}",
            **asdict(spec),
            "full_multiple_2bps": metrics_by_cost[2.0]["multiple"],
            "full_multiple_5bps": metrics_by_cost[5.0]["multiple"],
            "full_multiple_10bps": metrics_by_cost[10.0]["multiple"],
            "full_multiple_20bps": metrics_by_cost[20.0]["multiple"],
            "full_multiple_50bps": metrics_by_cost[50.0]["multiple"],
            "full_cagr_20bps": metrics_by_cost[20.0]["cagr"],
            "full_sharpe_20bps": metrics_by_cost[20.0]["sharpe"],
            "full_max_drawdown_20bps": metrics_by_cost[20.0]["max_drawdown"],
            "full_annualized_turnover": metrics_by_cost[20.0]["annualized_turnover"],
            "rolling_1y_median_multiple": float(rolling_1y.median()) if not rolling_1y.empty else 0.0,
            "rolling_1y_worst_multiple": float(rolling_1y.min()) if not rolling_1y.empty else 0.0,
        }
        rows.append(row)
        paths[row["variant_id"]] = (assets, gross, turnover)
        print(f"completed {index}/{len(specs)} trend-stop specs", flush=True)

    summary = pd.DataFrame(rows)
    # Fresh-start rolling validation for the best three by the one-year screen.
    top_ids = summary.sort_values(
        ["rolling_1y_median_multiple", "full_multiple_20bps"], ascending=False
    ).head(3)["variant_id"].tolist()
    rolling_rows: list[dict[str, object]] = []
    for variant_id in top_ids:
        spec = next(item for item in specs if f"ma{item.ma_window}_confirm{item.confirm_days}" == variant_id)
        rolling_rows.append(
            {
                "variant_id": variant_id,
                **_rolling_summary(market, score_panel, risk_on, config, spec),
            }
        )
    summary = summary.merge(pd.DataFrame(rolling_rows), on="variant_id", how="left")
    output_dir = ensure_dir(Path(args.output_dir))
    summary.to_csv(output_dir / "trend_stop_summary.csv", index=False)

    btc = _btc_metrics(market, config)
    best_row = summary.sort_values(
        ["rolling20_median_multiple", "full_multiple_20bps"], ascending=False
    ).dropna(subset=["rolling20_median_multiple"]).iloc[0]
    best_id = str(best_row["variant_id"])
    best_assets, best_gross, best_turnover = paths[best_id]
    best_returns = _cost_adjusted_returns(best_gross, best_turnover, 2.0)
    yearly = ((1.0 + best_returns).resample("YE").prod() - 1.0).rename("strategy").to_frame()
    yearly["btc"] = (1.0 + _cost_adjusted_returns(
        simulate_single_asset_targets(
            market.returns.loc[best_returns.index],
            pd.Series("bitcoin", index=best_returns.index, dtype="object"),
            total_cost_bps=0.0,
        ).daily_returns,
        simulate_single_asset_targets(
            market.returns.loc[best_returns.index],
            pd.Series("bitcoin", index=best_returns.index, dtype="object"),
            total_cost_bps=0.0,
        ).turnover,
        2.0,
    )).resample("YE").prod() - 1.0
    yearly.index = yearly.index.year
    yearly.index.name = "year"
    yearly.to_csv(output_dir / "selected_yearly_returns.csv")
    _write_report(output_dir, summary, btc, yearly)
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "start": str(config.start_timestamp.date()),
                "end": str(config.end_timestamp.date()),
                "costs": list(costs),
                "ma_windows": list(DEFAULT_MA_WINDOWS),
                "confirm_days": list(DEFAULT_CONFIRM_DAYS),
                "data": "data/processed/panel_daily.csv",
                "maximum_gross_exposure": 1.0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(summary.sort_values("full_multiple_20bps", ascending=False).to_string(index=False))
    print(f"Wrote trend-stop validation to {output_dir}")


if __name__ == "__main__":
    main()
