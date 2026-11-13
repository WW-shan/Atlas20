"""Run the pre-registered LS81 core-major funding-carry overlay.

The base book is the frozen LS57 long/profit-lock/regime-short strategy.  The
only new sleeve is a fixed core-major, market-neutral funding carry.  This
runner uses the real Bitget mark/liquidation engine and the separately loaded
Bitget market candles for fills.  It is research-only and never routes orders.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.derivatives.engine import (  # noqa: E402
    DerivativeBacktestConfig,
    run_derivative_backtest,
)
from atlas20.derivatives.signals import (  # noqa: E402
    combine_long_with_cash_budgeted_short,
    combine_signed_book_with_residual_sleeve,
    scale_long_targets,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_h5_regime_short_router import (  # noqa: E402
    FROZEN_CONFIG,
    LS57_CANDIDATE_ID,
    build_long_targets_for_trial,
    build_short_targets_for_trial,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

CORE8 = (
    "bitcoin",
    "ethereum",
    "solana",
    "ripple",
    "binancecoin",
    "dogecoin",
    "cardano",
    "avalanche-2",
)
EXTENDED10 = CORE8 + ("chainlink", "polkadot")
TRIAL_ID = "PR2026-11-LS81-LS57-CORE8-FUNDING-CARRY"
SAMPLE_WINDOWS: dict[str, tuple[str, str]] = {
    "full": ("2022-01-01", "2026-09-20"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-20"),
}


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _normalise_target(value: object) -> pd.Series:
    series = pd.to_numeric(pd.Series(value), errors="coerce")
    series.index = series.index.astype(str)
    if series.isna().any() or not np.isfinite(series.to_numpy(dtype=float)).all():
        raise ValueError("target weights must be finite")
    return series.astype(float).sort_index()


def _state_at(
    schedule: Mapping[pd.Timestamp, pd.Series] | None,
    date: pd.Timestamp,
) -> pd.Series:
    state = pd.Series(dtype=float)
    if not schedule:
        return state
    for raw_date, target in sorted(schedule.items(), key=lambda item: _as_utc(item[0])):
        signal_date = _as_utc(raw_date)
        if signal_date > date:
            break
        state = _normalise_target(target)
    return state


def _mark_available(
    mark_candles: Mapping[str, pd.DataFrame],
    market_candles: Mapping[str, pd.DataFrame],
    asset: str,
    date: pd.Timestamp,
    *,
    lookback_days: int = 3,
) -> bool:
    """Require a recent mark and a fill candle at the scheduled execution time."""
    mark = mark_candles.get(asset)
    market = market_candles.get(asset)
    if mark is None or market is None or mark.empty or market.empty:
        return False
    signal_date = _as_utc(date).normalize()
    recent_start = signal_date - pd.Timedelta(days=lookback_days)
    if not bool(((mark.index >= recent_start) & (mark.index < signal_date)).any()):
        return False
    execution_time = signal_date + pd.Timedelta(days=1, hours=3)
    if execution_time in market.index:
        return True
    later = market.index[market.index >= execution_time]
    return bool(len(later) and later[0] - execution_time <= pd.Timedelta(hours=1))


def build_asset_trend_filter(
    mark_candles: Mapping[str, pd.DataFrame],
    *,
    ma_days: int,
) -> Callable[[str, pd.Timestamp], bool]:
    """Return a strict completed-daily-close trend filter for carry long legs."""
    if ma_days < 1:
        raise ValueError("ma_days must be positive")
    daily: dict[str, tuple[pd.Series, pd.Series]] = {}
    for asset, frame in mark_candles.items():
        if frame.empty or "close" not in frame.columns:
            continue
        close = pd.to_numeric(frame["close"], errors="coerce").resample("1D").last().dropna()
        if close.empty:
            continue
        daily[str(asset)] = (close, close.rolling(ma_days, min_periods=ma_days).mean())

    def is_above(asset: str, date: pd.Timestamp) -> bool:
        values = daily.get(str(asset))
        if values is None:
            return False
        close, sma = values
        normalized = _as_utc(date).normalize()
        completed = close.index[close.index < normalized]
        if len(completed) == 0:
            return False
        last_date = completed[-1]
        average = sma.get(last_date, float("nan"))
        return bool(pd.notna(average) and float(close.loc[last_date]) > float(average))

    return is_above


def build_pit_funding_carry_schedule(
    *,
    funding_rates: pd.DataFrame,
    calendar: Sequence[pd.Timestamp] | pd.DatetimeIndex,
    assets: Sequence[str],
    base_targets: Mapping[pd.Timestamp, pd.Series] | None = None,
    market_available: Callable[[str, pd.Timestamp], bool] | None = None,
    rebalance_days: int = 7,
    lookback_days: int = 7,
    min_settlements: int = 3,
    min_assets: int = 6,
    count: int = 2,
    per_asset_weight: float = 0.25,
    long_enabled: bool = True,
    short_enabled: bool = True,
    long_trend_ok: Callable[[str, pd.Timestamp], bool] | None = None,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Build a strict-PIT core-major low/high funding carry schedule.

    Funding observations at the signal timestamp are excluded.  The sleeve is
    only emitted on the pre-registered weekly grid; an insufficient eligible
    set emits an empty target so a prior sleeve is cleared rather than carried
    forward silently.
    """
    if rebalance_days < 1:
        raise ValueError("rebalance_days must be positive")
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    if min_settlements < 1:
        raise ValueError("min_settlements must be positive")
    if count < 1:
        raise ValueError("count must be positive")
    enabled_sides = int(long_enabled) + int(short_enabled)
    if enabled_sides == 0:
        raise ValueError("at least one carry side must be enabled")
    if min_assets < enabled_sides * count:
        raise ValueError("min_assets must cover the enabled carry legs")
    if not np.isfinite(per_asset_weight) or per_asset_weight <= 0.0:
        raise ValueError("per_asset_weight must be positive and finite")

    dates = pd.DatetimeIndex(sorted({_as_utc(value) for value in calendar}))
    if dates.empty:
        return {}, pd.DataFrame(columns=["date", "asset", "mean_funding", "selected_side"])
    assets = tuple(str(asset) for asset in assets)
    funding = funding_rates.copy()
    funding.index = pd.DatetimeIndex([_as_utc(value) for value in funding.index])
    funding = funding[~funding.index.duplicated(keep="last")].sort_index()
    columns = {str(column).casefold(): str(column) for column in funding.columns}
    anchor = dates[0].normalize()
    schedule: dict[pd.Timestamp, pd.Series] = {}
    audit_rows: list[dict[str, Any]] = []

    for date in dates:
        normalized_date = date.normalize()
        if (normalized_date - anchor).days % rebalance_days:
            continue
        base = _state_at(base_targets, date)
        excluded = {str(asset) for asset, weight in base.items() if abs(float(weight)) > 1e-15}
        scores: dict[str, float] = {}
        for asset in assets:
            if asset in excluded:
                continue
            if market_available is not None and not market_available(asset, date):
                continue
            column = columns.get(asset.casefold())
            if column is None:
                continue
            window_start = date - pd.Timedelta(days=lookback_days)
            history = pd.to_numeric(
                funding.loc[(funding.index >= window_start) & (funding.index < date), column],
                errors="coerce",
            ).dropna()
            if len(history) < min_settlements:
                continue
            scores[asset] = float(history.mean())

        if len(scores) < min_assets:
            schedule[date] = pd.Series(dtype=float)
            audit_rows.append(
                {
                    "date": date,
                    "asset": None,
                    "mean_funding": float("nan"),
                    "selected_side": "empty",
                }
            )
            continue

        ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]))
        if long_enabled:
            eligible_longs = [
                asset
                for asset, _ in ranked
                if long_trend_ok is None or long_trend_ok(asset, date)
            ]
            long_assets = set(eligible_longs[:count])
        else:
            long_assets = set()
        short_assets = {asset for asset, _ in ranked[-count:]} if short_enabled else set()
        weights: dict[str, float] = {}
        for asset in sorted(long_assets):
            weights[asset] = per_asset_weight
        for asset in sorted(short_assets):
            weights[asset] = -per_asset_weight
        target = pd.Series(weights, dtype=float)
        schedule[date] = target.sort_index()
        for asset, score in sorted(scores.items()):
            side = "long" if asset in long_assets else "short" if asset in short_assets else "none"
            audit_rows.append(
                {
                    "date": date,
                    "asset": asset,
                    "mean_funding": score,
                    "selected_side": side,
                }
            )

    return schedule, pd.DataFrame(
        audit_rows,
        columns=["date", "asset", "mean_funding", "selected_side"],
    )


