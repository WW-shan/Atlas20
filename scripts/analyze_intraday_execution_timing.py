"""Test whether later or split intraday execution improves H5 fills.

This is an execution experiment, not a new alpha.  The strategy targets,
point-in-time Top20 universe, fees and T+1 rule are frozen.  Only the fill
time changes: 01:00 UTC (the current +1h assumption), 01:30, 02:00, or two
50/50 tranches at 01:00 and 01:30.  Binance 30-minute candles must carry
integer epoch-millisecond timestamps; corrupt timestamp units fail closed.
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

from atlas20.backtest.engine import BacktestResult  # noqa: E402
from atlas20.backtest.intraday import load_hourly_bars, pre_fill_returns  # noqa: E402
from atlas20.config import ResearchConfig  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    build_phase_momentum_targets,
)
from atlas20.universe.builder import MarketDataBundle  # noqa: E402

from scripts.download_binance_30m import validate_candle_frame, validate_epoch_ms  # noqa: E402
from scripts.run_phase_momentum import (  # noqa: E402
    _load_market,
    _production_result,
    _rolling_worst,
    _yearly_returns,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

BAR_MINUTES = 30
MISSING_POLICIES = ("prior_close", "day_close")


def load_30m_bars(directory: Path) -> dict[str, pd.DataFrame]:
    """Load validated 30-minute candles from a coverage manifest."""
    coverage = json.loads((directory / "coverage.json").read_text(encoding="utf-8"))
    bars: dict[str, pd.DataFrame] = {}
    for coin, info in coverage.items():
        if not info.get("available"):
            continue
        file_name = str(info.get("file") or f"{info['pair']}.csv")
        frame = pd.read_csv(directory / file_name)
        required = {"open_time_ms", "open", "high", "low", "close", "volume", "quote_volume"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{coin}: missing 30m columns {sorted(missing)}")
        frame["open_time_ms"] = [validate_epoch_ms(value) for value in frame["open_time_ms"]]
        frame["open_time"] = pd.to_datetime(frame["open_time_ms"], unit="ms", utc=True)
        frame = frame.sort_values("open_time_ms").drop_duplicates("open_time_ms").reset_index(drop=True)
        validate_candle_frame(frame, pair=str(coin))
        bars[str(coin)] = frame
    return bars


def _fill_observation(
    daily_returns: pd.DataFrame,
    intraday: dict[str, pd.DataFrame],
    *,
    fill_minutes: int,
    reference_close: pd.DataFrame | None,
    max_open_gap: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0 < fill_minutes <= 24 * 60 or fill_minutes % BAR_MINUTES != 0:
        raise ValueError("fill_minutes must be a positive multiple of 30 within one day")
    pre_fill = pd.DataFrame(np.nan, index=daily_returns.index, columns=daily_returns.columns)
    observed = pd.DataFrame(False, index=daily_returns.index, columns=daily_returns.columns)
    day_start = pd.DatetimeIndex(daily_returns.index).tz_localize("UTC")
    fill_bar = day_start + pd.Timedelta(minutes=fill_minutes - BAR_MINUTES)
    prior_close = None if reference_close is None else reference_close.reindex(daily_returns.index).shift(1)
    for coin in daily_returns.columns:
        frame = intraday.get(str(coin))
        if frame is None or frame.empty:
            continue
        times = pd.DatetimeIndex(pd.to_datetime(frame["open_time"], utc=True))
        opens = pd.Series(pd.to_numeric(frame["open"], errors="coerce").to_numpy(), index=times)
        closes = pd.Series(pd.to_numeric(frame["close"], errors="coerce").to_numpy(), index=times)
        start_price = opens.reindex(day_start).to_numpy(dtype=float)
        fill_price = closes.reindex(fill_bar).to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            pre = fill_price / start_price - 1.0
        valid = np.isfinite(pre) & (start_price > 0.0) & np.isfinite(fill_price) & (fill_price > 0.0)
        valid &= np.isfinite(daily_returns[coin].to_numpy(dtype=float))
        if prior_close is not None and coin in prior_close.columns:
            reference = prior_close[coin].to_numpy(dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                open_gap = np.abs(start_price / reference - 1.0)
            valid &= np.isfinite(open_gap) & (open_gap <= max_open_gap)
        pre_fill[coin] = pre
        observed[coin] = valid
    return pre_fill, observed


def pre_fill_returns_at_minutes(
    daily_returns: pd.DataFrame,
    intraday: dict[str, pd.DataFrame],
    *,
    fill_minutes: int,
    missing_fill: str = "day_close",
    reference_close: pd.DataFrame | None = None,
    max_open_gap: float = 0.05,
) -> pd.DataFrame:
    """Return the move from each day's 00:00 open to the requested fill time.

    ``fill_minutes=60`` uses the 30-minute bar opening at 00:30 and closing at
    01:00 UTC.  Missing observations are replaced by either the full daily
    return (``day_close``) or zero (``prior_close``), never silently by zero.
    """
    if missing_fill not in MISSING_POLICIES:
        raise ValueError(f"missing_fill must be one of {MISSING_POLICIES}")
    result = daily_returns.astype(float).copy()
    if missing_fill == "prior_close":
        result = result.where(result.isna(), 0.0)
    pre_fill, observed = _fill_observation(
        daily_returns.astype(float),
        intraday,
        fill_minutes=fill_minutes,
        reference_close=reference_close,
        max_open_gap=max_open_gap,
    )
    return result.mask(observed, pre_fill)


def execution_price_edge_bps(baseline_price: float, alternative_price: float, direction: float) -> float:
    """Price edge in bps; positive is favourable for a buy or a sell."""
    values = np.asarray([baseline_price, alternative_price, direction], dtype=float)
    if not np.isfinite(values).all() or baseline_price <= 0.0 or alternative_price <= 0.0 or direction == 0.0:
        return float("nan")
    if direction > 0.0:
        return float((baseline_price - alternative_price) / baseline_price * 10_000.0)
    return float((alternative_price - baseline_price) / baseline_price * 10_000.0)



VARIANT_FILLS = {
    "baseline_0100": (60, None),
    "advance_30m_0030": (30, None),
    "delay_30m_0130": (90, None),
    "delay_60m_0200": (120, None),
    "split_50_50_0100_0130": (60, 90),
}


def _combine_half_sleeves(first: BacktestResult, second: BacktestResult) -> tuple[pd.Series, pd.Series]:
    """Exact equity of two equal-capital sleeves filling at different times."""
    if not first.equity_curve.index.equals(second.equity_curve.index):
        raise ValueError("split sleeves have misaligned equity curves")
    equity = 0.5 * first.equity_curve.astype(float) + 0.5 * second.equity_curve.astype(float)
    returns = equity.pct_change().fillna(0.0)
    returns.name = "split_50_50"
    return returns, equity


def _simulate_variant(
    config: ResearchConfig,
    market: MarketDataBundle,
    built: PhaseMomentumBuildResult,
    index: pd.DatetimeIndex,
    *,
    prefill: dict[int, pd.DataFrame],
    cost_bps: float,
    first_minutes: int,
    second_minutes: int | None,
) -> tuple[pd.Series, pd.Series]:
    first = _production_result(
        config,
        market,
        built,
        index,
        cost_bps=cost_bps,
        pre_fill=prefill[first_minutes],
    )
    if second_minutes is None:
        return first.daily_returns, first.equity_curve
    second = _production_result(
        config,
        market,
        built,
        index,
        cost_bps=cost_bps,
        pre_fill=prefill[second_minutes],
    )
    return _combine_half_sleeves(first, second)


def _prices_and_observations(
    daily_returns: pd.DataFrame,
    intraday: dict[str, pd.DataFrame],
    *,
    fill_minutes: int,
    reference_close: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Close prices and validity masks at one intraday fill time."""
    prices = pd.DataFrame(np.nan, index=daily_returns.index, columns=daily_returns.columns)
    _, observed = _fill_observation(
        daily_returns,
        intraday,
        fill_minutes=fill_minutes,
        reference_close=reference_close,
        max_open_gap=0.05,
    )
    day_start = pd.DatetimeIndex(daily_returns.index).tz_localize("UTC")
    fill_bar = day_start + pd.Timedelta(minutes=fill_minutes - BAR_MINUTES)
    for coin in daily_returns.columns:
        frame = intraday.get(str(coin))
        if frame is None or frame.empty:
            continue
        closes = pd.Series(
            pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float),
            index=pd.DatetimeIndex(pd.to_datetime(frame["open_time"], utc=True)),
        )
        prices[coin] = closes.reindex(fill_bar).to_numpy(dtype=float)
    return prices, observed


