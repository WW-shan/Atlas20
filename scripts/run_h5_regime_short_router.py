"""Run the pre-registered H5 regime-routed dual-short research trial.

LS12 keeps the frozen H5 1.25x long book and holds at most one short sleeve:
a weekly weakest-four basket in BTC bear regimes, or funding-crowded H5 exits
outside bear regimes.  This is research only and never routes orders.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.derivatives.signals import (  # noqa: E402
    EXIT_SHORT_HOLDING_DAYS,
    build_cross_sectional_weak_short_schedule,
    build_exit_short_schedule,
    combine_long_with_cash_budgeted_short,
    funding_rank_percentile,
    scale_long_targets,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
    _short_mark_available,
)
from scripts.run_h5_exit_short import (  # noqa: E402
    _as_utc,
    _eligible_members_by_date,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

BASELINE_ID = "PR2026-10-D-L125"
CANDIDATE_ID = "PR2026-11-LS12-H5-REGIME-SHORT-ROUTER"
NO_TRADE_BAND_CANDIDATE_ID = "PR2026-11-LS16-H5-REGIME-SHORT-NOTRADE5"
NO_TRADE_BAND_FRACTION = 0.05
SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-regime-short-router-design.md"
NO_TRADE_BAND_SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-no-trade-band-design.md"
SHORT_CANDIDATES = {
    CANDIDATE_ID: 0.0,
    NO_TRADE_BAND_CANDIDATE_ID: NO_TRADE_BAND_FRACTION,
}
FROZEN_CONFIG: dict[str, Any] = {
    "h5_leverage": 1.25,
    "max_total_gross": 1.50,
    "long_buffer": 0.50,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
    "btc_ma_window": 200,
    "bear_lookback_days": 14,
    "bear_rebalance_days": 7,
    "bear_short_count": 4,
    "bear_per_asset_weight": 0.0625,
    "bear_funding_lookback_settlements": 3,
    "bear_funding_threshold": -0.0002,
    "exit_holding_days": EXIT_SHORT_HOLDING_DAYS,
    "exit_per_asset_weight": 0.025,
    "exit_funding_lookback_days": 7,
    "exit_funding_rank_min": 2.0 / 3.0,
    "exit_funding_min_assets": 5,
}
CONSTRUCTION = (
    "H5 1.25x + exactly one short sleeve selected by BTC close versus its "
    "200D SMA: bear = weekly 14D weakest-four PIT Top20 non-H5 basket; "
    "non-bear = 21D funding-top-tercile H5 exits; total short <=0.25x and "
    "hard total gross 1.50x"
)
NO_TRADE_BAND_CONSTRUCTION = (
    CONSTRUCTION
    + "; existing same-side positions use a 5% NAV no-trade region and only "
    "trade beyond that boundary, while opens/exits/side flips stay exact"
)


def _empty_weights() -> pd.Series:
    return pd.Series(dtype=float)


def _target_equal(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    index = pd.Index(left).union(pd.Index(right))
    left_values = pd.Series(left, dtype=float).reindex(index).fillna(0.0)
    right_values = pd.Series(right, dtype=float).reindex(index).fillna(0.0)
    difference = (left_values - right_values).abs()
    return bool(difference.empty or float(difference.max()) <= 1e-12)


def _normalize_short_schedule(
    schedule: Mapping[pd.Timestamp, pd.Series],
) -> dict[pd.Timestamp, pd.Series]:
    normalized: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in schedule.items():
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or (target < 0.0).any():
            raise ValueError("short sleeve targets must be finite and non-negative")
        normalized[date] = target.astype(float).sort_index()
    return dict(sorted(normalized.items()))


def _btc_bear_regime(
    btc_close: pd.Series,
    index: pd.DatetimeIndex,
    *,
    ma_window: int,
) -> pd.Series:
    """Return the point-in-time BTC close-below-SMA regime on every signal day."""
    if ma_window < 1:
        raise ValueError("ma_window must be positive")
    close = pd.to_numeric(pd.Series(btc_close), errors="coerce").dropna()
    close.index = pd.DatetimeIndex([_as_utc(value) for value in close.index])
    close = close[~close.index.duplicated(keep="last")].sort_index()
    threshold = close.rolling(ma_window, min_periods=ma_window).mean()
    target_index = pd.DatetimeIndex([_as_utc(value) for value in index])
    regime = (close < threshold).reindex(target_index).ffill()
    return regime.fillna(False).astype(bool)


def route_short_sleeves(
    *,
    calendar: pd.DatetimeIndex,
    bear: pd.Series,
    bear_schedule: Mapping[pd.Timestamp, pd.Series],
    non_bear_schedule: Mapping[pd.Timestamp, pd.Series],
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Route two precomputed schedules while enforcing one active sleeve.

    The inactive sleeve is flattened at the next signal day.  A position that
    existed before a regime change cannot reappear merely because it remains
    present in a stale exit-sleeve snapshot; only a genuinely new exit event
    can open it again outside bear periods.
    """
    dates = pd.DatetimeIndex([_as_utc(value) for value in calendar])
    if dates.empty:
        return {}, pd.DataFrame(columns=["date", "regime", "active_sleeve", "short_gross"])
    regime = bear.reindex(dates).ffill().fillna(False).astype(bool)
    bear_events = _normalize_short_schedule(bear_schedule)
    exit_events = _normalize_short_schedule(non_bear_schedule)
    bear_dates = list(bear_events)
    exit_dates = list(exit_events)
    bear_cursor = 0
    exit_cursor = 0
    bear_raw = _empty_weights()
    exit_raw = _empty_weights()
    active_bear = _empty_weights()
    active_exit = _empty_weights()
    previous: pd.Series | None = None
    previous_regime: bool | None = None
    routed: dict[pd.Timestamp, pd.Series] = {}
    audit_rows: list[dict[str, object]] = []

    for date in dates:
        bear_event = False
        while bear_cursor < len(bear_dates) and bear_dates[bear_cursor] <= date:
            bear_raw = bear_events[bear_dates[bear_cursor]].copy()
            bear_event = bear_dates[bear_cursor] == date
            bear_cursor += 1
        exit_event = False
        old_exit_assets = set(exit_raw.index)
        while exit_cursor < len(exit_dates) and exit_dates[exit_cursor] <= date:
            exit_raw = exit_events[exit_dates[exit_cursor]].copy()
            exit_event = exit_dates[exit_cursor] == date
            exit_cursor += 1
        exit_added = exit_raw.index.difference(pd.Index(sorted(old_exit_assets))).astype(str)

        is_bear = bool(regime.loc[date])
        switched = previous_regime is not None and is_bear != previous_regime
        if is_bear:
            active_exit = _empty_weights()
            if switched:
                active_bear = _empty_weights()
            if bear_event:
                active_bear = bear_raw.copy()
        else:
            active_bear = _empty_weights()
            if switched:
                active_exit = _empty_weights()
            retained = active_exit.index.intersection(exit_raw.index)
            active_exit = active_exit.reindex(retained).fillna(0.0)
            if exit_event:
                for asset in exit_added:
                    weight = float(exit_raw.get(asset, 0.0))
                    if weight > 0.0:
                        active_exit.loc[str(asset)] = weight
            active_exit = active_exit.sort_index()

        routed_target = (active_bear if is_bear else active_exit).copy()
        if previous is None or not _target_equal(previous.to_dict(), routed_target.to_dict()):
            routed[date] = routed_target
            previous = routed_target.copy()
        audit_rows.append(
            {
                "date": date,
                "regime": "bear" if is_bear else "non_bear",
                "active_sleeve": "bear_weak4" if is_bear else "funding_exit",
                "short_gross": float(routed_target.sum()),
            }
        )
        previous_regime = is_bear

    return routed, pd.DataFrame(audit_rows)


