"""Research-only shadow tracker for the LS23 and LS42 long/short candidates.

This script rebuilds a frozen long/short target book from point-in-time data,
records the signed long/short targets, and runs the derivatives research
engine.  It never creates orders, never touches the live executor, and never
changes the live ``PR2026-10-D-L125-V2`` track.

The default funding source is zero, which is an explicit upper bound because
the OOS mark tree extends beyond the exact Bitget funding history.  When a
non-zero funding source is selected, short selection is stopped once that
source becomes stale; positions are flattened at the first subsequent signal
day rather than silently carrying the last settlement forever.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping

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
    scale_long_targets,
)
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_derivatives_oos import load_symbol_map, resolve_signal_window  # noqa: E402
from scripts.run_h5_regime_short_router import (  # noqa: E402
    BASELINE_ID,
    FROZEN_CONFIG,
    LS23_CANDIDATE_ID,
    LS42_CANDIDATE_ID,
    LS42_PROFIT_LOCK_CONFIG,
    LS42_SPEC_PATH,
    SHORT_CANDIDATES,
    build_long_targets_for_trial,
    build_short_targets_for_trial,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

SHADOW_SPEC = LS23_CANDIDATE_ID
OOS_START = "2026-09-22"
DEFAULT_WARMUP_START = "2021-01-01"
DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_oos_20261112")
DEFAULT_OUTPUT_DIR = Path(
    "reports/derivatives_track_h5_profit_lock_regime_short/shadow_oos_2026_11"
)
TRIAL_CHOICES = (BASELINE_ID, LS23_CANDIDATE_ID, LS42_CANDIDATE_ID)
_TARGET_COLUMNS = [
    "signal_date",
    "execution_hint",
    "asset",
    "side",
    "target_weight",
    "target_notional_per_1k",
    "change_weight",
    "change_notional_per_1k",
    "action",
]


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _execution_hint(signal: pd.Timestamp) -> pd.Timestamp:
    """Frozen T+1 03:00 UTC execution hint for a daily signal."""
    return _as_utc(signal).normalize() + pd.Timedelta(days=1, hours=3)


def _targets_executing_after(
    targets: Mapping[pd.Timestamp, pd.Series],
    start: pd.Timestamp,
) -> dict[pd.Timestamp, pd.Series]:
    """Keep signals whose T+1 fill falls inside the requested OOS window.

    The engine filters by normalized execution time.  Filtering by signal date
    instead would omit the carry-in signal from the previous day even though
    its 03:00 fill is the first trade in the window.
    """
    start = _as_utc(start)
    return {
        _as_utc(signal): target
        for signal, target in targets.items()
        if _execution_hint(signal) >= start
    }


def _shadow_targets(
    targets: Mapping[pd.Timestamp, pd.Series],
    *,
    capital: float = 1000.0,
) -> pd.DataFrame:
    """Return a signed target ledger without losing short-side information.

    ``target_weight`` and ``target_notional_per_1k`` stay signed.  ``side`` is
    derived from the sign, while ``action`` describes the change from the
    previous target snapshot.  Closing rows use side ``flat`` and a zero target.
    """

    if not np.isfinite(capital) or capital <= 0.0:
        raise ValueError("capital must be positive and finite")

    rows: list[dict[str, object]] = []
    previous = pd.Series(dtype=float)
    for raw_signal, raw_target in sorted(targets.items()):
        signal = _as_utc(raw_signal)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
            raise ValueError("shadow targets must be finite")
        target = target.astype(float).sort_index()

        index = previous.index.union(target.index)
        current = target.reindex(index).fillna(0.0)
        prior = previous.reindex(index).fillna(0.0)
        delta = current - prior
        for asset in index:
            weight = float(current.loc[asset])
            change = float(delta.loc[asset])
            if abs(weight) <= 1e-15 and abs(change) <= 1e-15:
                continue
            if weight > 1e-15:
                side = "long"
            elif weight < -1e-15:
                side = "short"
            else:
                side = "flat"
            if abs(change) <= 1e-12:
                action = "HOLD"
            elif abs(prior.loc[asset]) <= 1e-15 and abs(weight) > 1e-15:
                action = "OPEN"
            elif abs(weight) <= 1e-15 and abs(prior.loc[asset]) > 1e-15:
                action = "CLOSE"
            elif abs(weight) > abs(prior.loc[asset]):
                action = "INCREASE"
            else:
                action = "DECREASE"
            rows.append(
                {
                    "signal_date": signal,
                    "execution_hint": _execution_hint(signal),
                    "asset": str(asset),
                    "side": side,
                    "target_weight": weight,
                    "target_notional_per_1k": weight * float(capital),
                    "change_weight": change,
                    "change_notional_per_1k": change * float(capital),
                    "action": action,
                }
            )
        previous = target

    return pd.DataFrame(rows, columns=_TARGET_COLUMNS)



def _mark_coverage(
    marks: Mapping[str, pd.DataFrame],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, int | float]:
    """Measure hourly mark coverage over an explicit evaluation window."""
    start = _as_utc(start)
    end = _as_utc(end)
    if end <= start:
        raise ValueError("coverage end must be after coverage start")
    expected = pd.date_range(start, end, freq="h", inclusive="left")
    missing_hours = 0
    assets_with_gaps = 0
    max_gap_hours = 0.0
    for frame in marks.values():
        index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
        index = index[(index >= start) & (index < end)].drop_duplicates().sort_values()
        missing = expected.difference(index)
        if len(missing):
            assets_with_gaps += 1
            missing_hours += len(missing)
        if len(index) > 1:
            gaps = index.to_series().diff().dropna().dt.total_seconds() / 3600.0
            max_gap_hours = max(max_gap_hours, float(gaps.max()))
    return {
        "assets": len(marks),
        "expected_hours": int(len(expected)),
        "missing_hours": int(missing_hours),
        "assets_with_gaps": int(assets_with_gaps),
        "max_gap_hours": float(max_gap_hours),
    }


def _merge_mark_maps(
    warmup: Mapping[str, pd.DataFrame],
    execution: Mapping[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Merge warmup history with OOS marks; execution marks win on overlap."""
    merged: dict[str, pd.DataFrame] = {}
    for asset in sorted(set(warmup) | set(execution)):
        frames = [frame for frame in (warmup.get(asset), execution.get(asset)) if frame is not None]
        if not frames:
            continue
        frame = pd.concat(frames)
        frame.index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        merged[asset] = frame
    return merged

