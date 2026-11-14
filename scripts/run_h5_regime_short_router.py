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
    trim_extreme_run_single_leader_breakdown_exit,
    trim_extreme_run_single_leader_redistribute,
    trim_extreme_run_single_leader_skip_and_redistribute,
    trim_extreme_run_single_leader_stateful,
    tilt_long_targets_away_from_crowded_funding,
    combine_long_with_cash_budgeted_short,
    combine_long_with_priority_short_sleeves,
    combine_long_with_signed_sleeve,
    combine_signed_book_with_residual_sleeve,
    combine_sleeve_targets,
    funding_rank_percentile,
    inverse_volatility_reweight_long_targets,
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
LS40_CANDIDATE_ID = "PR2026-11-LS40-H5-LS23-INVVOL60"
LS41_CANDIDATE_ID = "PR2026-11-LS41-H5-LS23-LONGSTOP20"
LS42_CANDIDATE_ID = "PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE"
LS43_CANDIDATE_ID = "PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7"
LS44_CANDIDATE_ID = "PR2026-11-LS44-H5-LS23-PROFITLOCK-FULLEXIT-NEG7"
LS45_CANDIDATE_ID = "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
LS46_CANDIDATE_ID = "PR2026-11-LS46-H5-LS23-PROFITLOCK-REVERSAL-SHORT28"
LS47_CANDIDATE_ID = "PR2026-11-LS47-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-NOREENTRY"
LS48_CANDIDATE_ID = "PR2026-11-LS48-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-ONESHOT"
LS49_CANDIDATE_ID = "PR2026-11-LS49-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-MA21"
LS50_CANDIDATE_ID = "PR2026-11-LS50-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-BELOWSTOP"
LS51_CANDIDATE_ID = "PR2026-11-LS51-H5-LS23-PROFITLOCK-SKIP7DNEG"
LS52_CANDIDATE_ID = "PR2026-11-LS52-H5-LS23-PROFITLOCK-SKIP7DNEG-BULL"
LS53_CANDIDATE_ID = "PR2026-11-LS53-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21"
LS54_CANDIDATE_ID = "PR2026-11-LS54-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-REDISTRIBUTE"
LS55_CANDIDATE_ID = "PR2026-11-LS55-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-S075-REDISTRIBUTE"
LS56_CANDIDATE_ID = "PR2026-11-LS56-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-S0625-REDISTRIBUTE"
LS57_CANDIDATE_ID = "PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE"
LS58_CANDIDATE_ID = "PR2026-11-LS58-H5-LS23-DVOL75-RISKOFF"
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
LS40_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-inverse-vol60-design.md"
LS41_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-long-stop20-design.md"
LS42_SPEC_PATH = "docs/superpowers/specs/2026-11-12-h5-ls23-profit-lock-redistribute-design.md"
LS43_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-stronger7-design.md"
LS44_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-fullexit-neg7-design.md"
LS45_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-stronger21-design.md"
LS46_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-reversal-short28-design.md"
LS47_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-reversal-short28-noreentry-design.md"
LS48_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-reversal-short28-oneshot-design.md"
LS49_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-reversal-short28-ma21-design.md"
LS50_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-reversal-short28-belowstop-design.md"
LS51_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-design.md"
LS52_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-bull-design.md"
LS53_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-ma21-design.md"
LS54_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-ma21-redistribute-design.md"
LS55_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-ma21-s075-redistribute-design.md"
LS56_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-ma21-s0625-redistribute-design.md"
LS57_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-skip7dneg-ma21-stable1d-redistribute-design.md"
LS58_SPEC_PATH = "docs/superpowers/specs/2026-11-13-h5-ls23-dvol75-riskooff-design.md"
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
    LS40_CANDIDATE_ID: 0.0,
    LS41_CANDIDATE_ID: 0.0,
    LS42_CANDIDATE_ID: 0.0,
    LS43_CANDIDATE_ID: 0.0,
    LS44_CANDIDATE_ID: 0.0,
    LS45_CANDIDATE_ID: 0.0,
    LS46_CANDIDATE_ID: 0.0,
    LS47_CANDIDATE_ID: 0.0,
    LS48_CANDIDATE_ID: 0.0,
    LS49_CANDIDATE_ID: 0.0,
    LS50_CANDIDATE_ID: 0.0,
    LS51_CANDIDATE_ID: 0.0,
    LS52_CANDIDATE_ID: 0.0,
    LS53_CANDIDATE_ID: 0.0,
    LS54_CANDIDATE_ID: 0.0,
    LS55_CANDIDATE_ID: 0.0,
    LS56_CANDIDATE_ID: 0.0,
    LS57_CANDIDATE_ID: 0.0,
    LS58_CANDIDATE_ID: 0.0,
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
    LS40_CANDIDATE_ID,
    LS41_CANDIDATE_ID,
    LS42_CANDIDATE_ID,
    LS43_CANDIDATE_ID,
    LS44_CANDIDATE_ID,
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
    LS58_CANDIDATE_ID,
}
LONG_SKIP_NEGATIVE_CONFIRMATION_TRIALS = {LS51_CANDIDATE_ID}
LONG_BULL_SKIP_NEGATIVE_CONFIRMATION_TRIALS = {LS52_CANDIDATE_ID}
LONG_ABOVE_MA_SKIP_NEGATIVE_CONFIRMATION_TRIALS = {LS53_CANDIDATE_ID}
LONG_SKIP_NEGATIVE_CONFIRMATION_TRIALS |= LONG_BULL_SKIP_NEGATIVE_CONFIRMATION_TRIALS
LONG_SKIP_NEGATIVE_CONFIRMATION_TRIALS |= LONG_ABOVE_MA_SKIP_NEGATIVE_CONFIRMATION_TRIALS
LONG_SKIP_REDISTRIBUTE_TRIALS = {
    LS54_CANDIDATE_ID,
    LS55_CANDIDATE_ID,
    LS56_CANDIDATE_ID,
    LS57_CANDIDATE_ID,
    LS58_CANDIDATE_ID,
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
LONG_INVERSE_VOL_TRIALS = {LS40_CANDIDATE_ID}
LONG_STOP_TRIALS = {LS41_CANDIDATE_ID}
PROFIT_LOCK_REDISTRIBUTE_TRIALS = {
    LS42_CANDIDATE_ID,
    LS43_CANDIDATE_ID,
    LS45_CANDIDATE_ID,
}
LONG_BREAKDOWN_EXIT_TRIALS = {
    LS44_CANDIDATE_ID,
    LS46_CANDIDATE_ID,
    LS47_CANDIDATE_ID,
    LS48_CANDIDATE_ID,
    LS49_CANDIDATE_ID,
    LS50_CANDIDATE_ID,
}
REVERSAL_SHORT_TRIALS = {
    LS46_CANDIDATE_ID,
    LS47_CANDIDATE_ID,
    LS48_CANDIDATE_ID,
    LS49_CANDIDATE_ID,
    LS50_CANDIDATE_ID,
}
STOP_STATE_REVERSAL_SHORT_TRIALS = {
    LS48_CANDIDATE_ID,
    LS49_CANDIDATE_ID,
    LS50_CANDIDATE_ID,
}
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
LS41_LONG_STOP_CONFIG: dict[str, Any] = {"long_stop_loss_pct": 0.20}
LS42_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    "lookback_days": 21,
    "threshold": 1.0,
    "scale": 0.5,
    "max_asset_weight": 0.60,
}
LS43_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS42_PROFIT_LOCK_CONFIG,
    "recipient_confirmation_days": 7,
}
LS45_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS42_PROFIT_LOCK_CONFIG,
    "recipient_confirmation_days": 21,
}
PROFIT_LOCK_REDISTRIBUTE_CONFIG_BY_TRIAL = {
    LS42_CANDIDATE_ID: LS42_PROFIT_LOCK_CONFIG,
    LS43_CANDIDATE_ID: LS43_PROFIT_LOCK_CONFIG,
    LS45_CANDIDATE_ID: LS45_PROFIT_LOCK_CONFIG,
}
LS44_BREAKDOWN_EXIT_CONFIG: dict[str, Any] = {
    "lookback_days": 21,
    "threshold": 1.0,
    "scale": 0.5,
    "confirmation_days": 7,
}
LS46_REVERSAL_SHORT_CONFIG: dict[str, Any] = {
    "short_weight": 0.20,
    "hold_days": 28,
}
LS47_REVERSAL_SHORT_CONFIG: dict[str, Any] = {
    **LS46_REVERSAL_SHORT_CONFIG,
    "suppress_long_reentry": True,
}
LS48_REVERSAL_SHORT_CONFIG: dict[str, Any] = {
    **LS47_REVERSAL_SHORT_CONFIG,
    "block_reentry_after_stop": True,
}
LS49_REVERSAL_SHORT_CONFIG: dict[str, Any] = {
    **LS48_REVERSAL_SHORT_CONFIG,
    "rearm_ma_days": 21,
}
LS50_REVERSAL_SHORT_CONFIG: dict[str, Any] = {
    **LS48_REVERSAL_SHORT_CONFIG,
    "rearm_below_stop": True,
}
LS51_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS22_PROFIT_LOCK_CONFIG,
    "skip_if_confirmation_negative_days": 7,
}
LS52_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS51_PROFIT_LOCK_CONFIG,
    "skip_negative_confirmation_regime": "btc_above_ma200",
}
LS53_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS51_PROFIT_LOCK_CONFIG,
    "skip_negative_confirmation_above_ma_days": 21,
}
LS54_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS45_PROFIT_LOCK_CONFIG,
    "skip_if_confirmation_negative_days": 7,
    "skip_negative_confirmation_above_ma_days": 21,
}
LS55_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS54_PROFIT_LOCK_CONFIG,
    "skip_scale": 0.75,
}
LS56_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS54_PROFIT_LOCK_CONFIG,
    "skip_scale": 0.625,
}
LS57_PROFIT_LOCK_CONFIG: dict[str, Any] = {
    **LS54_PROFIT_LOCK_CONFIG,
    "skip_negative_confirmation_min_daily_return": 0.0,
}
LS58_DVOL_CONFIG: dict[str, Any] = {
    "csv_path": "data/raw/deribit_dvol/BTC_DVOL_1D.csv",
    "threshold": 75.0,
    "scale": 0.0,
}
DVOL_RISK_OFF_TRIALS = {LS58_CANDIDATE_ID}
LONG_SKIP_REDISTRIBUTE_CONFIG_BY_TRIAL = {
    LS54_CANDIDATE_ID: LS54_PROFIT_LOCK_CONFIG,
    LS55_CANDIDATE_ID: LS55_PROFIT_LOCK_CONFIG,
    LS56_CANDIDATE_ID: LS56_PROFIT_LOCK_CONFIG,
    LS57_CANDIDATE_ID: LS57_PROFIT_LOCK_CONFIG,
    LS58_CANDIDATE_ID: LS57_PROFIT_LOCK_CONFIG,
}
REVERSAL_SHORT_CONFIG_BY_TRIAL = {
    LS46_CANDIDATE_ID: LS46_REVERSAL_SHORT_CONFIG,
    LS47_CANDIDATE_ID: LS47_REVERSAL_SHORT_CONFIG,
    LS48_CANDIDATE_ID: LS48_REVERSAL_SHORT_CONFIG,
    LS49_CANDIDATE_ID: LS49_REVERSAL_SHORT_CONFIG,
    LS50_CANDIDATE_ID: LS50_REVERSAL_SHORT_CONFIG,
}
LS40_INVERSE_VOL_CONFIG: dict[str, Any] = {
    "lookback_days": 60,
    "min_observations": 45,
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
    if trial_id in LONG_INVERSE_VOL_TRIALS:
        config["inverse_volatility_long_allocation"] = LS40_INVERSE_VOL_CONFIG
    if trial_id in LONG_STOP_TRIALS:
        config.update(LS41_LONG_STOP_CONFIG)
    if trial_id in PROFIT_LOCK_REDISTRIBUTE_TRIALS:
        config["profit_lock_redistribution"] = PROFIT_LOCK_REDISTRIBUTE_CONFIG_BY_TRIAL[
            trial_id
        ]
    if trial_id in LONG_SKIP_REDISTRIBUTE_TRIALS:
        config["profit_lock"] = LONG_SKIP_REDISTRIBUTE_CONFIG_BY_TRIAL[trial_id]
    if trial_id in DVOL_RISK_OFF_TRIALS:
        config["dvol_risk_off"] = dict(LS58_DVOL_CONFIG)
    elif trial_id in LONG_SKIP_NEGATIVE_CONFIRMATION_TRIALS:
        config["profit_lock"] = (
            LS53_PROFIT_LOCK_CONFIG
            if trial_id in LONG_ABOVE_MA_SKIP_NEGATIVE_CONFIRMATION_TRIALS
            else LS52_PROFIT_LOCK_CONFIG
            if trial_id in LONG_BULL_SKIP_NEGATIVE_CONFIRMATION_TRIALS
            else LS51_PROFIT_LOCK_CONFIG
        )
    if trial_id in LONG_BREAKDOWN_EXIT_TRIALS:
        config["profit_lock_breakdown_exit"] = LS44_BREAKDOWN_EXIT_CONFIG
    if trial_id in REVERSAL_SHORT_TRIALS:
        config["profit_lock_reversal_short"] = REVERSAL_SHORT_CONFIG_BY_TRIAL[trial_id]
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
LS42_CONSTRUCTION = (
    "Frozen LS23 with LS22 profit-lock freed weight redistributed to other "
    "already-held H5 assets pro-rata, capped at 60% NAV per asset, with any "
    "unallocatable remainder left in cash"
)
LS43_CONSTRUCTION = (
    "Frozen LS23 with LS22 profit-lock freed weight redistributed only to "
    "already-held H5 assets whose 7D trailing return is stronger than the "
    "trimmed leader's, pro-rata and capped at 60% NAV; otherwise cash"
)
LS44_CONSTRUCTION = (
    "Frozen LS23 with LS22 profit-lock scale changed from half to full exit "
    "only when the trimmed leader's own 7D trailing return is negative; "
    "otherwise the original half-trim remains"
)
LS45_CONSTRUCTION = (
    "Frozen LS23 with LS22 profit-lock freed weight redistributed only to "
    "already-held H5 assets whose 21D trailing return is stronger than the "
    "trimmed leader's, pro-rata and capped at 60% NAV; otherwise cash"
)
LS46_CONSTRUCTION = (
    "Frozen LS44 breakdown full exit, with the freed leader leg shorted at "
    "0.20x total for 28 calendar days; the reversal short has priority over "
    "the LS12 router while active, and both retain the 20% short stop"
)
LS47_CONSTRUCTION = (
    "LS46 reversal short plus a no-reentry rule: while a reversal short is "
    "active, the same asset is removed from the H5 long target so a routine "
    "H5 rebalance cannot immediately close the short; all other LS46 rules "
    "and the 20% short stop remain unchanged"
)
LS48_CONSTRUCTION = (
    "LS47 plus a stop-state rule: if a reversal short is stopped out, that "
    "asset cannot be reopened by another routine rebalance within the same "
    "28-day reversal window; a new reversal window can re-arm it, while all "
    "other LS47 rules and the 20% short stop remain unchanged"
)
LS49_CONSTRUCTION = (
    "LS48 stop-state rule with a price confirmation: a stopped reversal short "
    "can be re-armed only after the asset's last completed daily close is "
    "below its 21-day moving average; otherwise it stays flat until the "
    "current 28-day window expires or a new full-exit window starts"
)
LS50_CONSTRUCTION = (
    "LS48 stop-state rule with a breakout-retest confirmation: a stopped "
    "reversal short can be re-armed only after the asset's last completed "
    "daily close falls back below the actual stop price; otherwise it stays "
    "flat until the current 28-day window expires or a new window starts"
)
LS51_CONSTRUCTION = (
    "Frozen LS23 profit lock except that a 21D >=100% leader is not trimmed "
    "when its own 7D trailing return is negative; positive or missing 7D "
    "confirmation keeps the original half-trim"
)
LS52_CONSTRUCTION = (
    "LS51 skip rule restricted to BTC-above-MA200 bull regimes: in a bear "
    "regime the original LS22 half-trim remains, so the skipped 7D-negative "
    "trim is not allowed to add risk during broad downtrends"
)
LS53_CONSTRUCTION = (
    "LS51 skip rule restricted to leaders still above their own 21D moving "
    "average: a negative 7D pullback that has already lost MA21 receives the "
    "original LS22 half-trim instead of retaining the full leader weight"
)
LS54_CONSTRUCTION = (
    "LS53 skip rule combined with LS45 redistribution: when a trim is not "
    "skipped, freed weight is redistributed only to already-held H5 assets "
    "whose 21D trailing return is stronger than the trimmed leader, capped "
    "at 60% NAV; skipped events keep the full leader and redistribute nothing"
)
LS55_CONSTRUCTION = (
    "LS54 with the MA21-confirmed 7D-negative skip retaining 75% rather than "
    "100% of the leader; the unused 25% stays in cash, while non-skipped LS22 "
    "trims remain at 50% and use the LS45 stronger-21D redistribution"
)
LS56_CONSTRUCTION = (
    "LS54 with the MA21-confirmed 7D-negative skip retaining 62.5% rather "
    "than 100% of the leader; the unused 37.5% stays in cash, while "
    "non-skipped LS22 trims remain at 50% and use the LS45 redistribution"
)
LS57_CONSTRUCTION = (
    "LS54 with a latest-day stabilization gate: the MA21-confirmed 7D-negative "
    "trim is skipped only when the leader's 1D return is non-negative; "
    "otherwise the original half-trim applies, followed by the LS45 "
    "stronger-21D redistribution when not skipped"
)
LS58_CONSTRUCTION = (
    "LS57 unchanged except that the H5 long target is scaled to zero when the "
    "same completed signal day's Deribit BTC DVOL close is above 75; the "
    "short router, profit lock, stops, gross cap and T+1 execution are unchanged"
)
LS41_CONSTRUCTION = (
    "Frozen LS23 with a 20% hourly-mark adverse stop on every H5 long leg; "
    "funding is charged first, stop executes before liquidation, and a stopped "
    "leg may re-enter only at the next scheduled H5 target event"
)
LS40_CONSTRUCTION = (
    "Frozen LS23 with each multi-asset H5 long event reweighted inversely to "
    "its held assets' 60D realized volatility while preserving event gross; "
    "single-asset or incomplete-history events keep original H5 weights and "
    "the LS22 profit lock is applied after reweighting"
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


def apply_dvol_long_risk_off(
    long_targets: Mapping[pd.Timestamp, pd.Series],
    dvol: pd.Series,
    *,
    threshold: float,
    scale: float,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Scale the H5 long book when the completed DVOL close is above a level.

    The signal date is the same UTC day whose DVOL close is already complete
    when the next-day T+1 target is published. Missing DVOL observations fail
    closed rather than silently disabling the overlay.
    """
    if not np.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("threshold must be finite and positive")
    if not np.isfinite(scale) or not 0.0 <= scale <= 1.0:
        raise ValueError("scale must be finite and in [0, 1]")

    levels = pd.to_numeric(pd.Series(dvol), errors="coerce")
    levels.index = pd.DatetimeIndex([_as_utc(value) for value in levels.index])
    levels = levels[~levels.index.duplicated(keep="last")].sort_index()

    scaled: dict[pd.Timestamp, pd.Series] = {}
    audit_rows: list[dict[str, object]] = []
    for raw_date, raw_target in sorted(long_targets.items()):
        date = _as_utc(raw_date)
        if date not in levels.index or not np.isfinite(float(levels.loc[date])):
            raise ValueError(f"missing DVOL close for signal date {date}")
        level = float(levels.loc[date])
        transaction = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        transaction.index = transaction.index.astype(str)
        if transaction.isna().any() or (transaction < 0.0).any():
            raise ValueError("long targets must be finite and non-negative")
        before = float(transaction.sum())
        risk_off = level > float(threshold)
        after_target = transaction * float(scale) if risk_off else transaction
        after_target = after_target.loc[after_target.abs() > 1e-15]
        scaled[date] = after_target.astype(float).sort_index()
        audit_rows.append(
            {
                "date": date,
                "dvol_close": level,
                "threshold": float(threshold),
                "risk_off": risk_off,
                "scale": float(scale) if risk_off else 1.0,
                "target_gross_before": before,
                "target_gross_after": float(after_target.sum()),
            }
        )
    return scaled, pd.DataFrame(audit_rows)


def build_long_targets_for_trial(
    *,
    trial_id: str,
    long_targets: Mapping[pd.Timestamp, pd.Series],
    funding_rates: pd.DataFrame,
    universe: pd.DataFrame,
    available: set[str],
    prices: pd.DataFrame | None = None,
):
    if trial_id in LONG_SKIP_REDISTRIBUTE_TRIALS:
        if prices is None:
            raise ValueError("profit-lock skip/redistribute requires prices")
        config = LONG_SKIP_REDISTRIBUTE_CONFIG_BY_TRIAL[trial_id]
        return trim_extreme_run_single_leader_skip_and_redistribute(
            long_targets,
            prices=prices,
            lookback_days=int(config["lookback_days"]),
            threshold=float(config["threshold"]),
            scale=float(config["scale"]),
            skip_scale=float(config.get("skip_scale", 1.0)),
            max_asset_weight=float(config["max_asset_weight"]),
            recipient_confirmation_days=int(config["recipient_confirmation_days"]),
            skip_if_confirmation_negative_days=int(config["skip_if_confirmation_negative_days"]),
            skip_negative_confirmation_above_ma_days=int(
                config["skip_negative_confirmation_above_ma_days"]
            ),
            skip_negative_confirmation_min_daily_return=(
                None
                if config.get("skip_negative_confirmation_min_daily_return") is None
                else float(config["skip_negative_confirmation_min_daily_return"])
            ),
        )
    if trial_id in PROFIT_LOCK_REDISTRIBUTE_TRIALS:
        if prices is None:
            raise ValueError("profit-lock redistribution requires the point-in-time H5 price panel")
        return trim_extreme_run_single_leader_redistribute(
            long_targets,
            prices=prices,
            **PROFIT_LOCK_REDISTRIBUTE_CONFIG_BY_TRIAL[trial_id],
        )
    if trial_id in LONG_SKIP_NEGATIVE_CONFIRMATION_TRIALS:
        if prices is None:
            raise ValueError("profit-lock negative-confirmation skip requires prices")
        regime = None
        if trial_id in LONG_BULL_SKIP_NEGATIVE_CONFIRMATION_TRIALS:
            if "bitcoin" not in prices.columns:
                raise ValueError("BTC bull-regime skip requires bitcoin prices")
            btc = pd.to_numeric(prices["bitcoin"], errors="coerce")
            regime = (btc > btc.rolling(200, min_periods=200).mean()).rename(
                "btc_above_ma200"
            )
        if trial_id in LONG_ABOVE_MA_SKIP_NEGATIVE_CONFIRMATION_TRIALS:
            profit_lock_config = LS53_PROFIT_LOCK_CONFIG
        elif trial_id in LONG_BULL_SKIP_NEGATIVE_CONFIRMATION_TRIALS:
            profit_lock_config = {
                key: value
                for key, value in LS52_PROFIT_LOCK_CONFIG.items()
                if key != "skip_negative_confirmation_regime"
            }
        else:
            profit_lock_config = LS51_PROFIT_LOCK_CONFIG
        return trim_extreme_run_single_leader(
            long_targets,
            prices=prices,
            **profit_lock_config,
            skip_negative_confirmation_regime=regime,
        )
    if trial_id in LONG_BREAKDOWN_EXIT_TRIALS:
        if prices is None:
            raise ValueError("profit-lock breakdown exit requires the point-in-time H5 price panel")
        return trim_extreme_run_single_leader_breakdown_exit(
            long_targets,
            prices=prices,
            **LS44_BREAKDOWN_EXIT_CONFIG,
        )
    if trial_id in LONG_COMMON_GROSS_TRIALS:
        return preserve_relative_weights_on_same_selection(long_targets)
    if trial_id in LONG_INVERSE_VOL_TRIALS:
        if prices is None:
            raise ValueError("LS40 requires the point-in-time H5 price panel")
        reweighted, reweight_audit = inverse_volatility_reweight_long_targets(
            long_targets,
            prices=prices,
            **LS40_INVERSE_VOL_CONFIG,
        )
        trimmed, trim_audit = trim_extreme_run_single_leader(
            reweighted,
            prices=prices,
            **LS22_PROFIT_LOCK_CONFIG,
        )
        reweight_audit = reweight_audit.rename(
            columns={
                "holdings": "reweight_holdings",
                "gross_before": "reweight_gross_before",
                "gross_after": "reweight_gross_after",
                "l1_change": "reweight_l1_change",
                "changed": "reweight_changed",
                "missing_volatility": "reweight_missing_volatility",
            }
        )
        if trim_audit.empty:
            return trimmed, reweight_audit
        return trimmed, reweight_audit.merge(trim_audit, on="date", how="outer")
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



def _forward_fill_short_target(
    schedule: Mapping[pd.Timestamp, pd.Series],
    date: pd.Timestamp,
) -> pd.Series:
    prior = [stamp for stamp in schedule if stamp <= date]
    if not prior:
        return pd.Series(dtype=float)
    target = pd.to_numeric(pd.Series(schedule[prior[-1]]), errors="coerce")
    target.index = target.index.astype(str)
    if target.isna().any() or (target < 0.0).any():
        raise ValueError("short schedule targets must be finite and non-negative")
    return target.astype(float).sort_index()


def build_reversal_short_schedule(
    base_short_targets: Mapping[pd.Timestamp, pd.Series],
    profit_lock_audit: pd.DataFrame,
    *,
    hold_days: int,
    short_weight: float,
) -> dict[pd.Timestamp, pd.Series]:
    """Prioritize profit-lock reversal shorts over the base short router.

    Full-exit profit-lock events become short candidates for ``hold_days``.
    If several distinct assets overlap, the configured total short weight is
    split equally across those unique assets.  When no reversal short is
    active, the last base short target is carried forward.  Scheduling only
    at event and expiry dates avoids re-opening a stopped leg on every day.
    """
    if hold_days < 1:
        raise ValueError("hold_days must be positive")
    if not np.isfinite(short_weight) or not 0.0 < short_weight <= 0.25:
        raise ValueError("short_weight must be finite and in (0, 0.25]")
    if "full_exit" not in profit_lock_audit.columns:
        raise ValueError("profit-lock audit is missing full_exit")

    base: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in base_short_targets.items():
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or (target < 0.0).any():
            raise ValueError("short schedule targets must be finite and non-negative")
        base[date] = target.astype(float).sort_index()
    base = dict(sorted(base.items()))

    events: dict[pd.Timestamp, str] = {}
    for row in profit_lock_audit.itertuples(index=False):
        if not bool(getattr(row, "full_exit", False)):
            continue
        events[_as_utc(getattr(row, "date"))] = str(getattr(row, "leader"))
    if not events:
        return base

    expiry_dates = {date + pd.Timedelta(days=hold_days) for date in events}
    schedule_dates = sorted(set(base) | set(events) | expiry_dates)
    schedule: dict[pd.Timestamp, pd.Series] = {}
    for date in schedule_dates:
        active_assets = sorted(
            {
                asset
                for event_date, asset in events.items()
                if event_date <= date < event_date + pd.Timedelta(days=hold_days)
            }
        )
        if active_assets:
            weight = float(short_weight) / len(active_assets)
            schedule[date] = pd.Series(
                {asset: weight for asset in active_assets}, dtype=float
            ).sort_index()
        else:
            schedule[date] = _forward_fill_short_target(base, date)
    return schedule


def build_reversal_short_block_windows(
    profit_lock_audit: pd.DataFrame,
    *,
    hold_days: int,
    execution_hour: int = 3,
    execution_minute: int = 0,
) -> tuple[tuple[str, pd.Timestamp, pd.Timestamp], ...]:
    """Return execution-time windows for stop-aware reversal short episodes."""
    if hold_days < 1:
        raise ValueError("hold_days must be positive")
    if "full_exit" not in profit_lock_audit.columns:
        raise ValueError("profit-lock audit is missing full_exit")

    windows: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for row in profit_lock_audit.itertuples(index=False):
        if not bool(getattr(row, "full_exit", False)):
            continue
        signal_date = _as_utc(getattr(row, "date")).normalize()
        execution_start = signal_date + pd.Timedelta(
            days=1,
            hours=execution_hour,
            minutes=execution_minute,
        )
        execution_end = signal_date + pd.Timedelta(
            days=hold_days + 1,
            hours=execution_hour,
            minutes=execution_minute,
        )
        windows.append((str(getattr(row, "leader")), execution_start, execution_end))
    return tuple(sorted(windows, key=lambda item: (item[0], item[1], item[2])))


def suppress_long_targets_while_reversal_short(
    long_targets: Mapping[pd.Timestamp, pd.Series],
    short_targets: Mapping[pd.Timestamp, pd.Series],
    base_short_targets: Mapping[pd.Timestamp, pd.Series],
) -> dict[pd.Timestamp, pd.Series]:
    """Remove an asset from the long book while its reversal short is active."""
    normalized_long: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in long_targets.items():
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
            raise ValueError("long target weights must be finite")
        if (target < 0.0).any():
            raise ValueError("long target weights must be non-negative")
        normalized_long[date] = target.astype(float).sort_index()
    normalized_long = dict(sorted(normalized_long.items()))

    base: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in base_short_targets.items():
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or (target < 0.0).any():
            raise ValueError("base short targets must be finite and non-negative")
        base[date] = target.astype(float).sort_index()
    base = dict(sorted(base.items()))

    combined_short: dict[pd.Timestamp, pd.Series] = {}
    for raw_date, raw_target in short_targets.items():
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce")
        target.index = target.index.astype(str)
        if target.isna().any() or (target < 0.0).any():
            raise ValueError("short targets must be finite and non-negative")
        combined_short[date] = target.astype(float).sort_index()
    combined_short = dict(sorted(combined_short.items()))

    dates = sorted(set(normalized_long) | set(combined_short) | set(base))
    suppressed: dict[pd.Timestamp, pd.Series] = {}
    for date in dates:
        long_target = _forward_fill_short_target(normalized_long, date)
        base_target = _forward_fill_short_target(base, date)
        short_target = _forward_fill_short_target(combined_short, date)
        if not _target_equal(short_target.to_dict(), base_target.to_dict()):
            for asset in short_target.index:
                if asset in long_target.index:
                    long_target.loc[asset] = 0.0
        suppressed[date] = long_target[long_target > 1e-15].sort_index()
    return suppressed


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
    profit_lock_audit: pd.DataFrame | None = None,
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
    base_short = build_regime_short_schedules(
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
    if trial_id in REVERSAL_SHORT_TRIALS:
        if profit_lock_audit is None:
            raise ValueError("reversal short requires the profit-lock audit")
        short_targets, sleeve_audit, bear_schedule, exit_schedule = base_short
        reversal_config = REVERSAL_SHORT_CONFIG_BY_TRIAL[trial_id]
        combined = build_reversal_short_schedule(
            short_targets,
            profit_lock_audit,
            short_weight=float(reversal_config["short_weight"]),
            hold_days=int(reversal_config["hold_days"]),
        )
        return combined, sleeve_audit, bear_schedule, exit_schedule
    return base_short


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
            LS40_CANDIDATE_ID,
            LS41_CANDIDATE_ID,
            LS42_CANDIDATE_ID,
            LS43_CANDIDATE_ID,
            LS44_CANDIDATE_ID,
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
            LS58_CANDIDATE_ID,
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
    parser.add_argument("--execution-hour", type=int, default=3)
    parser.add_argument("--execution-minute", type=int, default=0)
    parser.add_argument(
        "--execution-price-snap",
        choices=("exact", "floor", "ceil"),
        default="exact",
    )
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
    if not 0 <= args.execution_hour <= 23:
        parser.error("--execution-hour must be in [0, 23]")
    if not 0 <= args.execution_minute <= 59:
        parser.error("--execution-minute must be in [0, 59]")
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
    dvol_audit = pd.DataFrame()
    if args.trial_id in DVOL_RISK_OFF_TRIALS:
        dvol_path = Path(str(LS58_DVOL_CONFIG["csv_path"]))
        if not dvol_path.is_file():
            raise SystemExit(
                f"DVOL data not found: {dvol_path}; run scripts/download_deribit_dvol.py"
            )
        dvol_frame = pd.read_csv(dvol_path)
        if not {"date", "close"}.issubset(dvol_frame.columns):
            raise SystemExit(f"DVOL data {dvol_path} needs date and close columns")
        dvol_series = pd.to_numeric(dvol_frame["close"], errors="coerce")
        dvol_series.index = pd.DatetimeIndex(
            pd.to_datetime(dvol_frame["date"], utc=True, format="mixed")
        )
        evaluation_start = pd.Timestamp(args.evaluation_start, tz="UTC")
        overlay_targets = {
            date: target
            for date, target in long_targets.items()
            if _as_utc(date) >= evaluation_start
        }
        scaled_targets, dvol_audit = apply_dvol_long_risk_off(
            overlay_targets,
            dvol_series,
            threshold=float(LS58_DVOL_CONFIG["threshold"]),
            scale=float(LS58_DVOL_CONFIG["scale"]),
        )
        long_targets = {
            **{
                date: target
                for date, target in long_targets.items()
                if _as_utc(date) < evaluation_start
            },
            **scaled_targets,
        }
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
            profit_lock_audit=long_tilt_audit,
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
                mark_candles=mark_candles,
                start_date=args.start_date,
                short_funding=short_funding,
            )
            long_targets = suppress_long_targets_while_reversal_short(
                long_targets,
                short_targets,
                base_short_targets,
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
        long_stop_loss_pct=(
            float(LS41_LONG_STOP_CONFIG["long_stop_loss_pct"])
            if args.trial_id in LONG_STOP_TRIALS
            else None
        ),
        short_stop_reentry_block_windows=(
            build_reversal_short_block_windows(
                long_tilt_audit,
                hold_days=int(
                    REVERSAL_SHORT_CONFIG_BY_TRIAL[args.trial_id]["hold_days"]
                ),
                execution_hour=int(args.execution_hour),
                execution_minute=int(args.execution_minute),
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
        max_gross_exposure=target_total_gross,
        execution_hour=int(args.execution_hour),
        execution_minute=int(args.execution_minute),
        execution_price_snap=str(args.execution_price_snap),
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
    if "date" in dvol_audit.columns and not dvol_audit.empty:
        dvol_dates = pd.to_datetime(dvol_audit["date"], utc=True)
        dvol_audit = dvol_audit.loc[dvol_dates >= evaluation_start].copy()
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
        "execution_utc": f"{int(args.execution_hour):02d}:{int(args.execution_minute):02d}",
        "execution_price_model": f"mark_1h_open_{args.execution_price_snap}",
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
        "inverse_vol_event_count": (
            int(long_tilt_audit["reweight_changed"].notna().sum())
            if "reweight_changed" in long_tilt_audit.columns
            else 0
        ),
        "inverse_vol_changed_count": (
            int(long_tilt_audit["reweight_changed"].fillna(False).sum())
            if "reweight_changed" in long_tilt_audit.columns
            else 0
        ),
        "inverse_vol_l1_change_total": (
            float(long_tilt_audit["reweight_l1_change"].fillna(0.0).sum())
            if "reweight_l1_change" in long_tilt_audit.columns
            else 0.0
        ),
        "inverse_vol_missing_count": (
            int(long_tilt_audit["reweight_missing_volatility"].fillna(False).sum())
            if "reweight_missing_volatility" in long_tilt_audit.columns
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
        "profit_lock_redistributed_weight_total": (
            float(long_tilt_audit["redistributed_weight"].sum())
            if "redistributed_weight" in long_tilt_audit.columns
            else 0.0
        ),
        "profit_lock_full_exit_count": (
            int(long_tilt_audit["full_exit"].fillna(False).sum())
            if "full_exit" in long_tilt_audit.columns
            else 0
        ),
        "profit_lock_freed_weight_total": (
            float(long_tilt_audit["freed_weight"].sum())
            if "freed_weight" in long_tilt_audit.columns
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
        "dvol_risk_off_days": (
            int(dvol_audit["risk_off"].fillna(False).sum())
            if "risk_off" in dvol_audit.columns
            else 0
        ),
        "dvol_risk_off_long_gross_closed_total": (
            float(
                (
                    dvol_audit.loc[dvol_audit["risk_off"], "target_gross_before"]
                    - dvol_audit.loc[dvol_audit["risk_off"], "target_gross_after"]
                ).sum()
            )
            if {"risk_off", "target_gross_before", "target_gross_after"}.issubset(
                dvol_audit.columns
            )
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
        "gross_breach_hours": int(
            (result.gross_exposure > float(target_total_gross) + 1e-12).sum()
        ),
        "short_open_count": short_opens,
        "stop_loss_count": int(stop_reason.sum()) if not trades.empty else 0,
        "short_stop_loss_count": int((short_side & stop_reason).sum()) if not trades.empty else 0,
        "long_stop_loss_count": int(((trades.get("side") == "long") & stop_reason).sum()) if not trades.empty else 0,
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
    dvol_audit.to_csv(output_dir / "dvol_risk_off_audit.csv", index=False)
    if args.trial_id == LS20_CANDIDATE_ID:
        long_tilt_audit.to_csv(output_dir / "selection_event_audit.csv", index=False)
    if args.trial_id in LONG_PROFIT_LOCK_TRIALS:
        long_tilt_audit.to_csv(output_dir / "profit_lock_audit.csv", index=False)
    if args.trial_id in LONG_INVERSE_VOL_TRIALS:
        long_tilt_audit.to_csv(output_dir / "inverse_vol_audit.csv", index=False)
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
                    else LS40_SPEC_PATH
                    if args.trial_id == LS40_CANDIDATE_ID
                    else LS41_SPEC_PATH
                    if args.trial_id == LS41_CANDIDATE_ID
                    else LS42_SPEC_PATH
                    if args.trial_id == LS42_CANDIDATE_ID
                    else LS43_SPEC_PATH
                    if args.trial_id == LS43_CANDIDATE_ID
                    else LS44_SPEC_PATH
                    if args.trial_id == LS44_CANDIDATE_ID
                    else LS45_SPEC_PATH
                    if args.trial_id == LS45_CANDIDATE_ID
                    else LS46_SPEC_PATH
                    if args.trial_id == LS46_CANDIDATE_ID
                    else LS47_SPEC_PATH
                    if args.trial_id == LS47_CANDIDATE_ID
                    else LS48_SPEC_PATH
                    if args.trial_id == LS48_CANDIDATE_ID
                    else LS49_SPEC_PATH
                    if args.trial_id == LS49_CANDIDATE_ID
                    else LS50_SPEC_PATH
                    if args.trial_id == LS50_CANDIDATE_ID
                    else LS51_SPEC_PATH
                    if args.trial_id == LS51_CANDIDATE_ID
                    else LS52_SPEC_PATH
                    if args.trial_id == LS52_CANDIDATE_ID
                    else LS53_SPEC_PATH
                    if args.trial_id == LS53_CANDIDATE_ID
                    else LS54_SPEC_PATH
                    if args.trial_id == LS54_CANDIDATE_ID
                    else LS55_SPEC_PATH
                    if args.trial_id == LS55_CANDIDATE_ID
                    else LS56_SPEC_PATH
                    if args.trial_id == LS56_CANDIDATE_ID
                    else LS57_SPEC_PATH
                    if args.trial_id == LS57_CANDIDATE_ID
                    else LS58_SPEC_PATH
                    if args.trial_id == LS58_CANDIDATE_ID
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
                    else LS40_CONSTRUCTION
                    if args.trial_id == LS40_CANDIDATE_ID
                    else LS41_CONSTRUCTION
                    if args.trial_id == LS41_CANDIDATE_ID
                    else LS42_CONSTRUCTION
                    if args.trial_id == LS42_CANDIDATE_ID
                    else LS43_CONSTRUCTION
                    if args.trial_id == LS43_CANDIDATE_ID
                    else LS44_CONSTRUCTION
                    if args.trial_id == LS44_CANDIDATE_ID
                    else LS45_CONSTRUCTION
                    if args.trial_id == LS45_CANDIDATE_ID
                    else LS46_CONSTRUCTION
                    if args.trial_id == LS46_CANDIDATE_ID
                    else LS47_CONSTRUCTION
                    if args.trial_id == LS47_CANDIDATE_ID
                    else LS48_CONSTRUCTION
                    if args.trial_id == LS48_CANDIDATE_ID
                    else LS49_CONSTRUCTION
                    if args.trial_id == LS49_CANDIDATE_ID
                    else LS50_CONSTRUCTION
                    if args.trial_id == LS50_CANDIDATE_ID
                    else LS51_CONSTRUCTION
                    if args.trial_id == LS51_CANDIDATE_ID
                    else LS52_CONSTRUCTION
                    if args.trial_id == LS52_CANDIDATE_ID
                    else LS53_CONSTRUCTION
                    if args.trial_id == LS53_CANDIDATE_ID
                    else LS54_CONSTRUCTION
                    if args.trial_id == LS54_CANDIDATE_ID
                    else LS55_CONSTRUCTION
                    if args.trial_id == LS55_CANDIDATE_ID
                    else LS56_CONSTRUCTION
                    if args.trial_id == LS56_CANDIDATE_ID
                    else LS57_CONSTRUCTION
                    if args.trial_id == LS57_CANDIDATE_ID
                    else LS58_CONSTRUCTION
                    if args.trial_id == LS58_CANDIDATE_ID
                    else CONSTRUCTION
                ),
                "frozen_config": _trial_frozen_config(args.trial_id),
                "start_date": args.evaluation_start,
                "warmup_start_date": args.start_date,
                "end_date": args.end_date,
                "cost_bps": float(args.cost_bps),
                "execution_utc": f"{int(args.execution_hour):02d}:{int(args.execution_minute):02d}",
                "execution_price_model": f"mark_1h_open_{args.execution_price_snap}",
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
                f"- DVOL risk-off days: {summary['dvol_risk_off_days']}",
                f"- DVOL long gross closed: {summary['dvol_risk_off_long_gross_closed_total']:.6f}x",
                f"- Max observed gross: {summary['max_observed_gross']:.6f}x",
                f"- Gross breach hours: {summary['gross_breach_hours']}",
                f"- Liquidations: {summary['liquidation_count']}",
                f"- Stop-losses: {summary['stop_loss_count']} (long {summary['long_stop_loss_count']} / short {summary['short_stop_loss_count']})",
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
