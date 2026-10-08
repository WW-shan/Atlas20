"""Execution-delay sensitivity for the phase-momentum champion.

The production engine applies a target from signal date D to D+1's
close-to-close return, i.e. it fills at D's close.  Live trading cannot do
that: CoinMarketCap publishes D's close only after 00:00 UTC on D+1 and the
daily refresh runs at 02:30 UTC, so orders go out hours after the close the
signal used.  With daily bars alone the delay can only be bracketed: lag 0 is
the engine default, lag 1 fills at D+1's close (an upper bound for a same-day
morning fill), and lag 2 is a stress case.  Binance 1-hour candles
(``scripts/download_hourly_prices.py``) place the fill inside D+1 instead: a
fill ``H`` hours after the close credits the move up to the fill to the book
held before trading.  Coins without usable candles are run twice, filling at
D+1's close and at D's close; neither assumption is reliably conservative, so
the pair is reported as a bracket.
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

from atlas20.backtest.engine import BacktestResult  # noqa: E402
from atlas20.backtest.intraday import (  # noqa: E402
    MISSING_FILL_POLICIES,
    load_hourly_bars,
    observed_fill_mask,
    pre_fill_returns,
)
from atlas20.config import ResearchConfig  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    build_phase_momentum_targets,
)
from atlas20.universe.builder import MarketDataBundle  # noqa: E402

from scripts.run_phase_momentum import (  # noqa: E402
    _load_market,
    _parse_floats,
    _production_result,
    _rolling_worst,
    _yearly_returns,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def _execution_lag_table(
    config: ResearchConfig,
    market: MarketDataBundle,
    built: PhaseMomentumBuildResult,
    index: pd.DatetimeIndex,
    *,
    lags: tuple[int, ...],
    costs: tuple[float, ...],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for lag in lags:
        for cost in costs:
            result = _production_result(
                config,
                market,
                built,
                index,
                cost_bps=cost,
                execution_lag_days=lag,
            )
            rows.append(
                {
                    "execution_lag_days": int(lag),
                    "cost_bps": float(cost),
                    **_metrics_from_returns(result.daily_returns),
                    **_rolling_worst(result.daily_returns),
                }
            )
    return pd.DataFrame(rows)


def _observed_weight_share(result: BacktestResult, observed: pd.DataFrame) -> float:
    """Share of the traded books' gross weight whose fill hour the candles show."""
    index = result.daily_returns.index
    positions = {pd.Timestamp(date): position for position, date in enumerate(index)}
    total = 0.0
    seen = 0.0
    for signal_date, target in result.rebalance_targets.iterrows():
        position = positions.get(pd.Timestamp(signal_date))
        if position is None or position + 1 >= len(index):
            continue
        weights = target.astype(float).abs()
        shown = observed.loc[index[position + 1]].reindex(weights.index, fill_value=False)
        total += float(weights.sum())
        seen += float(weights[shown.astype(bool)].sum())
    return seen / total if total > 0 else float("nan")