def _funding_last_timestamp(funding: pd.DataFrame) -> pd.Timestamp | None:
    """Latest settlement timestamp available in a funding panel, if any."""
    if funding.empty:
        return None
    index = pd.DatetimeIndex([_as_utc(value) for value in funding.index])
    if index.empty:
        return None
    return pd.Timestamp(index.max())


def _cap_short_schedule_at_funding_end(
    schedule: Mapping[pd.Timestamp, pd.Series],
    *,
    calendar: pd.DatetimeIndex,
    funding_last: pd.Timestamp | None,
) -> dict[pd.Timestamp, pd.Series]:
    """Prevent stale funding from selecting shorts after the data ends.

    A signal may use a settlement stamped at the signal day's 00:00.  Once the
    next calendar day is reached, the funding panel is no longer fresh enough
    for a point-in-time short decision; add a flattening target at that first
    day so an already-open short cannot be silently carried on stale data.
    """

    if funding_last is None:
        return {}
    cutoff = funding_last.normalize()
    dates = pd.DatetimeIndex([_as_utc(value) for value in calendar]).sort_values()
    kept: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in schedule.items():
        date = _as_utc(raw_date)
        if date <= cutoff:
            target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
            target.index = target.index.astype(str)
            if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
                raise ValueError("short targets must be finite")
            kept[date] = target.astype(float)
    flatten_dates = dates[dates > cutoff]
    if len(flatten_dates):
        flatten_date = pd.Timestamp(flatten_dates[0])
        if flatten_date not in kept:
            kept[flatten_date] = pd.Series(dtype=float)
    return dict(sorted(kept.items()))


