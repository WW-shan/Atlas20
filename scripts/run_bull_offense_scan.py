"""Systematic scan of the bull-market offense strategy.

Goal: beat buy-and-hold BTC on TOTAL RETURN. Every candidate is reported
against BTC on the same window, with drawdown and leverage shown so the
trade-off is explicit.
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.backtest.engine import run_backtest  # noqa: E402
from atlas20.config import load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.strategies.bull_offense import build_bull_offense_targets  # noqa: E402
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data  # noqa: E402
from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402


def _uncapped_friction(config):
    """Return frictions suitable for a deliberately concentrated research lane.

    The base config's 35% per-coin cap is a diversification guard for the
    Top-20 book. Applying it here silently turns a one-name strategy into a
    35%-invested portfolio and flatters the BTC benchmark with 65% idle cash.
    """
    friction = config.frictions.model_copy(deep=True)
    friction.max_weight_per_coin = 1.0
    return friction


def _profile(name: str, returns: pd.Series, weights: pd.DataFrame, capital: float) -> dict:
    r = returns.dropna()
    eq = capital * (1 + r).cumprod()
    years = max(len(r) / 365.0, 1e-9)
    total = float(eq.iloc[-1] / capital - 1)
    cagr = float((1 + total) ** (1 / years) - 1)
    vol = float(r.std() * np.sqrt(365))
    maxdd = float((eq / eq.cummax() - 1).min())
    return {
        "strategy": name,
        "total_return": total,
        "final_equity": float(eq.iloc[-1]),
        "cagr": cagr,
        "vol": vol,
        "sharpe": float(r.mean() * 365 / vol) if vol > 0 else 0.0,
        "maxdd": maxdd,
        "calmar": cagr / abs(maxdd) if maxdd < 0 else 0.0,
        "exposure": float((weights.sum(axis=1) > 1e-8).mean()),
        "avg_gross": float(weights.sum(axis=1).mean()),
        "best_year": float((1 + r).resample("YE").prod().max() - 1),
        "worst_year": float((1 + r).resample("YE").prod().min() - 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bull offense scan")
    parser.add_argument("--config", default="config/base.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging("WARNING")
    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    panel, metadata = build_processed_datasets(config, sector_config)
    market = prepare_market_data(panel, metadata, config)
    sector_by_coin = metadata["sector"]
    # NOTE: this deliberately writes *next to* the pipeline report dir, not
    # inside it. `run_research.py` publishes `reports/latest` atomically by
    # replacing the whole directory, so anything living inside it is destroyed
    # on the next pipeline run.
    out = ensure_dir(config.resolve_path(config.paths.reports_dir).parent / "bull_offense_scan")

    # The backtest runs only on [start_timestamp, end_timestamp]; the panel
    # carries an earlier buffer so universe eligibility (history/volume) has
    # enough lookback. Every downstream window must use this trimmed index,
    # otherwise the equity curve includes the pre-window ramp.
    backtest_returns = market.returns.loc[config.start_timestamp : config.end_timestamp]

    # Point-in-time Top-N universe, rebuilt at every weekly rebalance date.
    # The strategy is handed this exact calendar so the universe and the
    # selection loop can never drift onto different schedules.
    weekly_dates = get_rebalance_dates(
        backtest_returns.index, config.start_timestamp, "weekly", "7D"
    )
    universe = build_rebalance_universe(market, weekly_dates, config)
    print(f"Universe: {universe['coin_id'].nunique()} distinct coins ever in Top-{config.universe.universe_size}")

    rows = []
    curves = {}
    diagnostics = {}

    research_friction = _uncapped_friction(config)
    bh = run_backtest(
        "BTC_BUY_HOLD",
        backtest_returns,
        {backtest_returns.index[0]: pd.Series({"bitcoin": 1.0})},
        sector_by_coin,
        research_friction,
        config.initial_capital,
    )
    rows.append(_profile("BTC_BUY_HOLD", bh.daily_returns, bh.weights, config.initial_capital))
    curves["BTC_BUY_HOLD"] = bh.equity_curve

    grid = list(itertools.product(
        [1, 2, 3],          # hold_count
        [14, 21, 30, 45],   # lookback
        [20, 50, 100],      # exit MA window
        [1.0, 1.25, 1.5, 2.0],  # leverage
    ))
    print(f"Running {len(grid)} combinations...", flush=True)

    for hold, lb, ma, lev in grid:
        name = f"BO_h{hold}_lb{lb}_ma{ma}_x{lev:g}"
        built = build_bull_offense_targets(
            market, universe,
            hold_count=hold, frequency="weekly", frequency_value="7D",
            lookback=lb, exit_ma_window=ma,
            max_leverage=lev, leverage_when_strong=lev,
            rebalance_dates=weekly_dates,
        )
        if not built.targets:
            continue
        res = run_backtest(
            name, backtest_returns, built.targets, sector_by_coin,
            research_friction, config.initial_capital,
            leverage_by_date=built.leverage_by_date,
            max_gross_exposure=lev,
        )
        rows.append(_profile(name, res.daily_returns, res.weights, config.initial_capital))
        curves[name] = res.equity_curve
        diagnostics[name] = built.signal_history

    summary = pd.DataFrame(rows).set_index("strategy")
    btc_total = summary.loc["BTC_BUY_HOLD", "total_return"]
    summary["beats_btc"] = summary["total_return"] > btc_total
    summary = summary.sort_values("total_return", ascending=False)
    summary.to_csv(out / "bull_offense_summary.csv")

    equity = pd.DataFrame(curves)
    equity.to_csv(out / "bull_offense_equity_curves.csv")

    # Yearly returns, so a headline number driven by a single lucky year is
    # obvious rather than buried inside one CAGR.
    yearly = equity.resample("YE").last().div(equity.resample("YE").first()).sub(1.0)
    yearly = yearly.loc[:, summary.index]
    yearly.to_csv(out / "bull_offense_yearly_returns.csv")

    # How the whole grid behaves, not just the winner: a strategy family whose
    # median cell also beats BTC is far less likely to be a curve-fit fluke.
    candidates = summary.drop(index="BTC_BUY_HOLD")
    stability = pd.DataFrame(
        {
            "statistic": ["count", "median", "p25", "p75", "min", "max", "share_beating_btc"],
            "total_return": [
                float(len(candidates)),
                float(candidates["total_return"].median()),
                float(candidates["total_return"].quantile(0.25)),
                float(candidates["total_return"].quantile(0.75)),
                float(candidates["total_return"].min()),
                float(candidates["total_return"].max()),
                float(candidates["beats_btc"].mean()),
            ],
            "cagr": [
                float("nan"),
                float(candidates["cagr"].median()),
                float(candidates["cagr"].quantile(0.25)),
                float(candidates["cagr"].quantile(0.75)),
                float(candidates["cagr"].min()),
                float(candidates["cagr"].max()),
                float("nan"),
            ],
            "maxdd": [
                float("nan"),
                float(candidates["maxdd"].median()),
                float(candidates["maxdd"].quantile(0.25)),
                float(candidates["maxdd"].quantile(0.75)),
                float(candidates["maxdd"].min()),
                float(candidates["maxdd"].max()),
                float("nan"),
            ],
        }
    )
    stability.to_csv(out / "bull_offense_stability.csv", index=False)

    # Leverage is a separate robustness dimension. Report each bucket rather
    # than letting a few x2 cells dominate the headline: x2 returns are only
    # meaningful after borrow/funding costs, which this scan intentionally
    # does not model yet.
    candidates_with_leverage = candidates.copy()
    candidates_with_leverage["leverage"] = (
        candidates_with_leverage.index.to_series().str.rsplit("_", n=1).str[-1].str[1:].astype(float)
    )
    leverage_summary = (
        candidates_with_leverage.groupby("leverage", sort=True)
        .agg(
            combinations=("total_return", "size"),
            beating_btc=("beats_btc", "sum"),
            median_total_return=("total_return", "median"),
            median_cagr=("cagr", "median"),
            median_maxdd=("maxdd", "median"),
            best_total_return=("total_return", "max"),
        )
        .reset_index()
    )
    leverage_summary.to_csv(out / "bull_offense_leverage_summary.csv", index=False)

    report = [
        "# Bull Offense Scan",
        "",
        f"Window: {backtest_returns.index.min().date()} to {backtest_returns.index.max().date()}",
        f"BTC buy-and-hold total return: {btc_total*100:.1f}%",
        f"Combinations tested: {len(grid)}",
        f"Candidates beating BTC: {int(summary['beats_btc'].sum())}",
        "",
        "## Yearly returns (top 8 by total return)",
        "",
        dataframe_to_markdown(
            (
                yearly[["BTC_BUY_HOLD", *summary.drop(index="BTC_BUY_HOLD").index[:8]]]
                * 100
            )
            .round(1)
            .reset_index()
        ),
        "",
        "## Parameter-grid robustness",
        "",
        dataframe_to_markdown(stability),
        "",
        "## Leverage robustness",
        "",
        dataframe_to_markdown(leverage_summary),
        "",
        "## Top 10 unlevered (x1) by total return",
        "",
        dataframe_to_markdown(
            candidates_with_leverage[candidates_with_leverage["leverage"] == 1.0]
            .sort_values("total_return", ascending=False)
            .head(10)
            .reset_index()
        ),
        "",
        "## Top 20 by total return",
        "",
        dataframe_to_markdown(summary.head(20).reset_index()),
        "",
        "## Best risk-adjusted among BTC-beaters",
        "",
        dataframe_to_markdown(
            summary[summary["beats_btc"]].sort_values("sharpe", ascending=False).head(10).reset_index()
        ),
        "",
    ]
    (out / "bull_offense_report.md").write_text("\n".join(report), encoding="utf-8")

    cols = ["total_return", "cagr", "sharpe", "maxdd", "calmar", "avg_gross", "exposure"]
    print("\n=== BTC benchmark ===")
    print(summary.loc[["BTC_BUY_HOLD"], cols].to_string())
    print("\n=== Top 15 by TOTAL RETURN ===")
    print(summary.head(15)[cols + ["beats_btc"]].to_string())
    print(f"\nBeating BTC: {int(summary['beats_btc'].sum())} / {len(summary)-1}")
    print(f"Report: {out}")


if __name__ == "__main__":
    main()