def _fill_timing_table(
    config: ResearchConfig,
    market: MarketDataBundle,
    built: PhaseMomentumBuildResult,
    index: pd.DatetimeIndex,
    *,
    hourly: dict[str, pd.DataFrame],
    fill_hours: tuple[int, ...],
    costs: tuple[float, ...],
) -> pd.DataFrame:
    """Metrics for fills ``H`` hours after the signal close, per cost.

    Every fill hour is run under both missing-candle policies, so coins the
    venue does not list are bracketed rather than assumed away.
    """
    daily = market.returns.loc[index]
    closes = market.raw_price.reindex(index=index, columns=daily.columns)
    rows: list[dict[str, object]] = []
    for hours in fill_hours:
        observed = observed_fill_mask(daily, hourly, fill_hours=hours, reference_close=closes)
        for policy in MISSING_FILL_POLICIES:
            pre_fill = pre_fill_returns(
                daily,
                hourly,
                fill_hours=hours,
                missing_fill=policy,
                reference_close=closes,
            )
            for cost in costs:
                result = _production_result(
                    config,
                    market,
                    built,
                    index,
                    cost_bps=cost,
                    pre_fill=pre_fill,
                )
                rows.append(
                    {
                        "fill_hours": int(hours),
                        "missing_hourly": policy,
                        "cost_bps": float(cost),
                        **_metrics_from_returns(result.daily_returns),
                        **_rolling_worst(result.daily_returns),
                        "observed_weight_share": _observed_weight_share(result, observed),
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", default="2,20,50,100")
    parser.add_argument("--lags", default="0,1,2")
    parser.add_argument(
        "--fill-hours",
        default="1,3,6,12",
        help="Intraday fills, in hours after the signal close (the 02:30 UTC refresh makes 3 the central case).",
    )
    parser.add_argument("--hourly-dir", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--yearly-cost-bps", type=float, default=20.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_execution_lag_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    costs = _parse_floats(args.cost_bps)
    lags = tuple(int(item.strip()) for item in args.lags.split(",") if item.strip())
    if not lags or any(lag < 0 for lag in lags):
        raise ValueError("--lags must be a non-empty list of non-negative integers")
    fill_hours = tuple(int(item.strip()) for item in args.fill_hours.split(",") if item.strip())
    if any(not 1 <= hours <= 23 for hours in fill_hours):
        raise ValueError("--fill-hours must be integers within [1, 23]")
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    spec = PhaseMomentumSpec()
    built = build_phase_momentum_targets(market, universe, index, spec=spec)

    summary = _execution_lag_table(config, market, built, index, lags=lags, costs=costs)
    hourly = load_hourly_bars(args.hourly_dir) if fill_hours else {}
    fill_timing = _fill_timing_table(
        config,
        market,
        built,
        index,
        hourly=hourly,
        fill_hours=fill_hours,
        costs=costs,
    )
    yearly = pd.concat(
        [
            _yearly_returns(
                _production_result(
                    config,
                    market,
                    built,
                    index,
                    cost_bps=args.yearly_cost_bps,
                    execution_lag_days=lag,
                ).daily_returns
            ).rename(f"lag_{lag}d")
            for lag in lags
        ],
        axis=1,
    )

    output_dir = ensure_dir(args.output_dir)
    summary.to_csv(output_dir / "summary.csv", index=False)
    fill_timing.to_csv(output_dir / "fill_timing.csv", index=False)
    yearly.to_csv(output_dir / "yearly.csv", index_label="date")
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": list(costs),
        "execution_lag_days": list(lags),
        "fill_hours": list(fill_hours),
        "hourly_dir": str(args.hourly_dir),
        "hourly_coins": sorted(hourly),
        "missing_hourly_policies": {
            "day_close": "coins without a usable candle fill at the execution day's close",
            "prior_close": "coins without a usable candle fill at the signal close",
        },
        "candle_sanity_check": "a day whose 00:00 UTC open is more than 5% from the panel's prior close is unobserved",
        "yearly_cost_bps": args.yearly_cost_bps,
        "strategy": "phase momentum primary spec (PhaseMomentumSpec defaults, PRIMARY_SIGNAL_SPECS)",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = "\n".join(
        [
            "# Phase-Momentum Execution-Delay Sensitivity",
            "",
            "Lag 0 fills at the signal close, which is the production engine default and the",
            "basis of every headline number. Live orders can only go out after CoinMarketCap",
            "publishes that close (after 00:00 UTC) and the 02:30 UTC refresh finishes, so the",
            "real fill sits between lag 0 and lag 1. Lag 1 fills at the next day's close; lag 2",
            "is a stress case. The strategy, universe, and costs are otherwise unchanged.",
            "",
            "## Summary",
            "",
            dataframe_to_markdown(summary),
            "",
            "## Intraday fills from Binance 1-hour candles",
            "",
            "A fill H hours after the signal close credits the move from the close to the fill",
            "to the book held before trading; the new book earns the rest of the day. The daily",
            "refresh starts at 02:30 UTC and finishes within minutes, so 3 hours is the central",
            "case for an automated order. Coins without a usable candle (not listed on Binance,",
            "or a day whose open is more than 5% from the panel's prior close) are bracketed:",
            "`day_close` fills them at the execution day's close, `prior_close` at the signal",
            "close; a later fill can help or hurt, so neither end is a guaranteed bound.",
            "`observed_weight_share` is the share of traded weight the candles cover.",
            "",
            dataframe_to_markdown(fill_timing),
            "",
            f"## Yearly returns at {args.yearly_cost_bps:g} bps",
            "",
            dataframe_to_markdown(yearly.reset_index()),
            "",
        ]
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(summary.to_string(index=False))
    print(fill_timing.to_string(index=False))
    print(f"Wrote execution-lag sensitivity to {output_dir}")


if __name__ == "__main__":
    main()