def _daily_frame(
    result,
    *,
    start: pd.Timestamp,
    end_date: pd.Timestamp,
    last_mark: pd.Timestamp,
) -> pd.DataFrame:
    """Full-day OOS returns plus the daily end-of-path gross exposure."""
    returns = result.daily_returns.loc[result.daily_returns.index >= start].copy()
    returns = returns.loc[returns.index <= end_date]
    if last_mark.normalize() == end_date and last_mark.hour < 23:
        returns = returns.loc[returns.index < end_date]
    if returns.empty:
        raise SystemExit("no complete out-of-sample daily returns in the requested window")
    daily = returns.rename("daily_return").to_frame()
    daily["nav_multiple"] = (1.0 + daily["daily_return"]).cumprod()
    gross = result.gross_exposure.resample("1D").last()
    daily["gross_exposure"] = gross.reindex(daily.index)
    daily["equity"] = result.daily_equity.reindex(daily.index)
    return daily.reset_index(names="date")


def _latest_target_rows(targets: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return targets
    latest = targets["signal_date"].max()
    return targets.loc[targets["signal_date"] == latest].copy()


def _shadow_spec(trial_id: str) -> str:
    """Return the frozen specification or baseline label for a shadow run."""
    if trial_id == LS23_CANDIDATE_ID:
        return "docs/superpowers/specs/2026-11-12-h5-profit-lock-regime-short-design.md"
    if trial_id == LS42_CANDIDATE_ID:
        return LS42_SPEC_PATH
    if trial_id == BASELINE_ID:
        return "frozen H5 1.25x long-only baseline"
    raise ValueError(f"unsupported shadow trial: {trial_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", choices=TRIAL_CHOICES, default=SHADOW_SPEC)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument(
        "--warmup-raw-dir",
        type=Path,
        default=None,
        help="optional full-history mark tree used to rebuild stateful signals before the OOS window",
    )
    parser.add_argument("--start-date", default=OOS_START)
    parser.add_argument("--warmup-start", default=DEFAULT_WARMUP_START)
    parser.add_argument(
        "--end-date",
        default=None,
        help="latest completed signal date; default is the latest complete mark day",
    )
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument(
        "--funding-source",
        choices=("zero", "binance-proxy", "bitget-exact"),
        default="zero",
        help="zero is an explicit upper bound; non-zero sources are capped when stale",
    )
    parser.add_argument(
        "--funding-missing-policy",
        choices=("error", "skip", "carry_last", "stress_median"),
        default="skip",
    )
    parser.add_argument(
        "--missing-mark-policy",
        choices=("error", "carry", "exit_last"),
        default="carry",
    )
    parser.add_argument("--missing-mark-max-carry-hours", type=int, default=3)
    parser.add_argument("--max-staleness-hours", type=float, default=30.0)
    parser.add_argument("--allow-stale", action="store_true")
    parser.add_argument(
        "--allow-incomplete-marks",
        action="store_true",
        help="continue only for a deliberately labelled incomplete-data diagnostic",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    start = _as_utc(args.start_date)
    warmup_start = _as_utc(args.warmup_start)
    if start <= warmup_start:
        parser.error("--start-date must be after --warmup-start")
    if args.cost_bps < 0.0:
        parser.error("--cost-bps must be non-negative")
    if args.capital <= 0.0:
        parser.error("--capital must be positive")
    configure_logging("ERROR")

    symbol_map = load_symbol_map(args.raw_dir)
    execution_marks = load_mark_candles(args.raw_dir, symbol_map)
    if not execution_marks:
        raise SystemExit(f"no market candles found in {args.raw_dir}/candles")
    last_mark = max(frame.index.max() for frame in execution_marks.values())
    try:
        signal_end_day, staleness_hours = resolve_signal_window(
            last_mark,
            requested_end=args.end_date,
            max_staleness_hours=float(args.max_staleness_hours),
            allow_stale=bool(args.allow_stale),
        )
    except ValueError as exc:
        raise SystemExit(
            f"{exc}. Refresh the OOS marks (make derivatives-oos-data) or pass "
            "--allow-stale for a deliberate backfill."
        ) from exc
    end_date = pd.Timestamp(signal_end_day).normalize()
    if end_date <= start:
        raise SystemExit("no completed signal days in the requested OOS window")
    coverage_end = min(end_date + pd.Timedelta(days=1), last_mark + pd.Timedelta(hours=1))
    mark_coverage = _mark_coverage(execution_marks, start=start, end=coverage_end)
    if int(mark_coverage["missing_hours"]) > 0 and not args.allow_incomplete_marks:
        raise SystemExit(
            f"mark coverage is incomplete in {args.raw_dir}: "
            f"{mark_coverage['missing_hours']} missing hours across "
            f"{mark_coverage['assets_with_gaps']} assets (max gap "
            f"{mark_coverage['max_gap_hours']:.1f}h) in {start}..{coverage_end}; "
            "refresh the marks or pass --allow-incomplete-marks only for a "
            "deliberately labelled diagnostic"
        )

    warmup_marks: dict[str, pd.DataFrame] = {}
    if args.warmup_raw_dir is not None:
        if not args.warmup_raw_dir.is_dir():
            raise SystemExit(f"warmup mark directory does not exist: {args.warmup_raw_dir}")
        warmup_marks = load_mark_candles(args.warmup_raw_dir, symbol_map)
        if not warmup_marks:
            raise SystemExit(f"no warmup market candles found in {args.warmup_raw_dir}/candles")
    marks = _merge_mark_maps(warmup_marks, execution_marks)

    _, market, universe, index = _load_market(
        args.config,
        start_date=str(warmup_start.date()),
        end_date=str(end_date.date()),
    )
    if index.empty:
        raise SystemExit("the processed market panel has no rows in the requested window")
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_raw = _long_targets_from_build(built, index)
    available = set(marks)
    restricted, dropped = _restrict_targets(long_raw, available, marks)
    long_base = scale_long_targets(
        restricted,
        leverage=float(FROZEN_CONFIG["h5_leverage"]),
        max_gross=float(FROZEN_CONFIG["h5_leverage"]),
    )
    funding = _funding_for_source(
        args.funding_source,
        raw_dir=args.raw_dir,
        binance_dir=Path("data/raw/binance_funding"),
        symbol_map=symbol_map,
        coins=set(market.price.columns),
    )
    if not funding.empty:
        funding = funding.dropna(how="all").loc[:, funding.notna().any(axis=0)]
    funding_last = _funding_last_timestamp(funding)

    long_targets, profit_lock_audit = build_long_targets_for_trial(
        trial_id=args.trial_id,
        long_targets=long_base,
        funding_rates=funding,
        universe=universe,
        available=available,
        prices=market.price,
    )
    short_targets: dict[pd.Timestamp, pd.Series] = {}
    sleeve_audit = pd.DataFrame()
    bear_schedule: dict[pd.Timestamp, pd.Series] = {}
    exit_schedule: dict[pd.Timestamp, pd.Series] = {}
    if args.trial_id in SHORT_CANDIDATES:
        short_targets, sleeve_audit, bear_schedule, exit_schedule = build_short_targets_for_trial(
            trial_id=args.trial_id,
            market=market,
            universe=universe,
            index=index,
            long_raw=long_raw,
            long_targets=long_targets,
            funding=funding,
            available=available,
            mark_candles=marks,
            start_date=str(warmup_start.date()),
            short_funding=funding,
        )
        short_targets = _cap_short_schedule_at_funding_end(
            short_targets,
            calendar=index,
            funding_last=funding_last,
        )

    combined, target_audit = combine_long_with_cash_budgeted_short(
        long_targets,
        short_targets,
        max_total_gross=float(FROZEN_CONFIG["max_total_gross"]),
    )
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in symbol_map.columns:
        for record in symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)

    engine_end = pd.Timestamp(last_mark) + pd.Timedelta(hours=1)
    result = run_derivative_backtest(
        marks,
        combined,
        funding_rates=funding if not funding.empty else None,
        funding_intervals_hours=funding_intervals if not funding.empty else None,
        config=DerivativeBacktestConfig(
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
            missing_mark_policy=args.missing_mark_policy,
            missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
        ),
        start_time=start,
        end_time=engine_end,
    )
    daily = _daily_frame(result, start=start, end_date=end_date, last_mark=last_mark)
    oos_returns = pd.Series(
        daily["daily_return"].to_numpy(dtype=float),
        index=pd.DatetimeIndex(daily["date"]),
        name="daily_return",
    )
    # The engine's first daily row is the initialization point and is always
    # zero.  It is retained in oos_daily.csv but excluded from Sharpe/volatility,
    # matching the existing frozen OOS reports.
    metric_returns = oos_returns.iloc[1:] if len(oos_returns) > 1 else oos_returns
    metrics = _metrics_from_returns(metric_returns)

    shadow = _shadow_targets(
        _targets_executing_after(combined, start),
        capital=float(args.capital),
    )
    latest = _latest_target_rows(shadow)
    output_dir = ensure_dir(args.output_dir)
    daily.to_csv(output_dir / "oos_daily.csv", index=False)
    shadow.to_csv(output_dir / "oos_targets.csv", index=False)
    result.trades.to_csv(output_dir / "oos_trades.csv", index=False)
    result.funding.to_csv(output_dir / "oos_funding.csv", index=False)
    result.positions.to_csv(output_dir / "oos_positions.csv", index=False)
    result.gross_exposure.rename("gross_exposure").to_csv(
        output_dir / "oos_gross_exposure.csv", header=True
    )
    if not result.liquidations.empty:
        result.liquidations.to_csv(output_dir / "oos_liquidations.csv", index=False)
    profit_lock_oos = profit_lock_audit.copy()
    if "date" in profit_lock_oos.columns and not profit_lock_oos.empty:
        signal_dates = pd.to_datetime(profit_lock_oos["date"], utc=True)
        profit_lock_oos = profit_lock_oos.loc[
            signal_dates.map(lambda value: _execution_hint(value) >= start)
        ]
    if not profit_lock_oos.empty:
        profit_lock_oos.to_csv(output_dir / "oos_profit_lock_audit.csv", index=False)
    sleeve_oos = sleeve_audit.copy()
    if "date" in sleeve_oos.columns and not sleeve_oos.empty:
        sleeve_oos = sleeve_oos.loc[
            pd.to_datetime(sleeve_oos["date"], utc=True) >= start
        ]
    if not sleeve_oos.empty:
        sleeve_oos.to_csv(output_dir / "oos_sleeve_audit.csv", index=False)
    target_audit_oos = target_audit.copy()
    if isinstance(target_audit_oos.index, pd.DatetimeIndex):
        target_audit_oos = target_audit_oos.loc[
            [
                _execution_hint(value) >= start
                for value in target_audit_oos.index
            ]
        ]
        target_audit_table = target_audit_oos.reset_index(names="date")
    else:
        target_audit_table = target_audit_oos
    target_audit_table.to_csv(output_dir / "oos_target_gross.csv", index=False)
    dropped_oos = dropped.copy()
    if "date" in dropped_oos.columns and not dropped_oos.empty:
        dropped_dates = pd.to_datetime(dropped_oos["date"], utc=True)
        dropped_oos = dropped_oos.loc[
            dropped_dates.map(lambda value: _execution_hint(value) >= start)
        ]

    trades = result.trades
    short_side = trades.get("side", pd.Series(dtype=object)) == "short"
    if args.funding_source == "zero":
        funding_status = "zero (explicit upper bound; no funding charged)"
    elif funding_last is not None and funding_last >= coverage_end:
        funding_status = f"{args.funding_source} (complete for the OOS window)"
    else:
        funding_status = (
            f"{args.funding_source} (available through {funding_last}; "
            "stale shorts flattened)"
        )
    short_opens = int((short_side & (trades.get("action") == "open")).sum()) if not trades.empty else 0
    summary = {
        "tracked_spec": args.trial_id,
        "research_only": True,
        "live_execution": False,
        "start": str(start),
        "warmup_start": str(warmup_start),
        "end_date": str(end_date),
        "engine_end": str(engine_end),
        "last_mark": str(last_mark),
        "staleness_hours": float(staleness_hours),
        "days": int(len(daily)),
        "metric_days": int(len(metric_returns)),
        "cost_bps": float(args.cost_bps),
        "capital": float(args.capital),
        "funding_source": args.funding_source,
        "funding_last": None if funding_last is None else str(funding_last),
        "funding_missing_policy": args.funding_missing_policy,
        "funding": funding_status,
        "mark_source": "bitget_mark",
        "missing_mark_policy": args.missing_mark_policy,
        "missing_mark_max_carry_hours": int(args.missing_mark_max_carry_hours),
        "h5_leverage": float(FROZEN_CONFIG["h5_leverage"]),
        "max_total_gross": float(FROZEN_CONFIG["max_total_gross"]),
        "rebalance_no_trade_band": float(SHORT_CANDIDATES.get(args.trial_id, 0.0)),
        "max_target_total_gross": (
            float(target_audit_oos["total_gross"].max())
            if not target_audit_oos.empty
            else 0.0
        ),
        "max_funded_short_gross": (
            float(target_audit_oos["funded_short_gross"].max())
            if not target_audit_oos.empty
            else 0.0
        ),
        "max_observed_gross": (
            float(result.gross_exposure.max()) if not result.gross_exposure.empty else 0.0
        ),
        "gross_breach_hours": int(
            (result.gross_exposure > float(FROZEN_CONFIG["max_total_gross"]) + 1e-12).sum()
        ),
        "short_open_count": short_opens,
        "short_stop_loss_count": int(
            (short_side & (trades.get("reason") == "stop_loss")).sum()
        ) if not trades.empty else 0,
        "liquidation_count": int(len(result.liquidations)),
        "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
        "fees_total": float(trades["fee"].sum()) if not trades.empty else 0.0,
        "profit_lock_trimmed_count": (
            int(profit_lock_oos["trimmed"].sum())
            if "trimmed" in profit_lock_oos.columns
            else 0
        ),
        "profit_lock_redistributed_weight_total": (
            float(profit_lock_oos["redistributed_weight"].sum())
            if "redistributed_weight" in profit_lock_oos.columns
            else 0.0
        ),
        "profit_lock_cash_weight_total": (
            float(profit_lock_oos["cash_weight"].sum())
            if "cash_weight" in profit_lock_oos.columns
            else 0.0
        ),
        "dropped_target_rows": int(len(dropped_oos)),
        "available_mark_count": int(len(marks)),
        "execution_mark_count": int(len(execution_marks)),
        "raw_dir": str(args.raw_dir),
        "warmup_raw_dir": str(args.warmup_raw_dir) if args.warmup_raw_dir else None,
        "mark_coverage": mark_coverage,
        "allow_incomplete_marks": bool(args.allow_incomplete_marks),
        **metrics,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "tracked_spec": args.trial_id,
                "spec": _shadow_spec(args.trial_id),
                "research_only": True,
                "live_execution": False,
                "frozen_config": {
                    **FROZEN_CONFIG,
                    "rebalance_no_trade_band": float(
                        SHORT_CANDIDATES.get(args.trial_id, 0.0)
                    ),
                    **(
                        {"profit_lock_redistribution": LS42_PROFIT_LOCK_CONFIG}
                        if args.trial_id == LS42_CANDIDATE_ID
                        else {}
                    ),
                },
                "start": str(start),
                "warmup_start": str(warmup_start),
                "end_date": str(end_date),
                "cost_bps": float(args.cost_bps),
                "funding_source": args.funding_source,
                "funding_last": None if funding_last is None else str(funding_last),
                "mark_source": "bitget_mark",
                "raw_dir": str(args.raw_dir),
                "warmup_raw_dir": str(args.warmup_raw_dir) if args.warmup_raw_dir else None,
                "mark_coverage": mark_coverage,
                "allow_incomplete_marks": bool(args.allow_incomplete_marks),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    latest_table = latest[
        [
            "asset",
            "side",
            "target_weight",
            "target_notional_per_1k",
            "change_weight",
            "change_notional_per_1k",
            "action",
            "execution_hint",
        ]
    ].set_index("asset") if not latest.empty else latest
    metrics_table = pd.DataFrame([{"spec": args.trial_id, **metrics}]).set_index("spec")
    counters_table = pd.DataFrame(
        [
            {
                "spec": args.trial_id,
                "max_target_gross": summary["max_target_total_gross"],
                "max_observed_gross": summary["max_observed_gross"],
                "gross_breach_hours": summary["gross_breach_hours"],
                "short_opens": summary["short_open_count"],
                "short_stops": summary["short_stop_loss_count"],
                "liquidations": summary["liquidation_count"],
                "funding_total": summary["funding_total"],
                "fees_total": summary["fees_total"],
            }
        ]
    ).set_index("spec")
    report_lines = [
        f"# Derivatives Shadow OOS Tracker — {args.trial_id}",
        "",
        f"- window: {start} → {end_date} ({len(daily)} daily rows; {len(metric_returns)} metric returns)",
        "- research only: yes; live execution: **no**",
        (
            "- frozen long/short book: H5 1.25x + LS23 profit-lock/regime short"
            if args.trial_id == LS23_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS42 profit-lock redistribution/regime short"
            if args.trial_id == LS42_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x baseline"
        ),
        f"- cost: {float(args.cost_bps):g} bps; capital reference: {args.capital:,.0f} units",
        f"- funding: {summary['funding']}",
        f"- last mark: {last_mark}; staleness: {staleness_hours:.1f}h",
        f"- warmup history: {args.warmup_raw_dir or 'same as OOS marks'}",
        f"- mark coverage: {mark_coverage['missing_hours']} missing hours; "
        f"{mark_coverage['assets']} assets checked; max gap {mark_coverage['max_gap_hours']:.1f}h",
        "",
        "## OOS metrics",
        "",
        dataframe_to_markdown(metrics_table),
        "",
        "## Execution and risk counters",
        "",
        dataframe_to_markdown(counters_table),
        "",
        "## Latest target book",
        "",
        f"- signal date: {latest['signal_date'].max() if not latest.empty else 'none'}",
        "",
        dataframe_to_markdown(latest_table) if not latest_table.empty else "_No target rows._",
        "",
        "The first daily row is the engine initialization point and is excluded from Sharpe/volatility; it remains in `oos_daily.csv`.",
        "",
        "Research output only; not an order or a live approval.",
    ]
    (output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "spec": args.trial_id,
                "metrics": metrics,
                "days": int(len(daily)),
                "end_date": str(end_date),
                "funding_source": args.funding_source,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    print(f"Wrote research-only shadow tracker to {output_dir}")


if __name__ == "__main__":
    main()
