"""Run the pre-registered LS15 bull-market weak-H5 cash-buffer trial.

LS15 keeps the frozen LS12 dual-short router and applies a 10% cash buffer to
the whole target book only when BTC is above its 200D SMA while the
unthrottled H5 shadow has underperformed BTC over 14 days. Research only.
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
    combine_long_with_cash_budgeted_short,
    scale_long_targets,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_h5_exit_short import _as_utc  # noqa: E402
from scripts.run_h5_regime_short_router import (  # noqa: E402
    _btc_bear_regime,
    _target_equal,
    _write_schedule,
    build_regime_short_schedules,
)
from scripts.run_h5_relative_half_risk import weekly_relative_half_state  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

BASELINE_ID = "PR2026-10-D-L125"
CANDIDATE_ID = "PR2026-11-LS15-H5-BULL-WEAK-CASH10"
SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-bull-weak-cash10-design.md"
FROZEN_CONFIG: dict[str, Any] = {
    "h5_leverage": 1.25,
    "cash_buffer_gross_scale": 0.90,
    "relative_lookback_days": 14,
    "evaluation_days": 7,
    "btc_ma_window": 200,
    "max_total_gross": 1.50,
    "long_buffer": 0.50,
    "short_buffer": 0.50,
    "short_stop_loss_pct": 0.20,
}
CONSTRUCTION = (
    "Frozen LS12 H5 1.25x + regime-routed dual shorts; when BTC is above "
    "200D SMA and unthrottled H5 shadow 14D return is below BTC 14D return, "
    "scale the whole target book to 0.90; weekly state, T+1 UTC +3h"
)


def scale_target_book_by_state(
    targets: Mapping[pd.Timestamp, pd.Series],
    *,
    index: pd.DatetimeIndex,
    insurance: pd.Series,
    gross_scale: float,
) -> dict[pd.Timestamp, pd.Series]:
    """Scale signed target books while preserving their relative structure."""
    if not 0.0 < gross_scale <= 1.0:
        raise ValueError("gross_scale must be in (0, 1]")
    dates = pd.DatetimeIndex([_as_utc(value) for value in index])
    target_dates = sorted({_as_utc(value) for value in targets})
    state = insurance.reindex(dates).fillna(False).astype(bool)
    state_dates = set(state.index[state.ne(state.shift()).fillna(True)].tolist())
    event_dates = sorted(set(target_dates) | state_dates)
    cursor = 0
    last_target = pd.Series(dtype=float)
    previous: pd.Series | None = None
    scaled: dict[pd.Timestamp, pd.Series] = {}
    for date in event_dates:
        while cursor < len(target_dates) and target_dates[cursor] <= date:
            raw = pd.to_numeric(targets[target_dates[cursor]], errors="coerce").fillna(0.0)
            raw.index = raw.index.astype(str)
            last_target = raw.astype(float).sort_index()
            cursor += 1
        if last_target.empty:
            continue
        scale = float(gross_scale) if bool(state.get(date, False)) else 1.0
        target = last_target * scale
        if previous is None or not _target_equal(previous.to_dict(), target.to_dict()):
            scaled[date] = target
            previous = target.copy()
    return scaled


def _engine_config(args: argparse.Namespace) -> DerivativeBacktestConfig:
    return DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(FROZEN_CONFIG["long_buffer"]),
        short_buffer=float(FROZEN_CONFIG["short_buffer"]),
        short_stop_loss_pct=float(FROZEN_CONFIG["short_stop_loss_pct"]),
        max_gross_exposure=float(FROZEN_CONFIG["max_total_gross"]),
        funding_missing_policy=args.funding_missing_policy,
        funding_stress=args.funding_stress,
        funding_multiplier=float(args.funding_multiplier),
        missing_mark_policy=args.missing_mark_policy,
        missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
    )


def _run_engine(
    *,
    mark_candles: dict[str, pd.DataFrame],
    targets: Mapping[pd.Timestamp, pd.Series],
    funding: pd.DataFrame,
    funding_intervals: Mapping[str, float],
    args: argparse.Namespace,
):
    return run_derivative_backtest(
        mark_candles,
        dict(targets),
        funding_rates=funding if not funding.empty else None,
        funding_intervals_hours=dict(funding_intervals) if not funding.empty else None,
        config=_engine_config(args),
        start_time=pd.Timestamp(args.start_date, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", choices=(BASELINE_ID, CANDIDATE_ID), required=True)
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

    _, market, universe, index = _load_market(
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
    risk_on_long = scale_long_targets(
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
    insurance_mask = pd.Series(False, index=pd.DatetimeIndex([_as_utc(v) for v in index]))
    risk_off = insurance_mask.copy()
    h5_relative = pd.Series(dtype=float)
    btc_relative = pd.Series(dtype=float)
    if args.trial_id == CANDIDATE_ID:
        short_targets, sleeve_audit, bear_schedule, exit_schedule = build_regime_short_schedules(
            market=market,
            universe=universe,
            index=index,
            long_raw=long_raw,
            long_targets=risk_on_long,
            funding=funding,
            available=available,
            mark_candles=mark_candles,
            start_date=args.start_date,
        )
        shadow = _run_engine(
            mark_candles=mark_candles,
            targets=risk_on_long,
            funding=funding,
            funding_intervals=funding_intervals,
            args=args,
        )
        risk_off, h5_relative, btc_relative = weekly_relative_half_state(
            index=index,
            shadow_returns=shadow.daily_returns,
            btc_close=market.price["bitcoin"],
            lookback_days=int(FROZEN_CONFIG["relative_lookback_days"]),
            evaluation_days=int(FROZEN_CONFIG["evaluation_days"]),
            anchor=args.start_date,
        )
        bear = _btc_bear_regime(
            market.price["bitcoin"],
            index,
            ma_window=int(FROZEN_CONFIG["btc_ma_window"]),
        )
        insurance_mask = (risk_off & ~bear).astype(bool)
    base_combined, target_audit = combine_long_with_cash_budgeted_short(
        risk_on_long,
        short_targets,
        max_total_gross=float(FROZEN_CONFIG["max_total_gross"]),
    )
    combined = (
        scale_target_book_by_state(
            base_combined,
            index=index,
            insurance=insurance_mask,
            gross_scale=float(FROZEN_CONFIG["cash_buffer_gross_scale"]),
        )
        if args.trial_id == CANDIDATE_ID
        else base_combined
    )
    result = _run_engine(
        mark_candles=mark_candles,
        targets=combined,
        funding=funding,
        funding_intervals=funding_intervals,
        args=args,
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
        "cash_buffer_gross_scale": float(FROZEN_CONFIG["cash_buffer_gross_scale"]),
        "max_total_gross": float(FROZEN_CONFIG["max_total_gross"]),
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
        "insurance_days": int(insurance_mask.sum()) if not insurance_mask.empty else 0,
        "insurance_switch_count": int((insurance_mask != insurance_mask.shift()).sum() - 1) if not insurance_mask.empty else 0,
        "risk_off_days": int(risk_off.sum()) if not risk_off.empty else 0,
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
    pd.DataFrame(
        {
            "risk_off": risk_off,
            "insurance": insurance_mask,
            "h5_14d_return": h5_relative,
            "btc_14d_return": btc_relative,
        }
    ).to_csv(output_dir / "insurance_state.csv", index_label="date")
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
                "spec": SPEC_PATH,
                "construction": "H5 1.25x long-only" if args.trial_id == BASELINE_ID else CONSTRUCTION,
                "frozen_config": FROZEN_CONFIG,
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
                f"- Insurance days: {summary['insurance_days']}",
                f"- Max requested short gross: {summary['max_requested_short_gross']:.6f}x",
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
    print(f"Wrote LS15 research output to {output_dir}")


if __name__ == "__main__":
    main()