def _scale_schedule(
    schedule: Mapping[pd.Timestamp, pd.Series],
    scale: float,
) -> dict[pd.Timestamp, pd.Series]:
    if not np.isfinite(scale) or scale < 0.0:
        raise ValueError("scale must be finite and non-negative")
    return {date: _normalise_target(target) * float(scale) for date, target in schedule.items()}


def _sample_metrics(returns: pd.Series, sample: str) -> dict[str, float]:
    start, end = SAMPLE_WINDOWS[sample]
    segment = returns.loc[
        (returns.index >= pd.Timestamp(start, tz="UTC"))
        & (returns.index <= pd.Timestamp(end, tz="UTC"))
    ]
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def _run_engine(
    *,
    mark_candles: Mapping[str, pd.DataFrame],
    market_candles: Mapping[str, pd.DataFrame],
    targets: Mapping[pd.Timestamp, pd.Series],
    funding: pd.DataFrame,
    funding_intervals: Mapping[str, float],
    funding_missing_policy: str,
    funding_stress: str,
    funding_multiplier: float,
    cost_bps: float,
    long_buffer: float,
    target_gross: float,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
) -> Any:
    config = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(long_buffer),
        short_buffer=float(FROZEN_CONFIG["short_buffer"]),
        short_stop_loss_pct=float(FROZEN_CONFIG["short_stop_loss_pct"]),
        max_gross_exposure=float(target_gross),
        hard_gross_exposure=float(FROZEN_CONFIG["max_total_gross"]),
        funding_missing_policy=funding_missing_policy,
        funding_stress=funding_stress,
        funding_multiplier=float(funding_multiplier),
        missing_mark_policy="carry",
        missing_mark_max_carry_hours=3,
        fill_missing_policy="error",
    )
    return run_derivative_backtest(
        mark_candles,
        targets,
        funding_rates=funding,
        funding_intervals_hours=funding_intervals,
        market_candles=market_candles,
        config=config,
        start_time=start_time,
        end_time=end_time,
    )