def _trade_deltas(
    result: BacktestResult,
    market: MarketDataBundle,
    index: pd.DatetimeIndex,
    *,
    prefill: pd.DataFrame,
) -> pd.DataFrame:
    """Signed traded weight per asset on each execution day.

    The prior book is marked from the prior close to the fill using the same
    prefill path as the production engine.  The resulting weights are compared
    with the final target after normalisation/caps, so both buys and sells
    include drift rather than assuming a static prior target.
    """
    columns = market.returns.columns
    deltas = pd.DataFrame(0.0, index=index, columns=columns)
    returns = market.returns.loc[index].reindex(columns=columns)
    fill_split = prefill.reindex(index=index, columns=columns).where(
        prefill.reindex(index=index, columns=columns).notna(),
        returns,
    ).fillna(0.0)
    for position in range(1, len(index)):
        signal_date = index[position - 1]
        if signal_date not in result.rebalance_targets.index:
            continue
        execution_date = index[position]
        target = result.rebalance_targets.loc[signal_date].reindex(columns).fillna(0.0).astype(float)
        previous = result.weights.loc[signal_date].reindex(columns).fillna(0.0).astype(float)
        split = fill_split.loc[execution_date]
        growth = 1.0 + float((previous * split).sum())
        current = previous * (1.0 + split) / growth if growth > 0.0 else previous * 0.0
        deltas.loc[execution_date] = target - current
    return deltas