def _write_schedule(path: Path, schedule: Mapping[pd.Timestamp, pd.Series]) -> None:
    rows = [
        {"date": date, "asset": str(asset), "weight": float(weight)}
        for date, target in sorted(schedule.items())
        for asset, weight in target.items()
        if abs(float(weight)) > 1e-15
    ]
    pd.DataFrame(rows, columns=["date", "asset", "weight"]).to_csv(path, index=False)


def build_regime_short_schedules(
    *,
    market: Any,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    long_raw: Mapping[pd.Timestamp, pd.Series],
    long_targets: Mapping[pd.Timestamp, pd.Series],
    funding: pd.DataFrame,
    available: set[str],
    mark_candles: dict[str, pd.DataFrame],
    start_date: str,
) -> tuple[
    dict[pd.Timestamp, pd.Series],
    pd.DataFrame,
    dict[pd.Timestamp, pd.Series],
    dict[pd.Timestamp, pd.Series],
]:
    """Build the frozen LS12 short router from market and H5 inputs."""
    bear = _btc_bear_regime(
        market.price["bitcoin"],
        index,
        ma_window=int(FROZEN_CONFIG["btc_ma_window"]),
    )
    bear_schedule = build_cross_sectional_weak_short_schedule(
        market.price,
        universe,
        long_targets,
        calendar=index,
        funding_rates=funding if not funding.empty else None,
        eligible=available,
        short_available=lambda asset, date: _short_mark_available(mark_candles, asset, date),
        lookback=int(FROZEN_CONFIG["bear_lookback_days"]),
        rebalance_days=int(FROZEN_CONFIG["bear_rebalance_days"]),
        short_count=int(FROZEN_CONFIG["bear_short_count"]),
        per_asset_weight=float(FROZEN_CONFIG["bear_per_asset_weight"]),
        funding_threshold=float(FROZEN_CONFIG["bear_funding_threshold"]),
        funding_lookback=int(FROZEN_CONFIG["bear_funding_lookback_settlements"]),
        anchor=start_date,
    )
    eligible_by_date = _eligible_members_by_date(universe, list(long_raw))

    def exit_entry_allowed(asset: str, date: pd.Timestamp) -> bool:
        if not _short_mark_available(mark_candles, asset, date):
            return False
        rank = funding_rank_percentile(
            funding if not funding.empty else None,
            universe,
            asset,
            as_of=date,
            eligible=available,
            lookback_days=int(FROZEN_CONFIG["exit_funding_lookback_days"]),
            min_assets=int(FROZEN_CONFIG["exit_funding_min_assets"]),
        )
        return rank is not None and rank >= float(FROZEN_CONFIG["exit_funding_rank_min"])

    exit_schedule = build_exit_short_schedule(
        long_raw,
        holding_days=int(FROZEN_CONFIG["exit_holding_days"]),
        eligible_by_date=eligible_by_date,
        per_asset_weight=float(FROZEN_CONFIG["exit_per_asset_weight"]),
        entry_allowed=exit_entry_allowed,
    )
    short_targets, sleeve_audit = route_short_sleeves(
        calendar=index,
        bear=bear,
        bear_schedule=bear_schedule,
        non_bear_schedule=exit_schedule,
    )
    return short_targets, sleeve_audit, bear_schedule, exit_schedule


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--trial-id",
        choices=(BASELINE_ID, CANDIDATE_ID, NO_TRADE_BAND_CANDIDATE_ID),
        required=True,
    )
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_20261009"))
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--funding-source", choices=("zero", "binance-proxy", "bitget-exact"), default="binance-proxy")
    parser.add_argument("--funding-stress", choices=("none", "long-adverse", "short-adverse"), default="none")
    parser.add_argument("--funding-multiplier", type=float, default=1.0)
    parser.add_argument("--funding-missing-policy", choices=("error", "skip", "carry_last", "stress_median"), default="skip")
    parser.add_argument("--missing-mark-policy", choices=("error", "carry", "exit_last"), default="carry")
    parser.add_argument("--missing-mark-max-carry-hours", type=int, default=3)
    args = parser.parse_args()
    configure_logging("ERROR")

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_raw = _long_targets_from_build(built, index)
    symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, symbol_map)
    available = set(mark_candles)
    restricted, dropped = _restrict_targets(long_raw, available, mark_candles)
    long_targets = scale_long_targets(
        restricted,
        leverage=float(FROZEN_CONFIG["h5_leverage"]),
        max_gross=float(FROZEN_CONFIG["h5_leverage"]),
    )
    funding = _funding_for_source(
        args.funding_source,
        raw_dir=args.raw_dir,
        binance_dir=args.binance_funding_dir,
        symbol_map=symbol_map,
        coins=set(market.price.columns),
    )
    if not funding.empty:
        funding = funding.dropna(how="all").loc[:, funding.notna().any(axis=0)]
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in symbol_map.columns:
        for record in symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)

    short_targets: dict[pd.Timestamp, pd.Series] = {}
    sleeve_audit = pd.DataFrame(columns=["date", "regime", "active_sleeve", "short_gross"])
    bear_schedule: dict[pd.Timestamp, pd.Series] = {}
    exit_schedule: dict[pd.Timestamp, pd.Series] = {}
    if args.trial_id in SHORT_CANDIDATES:
        short_targets, sleeve_audit, bear_schedule, exit_schedule = build_regime_short_schedules(
            market=market,
            universe=universe,
            index=index,
            long_raw=long_raw,
            long_targets=long_targets,
            funding=funding,
            available=available,
            mark_candles=mark_candles,
            start_date=args.start_date,
        )

    combined, target_audit = combine_long_with_cash_budgeted_short(
        long_targets,
        short_targets,
        max_total_gross=float(FROZEN_CONFIG["max_total_gross"]),
    )
    cfg = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(FROZEN_CONFIG["long_buffer"]),
        short_buffer=float(FROZEN_CONFIG["short_buffer"]),
        short_stop_loss_pct=float(FROZEN_CONFIG["short_stop_loss_pct"]),
        max_gross_exposure=float(FROZEN_CONFIG["max_total_gross"]),
        rebalance_no_trade_band=float(SHORT_CANDIDATES.get(args.trial_id, 0.0)),
        funding_missing_policy=args.funding_missing_policy,
        funding_stress=args.funding_stress,
        funding_multiplier=float(args.funding_multiplier),
        missing_mark_policy=args.missing_mark_policy,
        missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
    )
    result = run_derivative_backtest(
        mark_candles,
        combined,
        funding_rates=funding if not funding.empty else None,
        funding_intervals_hours=funding_intervals if not funding.empty else None,
        config=cfg,
        start_time=pd.Timestamp(args.start_date, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )
    metrics = _metrics_from_returns(result.daily_returns)
    trades = result.trades
    short_side = trades.get("side", pd.Series(dtype=object)) == "short"
    stop_reason = trades.get("reason", pd.Series(dtype=object)) == "stop_loss"
    short_opens = int((short_side & (trades.get("action") == "open")).sum()) if not trades.empty else 0
    summary = {
        "trial_id": args.trial_id,
        "baseline": args.trial_id == BASELINE_ID,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": float(args.cost_bps),
        "funding_source": args.funding_source,
        "funding_stress": args.funding_stress,
        "funding_multiplier": float(args.funding_multiplier),
        "funding_missing_policy": args.funding_missing_policy,
        "mark_source": "bitget_mark",
        "missing_mark_policy": args.missing_mark_policy,
        "missing_mark_max_carry_hours": int(args.missing_mark_max_carry_hours),
        "h5_leverage": float(FROZEN_CONFIG["h5_leverage"]),
        "max_total_gross": float(FROZEN_CONFIG["max_total_gross"]),
        "rebalance_no_trade_band": float(SHORT_CANDIDATES.get(args.trial_id, 0.0)),
        "max_requested_short_gross": float(target_audit["requested_short_gross"].max()),
        "max_funded_short_gross": float(target_audit["funded_short_gross"].max()),
        "max_target_total_gross": float(target_audit["total_gross"].max()),
        "max_observed_gross": float(result.gross_exposure.max()) if not result.gross_exposure.empty else 0.0,
        "gross_breach_hours": int((result.gross_exposure > float(FROZEN_CONFIG["max_total_gross"]) + 1e-12).sum()),
        "short_open_count": short_opens,
        "stop_loss_count": int((short_side & stop_reason).sum()) if not trades.empty else 0,
        "liquidation_count": int(len(result.liquidations)),
        "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
        "fees_total": float(trades["fee"].sum()) if not trades.empty else 0.0,
        "bear_days": int((sleeve_audit["regime"] == "bear").sum()) if not sleeve_audit.empty else 0,
        "non_bear_days": int((sleeve_audit["regime"] == "non_bear").sum()) if not sleeve_audit.empty else 0,
        "regime_switch_count": int((sleeve_audit["regime"] != sleeve_audit["regime"].shift()).sum() - 1) if not sleeve_audit.empty else 0,
        "dropped_target_rows": int(len(dropped)),
        "available_mark_count": int(len(mark_candles)),
        **metrics,
    }
    output_dir = ensure_dir(Path(args.output_dir) / args.trial_id)
    result.equity_curve.to_csv(output_dir / "equity_curve.csv", header=True)
    result.daily_returns.to_csv(output_dir / "daily_returns.csv", header=True)
    result.trades.to_csv(output_dir / "trades.csv", index=False)
    result.funding.to_csv(output_dir / "funding.csv", index=False)
    result.liquidations.to_csv(output_dir / "liquidations.csv", index=False)
    result.positions.to_csv(output_dir / "positions.csv", index=False)
    result.gross_exposure.to_csv(output_dir / "gross_exposure.csv", header=True)
    target_audit.to_csv(output_dir / "target_gross.csv", index=False)
    sleeve_audit.to_csv(output_dir / "sleeve_audit.csv", index=False)
    _write_schedule(output_dir / "routed_short_schedule.csv", short_targets)
    _write_schedule(output_dir / "bear_weak4_schedule.csv", bear_schedule)
    _write_schedule(output_dir / "funding_exit_schedule.csv", exit_schedule)
    dropped.to_csv(output_dir / "dropped_targets.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "trial_id": args.trial_id,
                "window": "main",
                "fill": "lag0",
                "cost_bps": float(args.cost_bps),
                "sharpe": metrics["sharpe"],
                "multiple": metrics["multiple"],
                "max_drawdown": metrics["max_drawdown"],
                "source": str(output_dir / "summary.json"),
            }
        ]
    ).to_csv(output_dir / "trial_results.csv", index=False)
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "candidate_id": args.trial_id,
                "baseline": args.trial_id == BASELINE_ID,
                "spec": (
                    SPEC_PATH
                    if args.trial_id == CANDIDATE_ID
                    else NO_TRADE_BAND_SPEC_PATH
                    if args.trial_id == NO_TRADE_BAND_CANDIDATE_ID
                    else ""
                ),
                "construction": (
                    "H5 1.25x long-only"
                    if args.trial_id == BASELINE_ID
                    else NO_TRADE_BAND_CONSTRUCTION
                    if args.trial_id == NO_TRADE_BAND_CANDIDATE_ID
                    else CONSTRUCTION
                ),
                "frozen_config": {
                    **FROZEN_CONFIG,
                    "rebalance_no_trade_band": float(
                        SHORT_CANDIDATES.get(args.trial_id, 0.0)
                    ),
                },
                "start_date": args.start_date,
                "end_date": args.end_date,
                "cost_bps": float(args.cost_bps),
                "funding_source": args.funding_source,
                "funding_stress": args.funding_stress,
                "funding_multiplier": float(args.funding_multiplier),
                "mark_source": "bitget_mark",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                f"# {args.trial_id}",
                "",
                f"- Window: {args.start_date} to {args.end_date}",
                f"- Cost: {float(args.cost_bps):g} bps",
                f"- Terminal multiple: {metrics['multiple']:.4f}x",
                f"- Sharpe: {metrics['sharpe']:.4f}",
                f"- Max drawdown: {metrics['max_drawdown']:.4%}",
                f"- Max requested short gross: {summary['max_requested_short_gross']:.6f}x",
                f"- Rebalance no-trade band: {summary['rebalance_no_trade_band']:.4%} NAV",
                f"- Max observed gross: {summary['max_observed_gross']:.6f}x",
                f"- Gross breach hours: {summary['gross_breach_hours']}",
                f"- Liquidations: {summary['liquidation_count']}",
                f"- Short stop-losses: {summary['stop_loss_count']}",
                "",
                "Research output only; not an order or a live approval.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    print(f"Wrote regime short-router research output to {output_dir}")


if __name__ == "__main__":
    main()