def _scenario_config(name: str) -> tuple[str, float]:
    scenarios = {
        "normal": ("none", 1.0),
        "two-sided-adverse-1x": ("two-sided-adverse", 1.0),
        "two-sided-adverse-3x": ("two-sided-adverse", 3.0),
    }
    if name not in scenarios:
        raise ValueError(f"unknown funding scenario: {name}")
    return scenarios[name]


def _summary_row(
    *,
    label: str,
    allocation: float,
    cost_bps: float,
    scenario: str,
    result: Any,
    target_audit: pd.DataFrame,
    long_buffer: float,
    target_gross: float,
    base: bool = False,
) -> dict[str, Any]:
    full = _sample_metrics(result.daily_returns, "full")
    discovery = _sample_metrics(result.daily_returns, "discovery")
    validation = _sample_metrics(result.daily_returns, "validation")
    mark_carries = result.mark_carries
    return {
        "label": label,
        "allocation": allocation,
        "cost_bps": float(cost_bps),
        "funding_scenario": scenario,
        "base": bool(base),
        "long_buffer": float(long_buffer),
        "target_gross": float(target_gross),
        "full_multiple": full["multiple"],
        "full_cagr": full["cagr"],
        "full_sharpe": full["sharpe"],
        "full_max_drawdown": full["max_drawdown"],
        "discovery_multiple": discovery["multiple"],
        "discovery_sharpe": discovery["sharpe"],
        "validation_multiple": validation["multiple"],
        "validation_sharpe": validation["sharpe"],
        "mean_gross": float(result.gross_exposure.mean()),
        "max_observed_gross": float(result.gross_exposure.max()),
        "gross_breach_hours": int(
            (result.gross_exposure > float(FROZEN_CONFIG["max_total_gross"]) + 1e-12).sum()
        ),
        "liquidation_count": int(len(result.liquidations)),
        "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
        "fees_total": float(result.trades["fee"].sum()) if not result.trades.empty else 0.0,
        "mark_carry_count": int(len(mark_carries)),
        "mark_carry_max_hours": (
            float(pd.to_numeric(mark_carries["hours"], errors="coerce").max())
            if not mark_carries.empty
            else 0.0
        ),
        "mean_requested_sleeve_gross": (
            float(target_audit["requested_sleeve_gross"].mean())
            if "requested_sleeve_gross" in target_audit.columns and not target_audit.empty
            else 0.0
        ),
        "max_requested_sleeve_gross": (
            float(target_audit["requested_sleeve_gross"].max())
            if "requested_sleeve_gross" in target_audit.columns and not target_audit.empty
            else 0.0
        ),
        "mean_combined_gross": (
            float(target_audit["total_gross"].mean())
            if "total_gross" in target_audit.columns and not target_audit.empty
            else 0.0
        ),
    }


