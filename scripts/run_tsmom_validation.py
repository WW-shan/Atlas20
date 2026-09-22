"""Run a no-leverage time-series-momentum research grid.

The grid is intentionally narrower than the CTREND scan.  It tests the
hypothesis supported by the momentum literature: a coin must first pass its
own trailing-return / trend gate, and only then is it eligible for selection or
regular volatility-scaled portfolio weight.

All runs use point-in-time universes, T+1 execution, and a hard gross-exposure
cap of 1.0.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
import argparse
import json
import logging
import math
import multiprocessing as mp
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.analytics.metrics import compute_summary_metrics  # noqa: E402
from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.backtest.engine import BacktestResult, run_backtest  # noqa: E402
from atlas20.config import FrictionConfig, ResearchConfig, load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import (  # noqa: E402
    btc_above_moving_average,
    btc_above_volatility_scaled_trailing,
)
from atlas20.strategies.overlays import apply_daily_risk_overlay  # noqa: E402
from atlas20.strategies.tsmom import TSMOMSettings, build_tsmom_targets  # noqa: E402
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)


LOGGER = logging.getLogger("atlas20.scripts.tsmom_validation")


@dataclass(frozen=True)
class TSMOMBaseSpec:
    base_id: str
    universe_size: int
    lookback: int
    frequency: str
    top_n: int | None
    score_family: str
    weighting: str
    asset_ma_window: int | None = None


@dataclass(frozen=True)
class TSMOMOverlaySpec:
    overlay_id: str
    target_volatility: float | None = None
    vol_window: int = 30
    btc_ma_window: int | None = None
    btc_confirm_days: int = 2
    btc_chandelier: bool = False


def _slug(value: object) -> str:
    return str(value).replace(" ", "_").lower()


def _candidate_id(base: TSMOMBaseSpec, overlay: TSMOMOverlaySpec) -> str:
    return f"{base.base_id}__{overlay.overlay_id}"


def _build_base_specs() -> list[TSMOMBaseSpec]:
    """Build the pre-registered TSMOM grid.

    The grid keeps the economically meaningful dimensions and avoids filling
    it with near-duplicate weighting rules.  The same lookback/frequency grid
    is run on both the true Top20 and a Top50 sensitivity universe; Top50 is
    explicitly a sensitivity test, not a replacement for the user's Top20
    production rule.
    """
    specs: list[TSMOMBaseSpec] = []
    for universe_size in (20, 50):
        for lookback in (30, 90, 180):
            for frequency in ("7D", "14D", "28D"):
                for top_n in (1, 3, None):
                    weightings = ("equal",) if top_n == 1 else ("equal", "inverse_vol")
                    for score_family in ("tsmom", "tsmom_vol_adjusted"):
                        for weighting in weightings:
                            base_id = "__".join(
                                [
                                    f"tsmom_u{universe_size}",
                                    f"lb{lookback}",
                                    frequency.lower(),
                                    f"top{top_n if top_n is not None else 'all'}",
                                    score_family,
                                    weighting,
                                    "ownma_none",
                                ]
                            )
                            specs.append(
                                TSMOMBaseSpec(
                                    base_id=base_id,
                                    universe_size=universe_size,
                                    lookback=lookback,
                                    frequency=frequency,
                                    top_n=top_n,
                                    score_family=score_family,
                                    weighting=weighting,
                                    asset_ma_window=None,
                                )
                            )
    return specs


def _build_overlay_specs() -> list[TSMOMOverlaySpec]:
    return [
        TSMOMOverlaySpec("none"),
        TSMOMOverlaySpec("vol50", target_volatility=0.50),
        TSMOMOverlaySpec("vol80", target_volatility=0.80),
        TSMOMOverlaySpec("btc_ma50", btc_ma_window=50),
        TSMOMOverlaySpec("btc_ma100", btc_ma_window=100),
        TSMOMOverlaySpec("btc_ma200", btc_ma_window=200),
        TSMOMOverlaySpec("btc_chandelier30", btc_chandelier=True),
        TSMOMOverlaySpec(
            "btc_ma100_vol50",
            btc_ma_window=100,
            target_volatility=0.50,
        ),
    ]


def _universe_variants(
    market: MarketDataBundle,
    config: ResearchConfig,
) -> tuple[dict[int, pd.DataFrame], list[pd.Timestamp]]:
    frequency_values = sorted(
        {
            "7D",
            "14D",
            "21D",
            "28D",
            *config.rebalancing.frequencies.values(),
        }
        - {"month_end"}
    )
    rebalance_dates = sorted(
        {
            date
            for frequency in frequency_values
            for date in get_rebalance_dates(
                market.price.index,
                config.start_timestamp,
                frequency,
                frequency,
            )
        }
    )
    universes: dict[int, pd.DataFrame] = {}
    for size in (20, 50):
        local = config.model_copy(deep=True)
        local.universe.universe_size = size
        universes[size] = build_rebalance_universe(market, rebalance_dates, local)
    return universes, rebalance_dates


def _friction(config: ResearchConfig, total_cost_bps: float) -> FrictionConfig:
    friction = config.frictions.model_copy(deep=True)
    half_cost = float(total_cost_bps) / 2.0
    friction.fee_bps = half_cost
    friction.slippage_bps = half_cost
    friction.max_weight_per_coin = 1.0
    friction.max_weight_per_sector = 1.0
    return friction


def _risk_on_series(market: MarketDataBundle, overlay: TSMOMOverlaySpec) -> pd.Series | None:
    if overlay.btc_ma_window is not None:
        return btc_above_moving_average(
            market.price,
            ma_window=int(overlay.btc_ma_window),
            confirm_days=int(overlay.btc_confirm_days),
        )
    if overlay.btc_chandelier:
        return btc_above_volatility_scaled_trailing(
            market.price,
            lookback=30,
            vol_window=30,
            vol_multiple=2.0,
            confirm_days=2,
        )
    return None


def _portfolio_volatility_exposure(
    targets: dict[pd.Timestamp, pd.Series],
    market: MarketDataBundle,
    target_volatility: float,
    vol_window: int,
) -> dict[pd.Timestamp, float]:
    exposures: dict[pd.Timestamp, float] = {}
    history = market.returns
    for date, target in targets.items():
        timestamp = pd.Timestamp(date)
        if target.empty:
            exposures[timestamp] = 0.0
            continue
        weights = target[target > 0.0].astype(float)
        if weights.empty:
            exposures[timestamp] = 0.0
            continue
        weights = weights / weights.sum()
        window = (
            history.reindex(columns=weights.index)
            .loc[:timestamp]
            .tail(int(vol_window))
            .dropna(how="any")
        )
        if len(window) < max(10, int(vol_window) // 2):
            exposures[timestamp] = 0.0
            continue
        cov = window.cov() * 365.0
        variance = float(weights.to_numpy() @ cov.to_numpy() @ weights.to_numpy())
        if not math.isfinite(variance) or variance <= 0.0:
            exposures[timestamp] = 0.0
            continue
        portfolio_vol = math.sqrt(variance)
        exposures[timestamp] = min(1.0, max(0.0, float(target_volatility) / portfolio_vol))
    return exposures


_BASE_TARGET_CACHE: dict[tuple[str, str], dict[pd.Timestamp, pd.Series]] = {}


def _base_targets(
    base: TSMOMBaseSpec,
    market: MarketDataBundle,
    universes: dict[int, pd.DataFrame],
    config: ResearchConfig,
) -> dict[pd.Timestamp, pd.Series]:
    key = (base.base_id, config.start_timestamp.date().isoformat())
    cached = _BASE_TARGET_CACHE.get(key)
    if cached is not None:
        return cached
    universe = universes[base.universe_size]
    built = build_tsmom_targets(
        market,
        universe,
        config,
        top_n=base.top_n,
        frequency=base.frequency,
        settings=TSMOMSettings(
            lookback=base.lookback,
            score_family=base.score_family,
            weighting=base.weighting,
            vol_window=30,
            asset_ma_window=base.asset_ma_window,
            min_lookback_return=0.0,
            max_weight=0.60,
        ),
        include_btc=True,
    )
    _BASE_TARGET_CACHE[key] = built.targets
    return built.targets


def _run_tsmom_backtest(
    base: TSMOMBaseSpec,
    overlay: TSMOMOverlaySpec,
    market: MarketDataBundle,
    universes: dict[int, pd.DataFrame],
    config: ResearchConfig,
    *,
    total_cost_bps: float = 20.0,
    start_date: pd.Timestamp | None = None,
) -> BacktestResult:
    local_config = config
    if start_date is not None:
        local_config = config.model_copy(deep=True)
        local_config.start_date = pd.Timestamp(start_date).strftime("%Y-%m-%d")

    targets = _base_targets(base, market, universes, local_config)
    risk_on = _risk_on_series(market, overlay)
    if risk_on is not None:
        targets = apply_daily_risk_overlay(targets, risk_on, risk_off_target=None)
    exposure = None
    if overlay.target_volatility is not None:
        exposure = _portfolio_volatility_exposure(
            targets,
            market,
            target_volatility=float(overlay.target_volatility),
            vol_window=overlay.vol_window,
        )

    asset_returns = market.returns.loc[
        local_config.start_timestamp : local_config.end_timestamp
    ]
    return run_backtest(
        name=_candidate_id(base, overlay),
        asset_returns=asset_returns,
        rebalance_targets=targets,
        sector_by_coin=market.metadata["sector"],
        friction=_friction(config, total_cost_bps),
        initial_capital=config.initial_capital,
        gross_target_exposure=1.0,
        leverage_by_date=exposure,
        max_gross_exposure=1.0,
    )


def _summary_row(
    base: TSMOMBaseSpec,
    overlay: TSMOMOverlaySpec,
    result: BacktestResult,
    config: ResearchConfig,
    total_cost_bps: float,
) -> dict[str, object]:
    metrics = compute_summary_metrics(result, config.annualization_days)
    row: dict[str, object] = {
        **asdict(base),
        **asdict(overlay),
        "candidate_id": _candidate_id(base, overlay),
        "total_cost_bps": float(total_cost_bps),
    }
    row.update(metrics)
    row["multiple"] = float(metrics["total_return"]) + 1.0
    return row


_WORKER_MARKET: MarketDataBundle | None = None
_WORKER_UNIVERSES: dict[int, pd.DataFrame] | None = None
_WORKER_CONFIG: ResearchConfig | None = None
_WORKER_BASES: dict[str, TSMOMBaseSpec] | None = None
_WORKER_OVERLAYS: dict[str, TSMOMOverlaySpec] | None = None
_WORKER_COST_BPS: float = 20.0


def _seed_workers(
    market: MarketDataBundle,
    universes: dict[int, pd.DataFrame],
    config: ResearchConfig,
    bases: list[TSMOMBaseSpec],
    overlays: list[TSMOMOverlaySpec],
    cost_bps: float,
) -> None:
    global _WORKER_MARKET, _WORKER_UNIVERSES, _WORKER_CONFIG
    global _WORKER_BASES, _WORKER_OVERLAYS, _WORKER_COST_BPS
    _WORKER_MARKET = market
    _WORKER_UNIVERSES = universes
    _WORKER_CONFIG = config
    _WORKER_BASES = {spec.base_id: spec for spec in bases}
    _WORKER_OVERLAYS = {spec.overlay_id: spec for spec in overlays}
    _WORKER_COST_BPS = float(cost_bps)
    _BASE_TARGET_CACHE.clear()


def _screen_task(task: tuple[str, str]) -> dict[str, object]:
    if (
        _WORKER_MARKET is None
        or _WORKER_UNIVERSES is None
        or _WORKER_CONFIG is None
        or _WORKER_BASES is None
        or _WORKER_OVERLAYS is None
    ):
        raise RuntimeError("TSMOM worker was not initialised")
    base_id, overlay_id = task
    base = _WORKER_BASES[base_id]
    overlay = _WORKER_OVERLAYS[overlay_id]
    result = _run_tsmom_backtest(
        base,
        overlay,
        _WORKER_MARKET,
        _WORKER_UNIVERSES,
        _WORKER_CONFIG,
        total_cost_bps=_WORKER_COST_BPS,
    )
    return _summary_row(
        base,
        overlay,
        result,
        _WORKER_CONFIG,
        total_cost_bps=_WORKER_COST_BPS,
    )


def _period_slice(returns: pd.Series, start: str, end: str | None = None) -> pd.Series:
    subset = returns.loc[pd.Timestamp(start) :]
    if end is not None:
        subset = subset.loc[: pd.Timestamp(end)]
    return subset


def _period_metrics(returns: pd.Series, annualization_days: int) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    if clean.empty:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }
    equity = (1.0 + clean).cumprod()
    years = max(len(clean) / float(annualization_days), 1.0 / float(annualization_days))
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    sharpe = float(clean.mean() / clean.std(ddof=1) * math.sqrt(annualization_days)) if len(clean) > 1 and clean.std(ddof=1) > 0 else 0.0
    drawdown = float((equity / equity.cummax() - 1.0).min())
    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": drawdown,
    }


def _btc_benchmark(market: MarketDataBundle, config: ResearchConfig) -> BacktestResult:
    returns = market.returns.loc[
        config.start_timestamp : config.end_timestamp,
        ["bitcoin"],
    ]
    target = pd.Series({"bitcoin": 1.0})
    # The production friction config caps a diversified book at 35% per coin.
    # A single-asset benchmark must explicitly remove those diversification
    # caps or it silently holds 65% cash and understates BTC buy-and-hold.
    friction = config.frictions.model_copy(deep=True)
    friction.max_weight_per_coin = 1.0
    friction.max_weight_per_sector = 1.0
    return run_backtest(
        name="BTC_BH",
        asset_returns=returns,
        rebalance_targets={pd.Timestamp(config.start_timestamp): target},
        sector_by_coin=market.metadata["sector"],
        friction=friction,
        initial_capital=config.initial_capital,
        gross_target_exposure=1.0,
        max_gross_exposure=1.0,
    )


def _write_report(
    path: Path,
    summary: pd.DataFrame,
    btc_metrics: dict[str, object],
    yearly: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    ordered = summary.sort_values(
        ["multiple", "sharpe"], ascending=[False, False], kind="mergesort"
    )
    columns = [
        "candidate_id",
        "universe_size",
        "lookback",
        "frequency",
        "top_n",
        "score_family",
        "weighting",
        "overlay_id",
        "multiple",
        "cagr",
        "sharpe",
        "max_drawdown",
        "annualized_turnover",
    ]
    present = [column for column in columns if column in ordered.columns]
    lines = [
        "# Time-Series Momentum Validation",
        "",
        "This report is generated from the real point-in-time CMC panel. "
        "Every candidate is long-only, unlevered, executed T+1, and charged "
        "20bps per side in the screen. Top50 rows are a sensitivity universe, "
        "not the production Top20 rule.",
        "",
        "## BTC Benchmark",
        "",
        dataframe_to_markdown(pd.DataFrame([btc_metrics])),
        "",
        "## Top Candidates",
        "",
        dataframe_to_markdown(ordered[present].head(50).reset_index(drop=True)),
        "",
        "## Yearly Returns",
        "",
        dataframe_to_markdown(yearly.reset_index()),
        "",
        "## Validation",
        "",
        dataframe_to_markdown(validation.reset_index(drop=True)),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/tsmom_validation_2022"))
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--screen-only", action="store_true")
    parser.add_argument("--validation-candidates", type=int, default=20)
    parser.add_argument("--cost-bps", type=float, default=20.0)
    args = parser.parse_args()

    config = load_config(args.config)
    config = config.model_copy(deep=True)
    if args.start_date:
        config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    configure_logging(config.logging.level)
    if args.workers <= 0:
        parser.error("--workers must be positive")

    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    panel, metadata = build_processed_datasets(config, sector_config, persist=False)
    market = prepare_market_data(panel, metadata, config)
    universes, _ = _universe_variants(market, config)
    bases = _build_base_specs()
    overlays = _build_overlay_specs()
    tasks = [
        (base.base_id, overlay.overlay_id)
        for base in bases
        for overlay in overlays
    ]
    LOGGER.info(
        "TSMOM screen: %d bases x %d overlays = %d candidates, %d workers",
        len(bases),
        len(overlays),
        len(tasks),
        args.workers,
    )

    if args.workers > 1:
        _seed_workers(market, universes, config, bases, overlays, args.cost_bps)
        with ProcessPoolExecutor(
            max_workers=args.workers,
            mp_context=mp.get_context("fork"),
        ) as executor:
            rows = list(executor.map(_screen_task, tasks, chunksize=2))
    else:
        _seed_workers(market, universes, config, bases, overlays, args.cost_bps)
        rows = [_screen_task(task) for task in tasks]

    summary = pd.DataFrame(rows)
    summary = summary.sort_values(["multiple", "sharpe"], ascending=False, kind="mergesort").reset_index(drop=True)
    output_dir = ensure_dir(args.output_dir)
    summary.to_csv(output_dir / "candidate_summary.csv", index=False)

    btc_result = _btc_benchmark(market, config)
    btc_metrics = compute_summary_metrics(btc_result, config.annualization_days)
    btc_metrics["multiple"] = float(btc_metrics["total_return"]) + 1.0
    (output_dir / "btc_benchmark.json").write_text(
        json.dumps(btc_metrics, indent=2, default=str),
        encoding="utf-8",
    )

    if args.screen_only:
        (output_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "window": {
                        "start": config.start_timestamp.date().isoformat(),
                        "end": config.end_timestamp.date().isoformat(),
                    },
                    "candidates": len(tasks),
                    "screen_only": True,
                    "leverage": "hard cap 1.0",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Wrote TSMOM screen to {output_dir}")
        return

    base_by_id = {base.base_id: base for base in bases}
    overlay_by_id = {overlay.overlay_id: overlay for overlay in overlays}
    validation_ids = summary.head(max(1, args.validation_candidates))["candidate_id"].tolist()
    validation_rows: list[dict[str, object]] = []
    yearly_columns: dict[str, pd.Series] = {}
    for candidate_id in validation_ids:
        base_id, overlay_id = candidate_id.rsplit("__", 1)
        # Base IDs never contain a double underscore after the separator, but
        # the overlay can contain underscores.  Recover the pair explicitly.
        if base_id not in base_by_id:
            matches = [
                base
                for base in bases
                if candidate_id.startswith(base.base_id + "__")
                and candidate_id == _candidate_id(base, overlay_by_id[overlay_id])
            ]
            if matches:
                base_id = matches[0].base_id
        base = base_by_id[base_id]
        overlay = overlay_by_id[overlay_id]
        result = _run_tsmom_backtest(
            base,
            overlay,
            market,
            universes,
            config,
            total_cost_bps=args.cost_bps,
        )
        yearly = (1.0 + result.daily_returns).resample("YE").prod() - 1.0
        yearly_columns[candidate_id] = yearly
        for period, start, end in (
            ("2022", "2022-01-01", "2022-12-31"),
            ("2023", "2023-01-01", "2023-12-31"),
            ("2024", "2024-01-01", "2024-12-31"),
            ("2025", "2025-01-01", "2025-12-31"),
            ("2026_ytd", "2026-01-01", None),
        ):
            validation_rows.append(
                {
                    "candidate_id": candidate_id,
                    "period": period,
                    **_period_metrics(
                        _period_slice(result.daily_returns, start, end),
                        config.annualization_days,
                    ),
                }
            )
    yearly_frame = pd.DataFrame(yearly_columns)
    yearly_frame.index.name = "year"
    validation_frame = pd.DataFrame(validation_rows)
    validation_frame.to_csv(output_dir / "period_performance.csv", index=False)

    # Cost stress the already-validated set.  This is intentionally a
    # re-simulation rather than a fee approximation because turnover differs
    # across regimes.
    cost_rows: list[dict[str, object]] = []
    for candidate_id in validation_ids:
        base_id = next(
            base.base_id
            for base in bases
            if candidate_id.startswith(base.base_id + "__")
        )
        overlay_id = candidate_id[len(base_id) + 2 :]
        base = base_by_id[base_id]
        overlay = overlay_by_id[overlay_id]
        for cost_bps in (5.0, 10.0, 20.0, 50.0, 100.0):
            result = _run_tsmom_backtest(
                base,
                overlay,
                market,
                universes,
                config,
                total_cost_bps=cost_bps,
            )
            metrics = compute_summary_metrics(result, config.annualization_days)
            cost_rows.append(
                {
                    "candidate_id": candidate_id,
                    "total_cost_bps": cost_bps,
                    "multiple": float(metrics["total_return"]) + 1.0,
                    "cagr": metrics["cagr"],
                    "sharpe": metrics["sharpe"],
                    "max_drawdown": metrics["max_drawdown"],
                }
            )
    cost_frame = pd.DataFrame(cost_rows)
    cost_frame.to_csv(output_dir / "cost_stress.csv", index=False)
    _write_report(
        output_dir / "tsmom_report.md",
        summary,
        btc_metrics,
        yearly_frame,
        validation_frame,
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "window": {
                    "start": config.start_timestamp.date().isoformat(),
                    "end": config.end_timestamp.date().isoformat(),
                },
                "candidates": len(tasks),
                "validation_candidates": len(validation_ids),
                "leverage": "hard cap 1.0",
                "screen_cost_bps": args.cost_bps,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote TSMOM validation to {output_dir}")


if __name__ == "__main__":
    main()
