"""Research-only shadow tracker for the LS23, LS42, and LS43 long/short candidates.

This script rebuilds a frozen long/short target book from point-in-time data,
records the signed long/short targets, and runs the derivatives research
engine.  It never creates orders, never touches the live executor, and never
changes the live LS45-G125 track (the explicit wrapper selects that ID).

The default funding source is zero, which is an explicit upper bound because
the OOS mark tree extends beyond the exact Bitget funding history.  When a
non-zero funding source is selected, short selection is stopped once that
source becomes stale; positions are flattened at the first subsequent signal
day rather than silently carrying the last settlement forever.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
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
from atlas20.derivatives.execution import ContractSpec  # noqa: E402
from atlas20.derivatives.data_audit import audit_derivatives_data  # noqa: E402
from atlas20.derivatives.live_chain import file_sha256  # noqa: E402
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
    LS42_SPEC_PATH,
    LS43_CANDIDATE_ID,
    LS43_SPEC_PATH,
    LS45_CANDIDATE_ID,
    LS45_SPEC_PATH,
    LS46_CANDIDATE_ID,
    LS46_SPEC_PATH,
    LS47_CANDIDATE_ID,
    LS47_SPEC_PATH,
    LS48_CANDIDATE_ID,
    LS48_SPEC_PATH,
    LS49_CANDIDATE_ID,
    LS49_SPEC_PATH,
    LS50_CANDIDATE_ID,
    LS50_SPEC_PATH,
    LS51_CANDIDATE_ID,
    LS51_SPEC_PATH,
    LS52_CANDIDATE_ID,
    LS52_SPEC_PATH,
    LS53_CANDIDATE_ID,
    LS53_SPEC_PATH,
    LS54_CANDIDATE_ID,
    LS54_SPEC_PATH,
    LS55_CANDIDATE_ID,
    LS55_SPEC_PATH,
    LS56_CANDIDATE_ID,
    LS56_SPEC_PATH,
    LS57_CANDIDATE_ID,
    LS57_SPEC_PATH,
    PROFIT_LOCK_REDISTRIBUTE_CONFIG_BY_TRIAL,
    REVERSAL_SHORT_CONFIG_BY_TRIAL,
    SHORT_CANDIDATES,
    STOP_STATE_REVERSAL_SHORT_TRIALS,
    build_reversal_short_block_windows,
    build_long_targets_for_trial,
    build_short_targets_for_trial,
    suppress_long_targets_while_reversal_short,
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
TRIAL_CHOICES = (
    BASELINE_ID,
    LS23_CANDIDATE_ID,
    LS42_CANDIDATE_ID,
    LS43_CANDIDATE_ID,
    LS45_CANDIDATE_ID,
    LS46_CANDIDATE_ID,
    LS47_CANDIDATE_ID,
    LS48_CANDIDATE_ID,
    LS49_CANDIDATE_ID,
    LS50_CANDIDATE_ID,
    LS51_CANDIDATE_ID,
    LS52_CANDIDATE_ID,
    LS53_CANDIDATE_ID,
    LS54_CANDIDATE_ID,
    LS55_CANDIDATE_ID,
    LS56_CANDIDATE_ID,
    LS57_CANDIDATE_ID,
)
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


def _execution_hint(
    signal: pd.Timestamp,
    *,
    execution_hour: int = 1,
    execution_minute: int = 5,
) -> pd.Timestamp:
    """Return the configured T+1 execution hint for a daily signal."""

    return _as_utc(signal).normalize() + pd.Timedelta(
        days=1,
        hours=execution_hour,
        minutes=execution_minute,
    )


def _execution_price_model(snap: str) -> str:
    """Name the hourly-bar execution-price convention written to manifests."""

    return f"mark_1h_open_{snap}"


def _targets_executing_after(
    targets: Mapping[pd.Timestamp, pd.Series],
    start: pd.Timestamp,
    *,
    execution_hour: int = 1,
    execution_minute: int = 5,
) -> dict[pd.Timestamp, pd.Series]:
    """Keep signals whose T+1 fill falls inside the requested OOS window.

    The engine filters by normalized execution time.  Filtering by signal date
    instead would omit the carry-in signal from the previous day even though
    its configured T+1 fill is the first trade in the window.
    """
    start = _as_utc(start)
    return {
        _as_utc(signal): target
        for signal, target in targets.items()
        if _execution_hint(
            signal,
            execution_hour=execution_hour,
            execution_minute=execution_minute,
        )
        >= start
    }


def _shadow_targets(
    targets: Mapping[pd.Timestamp, pd.Series],
    *,
    capital: float = 1000.0,
    execution_hour: int = 1,
    execution_minute: int = 5,
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
                    "execution_hint": _execution_hint(
                        signal,
                        execution_hour=execution_hour,
                        execution_minute=execution_minute,
                    ),
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
) -> dict[str, object]:
    """Measure hourly mark coverage over each asset's available history.

    Assets enter the point-in-time universe at different times.  Counting the
    pre-listing period as a data gap makes every later-listed asset look
    corrupt and hides the gaps that actually matter after it starts trading.
    """
    start = _as_utc(start)
    end = _as_utc(end)
    if end <= start:
        raise ValueError("coverage end must be after coverage start")
    missing_hours = 0
    expected_hours = 0
    expected_asset_hours_sum = 0
    assets_with_gaps = 0
    assets_with_observations = 0
    max_gap_hours = 0.0
    gap_event_count = 0
    two_hour_gap_count = 0
    for frame in marks.values():
        index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
        index = index[(index >= start) & (index < end)].drop_duplicates().sort_values()
        if index.empty:
            continue
        assets_with_observations += 1
        expected = pd.date_range(index.min(), end, freq="h", inclusive="left")
        expected_hours = max(expected_hours, len(expected))
        expected_asset_hours_sum += len(expected)
        missing = expected.difference(index)
        if len(missing):
            assets_with_gaps += 1
            missing_hours += len(missing)
        if len(index) > 1:
            gaps = index.to_series().diff().dropna().dt.total_seconds() / 3600.0
            max_gap_hours = max(max_gap_hours, float(gaps.max()))
            material_gaps = gaps[gaps > 1.0]
            gap_event_count += int(len(material_gaps))
            two_hour_gap_count += int((material_gaps <= 2.0).sum())
    return {
        "window_start": str(start),
        "window_end": str(end),
        "assets": len(marks),
        "assets_with_observations": int(assets_with_observations),
        "expected_hours": int(expected_hours),
        "expected_asset_hours_sum": int(expected_asset_hours_sum),
        "missing_hours": int(missing_hours),
        "assets_with_gaps": int(assets_with_gaps),
        "max_gap_hours": float(max_gap_hours),
        "gap_event_count": int(gap_event_count),
        "two_hour_gap_count": int(two_hour_gap_count),
    }


def _mark_tree_provenance(
    raw_dir: Path,
    symbol_map: pd.DataFrame,
) -> dict[str, object]:
    """Hash every mapped mark file and report symbols without a local file.

    The live data audit fingerprints the *current* raw tree.  Historical
    stateful research also consumes a separate warmup tree, so that tree needs
    its own content identity instead of inheriting the current tree's pass.
    """

    raw_dir = Path(raw_dir)
    paths: set[Path] = set()
    missing_symbols: set[str] = set()
    required = {"coin_id", "bitget_symbol"}
    missing_columns = required.difference(symbol_map.columns)
    if missing_columns:
        raise ValueError(f"symbol map missing columns {sorted(missing_columns)}")
    for record in symbol_map.to_dict("records"):
        raw_symbol = record.get("bitget_symbol")
        if pd.isna(raw_symbol):
            continue
        symbol = str(raw_symbol).strip()
        if not symbol or symbol.lower() in {"nan", "none"}:
            continue
        path = raw_dir / "candles" / f"{symbol}_mark.csv"
        if path.is_file():
            paths.add(path)
        else:
            missing_symbols.add(symbol)

    files: dict[str, str] = {}
    for path in sorted(paths, key=str):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        files[str(path.relative_to(raw_dir))] = digest.hexdigest()
    payload = "\n".join(f"{name}\0{digest}" for name, digest in files.items()).encode()
    fingerprint = "sha256:" + hashlib.sha256(payload).hexdigest() if files else None
    return {
        "raw_dir": str(raw_dir),
        "files": files,
        "mark_file_count": len(files),
        "missing_symbols": sorted(missing_symbols),
        "fingerprint": fingerprint,
    }


def _execution_mark_audit(
    targets: Mapping[pd.Timestamp, pd.Series],
    mark_candles: Mapping[str, pd.DataFrame],
    *,
    execution_hour: int = 1,
    execution_minute: int = 5,
    execution_price_snap: str = "floor",
    start: pd.Timestamp | None = None,
) -> dict[str, object]:
    """Check that every target change has a usable execution bar.

    ``_restrict_targets`` removes an asset when its own mark frame has no bar
    near the fill time.  This audit applies the same resolver after the signed
    long/short book is assembled and also includes assets that are being
    closed, making a silent target drop visible in the research manifest.
    """

    window_start = None if start is None else _as_utc(start)
    exact_bar_count = 0
    floor_resolved_count = 0
    required_pair_count = 0
    missing: list[dict[str, str]] = []
    previous_assets: set[str] = set()
    for signal_time in sorted(targets):
        signal = _as_utc(signal_time)
        execution_time = _execution_hint(
            signal,
            execution_hour=execution_hour,
            execution_minute=execution_minute,
        )
        if window_start is not None and execution_time < window_start:
            continue
        raw = pd.to_numeric(pd.Series(targets[signal_time]), errors="coerce")
        raw.index = raw.index.astype(str)
        if raw.isna().any() or not np.isfinite(raw.to_numpy(dtype=float)).all():
            raise ValueError("target weights must be finite numbers")
        current_assets = {
            str(asset) for asset, weight in raw.items() if abs(float(weight)) > 1e-15
        }
        required_assets = current_assets | previous_assets
        previous_assets = current_assets
        for asset in sorted(required_assets):
            required_pair_count += 1
            frame = mark_candles.get(asset)
            index = (
                pd.DatetimeIndex([])
                if frame is None
                else pd.DatetimeIndex([_as_utc(value) for value in frame.index]).sort_values()
            )
            if execution_time in index:
                exact_bar_count += 1
                continue
            if execution_price_snap == "floor":
                earlier = index[index <= execution_time]
                resolved = bool(
                    len(earlier)
                    and execution_time - earlier[-1] <= pd.Timedelta(hours=1)
                )
            elif execution_price_snap == "ceil":
                later = index[index >= execution_time]
                resolved = bool(
                    len(later)
                    and later[0] - execution_time <= pd.Timedelta(hours=1)
                )
            elif execution_price_snap == "exact":
                resolved = False
            else:
                raise ValueError("execution_price_snap must be 'exact', 'floor', or 'ceil'")
            if resolved:
                floor_resolved_count += 1
                continue
            missing.append(
                {
                    "signal_date": str(signal),
                    "execution_hint": str(execution_time),
                    "asset": asset,
                    "reason": f"no mark within one hour for {execution_price_snap} snap",
                }
            )

    return {
        "execution_utc": f"{int(execution_hour):02d}:{int(execution_minute):02d}",
        "execution_price_snap": execution_price_snap,
        "required_pair_count": required_pair_count,
        "resolved_pair_count": exact_bar_count + floor_resolved_count,
        "exact_bar_count": exact_bar_count,
        "floor_resolved_count": floor_resolved_count,
        "missing_pair_count": len(missing),
        "missing": missing,
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
        kept: dict[pd.Timestamp, pd.Series] = {}
        for raw_date, raw_target in schedule.items():
            date = _as_utc(raw_date)
            target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
            target.index = target.index.astype(str)
            if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
                raise ValueError("short targets must be finite")
            kept[date] = target.astype(float)
        return dict(sorted(kept.items()))
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


def _engine_end_for_signal_end(
    signal_end: pd.Timestamp,
    *,
    execution_hour: int = 1,
    execution_minute: int = 5,
) -> pd.Timestamp:
    """Include the last signal's next-day execution in the engine path.

    The engine treats ``end_time`` as exclusive and floors ``01:05`` to the
    ``01:00`` mark bar.  Ending at ``signal_end + 1 day`` excludes that bar and
    silently omits the final OPEN from trades, positions, quantisation and stop
    statistics even though the live executor executes it.
    """

    return _execution_hint(
        signal_end,
        execution_hour=execution_hour,
        execution_minute=execution_minute,
    ) + pd.Timedelta(seconds=1)


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
    if trial_id == LS43_CANDIDATE_ID:
        return LS43_SPEC_PATH
    if trial_id == LS45_CANDIDATE_ID:
        return LS45_SPEC_PATH
    if trial_id == LS46_CANDIDATE_ID:
        return LS46_SPEC_PATH
    if trial_id == LS47_CANDIDATE_ID:
        return LS47_SPEC_PATH
    if trial_id == LS48_CANDIDATE_ID:
        return LS48_SPEC_PATH
    if trial_id == LS49_CANDIDATE_ID:
        return LS49_SPEC_PATH
    if trial_id == LS50_CANDIDATE_ID:
        return LS50_SPEC_PATH
    if trial_id == LS51_CANDIDATE_ID:
        return LS51_SPEC_PATH
    if trial_id == LS52_CANDIDATE_ID:
        return LS52_SPEC_PATH
    if trial_id == LS53_CANDIDATE_ID:
        return LS53_SPEC_PATH
    if trial_id == LS54_CANDIDATE_ID:
        return LS54_SPEC_PATH
    if trial_id == LS55_CANDIDATE_ID:
        return LS55_SPEC_PATH
    if trial_id == LS56_CANDIDATE_ID:
        return LS56_SPEC_PATH
    if trial_id == LS57_CANDIDATE_ID:
        return LS57_SPEC_PATH
    if trial_id == BASELINE_ID:
        return "frozen H5 1.25x long-only baseline"
    raise ValueError(f"unsupported shadow trial: {trial_id}")


def _resolve_max_total_gross(value: float | None) -> float:
    if value is None:
        return float(FROZEN_CONFIG["max_total_gross"])
    resolved = float(value)
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError("max_total_gross must be positive and finite")
    return resolved


def _contract_specs_from_symbol_map(symbol_map: pd.DataFrame) -> dict[str, ContractSpec]:
    """Build current-snapshot venue specs from the frozen symbol map."""

    specs: dict[str, ContractSpec] = {}
    for record in symbol_map.to_dict("records"):
        asset = str(record.get("coin_id") or "").strip()
        symbol = str(record.get("bitget_symbol") or "").strip()
        if not asset or not symbol:
            continue
        status = str(record.get("contract_status") or "").strip().lower()
        if status and status != "normal":
            continue
        try:
            step = float(record.get("size_multiplier"))
            min_usdt = float(record.get("min_trade_usdt"))
        except (TypeError, ValueError):
            continue
        if not np.isfinite(step) or step <= 0.0:
            continue
        if not np.isfinite(min_usdt) or min_usdt <= 0.0:
            continue
        specs[asset] = ContractSpec(
            symbol=symbol,
            quantity_multiplier=step,
            min_order_usdt=min_usdt,
        )
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--panel", type=Path, default=Path("data/processed/panel_daily.csv"))
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
        "--engine-capital",
        type=float,
        default=None,
        help="starting equity for live-parity venue minimums; defaults to --capital",
    )
    parser.add_argument("--execution-hour", type=int, default=1)
    parser.add_argument("--execution-minute", type=int, default=5)
    parser.add_argument(
        "--execution-price-snap",
        choices=("exact", "floor", "ceil"),
        default="floor",
        help="snap the configured execution minute to an available hourly mark bar",
    )
    parser.add_argument(
        "--contract-specs-from-symbol-map",
        action="store_true",
        help="apply the frozen symbol-map quantity step and minimum notional",
    )
    parser.add_argument("--min-rebalance-usdt", type=float, default=0.0)
    parser.add_argument(
        "--normalize-isolated-margin",
        choices=("none", "rebalance", "daily"),
        default="none",
    )
    parser.add_argument(
        "--max-total-gross",
        type=float,
        default=None,
        help="override the frozen total gross cap; live candidate uses 1.25",
    )
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
    parser.add_argument(
        "--allow-data-audit-failures",
        action="store_true",
        help="allow a research-only run whose data audit has hard failures; never live-ready",
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
    engine_capital = float(args.capital if args.engine_capital is None else args.engine_capital)
    if engine_capital <= 0.0:
        parser.error("--engine-capital must be positive")
    if not 0 <= args.execution_hour <= 23:
        parser.error("--execution-hour must be in [0, 23]")
    if not 0 <= args.execution_minute <= 59:
        parser.error("--execution-minute must be in [0, 59]")
    if args.min_rebalance_usdt < 0.0:
        parser.error("--min-rebalance-usdt must be non-negative")
    try:
        max_total_gross = _resolve_max_total_gross(args.max_total_gross)
    except ValueError as exc:
        parser.error(str(exc))
    configure_logging("ERROR")

    symbol_map = load_symbol_map(args.raw_dir)
    contract_specs = (
        _contract_specs_from_symbol_map(symbol_map)
        if args.contract_specs_from_symbol_map
        else None
    )
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
            f"{exc}. Refresh the OOS marks (make derivatives-live-data) or pass "
            "--allow-stale for a deliberate backfill."
        ) from exc
    end_date = pd.Timestamp(signal_end_day).normalize()
    if end_date <= start:
        raise SystemExit("no completed signal days in the requested OOS window")
    engine_end = _engine_end_for_signal_end(
        end_date,
        execution_hour=int(args.execution_hour),
        execution_minute=int(args.execution_minute),
    )
    coverage_end = min(engine_end, last_mark + pd.Timedelta(hours=1))

    warmup_marks: dict[str, pd.DataFrame] = {}
    warmup_mark_provenance: dict[str, object] = {
        "raw_dir": None,
        "files": {},
        "mark_file_count": 0,
        "missing_symbols": [],
        "fingerprint": None,
    }
    warmup_mark_coverage: dict[str, object] = {
        "assets": 0,
        "expected_hours": 0,
        "missing_hours": 0,
        "assets_with_gaps": 0,
        "max_gap_hours": 0.0,
    }
    if args.warmup_raw_dir is not None:
        if not args.warmup_raw_dir.is_dir():
            raise SystemExit(f"warmup mark directory does not exist: {args.warmup_raw_dir}")
        warmup_marks = load_mark_candles(args.warmup_raw_dir, symbol_map)
        if not warmup_marks:
            raise SystemExit(f"no warmup market candles found in {args.warmup_raw_dir}/candles")
        warmup_mark_provenance = _mark_tree_provenance(args.warmup_raw_dir, symbol_map)
        warmup_mark_coverage = _mark_coverage(
            warmup_marks,
            start=warmup_start,
            end=min(start, coverage_end),
        )
    marks = _merge_mark_maps(warmup_marks, execution_marks)
    mark_coverage = _mark_coverage(marks, start=start, end=coverage_end)
    if int(mark_coverage["missing_hours"]) > 0 and not args.allow_incomplete_marks:
        raise SystemExit(
            f"mark coverage is incomplete in {args.raw_dir}"
            + (f" + {args.warmup_raw_dir}" if args.warmup_raw_dir is not None else "")
            + f": {mark_coverage['missing_hours']} missing hours across "
            f"{mark_coverage['assets_with_gaps']} assets (max gap "
            f"{mark_coverage['max_gap_hours']:.1f}h) in {start}..{coverage_end}; "
            "refresh the marks or pass --allow-incomplete-marks only for a "
            "deliberately labelled diagnostic"
        )

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
    restricted, dropped = _restrict_targets(
        long_raw,
        available,
        marks,
        execution_hour=int(args.execution_hour),
        execution_minute=int(args.execution_minute),
        execution_price_snap=str(args.execution_price_snap),
    )
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
            profit_lock_audit=profit_lock_audit,
        )
        short_targets = _cap_short_schedule_at_funding_end(
            short_targets,
            calendar=index,
            funding_last=funding_last,
        )
        if args.trial_id in {
            LS47_CANDIDATE_ID,
            LS48_CANDIDATE_ID,
            LS49_CANDIDATE_ID,
            LS50_CANDIDATE_ID,
        }:
            base_short_targets, _, _, _ = build_short_targets_for_trial(
                trial_id=LS23_CANDIDATE_ID,
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
            base_short_targets = _cap_short_schedule_at_funding_end(
                base_short_targets,
                calendar=index,
                funding_last=funding_last,
            )
            long_targets = suppress_long_targets_while_reversal_short(
                long_targets,
                short_targets,
                base_short_targets,
            )

    combined, target_audit = combine_long_with_cash_budgeted_short(
        long_targets,
        short_targets,
        max_total_gross=max_total_gross,
    )
    execution_mark_audit = _execution_mark_audit(
        combined,
        marks,
        execution_hour=int(args.execution_hour),
        execution_minute=int(args.execution_minute),
        execution_price_snap=str(args.execution_price_snap),
        start=start,
    )
    if int(execution_mark_audit["missing_pair_count"]) > 0 and not args.allow_incomplete_marks:
        missing_examples = execution_mark_audit["missing"][:10]
        raise SystemExit(
            "target execution mark audit failed: "
            f"{len(execution_mark_audit['missing'])} target pair(s) lack a usable "
            f"mark near {int(args.execution_hour):02d}:{int(args.execution_minute):02d} UTC; "
            f"examples={missing_examples}. Refresh the marks or pass "
            "--allow-incomplete-marks only for a deliberately labelled diagnostic"
        )
    latest_target = combined[max(combined)] if combined else pd.Series(dtype=float)
    required_short_assets = {
        str(asset) for asset, weight in latest_target.items() if float(weight) < 0.0
    }
    data_audit = audit_derivatives_data(
        args.raw_dir,
        args.panel,
        args.raw_dir / "symbol_map.csv",
        now=datetime.now(timezone.utc),
        required_short_assets=required_short_assets,
        require_all_funding_fresh=(args.funding_source == "bitget-exact"),
    )
    if not data_audit.passed and not args.allow_data_audit_failures:
        raise SystemExit(
            "data audit failed before the research run: "
            + "; ".join(data_audit.hard_failures[:10])
            + "; use --allow-data-audit-failures only for an explicitly labelled "
            "historical diagnostic"
        )
    data_fingerprint = data_audit.provenance.get("fingerprint")
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in symbol_map.columns:
        for record in symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)

    # Evaluate through the last signal's next-day execution, but not through
    # newer warmup marks.  The daily performance frame is still cut at
    # ``end_date``; this extension only lets the final OPEN happen and makes
    # trades, positions, quantisation and stop statistics match the live book.
    result = run_derivative_backtest(
        marks,
        combined,
        funding_rates=funding if not funding.empty else None,
        funding_intervals_hours=funding_intervals if not funding.empty else None,
        config=DerivativeBacktestConfig(
            initial_capital=engine_capital,
            taker_fee_bps=float(args.cost_bps),
            slippage_bps=0.0,
            liquidation_slippage_bps=5.0,
            long_buffer=float(FROZEN_CONFIG["long_buffer"]),
            short_buffer=float(FROZEN_CONFIG["short_buffer"]),
            short_stop_loss_pct=float(FROZEN_CONFIG["short_stop_loss_pct"]),
            short_stop_reentry_block_windows=(
                build_reversal_short_block_windows(
                    profit_lock_audit,
                    hold_days=int(
                        REVERSAL_SHORT_CONFIG_BY_TRIAL[args.trial_id]["hold_days"]
                    ),
                )
                if args.trial_id in STOP_STATE_REVERSAL_SHORT_TRIALS
                else ()
            ),
            short_stop_reentry_rearm_ma_days=(
                int(REVERSAL_SHORT_CONFIG_BY_TRIAL[args.trial_id]["rearm_ma_days"])
                if args.trial_id in STOP_STATE_REVERSAL_SHORT_TRIALS
                and REVERSAL_SHORT_CONFIG_BY_TRIAL[args.trial_id].get("rearm_ma_days")
                is not None
                else None
            ),
            short_stop_reentry_rearm_below_stop=bool(
                REVERSAL_SHORT_CONFIG_BY_TRIAL[args.trial_id].get(
                    "rearm_below_stop", False
                )
                if args.trial_id in STOP_STATE_REVERSAL_SHORT_TRIALS
                else False
            ),
            max_gross_exposure=max_total_gross,
            rebalance_no_trade_band=float(SHORT_CANDIDATES.get(args.trial_id, 0.0)),
            execution_hour=int(args.execution_hour),
            execution_minute=int(args.execution_minute),
            execution_price_snap=str(args.execution_price_snap),
            contract_specs=contract_specs,
            min_rebalance_usdt=float(args.min_rebalance_usdt),
            normalize_isolated_margin=str(args.normalize_isolated_margin),
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
        _targets_executing_after(
            combined,
            start,
            execution_hour=int(args.execution_hour),
            execution_minute=int(args.execution_minute),
        ),
        capital=float(args.capital),
        execution_hour=int(args.execution_hour),
        execution_minute=int(args.execution_minute),
    )
    latest = _latest_target_rows(shadow)
    output_dir = ensure_dir(args.output_dir)
    daily.to_csv(output_dir / "oos_daily.csv", index=False)
    shadow.to_csv(output_dir / "oos_targets.csv", index=False)
    result.trades.to_csv(output_dir / "oos_trades.csv", index=False)
    result.funding.to_csv(output_dir / "oos_funding.csv", index=False)
    result.positions.to_csv(output_dir / "oos_positions.csv", index=False)
    result.margin_events.to_csv(output_dir / "oos_margin_events.csv", index=False)
    result.order_quantizations.to_csv(
        output_dir / "oos_order_quantizations.csv",
        index=False,
    )
    result.order_skips.to_csv(output_dir / "oos_order_skips.csv", index=False)
    result.mark_carries.to_csv(output_dir / "oos_mark_carries.csv", index=False)
    result.fill_downgrades.to_csv(output_dir / "oos_fill_downgrades.csv", index=False)
    pd.DataFrame(
        execution_mark_audit["missing"],
        columns=["signal_date", "execution_hint", "asset", "reason"],
    ).to_csv(output_dir / "oos_execution_mark_gaps.csv", index=False)
    result.gross_exposure.rename("gross_exposure").to_csv(
        output_dir / "oos_gross_exposure.csv", header=True
    )
    if not result.liquidations.empty:
        result.liquidations.to_csv(output_dir / "oos_liquidations.csv", index=False)
    profit_lock_oos = profit_lock_audit.copy()
    if "date" in profit_lock_oos.columns and not profit_lock_oos.empty:
        signal_dates = pd.to_datetime(profit_lock_oos["date"], utc=True)
        profit_lock_oos = profit_lock_oos.loc[
            signal_dates.map(
                lambda value: _execution_hint(
                    value,
                    execution_hour=int(args.execution_hour),
                    execution_minute=int(args.execution_minute),
                )
                >= start
            )
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
                _execution_hint(
                    value,
                    execution_hour=int(args.execution_hour),
                    execution_minute=int(args.execution_minute),
                )
                >= start
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
            dropped_dates.map(
                lambda value: _execution_hint(
                    value,
                    execution_hour=int(args.execution_hour),
                    execution_minute=int(args.execution_minute),
                )
                >= start
            )
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
    targets_sha256 = file_sha256(output_dir / "oos_targets.csv")
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
        "engine_capital": engine_capital,
        "execution_utc": f"{int(args.execution_hour):02d}:{int(args.execution_minute):02d}",
        "execution_price_model": _execution_price_model(str(args.execution_price_snap)),
        "execution_price_resolution": "configured_snap_within_60_minutes",
        "execution_source": "signal_ledger_daily_close_next_day",
        "live_parity": bool(args.contract_specs_from_symbol_map),
        "contract_spec_source": (
            "symbol_map_current_snapshot_approximation"
            if args.contract_specs_from_symbol_map
            else "ideal_unquantized"
        ),
        "min_rebalance_usdt": float(args.min_rebalance_usdt),
        "normalize_isolated_margin": str(args.normalize_isolated_margin),
        "order_skip_count": int(len(result.order_skips)),
        "order_quantization_count": int(len(result.order_quantizations)),
        "margin_event_count": int(len(result.margin_events)),
        "mark_carry_count": int(len(result.mark_carries)),
        "mark_carry_hours_total": (
            float(result.mark_carries["hours"].sum())
            if not result.mark_carries.empty
            else 0.0
        ),
        "fill_downgrade_count": int(len(result.fill_downgrades)),
        "execution_mark_audit": execution_mark_audit,
        "warmup_data_fingerprint": warmup_mark_provenance["fingerprint"],
        "warmup_mark_file_count": warmup_mark_provenance["mark_file_count"],
        "warmup_missing_symbols": warmup_mark_provenance["missing_symbols"],
        "warmup_mark_coverage": warmup_mark_coverage,
        "targets_file": "oos_targets.csv",
        "targets_sha256": targets_sha256,
        "data_fingerprint": data_fingerprint,
        "data_audit_passed": bool(data_audit.passed),
        "data_audit_hard_failures": len(data_audit.hard_failures),
        "data_audit_warnings": len(data_audit.warnings),
        "allow_data_audit_failures": bool(args.allow_data_audit_failures),
        "funding_source": args.funding_source,
        "funding_last": None if funding_last is None else str(funding_last),
        "funding_missing_policy": args.funding_missing_policy,
        "funding": funding_status,
        "mark_source": "bitget_mark",
        "missing_mark_policy": args.missing_mark_policy,
        "missing_mark_max_carry_hours": int(args.missing_mark_max_carry_hours),
        "h5_leverage": float(FROZEN_CONFIG["h5_leverage"]),
        "max_total_gross": float(max_total_gross),
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
            (result.gross_exposure > max_total_gross + 1e-12).sum()
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
        "profit_lock_confirmed_recipient_event_count": (
            int(
                (
                    profit_lock_oos["trimmed"].fillna(False)
                    & (profit_lock_oos["eligible_recipient_count"] > 0)
                ).sum()
            )
            if {
                "trimmed",
                "eligible_recipient_count",
            }.issubset(profit_lock_oos.columns)
            else 0
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
                "last_mark": str(last_mark),
                "staleness_hours": float(staleness_hours),
                "index_end_date": str(end_date.date()),
                "signal_end_date": str(end_date.date()),
                "engine_end": str(engine_end),
                "max_total_gross": float(max_total_gross),
                "frozen_config": {
                    **FROZEN_CONFIG,
                    "rebalance_no_trade_band": float(
                        SHORT_CANDIDATES.get(args.trial_id, 0.0)
                    ),
                    "max_total_gross": float(max_total_gross),
                    **(
                        {
                            "profit_lock_redistribution": PROFIT_LOCK_REDISTRIBUTE_CONFIG_BY_TRIAL[
                                args.trial_id
                            ]
                        }
                        if args.trial_id in PROFIT_LOCK_REDISTRIBUTE_CONFIG_BY_TRIAL
                        else {}
                    ),
                    **(
                        {
                            "profit_lock_reversal_short": REVERSAL_SHORT_CONFIG_BY_TRIAL[
                                args.trial_id
                            ]
                        }
                        if args.trial_id in REVERSAL_SHORT_CONFIG_BY_TRIAL
                        else {}
                    ),
                },
                "start": str(start),
                "warmup_start": str(warmup_start),
                "end_date": str(end_date),
                "cost_bps": float(args.cost_bps),
                "engine_capital": engine_capital,
                "execution_utc": f"{int(args.execution_hour):02d}:{int(args.execution_minute):02d}",
                "execution_price_model": _execution_price_model(
                    str(args.execution_price_snap)
                ),
                "execution_price_resolution": "configured_snap_within_60_minutes",
                "execution_source": "signal_ledger_daily_close_next_day",
                "live_parity": bool(args.contract_specs_from_symbol_map),
                "contract_spec_source": (
                    "symbol_map_current_snapshot_approximation"
                    if args.contract_specs_from_symbol_map
                    else "ideal_unquantized"
                ),
                "min_rebalance_usdt": float(args.min_rebalance_usdt),
                "normalize_isolated_margin": str(args.normalize_isolated_margin),
                "mark_carry_count": int(len(result.mark_carries)),
                "fill_downgrade_count": int(len(result.fill_downgrades)),
                "execution_mark_audit": execution_mark_audit,
                "targets_file": "oos_targets.csv",
                "targets_sha256": targets_sha256,
                "warmup_data_fingerprint": warmup_mark_provenance["fingerprint"],
                "warmup_mark_files": warmup_mark_provenance["files"],
                "warmup_mark_file_count": warmup_mark_provenance["mark_file_count"],
                "warmup_missing_symbols": warmup_mark_provenance["missing_symbols"],
                "warmup_mark_coverage": warmup_mark_coverage,
                "data_fingerprint": data_fingerprint,
                "data_audit_required": True,
                "data_audit_passed": bool(data_audit.passed),
                "data_audit_hard_failures": data_audit.hard_failures[:20],
                "data_audit_warnings": data_audit.warnings[:20],
                "allow_data_audit_failures": bool(args.allow_data_audit_failures),
                "funding_source": args.funding_source,
                "funding_last": None if funding_last is None else str(funding_last),
                "mark_missing_policy": args.missing_mark_policy,
                "mark_missing_max_carry_hours": int(args.missing_mark_max_carry_hours),
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
                "short_stop_exits": summary["short_stop_loss_count"],
                "liquidations": summary["liquidation_count"],
                "funding_total": summary["funding_total"],
                "fees_total": summary["fees_total"],
            }
        ]
    ).set_index("spec")
    warmup_coverage_text = (
        "no observations in requested warmup window"
        if int(warmup_mark_coverage["expected_asset_hours_sum"]) == 0
        else (
            f"{int(warmup_mark_coverage['missing_hours'])} missing hours; "
            f"{int(warmup_mark_coverage['gap_event_count'])} gaps "
            f"({int(warmup_mark_coverage['two_hour_gap_count'])} two-hour); "
            f"max gap {float(warmup_mark_coverage['max_gap_hours']):.1f}h"
        )
    )
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
            else "- frozen long/short book: H5 1.25x + LS43 stronger-7D profit-lock redistribution/regime short"
            if args.trial_id == LS43_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS45 stronger-21D profit-lock redistribution/regime short"
            if args.trial_id == LS45_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS46 profit-lock reversal short/regime router"
            if args.trial_id == LS46_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS47 no-reentry reversal short/regime router"
            if args.trial_id == LS47_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS48 one-shot reversal short/regime router"
            if args.trial_id == LS48_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS49 MA21-rearmed reversal short/regime router"
            if args.trial_id == LS49_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS50 below-stop-rearmed reversal short/regime router"
            if args.trial_id == LS50_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS51 profit-lock skip on 7D-negative leader"
            if args.trial_id == LS51_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS52 bull-only 7D-negative profit-lock skip"
            if args.trial_id == LS52_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS53 MA21-confirmed 7D-negative profit-lock skip"
            if args.trial_id == LS53_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS54 MA21-confirmed skip with stronger-21D redistribution"
            if args.trial_id == LS54_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS55 75% MA21-confirmed skip with stronger-21D redistribution"
            if args.trial_id == LS55_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS56 62.5% MA21-confirmed skip with stronger-21D redistribution"
            if args.trial_id == LS56_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x + LS57 MA21 skip gated by non-negative 1D confirmation"
            if args.trial_id == LS57_CANDIDATE_ID
            else "- frozen long/short book: H5 1.25x baseline"
        ),
        f"- cost: {float(args.cost_bps):g} bps; capital reference: {args.capital:,.0f} units",
        f"- execution: {int(args.execution_hour):02d}:{int(args.execution_minute):02d} UTC; "
        f"price model {_execution_price_model(str(args.execution_price_snap))}",
        f"- engine end: {engine_end} (includes the final T+1 execution; "
        f"daily metrics end {end_date.date()})",
        f"- target ledger: oos_targets.csv; sha256 {summary['targets_sha256']}",
        f"- funding: {summary['funding']}",
        f"- last mark: {last_mark}; staleness: {staleness_hours:.1f}h",
        f"- warmup history: {args.warmup_raw_dir or 'same as OOS marks'}",
        f"- warmup provenance: {summary['warmup_data_fingerprint'] or 'not supplied'}; "
        f"{summary['warmup_mark_file_count']} mark files; "
        f"{warmup_coverage_text}",
        f"- mark coverage: {mark_coverage['missing_hours']} missing hours; "
        f"{mark_coverage['assets']} assets checked; "
        f"{mark_coverage['gap_event_count']} gaps "
        f"({mark_coverage['two_hour_gap_count']} two-hour); "
        f"max gap {mark_coverage['max_gap_hours']:.1f}h",
        f"- execution-bar audit: {execution_mark_audit['resolved_pair_count']}/"
        f"{execution_mark_audit['required_pair_count']} target pairs resolved; "
        f"{execution_mark_audit['missing_pair_count']} missing",
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
