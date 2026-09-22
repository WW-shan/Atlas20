"""Persist and stress-test the unlevered bull-offense finalist.

The candidate below is the one that survived the no-leverage ablation
(``scripts/run_no_leverage_ablation.py``), the bull-offense grid
(``scripts/run_bull_offense_scan.py``) and an ad-hoc volatility-target grid
that previously existed only in ``/tmp``.  This script makes it reproducible
inside the repository and records the evidence needed to decide whether it is
safe enough for live trading:

  structure
  ---------
  point-in-time Top-N universe, weekly rebalance
    -> BTC 50-day trend gate       (flat whenever BTC is below its own MA)
    -> hold the single strongest  30-day absolute + relative-to-BTC momentum
    -> daily asset stop on the holding's own 50-day MA
       (exit at T+1, no re-entry before the next scheduled rebalance)
    -> 80% annualized target-volatility scaling, capped at 1.0x gross

Everything is strictly unlevered: gross exposure is hard-capped at 1.0 and
the run raises if any candidate ever exceeds it.

Outputs (in ``reports/bull_offense_finalist`` by default):

  sweep_summary.csv        structural grid x target-vol, at the base cost
  cost_sensitivity.csv     20/50/100/150 bps for the ranked finalists
  finalist_metrics.csv     headline metrics for the champion at every cost
  finalist_yearly.csv      calendar-year returns, strategy vs BTC
  finalist_rolling.csv     monthly rolling-start comparison vs BTC
  finalist_contribution.csv per-asset additive contribution of the champion
  finalist_daily_returns.csv
  finalist_equity.csv
  run_manifest.json        data fingerprint + parameters actually used
  report.md                human-readable summary
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.analytics.metrics import compute_summary_metrics  # noqa: E402
from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.backtest.engine import BacktestResult, run_backtest  # noqa: E402
from atlas20.config import ResearchConfig, load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import absolute_trend_mask, realized_volatility  # noqa: E402
from atlas20.strategies.bull_offense import build_bull_offense_targets  # noqa: E402
from atlas20.strategies.overlays import apply_daily_asset_stop_overlay  # noqa: E402
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)

# Champion parameters, fixed so the persisted report can never silently drift
# onto a different cell of the grid.
FINALIST = {
    "hold_count": 1,
    "lookback": 30,
    "btc_trend_ma": 50,
    "asset_stop_ma": 50,
    "target_vol": 0.8,
    "vol_window": 30,
    "frequency": "weekly",
    "frequency_value": "7D",
}

SWEEP_HOLD = (1, 2, 3)
SWEEP_LOOKBACK = (14, 21, 30, 45)
SWEEP_BTC_MA = (20, 50, 100)
SWEEP_ASSET_MA = (0, 50, 100)  # 0 == no per-asset stop
SWEEP_TARGET_VOL = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
COST_LEVELS_BPS = (20.0, 50.0, 100.0, 150.0)
# Headline rolling table only counts windows long enough to be informative;
# every window (>= 30 days) is still written out separately.
ROLLING_MIN_DAYS = 180

# Worker-process globals, seeded before the fork so every task reuses one copy
# of the panel instead of re-reading CSVs.
_WORKER: dict[str, object] = {}


def _parse_cost_levels(value: str) -> tuple[float, ...]:
    """Parse the cost grid, in bps per unit of traded notional.

    A full switch from one coin to another trades twice the capital (sell the
    old name, buy the new one), so the engine charges ``2 x cost`` on a switch.
    Enter the single-side fee + slippage here, not the round-trip number.
    """
    try:
        levels = tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError("cost levels must be comma-separated numbers") from exc
    if not levels:
        raise ValueError("at least one cost level is required")
    if any(level < 0.0 for level in levels):
        raise ValueError("cost levels must be non-negative")
    return levels


def _fingerprint(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "exists": True,
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def _prepare(config: ResearchConfig) -> dict[str, object]:
    """Load the panel and build the point-in-time universe once."""
    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    panel, metadata = build_processed_datasets(config, sector_config, persist=False)
    market = prepare_market_data(panel, metadata, config)
    backtest_returns = market.returns.loc[config.start_timestamp : config.end_timestamp]
    weekly_dates = get_rebalance_dates(
        backtest_returns.index, config.start_timestamp, "7D", "7D"
    )
    universe = build_rebalance_universe(market, weekly_dates, config)
    return {
        "config": config,
        "market": market,
        "universe": universe,
        "weekly_dates": weekly_dates,
        "backtest_returns": backtest_returns,
        "sector_by_coin": metadata["sector"],
        "vol_frame": realized_volatility(market.price, window=FINALIST["vol_window"]),
        "trend_cache": {},
    }


def _research_friction(config: ResearchConfig, total_cost_bps: float):
    """Concentrated research lane: no per-coin / per-sector caps, split cost."""
    friction = config.frictions.model_copy(deep=True)
    friction.max_weight_per_coin = 1.0
    friction.max_weight_per_sector = 1.0
    friction.fee_bps = float(total_cost_bps) / 2.0
    friction.slippage_bps = float(total_cost_bps) / 2.0
    return friction


def _structural_targets(
    state: dict[str, object],
    *,
    hold_count: int,
    lookback: int,
    btc_ma: int,
    asset_ma: int,
) -> dict[pd.Timestamp, pd.Series]:
    """Build the rebalance targets, cached per structural cell."""
    cache: dict[tuple[int, int, int, int], dict[pd.Timestamp, pd.Series]] = state["trend_cache"]  # type: ignore[assignment]
    key = (hold_count, lookback, btc_ma, asset_ma)
    if key in cache:
        return cache[key]

    market: MarketDataBundle = state["market"]  # type: ignore[assignment]
    built = build_bull_offense_targets(
        market,
        state["universe"],  # type: ignore[arg-type]
        hold_count=hold_count,
        frequency=FINALIST["frequency"],
        frequency_value=FINALIST["frequency_value"],
        lookback=lookback,
        exit_ma_window=btc_ma,
        max_leverage=1.0,
        leverage_when_strong=1.0,
        rebalance_dates=state["weekly_dates"],  # type: ignore[arg-type]
    )
    targets = built.targets
    if asset_ma > 0:
        targets = apply_daily_asset_stop_overlay(
            targets, absolute_trend_mask(market.price, ma_window=asset_ma)
        )
    cache[key] = targets
    return targets


def _vol_exposure(
    targets: dict[pd.Timestamp, pd.Series],
    vol_frame: pd.DataFrame,
    target_vol: float,
) -> dict[pd.Timestamp, float]:
    """Scale each rebalance's gross exposure toward ``target_vol``.

    The scaling may only de-risk: exposure is capped at 1.0 because the user
    explicitly does not want leverage in the research lane.
    """
    exposure: dict[pd.Timestamp, float] = {}
    for date, target in targets.items():
        date = pd.Timestamp(date)
        if target is None or target.empty or date not in vol_frame.index:
            exposure[date] = 0.0
            continue
        positions = target[target > 0]
        scales = [
            float(target_vol) / float(vol_frame.loc[date, coin])
            for coin in positions.index
            if coin in vol_frame.columns
            and pd.notna(vol_frame.loc[date, coin])
            and float(vol_frame.loc[date, coin]) > 0.0
        ]
        if not scales:
            exposure[date] = 1.0
        else:
            exposure[date] = min(1.0, sum(scales) / len(scales))
    return exposure


def _run(
    config: ResearchConfig,
    state: dict[str, object],
    *,
    hold_count: int,
    lookback: int,
    btc_ma: int,
    asset_ma: int,
    target_vol: float,
    cost_bps: float,
    name: str,
) -> BacktestResult:
    targets = _structural_targets(
        state,
        hold_count=hold_count,
        lookback=lookback,
        btc_ma=btc_ma,
        asset_ma=asset_ma,
    )
    exposure = _vol_exposure(
        targets, state["vol_frame"],  # type: ignore[arg-type]
        target_vol,
    )
    return run_backtest(
        name,
        state["backtest_returns"],  # type: ignore[arg-type]
        targets,
        state["sector_by_coin"],  # type: ignore[arg-type]
        _research_friction(config, cost_bps),
        config.initial_capital,
        gross_target_exposure=1.0,
        leverage_by_date=exposure,
        max_gross_exposure=1.0,
    )


def _btc_result(state: dict[str, object], config: ResearchConfig, cost_bps: float) -> BacktestResult:
    returns: pd.DataFrame = state["backtest_returns"]  # type: ignore[assignment]
    return run_backtest(
        "BTC_BUY_HOLD",
        returns,
        {returns.index[0]: pd.Series({"bitcoin": 1.0})},
        state["sector_by_coin"],  # type: ignore[arg-type]
        _research_friction(config, cost_bps),
        config.initial_capital,
    )


def _metrics_row(
    result: BacktestResult,
    config: ResearchConfig,
    *,
    total_cost_bps: float,
    **params: object,
) -> dict[str, object]:
    metrics = compute_summary_metrics(result, config.annualization_days)
    gross = result.weights.sum(axis=1)
    return {
        **params,
        **metrics,
        "total_cost_bps": float(total_cost_bps),
        "avg_gross_exposure": float(gross.mean()),
        "max_gross_exposure": float(gross.max()),
        "pct_days_flat": float((gross <= 1e-8).mean()),
    }


def _neighbourhood_stats(sweep: pd.DataFrame) -> pd.DataFrame:
    """Score every sweep cell by how its immediate neighbours behave.

    A single cell with a great Sharpe is not evidence; a cell whose
    +/-1-step neighbours (lookback, BTC MA, asset stop, target vol, hold
    count) also beat BTC is much harder to produce by fitting one lucky
    parameter combination. The grid values here are the exact ones the sweep
    enumerates, so a "neighbour" is always a real, tested cell.
    """
    if sweep.empty:
        return sweep

    axes: dict[str, tuple[float, ...]] = {
        "hold_count": tuple(sorted(SWEEP_HOLD)),
        "lookback": tuple(sorted(SWEEP_LOOKBACK)),
        "btc_ma": tuple(sorted(SWEEP_BTC_MA)),
        "asset_ma": tuple(sorted(SWEEP_ASSET_MA)),
        "target_vol": tuple(sorted(SWEEP_TARGET_VOL)),
    }
    lookup = sweep.set_index(
        ["hold_count", "lookback", "btc_ma", "asset_ma", "target_vol"]
    )
    rows: list[dict[str, object]] = []
    for key, _ in lookup.iterrows():
        current = dict(zip(lookup.index.names, key))
        neighbour_keys = []
        for axis, values in axes.items():
            ordered = list(values)
            position = ordered.index(current[axis])
            for offset in (-1, 1):
                candidate_position = position + offset
                if 0 <= candidate_position < len(ordered):
                    neighbour = dict(current)
                    neighbour[axis] = ordered[candidate_position]
                    neighbour_keys.append(tuple(neighbour[name] for name in lookup.index.names))
        neighbour_keys = [candidate for candidate in dict.fromkeys(neighbour_keys) if candidate in lookup.index]
        if not neighbour_keys:
            rows.append({"neighbour_count": 0, "neighbour_beats_share": float("nan"), "neighbour_median_sharpe": float("nan")})
            continue
        neighbours = lookup.loc[neighbour_keys]
        rows.append(
            {
                "neighbour_count": len(neighbour_keys),
                "neighbour_beats_share": float(neighbours["beats_btc_total"].mean()),
                "neighbour_median_sharpe": float(neighbours["sharpe"].median()),
                "neighbour_median_total_return": float(neighbours["total_return"].median()),
            }
        )

    stats = pd.DataFrame(rows, index=lookup.index).reset_index()
    merged = sweep.merge(stats, on=list(lookup.index.names), how="left")
    # A plateau cell beats BTC itself *and* is surrounded by cells that do too.
    merged["plateau_score"] = (
        merged["neighbour_beats_share"].fillna(0.0) * 0.5
        + merged["neighbour_median_sharpe"].fillna(0.0) / 2.0
    )
    return merged


# ---------------------------------------------------------------- sweep tasks


def _sweep_task(task: dict[str, object]) -> dict[str, object]:
    state = _WORKER["state"]
    config = _WORKER["config"]
    results: list[dict[str, object]] = []
    sweep_cost_bps = float(task.get("cost_bps", 20.0))
    for target_vol in task["target_vols"]:  # type: ignore[index]
        result = _run(
            config,  # type: ignore[arg-type]
            state,  # type: ignore[arg-type]
            hold_count=task["hold_count"],  # type: ignore[arg-type]
            lookback=task["lookback"],  # type: ignore[arg-type]
            btc_ma=task["btc_ma"],  # type: ignore[arg-type]
            asset_ma=task["asset_ma"],  # type: ignore[arg-type]
            target_vol=target_vol,
            cost_bps=sweep_cost_bps,
            name="sweep",
        )
        results.append(
            _metrics_row(
                result,
                config,  # type: ignore[arg-type]
                total_cost_bps=sweep_cost_bps,
                hold_count=task["hold_count"],
                lookback=task["lookback"],
                btc_ma=task["btc_ma"],
                asset_ma=task["asset_ma"],
                target_vol=target_vol,
            )
        )
    return {"rows": results}


def _cost_task(task: dict[str, object]) -> dict[str, object]:
    state = _WORKER["state"]
    config = _WORKER["config"]
    rows: list[dict[str, object]] = []
    for cost_bps in task["cost_levels"]:  # type: ignore[index]
        result = _run(
            config,  # type: ignore[arg-type]
            state,  # type: ignore[arg-type]
            hold_count=task["hold_count"],  # type: ignore[arg-type]
            lookback=task["lookback"],  # type: ignore[arg-type]
            btc_ma=task["btc_ma"],  # type: ignore[arg-type]
            asset_ma=task["asset_ma"],  # type: ignore[arg-type]
            target_vol=task["target_vol"],
            cost_bps=cost_bps,
            name="cost",
        )
        rows.append(
            _metrics_row(
                result,
                config,  # type: ignore[arg-type]
                total_cost_bps=cost_bps,
                hold_count=task["hold_count"],
                lookback=task["lookback"],
                btc_ma=task["btc_ma"],
                asset_ma=task["asset_ma"],
                target_vol=task["target_vol"],
            )
        )
    return {"rows": rows}


def _run_pool(tasks: list[dict[str, object]], worker, max_workers: int) -> list[dict[str, object]]:
    if max_workers <= 1:
        return [worker(task) for task in tasks]
    context = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(max_workers=max_workers, mp_context=context) as pool:
        return list(pool.map(worker, tasks, chunksize=1))


# ------------------------------------------------------------------ analytics


def _rolling_starts(
    strategy: pd.Series,
    btc: pd.Series,
    *,
    cost_bps: float,
    min_days: int = 180,
) -> list[dict[str, object]]:
    frame = pd.DataFrame({"strategy": strategy, "btc": btc}).dropna()
    if frame.empty:
        return []
    months = pd.date_range(
        frame.index.min().normalize().replace(day=1),
        frame.index.max().normalize().replace(day=1),
        freq="MS",
    )
    rows: list[dict[str, object]] = []
    for start in months:
        window = frame.loc[frame.index >= start]
        if len(window) < min_days:
            continue
        strat = (1.0 + window["strategy"]).cumprod()
        bench = (1.0 + window["btc"]).cumprod()
        ratio = strat / bench
        years = max(len(window) / 365.0, 1e-9)
        total = float(strat.iloc[-1]) - 1.0
        rows.append(
            {
                "cost_bps": float(cost_bps),
                "start": start.date().isoformat(),
                "multiple": float(strat.iloc[-1]),
                "btc_multiple": float(bench.iloc[-1]),
                "ratio": float(strat.iloc[-1] / bench.iloc[-1]),
                "cagr": float((1.0 + total) ** (1.0 / years) - 1.0),
                "maxdd": float((strat / strat.cummax() - 1.0).min()),
                "min_ratio": float(ratio.min()),
                "days": int(len(window)),
            }
        )
    return rows


def _yearly(result: BacktestResult, btc: BacktestResult) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "strategy": (1.0 + result.daily_returns).resample("YE").prod() - 1.0,
            "btc": (1.0 + btc.daily_returns).resample("YE").prod() - 1.0,
        }
    )
    frame["excess"] = frame["strategy"] - frame["btc"]
    frame["beats_btc"] = frame["strategy"] > frame["btc"]
    frame.index = frame.index.year
    frame.index.name = "year"
    return frame


def _contribution(result: BacktestResult, returns: pd.DataFrame) -> pd.DataFrame:
    """Additive per-asset contribution to the strategy's gross return.

    ``weights.loc[t]`` is the book held through day ``t`` and
    ``daily_returns`` is built from ``(weights * asset_return).sum()``, so the
    element-wise product sums back to the pre-cost gross return.
    """
    weights = result.weights.reindex(columns=returns.columns).fillna(0.0)
    asset_returns = returns.reindex(index=weights.index, columns=weights.columns).fillna(0.0)
    contribution = (weights * asset_returns).sum(axis=0)
    holding_days = (weights.abs() > 1e-8).sum(axis=0)
    frame = pd.DataFrame(
        {
            "contribution": contribution,
            "holding_days": holding_days,
            "share_of_gross": contribution / contribution.sum() if contribution.sum() != 0 else np.nan,
        }
    )
    frame.index.name = "coin_id"
    return frame.sort_values("contribution", ascending=False)


def _subperiods(returns: pd.Series) -> pd.DataFrame:
    periods = (
        ("2021", "2021-01-01", "2021-12-31"),
        ("2022", "2022-01-01", "2022-12-31"),
        ("2023", "2023-01-01", "2023-12-31"),
        ("2024", "2024-01-01", "2024-12-31"),
        ("2025", "2025-01-01", "2025-12-31"),
        ("2026_ytd", "2026-01-01", None),
        ("2021_2022", "2021-01-01", "2022-12-31"),
        ("2023_onward", "2023-01-01", None),
    )
    rows = []
    for label, start, end in periods:
        window = returns.loc[start:end] if end is None else returns.loc[start:end]
        if window.empty:
            continue
        eq = (1.0 + window).cumprod()
        years = max(len(window) / 365.0, 1e-9)
        total = float(eq.iloc[-1]) - 1.0
        vol = float(window.std(ddof=0) * np.sqrt(365))
        rows.append(
            {
                "period": label,
                "days": int(len(window)),
                "total_return": total,
                "cagr": float((1.0 + total) ** (1.0 / years) - 1.0),
                "sharpe": float(window.mean() * 365 / vol) if vol > 0 else 0.0,
                "max_drawdown": float((eq / eq.cummax() - 1.0).min()),
            }
        )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--top-cost-candidates", type=int, default=10)
    parser.add_argument(
        "--rolling-min-days",
        type=int,
        default=ROLLING_MIN_DAYS,
        help="Minimum length for a rolling-start window to enter the headline table.",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help=(
            "Override the backtest start date (YYYY-MM-DD). The 2021 leg of "
            "this window is an extreme outlier for the whole Top20 universe, so "
            "a 2022-01-01 start is the honest out-of-sample-style check."
        ),
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Override the backtest end date (YYYY-MM-DD). Defaults to the latest panel date.",
    )
    parser.add_argument("--skip-sweep", action="store_true")
    parser.add_argument(
        "--sweep-cost-bps",
        type=float,
        default=20.0,
        help=(
            "Single-side cost used to rank the 648-cell sweep. Lower it to match "
            "a cheaper venue: the ranking, not just the headline number, depends "
            "on trading cost because turnover varies a lot across cells."
        ),
    )
    parser.add_argument(
        "--cost-bps",
        default=",".join(f"{level:g}" for level in COST_LEVELS_BPS),
        help=(
            "Comma-separated single-side cost levels in bps (fee + slippage). "
            "A switch between two coins trades twice the capital, so the engine "
            "charges 2x this number on a switch. Example for a 0.08%% net taker "
            "fee after rebate plus 3 bps slippage: --cost-bps 11"
        ),
    )
    # The champion is a risk dial rather than a single magic cell: raising
    # target_vol buys return at the cost of drawdown, and a slower asset stop
    # trades a little return for a materially shallower drawdown. These
    # overrides let an alternative be re-validated end to end (sweep
    # neighbourhood, cost stress, rolling starts) without editing the file.
    parser.add_argument("--champion-hold", type=int, default=FINALIST["hold_count"])
    parser.add_argument("--champion-lookback", type=int, default=FINALIST["lookback"])
    parser.add_argument("--champion-btc-ma", type=int, default=FINALIST["btc_trend_ma"])
    parser.add_argument("--champion-asset-ma", type=int, default=FINALIST["asset_stop_ma"])
    parser.add_argument("--champion-target-vol", type=float, default=FINALIST["target_vol"])
    args = parser.parse_args()

    cost_levels = _parse_cost_levels(args.cost_bps)

    config = load_config(args.config)
    if args.start_date or args.end_date:
        config = config.model_copy(deep=True)
        if args.start_date:
            config.start_date = args.start_date
        if args.end_date:
            config.end_date = args.end_date
    configure_logging("WARNING")
    state = _prepare(config)
    backtest_returns: pd.DataFrame = state["backtest_returns"]  # type: ignore[assignment]
    print(
        f"Window {backtest_returns.index.min().date()} .. {backtest_returns.index.max().date()} "
        f"({len(backtest_returns)} days), "
        f"{state['universe']['coin_id'].nunique()} distinct coins ever in the Top-N pool",  # type: ignore[index]
        flush=True,
    )

    report_dir = ensure_dir(
        args.output_dir
        if args.output_dir is not None
        else config.resolve_path(config.paths.reports_dir).parent / "bull_offense_finalist"
    )

    sweep = pd.DataFrame()
    if not args.skip_sweep:
        tasks = [
            {
                "hold_count": hold,
                "lookback": lookback,
                "btc_ma": btc_ma,
                "asset_ma": asset_ma,
                "target_vols": list(SWEEP_TARGET_VOL),
                "cost_bps": float(args.sweep_cost_bps),
            }
            for hold in SWEEP_HOLD
            for lookback in SWEEP_LOOKBACK
            for btc_ma in SWEEP_BTC_MA
            for asset_ma in SWEEP_ASSET_MA
        ]
        cells = len(tasks) * len(SWEEP_TARGET_VOL)
        print(
            f"Sweeping {cells} structural x vol cells at {args.sweep_cost_bps:g} bps...",
            flush=True,
        )
        _WORKER["state"] = state
        _WORKER["config"] = config
        results = _run_pool(tasks, _sweep_task, args.workers)
        sweep = pd.DataFrame([row for item in results for row in item["rows"]])
        sweep["beats_btc_total"] = sweep["total_return"] > float(
            _btc_result(state, config, float(args.sweep_cost_bps)).daily_returns.pipe(
                lambda series: (1.0 + series).prod() - 1.0
            )
        )
        sweep = _neighbourhood_stats(sweep)
        sweep = sweep.sort_values(["sharpe", "cagr"], ascending=False).reset_index(drop=True)
        sweep.to_csv(report_dir / "sweep_summary.csv", index=False)
        print(f"Wrote {len(sweep)} sweep rows to {report_dir / 'sweep_summary.csv'}", flush=True)

    # ------------------------------------------------------------ finalists
    champion_row = {
        "hold_count": args.champion_hold,
        "lookback": args.champion_lookback,
        "btc_ma": args.champion_btc_ma,
        "asset_ma": args.champion_asset_ma,
        "target_vol": args.champion_target_vol,
    }
    if champion_row != {
        "hold_count": FINALIST["hold_count"],
        "lookback": FINALIST["lookback"],
        "btc_ma": FINALIST["btc_trend_ma"],
        "asset_ma": FINALIST["asset_stop_ma"],
        "target_vol": FINALIST["target_vol"],
    }:
        print(f"Champion overridden by CLI: {champion_row}", flush=True)

    def _as_candidate(row: pd.Series) -> dict[str, object]:
        return {
            "hold_count": int(row["hold_count"]),
            "lookback": int(row["lookback"]),
            "btc_ma": int(row["btc_ma"]),
            "asset_ma": int(row["asset_ma"]),
            "target_vol": float(row["target_vol"]),
        }

    # Cost stress is far more expensive per candidate than the 20 bps sweep,
    # so it runs on a deliberately chosen set rather than the whole grid:
    # the champion, the best cells by Sharpe, the best cells by raw return
    # (highest-skill but often highest-turnover), and the champion's own
    # immediate neighbours so a fragile single cell cannot hide.
    candidates: list[dict[str, object]] = [champion_row]
    if not sweep.empty:
        ranked_sets = [
            sweep.sort_values(["sharpe", "cagr"], ascending=False).head(args.top_cost_candidates),
            sweep.sort_values(["total_return", "sharpe"], ascending=False).head(args.top_cost_candidates),
        ]
        for _, row in pd.concat(ranked_sets).iterrows():
            candidate = _as_candidate(row)
            if candidate not in candidates:
                candidates.append(candidate)

        neighbourhood = pd.DataFrame()
        for axis, values in (
            ("lookback", SWEEP_LOOKBACK),
            ("btc_ma", SWEEP_BTC_MA),
            ("asset_ma", SWEEP_ASSET_MA),
            ("target_vol", SWEEP_TARGET_VOL),
        ):
            ordered = list(values)
            position = ordered.index(champion_row[axis])
            for offset in (0, -1, 1):
                candidate_position = position + offset
                if not 0 <= candidate_position < len(ordered):
                    continue
                slice_frame = sweep[
                    (sweep["hold_count"] == champion_row["hold_count"])
                    & (sweep[axis] == ordered[candidate_position])
                ]
                for other_axis, other_value in (
                    ("lookback", champion_row["lookback"]),
                    ("btc_ma", champion_row["btc_ma"]),
                    ("asset_ma", champion_row["asset_ma"]),
                    ("target_vol", champion_row["target_vol"]),
                ):
                    if other_axis != axis:
                        slice_frame = slice_frame[slice_frame[other_axis] == other_value]
                neighbourhood = pd.concat([neighbourhood, slice_frame])
        for _, row in neighbourhood.iterrows():
            candidate = _as_candidate(row)
            if candidate not in candidates:
                candidates.append(candidate)

    cost_tasks = [{**candidate, "cost_levels": list(cost_levels)} for candidate in candidates]
    print(f"Cost-stressing {len(cost_tasks)} candidates x {len(cost_levels)} costs...", flush=True)
    _WORKER["state"] = state
    _WORKER["config"] = config
    cost_results = _run_pool(cost_tasks, _cost_task, args.workers)
    cost = pd.DataFrame([row for item in cost_results for row in item["rows"]])

    btc_by_cost = {
        cost_bps: _btc_result(state, config, cost_bps) for cost_bps in cost_levels
    }
    cost["btc_total_return"] = cost["total_cost_bps"].map(
        {cost_bps: float((1.0 + res.daily_returns).prod() - 1.0) for cost_bps, res in btc_by_cost.items()}
    )
    cost["beats_btc"] = cost["total_return"] > cost["btc_total_return"]
    cost = cost.sort_values(["target_vol", "total_cost_bps"]).reset_index(drop=True)
    cost.to_csv(report_dir / "cost_sensitivity.csv", index=False)

    # ------------------------------------------------------- risk/return frontier
    # Every cost-stressed candidate, seen at the base cost and under the
    # harshest cost assumption. The frontier keeps the cells where no other
    # candidate is both higher-returning and shallower in drawdown, so the
    # champion can be judged against the alternatives that actually matter.
    key_columns = ["hold_count", "lookback", "btc_ma", "asset_ma", "target_vol"]
    # "Base" is the cheapest level the user asked for and "stress" is the most
    # expensive one, so the frontier stays meaningful for any custom --cost-bps.
    base_level = min(cost_levels)
    stress_level = max(cost_levels)
    base_cost = cost[cost["total_cost_bps"] == base_level].set_index(key_columns)
    stress_cost = cost[cost["total_cost_bps"] == stress_level].set_index(key_columns)
    frontier = base_cost[
        ["total_return", "cagr", "sharpe", "max_drawdown", "calmar", "annualized_turnover", "avg_gross_exposure"]
    ].join(
        stress_cost[["total_return", "sharpe", "max_drawdown"]].rename(
            columns=lambda column: f"stress{stress_level:g}_{column}"
        )
    )
    frontier = frontier.sort_values("total_return", ascending=False)
    pareto_flags = []
    for _, row in frontier.iterrows():
        dominated = (
            (frontier["total_return"] >= row["total_return"] + 1e-12)
            & (frontier["max_drawdown"] >= row["max_drawdown"] - 1e-12)
            & (
                (frontier["total_return"] > row["total_return"] + 1e-12)
                | (frontier["max_drawdown"] > row["max_drawdown"] + 1e-12)
            )
        ).any()
        pareto_flags.append(not dominated)
    frontier["pareto"] = pareto_flags
    frontier.reset_index().to_csv(report_dir / "frontier.csv", index=False)

    # ------------------------------------------------- champion deep dive
    champion_by_cost: dict[float, BacktestResult] = {}
    for cost_bps in cost_levels:
        champion_by_cost[cost_bps] = _run(
            config,
            state,
            hold_count=champion_row["hold_count"],  # type: ignore[arg-type]
            lookback=champion_row["lookback"],  # type: ignore[arg-type]
            btc_ma=champion_row["btc_ma"],  # type: ignore[arg-type]
            asset_ma=champion_row["asset_ma"],  # type: ignore[arg-type]
            target_vol=champion_row["target_vol"],  # type: ignore[arg-type]
            cost_bps=cost_bps,
            name=f"BO_finalist_{cost_bps:g}bps",
        )

    peak_gross = max(float(res.weights.sum(axis=1).max()) for res in champion_by_cost.values())
    sweep_peak = float(sweep["max_gross_exposure"].max()) if not sweep.empty else 0.0
    cost_peak = float(cost["max_gross_exposure"].max()) if not cost.empty else 0.0
    if max(peak_gross, sweep_peak, cost_peak) > 1.0 + 1e-9:
        raise AssertionError(
            f"unlevered guarantee violated: peak gross exposure "
            f"{max(peak_gross, sweep_peak, cost_peak):.6f} > 1.0"
        )

    finalist_metrics = pd.DataFrame(
        [
            _metrics_row(
                res,
                config,
                total_cost_bps=cost_bps,
                **champion_row,
            )
            for cost_bps, res in sorted(champion_by_cost.items())
        ]
    )
    btc_metrics = pd.DataFrame(
        [
            _metrics_row(
                res,
                config,
                total_cost_bps=cost_bps,
                hold_count=0,
                lookback=0,
                btc_ma=0,
                asset_ma=0,
                target_vol=1.0,
            )
            for cost_bps, res in sorted(btc_by_cost.items())
        ]
    )
    finalist_metrics.to_csv(report_dir / "finalist_metrics.csv", index=False)
    btc_metrics.to_csv(report_dir / "btc_metrics.csv", index=False)

    base = champion_by_cost[base_level]
    base_btc = btc_by_cost[base_level]
    yearly = _yearly(base, base_btc)
    yearly.to_csv(report_dir / "finalist_yearly.csv")

    rolling_rows: list[dict[str, object]] = []
    rolling_all_rows: list[dict[str, object]] = []
    for cost_bps in cost_levels:
        rolling_rows.extend(
            _rolling_starts(
                champion_by_cost[cost_bps].daily_returns,
                base_btc.daily_returns,
                cost_bps=cost_bps,
                min_days=args.rolling_min_days,
            )
        )
        rolling_all_rows.extend(
            _rolling_starts(
                champion_by_cost[cost_bps].daily_returns,
                base_btc.daily_returns,
                cost_bps=cost_bps,
                min_days=30,
            )
        )
    rolling = pd.DataFrame(rolling_rows)
    rolling.to_csv(report_dir / "finalist_rolling.csv", index=False)
    pd.DataFrame(rolling_all_rows).to_csv(report_dir / "finalist_rolling_all_windows.csv", index=False)

    contribution = _contribution(base, backtest_returns.reindex(columns=base.weights.columns))
    contribution.to_csv(report_dir / "finalist_contribution.csv")

    subperiods = _subperiods(base.daily_returns)
    btc_subperiods = _subperiods(base_btc.daily_returns).rename(
        columns={
            "total_return": "btc_total_return",
            "cagr": "btc_cagr",
            "sharpe": "btc_sharpe",
            "max_drawdown": "btc_max_drawdown",
        }
    )
    subperiods = subperiods.merge(
        btc_subperiods[["period", "btc_total_return", "btc_cagr", "btc_sharpe", "btc_max_drawdown"]],
        on="period",
        how="left",
    )
    subperiods["excess_total_return"] = subperiods["total_return"] - subperiods["btc_total_return"]
    subperiods.to_csv(report_dir / "finalist_subperiods.csv", index=False)

    daily = pd.DataFrame(
        {
            f"strategy_{cost_bps:g}bps": champion_by_cost[cost_bps].daily_returns
            for cost_bps in cost_levels
        }
    )
    daily["btc"] = base_btc.daily_returns
    daily.to_csv(report_dir / "finalist_daily_returns.csv")

    equity = pd.DataFrame(
        {
            f"strategy_{cost_bps:g}bps": champion_by_cost[cost_bps].equity_curve
            / config.initial_capital
            for cost_bps in cost_levels
        }
    )
    equity["btc"] = base_btc.equity_curve / config.initial_capital
    equity.to_csv(report_dir / "finalist_equity.csv")

    rolling_all = pd.DataFrame(rolling_all_rows)
    rolling_summary_all = (
        rolling_all.groupby("cost_bps")
        .agg(
            windows=("ratio", "size"),
            win_rate_vs_btc=("ratio", lambda s: float((s > 1.0).mean())),
            worst_ratio=("ratio", "min"),
            median_ratio=("ratio", "median"),
            median_cagr=("cagr", "median"),
            median_maxdd=("maxdd", "median"),
        )
        .reset_index()
    )
    rolling_summary_all.to_csv(report_dir / "finalist_rolling_summary_all_windows.csv", index=False)

    rolling_summary = (
        rolling.groupby("cost_bps")
        .agg(
            windows=("ratio", "size"),
            win_rate_vs_btc=("ratio", lambda s: float((s > 1.0).mean())),
            worst_ratio=("ratio", "min"),
            median_ratio=("ratio", "median"),
            median_cagr=("cagr", "median"),
            median_maxdd=("maxdd", "median"),
        )
        .reset_index()
    )
    rolling_summary.to_csv(report_dir / "finalist_rolling_summary.csv", index=False)

    top_contrib = contribution.head(10).reset_index().assign(
        contribution_pct=lambda frame: (frame["contribution"] * 100).round(1),
        share_of_gross_pct=lambda frame: (frame["share_of_gross"] * 100).round(1),
    )
    assert "coin_id" in top_contrib.columns

    if sweep.empty:
        champion_plateau = float("nan")
        champion_neighbour_share = float("nan")
        champion_neighbour_sharpe = float("nan")
    else:
        champion_mask = (
            (sweep["hold_count"] == champion_row["hold_count"])
            & (sweep["lookback"] == champion_row["lookback"])
            & (sweep["btc_ma"] == champion_row["btc_ma"])
            & (sweep["asset_ma"] == champion_row["asset_ma"])
            & (sweep["target_vol"] == champion_row["target_vol"])
        )
        champion_cell = sweep[champion_mask].iloc[0]
        champion_plateau = float(champion_cell["plateau_score"])
        champion_neighbour_share = float(champion_cell["neighbour_beats_share"])
        champion_neighbour_sharpe = float(champion_cell["neighbour_median_sharpe"])
    manifest = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "window": {
            "start": backtest_returns.index.min().isoformat(),
            "end": backtest_returns.index.max().isoformat(),
            "days": int(len(backtest_returns)),
        },
        "finalist": {
            **FINALIST,
            "max_gross_exposure": 1.0,
            "leverage": False,
        },
        "sweep_cells": int(len(sweep)),
        "cost_levels_bps": list(cost_levels),
        "data_fingerprint": {
            # The processed panel is rewritten by every research script, so the
            # hash documents the exact input this run consumed rather than a
            # stable property of the workspace.
            "panel": _fingerprint(config.resolve_path(config.paths.processed_dir) / "panel_daily.csv"),
            "rebalance_universe": _fingerprint(
                config.resolve_path(config.paths.processed_dir) / "rebalance_universe.csv"
            ),
        },
        "peak_gross_exposure": round(max(peak_gross, sweep_peak, cost_peak), 12),
        "champion_plateau_score": None if sweep.empty else champion_plateau,
        "champion_neighbour_beats_share": None if sweep.empty else champion_neighbour_share,
        "cost_stressed_candidates": [
            {
                "hold_count": int(candidate["hold_count"]),
                "lookback": int(candidate["lookback"]),
                "btc_ma": int(candidate["btc_ma"]),
                "asset_ma": int(candidate["asset_ma"]),
                "target_vol": float(candidate["target_vol"]),
            }
            for candidate in candidates
        ],
    }
    (report_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _table(frame: pd.DataFrame, index_name: str, percent: tuple[str, ...] = ()) -> str:
        """Render a markdown table whose first column is a real key.

        ``dataframe_to_markdown`` always prints the frame index, so every
        table here is given a meaningful index instead of a filler row number,
        and rate columns are formatted as percentages rather than raw
        fractions.
        """
        prepared = frame.copy()
        for column in percent:
            if column in prepared.columns:
                prepared[column] = prepared[column].map(
                    lambda value: f"{value:.1%}" if pd.notna(value) else ""
                )
        prepared.index.name = index_name
        return dataframe_to_markdown(prepared)

    if sweep.empty:
        # --skip-sweep runs have no neighbourhood evidence; keep the report
        # valid instead of emitting a table with no columns.
        plateau_lines: list[str] = []
    else:
        plateau_lines = [
            "## Parameter-plateau evidence (top sweep cells and their neighbours)",
            "",
            _table(
                sweep.head(10)[
                    [
                        "hold_count",
                        "lookback",
                        "btc_ma",
                        "asset_ma",
                        "target_vol",
                        "sharpe",
                        "total_return",
                        "max_drawdown",
                        "neighbour_count",
                        "neighbour_beats_share",
                        "neighbour_median_sharpe",
                        "plateau_score",
                    ]
                ],
                index_name="cell",
                percent=("total_return", "max_drawdown", "neighbour_beats_share"),
            ),
            "",
            f"Champion plateau score: {champion_plateau:.3f} (neighbours beating BTC: "
            f"{champion_neighbour_share:.0%}, median neighbour Sharpe "
            f"{champion_neighbour_sharpe:.3f})",
            "",
        ]

    report_lines = [
        "# Bull Offense Finalist (unlevered)",
        "",
        f"- Window: {backtest_returns.index.min().date()} .. {backtest_returns.index.max().date()} "
        f"({len(backtest_returns)} days)",
        f"- Structure: point-in-time Top-N, weekly rebalance, BTC {FINALIST['btc_trend_ma']}D trend gate, "
        f"top {FINALIST['hold_count']} by {FINALIST['lookback']}D absolute+relative momentum, "
        f"asset stop on its own {FINALIST['asset_stop_ma']}D MA, "
        f"{FINALIST['target_vol']:.0%} target vol ({FINALIST['vol_window']}D window)",
        "- Leverage: none. Gross exposure hard-capped at 1.0x.",
        f"- Peak gross exposure observed: {manifest['peak_gross_exposure']:.4f}",
        f"- Average gross exposure: {finalist_metrics['avg_gross_exposure'].iloc[0]:.1%}; "
        f"flat on {finalist_metrics['pct_days_flat'].iloc[0]:.1%} of days",
        "",
        "## Champion at each cost level",
        "",
        _table(
            finalist_metrics.set_index("total_cost_bps")[
                [
                    "total_return",
                    "cagr",
                    "sharpe",
                    "max_drawdown",
                    "calmar",
                    "annualized_turnover",
                    "avg_gross_exposure",
                    "pct_days_flat",
                ]
            ],
            index_name="cost_bps",
            percent=("total_return", "cagr", "max_drawdown", "avg_gross_exposure", "pct_days_flat"),
        ),
        "",
        "## BTC buy-and-hold on the same window",
        "",
        _table(
            btc_metrics.set_index("total_cost_bps")[
                ["total_return", "cagr", "sharpe", "max_drawdown"]
            ],
            index_name="cost_bps",
            percent=("total_return", "cagr", "max_drawdown"),
        ),
        "",
        f"## Yearly returns ({base_level:g} bps)",
        "",
        _table(
            yearly.reset_index().set_index("year"),
            index_name="year",
            percent=("strategy", "btc", "excess"),
        ),
        "",
        f"## Sub-periods ({base_level:g} bps)",
        "",
        _table(
            subperiods.set_index("period")[
                [
                    "total_return",
                    "btc_total_return",
                    "excess_total_return",
                    "cagr",
                    "sharpe",
                    "max_drawdown",
                ]
            ],
            index_name="period",
            percent=("total_return", "btc_total_return", "excess_total_return", "cagr", "max_drawdown"),
        ),
        "",
        "## Champion vs the risk/return frontier (cost-stressed)",
        "",
        _table(
            frontier.reset_index()[
                [
                    "hold_count",
                    "lookback",
                    "btc_ma",
                    "asset_ma",
                    "target_vol",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    f"stress{stress_level:g}_total_return",
                    f"stress{stress_level:g}_max_drawdown",
                    "pareto",
                ]
            ].sort_values("total_return", ascending=False),
            index_name="cell",
            percent=("total_return", "max_drawdown", f"stress{stress_level:g}_total_return", f"stress{stress_level:g}_max_drawdown"),
        ),
        "",
        *plateau_lines,
        f"## Rolling monthly starts, windows >= {args.rolling_min_days} days",
        "",
        _table(
            rolling_summary.set_index("cost_bps"),
            index_name="cost_bps",
            percent=("win_rate_vs_btc", "median_maxdd"),
        ),
        "",
        "## Rolling monthly starts, every window (>= 30 days)",
        "",
        _table(
            rolling_summary_all.set_index("cost_bps"),
            index_name="cost_bps",
            percent=("win_rate_vs_btc", "median_maxdd"),
        ),
        "",
        f"## Asset contribution ({base_level:g} bps, additive share of gross return)",
        "",
        _table(
            top_contrib.set_index("coin_id")[
                ["contribution_pct", "share_of_gross_pct", "holding_days"]
            ],
            index_name="coin",
        ),
        "",
    ]
    (report_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")

    print("\nChampion metrics")
    print(
        finalist_metrics[
            ["total_cost_bps", "total_return", "cagr", "sharpe", "max_drawdown", "calmar", "annualized_turnover"]
        ].to_string(index=False, float_format=lambda value: f"{value:,.4f}")
    )
    print("\nBTC metrics")
    print(
        btc_metrics[["total_cost_bps", "total_return", "cagr", "sharpe", "max_drawdown"]].to_string(
            index=False, float_format=lambda value: f"{value:,.4f}"
        )
    )
    print("\nRolling starts vs BTC")
    print(rolling_summary.to_string(index=False, float_format=lambda value: f"{value:,.4f}"))
    print(f"\nWrote finalist outputs to {report_dir}")


if __name__ == "__main__":
    main()
