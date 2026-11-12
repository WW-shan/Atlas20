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

import numpy as np
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
    build_cross_sectional_funding_short_schedule,
    build_cross_sectional_funding_carry_schedule,
    build_cross_sectional_volatility_pair_schedule,
    build_cross_sectional_weak_short_schedule,
    build_exit_short_schedule,
    preserve_relative_weights_on_same_selection,
    route_short_schedule_with_long_exclusions,
    route_signed_sleeve_with_long_exclusions,
    trim_extreme_run_single_leader,
    trim_extreme_run_single_leader_stateful,
    tilt_long_targets_away_from_crowded_funding,
    combine_long_with_cash_budgeted_short,
    combine_long_with_priority_short_sleeves,
    combine_long_with_signed_sleeve,
    combine_signed_book_with_residual_sleeve,
    combine_sleeve_targets,
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
LS17_CANDIDATE_ID = "PR2026-11-LS17-H5-FUNDING-BASKET"
LS18_CANDIDATE_ID = "PR2026-11-LS18-H5-FUNDING-TILT"
LS20_CANDIDATE_ID = "PR2026-11-LS20-H5-COMMON-GROSS"
LS21_CANDIDATE_ID = "PR2026-11-LS21-H5-POSITIVE-CARRY-SHORT"
LS21_BEAR_FUNDING_THRESHOLD = 0.0
LS22_CANDIDATE_ID = "PR2026-11-LS22-H5-EXTREME-RUN-PROFIT-LOCK"
LS23_CANDIDATE_ID = "PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT"
LS24_CANDIDATE_ID = "PR2026-11-LS24-H5-PROFIT-LOCK-CROSS-VENUE-SHORT"
LS24_BEAR_FUNDING_THRESHOLD = 0.0
LS25_CANDIDATE_ID = "PR2026-11-LS25-H5-STATEFUL-PROFIT-LOCK"
LS26_CANDIDATE_ID = "PR2026-11-LS26-H5-REARMING-PROFIT-LOCK"
LS27_CANDIDATE_ID = "PR2026-11-LS27-H5-PROFIT-LOCK-DYNAMIC-SHORT"
LS28_CANDIDATE_ID = "PR2026-11-LS28-H5-PROFIT-LOCK-PRIORITY-SHORT"
LS29_CANDIDATE_ID = "PR2026-11-LS29-H5-CONCENTRATION-PROFIT-LOCK-REGIME-SHORT"
LS30_CANDIDATE_ID = "PR2026-11-LS30-H5-FUNDING-CARRY-NEUTRAL"
LS31_CANDIDATE_ID = "PR2026-11-LS31-H5-FUNDING-CARRY-LONG60"
LS32_CANDIDATE_ID = "PR2026-11-LS32-H5-FUNDING-CARRY-HOLD4-LONG60"
LS33_CANDIDATE_ID = "PR2026-11-LS33-H5-LS23-RESIDUAL-CARRY-LONG60"
LS33_CONTROL_ID = "PR2026-11-LS33C-H5-LS23-LONG60-CONTROL"
LS34_CANDIDATE_ID = "PR2026-11-LS34-H5-LS23-RESIDUAL-CARRY-SHORTHOLD"
LS35_CANDIDATE_ID = "PR2026-11-LS35-H5-LS23-RESIDUAL-CARRY-SIGN"
LS36_CANDIDATE_ID = "PR2026-11-LS36-H5-LS23-RESIDUAL-SHORT-CARRY"
LS37_CANDIDATE_ID = "PR2026-11-LS37-H5-LS23-RESIDUAL-CARRY-14D"
LS38_CANDIDATE_ID = "PR2026-11-LS38-H5-LS23-NOTRADE5"
LS39_CANDIDATE_ID = "PR2026-11-LS39-H5-LS23-LOWVOL-PAIR"
SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-regime-short-router-design.md"
NO_TRADE_BAND_SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-no-trade-band-design.md"
LS17_SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-funding-basket-design.md"
LS18_SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-funding-tilt-design.md"
LS20_SPEC_PATH = "docs/superpowers/specs/2026-11-11-h5-common-gross-design.md"
LS21_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-positive-carry-short-design.md"
LS22_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-extreme-run-profit-lock-design.md"
LS23_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-profit-lock-regime-short-design.md"
LS24_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-cross-venue-funding-short-design.md"
LS25_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-stateful-profit-lock-design.md"
LS26_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-rearming-profit-lock-design.md"
LS27_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-profit-lock-dynamic-short-design.md"
LS28_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-profit-lock-priority-short-design.md"
LS29_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-concentration-profit-lock-regime-short-design.md"
LS30_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-funding-carry-neutral-sleeve-design.md"
LS31_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-funding-carry-long60-design.md"
LS32_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-funding-carry-holdband-design.md"
LS33_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-design.md"
LS34_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-shorthold-design.md"
LS35_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-sign-design.md"
LS36_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-residual-short-carry-design.md"
LS37_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-14d-design.md"
LS38_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-notrade5-design.md"
LS39_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-lowvol-pair-design.md"
LS31_LONG_BUFFER = 0.60
LS32_LONG_BUFFER = 0.60
LS27_MAX_REQUESTED_SHORT_GROSS = 0.50
LS27_TARGET_TOTAL_GROSS = 1.48
SHORT_CANDIDATES = {
    CANDIDATE_ID: 0.0,
    NO_TRADE_BAND_CANDIDATE_ID: NO_TRADE_BAND_FRACTION,
    LS17_CANDIDATE_ID: 0.0,
    LS18_CANDIDATE_ID: 0.0,
    LS20_CANDIDATE_ID: 0.0,
    LS21_CANDIDATE_ID: 0.0,
    LS23_CANDIDATE_ID: 0.0,
    LS24_CANDIDATE_ID: 0.0,
    LS27_CANDIDATE_ID: 0.0,
    LS28_CANDIDATE_ID: 0.0,
    LS29_CANDIDATE_ID: 0.0,
    LS33_CANDIDATE_ID: 0.0,
    LS33_CONTROL_ID: 0.0,
    LS34_CANDIDATE_ID: 0.0,
    LS35_CANDIDATE_ID: 0.0,
    LS36_CANDIDATE_ID: 0.0,
    LS37_CANDIDATE_ID: 0.0,
    LS38_CANDIDATE_ID: 0.05,
    LS39_CANDIDATE_ID: 0.0,
}
NON_BEAR_MODE_BY_TRIAL = {LS17_CANDIDATE_ID: "high_funding"}
LONG_TILT_TRIALS = {LS18_CANDIDATE_ID}
LONG_COMMON_GROSS_TRIALS = {LS20_CANDIDATE_ID}
LONG_PROFIT_LOCK_TRIALS = {
    LS22_CANDIDATE_ID,
    LS23_CANDIDATE_ID,
    LS24_CANDIDATE_ID,
    LS25_CANDIDATE_ID,
    LS26_CANDIDATE_ID,
    LS27_CANDIDATE_ID,
    LS28_CANDIDATE_ID,
    LS29_CANDIDATE_ID,
    LS33_CANDIDATE_ID,
    LS33_CONTROL_ID,
    LS34_CANDIDATE_ID,
    LS35_CANDIDATE_ID,
    LS36_CANDIDATE_ID,
    LS37_CANDIDATE_ID,
    LS38_CANDIDATE_ID,
    LS39_CANDIDATE_ID,
}
LONG_STATEFUL_PROFIT_LOCK_TRIALS = {LS25_CANDIDATE_ID}
LONG_REARMING_PROFIT_LOCK_TRIALS = {LS26_CANDIDATE_ID}
LONG_CONCENTRATION_PROFIT_LOCK_TRIALS = {LS29_CANDIDATE_ID}
MARKET_NEUTRAL_TRIALS = {
    LS30_CANDIDATE_ID,
    LS31_CANDIDATE_ID,
    LS32_CANDIDATE_ID,
}
LOW_VOL_PAIR_TRIALS = {LS39_CANDIDATE_ID}
RESIDUAL_CARRY_TRIALS = {
    LS33_CANDIDATE_ID,
    LS34_CANDIDATE_ID,
    LS35_CANDIDATE_ID,
    LS36_CANDIDATE_ID,
    LS37_CANDIDATE_ID,
}
LONG60_TRIALS = {
    LS31_CANDIDATE_ID,
    LS32_CANDIDATE_ID,
    LS33_CANDIDATE_ID,
    LS33_CONTROL_ID,
    LS34_CANDIDATE_ID,
    LS35_CANDIDATE_ID,
    LS36_CANDIDATE_ID,
    LS37_CANDIDATE_ID,
}
CROSS_VENUE_FUNDING_TRIALS = {LS24_CANDIDATE_ID}
LS22_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    "lookback_days": 21,
    "threshold": 1.0,
    "scale": 0.5,
}
LS29_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS22_PROFIT_LOCK_CONFIG,
    "min_leader_weight": 0.25,
}
HIGH_FUNDING_SHORT_CONFIG: dict[str, Any] = {
    "lookback_days": 7,
    "rebalance_days": 7,
    "short_count": 4,
    "per_asset_weight": 0.0625,
    "min_assets": 5,
}
FUNDING_CARRY_CONFIG: dict[str, Any] = {
    "lookback_days": 7,
    "rebalance_days": 7,
    "count": 2,
    "per_asset_weight": 0.0625,
    "min_assets": 8,
    "min_settlements": 3,
}
LS32_CARRY_CONFIG: dict[str, Any] = {
    **FUNDING_CARRY_CONFIG,
    "hold_count": 4,
}
LS34_CARRY_CONFIG: dict[str, Any] = {
    **FUNDING_CARRY_CONFIG,
    "hold_count": 4,
    "hold_long": False,
    "hold_short": True,
}
LS35_CARRY_CONFIG: dict[str, Any] = {
    **FUNDING_CARRY_CONFIG,
    "carry_sign_only": True,
}
LS36_CARRY_CONFIG: dict[str, Any] = {
    **FUNDING_CARRY_CONFIG,
    "carry_sign_only": True,
    "long_enabled": False,
    "short_enabled": True,
}
LS37_CARRY_CONFIG: dict[str, Any] = {
    **FUNDING_CARRY_CONFIG,
    "rebalance_days": 14,
}
LS39_VOL_PAIR_CONFIG: dict[str, Any] = {
    "lookback_days": 60,
    "min_observations": 45,
    "rebalance_days": 28,
    "count": 4,
    "per_asset_weight": 0.025,
    "min_assets": 8,
}
FUNDING_LONG_TILT_CONFIG: dict[str, Any] = {
    "lookback_days": 7,
    "rank_min": 2.0 / 3.0,
    "min_assets": 5,
    "crowded_weight_scale": 0.5,
    "max_asset_weight": 0.60,
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


def _trial_frozen_config(trial_id: str) -> dict[str, Any]:
    """Return the actual frozen research config recorded for one trial."""
    config: dict[str, Any] = {**FROZEN_CONFIG}
    if trial_id in LONG60_TRIALS:
        config["long_buffer"] = LS31_LONG_BUFFER
    config["rebalance_no_trade_band"] = float(SHORT_CANDIDATES.get(trial_id, 0.0))
    config["non_bear_sleeve"] = (
        "ls12_router_plus_residual_lowvol_pair"
        if trial_id in LOW_VOL_PAIR_TRIALS
        else "ls12_router_plus_residual_funding_carry"
        if trial_id in RESIDUAL_CARRY_TRIALS
        else "funding_carry_market_neutral"
        if trial_id in MARKET_NEUTRAL_TRIALS
        else NON_BEAR_MODE_BY_TRIAL.get(trial_id, "h5_exit")
        if trial_id in SHORT_CANDIDATES
        else "none"
    )
    if trial_id == LS17_CANDIDATE_ID:
        config.update(HIGH_FUNDING_SHORT_CONFIG)
    if trial_id == LS18_CANDIDATE_ID:
        config.update(FUNDING_LONG_TILT_CONFIG)
    if trial_id in LONG_PROFIT_LOCK_TRIALS:
        config.update(LS22_PROFIT_LOCK_CONFIG)
    if trial_id in CROSS_VENUE_FUNDING_TRIALS:
        config["cross_venue_funding"] = {
            "binance_lookback_settlements": 3,
            "bybit_lookback_settlements": 3,
            "missing_policy": "ineligible",
            "score": "elementwise_min",
            "threshold": 0.0,
        }
    if trial_id in LOW_VOL_PAIR_TRIALS:
        config["volatility_pair"] = LS39_VOL_PAIR_CONFIG
    if trial_id in MARKET_NEUTRAL_TRIALS | RESIDUAL_CARRY_TRIALS:
        config["funding_carry"] = (
            LS32_CARRY_CONFIG
            if trial_id == LS32_CANDIDATE_ID
            else LS34_CARRY_CONFIG
            if trial_id == LS34_CANDIDATE_ID
            else LS35_CARRY_CONFIG
            if trial_id == LS35_CANDIDATE_ID
            else LS36_CARRY_CONFIG
            if trial_id == LS36_CANDIDATE_ID
            else LS37_CARRY_CONFIG
            if trial_id == LS37_CANDIDATE_ID
            else FUNDING_CARRY_CONFIG
        )
    return config


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
LS17_CONSTRUCTION = (
    "H5 1.25x + exactly one short sleeve selected by BTC close versus its "
    "200D SMA: bear = weekly 14D weakest-four PIT Top20 non-H5 basket; "
    "non-bear = weekly top-four positive 7D funding PIT Top20 non-H5 basket; "
    "total short <=0.25x and hard total gross 1.50x"
)
LS18_CONSTRUCTION = (
    "Frozen LS12 H5 1.25x + dual-short router; before execution, halve any "
    "H5 long leg whose positive 7D funding is in the top third of the PIT "
    "cross-section, redistribute freed weight to other non-crowded H5 legs "
    "with a 60% per-asset cap, and leave unallocatable weight in cash"
)
LS20_CONSTRUCTION = (
    "Frozen LS12 H5 1.25x + dual-short router; when the H5 selected asset set "
    "is unchanged, preserve the prior relative weights and only scale them to "
    "the new target gross; selection changes still execute the exact new target"
)
LS21_CONSTRUCTION = (
    "Frozen LS12 H5 1.25x + dual-short router; the bear weak-four sleeve only "
    "admits candidates whose three-settlement mean funding is strictly positive; "
    "the non-bear funding-exit sleeve and all other rules are unchanged"
)
LS22_CONSTRUCTION = (
    "Frozen H5 1.25x long-only; at each H5 target event, if the largest long "
    "leg has a 21D trailing return of at least 100%, halve only that leg and "
    "leave the freed weight in cash; no redistribution and no short sleeve"
)
LS23_CONSTRUCTION = (
    "LS22 single-leader profit lock applied to the H5 long book, combined with "
    "the frozen LS12 BTC-200D dual-short router; only the long book is trimmed"
)
LS24_CONSTRUCTION = (
    "LS23 long book plus the frozen LS12 dual-short router, with every short "
    "candidate required to have positive minimum Binance/Bybit last-three-"
    "settlement mean funding; missing Bybit history is ineligible"
)
LS25_CONSTRUCTION = (
    "Frozen H5 1.25x long-only; after the largest long leg first reaches a 21D "
    "trailing return of at least 100%, keep that same leader at half of each "
    "new H5 target until the largest holding changes; no redistribution and "
    "no short sleeve"
)
LS26_CONSTRUCTION = (
    "Frozen H5 1.25x long-only; after the largest long leg first reaches a 21D "
    "trailing return of at least 100%, keep that same leader at half of each "
    "new H5 target while the 21D return remains at least 100%; release below "
    "100% and allow a later re-trigger; no redistribution and no short sleeve"
)
LS27_CONSTRUCTION = (
    "LS22 single-leader profit lock applied to the H5 long book, combined with "
    "an equal nominal blend of the frozen LS12 dual-short router and the frozen "
    "R6 weekly bottom-four short; requested short gross up to 0.50x, funded only "
    "by unused long gross, hard total gross 1.50x"
)
LS28_CONSTRUCTION = (
    "LS22 single-leader profit lock applied to the H5 long book; the frozen LS12 "
    "dual-short router is funded first up to 0.25x and the frozen R6 bottom-four "
    "short receives only residual unused gross, with target/hard total gross 1.50x"
)
LS29_CONSTRUCTION = (
    "Frozen H5 1.25x plus the frozen LS12 dual-short router; the LS22 single-leader "
    "profit lock is applied only when the leader already represents at least 25% "
    "of NAV, otherwise the extreme trailing return does not trigger a trim"
)
LS30_CONSTRUCTION = (
    "Frozen H5 1.25x plus a market-neutral 0.25x funding-carry sleeve: long the "
    "two lowest 7D funding PIT Top20 non-H5 names and short the two highest, "
    "weekly rebalance with 20% short stops and hard total gross 1.50x"
)
LS31_CONSTRUCTION = (
    "LS30 funding-carry sleeve with the only change being a 60% long buffer "
    "instead of 50%; all selection, stop, gross and execution rules unchanged"
)
LS32_CONSTRUCTION = (
    "LS31 funding-carry sleeve with a 2x-entry-count rank hold band: retain "
    "existing legs while they remain in the lowest/highest four eligible "
    "funding ranks, replace only when they leave that band; all other rules "
    "unchanged"
)
LS33_CONSTRUCTION = (
    "Frozen LS23 H5 profit-lock plus LS12 dual-short router with priority on "
    "gross; the frozen LS31 market-neutral funding-carry sleeve receives only "
    "remaining non-overlapping gross up to 1.50x total, with a 60% long buffer"
)
LS33_CONTROL_CONSTRUCTION = (
    "Frozen LS23 H5 profit-lock plus LS12 dual-short router with a 60% long "
    "buffer and no funding-carry sleeve; control for LS33 buffer attribution"
)
LS34_CONSTRUCTION = (
    "LS33 residual-budget market-neutral funding carry with short legs allowed "
    "to remain while inside the highest four eligible funding ranks; long "
    "legs always exit outside the lowest two"
)
LS35_CONSTRUCTION = (
    "LS33 residual-budget funding carry restricted to true carry: long only "
    "negative-funding names and short only positive-funding names, with exact "
    "lowest/highest-two ranking"
)
LS36_CONSTRUCTION = (
    "LS33 residual-budget carry reduced to its short leg only: highest positive "
    "7D funding two names at 6.25% NAV each, no long carry"
)
LS37_CONSTRUCTION = (
    "LS33 residual-budget market-neutral funding carry rebalanced every 14 "
    "days instead of 7; ranking and weights unchanged"
)
LS38_CONSTRUCTION = (
    "Frozen LS23 with a 5% NAV same-side no-trade band; opens, exits, side "
    "flips and gross-guard events remain exact"
)
LS39_CONSTRUCTION = (
    "Frozen LS23 with a monthly residual-gross low-volatility pair: long the "
    "four lowest 60D realized-volatility PIT Top20 non-H5 names and short the "
    "four highest at 2.5% NAV each; 28D rebalance, base priority, hard gross 1.50x"
)


def _normalize_funding_grid(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.index = pd.DatetimeIndex(
        [_as_utc(value).floor("min") for value in normalized.index]
    )
    normalized = normalized[~normalized.index.duplicated(keep="last")].sort_index()
    return normalized


def conservative_cross_venue_funding(
    binance: pd.DataFrame,
    bybit: pd.DataFrame,
) -> pd.DataFrame:
    """Elementwise minimum of two funding panels; missing either side stays NaN."""
    binance = _normalize_funding_grid(binance)
    bybit = _normalize_funding_grid(bybit)
    index = pd.DatetimeIndex(binance.index).union(pd.DatetimeIndex(bybit.index))
    columns = pd.Index(binance.columns).union(pd.Index(bybit.columns))
    left = binance.reindex(index=index, columns=columns)
    right = bybit.reindex(index=index, columns=columns)
    values = np.minimum(
        left.to_numpy(dtype=float),
        right.to_numpy(dtype=float),
    )
    return pd.DataFrame(values, index=index, columns=columns)


def load_bybit_funding(
    path: Path,
    *,
    coins: set[str],
    index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Load Bybit funding on the Binance settlement grid without filling gaps."""
    target_index = pd.DatetimeIndex([_as_utc(value) for value in index])
    columns: dict[str, pd.Series] = {}
    for coin in sorted(coins):
        csv_path = path / f"{coin}.csv"
        if not csv_path.exists():
            continue
        frame = pd.read_csv(csv_path)
        if frame.empty or not {"funding_time", "funding_rate"}.issubset(frame.columns):
            continue
        stamps = pd.to_datetime(frame["funding_time"], utc=True, errors="coerce")
        values = pd.to_numeric(frame["funding_rate"], errors="coerce")
        series = pd.Series(values.to_numpy(dtype=float), index=stamps).dropna()
        series = series[~series.index.duplicated(keep="last")].sort_index()
        if not series.empty:
            columns[coin] = series
    if not columns:
        return pd.DataFrame(index=target_index)
    return pd.DataFrame(columns).reindex(target_index)


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
    non_bear_mode: str = "h5_exit",
    bear_funding_threshold: float | None = None,
    funding_positive_only: bool = False,
) -> tuple[
    dict[pd.Timestamp, pd.Series],
    pd.DataFrame,
    dict[pd.Timestamp, pd.Series],
    dict[pd.Timestamp, pd.Series],
]:
    """Build the frozen regime-routed short sleeves from market and H5 inputs."""
    if non_bear_mode not in {"h5_exit", "high_funding"}:
        raise ValueError("non_bear_mode must be 'h5_exit' or 'high_funding'")
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
        funding_threshold=(
            float(FROZEN_CONFIG["bear_funding_threshold"])
            if bear_funding_threshold is None
            else float(bear_funding_threshold)
        ),
        funding_lookback=int(FROZEN_CONFIG["bear_funding_lookback_settlements"]),
        anchor=start_date,
    )
    if non_bear_mode == "high_funding":
        exit_schedule = build_cross_sectional_funding_short_schedule(
            universe,
            long_targets,
            calendar=index,
            funding_rates=funding if not funding.empty else None,
            eligible=available,
            short_available=lambda asset, date: _short_mark_available(
                mark_candles, asset, date
            ),
            lookback_days=int(HIGH_FUNDING_SHORT_CONFIG["lookback_days"]),
            rebalance_days=int(HIGH_FUNDING_SHORT_CONFIG["rebalance_days"]),
            short_count=int(HIGH_FUNDING_SHORT_CONFIG["short_count"]),
            per_asset_weight=float(HIGH_FUNDING_SHORT_CONFIG["per_asset_weight"]),
            min_assets=int(HIGH_FUNDING_SHORT_CONFIG["min_assets"]),
            anchor=start_date,
        )
    else:
        eligible_by_date = _eligible_members_by_date(universe, list(long_raw))
        ranking_funding = (
            funding.where(funding > 0.0)
            if funding_positive_only and not funding.empty
            else funding
        )

        def exit_entry_allowed(asset: str, date: pd.Timestamp) -> bool:
            if not _short_mark_available(mark_candles, asset, date):
                return False
            rank = funding_rank_percentile(
                ranking_funding if not ranking_funding.empty else None,
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


def build_routed_bottom4_schedule(
    *,
    market: Any,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    long_targets: Mapping[pd.Timestamp, pd.Series],
    funding: pd.DataFrame,
    available: set[str],
    mark_candles: dict[str, pd.DataFrame],
    start_date: str,
) -> dict[pd.Timestamp, pd.Series]:
    """Build and route the frozen R6 bottom-four short sleeve."""
    raw = build_cross_sectional_weak_short_schedule(
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
    return route_short_schedule_with_long_exclusions(
        raw,
        long_targets=long_targets,
        universe=universe,
        calendar=index,
    )


def build_priority_short_schedules(
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
    dict[pd.Timestamp, pd.Series],
]:
    """Return the priority LS12 sleeve and the residual R6 sleeve."""
    router, router_audit, bear_schedule, exit_schedule = build_regime_short_schedules(
        market=market,
        universe=universe,
        index=index,
        long_raw=long_raw,
        long_targets=long_targets,
        funding=funding,
        available=available,
        mark_candles=mark_candles,
        start_date=start_date,
        non_bear_mode="h5_exit",
    )
    bottom4 = build_routed_bottom4_schedule(
        market=market,
        universe=universe,
        index=index,
        long_targets=long_targets,
        funding=funding,
        available=available,
        mark_candles=mark_candles,
        start_date=start_date,
    )
    return router, router_audit, bear_schedule, exit_schedule, bottom4


def build_funding_carry_sleeve(
    *,
    trial_id: str,
    market: Any,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    long_targets: Mapping[pd.Timestamp, pd.Series],
    funding: pd.DataFrame,
    available: set[str],
    mark_candles: dict[str, pd.DataFrame],
    start_date: str,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Build the frozen market-neutral funding-carry sleeve."""
    carry_config = (
        LS32_CARRY_CONFIG
        if trial_id == LS32_CANDIDATE_ID
        else LS34_CARRY_CONFIG
        if trial_id == LS34_CANDIDATE_ID
        else LS35_CARRY_CONFIG
        if trial_id == LS35_CANDIDATE_ID
        else LS36_CARRY_CONFIG
        if trial_id == LS36_CANDIDATE_ID
        else LS37_CARRY_CONFIG
        if trial_id == LS37_CANDIDATE_ID
        else FUNDING_CARRY_CONFIG
    )
    raw = build_cross_sectional_funding_carry_schedule(
        universe,
        long_targets,
        calendar=index,
        funding_rates=funding if not funding.empty else None,
        eligible=available,
        market_available=lambda asset, date: _short_mark_available(
            mark_candles, asset, date
        ),
        anchor=start_date,
        **carry_config,
    )
    routed = route_signed_sleeve_with_long_exclusions(
        raw,
        long_targets=long_targets,
        universe=universe,
        calendar=index,
    )
    rows = []
    for date, target in sorted(routed.items()):
        long_gross = float(target.clip(lower=0.0).sum())
        short_gross = float((-target.clip(upper=0.0)).sum())
        rows.append(
            {
                "date": date,
                "regime": "neutral",
                "active_sleeve": "funding_carry",
                "long_gross": long_gross,
                "short_gross": short_gross,
                "net_gross": float(target.sum()),
            }
        )
    return routed, pd.DataFrame(rows)



def build_low_vol_pair_sleeve(
    *,
    market: Any,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    long_targets: Mapping[pd.Timestamp, pd.Series],
    available: set[str],
    mark_candles: dict[str, pd.DataFrame],
    start_date: str,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Build the frozen monthly low-volatility long / high-volatility short sleeve."""
    raw = build_cross_sectional_volatility_pair_schedule(
        market.price,
        universe,
        long_targets,
        calendar=index,
        eligible=available,
        trade_available=lambda asset, date: _short_mark_available(
            mark_candles, asset, date
        ),
        anchor=start_date,
        **LS39_VOL_PAIR_CONFIG,
    )
    rows = []
    for date, target in sorted(raw.items()):
        long_gross = float(target.clip(lower=0.0).sum())
        short_gross = float((-target.clip(upper=0.0)).sum())
        rows.append(
            {
                "date": date,
                "regime": "neutral",
                "active_sleeve": "low_vol_pair",
                "long_gross": long_gross,
                "short_gross": short_gross,
                "net_gross": float(target.sum()),
            }
        )
    return raw, pd.DataFrame(rows)

def build_dynamic_short_schedules(
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
    dict[pd.Timestamp, pd.Series],
]:
    """Blend the frozen LS12 router with the frozen R6 bottom-four short.

    Each component requests 0.25x gross.  The caller separately applies the
    long book's unused-gross budget, so a full 1.25x long book funds half of
    the 0.50x request while a profit-lock trim can fund more.
    """
    router, router_audit, bear_schedule, exit_schedule = build_regime_short_schedules(
        market=market,
        universe=universe,
        index=index,
        long_raw=long_raw,
        long_targets=long_targets,
        funding=funding,
        available=available,
        mark_candles=mark_candles,
        start_date=start_date,
        non_bear_mode="h5_exit",
    )
    bottom4 = build_routed_bottom4_schedule(
        market=market,
        universe=universe,
        index=index,
        long_targets=long_targets,
        funding=funding,
        available=available,
        mark_candles=mark_candles,
        start_date=start_date,
    )
    combined = combine_sleeve_targets(
        {
            "ls12_router": (router, 1.0),
            "bottom4": (bottom4, 1.0),
        },
        max_gross=LS27_MAX_REQUESTED_SHORT_GROSS,
    )
    audit = router_audit.copy()
    if not audit.empty:
        audit = audit.rename(columns={"short_gross": "router_short_gross"})
        audit["active_sleeve"] = "dynamic_short_ensemble"
        schedule_dates = sorted(bottom4)
        state = pd.Series(dtype=float)
        cursor = 0
        bottom_gross: list[float] = []
        for raw_date in audit["date"]:
            date = _as_utc(raw_date)
            while cursor < len(schedule_dates) and schedule_dates[cursor] <= date:
                state = bottom4[schedule_dates[cursor]].copy()
                cursor += 1
            bottom_gross.append(float(state.sum()))
        audit["bottom4_short_gross"] = bottom_gross
    return combined, audit, bear_schedule, exit_schedule, bottom4


def non_bear_mode_for_trial(trial_id: str) -> str:
    return NON_BEAR_MODE_BY_TRIAL.get(trial_id, "h5_exit")


def build_long_targets_for_trial(
    *,
    trial_id: str,
    long_targets: Mapping[pd.Timestamp, pd.Series],
    funding_rates: pd.DataFrame,
    universe: pd.DataFrame,
    available: set[str],
    prices: pd.DataFrame | None = None,
):
    if trial_id in LONG_COMMON_GROSS_TRIALS:
        return preserve_relative_weights_on_same_selection(long_targets)
    if trial_id in LONG_STATEFUL_PROFIT_LOCK_TRIALS:
        if prices is None:
            raise ValueError("LS25 requires the point-in-time H5 price panel")
        return trim_extreme_run_single_leader_stateful(
            long_targets,
            prices=prices,
            **LS22_PROFIT_LOCK_CONFIG,
        )
    if trial_id in LONG_REARMING_PROFIT_LOCK_TRIALS:
        if prices is None:
            raise ValueError("LS26 requires the point-in-time H5 price panel")
        return trim_extreme_run_single_leader_stateful(
            long_targets,
            prices=prices,
            release_at_threshold=True,
            **LS22_PROFIT_LOCK_CONFIG,
        )
    if trial_id in LONG_CONCENTRATION_PROFIT_LOCK_TRIALS:
        if prices is None:
            raise ValueError("LS29 requires the point-in-time H5 price panel")
        return trim_extreme_run_single_leader(
            long_targets,
            prices=prices,
            **LS29_PROFIT_LOCK_CONFIG,
        )
    if trial_id in LONG_PROFIT_LOCK_TRIALS:
        if prices is None:
            raise ValueError("LS22 requires the point-in-time H5 price panel")
        return trim_extreme_run_single_leader(
            long_targets,
            prices=prices,
            **LS22_PROFIT_LOCK_CONFIG,
        )
    if trial_id not in LONG_TILT_TRIALS:
        return long_targets, pd.DataFrame(
            columns=[
                "date",
                "holdings",
                "crowded_legs",
                "crowded_assets",
                "target_gross_before",
                "target_gross_after",
                "freed_weight",
                "redistributed_weight",
                "cash_weight",
            ]
        )
    return tilt_long_targets_away_from_crowded_funding(
        long_targets,
        funding_rates=funding_rates,
        universe=universe,
        eligible=available,
        **FUNDING_LONG_TILT_CONFIG,
    )


def build_short_targets_for_trial(
    *,
    trial_id: str,
    market: Any,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    long_raw: Mapping[pd.Timestamp, pd.Series],
    long_targets: Mapping[pd.Timestamp, pd.Series],
    funding: pd.DataFrame,
    available: set[str],
    mark_candles: dict[str, pd.DataFrame],
    start_date: str,
    short_funding: pd.DataFrame | None = None,
):
    if trial_id == LS28_CANDIDATE_ID:
        priority, audit, bear, exit_schedule, _ = build_priority_short_schedules(
            market=market,
            universe=universe,
            index=index,
            long_raw=long_raw,
            long_targets=long_targets,
            funding=funding,
            available=available,
            mark_candles=mark_candles,
            start_date=start_date,
        )
        return priority, audit, bear, exit_schedule
    if trial_id == LS27_CANDIDATE_ID:
        combined, audit, bear, exit_schedule, _ = build_dynamic_short_schedules(
            market=market,
            universe=universe,
            index=index,
            long_raw=long_raw,
            long_targets=long_targets,
            funding=funding,
            available=available,
            mark_candles=mark_candles,
            start_date=start_date,
        )
        return combined, audit, bear, exit_schedule
    return build_regime_short_schedules(
        market=market,
        universe=universe,
        index=index,
        long_raw=long_raw,
        long_targets=long_targets,
        funding=short_funding if short_funding is not None else funding,
        available=available,
        mark_candles=mark_candles,
        start_date=start_date,
        non_bear_mode=non_bear_mode_for_trial(trial_id),
        bear_funding_threshold=(
            LS24_BEAR_FUNDING_THRESHOLD
            if trial_id == LS24_CANDIDATE_ID
            else LS21_BEAR_FUNDING_THRESHOLD
            if trial_id == LS21_CANDIDATE_ID
            else None
        ),
        funding_positive_only=trial_id in CROSS_VENUE_FUNDING_TRIALS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--trial-id",
        choices=(
            BASELINE_ID,
            CANDIDATE_ID,
            NO_TRADE_BAND_CANDIDATE_ID,
            LS17_CANDIDATE_ID,
            LS18_CANDIDATE_ID,
            LS20_CANDIDATE_ID,
            LS21_CANDIDATE_ID,
            LS22_CANDIDATE_ID,
            LS23_CANDIDATE_ID,
            LS24_CANDIDATE_ID,
            LS25_CANDIDATE_ID,
            LS26_CANDIDATE_ID,
            LS27_CANDIDATE_ID,
            LS28_CANDIDATE_ID,
            LS29_CANDIDATE_ID,
            LS30_CANDIDATE_ID,
            LS31_CANDIDATE_ID,
            LS32_CANDIDATE_ID,
            LS33_CANDIDATE_ID,
            LS33_CONTROL_ID,
            LS34_CANDIDATE_ID,
            LS35_CANDIDATE_ID,
            LS36_CANDIDATE_ID,
            LS37_CANDIDATE_ID,
            LS38_CANDIDATE_ID,
            LS39_CANDIDATE_ID,
        ),
        required=True,
    )
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument(
        "--evaluation-start",
        default=None,
        help="optional cash-start date; history still begins at --start-date",
    )
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_20261009"))
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument(
        "--bybit-funding-dir",
        type=Path,
        default=Path("data/raw/alternative_funding/bybit"),
    )
    parser.add_argument("--funding-source", choices=("zero", "binance-proxy", "bitget-exact"), default="binance-proxy")
    parser.add_argument("--funding-stress", choices=("none", "long-adverse", "short-adverse"), default="none")
    parser.add_argument("--funding-multiplier", type=float, default=1.0)
    parser.add_argument("--funding-missing-policy", choices=("error", "skip", "carry_last", "stress_median"), default="skip")
    parser.add_argument("--missing-mark-policy", choices=("error", "carry", "exit_last"), default="carry")
    parser.add_argument("--missing-mark-max-carry-hours", type=int, default=3)
    args = parser.parse_args()
    if args.evaluation_start is None:
        args.evaluation_start = args.start_date
    if pd.Timestamp(args.evaluation_start) < pd.Timestamp(args.start_date):
        parser.error("--evaluation-start must be on or after --start-date")
    if pd.Timestamp(args.evaluation_start) >= pd.Timestamp(args.end_date):
        parser.error("--evaluation-start must be earlier than --end-date")
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
    short_funding = funding
    if args.trial_id in CROSS_VENUE_FUNDING_TRIALS:
        bybit_funding = load_bybit_funding(
            args.bybit_funding_dir,
            coins=set(market.price.columns),
            index=pd.DatetimeIndex(funding.index),
        )
        short_funding = conservative_cross_venue_funding(funding, bybit_funding)
    long_targets, long_tilt_audit = build_long_targets_for_trial(
        trial_id=args.trial_id,
        long_targets=long_targets,
        funding_rates=funding,
        universe=universe,
        available=available,
        prices=market.price,
    )
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in symbol_map.columns:
        for record in symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)

    short_targets: dict[pd.Timestamp, pd.Series] = {}
    priority_short_targets: dict[pd.Timestamp, pd.Series] = {}
    sleeve_audit = pd.DataFrame(columns=["date", "regime", "active_sleeve", "short_gross"])
    bear_schedule: dict[pd.Timestamp, pd.Series] = {}
    exit_schedule: dict[pd.Timestamp, pd.Series] = {}
    bottom4_schedule: dict[pd.Timestamp, pd.Series] = {}
    carry_schedule: dict[pd.Timestamp, pd.Series] = {}
    if args.trial_id in MARKET_NEUTRAL_TRIALS:
        carry_schedule, sleeve_audit = build_funding_carry_sleeve(
            trial_id=args.trial_id,
            market=market,
            universe=universe,
            index=index,
            long_targets=long_targets,
            funding=funding,
            available=available,
            mark_candles=mark_candles,
            start_date=args.start_date,
        )
    elif args.trial_id == LS27_CANDIDATE_ID:
        (
            short_targets,
            sleeve_audit,
            bear_schedule,
            exit_schedule,
            bottom4_schedule,
        ) = build_dynamic_short_schedules(
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
    elif args.trial_id == LS28_CANDIDATE_ID:
        (
            priority_short_targets,
            sleeve_audit,
            bear_schedule,
            exit_schedule,
            bottom4_schedule,
        ) = build_priority_short_schedules(
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
        short_targets = priority_short_targets
    elif args.trial_id in SHORT_CANDIDATES:
        short_targets, sleeve_audit, bear_schedule, exit_schedule = build_short_targets_for_trial(
            trial_id=args.trial_id,
            market=market,
            universe=universe,
            index=index,
            long_raw=long_raw,
            long_targets=long_targets,
            funding=funding,
            available=available,
            mark_candles=mark_candles,
            start_date=args.start_date,
            short_funding=short_funding,
        )

    carry_sleeve_audit = pd.DataFrame()
    low_vol_schedule: dict[pd.Timestamp, pd.Series] = {}
    low_vol_sleeve_audit = pd.DataFrame()
    if args.trial_id in LOW_VOL_PAIR_TRIALS:
        low_vol_schedule, low_vol_sleeve_audit = build_low_vol_pair_sleeve(
            market=market,
            universe=universe,
            index=index,
            long_targets=long_targets,
            available=available,
            mark_candles=mark_candles,
            start_date=args.start_date,
        )
    if args.trial_id in RESIDUAL_CARRY_TRIALS:
        carry_schedule, carry_sleeve_audit = build_funding_carry_sleeve(
            trial_id=args.trial_id,
            market=market,
            universe=universe,
            index=index,
            long_targets=long_targets,
            funding=funding,
            available=available,
            mark_candles=mark_candles,
            start_date=args.start_date,
        )

    target_total_gross = (
        LS27_TARGET_TOTAL_GROSS
        if args.trial_id == LS27_CANDIDATE_ID
        else float(FROZEN_CONFIG["max_total_gross"])
    )
    if args.trial_id in LOW_VOL_PAIR_TRIALS:
        base_combined, _ = combine_long_with_cash_budgeted_short(
            long_targets,
            short_targets,
            max_total_gross=target_total_gross,
        )
        combined, target_audit = combine_signed_book_with_residual_sleeve(
            base_combined,
            low_vol_schedule,
            max_total_gross=target_total_gross,
        )
    elif args.trial_id in RESIDUAL_CARRY_TRIALS:
        base_combined, _ = combine_long_with_cash_budgeted_short(
            long_targets,
            short_targets,
            max_total_gross=target_total_gross,
        )
        combined, target_audit = combine_signed_book_with_residual_sleeve(
            base_combined,
            carry_schedule,
            max_total_gross=target_total_gross,
        )
    elif args.trial_id in MARKET_NEUTRAL_TRIALS:
        combined, target_audit = combine_long_with_signed_sleeve(
            long_targets,
            carry_schedule,
            max_total_gross=target_total_gross,
        )
    elif args.trial_id == LS28_CANDIDATE_ID:
        combined, target_audit = combine_long_with_priority_short_sleeves(
            long_targets,
            priority_short_targets,
            bottom4_schedule,
            max_total_gross=target_total_gross,
        )
    else:
        combined, target_audit = combine_long_with_cash_budgeted_short(
            long_targets,
            short_targets,
            max_total_gross=target_total_gross,
        )
    cfg = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=(
            LS31_LONG_BUFFER
            if args.trial_id in LONG60_TRIALS
            else float(FROZEN_CONFIG["long_buffer"])
        ),
        short_buffer=float(FROZEN_CONFIG["short_buffer"]),
        short_stop_loss_pct=float(FROZEN_CONFIG["short_stop_loss_pct"]),
        max_gross_exposure=target_total_gross,
        hard_gross_exposure=(
            float(FROZEN_CONFIG["max_total_gross"])
            if args.trial_id
            in (
                MARKET_NEUTRAL_TRIALS
                | LOW_VOL_PAIR_TRIALS
                | RESIDUAL_CARRY_TRIALS
                | {LS27_CANDIDATE_ID, LS28_CANDIDATE_ID}
            )
            else None
        ),
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
        start_time=pd.Timestamp(args.evaluation_start, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )
    evaluation_start = pd.Timestamp(args.evaluation_start, tz="UTC")
    if "date" in long_tilt_audit.columns and not long_tilt_audit.empty:
        long_tilt_dates = pd.to_datetime(long_tilt_audit["date"], utc=True)
        long_tilt_audit = long_tilt_audit.loc[long_tilt_dates >= evaluation_start].copy()
    if "date" in sleeve_audit.columns and not sleeve_audit.empty:
        sleeve_dates = pd.to_datetime(sleeve_audit["date"], utc=True)
        sleeve_audit = sleeve_audit.loc[sleeve_dates >= evaluation_start].copy()
    if isinstance(target_audit.index, pd.DatetimeIndex):
        target_audit = target_audit.loc[target_audit.index >= evaluation_start].copy()
    metrics = _metrics_from_returns(result.daily_returns)
    trades = result.trades
    short_side = trades.get("side", pd.Series(dtype=object)) == "short"
    stop_reason = trades.get("reason", pd.Series(dtype=object)) == "stop_loss"
    short_opens = int((short_side & (trades.get("action") == "open")).sum()) if not trades.empty else 0
    summary = {
        "trial_id": args.trial_id,
        "baseline": args.trial_id == BASELINE_ID,
        "start_date": args.evaluation_start,
        "warmup_start_date": args.start_date,
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
        "long_buffer": (
            LS31_LONG_BUFFER
            if args.trial_id in LONG60_TRIALS
            else float(FROZEN_CONFIG["long_buffer"])
        ),
        "max_total_gross": float(FROZEN_CONFIG["max_total_gross"]),
        "target_total_gross": target_total_gross,
        "rebalance_no_trade_band": float(SHORT_CANDIDATES.get(args.trial_id, 0.0)),
        "non_bear_sleeve": (
            "ls12_router_plus_residual_lowvol_pair"
            if args.trial_id in LOW_VOL_PAIR_TRIALS
            else "ls12_router_plus_residual_funding_carry"
            if args.trial_id in RESIDUAL_CARRY_TRIALS
            else "dynamic_short_ensemble"
            if args.trial_id == LS27_CANDIDATE_ID
            else "priority_short_ls12_plus_residual_r6"
            if args.trial_id == LS28_CANDIDATE_ID
            else "funding_carry_market_neutral"
            if args.trial_id in MARKET_NEUTRAL_TRIALS
            else non_bear_mode_for_trial(args.trial_id)
            if args.trial_id in SHORT_CANDIDATES
            else "none"
        ),
        "funding_tilt_event_count": (
            int(len(long_tilt_audit))
            if "crowded_legs" in long_tilt_audit.columns
            else 0
        ),
        "funding_tilt_crowded_leg_count": (
            int(long_tilt_audit["crowded_legs"].sum())
            if "crowded_legs" in long_tilt_audit.columns
            else 0
        ),
        "funding_tilt_cash_weight_total": (
            float(long_tilt_audit["cash_weight"].sum())
            if "cash_weight" in long_tilt_audit.columns
            else 0.0
        ),
        "relative_tilt_skipped_count": (
            int(long_tilt_audit["relative_tilt_skipped"].sum())
            if "relative_tilt_skipped" in long_tilt_audit.columns
            else 0
        ),
        "relative_l1_skipped_total": (
            float(long_tilt_audit["relative_l1_skipped"].sum())
            if "relative_l1_skipped" in long_tilt_audit.columns
            else 0.0
        ),
        "profit_lock_event_count": int(len(long_tilt_audit)) if "trimmed" in long_tilt_audit.columns else 0,
        "profit_lock_trimmed_count": (
            int(long_tilt_audit["trimmed"].sum())
            if "trimmed" in long_tilt_audit.columns
            else 0
        ),
        "low_vol_pair_event_count": int(len(low_vol_sleeve_audit)),
        "low_vol_pair_long_gross_total": (
            float(low_vol_sleeve_audit["long_gross"].sum())
            if not low_vol_sleeve_audit.empty
            else 0.0
        ),
        "low_vol_pair_short_gross_total": (
            float(low_vol_sleeve_audit["short_gross"].sum())
            if not low_vol_sleeve_audit.empty
            else 0.0
        ),
        "profit_lock_cash_weight_total": (
            float(
                (
                    long_tilt_audit["gross_before"]
                    - long_tilt_audit["gross_after"]
                ).sum()
            )
            if {"gross_before", "gross_after"}.issubset(long_tilt_audit.columns)
            else 0.0
        ),
        "max_requested_short_gross": float(target_audit["requested_short_gross"].max()),
        "bear_funding_threshold": (
            float(LS24_BEAR_FUNDING_THRESHOLD)
            if args.trial_id == LS24_CANDIDATE_ID
            else float(LS21_BEAR_FUNDING_THRESHOLD)
            if args.trial_id == LS21_CANDIDATE_ID
            else float(FROZEN_CONFIG["bear_funding_threshold"])
        ),
        "cross_venue_funding": args.trial_id in CROSS_VENUE_FUNDING_TRIALS,
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
    target_audit.to_csv(output_dir / "target_gross.csv", index_label="date")
    long_tilt_audit.to_csv(output_dir / "funding_tilt_audit.csv", index=False)
    if args.trial_id == LS20_CANDIDATE_ID:
        long_tilt_audit.to_csv(output_dir / "selection_event_audit.csv", index=False)
    if args.trial_id in LONG_PROFIT_LOCK_TRIALS:
        long_tilt_audit.to_csv(output_dir / "profit_lock_audit.csv", index=False)
    sleeve_audit.to_csv(output_dir / "sleeve_audit.csv", index=False)
    _write_schedule(output_dir / "routed_short_schedule.csv", short_targets)
    _write_schedule(output_dir / "bear_weak4_schedule.csv", bear_schedule)
    _write_schedule(output_dir / "funding_exit_schedule.csv", exit_schedule)
    if bottom4_schedule:
        _write_schedule(output_dir / "bottom4_schedule.csv", bottom4_schedule)
    if carry_schedule:
        _write_schedule(output_dir / "carry_schedule.csv", carry_schedule)
    if low_vol_schedule:
        _write_schedule(output_dir / "low_vol_pair_schedule.csv", low_vol_schedule)
    if not low_vol_sleeve_audit.empty:
        low_vol_sleeve_audit.to_csv(output_dir / "low_vol_pair_audit.csv", index=False)
    if not carry_sleeve_audit.empty:
        carry_sleeve_audit.to_csv(output_dir / "carry_sleeve_audit.csv", index=False)
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
                    else LS17_SPEC_PATH
                    if args.trial_id == LS17_CANDIDATE_ID
                    else LS18_SPEC_PATH
                    if args.trial_id == LS18_CANDIDATE_ID
                    else LS20_SPEC_PATH
                    if args.trial_id == LS20_CANDIDATE_ID
                    else LS21_SPEC_PATH
                    if args.trial_id == LS21_CANDIDATE_ID
                    else LS22_SPEC_PATH
                    if args.trial_id == LS22_CANDIDATE_ID
                    else LS23_SPEC_PATH
                    if args.trial_id == LS23_CANDIDATE_ID
                    else LS24_SPEC_PATH
                    if args.trial_id == LS24_CANDIDATE_ID
                    else LS25_SPEC_PATH
                    if args.trial_id == LS25_CANDIDATE_ID
                    else LS26_SPEC_PATH
                    if args.trial_id == LS26_CANDIDATE_ID
                    else LS27_SPEC_PATH
                    if args.trial_id == LS27_CANDIDATE_ID
                    else LS28_SPEC_PATH
                    if args.trial_id == LS28_CANDIDATE_ID
                    else LS29_SPEC_PATH
                    if args.trial_id == LS29_CANDIDATE_ID
                    else LS30_SPEC_PATH
                    if args.trial_id == LS30_CANDIDATE_ID
                    else LS31_SPEC_PATH
                    if args.trial_id == LS31_CANDIDATE_ID
                    else LS32_SPEC_PATH
                    if args.trial_id == LS32_CANDIDATE_ID
                    else LS33_SPEC_PATH
                    if args.trial_id in {LS33_CANDIDATE_ID, LS33_CONTROL_ID}
                    else LS34_SPEC_PATH
                    if args.trial_id == LS34_CANDIDATE_ID
                    else LS35_SPEC_PATH
                    if args.trial_id == LS35_CANDIDATE_ID
                    else LS36_SPEC_PATH
                    if args.trial_id == LS36_CANDIDATE_ID
                    else LS37_SPEC_PATH
                    if args.trial_id == LS37_CANDIDATE_ID
                    else LS38_SPEC_PATH
                    if args.trial_id == LS38_CANDIDATE_ID
                    else LS39_SPEC_PATH
                    if args.trial_id == LS39_CANDIDATE_ID
                    else ""
                ),
                "construction": (
                    "H5 1.25x long-only"
                    if args.trial_id == BASELINE_ID
                    else NO_TRADE_BAND_CONSTRUCTION
                    if args.trial_id == NO_TRADE_BAND_CANDIDATE_ID
                    else LS17_CONSTRUCTION
                    if args.trial_id == LS17_CANDIDATE_ID
                    else LS18_CONSTRUCTION
                    if args.trial_id == LS18_CANDIDATE_ID
                    else LS20_CONSTRUCTION
                    if args.trial_id == LS20_CANDIDATE_ID
                    else LS21_CONSTRUCTION
                    if args.trial_id == LS21_CANDIDATE_ID
                    else LS22_CONSTRUCTION
                    if args.trial_id == LS22_CANDIDATE_ID
                    else LS23_CONSTRUCTION
                    if args.trial_id == LS23_CANDIDATE_ID
                    else LS24_CONSTRUCTION
                    if args.trial_id == LS24_CANDIDATE_ID
                    else LS25_CONSTRUCTION
                    if args.trial_id == LS25_CANDIDATE_ID
                    else LS26_CONSTRUCTION
                    if args.trial_id == LS26_CANDIDATE_ID
                    else LS27_CONSTRUCTION
                    if args.trial_id == LS27_CANDIDATE_ID
                    else LS28_CONSTRUCTION
                    if args.trial_id == LS28_CANDIDATE_ID
                    else LS29_CONSTRUCTION
                    if args.trial_id == LS29_CANDIDATE_ID
                    else LS30_CONSTRUCTION
                    if args.trial_id == LS30_CANDIDATE_ID
                    else LS31_CONSTRUCTION
                    if args.trial_id == LS31_CANDIDATE_ID
                    else LS32_CONSTRUCTION
                    if args.trial_id == LS32_CANDIDATE_ID
                    else LS33_CONSTRUCTION
                    if args.trial_id == LS33_CANDIDATE_ID
                    else LS33_CONTROL_CONSTRUCTION
                    if args.trial_id == LS33_CONTROL_ID
                    else LS34_CONSTRUCTION
                    if args.trial_id == LS34_CANDIDATE_ID
                    else LS35_CONSTRUCTION
                    if args.trial_id == LS35_CANDIDATE_ID
                    else LS36_CONSTRUCTION
                    if args.trial_id == LS36_CANDIDATE_ID
                    else LS37_CONSTRUCTION
                    if args.trial_id == LS37_CANDIDATE_ID
                    else LS38_CONSTRUCTION
                    if args.trial_id == LS38_CANDIDATE_ID
                    else LS39_CONSTRUCTION
                    if args.trial_id == LS39_CANDIDATE_ID
                    else CONSTRUCTION
                ),
                "frozen_config": _trial_frozen_config(args.trial_id),
                "start_date": args.evaluation_start,
                "warmup_start_date": args.start_date,
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
                f"- Window: {args.evaluation_start} to {args.end_date} (warmup {args.start_date})",
                f"- Cost: {float(args.cost_bps):g} bps",
                f"- Terminal multiple: {metrics['multiple']:.4f}x",
                f"- Sharpe: {metrics['sharpe']:.4f}",
                f"- Max drawdown: {metrics['max_drawdown']:.4%}",
                f"- Max requested short gross: {summary['max_requested_short_gross']:.6f}x",
                f"- Rebalance no-trade band: {summary['rebalance_no_trade_band']:.4%} NAV",
                f"- Non-bear short sleeve: {summary['non_bear_sleeve']}",
                f"- Bear funding threshold: {summary['bear_funding_threshold']:.8f}",
                f"- Funding long-tilt events: {summary['funding_tilt_event_count']}",
                f"- Relative tilts skipped: {summary['relative_tilt_skipped_count']}",
                f"- Profit-lock events: {summary['profit_lock_event_count']}",
                f"- Profit-lock trimmed events: {summary['profit_lock_trimmed_count']}",
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