def candidate_passes_reference(
    candidate: Mapping[str, Any],
    reference: Mapping[str, Any],
    *,
    max_mdd_slippage: float = 0.01,
) -> bool:
    """Compare a candidate with a saved candidate on the same frozen metrics."""
    return bool(
        float(candidate["full_multiple"]) >= float(reference["full_multiple"])
        and float(candidate["full_sharpe"]) > float(reference["full_sharpe"])
        and float(candidate["full_max_drawdown"])
        >= float(reference["full_max_drawdown"]) - float(max_mdd_slippage)
        and float(candidate["validation_multiple"]) >= float(reference["validation_multiple"])
        and float(candidate["validation_sharpe"]) >= float(reference["validation_sharpe"])
    )


def _report(
    summary: pd.DataFrame,
    schedule_audit: pd.DataFrame,
    *,
    trial_id: str,
    core_assets: Sequence[str],
    mark_count: int,
    market_count: int,
    start_date: str,
    end_date: str,
    reference: Mapping[str, Any] | None = None,
    reference_label: str = "reference",
) -> str:
    selected = schedule_audit.loc[schedule_audit["selected_side"].isin(["long", "short"])]
    lines = [
        f"# {trial_id}",
        "",
        f"- Window: {start_date} → {end_date} (UTC)",
        f"- Core universe: {', '.join(core_assets)}",
        f"- Bitget mark symbols: {mark_count}; Bitget market symbols: {market_count}",
        "- Base: frozen LS57; only residual gross is used by the carry sleeve",
        "- Signal: Binance 8h funding settlements strictly before D; D settlement excluded",
        "- Execution: T+1 UTC +3h; Bitget mark for mark/liquidation; Bitget market for fills",
        "- This is research-only; no orders are routed",
        "",
        "## Runs",
        "",
        dataframe_to_markdown(
            summary[
                [
                    "label",
                    "allocation",
                    "cost_bps",
                    "funding_scenario",
                    "full_multiple",
                    "full_sharpe",
                    "full_max_drawdown",
                    "validation_multiple",
                    "validation_sharpe",
                    "max_observed_gross",
                    "gross_breach_hours",
                    "liquidation_count",
                    "mark_carry_count",
                    "mark_carry_max_hours",
                ]
            ].reset_index(drop=True)
        ),
        "",
        "## Sleeve selection audit",
        "",
        f"- Weekly signal dates with at least one selected carry leg: {selected['date'].nunique() if not selected.empty else 0}",
        f"- Total selected leg-observations: {len(selected)}",
        f"- Long observations: {int((selected['selected_side'] == 'long').sum()) if not selected.empty else 0}",
        f"- Short observations: {int((selected['selected_side'] == 'short').sum()) if not selected.empty else 0}",
        "",
        "## Decision",
        "",
    ]
    if summary.empty:
        lines.append("No runs completed.")
    else:
        base = summary.loc[
            (summary["base"]) & (summary["cost_bps"] == 20.0) & (summary["funding_scenario"] == "normal")
        ]
        candidate = summary.loc[
            (~summary["base"])
            & (summary["cost_bps"] == 20.0)
            & (summary["funding_scenario"] == "normal")
        ]
        if base.empty or candidate.empty:
            lines.append("Baseline/candidate normal 20bps run is incomplete; no promotion inference.")
        else:
            base_row = base.iloc[0]
            best = candidate.sort_values(["full_multiple", "full_sharpe"], ascending=False).iloc[0]
            lines.append(
                f"Best pre-registered 20bps allocation: {best['allocation']:.0%}; "
                f"full {best['full_multiple']:.4f}x / Sharpe {best['full_sharpe']:.4f} / "
                f"MDD {best['full_max_drawdown']:.4%}; validation "
                f"{best['validation_multiple']:.4f}x / Sharpe {best['validation_sharpe']:.4f}."
            )
            if reference is not None:
                passed = candidate_passes_reference(best, reference)
                lines.append(
                    f"Saved reference {reference_label}: {float(reference['full_multiple']):.4f}x / "
                    f"Sharpe {float(reference['full_sharpe']):.4f} / MDD "
                    f"{float(reference['full_max_drawdown']):.4%}; validation "
                    f"{float(reference['validation_multiple']):.4f}x / Sharpe "
                    f"{float(reference['validation_sharpe']):.4f}."
                )
                lines.append(
                    "Pre-registered reference comparison: **PASS**."
                    if passed
                    else "Pre-registered reference comparison: **FAIL**."
                )
            else:
                passed = (
                    best["full_multiple"] > base_row["full_multiple"]
                    and best["full_sharpe"] > base_row["full_sharpe"]
                    and best["full_max_drawdown"] >= base_row["full_max_drawdown"] - 0.01
                    and best["validation_multiple"] > base_row["validation_multiple"]
                    and best["validation_sharpe"] > base_row["validation_sharpe"]
                    and best["liquidation_count"] == 0
                    and best["gross_breach_hours"] == 0
                    and best["mark_carry_max_hours"] <= 3.0
                )
                lines.append(
                    "Primary 20bps normal gate: **PASS**." if passed else "Primary 20bps normal gate: **FAIL**."
                )
            if passed:
                lines.append(
                    "This is not a live promotion. Cost, adverse-funding, rolling, bootstrap and "
                    "independent OOS checks remain required."
                )
    lines.extend(["", "Research output only; not an order or a live approval.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", default=TRIAL_ID)
    parser.add_argument("--warmup-start", default="2021-01-01")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_20261009"))
    parser.add_argument(
        "--market-dir",
        type=Path,
        default=Path("data/raw/bitget_derivatives/merged_market_20261009"),
    )
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--variant", choices=("core8", "extended10"), default="core8")
    parser.add_argument("--costs-bps", default="20")
    parser.add_argument("--allocations", default="0.10,0.20,0.25")
    parser.add_argument("--funding-scenarios", default="normal")
    parser.add_argument("--carry-side", choices=("both", "long-only", "short-only"), default="both")
    parser.add_argument(
        "--carry-long-trend-ma",
        type=int,
        default=0,
        help="require carry long candidates above their own completed N-day SMA; 0 disables",
    )
    parser.add_argument("--long-buffer", type=float, default=float(FROZEN_CONFIG["long_buffer"]))
    parser.add_argument("--target-gross", type=float, default=float(FROZEN_CONFIG["max_total_gross"]))
    parser.add_argument("--funding-source", choices=("binance-proxy", "bitget-exact"), default="binance-proxy")
    parser.add_argument(
        "--funding-missing-policy",
        choices=("error", "skip", "carry_last", "stress_median"),
        default="skip",
    )
    parser.add_argument(
        "--save-raw-ledgers",
        action="store_true",
        help="retain per-run funding and trade ledgers; disabled by default to keep reports lean",
    )
    parser.add_argument(
        "--reference-run-summary",
        type=Path,
        default=None,
        help="optional saved run_summary.csv for a pre-registered candidate comparison",
    )
    parser.add_argument("--reference-label", default="reference")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    configure_logging("ERROR")

    costs = [float(value) for value in args.costs_bps.split(",") if value.strip()]
    allocations = [float(value) for value in args.allocations.split(",") if value.strip()]
    scenarios = [value.strip() for value in args.funding_scenarios.split(",") if value.strip()]
    long_enabled = args.carry_side in {"both", "long-only"}
    short_enabled = args.carry_side in {"both", "short-only"}
    if not costs or not allocations or not scenarios:
        parser.error("costs, allocations and funding scenarios must be non-empty")
    if any(value < 0.0 for value in costs + allocations):
        parser.error("costs and allocations must be non-negative")
    if not 0.0 < args.long_buffer < 1.0:
        parser.error("long-buffer must be in (0, 1)")
    if not 0.0 < args.target_gross <= float(FROZEN_CONFIG["max_total_gross"]):
        parser.error("target-gross must be positive and no greater than the frozen gross cap")
    core_assets = CORE8 if args.variant == "core8" else EXTENDED10
    start_time = pd.Timestamp(args.start_date, tz="UTC")
    end_time = pd.Timestamp(args.end_date, tz="UTC")
    if start_time >= end_time:
        parser.error("start-date must precede end-date")

    _, market, universe, index = _load_market(
        args.config,
        start_date=args.warmup_start,
        end_date=args.end_date,
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_raw = _long_targets_from_build(built, index)
    mark_symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    market_symbol_map = pd.read_csv(args.market_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, mark_symbol_map)
    market_candles = load_mark_candles(
        args.market_dir,
        market_symbol_map,
        candle_type="market",
    )
    trade_available = set(mark_candles).intersection(market_candles)
    long_trend_ok = (
        build_asset_trend_filter(mark_candles, ma_days=args.carry_long_trend_ma)
        if args.carry_long_trend_ma > 0
        else None
    )
    restricted, dropped = _restrict_targets(long_raw, trade_available, market_candles)
    long_targets = scale_long_targets(
        restricted,
        leverage=float(FROZEN_CONFIG["h5_leverage"]),
        max_gross=float(FROZEN_CONFIG["h5_leverage"]),
    )
    funding = _funding_for_source(
        args.funding_source,
        raw_dir=args.raw_dir,
        binance_dir=args.binance_funding_dir,
        symbol_map=mark_symbol_map,
        coins=set(market.price.columns),
    )
    if funding.empty:
        raise SystemExit("funding data is empty; LS81 requires a historical funding proxy")
    funding = funding.dropna(how="all").loc[:, funding.notna().any(axis=0)]
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in mark_symbol_map.columns:
        for record in mark_symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)

    long_targets, long_audit = build_long_targets_for_trial(
        trial_id=LS57_CANDIDATE_ID,
        long_targets=long_targets,
        funding_rates=funding,
        universe=universe,
        available=trade_available,
        prices=market.price,
    )
    short_targets, sleeve_audit, _, _ = build_short_targets_for_trial(
        trial_id=LS57_CANDIDATE_ID,
        market=market,
        universe=universe,
        index=index,
        long_raw=long_raw,
        long_targets=long_targets,
        funding=funding,
        available=trade_available,
        mark_candles=market_candles,
        start_date=args.warmup_start,
        profit_lock_audit=long_audit,
    )
    base_targets, base_audit = combine_long_with_cash_budgeted_short(
        long_targets,
        short_targets,
        max_total_gross=float(FROZEN_CONFIG["max_total_gross"]),
    )
    carry_schedule, schedule_audit = build_pit_funding_carry_schedule(
        funding_rates=funding,
        calendar=index,
        assets=core_assets,
        base_targets=base_targets,
        market_available=lambda asset, date: _mark_available(
            mark_candles,
            market_candles,
            asset,
            date,
            lookback_days=3,
        ),
        rebalance_days=7,
        lookback_days=7,
        min_settlements=3,
        min_assets=6,
        count=2,
        per_asset_weight=0.25,
        long_enabled=long_enabled,
        short_enabled=short_enabled,
        long_trend_ok=long_trend_ok,
    )
    raw_sleeve_gross = max(
        (float(target.abs().sum()) for target in carry_schedule.values()),
        default=0.0,
    )
    for asset in core_assets:
        if asset not in funding.columns:
            raise SystemExit(f"core asset missing funding history: {asset}")
        if asset not in trade_available:
            raise SystemExit(f"core asset missing Bitget mark/market history: {asset}")

    summary_rows: list[dict[str, Any]] = []
    result_frames: dict[str, pd.DataFrame] = {}
    event_frames: dict[str, dict[str, pd.DataFrame]] = {}
    for scenario in scenarios:
        stress, multiplier = _scenario_config(scenario)
        for cost in costs:
            base_result = _run_engine(
                mark_candles=mark_candles,
                market_candles=market_candles,
                targets=base_targets,
                funding=funding,
                funding_intervals=funding_intervals,
                funding_missing_policy=args.funding_missing_policy,
                funding_stress=stress,
                funding_multiplier=multiplier,
                cost_bps=cost,
                long_buffer=args.long_buffer,
                target_gross=args.target_gross,
                start_time=start_time,
                end_time=end_time,
            )
            summary_rows.append(
                _summary_row(
                    label="LS57 baseline",
                    allocation=0.0,
                    cost_bps=cost,
                    scenario=scenario,
                    result=base_result,
                    target_audit=base_audit,
                    long_buffer=args.long_buffer,
                    target_gross=args.target_gross,
                    base=True,
                )
            )
            base_key = f"base_{scenario}_{cost:g}"
            event_frames[base_key] = {
                "liquidations": base_result.liquidations,
                "mark_carries": base_result.mark_carries,
            }
            if args.save_raw_ledgers:
                event_frames[base_key].update(
                    {"trades": base_result.trades, "funding": base_result.funding}
                )
            for allocation in allocations:
                sleeve_scale = (
                    float(allocation) / raw_sleeve_gross
                    if raw_sleeve_gross > 0.0
                    else 0.0
                )
                scaled = _scale_schedule(carry_schedule, sleeve_scale)
                combined, target_audit = combine_signed_book_with_residual_sleeve(
                    base_targets,
                    scaled,
                    max_total_gross=float(args.target_gross),
                )
                result = _run_engine(
                    mark_candles=mark_candles,
                    market_candles=market_candles,
                    targets=combined,
                    funding=funding,
                    funding_intervals=funding_intervals,
                    funding_missing_policy=args.funding_missing_policy,
                    funding_stress=stress,
                    funding_multiplier=multiplier,
                    cost_bps=cost,
                    long_buffer=args.long_buffer,
                    target_gross=args.target_gross,
                    start_time=start_time,
                    end_time=end_time,
                )
                label = f"core8 {allocation:.0%} residual"
                if args.variant == "extended10":
                    label = f"extended10 {allocation:.0%} residual"
                if args.carry_side != "both":
                    label = f"{args.variant} {args.carry_side} {allocation:.0%} gross"
                if args.carry_long_trend_ma > 0:
                    label = f"{label} longMA{args.carry_long_trend_ma}"
                summary_rows.append(
                    _summary_row(
                        label=label,
                        allocation=allocation,
                        cost_bps=cost,
                        scenario=scenario,
                        result=result,
                        target_audit=target_audit,
                        long_buffer=args.long_buffer,
                        target_gross=args.target_gross,
                    )
                )
                key = f"{scenario}_{cost:g}_{allocation:.2f}"
                result_frames[key] = pd.DataFrame(
                    {
                        "daily_return": result.daily_returns,
                        "gross_exposure": result.gross_exposure.reindex(result.daily_returns.index),
                    }
                )
                event_frames[key] = {
                    "liquidations": result.liquidations,
                    "mark_carries": result.mark_carries,
                }
                if args.save_raw_ledgers:
                    event_frames[key].update(
                        {"trades": result.trades, "funding": result.funding}
                    )

    summary = pd.DataFrame(summary_rows)
    reference_row: pd.Series | None = None
    if args.reference_run_summary is not None:
        reference_summary = pd.read_csv(args.reference_run_summary)
        reference_candidates = reference_summary.loc[
            (~reference_summary["base"].astype(bool))
            & (pd.to_numeric(reference_summary["cost_bps"], errors="coerce") == 20.0)
            & (reference_summary["funding_scenario"].astype(str) == "normal")
        ]
        if reference_candidates.empty:
            raise SystemExit(
                f"reference summary has no 20bps normal candidate: {args.reference_run_summary}"
            )
        reference_row = reference_candidates.iloc[0]
    output_dir = ensure_dir(args.output_dir)
    summary.to_csv(output_dir / "run_summary.csv", index=False)
    schedule_audit.to_csv(output_dir / "funding_schedule_audit.csv", index=False)
    pd.DataFrame(base_audit).to_csv(output_dir / "base_target_gross.csv", index_label="date")
    pd.DataFrame(carry_schedule).T.to_csv(output_dir / "carry_schedule.csv", index_label="date")
    for key, frame in result_frames.items():
        frame.to_csv(output_dir / f"daily_{key}.csv", index_label="date")
    for key, frames in event_frames.items():
        for name, frame in frames.items():
            frame.to_csv(output_dir / f"{name}_{key}.csv", index=False)
    manifest = {
        "trial_id": args.trial_id,
        "variant": args.variant,
        "carry_side": args.carry_side,
        "carry_long_trend_ma": args.carry_long_trend_ma,
        "raw_sleeve_gross": raw_sleeve_gross,
        "core_assets": list(core_assets),
        "warmup_start": args.warmup_start,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "costs_bps": costs,
        "allocations": allocations,
        "funding_scenarios": scenarios,
        "funding_source": args.funding_source,
        "funding_missing_policy": args.funding_missing_policy,
        "mark_source": "bitget_mark",
        "fill_source": "bitget_market",
        "missing_mark_policy": "carry",
        "missing_mark_max_carry_hours": 3,
        "gross_cap": float(FROZEN_CONFIG["max_total_gross"]),
        "target_gross": float(args.target_gross),
        "long_buffer": float(args.long_buffer),
        "orders_sent": False,
        "raw_ledgers_retained": bool(args.save_raw_ledgers),
        "reference_run_summary": (
            str(args.reference_run_summary) if args.reference_run_summary is not None else None
        ),
        "reference_label": args.reference_label if args.reference_run_summary is not None else None,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(
        _report(
            summary,
            schedule_audit,
            trial_id=args.trial_id,
            core_assets=core_assets,
            mark_count=len(mark_candles),
            market_count=len(market_candles),
            start_date=args.start_date,
            end_date=args.end_date,
            reference=reference_row,
            reference_label=args.reference_label,
        ),
        encoding="utf-8",
    )
    print(f"wrote {output_dir}; runs={len(summary)}")
    print(summary[["label", "allocation", "cost_bps", "funding_scenario", "full_multiple", "full_sharpe", "full_max_drawdown"]].to_string(index=False))


if __name__ == "__main__":
    main()