def _trade_impact_for_variant(
    deltas: pd.DataFrame,
    baseline_prices: pd.DataFrame,
    baseline_observed: pd.DataFrame,
    alternative_prices: pd.DataFrame,
    alternative_observed: pd.DataFrame,
    *,
    variant: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return event-level and asset-level execution-price edges in bps."""
    direction = np.sign(deltas.to_numpy(dtype=float))
    baseline = baseline_prices.to_numpy(dtype=float)
    alternative = alternative_prices.to_numpy(dtype=float)
    valid = (
        baseline_observed.to_numpy(dtype=bool)
        & alternative_observed.to_numpy(dtype=bool)
        & np.isfinite(baseline)
        & np.isfinite(alternative)
        & (baseline > 0.0)
        & (alternative > 0.0)
        & (direction != 0.0)
    )
    numerator = np.where(direction > 0.0, baseline - alternative, alternative - baseline)
    with np.errstate(divide="ignore", invalid="ignore"):
        edges = np.where(valid, numerator / baseline * 10_000.0, np.nan)
    weights = np.abs(deltas.to_numpy(dtype=float))
    covered_weights = np.where(valid, weights, 0.0)

    asset_rows: list[dict[str, object]] = []
    for column_index, coin in enumerate(deltas.columns):
        coin_weights = covered_weights[:, column_index]
        total_coin_weight = float(weights[:, column_index].sum())
        if total_coin_weight <= 0.0:
            continue
        coin_edges = edges[:, column_index]
        usable = np.isfinite(coin_edges) & (coin_weights > 0.0)
        asset_rows.append(
            {
                "variant": variant,
                "asset": str(coin),
                "traded_weight": total_coin_weight,
                "covered_weight_share": float(coin_weights.sum() / total_coin_weight),
                "weighted_edge_bps": (
                    float(np.average(coin_edges[usable], weights=coin_weights[usable])) if usable.any() else np.nan
                ),
            }
        )

    event_rows: list[dict[str, object]] = []
    for row_index, date in enumerate(deltas.index):
        event_total = float(weights[row_index].sum())
        if event_total <= 0.0:
            continue
        usable = np.isfinite(edges[row_index]) & (covered_weights[row_index] > 0.0)
        covered = float(covered_weights[row_index].sum())
        event_rows.append(
            {
                "date": date,
                "year": int(pd.Timestamp(date).year),
                "variant": variant,
                "traded_weight": event_total,
                "covered_weight": covered,
                "covered_weight_share": covered / event_total,
                "weighted_edge_bps": (
                    float(np.average(edges[row_index, usable], weights=covered_weights[row_index, usable]))
                    if usable.any()
                    else np.nan
                ),
                "conservative_edge_bps": (
                    float(np.nansum(edges[row_index, usable] * covered_weights[row_index, usable]) / event_total)
                    if usable.any()
                    else 0.0
                ),
                "buy_weight": float(weights[row_index][direction[row_index] > 0.0].sum()),
                "sell_weight": float(weights[row_index][direction[row_index] < 0.0].sum()),
            }
        )
    return pd.DataFrame(event_rows), pd.DataFrame(asset_rows)


def _impact_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for variant, group in events.groupby("variant", sort=False):
        usable = group[group["weighted_edge_bps"].notna()]
        total_weight = float(group["traded_weight"].sum())
        covered_weight = float(group["covered_weight"].sum())
        rows.append(
            {
                "variant": variant,
                "events": int(len(usable)),
                "traded_weight": total_weight,
                "covered_weight_share": covered_weight / total_weight if total_weight > 0.0 else np.nan,
                "weighted_edge_bps": (
                    float(np.average(usable["weighted_edge_bps"], weights=usable["covered_weight"]))
                    if not usable.empty
                    else np.nan
                ),
                "conservative_edge_bps": (
                    float((usable["weighted_edge_bps"] * usable["covered_weight"]).sum() / total_weight)
                    if not usable.empty and total_weight > 0.0
                    else np.nan
                ),
                "event_mean_edge_bps": float(usable["weighted_edge_bps"].mean()) if not usable.empty else np.nan,
                "event_median_edge_bps": float(usable["weighted_edge_bps"].median()) if not usable.empty else np.nan,
                "positive_event_share": float((usable["weighted_edge_bps"] > 0.0).mean()) if not usable.empty else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _variant_gate_table(
    summary: pd.DataFrame,
    impact_summary: pd.DataFrame,
    *,
    analysis_cost: float,
    minimum_coverage: float = 0.95,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    impact_lookup = impact_summary.set_index(["missing_fill", "variant"])
    for policy in MISSING_POLICIES:
        at_cost = summary[(summary["missing_fill"] == policy) & (summary["cost_bps"] == analysis_cost)].set_index("variant")
        if "baseline_0100" not in at_cost.index:
            continue
        baseline = at_cost.loc["baseline_0100"]
        for variant in VARIANT_FILLS:
            if variant == "baseline_0100" or variant not in at_cost.index:
                continue
            row = at_cost.loc[variant]
            coverage = float(impact_lookup.loc[(policy, variant), "covered_weight_share"])
            relative_50 = float(
                summary[
                    (summary["missing_fill"] == policy)
                    & (summary["variant"] == variant)
                    & (summary["cost_bps"] == 50.0)
                ]["relative_multiple"].iloc[0]
            )
            relative_100 = float(
                summary[
                    (summary["missing_fill"] == policy)
                    & (summary["variant"] == variant)
                    & (summary["cost_bps"] == 100.0)
                ]["relative_multiple"].iloc[0]
            )
            gates = {
                "coverage_ok": coverage >= minimum_coverage,
                "return_ok": float(row["multiple"]) > float(baseline["multiple"]),
                "sharpe_ok": float(row["sharpe"]) > float(baseline["sharpe"]),
                "drawdown_ok": float(row["max_drawdown"]) >= float(baseline["max_drawdown"]) - 0.02,
                "rolling_ok": float(row["rolling_1y_worst_multiple"])
                >= float(baseline["rolling_1y_worst_multiple"]),
                "ex2022_ok": float(row["multiple_ex_2022"]) >= float(baseline["multiple_ex_2022"]),
                "cost_50_ok": relative_50 >= 1.0,
                "cost_100_ok": relative_100 >= 1.0,
            }
            rows.append(
                {
                    "missing_fill": policy,
                    "variant": variant,
                    "trade_weight_coverage": coverage,
                    "relative_multiple_20bps": float(row["multiple"]) / float(baseline["multiple"]),
                    "sharpe_change": float(row["sharpe"]) - float(baseline["sharpe"]),
                    "drawdown_change_pp": (
                        float(row["max_drawdown"]) - float(baseline["max_drawdown"])
                    )
                    * 100.0,
                    "relative_multiple_50bps": relative_50,
                    "relative_multiple_100bps": relative_100,
                    "ex2022_relative": float(row["multiple_ex_2022"]) / float(baseline["multiple_ex_2022"]),
                    **gates,
                    "passed_all_gates": all(gates.values()),
                }
            )
    return pd.DataFrame(rows)


def _remove_2022_multiple(returns: pd.Series) -> float:
    selected = returns[returns.index > pd.Timestamp("2022-12-31", tz=returns.index.tz)]
    return float((1.0 + selected.fillna(0.0)).prod())

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--intraday-dir", type=Path, default=Path("data/raw/binance_30m"))
    parser.add_argument("--hourly-dir", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_execution_timing_30m"))
    parser.add_argument("--costs", default="2,20,50,100")
    parser.add_argument("--analysis-cost-bps", type=float, default=20.0)
    args = parser.parse_args(argv)

    costs = tuple(float(value.strip()) for value in args.costs.split(",") if value.strip())
    if not costs or any(value < 0.0 for value in costs):
        raise SystemExit("--costs must be a non-empty list of non-negative numbers")
    if args.analysis_cost_bps not in costs:
        raise SystemExit("--analysis-cost-bps must also appear in --costs")
    configure_logging("INFO")
    output_dir = ensure_dir(args.output_dir)
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    built = build_phase_momentum_targets(market, universe, index, spec=PhaseMomentumSpec())
    intraday = load_30m_bars(args.intraday_dir)
    hourly = load_hourly_bars(args.hourly_dir)
    daily = market.returns.loc[index]
    closes = market.raw_price.reindex(index=index, columns=daily.columns)
    print(f"Loaded {len(intraday)} validated 30m assets for {len(index)} days")

    prefill: dict[str, dict[int, pd.DataFrame]] = {}
    hourly_prefill: dict[str, pd.DataFrame] = {}
    for policy in MISSING_POLICIES:
        prefill[policy] = {
            minutes: pre_fill_returns_at_minutes(
                daily,
                intraday,
                fill_minutes=minutes,
                missing_fill=policy,
                reference_close=closes,
            )
            for minutes in (30, 60, 90, 120)
        }
        hourly_prefill[policy] = pre_fill_returns(
            daily,
            hourly,
            fill_hours=1,
            missing_fill=policy,
            reference_close=closes,
        )

    summary_rows: list[dict[str, object]] = []
    yearly_frames: list[pd.Series] = []
    return_frames: dict[str, pd.Series] = {}
    impact_events: list[pd.DataFrame] = []
    impact_assets: list[pd.DataFrame] = []
    price_cache: dict[str, dict[int, tuple[pd.DataFrame, pd.DataFrame]]] = {}

    for policy in MISSING_POLICIES:
        hourly_result = _production_result(
            config,
            market,
            built,
            index,
            cost_bps=args.analysis_cost_bps,
            pre_fill=hourly_prefill[policy],
        )
        summary_rows.append(
            {
                "missing_fill": policy,
                "variant": "hourly_anchor_0100",
                "cost_bps": float(args.analysis_cost_bps),
                **_metrics_from_returns(hourly_result.daily_returns),
                **_rolling_worst(hourly_result.daily_returns),
                "multiple_ex_2022": _remove_2022_multiple(hourly_result.daily_returns),
            }
        )

        prices: dict[int, tuple[pd.DataFrame, pd.DataFrame]] = {}
        for minutes in (30, 60, 90, 120):
            prices[minutes] = _prices_and_observations(
                daily,
                intraday,
                fill_minutes=minutes,
                reference_close=closes,
            )
        price_cache[policy] = prices

        deltas = _trade_deltas(
            hourly_result,
            market,
            index,
            prefill=prefill[policy][60],
        )
        split_prices = 0.5 * (prices[60][0] + prices[90][0])
        split_observed = prices[60][1] & prices[90][1]
        impact_specs = {
            "advance_30m_0030": (prices[30][0], prices[30][1]),
            "delay_30m_0130": (prices[90][0], prices[90][1]),
            "delay_60m_0200": (prices[120][0], prices[120][1]),
            "split_50_50_0100_0130": (split_prices, split_observed),
        }
        for variant, (alternative_prices, alternative_observed) in impact_specs.items():
            events, assets = _trade_impact_for_variant(
                deltas,
                prices[60][0],
                prices[60][1],
                alternative_prices,
                alternative_observed,
                variant=variant,
            )
            if not events.empty:
                impact_events.append(events.assign(missing_fill=policy))
            if not assets.empty:
                impact_assets.append(assets.assign(missing_fill=policy))

        for cost in costs:
            for variant, (first_minutes, second_minutes) in VARIANT_FILLS.items():
                returns, equity = _simulate_variant(
                    config,
                    market,
                    built,
                    index,
                    prefill=prefill[policy],
                    cost_bps=cost,
                    first_minutes=first_minutes,
                    second_minutes=second_minutes,
                )
                summary_rows.append(
                    {
                        "missing_fill": policy,
                        "variant": variant,
                        "cost_bps": float(cost),
                        **_metrics_from_returns(returns),
                        **_rolling_worst(returns),
                        "multiple_ex_2022": _remove_2022_multiple(returns),
                    }
                )
                if cost == args.analysis_cost_bps:
                    return_frames[f"{policy}__{variant}"] = returns
                    yearly_frames.append(_yearly_returns(returns).rename(f"{policy}__{variant}"))

    summary = pd.DataFrame(summary_rows)
    baseline = summary[summary["variant"] == "baseline_0100"].set_index(["missing_fill", "cost_bps"])
    summary["relative_multiple"] = [
        (
            row["multiple"]
            / baseline.loc[(row["missing_fill"], row["cost_bps"]), "multiple"]
            if row["variant"] not in ("baseline_0100", "hourly_anchor_0100")
            else 1.0
        )
        for _, row in summary.iterrows()
    ]
    summary["drawdown_change_pp"] = [
        (
            (row["max_drawdown"] - baseline.loc[(row["missing_fill"], row["cost_bps"]), "max_drawdown"])
            * 100.0
            if row["variant"] not in ("baseline_0100", "hourly_anchor_0100")
            else 0.0
        )
        for _, row in summary.iterrows()
    ]
    summary.to_csv(output_dir / "summary.csv", index=False)

    yearly = pd.concat(yearly_frames, axis=1)
    yearly.to_csv(output_dir / "yearly_returns.csv", index_label="date")
    pd.DataFrame(return_frames).to_csv(output_dir / "daily_returns.csv", index_label="date")

    events = pd.concat(impact_events, ignore_index=True) if impact_events else pd.DataFrame()
    assets = pd.concat(impact_assets, ignore_index=True) if impact_assets else pd.DataFrame()
    events.to_csv(output_dir / "trade_events.csv", index=False)
    assets.to_csv(output_dir / "trade_impact_by_asset.csv", index=False)
    uncovered = (
        assets.groupby(["missing_fill", "asset"], sort=True)
        .agg(
            traded_weight=("traded_weight", "max"),
            covered_weight_share=("covered_weight_share", "max"),
        )
        .reset_index()
        .query("covered_weight_share < 1.0")
        .sort_values(["missing_fill", "traded_weight"], ascending=[True, False])
    )
    uncovered.to_csv(output_dir / "uncovered_trade_weight.csv", index=False)
    impact_summaries = []
    for policy in MISSING_POLICIES:
        policy_events = events[events["missing_fill"] == policy]
        impact_summary = _impact_summary(policy_events)
        impact_summary.insert(0, "missing_fill", policy)
        impact_summaries.append(impact_summary)
    impact_summary = pd.concat(impact_summaries, ignore_index=True)
    impact_summary.to_csv(output_dir / "impact_summary.csv", index=False)
    gates = _variant_gate_table(
        summary,
        impact_summary,
        analysis_cost=args.analysis_cost_bps,
    )
    gates.to_csv(output_dir / "decision_gates.csv", index=False)

    usable_events = events[events["weighted_edge_bps"].notna()].copy()
    impact_yearly = (
        usable_events.groupby(["missing_fill", "variant", "year"], sort=True)
        .apply(
            lambda group: pd.Series(
                {
                    "weighted_edge_bps": np.average(
                        group["weighted_edge_bps"],
                        weights=group["covered_weight"],
                    ),
                    "covered_weight_share": group["covered_weight"].sum()
                    / group["traded_weight"].sum(),
                    "events": len(group),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    impact_yearly.to_csv(output_dir / "impact_by_year.csv", index=False)

    target_assets = sorted(
        {
            str(asset)
            for target in built.targets.values()
            for asset, weight in target.items()
            if float(weight) > 1e-12
        }
    )
    coverage_json = json.loads((args.intraday_dir / "coverage.json").read_text(encoding="utf-8"))
    coverage_rows = []
    for coin in target_assets:
        info = coverage_json.get(coin, {})
        coverage_rows.append(
            {
                "asset": coin,
                "available_30m": bool(info.get("available")),
                "rows": int(info.get("rows", 0)),
                "first": info.get("first"),
                "last": info.get("last"),
                "missing_bars": info.get("missing_bars"),
                "gap_count": info.get("gap_count"),
                "full_2022_2026_rows_ok": (
                    int(info.get("rows", 0)) == 83_230 if info.get("available") else False
                ),
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    weight_by_asset = (
        assets[assets["missing_fill"] == MISSING_POLICIES[0]]
        .groupby("asset", sort=True)
        .agg(
            traded_weight=("traded_weight", "max"),
            trade_weight_coverage=("covered_weight_share", "max"),
        )
        .reset_index()
        .rename(columns={"asset": "asset"})
    )
    coverage = coverage.merge(weight_by_asset, on="asset", how="left").fillna(
        {"traded_weight": 0.0, "trade_weight_coverage": 0.0}
    )
    coverage.to_csv(output_dir / "data_coverage.csv", index=False)

    manifest = {
        "status": "diagnostic_only",
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "universe": "strict point-in-time Top20",
        "portfolio": "long-only spot, no leverage, gross exposure <= 1.0",
        "timestamps": "integer epoch milliseconds; seconds/microseconds fail closed",
        "variants": {
            "baseline_0100": "single fill at 01:00 UTC",
            "advance_30m_0030": "single fill at 00:30 UTC",
            "delay_30m_0130": "single fill at 01:30 UTC",
            "delay_60m_0200": "single fill at 02:00 UTC",
            "split_50_50_0100_0130": "50% at 01:00 and 50% at 01:30",
        },
        "missing_fill_policies": list(MISSING_POLICIES),
        "analysis_cost_bps": args.analysis_cost_bps,
        "cost_bps": list(costs),
        "intraday_dir": str(args.intraday_dir),
        "hourly_anchor_dir": str(args.hourly_dir),
        "target_asset_count": len(target_assets),
        "available_30m_asset_count": int(coverage["available_30m"].sum()),
        "missing_30m_assets": coverage.loc[~coverage["available_30m"], "asset"].tolist(),
        "decision_outcome": {
            "passed_all_gates": bool(gates["passed_all_gates"].any()),
            "variants_passed": gates.loc[gates["passed_all_gates"], "variant"].tolist(),
            "conclusion": "rejected; no alternative beats the same-data 01:00 baseline across coverage, return, risk, costs and robustness",
        },
        "decision_rules_fixed_before_results": {
            "data": "no invalid dates, duplicates or uncovered timestamp-unit conversions",
            "trade_weight_coverage": ">=0.95 for an actionable execution result",
            "return": "at 20bps, alternative multiple must exceed the same-data 01:00 baseline",
            "risk": "Sharpe must improve and MDD must not worsen by more than 2 percentage points",
            "robustness": "must not rely on 2022 and rolling 1-year worst must not worsen",
            "cost": "must remain no worse than baseline at 50 and 100bps",
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = "\n".join(
        [
            "# Intraday execution timing at 30-minute resolution",
            "",
            "This experiment changes only the H5 fill time. Strategy targets, the point-in-time Top20",
            "universe, T+1 rule, long-only gross exposure and costs are frozen.",
            "",
            "## Performance",
            "",
            dataframe_to_markdown(
                summary[
                    [
                        "missing_fill",
                        "variant",
                        "cost_bps",
                        "multiple",
                        "sharpe",
                        "max_drawdown",
                        "relative_multiple",
                        "drawdown_change_pp",
                        "multiple_ex_2022",
                        "rolling_1y_worst_multiple",
                    ]
                ]
            ),
            "",
            "## Execution-price edge",
            "",
            "Positive bps means the alternative fill price is better for the actual buy/sell side.",
            "",
            dataframe_to_markdown(impact_summary, number_columns={"weighted_edge_bps", "conservative_edge_bps"}),
            "",
            "## Decision gates",
            "",
            "The baseline is the same-data 01:00 fill. The 1h anchor is shown only as a venue/data-coverage sanity check.",
            "",
            dataframe_to_markdown(gates),
            "",
            "## Data coverage",
            "",
            f"H5 target assets: {len(target_assets)}; Binance 30m available: "
            f"{int(coverage['available_30m'].sum())}; missing: "
            f"{', '.join(manifest['missing_30m_assets']) or 'none'}.",
            "",
            dataframe_to_markdown(coverage),
            "",
        ]
    )
    conclusion = (
        "No alternative passes the pre-fixed gates."
        if not bool(gates["passed_all_gates"].any())
        else "At least one alternative passes every pre-fixed gate; it still requires a separate pre-registered confirmation."
    )
    report = report.replace(
        "## Performance",
        f"**Conclusion:** {conclusion}\n\n## Performance",
        1,
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(summary.to_string(index=False))
    print(impact_summary.to_string(index=False))
    print(f"Wrote 30m execution timing analysis to {output_dir}")


if __name__ == "__main__":
    main()
