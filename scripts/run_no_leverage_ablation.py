"""Run a unified, strictly unlevered strategy and risk-overlay ablation.

This script intentionally keeps the research matrix smaller than the full
convex-leader grid.  Its purpose is attribution: every candidate sees the same
point-in-time Top20 universe, the same friction model, and the same T+1
execution.  Gross exposure is capped at 1.0 at every rebalance.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
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
from atlas20.signals.regime import build_regime_frame  # noqa: E402
from atlas20.signals.risk import (  # noqa: E402
    absolute_trend_mask,
    btc_above_moving_average,
    btc_above_volatility_scaled_trailing,
    realized_volatility,
)
from atlas20.strategies.convex_leader import build_ctrend_lite_targets  # noqa: E402
from atlas20.strategies.implementations import (  # noqa: E402
    StrategyDefinition,
    build_rebalance_targets,
)
from atlas20.strategies.momentum_lead import build_momentum_lead_targets  # noqa: E402
from atlas20.strategies.overlays import (  # noqa: E402
    apply_daily_asset_stop_overlay,
    apply_daily_risk_overlay,
)
from atlas20.strategies.sector_lead_v3 import build_sector_lead_v3_targets  # noqa: E402
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)


@dataclass(frozen=True)
class BaseSpec:
    base_id: str
    family: str
    kind: str
    frequency: str
    regime_mode: str
    top_n: int | None = None
    score_family: str = ""
    concentrated: bool = False


@dataclass(frozen=True)
class OverlaySpec:
    overlay_id: str
    target_volatility: float | None = None
    vol_window: int = 30
    trend_window: int | None = None
    asset_trend_window: int | None = None
    risk_on_kind: str = "none"
    risk_on_window: int = 100


BASE_SPECS: tuple[BaseSpec, ...] = (
    BaseSpec("BTC_BH", "benchmark", "standard", "monthly", "always_on", concentrated=True),
    BaseSpec("ETH_BH", "benchmark", "standard", "monthly", "always_on", concentrated=True),
    BaseSpec("BTC_BH_bull", "benchmark", "standard", "monthly", "bull_only", concentrated=True),
    BaseSpec("ETH_BH_bull", "benchmark", "standard", "monthly", "bull_only", concentrated=True),
    BaseSpec("TOP20_EQ_bull", "equal_weight", "standard", "monthly", "bull_only"),
    BaseSpec("TOP20_MOM_top6_biweekly_bull", "momentum", "standard", "biweekly", "bull_only", top_n=6),
    BaseSpec("TOP20_MOM_top6_monthly_bull", "momentum", "standard", "monthly", "bull_only", top_n=6),
    BaseSpec("TOP20_MOM_top4_biweekly_bull", "momentum", "standard", "biweekly", "bull_only", top_n=4),
    BaseSpec("TOP20_SECTOR_top3_monthly_bull", "sector", "standard", "monthly", "bull_only", top_n=3),
    BaseSpec("MOM_LEAD_top1", "momentum_lead", "momentum_lead", "14D", "bull_only", top_n=1, concentrated=True),
    BaseSpec("MOM_LEAD_top2", "momentum_lead", "momentum_lead", "14D", "bull_only", top_n=2, concentrated=True),
    BaseSpec("MOM_LEAD_top3", "momentum_lead", "momentum_lead", "14D", "bull_only", top_n=3, concentrated=True),
    BaseSpec(
        "CTREND_balanced_top1",
        "ctrend_lite",
        "ctrend_lite",
        "14D",
        "always_on",
        top_n=1,
        score_family="ctrend_lite_balanced",
        concentrated=True,
    ),
    BaseSpec(
        "CTREND_balanced_top3",
        "ctrend_lite",
        "ctrend_lite",
        "14D",
        "always_on",
        top_n=3,
        score_family="ctrend_lite_balanced",
        concentrated=True,
    ),
    BaseSpec(
        "CTREND_balanced_top5",
        "ctrend_lite",
        "ctrend_lite",
        "14D",
        "always_on",
        top_n=5,
        score_family="ctrend_lite_balanced",
        concentrated=True,
    ),
    BaseSpec(
        "CTREND_breakout_top3",
        "ctrend_lite",
        "ctrend_lite",
        "14D",
        "always_on",
        top_n=3,
        score_family="ctrend_lite_breakout",
        concentrated=True,
    ),
    BaseSpec(
        "CTREND_relative_top3",
        "ctrend_lite",
        "ctrend_lite",
        "14D",
        "always_on",
        top_n=3,
        score_family="ctrend_lite_relative_strength",
        concentrated=True,
    ),
    BaseSpec("SECTOR_LEAD_top1", "sector_lead", "sector_lead", "14D", "bull_only", top_n=1, concentrated=True),
    BaseSpec("SECTOR_LEAD_top2", "sector_lead", "sector_lead", "14D", "bull_only", top_n=2, concentrated=True),
    BaseSpec("SECTOR_LEAD_top3", "sector_lead", "sector_lead", "14D", "bull_only", top_n=3, concentrated=True),
)


OVERLAY_SPECS: tuple[OverlaySpec, ...] = (
    OverlaySpec("none"),
    OverlaySpec("vol30", target_volatility=0.30),
    OverlaySpec("vol40", target_volatility=0.40),
    OverlaySpec("vol50", target_volatility=0.50),
    OverlaySpec("vol60", target_volatility=0.60),
    OverlaySpec("vol80", target_volatility=0.80),
    OverlaySpec("vol100", target_volatility=1.00),
    OverlaySpec("trend100", trend_window=100),
    OverlaySpec("trend200", trend_window=200),
    OverlaySpec("vol50_trend100", target_volatility=0.50, trend_window=100),
    OverlaySpec("vol40_trend200", target_volatility=0.40, trend_window=200),
    OverlaySpec("btc_ma100", risk_on_kind="btc_ma", risk_on_window=100),
    OverlaySpec("btc_ma200", risk_on_kind="btc_ma", risk_on_window=200),
    OverlaySpec("btc_chandelier30", risk_on_kind="btc_chandelier"),
    OverlaySpec("asset_ma50", asset_trend_window=50),
    OverlaySpec("asset_ma100", asset_trend_window=100),
    OverlaySpec(
        "asset_ma50_btc_ma100",
        asset_trend_window=50,
        risk_on_kind="btc_ma",
        risk_on_window=100,
    ),
    OverlaySpec(
        "asset_ma100_btc_ma100",
        asset_trend_window=100,
        risk_on_kind="btc_ma",
        risk_on_window=100,
    ),
    OverlaySpec("asset_ma50_vol60", asset_trend_window=50, target_volatility=0.60),
    OverlaySpec("asset_ma100_vol60", asset_trend_window=100, target_volatility=0.60),
)


def _standard_definition(spec: BaseSpec) -> StrategyDefinition:
    if spec.family == "benchmark":
        coin_id = spec.base_id.split("_")[0].lower()
        params = {"coin_id": "bitcoin" if coin_id == "btc" else "ethereum"}
    else:
        params = {}
        if spec.top_n is not None:
            params["hold_count" if spec.family == "momentum" else "top_k"] = spec.top_n
    return StrategyDefinition(
        name=spec.base_id,
        family=spec.family,
        frequency=spec.frequency,
        regime_mode=spec.regime_mode,
        params=params,
    )


def _apply_regime_filter_to_targets(
    targets: dict[pd.Timestamp, pd.Series],
    regime_frame: pd.DataFrame,
    regime_mode: str,
) -> dict[pd.Timestamp, pd.Series]:
    if regime_mode == "always_on":
        return targets
    return {
        pd.Timestamp(date): (target.copy() if bool(regime_frame.loc[date, "bull"]) else pd.Series(dtype=float))
        for date, target in targets.items()
    }


def build_base_targets(
    spec: BaseSpec,
    market: MarketDataBundle,
    universe: pd.DataFrame,
    regime_frame: pd.DataFrame,
    config: ResearchConfig,
) -> dict[pd.Timestamp, pd.Series]:
    if spec.kind == "standard":
        targets, _ = build_rebalance_targets(
            _standard_definition(spec),
            market,
            universe,
            regime_frame,
            config,
        )
        return targets

    if spec.kind == "momentum_lead":
        return build_momentum_lead_targets(
            market,
            universe,
            regime_frame,
            config,
            top_n=int(spec.top_n),
            frequency=spec.frequency,
            regime_mode=spec.regime_mode,
            weighted=True,
        ).targets

    if spec.kind == "ctrend_lite":
        targets = build_ctrend_lite_targets(
            market,
            universe,
            config,
            top_n=int(spec.top_n),
            frequency=spec.frequency,
            score_family=spec.score_family,
            include_btc=True,
        ).targets
        return _apply_regime_filter_to_targets(targets, regime_frame, spec.regime_mode)

    if spec.kind == "sector_lead":
        return build_sector_lead_v3_targets(
            market,
            universe,
            regime_frame,
            config,
            top_k=int(spec.top_n),
            frequency=spec.frequency,
            regime_mode=spec.regime_mode,
        ).targets

    raise ValueError(f"Unsupported base kind: {spec.kind}")


def _apply_trend_filter(
    targets: dict[pd.Timestamp, pd.Series],
    trend_mask: pd.DataFrame,
) -> dict[pd.Timestamp, pd.Series]:
    filtered: dict[pd.Timestamp, pd.Series] = {}
    for date, target in targets.items():
        date = pd.Timestamp(date)
        if target.empty:
            filtered[date] = target.copy()
            continue
        kept = [
            (coin, float(weight))
            for coin, weight in target.items()
            if coin in trend_mask.columns
            and date in trend_mask.index
            and bool(trend_mask.loc[date, coin])
        ]
        if not kept:
            filtered[date] = pd.Series(dtype=float)
            continue
        total = sum(weight for _, weight in kept)
        filtered[date] = pd.Series({coin: weight / total for coin, weight in kept})
    return filtered


def _scaled_exposure_for_targets(
    targets: dict[pd.Timestamp, pd.Series],
    market: MarketDataBundle,
    overlay: OverlaySpec,
) -> dict[pd.Timestamp, float] | None:
    if overlay.target_volatility is None:
        return None

    volatility = realized_volatility(market.price, window=overlay.vol_window)
    exposure: dict[pd.Timestamp, float] = {}
    for date, target in targets.items():
        date = pd.Timestamp(date)
        if target.empty or date not in volatility.index:
            exposure[date] = 0.0
            continue
        candidates = target[target > 0]
        scales = [
            float(overlay.target_volatility) / float(volatility.loc[date, coin])
            for coin in candidates.index
            if coin in volatility.columns and pd.notna(volatility.loc[date, coin])
            and float(volatility.loc[date, coin]) > 0.0
        ]
        if not scales:
            exposure[date] = 1.0
        else:
            # Deliberately cap at 1.0: the user does not want leverage, so the
            # target-vol overlay may only de-risk, never amplify.
            exposure[date] = min(1.0, sum(scales) / len(scales))
    return exposure


def _risk_on_series(
    market: MarketDataBundle,
    overlay: OverlaySpec,
) -> pd.Series | None:
    if overlay.risk_on_kind == "none":
        return None
    if overlay.risk_on_kind == "btc_ma":
        return btc_above_moving_average(
            market.price,
            ma_window=overlay.risk_on_window,
            confirm_days=2,
        )
    if overlay.risk_on_kind == "btc_chandelier":
        return btc_above_volatility_scaled_trailing(
            market.price,
            lookback=30,
            vol_window=overlay.vol_window,
            vol_multiple=2.0,
            confirm_days=2,
        )
    raise ValueError(f"Unsupported risk_on_kind: {overlay.risk_on_kind}")


def _friction_for_spec(config: ResearchConfig, spec: BaseSpec) -> FrictionConfig:
    friction = config.frictions.model_copy(deep=True)
    if spec.concentrated:
        # The concentrated lanes deliberately hold one to five leaders rather
        # than a diversified 20-name book, so the diversified caps do not apply.
        friction.max_weight_per_coin = 1.0
        friction.max_weight_per_sector = 1.0
    return friction


def run_candidate(
    spec: BaseSpec,
    overlay: OverlaySpec,
    market: MarketDataBundle,
    universe: pd.DataFrame,
    regime_frame: pd.DataFrame,
    config: ResearchConfig,
    *,
    total_cost_bps: float = 20.0,
) -> BacktestResult:
    base_targets = build_base_targets(spec, market, universe, regime_frame, config)
    targets = base_targets
    if overlay.trend_window is not None:
        targets = _apply_trend_filter(
            targets,
            absolute_trend_mask(market.price, ma_window=overlay.trend_window),
        )

    if overlay.asset_trend_window is not None:
        targets = apply_daily_asset_stop_overlay(
            targets,
            absolute_trend_mask(market.price, ma_window=overlay.asset_trend_window),
        )

    risk_on = _risk_on_series(market, overlay)
    if risk_on is not None:
        targets = apply_daily_risk_overlay(targets, risk_on, risk_off_target=None)

    exposure = _scaled_exposure_for_targets(targets, market, overlay)
    friction = _friction_for_spec(config, spec).model_copy(deep=True)
    half_cost = float(total_cost_bps) / 2.0
    friction.fee_bps = half_cost
    friction.slippage_bps = half_cost

    return run_backtest(
        name=f"{spec.base_id}__{overlay.overlay_id}",
        asset_returns=market.returns.loc[config.start_timestamp : config.end_timestamp],
        rebalance_targets=targets,
        sector_by_coin=market.metadata["sector"],
        friction=friction,
        initial_capital=config.initial_capital,
        gross_target_exposure=1.0,
        leverage_by_date=exposure,
        max_gross_exposure=1.0,
    )


def _calendar_period_slice(
    returns: pd.Series,
    start: str,
    end: str | None,
) -> pd.Series:
    """Return an inclusive slice for a named research period.

    An unbounded slice such as ``returns.loc[start:]`` is correct for a
    "from date onward" diagnostic but wrong for a calendar-year label. Keeping
    the bound explicit prevents the two cases from being confused again.
    """
    if end is None:
        return returns.loc[start:]
    return returns.loc[start:end]


def _calendar_period_return(
    returns: pd.Series,
    start: str,
    end: str | None,
) -> float:
    """Compound the return over one explicitly bounded calendar period."""
    subset = _calendar_period_slice(returns, start, end).astype(float).fillna(0.0)
    if subset.empty:
        return 0.0
    return float((1.0 + subset).prod() - 1.0)


def _period_metrics(returns: pd.Series, annualization_days: int = 365) -> dict[str, float]:
    returns = returns.astype(float).fillna(0.0)
    if returns.empty:
        return {"total_return": 0.0, "cagr": 0.0, "vol": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    equity = (1.0 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    periods = max(len(returns) - 1, 1)
    cagr = float((1.0 + total_return) ** (annualization_days / periods) - 1.0) if total_return > -1.0 else -1.0
    volatility = float(returns.std(ddof=0) * math.sqrt(annualization_days))
    sharpe = float(returns.mean() * annualization_days / volatility) if volatility > 0.0 else 0.0
    max_drawdown = float((equity / equity.cummax() - 1.0).min())
    return {
        "total_return": total_return,
        "cagr": cagr,
        "vol": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
    }


def _summary_row(
    spec: BaseSpec,
    overlay: OverlaySpec,
    result: BacktestResult,
    config: ResearchConfig,
) -> dict[str, object]:
    metrics = compute_summary_metrics(result, config.annualization_days)
    exposure = result.weights.sum(axis=1)
    row: dict[str, object] = {
        **asdict(spec),
        **asdict(overlay),
        "candidate_id": f"{spec.base_id}__{overlay.overlay_id}",
        **metrics,
        "avg_gross_exposure": float(exposure.mean()),
        "max_gross_exposure": float(exposure.max()),
        "beats_btc_total": False,
        "beats_btc_sharpe": False,
    }
    return row


def _write_report(
    path: Path,
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    subperiod: pd.DataFrame,
    cost: pd.DataFrame,
) -> None:
    ranked = summary.sort_values(["sharpe", "cagr"], ascending=False)
    by_return = summary.sort_values("total_return", ascending=False)
    lines = [
        "# Atlas20 No-Leverage Ablation",
        "",
        "- Gross exposure is capped at 1.0 for every candidate.",
        "- Signals are generated on close t and executed on t+1.",
        "- Base costs are 20 bps per unit turnover (10 bps fee + 10 bps slippage).",
        "- All candidates use the same point-in-time Top20 universe and same data snapshot.",
        "",
        "## Top 20 by Sharpe",
        "",
        dataframe_to_markdown(ranked.head(20).reset_index(drop=True)),
        "",
        "## Top 20 by Total Return",
        "",
        dataframe_to_markdown(by_return.head(20).reset_index(drop=True)),
        "",
        "## Yearly Returns",
        "",
        dataframe_to_markdown(yearly.reset_index()),
        "",
        "## Subperiod Summary",
        "",
        dataframe_to_markdown(subperiod.reset_index(drop=True)),
        "",
        "## Cost Stress",
        "",
        dataframe_to_markdown(cost.reset_index(drop=True)),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--top-cost-candidates", type=int, default=25)
    parser.add_argument("--start-date", default=None, help="Override the backtest start date.")
    parser.add_argument("--end-date", default=None, help="Override the backtest end date.")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.start_date or args.end_date:
        config = config.model_copy(deep=True)
        if args.start_date:
            config.start_date = args.start_date
        if args.end_date:
            config.end_date = args.end_date
    configure_logging(config.logging.level)
    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    panel, metadata = build_processed_datasets(config, sector_config, persist=False)
    market = prepare_market_data(panel, metadata, config)

    frequency_values = sorted(
        {
            value
            for value in config.rebalancing.frequencies.values()
            if value not in {"month_end"}
        }
        | {"7D", "14D", "21D", "28D"}
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
    universe = build_rebalance_universe(market, rebalance_dates, config)
    regime_frame = build_regime_frame(market.price, market.market_cap, config)

    rows: list[dict[str, object]] = []
    yearly_rows: dict[str, pd.Series] = {}
    subperiod_rows: list[dict[str, object]] = []
    daily_returns_by_candidate: dict[str, pd.Series] = {}

    total = len(BASE_SPECS) * len(OVERLAY_SPECS)
    print(f"Running {total} no-leverage candidates...")
    for index, spec in enumerate(BASE_SPECS, start=1):
        for overlay in OVERLAY_SPECS:
            result = run_candidate(spec, overlay, market, universe, regime_frame, config)
            row = _summary_row(spec, overlay, result, config)
            rows.append(row)
            candidate_id = str(row["candidate_id"])
            yearly_rows[candidate_id] = (1.0 + result.daily_returns).resample("YE").prod() - 1.0
            daily_returns_by_candidate[candidate_id] = result.daily_returns

            for label, start, end in (
                ("2021", "2021-01-01", "2021-12-31"),
                ("2022", "2022-01-01", "2022-12-31"),
                ("2023", "2023-01-01", "2023-12-31"),
                ("2024", "2024-01-01", "2024-12-31"),
                ("2025", "2025-01-01", "2025-12-31"),
                ("2026_ytd", "2026-01-01", None),
                ("2023_onward", "2023-01-01", None),
                ("2024_onward", "2024-01-01", None),
                ("2025_onward", "2025-01-01", None),
            ):
                subset = _calendar_period_slice(result.daily_returns, start, end)
                subperiod_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "period": label,
                        **_period_metrics(subset, config.annualization_days),
                    }
                )

        print(f"Evaluated base {index}/{len(BASE_SPECS)}: {spec.base_id}")

    summary = pd.DataFrame(rows)
    btc = summary[summary["base_id"] == "BTC_BH"].iloc[0]
    summary["beats_btc_total"] = pd.to_numeric(summary["total_return"], errors="coerce") > float(btc["total_return"])
    summary["beats_btc_sharpe"] = pd.to_numeric(summary["sharpe"], errors="coerce") > float(btc["sharpe"])

    yearly = pd.DataFrame(yearly_rows)
    yearly.index.name = "year"
    yearly = yearly.sort_index()
    subperiod = pd.DataFrame(subperiod_rows)

    top_ids = list(
        summary.sort_values(["sharpe", "cagr"], ascending=False)
        .head(args.top_cost_candidates)["candidate_id"]
    )
    cost_rows: list[dict[str, object]] = []
    spec_by_id = {spec.base_id: spec for spec in BASE_SPECS}
    overlay_by_id = {overlay.overlay_id: overlay for overlay in OVERLAY_SPECS}
    for candidate_id in top_ids:
        base_id, overlay_id = candidate_id.rsplit("__", 1)
        if base_id not in spec_by_id or overlay_id not in overlay_by_id:
            continue
        for total_cost_bps in (50.0, 100.0, 150.0):
            stressed = run_candidate(
                spec_by_id[base_id],
                overlay_by_id[overlay_id],
                market,
                universe,
                regime_frame,
                config,
                total_cost_bps=total_cost_bps,
            )
            stressed_metrics = compute_summary_metrics(stressed, config.annualization_days)
            cost_rows.append(
                {
                    "candidate_id": candidate_id,
                    "total_cost_bps": total_cost_bps,
                    "total_return": stressed_metrics["total_return"],
                    "cagr": stressed_metrics["cagr"],
                    "sharpe": stressed_metrics["sharpe"],
                    "max_drawdown": stressed_metrics["max_drawdown"],
                }
            )

    cost = pd.DataFrame(cost_rows)

    if not summary.empty and float(summary["max_gross_exposure"].max()) > 1.0 + 1e-9:
        raise AssertionError("no-leverage matrix produced gross exposure above 1.0")

    report_dir = ensure_dir(
        args.output_dir
        if args.output_dir is not None
        else config.resolve_path(config.paths.reports_dir).parent / "no_leverage_ablation"
    )
    summary.to_csv(report_dir / "candidate_summary.csv", index=False)
    yearly.to_csv(report_dir / "yearly_returns.csv")
    subperiod.to_csv(report_dir / "subperiod_summary.csv", index=False)
    cost.to_csv(report_dir / "cost_sensitivity.csv", index=False)
    daily_returns = pd.DataFrame(daily_returns_by_candidate)
    daily_returns.to_csv(report_dir / "daily_returns.csv")
    _write_report(report_dir / "report.md", summary, yearly, subperiod, cost)
    (report_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "candidates": len(summary),
                "base_candidates": len(BASE_SPECS),
                "overlays": len(OVERLAY_SPECS),
                "max_gross_exposure": float(summary["max_gross_exposure"].max()) if not summary.empty else 0.0,
                "base_cost_bps": 20.0,
                "no_leverage": True,
                "window": {
                    "start": config.start_timestamp.date().isoformat(),
                    "end": config.end_timestamp.date().isoformat(),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ranked = summary.sort_values(["sharpe", "cagr"], ascending=False)
    print("\nTop 15 by Sharpe")
    print(
        ranked[
            [
                "candidate_id",
                "total_return",
                "cagr",
                "sharpe",
                "max_drawdown",
                "annualized_turnover",
                "max_gross_exposure",
            ]
        ]
        .head(15)
        .to_string(index=False, float_format=lambda value: f"{value:,.4f}")
    )
    print(f"\nWrote no-leverage ablation outputs to {report_dir}")


if __name__ == "__main__":
    main()
