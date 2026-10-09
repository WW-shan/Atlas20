"""Inventory every strategy configuration the project has backtested.

The Deflated Sharpe Ratio in ``scripts/run_phase_momentum_multiple_testing.py``
needs the number of trials behind the champion and the dispersion of their
Sharpe ratios.  This script rebuilds that record from the report artifacts in
``reports/`` and, read-only through ``git show``, from report files that were
deleted from ``reports/`` but survive in git history.

Conventions
-----------
* A configuration is one set of strategy rules and parameters on one universe.
  Cost levels, rolling start dates, phase offsets, sub-windows and stress
  windows are multiplicity inside a study, not new configurations.
* A study is one report directory.  Every configuration a study lists counts,
  even when two of them happen to produce identical returns.
* A configuration is new unless it reproduces, to 1e-9, the annualized Sharpe
  of a configuration in an earlier-processed study on the same window start,
  universe and cost, or it is a declared re-run of an earlier configuration
  (the same grid and config id on another window or data panel).
* Each study is read at its primary cost: the cost nearest 20 bps at which
  every configuration of the study was evaluated.  ``N bps`` is fee plus
  slippage per unit of one-way turnover (``src/atlas20/backtest/engine.py``).
* Sharpe ratios are the annualized values each study stored:
  sqrt(365) * mean / std of daily returns with a zero risk-free rate.  No
  conversion is applied.

Studies are processed scope-first: Top20 studies starting 2022-01-01 (with
their 2023-01-01 out-of-sample meta-strategies) in research order, then Top50
studies starting 2022-01-01, then every other window.  A configuration counts
in the Top20/2022 scope whenever it was tested there, and counts once overall.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

PERIODS_PER_YEAR = 365
SHARPE_DECIMALS = 9
REFERENCE_COST_BPS = 20.0
SCOPE_UNIVERSE = "Top20"
SCOPE_START = "2022-01-01"
OOS_START = "2023-01-01"
# Parent of 9d71d1e ("make CoinMarketCap the only historical provider"), which
# deleted the April profit-max and sector studies from reports/.
APRIL_COMMIT = "9d71d1e^"
# Last commit holding the 144-cell bull-offense scan; e896e4e cut it to 36 cells.
BULL_SCAN_COMMIT = "5b37099"

UNCOMMITTED_ORIGINS = frozenset({"working tree (modified)", "working tree (untracked)"})
ALL_TRIALS = "all_trials"
PREREGISTERED_STUDY = "phase_momentum_hypotheses_2026_10"
PREREGISTERED_LEDGER = Path("reports/research_trial_inventory/preregistered_trials.csv")
TOP20_2022_TRIALS = "top20_2022_trials"

# Top20 / 2022-01-01 studies in research order (commit order; lane logic
# inside one commit).  Earlier studies own a repeated return stream.
TOP20_2022_ORDER: tuple[str, ...] = (
    "convex_validation_2022_top20",
    "convex_overlay_sweep_2022_top20",
    "convex_overlay_sweep_2022_top20_validation",
    "ctrend_focus_2022_top20",
    "ctrend_champion_top20_2022",
    "no_leverage_ablation_2022",
    "tsmom_validation_2022",
    "bull_offense_finalist_2022",
    "trend_stop_champion_2022",
    "trend_stop_validation_2022",
    "event_driven_validation_2022",
    "strategy_evidence_audit_2022",
    "decision_point_ablation_2022",
    "volatility_gate_validation_2022",
    "phase_invariant_vol_target_2022",
    "phase_invariant_vol_target_gates_2022",
    "phase_invariant_vol_target_gates_btc_2022",
    "vol_target_frontier_2022",
    "vol_target_neighborhood_2022",
    "vol_target_cost_rolling_2022",
    "vol_target_score_family_balanced_2022",
    "vol_target_score_family_relative_strength_2022",
    "vol_target_score_family_breakout_2022",
    "vol_target_score_family_acceleration_2022",
    "vol_target_score_family_vol_adjusted_2022",
    "vol_target_ensemble_2022",
    "vol_target_walk_forward_2022",
    "vol_target_walk_forward_multiple_2022",
    "momentum_event_ensemble_2022",
    "momentum_event_breadth_overlay_2022",
    "research_md:momentum_event_gate_audit",
    "research_md:trend_stop_champion_with_btc",
    "phase_momentum_2022",
    "phase_momentum_parameter_ensemble_2022",
    "phase_momentum_trend_overlay_2022",
    "phase_momentum_walk_forward_2022",
    "phase_momentum_leave_one_out_2022",
    "phase_momentum_parameter_leave_one_out_2022",
    "phase_momentum_execution_lag_2022",
    PREREGISTERED_STUDY,
)
TOP50_2022_ORDER: tuple[str, ...] = (
    "convex_validation_2022_top50",
    "ctrend_focus_2022_top50",
    "ensemble_ctrend_2022_top50",
)
# Other windows.  Re-runs of Top20/2022 grids come first, so a strategy they
# reproduce exactly on a shared window inherits the in-scope configuration;
# a surviving artifact comes before its superseded git copy.
OTHER_WINDOW_ORDER: tuple[str, ...] = (
    "no_leverage_ablation_v2",
    "top20_convex_validation(old panel)",
    "bull_offense_finalist",
    "bull_offense_finalist_aggressive",
    "pipeline_latest",
    "pipeline_bear_bottom_2022_11_21",
    "pipeline_five_year_2020_2024",
    "pipeline_five_year_exact_2021_04_22",
    "git:profit_max_search",
    "git:profit_max_refine",
    "git:sector_lead_v3_scan(bear_bottom)",
    "git:sector_lead_v3_scan(five_year_exact)",
    "git:sector_lead_v3_study",
    "git:sector_v2_study",
    "git:stop_scan_trailing",
    "git:stop_study",
    "bull_offense_scan",
    f"git:bull_offense_scan@{BULL_SCAN_COMMIT}",
)
PROCESSING_ORDER: tuple[str, ...] = TOP20_2022_ORDER + TOP50_2022_ORDER + OTHER_WINDOW_ORDER

# Report directories that hold no new configuration (rolling starts,
# sub-windows, stress windows, audits, live signals, or a re-listing).
NO_NEW_CONFIGURATION_DIRS: dict[str, str] = {
    "convex_validation_2022_top20_validation": "robustness re-runs of Top20 screen cells",
    "ctrend_focus_2022_top50_validation": "robustness re-runs of Top50 focus cells",
    "focus_top_2022_top50": "one Top50 focus cell re-run with daily returns",
    "phase_momentum_fixed_cscv_2022": "CSCV over the fixed phase-momentum family",
    "phase_momentum_regime_2022": "regime breakdown of the primary",
    "phase_momentum_robustness_2022": "rolling starts, sub-windows and the 2020-10 to 2021-12 stress window",
    "phase_momentum_selection_audit_2022": "selection audit of the primary",
    "phase_momentum_live": "live signal",
    "phase_momentum_asset_attribution": "per-coin attribution of the primary (trials counted via the ledger)",
    "phase_momentum_asset_attribution_h3": "per-coin attribution of H3 (trials counted via the ledger)",
    "phase_momentum_book_concentration": "book concentration of the primary (no new configuration)",
    "phase_momentum_candidate_eval": "side-by-side re-listing of registered trials (counted via the ledger)",
    "phase_momentum_crash_states": "crash-month state diagnostic of the frozen trial (no configuration)",
    "phase_momentum_flow_states": "volume/turnover state screening of the frozen trial (no configuration)",
    "phase_momentum_hourly_states": "intraday state screening of the frozen trial (no configuration)",
    "phase_momentum_funding_states": "funding-rate state screening of the frozen trial (no configuration)",
    "phase_momentum_chase_risk": "entry-extremity diagnostic of the frozen trial (no configuration)",
    "phase_momentum_candidate_eval_h5": "side-by-side re-listing of registered trials (counted via the ledger)",
    "phase_momentum_dispersion_diagnostic": "diagnostic screening of the dispersion mechanism (no configuration)",
    "phase_momentum_dsr_gap": "prices the Deflated Sharpe gap of a saved return series (no configuration)",
    "phase_momentum_dispersion_overlay": "diagnostic screening of the dispersion overlay (no charged configuration)",
    "phase_momentum_multiple_testing_h3": "CSCV/PBO over the fixed candidate family",
    "phase_momentum_multiple_testing_overlays": "CSCV/PBO over the fixed candidate family",
    "phase_momentum_regime_overlays": "regime breakdown of saved candidate returns",
    "provider_publication": "CMC publication-time probe (ops, no strategy configuration)",
    "phase_momentum_multiple_testing_2022": "re-listing of phase-momentum configurations counted in their own studies",
    "phase_momentum_oos_2026": "out-of-sample tracking of the frozen primary",
}
NON_RESEARCH_DIRS = frozenset({"app_runs", "ui_mockups", "research_trial_inventory"})

VARIES: dict[str, str] = {
    "pipeline_latest": "TOP20_MOM / TOP20_SECTOR top-N x frequency x regime; EQ/BTC/ETH bull_only",
    "pipeline_bear_bottom_2022_11_21": "same 27 strategies as pipeline_latest (old panel)",
    "pipeline_five_year_2020_2024": "same 27 strategies as pipeline_latest (old panel)",
    "pipeline_five_year_exact_2021_04_22": "same 27 strategies as pipeline_latest (old panel)",
    "git:profit_max_search": "momentum_lead / sector_lead x top-N x frequency x weights x liquidity x BTC stop",
    "git:profit_max_refine": "14 files: weight surfaces, random weights, 11-17D calendars, trailing lookback/confirm, universe looseness, regime overlays",
    "git:sector_lead_v3_scan(bear_bottom)": "top1/2 x 7D/biweekly x (no stop, BTC trailing 14/18/21/24 x re-entry)",
    "git:sector_lead_v3_scan(five_year_exact)": "same grid as the bear-bottom scan",
    "git:sector_lead_v3_study": "sector-lead v3 variants",
    "git:sector_v2_study": "sector-lead v2 variants",
    "git:stop_scan_trailing": "BTC trailing-stop lookbacks",
    "git:stop_study": "BTC stop variants",
    "bull_offense_scan": "hold 1-3 x lookback 14-45 x exit MA 20/50/100",
    f"git:bull_offense_scan@{BULL_SCAN_COMMIT}": "same grid x leverage 1/1.25/1.5/2",
    "bull_offense_finalist": "hold x lookback x BTC MA x asset MA x target vol 0.5-1.0",
    "bull_offense_finalist_2022": "hold x lookback x BTC MA x asset MA x target vol 0.5-1.0",
    "bull_offense_finalist_aggressive": "one finalist grid cell at 5/8/10/15 bps",
    "top20_convex_validation(old panel)": "2218 recipes: ctrend_lite 1440, leader_momentum 576, sector_lead 180, champion_ablation 22",
    "convex_validation_2022_top20": "2218 recipes: ctrend_lite 1440, leader_momentum 576, sector_lead 180, champion_ablation 22",
    "convex_validation_2022_top50": "2218 recipes: ctrend_lite 1440, leader_momentum 576, sector_lead 180, champion_ablation 22",
    "convex_overlay_sweep_2022_top20": "cycle x 3 CTREND scores x BTC in/out x stop type and parameters x risk-off/initial asset",
    "convex_overlay_sweep_2022_top20_validation": "volatility targets on the overlay champion",
    "ctrend_focus_2022_top20": "liquidity x 14/21D x 3 scores x BTC x MA 75-150 x confirm",
    "ctrend_focus_2022_top50": "liquidity x 14/21D x 3 scores x BTC x MA 75-150 x confirm",
    "ensemble_ctrend_2022_top50": "2/3/5/10-component equal-weight CTREND ensembles",
    "no_leverage_ablation_2022": "20 bases x 20 overlays",
    "no_leverage_ablation_v2": "20 bases x 20 overlays",
    "tsmom_validation_2022": "180 bases x 8 overlays on Top20 and Top50",
    "ctrend_champion_top20_2022": "cost only (champion re-run)",
    "trend_stop_champion_2022": "cost only (champion re-run)",
    "trend_stop_validation_2022": "own-MA stop 20-200D (9 values) x confirm 1-3",
    "event_driven_validation_2022": "160 event-driven + 16 fixed-frequency + 36 rank-stop variants",
    "strategy_evidence_audit_2022": "one rule; 21 phase offsets and 1/3/7/21-tranche baskets",
    "decision_point_ablation_2022": "own stop / BTC gate / re-entry, 21-tranche baskets",
    "volatility_gate_validation_2022": "BTC gate lookback x volatility multiple x confirm",
    "phase_invariant_vol_target_2022": "14/21D x target vol 0.3-0.8 x stop",
    "phase_invariant_vol_target_gates_2022": "14/21D x target vol x stop x gate",
    "phase_invariant_vol_target_gates_btc_2022": "14/21D x target vol x stop x gate, BTC selectable",
    "vol_target_frontier_2022": "target vol 0.8-2.0",
    "vol_target_neighborhood_2022": "7-28D x target vol 0.5-0.8 x vol window 20/30/60",
    "vol_target_cost_rolling_2022": "costs and rolling starts of the vol-target versions",
    "vol_target_score_family_balanced_2022": "score family x target vol 0.5/0.6",
    "vol_target_score_family_relative_strength_2022": "score family x target vol 0.5/0.6",
    "vol_target_score_family_breakout_2022": "score family x target vol 0.5/0.6",
    "vol_target_score_family_acceleration_2022": "score family x target vol 0.5/0.6",
    "vol_target_score_family_vol_adjusted_2022": "score family x target vol 0.5/0.6",
    "vol_target_ensemble_2022": "fixed equal weight of 8 vol-target versions",
    "vol_target_walk_forward_2022": "walk-forward selection by trailing Sharpe",
    "vol_target_walk_forward_multiple_2022": "walk-forward selection by trailing return",
    "momentum_event_ensemble_2022": "primary, 3 event-rule neighbours, non-strict Top20 exit",
    "momentum_event_breadth_overlay_2022": "breadth threshold 0.40-0.60; blend 25/50/75",
    "research_md:momentum_event_gate_audit": "BTC gate (none, MA50/100/200 x confirm 1-3) and 90%/100% target vol",
    "research_md:trend_stop_champion_with_btc": "trend-stop champion with BTC allowed in selection",
    "phase_momentum_2022": "one-at-a-time parameter neighbours and single-signal ablations",
    "phase_momentum_parameter_ensemble_2022": "13-spec equal-weight parameter ensemble",
    "phase_momentum_trend_overlay_2022": "asset trend filters and their combinations",
    "phase_momentum_walk_forward_2022": "trailing-Sharpe selection over 25 specs; equal weight of 25",
    "phase_momentum_leave_one_out_2022": "drop one signal or one phase",
    "phase_momentum_parameter_leave_one_out_2022": "drop one of the 13 ensemble specs",
    "phase_momentum_execution_lag_2022": "extra execution lag of 0/1/2 days",
}

PIPELINE_SNAPSHOTS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    ("pipeline_latest", "latest", ("2021-01-01", "2026-09-21")),
    ("pipeline_bear_bottom_2022_11_21", "bear_bottom_to_current_2022_11_21_2026_04_22", ("2022-11-21", "2026-04-21")),
    ("pipeline_five_year_2020_2024", "five_year_2020_2024", ("2020-01-01", "2024-12-31")),
    ("pipeline_five_year_exact_2021_04_22", "five_year_exact_2021_04_22_2026_04_22", ("2021-04-22", "2026-04-21")),
)
PIPELINE_BENCHMARKS = frozenset({"BTC_BH__always_on", "ETH_BH__always_on", "TOP20_EQ__always_on"})
NO_LEVERAGE_BENCHMARKS = frozenset({"BTC_BH__none", "ETH_BH__none"})
APRIL_BEAR_DIR = "reports/bear_bottom_to_current_2022_11_21_2026_04_22"
APRIL_FIVE_DIR = "reports/five_year_exact_2021_04_22_2026_04_22"
APRIL_BEAR_WINDOW = ("2022-11-21", "2026-04-21")
APRIL_FIVE_WINDOW = ("2021-04-22", "2026-04-21")
PROFIT_MAX_METRICS = frozenset(
    {
        "multiple", "cagr", "sharpe", "mdd", "max_drawdown", "turnover", "annualized_turnover",
        "monthly_win_rate", "total_return", "final_equity", "ending_equity", "annualized_volatility",
        "sortino", "calmar", "avg_turnover_per_rebalance", "average_holdings", "vol", "exposure",
    }
)
SCREEN_FAMILY = {
    "ctrend_lite": "ctrend_lite",
    "leader_momentum": "leader_momentum",
    "champion_ablation": "leader_momentum",
    "sector_lead": "sector",
}
NO_LEVERAGE_FAMILY = {
    "ctrend_lite": "ctrend_lite",
    "momentum_lead": "leader_momentum",
    "momentum": "topN_momentum",
    "sector_lead": "sector",
    "sector": "sector",
    "benchmark": "benchmark_timing",
    "equal_weight": "benchmark_timing",
}
PHASE_WINDOW = ("2022-01-01", "2026-09-21")
PHASE_OOS_WINDOW = ("2023-01-01", "2026-09-21")
CTREND_WINDOW = ("2022-01-01", "2026-09-23")

# RESEARCH.md reports these runs only as text (2 bps multiples).  Each entry is
# (study, config id, window end, anchor text that must appear in RESEARCH.md).
_GATE_AUDIT = "research_md:momentum_event_gate_audit"
RESEARCH_MD_ONLY: tuple[tuple[str, str, str, str], ...] = (
    (_GATE_AUDIT, "no_btc_gate", "2026-09-21", "无 BTC 闸门只有 10.80x"),
    (_GATE_AUDIT, "btc_ma50_confirm1", "2026-09-21", "MA50/confirm1–3"),
    (_GATE_AUDIT, "btc_ma50_confirm2", "2026-09-21", "MA50/confirm1–3"),
    (_GATE_AUDIT, "btc_ma50_confirm3", "2026-09-21", "MA50/confirm1–3"),
    (_GATE_AUDIT, "btc_ma100_confirm1", "2026-09-21", "MA100/confirm1–3"),
    (_GATE_AUDIT, "btc_ma100_confirm3", "2026-09-21", "MA100/confirm1–3"),
    (_GATE_AUDIT, "btc_ma200_confirm1", "2026-09-21", "MA200/confirm1–3"),
    (_GATE_AUDIT, "btc_ma200_confirm2", "2026-09-21", "MA200/confirm1–3"),
    (_GATE_AUDIT, "btc_ma200_confirm3", "2026-09-21", "MA200/confirm1–3"),
    (_GATE_AUDIT, "target_vol_90_100", "2026-09-21", "90%/100%"),
    ("research_md:trend_stop_champion_with_btc", "btc_in_selection", "2026-09-23", "加入 BTC 后同一策略 @2bps 只有约 15x"),
)


def _fmt(value: object) -> str:
    """Stable text for a parameter value: integral floats print as integers."""
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isnan(number):
            return "nan"
        return str(int(number)) if number.is_integer() else repr(number)
    return str(value)


def _lookup(mapping: dict[str, str], key: object, where: str) -> str:
    try:
        return mapping[str(key)]
    except KeyError:
        raise ValueError(f"unknown strategy family {key!r} in {where}") from None


class TrialRecorder:
    """Collect one row per (study, universe, configuration, cost)."""

    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []
        self._index: dict[tuple[str, str, str, float], float] = {}
        self.repeated_rows = 0

    def add(
        self,
        study: str,
        config_id: object,
        window: tuple[str, str],
        cost_bps: float,
        universe: str,
        sharpe: float,
        *,
        source: str,
        column: str,
        family: str,
        lineage: str | None = None,
        benchmark: bool = False,
        note: str = "",
    ) -> None:
        config = str(config_id)
        cost = float(cost_bps)
        value = float(sharpe)
        if not math.isfinite(value):
            raise ValueError(f"{study}: configuration {config!r} at {cost:g} bps has a non-finite Sharpe in {source}")
        key = (study, universe, config, cost)
        if key in self._index:
            if abs(self._index[key] - value) > 10.0 ** -SHARPE_DECIMALS:
                raise ValueError(f"{study}: conflicting Sharpe values for {config!r} at {cost:g} bps in {source}")
            self.repeated_rows += 1
            return
        self._index[key] = value
        self.rows.append(
            {
                "study": study,
                "config_id": config,
                "window_start": window[0],
                "window_end": window[1],
                "cost_bps": cost,
                "universe": universe,
                "annualized_sharpe": value,
                "family": family,
                "benchmark": bool(benchmark),
                "lineage": lineage or study,
                "source": source,
                "source_column": column,
                "note": note,
            }
        )

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


@dataclass(frozen=True)
class UnscoredConfiguration:
    """A configuration that was run but has no recorded Sharpe ratio."""

    study: str
    config_id: str
    window_start: str
    window_end: str
    cost_bps: float
    universe: str
    family: str
    reason: str
    source: str


class Sources:
    """Read report files from the working tree, or read-only from git history."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.read: dict[str, dict[str, str]] = {}
        self._status = self._working_tree_status()

    def csv(self, relative: str) -> pd.DataFrame:
        return pd.read_csv(io.BytesIO(self._working_tree_bytes(relative)))

    def json(self, relative: str) -> dict[str, object]:
        data: dict[str, object] = json.loads(self._working_tree_bytes(relative).decode("utf-8"))
        return data

    def git_csv(self, commit: str, relative: str) -> pd.DataFrame:
        data = self.git("show", f"{commit}:{relative}")
        self._record(f"{commit}:{relative}", data, origin=f"git show {commit}")
        return pd.read_csv(io.BytesIO(data))

    def git_csv_paths(self, commit: str, directory: str) -> list[str]:
        listing = self.git("ls-tree", "--name-only", commit, directory.rstrip("/") + "/").decode("utf-8")
        return sorted(line for line in listing.splitlines() if line.endswith(".csv"))

    def git(self, *args: str) -> bytes:
        result = subprocess.run(["git", *args], cwd=self.repo_root, capture_output=True, check=False)
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"git {' '.join(args)} failed: {message}")
        return result.stdout

    def report_dirs(self) -> list[str]:
        return sorted(path.name for path in (self.repo_root / "reports").iterdir() if path.is_dir())

    def _working_tree_bytes(self, relative: str) -> bytes:
        data = (self.repo_root / relative).read_bytes()
        self._record(relative, data, origin=f"working tree ({self._status.get(relative, 'committed')})")
        return data

    def _record(self, label: str, data: bytes, *, origin: str) -> None:
        self.read[label] = {"origin": origin, "sha256": hashlib.sha256(data).hexdigest()}

    def _working_tree_status(self) -> dict[str, str]:
        listing = self.git("status", "--porcelain=v1", "--untracked-files=all", "--", "reports").decode("utf-8")
        status: dict[str, str] = {}
        for line in listing.splitlines():
            code, name = line[:2], line[3:]
            status[name] = "untracked" if code == "??" else "modified"
        return status


# --------------------------------------------------------------------------- loaders


def _pipeline_family(strategy: str) -> str:
    if strategy.startswith("TOP20_MOM"):
        return "topN_momentum"
    if strategy.startswith("TOP20_SECTOR"):
        return "sector"
    return "benchmark_timing"


def _load_pipeline(src: Sources, rec: TrialRecorder) -> None:
    for study, directory, window in PIPELINE_SNAPSHOTS:
        path = f"reports/{directory}/strategy_summary.csv"
        frame = src.csv(path)
        for strategy, sharpe in zip(frame["strategy"], frame["sharpe"]):
            rec.add(
                study, strategy, window, 20.0, "Top20", sharpe,
                source=path, column="sharpe", family=_pipeline_family(str(strategy)),
                lineage="pipeline", benchmark=strategy in PIPELINE_BENCHMARKS,
                note="" if study == "pipeline_latest" else "old panel",
            )


def _bull_id(row: pd.Series) -> str:
    return (
        f"h{_fmt(row['hold_count'])}_lb{_fmt(row['lookback'])}_btcma{_fmt(row['btc_ma'])}"
        f"_assetma{_fmt(row['asset_ma'])}_tv{_fmt(row['target_vol'])}"
    )


def _load_bull_offense(src: Sources, rec: TrialRecorder, bull_commit: str) -> None:
    path = "reports/bull_offense_scan/bull_offense_summary.csv"
    frame = src.csv(path)
    for strategy, sharpe in zip(frame["strategy"], frame["sharpe"]):
        rec.add(
            "bull_offense_scan", strategy, ("2021-01-01", "2026-09-21"), 20.0, "Top20", sharpe,
            source=path, column="sharpe", family="bull_offense", lineage="bull_offense_scan",
            benchmark=strategy == "BTC_BUY_HOLD",
        )
    frame = src.git_csv(bull_commit, path)
    for strategy, sharpe in zip(frame["strategy"], frame["sharpe"]):
        leverage = str(strategy).rsplit("_x", 1)[-1] if "_x" in str(strategy) else ""
        rec.add(
            f"git:bull_offense_scan@{bull_commit}", strategy, ("2021-01-01", "2026-09-20"), 20.0, "Top20", sharpe,
            source=f"git show {bull_commit}:{path}", column="sharpe", family="bull_offense",
            lineage="bull_offense_scan", benchmark=strategy == "BTC_BUY_HOLD",
            note="" if leverage in ("", "1") else f"leverage x{leverage}, removed from reports/ in e896e4e",
        )
    for study, start in (("bull_offense_finalist", "2021-01-01"), ("bull_offense_finalist_2022", "2022-01-01")):
        window = (start, "2026-09-21")
        sweep_path = f"reports/{study}/sweep_summary.csv"
        sweep = src.csv(sweep_path)
        for _, row in sweep.iterrows():
            rec.add(
                study, _bull_id(row), window, row["total_cost_bps"], "Top20", row["sharpe"],
                source=sweep_path, column="sharpe", family="bull_offense", lineage="bull_offense_finalist",
            )
        cost_path = f"reports/{study}/cost_sensitivity.csv"
        for _, row in src.csv(cost_path).iterrows():
            rec.add(
                study, _bull_id(row), window, row["total_cost_bps"], "Top20", row["sharpe"],
                source=cost_path, column="sharpe", family="bull_offense", lineage="bull_offense_finalist",
                note="cost re-run of a sweep cell",
            )
    path = "reports/bull_offense_finalist_aggressive/cost_sensitivity.csv"
    for _, row in src.csv(path).iterrows():
        rec.add(
            "bull_offense_finalist_aggressive", _bull_id(row), ("2021-01-01", "2026-09-21"),
            row["total_cost_bps"], "Top20", row["sharpe"], source=path, column="sharpe",
            family="bull_offense", lineage="bull_offense_finalist",
        )


def _load_convex_screens(src: Sources, rec: TrialRecorder) -> None:
    screens = (
        ("top20_convex_validation(old panel)", "top20_convex_validation", ("2021-01-01", "2026-09-20"), "Top20",
         "old (pre-CMC-only) panel; window end not recorded"),
        ("convex_validation_2022_top20", "convex_validation_2022_top20", ("2022-01-01", "2026-09-23"), "Top20", ""),
        ("convex_validation_2022_top50", "convex_validation_2022_top50", ("2022-01-01", "2026-09-22"), "Top50", ""),
    )
    for study, directory, window, universe, note in screens:
        path = f"reports/{directory}/candidate_summary.csv"
        frame = src.csv(path)
        for cid, family, sharpe in zip(frame["candidate_id"], frame["family_id"], frame["sharpe"]):
            rec.add(
                study, cid, window, 20.0, universe, sharpe, source=path, column="sharpe",
                family=_lookup(SCREEN_FAMILY, family, path), lineage="convex_screen", note=note,
            )


def _load_ctrend_lanes(src: Sources, rec: TrialRecorder) -> None:
    path = "reports/convex_overlay_sweep_2022_top20/candidate_summary.csv"
    frame = src.csv(path)
    for cost in (2, 20):
        column = f"sharpe_{cost}bps"
        for cid, sharpe in zip(frame["candidate_id"], frame[column]):
            rec.add(
                "convex_overlay_sweep_2022_top20", cid, CTREND_WINDOW, cost, "Top20", sharpe,
                source=path, column=column, family="ctrend_lite",
                note="window end not recorded; inferred from the Top20 screen",
            )
    path = "reports/convex_overlay_sweep_2022_top20_validation/voltarget_overlay.csv"
    frame = src.csv(path)
    for cost, block in frame.groupby("cost_bps", sort=False):
        # Each cost block starts with the champion without volatility targeting;
        # target_vol cannot tell that row (listed as 1.0) from the 100% target.
        for position, (target, sharpe) in enumerate(zip(block["target_vol"], block["sharpe"])):
            cid = "champion_no_voltarget" if position == 0 else f"champion_voltarget_tv{_fmt(target)}"
            rec.add(
                "convex_overlay_sweep_2022_top20_validation", cid, CTREND_WINDOW, cost, "Top20", sharpe,
                source=path, column="sharpe", family="ctrend_lite",
            )
    for study, universe, end in (("ctrend_focus_2022_top20", "Top20", "2026-09-23"),
                                 ("ctrend_focus_2022_top50", "Top50", "2026-09-22")):
        path = f"reports/{study}/candidate_summary.csv"
        frame = src.csv(path)
        for cid, sharpe in zip(frame["candidate_id"], frame["sharpe"]):
            rec.add(
                study, cid, ("2022-01-01", end), 20.0, universe, sharpe, source=path, column="sharpe",
                family="ctrend_lite", note="window end inferred",
            )
    path = "reports/ensemble_ctrend_2022_top50/summary.csv"
    frame = src.csv(path)
    for variant, sharpe in zip(frame["variant"], frame["sharpe"]):
        rec.add(
            "ensemble_ctrend_2022_top50", variant, ("2022-01-01", "2026-09-21"), 20.0, "Top50", sharpe,
            source=path, column="sharpe", family="ctrend_lite", note="cost not recorded (assumed 20 bps)",
        )
    for study, cid in (("ctrend_champion_top20_2022", "CTREND_TOP20_CHAMPION"),
                       ("trend_stop_champion_2022", "CTREND_TREND_STOP")):
        path = f"reports/{study}/performance_summary.csv"
        frame = src.csv(path)
        for candidate, cost, sharpe in zip(frame["candidate_id"], frame["total_cost_bps"], frame["sharpe"]):
            benchmark = str(candidate).startswith("BTC_BH")
            rec.add(
                study, "BTC_BH" if benchmark else cid, CTREND_WINDOW, cost, "Top20", sharpe,
                source=path, column="sharpe", family="ctrend_lite", benchmark=benchmark,
            )
    path = "reports/trend_stop_validation_2022/trend_stop_summary.csv"
    frame = src.csv(path)
    for variant, sharpe in zip(frame["variant_id"], frame["full_sharpe_20bps"]):
        rec.add(
            "trend_stop_validation_2022", variant, CTREND_WINDOW, 20.0, "Top20", sharpe,
            source=path, column="full_sharpe_20bps", family="ctrend_lite",
        )
    path = "reports/event_driven_validation_2022/event_variant_summary.csv"
    frame = src.csv(path)
    for cost in (2, 20):
        column = f"full_sharpe_{cost}bps"
        for variant, sharpe in zip(frame["variant_id"], frame[column]):
            rec.add(
                "event_driven_validation_2022", variant, CTREND_WINDOW, cost, "Top20", sharpe,
                source=path, column=column, family="ctrend_lite",
            )
    path = "reports/strategy_evidence_audit_2022/staggered_robustness.csv"
    frame = src.csv(path)
    for cost, group in frame[frame["tranches"] == 21].groupby("cost_bps"):
        rec.add(
            "strategy_evidence_audit_2022", "trend_stop_rule_21tranche_basket", PHASE_WINDOW, cost, "Top20",
            group["sharpe"].iloc[0], source=path, column="sharpe (tranches == 21)", family="ctrend_lite",
            note="21 phase offsets and 1/3/7-tranche baskets are multiplicity of one rule",
        )
    path = "reports/decision_point_ablation_2022/staggered_basket.csv"
    frame = src.csv(path).drop_duplicates(["variant_id", "cost_bps"])
    for variant, cost, sharpe in zip(frame["variant_id"], frame["cost_bps"], frame["sharpe"]):
        rec.add(
            "decision_point_ablation_2022", variant, PHASE_WINDOW, cost, "Top20", sharpe,
            source=path, column="sharpe (21-tranche basket)", family="ctrend_lite",
        )
    path = "reports/volatility_gate_validation_2022/staggered_basket.csv"
    frame = src.csv(path)
    for _, row in frame.iterrows():
        cid = (
            f"lb{_fmt(row['lookback'])}_vw{_fmt(row['vol_window'])}"
            f"_k{_fmt(row['vol_multiple'])}_c{_fmt(row['confirm_days'])}"
        )
        rec.add(
            "volatility_gate_validation_2022", cid, PHASE_WINDOW, row["cost_bps"], "Top20", row["sharpe"],
            source=path, column="sharpe (21-tranche basket)", family="ctrend_lite",
        )


def _load_no_leverage_and_tsmom(src: Sources, rec: TrialRecorder) -> None:
    for study, start in (("no_leverage_ablation_2022", "2022-01-01"), ("no_leverage_ablation_v2", "2021-01-01")):
        window = (start, "2026-09-21")
        path = f"reports/{study}/candidate_summary.csv"
        summary = src.csv(path)
        families = dict(zip(summary["candidate_id"], summary["family"]))
        for cid, family, sharpe in zip(summary["candidate_id"], summary["family"], summary["sharpe"]):
            rec.add(
                study, cid, window, 20.0, "Top20", sharpe, source=path, column="sharpe",
                family=_lookup(NO_LEVERAGE_FAMILY, family, path), lineage="no_leverage",
                benchmark=cid in NO_LEVERAGE_BENCHMARKS,
            )
        cost_path = f"reports/{study}/cost_sensitivity.csv"
        costs = src.csv(cost_path)
        for cid, cost, sharpe in zip(costs["candidate_id"], costs["total_cost_bps"], costs["sharpe"]):
            rec.add(
                study, cid, window, cost, "Top20", sharpe, source=cost_path, column="sharpe",
                family=_lookup(NO_LEVERAGE_FAMILY, families.get(cid, ""), cost_path), lineage="no_leverage",
                benchmark=cid in NO_LEVERAGE_BENCHMARKS, note="cost re-run",
            )
    path = "reports/tsmom_validation_2022/candidate_summary.csv"
    frame = src.csv(path)
    for cid, cost, size, sharpe in zip(
        frame["candidate_id"], frame["total_cost_bps"], frame["universe_size"], frame["sharpe"]
    ):
        rec.add(
            "tsmom_validation_2022", cid, ("2022-01-01", "2026-09-22"), cost, f"Top{int(size)}", sharpe,
            source=path, column="sharpe", family="tsmom",
        )


def _vol_target_dirs(src: Sources) -> list[str]:
    fixed = [
        "phase_invariant_vol_target_2022",
        "phase_invariant_vol_target_gates_2022",
        "phase_invariant_vol_target_gates_btc_2022",
        "vol_target_frontier_2022",
        "vol_target_neighborhood_2022",
        "vol_target_cost_rolling_2022",
    ]
    score_families = [
        name for name in src.report_dirs()
        if name.startswith("vol_target_score_family_") and name.endswith("_2022")
    ]
    return fixed + score_families


def _load_vol_target_lane(src: Sources, rec: TrialRecorder) -> None:
    for study in _vol_target_dirs(src):
        manifest = src.json(f"reports/{study}/manifest.json")
        score_family = str(manifest.get("score_family", ""))
        include_btc = bool(manifest.get("include_btc", False))
        path = f"reports/{study}/variant_summary.csv"
        frame = src.csv(path)
        for _, row in frame.iterrows():
            cid = (
                f"c{_fmt(row['cycle_days'])}_tv{_fmt(row['target_volatility'])}_vw{_fmt(row['vol_window'])}"
                f"_{row['stop_mode']}_{row['gate_mode']}"
            )
            cid += "_withbtc" if include_btc else ""
            cid += "" if score_family == "ctrend_lite_balanced" else f"_{score_family}"
            rec.add(
                study, cid, PHASE_WINDOW, row["cost_bps"], "Top20", row["basket_sharpe"],
                source=path, column="basket_sharpe", family="ctrend_lite",
            )
    for study, cid in (("vol_target_walk_forward_2022", "wf_select_trailing_sharpe"),
                       ("vol_target_walk_forward_multiple_2022", "wf_select_trailing_return")):
        path = f"reports/{study}/summary.csv"
        frame = src.csv(path).set_index("strategy")
        rec.add(
            study, cid, PHASE_OOS_WINDOW, 20.0, "Top20", frame.loc["walk_forward_switch40bps", "sharpe"],
            source=path, column="sharpe (walk_forward_switch40bps)", family="ctrend_lite",
            note="out-of-sample window; 20 bps plus 40 bps per switch",
        )
        rec.add(
            study, "vt_equal_weight_8", PHASE_OOS_WINDOW, 20.0, "Top20",
            frame.loc["equal_weight_candidates", "sharpe"], source=path,
            column="sharpe (equal_weight_candidates)", family="ctrend_lite", lineage="vol_target_ensemble",
            note="out-of-sample sub-window of vol_target_ensemble_2022",
        )
    path = "reports/vol_target_ensemble_2022/summary.csv"
    frame = src.csv(path)
    full = frame[(frame["strategy"] == "ensemble") & (frame["period"] == "full")]
    for cost, sharpe in zip(full["cost_bps"], full["sharpe"]):
        rec.add(
            "vol_target_ensemble_2022", "vt_equal_weight_8", PHASE_WINDOW, cost, "Top20", sharpe,
            source=path, column="sharpe (period == full)", family="ctrend_lite", lineage="vol_target_ensemble",
        )


def _momentum_event_primary(src: Sources) -> tuple[str, list[str]]:
    """Primary spec name and the neighbours that report multiples only."""
    specs = src.csv("reports/momentum_event_ensemble_2022/spec_sensitivity.csv")
    names = list(dict.fromkeys(str(name) for name in specs["spec"]))
    primary = [name for name in names if name.startswith("primary")]
    if len(primary) != 1:
        raise ValueError(f"expected one primary spec in momentum_event_ensemble_2022, found {primary}")
    membership = src.csv("reports/momentum_event_ensemble_2022/membership_sensitivity.csv")
    neighbours = [name for name in names if name != primary[0]]
    if (~membership["strict_top20_exit"].astype(bool)).any():
        neighbours.append("non_strict_top20_exit")
    return primary[0], neighbours


def _load_momentum_event_lane(src: Sources, rec: TrialRecorder) -> list[UnscoredConfiguration]:
    primary, neighbours = _momentum_event_primary(src)
    path = "reports/momentum_event_ensemble_2022/summary.csv"
    frame = src.csv(path)
    full = frame[frame["period"] == "full_2022_plus"]
    for cost, sharpe in zip(full["cost_bps"], full["sharpe"]):
        rec.add(
            "momentum_event_ensemble_2022", primary, PHASE_WINDOW, cost, "Top20", sharpe,
            source=path, column="sharpe (period == full_2022_plus)", family="ctrend_lite",
        )
    study = "momentum_event_breadth_overlay_2022"
    path = f"reports/{study}/breadth_threshold_sensitivity.csv"
    frame = src.csv(path)
    for threshold, cost, sharpe in zip(frame["breadth_threshold"], frame["cost_bps"], frame["full_sharpe"]):
        rec.add(
            study, f"breadth_thr{_fmt(threshold)}", PHASE_WINDOW, cost, "Top20", sharpe,
            source=path, column="full_sharpe", family="ctrend_lite",
        )
    path = f"reports/{study}/blend_sensitivity.csv"
    frame = src.csv(path)
    for base, breadth, cost, sharpe in zip(
        frame["baseline_weight"], frame["breadth50_weight"], frame["cost_bps"], frame["full_sharpe"]
    ):
        rec.add(
            study, f"blend_base{_fmt(base)}_breadth50_{_fmt(breadth)}", PHASE_WINDOW, cost, "Top20", sharpe,
            source=path, column="full_sharpe", family="ctrend_lite",
        )
    return [
        UnscoredConfiguration(
            "momentum_event_ensemble_2022", name, *PHASE_WINDOW, 20.0, "Top20", "ctrend_lite",
            "multiples only (no Sharpe recorded)",
            "reports/momentum_event_ensemble_2022/spec_sensitivity.csv; membership_sensitivity.csv",
        )
        for name in neighbours
    ]


def _load_phase_momentum_lane(src: Sources, rec: TrialRecorder) -> None:
    family = "phase_momentum"
    path = "reports/phase_momentum_2022/summary.csv"
    frame = src.csv(path)
    primary = frame[frame["strategy"] == "phase_momentum"]
    for cost, sharpe in zip(primary["cost_bps"], primary["sharpe"]):
        rec.add("phase_momentum_2022", "primary", PHASE_WINDOW, cost, "Top20", sharpe,
                source=path, column="sharpe", family=family)
    path = "reports/phase_momentum_2022/parameter_neighborhood.csv"
    frame = src.csv(path)
    for strategy, cost, sharpe in zip(frame["strategy"], frame["cost_bps"], frame["sharpe"]):
        cid = str(strategy).replace("param_", "", 1)
        if cid != "primary":  # the primary is read from summary.csv
            rec.add("phase_momentum_2022", cid, PHASE_WINDOW, cost, "Top20", sharpe,
                    source=path, column="sharpe", family=family)
    path = "reports/phase_momentum_2022/signal_ablation.csv"
    frame = src.csv(path)
    for strategy, cost, sharpe in zip(frame["strategy"], frame["cost_bps"], frame["sharpe"]):
        if strategy != "signal_all_signals":  # all signals is the primary
            rec.add("phase_momentum_2022", str(strategy).replace("signal_", "single_signal_", 1), PHASE_WINDOW,
                    cost, "Top20", sharpe, source=path, column="sharpe", family=family)
    path = "reports/phase_momentum_trend_overlay_2022/summary.csv"
    frame = src.csv(path)
    for strategy, cost, sharpe in zip(frame["strategy"], frame["cost_bps"], frame["sharpe"]):
        rec.add("phase_momentum_trend_overlay_2022", str(strategy).replace("param_", "", 1), PHASE_WINDOW, cost,
                "Top20", sharpe, source=path, column="sharpe", family=family)
    path = "reports/phase_momentum_parameter_ensemble_2022/summary.csv"
    frame = src.csv(path)
    for cost, sharpe in zip(frame["cost_bps"], frame["sharpe"]):
        rec.add("phase_momentum_parameter_ensemble_2022", "parameter_ensemble", PHASE_WINDOW, cost, "Top20", sharpe,
                source=path, column="sharpe", family=family)
    path = "reports/phase_momentum_walk_forward_2022/summary.csv"
    frame = src.csv(path).set_index("strategy")
    rec.add("phase_momentum_walk_forward_2022", "wf_select_trailing_sharpe", PHASE_OOS_WINDOW, 20.0, "Top20",
            frame.loc["walk_forward_sharpe_switch40bps", "sharpe"], source=path,
            column="sharpe (walk_forward_sharpe_switch40bps)", family=family,
            note="out-of-sample window; 20 bps plus 40 bps per switch")
    rec.add("phase_momentum_walk_forward_2022", "equal_weight_candidates", PHASE_OOS_WINDOW, 20.0, "Top20",
            frame.loc["fixed_equal_weight_candidates", "sharpe"], source=path,
            column="sharpe (fixed_equal_weight_candidates)", family=family, note="out-of-sample window")
    path = "reports/phase_momentum_leave_one_out_2022/summary.csv"
    frame = src.csv(path)
    for variant, sharpe in zip(frame["variant"], frame["sharpe"]):
        rec.add("phase_momentum_leave_one_out_2022", variant, PHASE_WINDOW, 20.0, "Top20", sharpe,
                source=path, column="sharpe", family=family)
    path = "reports/phase_momentum_parameter_leave_one_out_2022/summary.csv"
    frame = src.csv(path)
    for excluded, sharpe in zip(frame["excluded_index"], frame["sharpe"]):
        rec.add("phase_momentum_parameter_leave_one_out_2022", f"ensemble_minus_spec{_fmt(excluded)}", PHASE_WINDOW,
                20.0, "Top20", sharpe, source=path, column="sharpe", family=family)
    path = "reports/phase_momentum_execution_lag_2022/summary.csv"
    frame = src.csv(path)
    for lag, cost, sharpe in zip(frame["execution_lag_days"], frame["cost_bps"], frame["sharpe"]):
        rec.add("phase_momentum_execution_lag_2022", f"execution_lag_{_fmt(lag)}d", PHASE_WINDOW, cost, "Top20",
                sharpe, source=path, column="sharpe", family=family)


def _load_april_lane(src: Sources, rec: TrialRecorder, commit: str) -> None:
    """Profit-max and sector studies deleted from reports/ in 9d71d1e."""
    note = "cost not recorded (preset 10 + 10 bps)"
    path = f"{APRIL_BEAR_DIR}/profit_max_search/profit_max_search_summary.csv"
    frame = src.git_csv(commit, path)
    keys = [column for column in frame.columns if column not in PROFIT_MAX_METRICS]
    for _, row in frame.iterrows():
        cid = "|".join(_fmt(row[key]) for key in keys)
        rec.add(
            "git:profit_max_search", cid, APRIL_BEAR_WINDOW, 20.0, "Top20", row["sharpe"],
            source=f"git show {commit}:{path}", column="sharpe",
            family="sector" if "sector_lead" in cid else "leader_momentum", note=note,
        )
    refine_paths = src.git_csv_paths(commit, f"{APRIL_BEAR_DIR}/profit_max_refine")
    if not refine_paths:
        raise ValueError(f"no profit_max_refine CSV files at {commit}")
    for path in refine_paths:
        frame = src.git_csv(commit, path)
        keys = [column for column in frame.columns if column not in PROFIT_MAX_METRICS]
        stem = Path(path).stem
        for _, row in frame.iterrows():
            # The search a file belongs to fixes settings its columns omit
            # (for example the all-1M versus ex-BTC universe), so the file
            # name is part of the configuration.
            cid = stem + ":" + "|".join(_fmt(row[key]) for key in keys)
            rec.add(
                "git:profit_max_refine", cid, APRIL_BEAR_WINDOW, 20.0, "Top20", row["sharpe"],
                source=f"git show {commit}:{APRIL_BEAR_DIR}/profit_max_refine/*.csv", column="sharpe",
                family="leader_momentum", note=note,
            )
    pipeline_names = {str(row["config_id"]) for row in rec.rows if row["lineage"] == "pipeline"}
    studies = (
        ("git:sector_lead_v3_scan(bear_bottom)", f"{APRIL_BEAR_DIR}/sector_lead_v3_scan/sector_lead_v3_scan_summary.csv",
         APRIL_BEAR_WINDOW),
        ("git:sector_lead_v3_scan(five_year_exact)",
         f"{APRIL_FIVE_DIR}/sector_lead_v3_scan/sector_lead_v3_scan_summary.csv", APRIL_FIVE_WINDOW),
        ("git:sector_lead_v3_study", f"{APRIL_FIVE_DIR}/sector_lead_v3_study/sector_lead_v3_summary.csv",
         APRIL_FIVE_WINDOW),
        ("git:sector_v2_study", f"{APRIL_FIVE_DIR}/sector_v2_study/sector_v2_summary.csv", APRIL_FIVE_WINDOW),
        ("git:stop_scan_trailing", f"{APRIL_FIVE_DIR}/stop_scan_trailing/trailing_stop_scan_summary.csv",
         APRIL_FIVE_WINDOW),
        ("git:stop_study", f"{APRIL_FIVE_DIR}/stop_study/stop_study_summary.csv", APRIL_FIVE_WINDOW),
    )
    for study, path, window in studies:
        frame = src.git_csv(commit, path)
        for strategy, sharpe in zip(frame["strategy"], frame["sharpe"]):
            if strategy in pipeline_names:
                lineage = "pipeline"
            elif study.startswith("git:sector_lead_v3_scan"):
                lineage = "sector_lead_v3_scan"
            else:
                lineage = study
            rec.add(
                study, strategy, window, 20.0, "Top20", sharpe, source=f"git show {commit}:{path}",
                column="sharpe", family="topN_momentum" if str(strategy).startswith("TOP20_MOM") else "sector",
                lineage=lineage, note=note,
            )


def _ledger_bool(value: object) -> bool:
    """Parse the ledger's textual boolean fields without accepting loose values."""
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no", ""}:
        return False
    raise ValueError(f"invalid ledger boolean {value!r}")


def _ledger_result_row(ledger: pd.DataFrame, trial_id: str) -> pd.Series | None:
    """The last terminal result row for one preregistered trial, if any."""
    rows = ledger[
        (ledger["trial_id"].astype(str) == trial_id)
        & (ledger["status"].astype(str).str.lower().isin({"completed", "evaluated", "evaluate_only", "failed"}))
    ]
    if rows.empty:
        return None
    return rows.iloc[-1]


def _load_preregistered_lane(src: Sources, rec: TrialRecorder) -> list[UnscoredConfiguration]:
    """Load the pre-registered H2-H4 ledger into the trial inventory.

    A registered trial that has not produced a usable main/lag0/20bps Sharpe
    is returned as an unscored configuration, so it still counts in the
    multiple-testing denominator.  Completed counted trials contribute their
    registered main-window Sharpe.  The baseline/control entries are never
    counted as new trials.
    """
    ledger_path = Path(src.repo_root) / PREREGISTERED_LEDGER
    if not ledger_path.exists():
        return []
    ledger = src.csv(str(PREREGISTERED_LEDGER)).fillna("")
    required = {"trial_id", "status", "counts_as_trial"}
    missing = sorted(required - set(ledger.columns))
    if missing:
        raise ValueError(f"{PREREGISTERED_LEDGER}: missing columns {missing}")

    registrations = ledger[ledger["status"].astype(str).str.lower() == "registered"].copy()
    if registrations.empty:
        return []
    unscored: list[UnscoredConfiguration] = []
    seen: set[str] = set()
    for _, registration in registrations.iterrows():
        trial_id = str(registration["trial_id"])
        if trial_id in seen:
            continue
        seen.add(trial_id)
        if not _ledger_bool(registration.get("counts_as_trial", "")):
            continue

        terminal = _ledger_result_row(ledger, trial_id)
        if terminal is None:
            unscored.append(
                UnscoredConfiguration(
                    PREREGISTERED_STUDY,
                    trial_id,
                    SCOPE_START,
                    PHASE_WINDOW[1],
                    REFERENCE_COST_BPS,
                    SCOPE_UNIVERSE,
                    "phase_momentum",
                    "registered but not yet completed",
                    str(PREREGISTERED_LEDGER),
                )
            )
            continue
        status = str(terminal.get("status", "")).lower()
        result_path = str(terminal.get("result_path", "")).strip()
        if status == "failed":
            reason = "completed run failed"
        elif not result_path:
            reason = "completed run has no result_path"
        elif not (Path(src.repo_root) / result_path).exists():
            reason = f"result file missing: {result_path}"
        else:
            runs = src.csv(result_path).fillna("")
            rows = runs[
                (runs["trial_id"].astype(str) == trial_id)
                & (runs["window"].astype(str) == "main")
                & (runs["fill"].astype(str) == "lag0")
                & (pd.to_numeric(runs["cost_bps"], errors="coerce") == REFERENCE_COST_BPS)
            ]
            if rows.empty:
                reason = "no main/lag0/20bps result row"
            else:
                sharpe = pd.to_numeric(rows["sharpe"], errors="coerce").iloc[-1]
                if pd.isna(sharpe) or not math.isfinite(float(sharpe)):
                    reason = "main/lag0/20bps Sharpe is not finite"
                else:
                    rec.add(
                        PREREGISTERED_STUDY,
                        trial_id,
                        PHASE_WINDOW,
                        REFERENCE_COST_BPS,
                        SCOPE_UNIVERSE,
                        float(sharpe),
                        source=result_path,
                        column="sharpe (window='main', fill='lag0', cost_bps=20)",
                        family="phase_momentum",
                        lineage=PREREGISTERED_STUDY,
                    )
                    continue
        unscored.append(
            UnscoredConfiguration(
                PREREGISTERED_STUDY,
                trial_id,
                SCOPE_START,
                PHASE_WINDOW[1],
                REFERENCE_COST_BPS,
                SCOPE_UNIVERSE,
                "phase_momentum",
                reason,
                result_path or str(PREREGISTERED_LEDGER),
            )
        )
    return unscored


def research_md_configurations(research_md: str) -> tuple[list[UnscoredConfiguration], dict[str, bool]]:
    """Configurations RESEARCH.md reports only as text, and whether each anchor is still present."""
    configurations = [
        UnscoredConfiguration(
            study, config_id, SCOPE_START, end, 2.0, SCOPE_UNIVERSE, "ctrend_lite",
            "RESEARCH.md text only (2 bps multiple)", f"RESEARCH.md: {anchor}",
        )
        for study, config_id, end, anchor in RESEARCH_MD_ONLY
    ]
    anchors = {anchor: anchor in research_md for _, _, _, anchor in RESEARCH_MD_ONLY}
    return configurations, anchors


def collect_trials(
    src: Sources, *, april_commit: str, bull_commit: str
) -> tuple[pd.DataFrame, list[UnscoredConfiguration], int]:
    """Every (study, universe, configuration, cost) row, the unscored configurations, and repeated rows skipped."""
    rec = TrialRecorder()
    _load_pipeline(src, rec)
    _load_bull_offense(src, rec, bull_commit)
    _load_convex_screens(src, rec)
    _load_ctrend_lanes(src, rec)
    _load_no_leverage_and_tsmom(src, rec)
    _load_vol_target_lane(src, rec)
    unscored = _load_momentum_event_lane(src, rec)
    _load_phase_momentum_lane(src, rec)
    unscored.extend(_load_preregistered_lane(src, rec))
    _load_april_lane(src, rec, april_commit)
    return rec.frame(), unscored, rec.repeated_rows


# --------------------------------------------------------------------------- de-duplication


def primary_costs(rows: pd.DataFrame) -> dict[str, float]:
    """Cost nearest 20 bps at which every configuration of a study was evaluated.

    Benchmarks are ignored when the study has anything else.  If no cost covers
    every configuration, the nearest evaluated cost is used.  Ties go to the
    higher cost.
    """
    result: dict[str, float] = {}
    for study, group in rows.groupby("study", sort=False):
        scored = group[~group["benchmark"]] if (~group["benchmark"]).any() else group
        configurations = len(scored[["universe", "config_id"]].drop_duplicates())
        complete = [
            float(cost)
            for cost, at_cost in scored.groupby("cost_bps")
            if len(at_cost[["universe", "config_id"]].drop_duplicates()) == configurations
        ]
        candidates = complete or sorted(float(cost) for cost in scored["cost_bps"].unique())
        result[str(study)] = min(candidates, key=lambda cost: (abs(cost - REFERENCE_COST_BPS), -cost))
    return result


def assign_identities(trials: pd.DataFrame) -> pd.Series:
    """Configuration identity ``lineage|universe|config_id``.

    Studies that re-run one grid on another window or data panel share a
    lineage, so the same config id there is the same configuration.  Names
    alone are not trusted across lineages: the no-leverage ablation's
    ``X_bull__none`` bases re-implement the pipeline's ``X__bull_only``
    strategies, but only some reproduce the pipeline's returns, and those
    are caught by the Sharpe match on the shared window.
    """
    return trials["lineage"] + "|" + trials["universe"] + "|" + trials["config_id"]


def scope_group(universe: str, window_start: str) -> int:
    """0: Top20 from 2022 (with 2023 out-of-sample meta); 1: Top50 from 2022; 2: other windows."""
    if universe == SCOPE_UNIVERSE and window_start in (SCOPE_START, OOS_START):
        return 0
    if window_start == SCOPE_START:
        return 1
    return 2


def in_top20_2022_scope(universe: pd.Series, window_start: pd.Series) -> pd.Series:
    return (universe == SCOPE_UNIVERSE) & (window_start == SCOPE_START)


def flag_new_configurations(trials: pd.DataFrame, order: Sequence[str]) -> pd.DataFrame:
    """Mark each configuration new, or name the earlier configuration it repeats.

    ``trials`` holds one row per (study, universe, config_id) with columns
    ``study, config_id, universe, window_start, cost_bps, annualized_sharpe``
    and ``identity``.  Studies are processed by scope group, then by their
    position in ``order``.  A row is new unless an earlier-processed study
    holds the same identity or the same stream: window start, universe, cost
    and Sharpe rounded to 1e-9.  Rows inside one study never repeat each other.
    """
    rank = {study: position for position, study in enumerate(order)}
    unknown = sorted(set(trials["study"]) - set(rank))
    if unknown:
        raise ValueError(f"studies missing from the processing order: {unknown}")
    frame = trials.reset_index(drop=True).copy()
    frame["_group"] = [scope_group(u, w) for u, w in zip(frame["universe"], frame["window_start"])]
    frame["_rank"] = frame["study"].map(rank)
    frame["_row"] = np.arange(len(frame))
    frame = frame.sort_values(["_group", "_rank", "_row"], kind="stable").reset_index(drop=True)
    streams = list(
        zip(
            frame["window_start"],
            frame["universe"],
            frame["cost_bps"].astype(float),
            frame["annualized_sharpe"].astype(float).round(SHARPE_DECIMALS),
        )
    )
    labels = (frame["study"] + ":" + frame["config_id"]).tolist()
    identities = frame["identity"].tolist()
    seen_streams: dict[tuple[object, ...], str] = {}
    seen_identities: dict[str, str] = {}
    is_new = np.zeros(len(frame), dtype=bool)
    duplicate_of = [""] * len(frame)
    segments = frame.groupby(["_group", "_rank"], sort=True).indices
    for key in sorted(segments):
        positions = segments[key]
        segment_streams: dict[tuple[object, ...], str] = {}
        segment_identities: dict[str, str] = {}
        for position in positions:
            earlier = seen_identities.get(identities[position]) or seen_streams.get(streams[position])
            if earlier is None:
                is_new[position] = True
            else:
                duplicate_of[position] = earlier
            segment_streams.setdefault(streams[position], labels[position])
            segment_identities.setdefault(identities[position], labels[position])
        for key, label in segment_streams.items():
            seen_streams.setdefault(key, label)
        for key, label in segment_identities.items():
            seen_identities.setdefault(key, label)
    frame[ALL_TRIALS] = is_new
    frame[TOP20_2022_TRIALS] = is_new & in_top20_2022_scope(frame["universe"], frame["window_start"]).to_numpy()
    frame["duplicate_of"] = duplicate_of
    return frame.drop(columns=["_group", "_rank", "_row"])


def scope_summary(sharpes: pd.Series, *, unscored: int, description: str) -> dict[str, object]:
    """Trial count and Sharpe dispersion for one scope."""
    values = pd.to_numeric(sharpes, errors="raise").astype(float)
    if len(values) < 2:
        raise ValueError("a scope needs at least two configurations with a Sharpe ratio")
    std = float(values.std(ddof=1))
    return {
        "n_trials": int(len(values) + unscored),
        "n_with_sharpe": int(len(values)),
        "n_without_sharpe": int(unscored),
        "n_distinct_sharpe_values": int(values.round(SHARPE_DECIMALS).nunique()),
        "sharpe_mean_annualized": float(values.mean()),
        "sharpe_std_annualized": std,
        "sharpe_std_per_period": std / math.sqrt(PERIODS_PER_YEAR),
        "periods_per_year": PERIODS_PER_YEAR,
        "sharpe_std_ddof": 1,
        "filter": description,
    }


def unclassified_report_dirs(report_dirs: Sequence[str], used_dirs: set[str]) -> list[str]:
    """Report directories that are neither a trial source nor declared as holding no new configuration."""
    known = used_dirs | set(NO_NEW_CONFIGURATION_DIRS) | NON_RESEARCH_DIRS
    return sorted(name for name in report_dirs if name not in known)


# --------------------------------------------------------------------------- outputs


def _unscored_in_scope(configuration: UnscoredConfiguration) -> bool:
    return configuration.universe == SCOPE_UNIVERSE and configuration.window_start == SCOPE_START


def _study_status(study: str) -> str:
    if study.startswith("git:"):
        return "git history only"
    if study.startswith("research_md:"):
        return "RESEARCH.md text only"
    return "reports/"


def build_inventory(
    rows: pd.DataFrame,
    flagged: pd.DataFrame,
    unscored: list[UnscoredConfiguration],
    primary: dict[str, float],
    *,
    relisted: int,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for study in PROCESSING_ORDER:
        all_rows = rows[rows["study"] == study]
        scored = flagged[flagged["study"] == study]
        extra = [u for u in unscored if u.study == study]
        if all_rows.empty and not extra:
            continue
        starts = set(scored["window_start"]) | {u.window_start for u in extra}
        ends = set(scored["window_end"]) | {u.window_end for u in extra}
        universes = sorted(set(scored["universe"]) | {u.universe for u in extra})
        in_scope = int(scored[TOP20_2022_TRIALS].sum()) + sum(_unscored_in_scope(u) for u in extra)
        new = int(scored[ALL_TRIALS].sum()) + len(extra)
        sources = sorted(set(all_rows["source"]) | {u.source for u in extra})
        notes = sorted({str(note) for note in all_rows["note"] if note}) if not all_rows.empty else []
        primary_cost = primary.get(study, extra[0].cost_bps if extra else float("nan"))
        records.append(
            {
                "study": study,
                "status": _study_status(study),
                "source": "; ".join(sources),
                "varies": VARIES.get(study, ""),
                "configurations": int(len(scored) + len(extra)),
                "configurations_with_sharpe": int(len(scored)),
                "new_configurations": new,
                "top20_2022_configurations": in_scope,
                "window_start": ";".join(sorted(starts)),
                "window_end": ";".join(sorted(ends)),
                "primary_cost_bps": primary_cost,
                "costs_evaluated_bps": ";".join(_fmt(c) for c in sorted(set(all_rows["cost_bps"]))),
                "universe": ";".join(universes),
                ALL_TRIALS: new > 0,
                TOP20_2022_TRIALS: in_scope > 0,
                "note": "; ".join(notes),
            }
        )
    for directory, reason in NO_NEW_CONFIGURATION_DIRS.items():
        records.append(
            {
                "study": directory,
                "status": "reports/ (no new configuration)",
                "source": f"reports/{directory}/",
                "varies": reason,
                "configurations": relisted if directory == "phase_momentum_multiple_testing_2022" else 0,
                "configurations_with_sharpe": 0,
                "new_configurations": 0,
                "top20_2022_configurations": 0,
                ALL_TRIALS: False,
                TOP20_2022_TRIALS: False,
            }
        )
    return pd.DataFrame(records)


def reimplemented_pipeline_strategies(flagged: pd.DataFrame) -> pd.DataFrame:
    """Pipeline bull-only strategies next to their no-leverage re-implementation on 2021-01-01."""
    pipeline = flagged[flagged["study"] == "pipeline_latest"].set_index("config_id")["annualized_sharpe"]
    ablation = flagged[flagged["study"] == "no_leverage_ablation_v2"].set_index("config_id")["annualized_sharpe"]
    suffix = "__bull_only"
    records = [
        {
            "pipeline": name,
            "ablation": name[: -len(suffix)] + "_bull__none",
            "pipeline_sharpe": float(sharpe),
            "ablation_sharpe": float(ablation[name[: -len(suffix)] + "_bull__none"]),
        }
        for name, sharpe in pipeline.items()
        if str(name).endswith(suffix) and name[: -len(suffix)] + "_bull__none" in ablation.index
    ]
    return pd.DataFrame(records, columns=["pipeline", "ablation", "pipeline_sharpe", "ablation_sharpe"])


def _markdown(frame: pd.DataFrame, index: str) -> str:
    return str(dataframe_to_markdown(frame.set_index(index).astype(str)))


def write_readme(
    output_dir: Path,
    *,
    summary: dict[str, dict[str, object]],
    flagged: pd.DataFrame,
    unscored: list[UnscoredConfiguration],
    anchors: dict[str, bool],
    april_commit: str,
    bull_commit: str,
    head: str,
    uncommitted: list[str],
) -> None:
    totals = pd.DataFrame(
        [
            {
                "scope": scope,
                "trials": f"{stats['n_trials']:,}",
                "with Sharpe": f"{stats['n_with_sharpe']:,}",
                "distinct Sharpe values": f"{stats['n_distinct_sharpe_values']:,}",
                "mean Sharpe": f"{stats['sharpe_mean_annualized']:.4f}",
                "std (annualized)": f"{stats['sharpe_std_annualized']:.4f}",
                "std (per day)": f"{stats['sharpe_std_per_period']:.5f}",
            }
            for scope, stats in summary.items()
        ]
    )
    unscored_frame = pd.DataFrame([u.__dict__ for u in unscored])
    by_family = (
        pd.concat(
            [
                flagged[[ALL_TRIALS, TOP20_2022_TRIALS, "family"]],
                unscored_frame.assign(
                    **{ALL_TRIALS: True, TOP20_2022_TRIALS: [_unscored_in_scope(u) for u in unscored]}
                )[[ALL_TRIALS, TOP20_2022_TRIALS, "family"]],
            ]
        )
        .groupby("family")[[ALL_TRIALS, TOP20_2022_TRIALS]]
        .sum()
        .astype(int)
        .reset_index()
    )
    git_only = flagged[flagged["study"].str.startswith("git:") & flagged[ALL_TRIALS]]
    april = git_only[git_only["study"] != f"git:bull_offense_scan@{bull_commit}"]
    april_best = april.loc[april["annualized_sharpe"].idxmax()] if not april.empty else None
    repeats = flagged[flagged["study"].str.startswith("git:profit_max") & ~flagged[ALL_TRIALS]]
    search_repeats = int((repeats["study"] == "git:profit_max_search").sum())
    refine_files = ", ".join(
        sorted({str(cid).split(":", 1)[0] for cid in repeats.loc[repeats["study"] == "git:profit_max_refine", "config_id"]})
    )
    twins = reimplemented_pipeline_strategies(flagged)
    gaps = (twins["pipeline_sharpe"] - twins["ablation_sharpe"]).abs()
    tolerance = 10.0 ** -SHARPE_DECIMALS
    differing = twins[gaps > tolerance]
    differing_gaps = gaps[gaps > tolerance]
    differing_names = ", ".join(f"`{name}`" for name in differing["pipeline"])
    bull_git = f"git:bull_offense_scan@{bull_commit}"
    levered = int((flagged["study"].eq(bull_git) & flagged[ALL_TRIALS]).sum())
    missing_anchors = [anchor for anchor, found in anchors.items() if not found]
    top = summary[TOP20_2022_TRIALS]
    lines = [
        "# Research Trial Inventory",
        "",
        "Every strategy configuration the project has backtested, built by",
        "`scripts/build_trial_inventory.py`. The multiple-testing diagnostics read",
        "`summary.json`; `trial_sharpes.csv` has one row per configuration and study",
        "and `trial_inventory.csv` one row per study.",
        "",
        f"Built at commit `{head[:7]}`"
        + (
            f" from {len(uncommitted)} uncommitted source file(s): "
            + ", ".join(f"`{name}`" for name in uncommitted)
            + ". `manifest.json` records the SHA-256 of every source."
            if uncommitted else "; every source file is committed."
        ),
        "",
        "## Totals",
        "",
        _markdown(totals, "scope"),
        "",
        f"`{TOP20_2022_TRIALS}` is the comparable pool for the phase-momentum champion: Top20,",
        f"start {SCOPE_START}, cost nearest 20 bps. Its {top['n_with_sharpe']:,} Sharpe ratios come from",
        f"{top['n_distinct_sharpe_values']:,} distinct return streams; configurations inside one study",
        "that happen to give identical returns (liquidity tiers that never bind, stops",
        "that never fire) count separately. The `all_trials` Sharpe dispersion mixes",
        "windows (the April 2022-11-21 studies have Sharpe ratios near 2), so the",
        "multiple-testing script uses it only for the trial count.",
        "",
        "## Conventions",
        "",
        "- A configuration is one set of rules and parameters on one universe. Costs,",
        "  rolling starts, phase offsets and sub-windows are multiplicity, not configurations.",
        "- A study is one report directory. A configuration is new unless it reproduces,",
        "  to 1e-9, the Sharpe of a configuration in an earlier-processed study on the same",
        "  window start, universe and cost, or re-runs the same grid cell on another window",
        "  or data panel (`duplicate_of` in `trial_sharpes.csv` names the earlier one).",
        "- Processing is scope-first (Top20/2022 in research order, then Top50/2022, then",
        "  other windows), so a configuration counts in the Top20/2022 scope whenever it",
        "  was tested there.",
        "- Each study is read at the cost nearest 20 bps at which all its configurations",
        "  ran. `N bps` is fee plus slippage per unit of one-way turnover",
        "  (`src/atlas20/backtest/engine.py`: `fee_rate * sum|dw|`).",
        "- Sharpe ratios are the stored annualized values, sqrt(365) * mean / std with a",
        "  zero risk-free rate. Most runners use ddof=0, some ddof=1 (a 0.03% difference",
        "  over 1,725 days); no conversion is applied.",
        "- Pure buy-and-hold benchmarks are not configurations. The 32 candidates in",
        "  `phase_momentum_multiple_testing_2022/` re-list configurations counted in their",
        "  own studies and are not counted again.",
        "",
        "## By strategy family",
        "",
        _markdown(by_family, "family"),
        "",
        "## Caveats",
        "",
        f"- **Text only.** {sum(u.reason.startswith('RESEARCH.md') for u in unscored)} configurations exist only as RESEARCH.md text:",
        "  the momentum-event BTC-gate and target-volatility neighbourhood of section 0.7",
        "  (no gate; MA50 confirm 1-3; MA100 confirm 1 and 3; MA200 confirm 1-3; 90%/100%",
        "  target vol) and the section 2 trend-stop champion with BTC allowed in selection.",
        f"  {sum(u.reason.startswith('multiples') for u in unscored)} momentum-event neighbours report multiples only. All count as",
        "  trials without a Sharpe ratio."
        + (f" Anchor text no longer found in RESEARCH.md: {missing_anchors}." if missing_anchors else ""),
        "- **Deleted from reports/.** The April profit-max and sector studies were deleted in",
        f"  `9d71d1e` and are read with `git show {april_commit}:...`: {len(april):,} configurations on",
        "  2022-11-21 to 2026-04-21 (old panel), not mentioned in RESEARCH.md. The 11-day /",
        "  2-day BTC gate reused by the later CTREND rules comes from this lane",
        "  (`profit_max_refine/champion_*_stop11_confirm2`)"
        + (
            f"; its best Sharpe is {april_best['annualized_sharpe']:.2f} (`{april_best['study']}`)."
            if april_best is not None else "."
        ),
        f"  The 144-cell bull-offense scan survives only at `{bull_commit}`; its {levered} levered",
        "  cells are no longer in reports/.",
        f"- **Re-implemented pipeline strategies.** The no-leverage ablation re-implements {len(twins)}",
        "  pipeline bull-only strategies as `X_bull__none`. On the shared 2021-01-01 window",
        f"  {int((gaps <= tolerance).sum())} reproduce the pipeline Sharpe exactly and count once;"
        + (
            f" {len(differing)} ({differing_names}) differ by {differing_gaps.min():.2f} to"
            f" {differing_gaps.max():.2f} in Sharpe, so they are different return streams and count"
            " as separate trials."
            if not differing.empty else ""
        ),
        "- **Earlier hand count.** A first inventory (2026-09-24) gave 14,124 configurations",
        f"  overall. It counted every profit-max row as new, but {len(repeats)} reproduce an earlier",
        f"  study's Sharpe exactly ({search_repeats} profit_max_search rows re-list pipeline strategies",
        f"  as benchmarks; {len(repeats) - search_repeats} profit_max_refine rows ({refine_files}) re-run",
        "  profit_max_search cells),",
        f"  and it merged the {len(differing)} differing re-implementations above by name. This build",
        f"  therefore counts {len(repeats)} fewer and {len(differing)} more. The Top20/2022 scope is unaffected.",
        "- **Not verifiable, not counted.** The deleted `scripts/run_profit_max_refine.py`",
        "  defines its own grid, but its summary CSV was never committed; the committed",
        "  refine CSVs came from other code. RESEARCH.md says it replaced earlier `/tmp`",
        "  results that were not kept.",
        "- **Phase momentum design.** No trials are recorded for how the phase-momentum",
        "  design itself was chosen (4 signals, 3 phases, 3-day check, Top2 hold), so the",
        "  phase-momentum count understates the search that produced it.",
        "- **Inferred fields.** The overlay-sweep and CTREND-focus window ends and the",
        "  old-panel screen end are inferred; the cost of `ensemble_ctrend_2022_top50` is not",
        "  recorded (20 bps assumed); the April studies' cost is the 10 + 10 bps preset.",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/research_trial_inventory"))
    parser.add_argument("--april-commit", default=APRIL_COMMIT)
    parser.add_argument("--bull-scan-commit", default=BULL_SCAN_COMMIT)
    parser.add_argument("--research-md", type=Path, default=Path("RESEARCH.md"))
    args = parser.parse_args()

    src = Sources(PROJECT_ROOT)
    rows, unscored, repeated_rows = collect_trials(
        src, april_commit=args.april_commit, bull_commit=args.bull_scan_commit
    )
    research_md_path = args.research_md if args.research_md.is_absolute() else PROJECT_ROOT / args.research_md
    research_text = research_md_path.read_text(encoding="utf-8")
    text_only, anchors = research_md_configurations(research_text)
    unscored = unscored + text_only

    used_dirs = {Path(label).parts[1] for label in src.read if label.startswith("reports/")}
    unclassified = unclassified_report_dirs(src.report_dirs(), used_dirs)
    if unclassified:
        raise ValueError(
            "report directories not in the trial inventory: "
            f"{unclassified}; add them as a study or to NO_NEW_CONFIGURATION_DIRS"
        )

    primary = primary_costs(rows)
    at_primary = rows[(rows["cost_bps"] == rows["study"].map(primary)) & ~rows["benchmark"]].copy()
    at_primary["identity"] = assign_identities(at_primary)
    flagged = flag_new_configurations(at_primary, PROCESSING_ORDER)

    unscored_in_scope = [u for u in unscored if _unscored_in_scope(u)]
    summary = {
        ALL_TRIALS: scope_summary(
            flagged.loc[flagged[ALL_TRIALS], "annualized_sharpe"],
            unscored=len(unscored),
            description=(
                "trial_sharpes.csv rows with all_trials == True (one row per configuration at its study's "
                "primary cost; pure buy-and-hold benchmarks and re-listings excluded; new = no earlier-processed "
                "study has the same identity or the same window_start/universe/cost/Sharpe rounded to 1e-9), "
                "plus configurations without a Sharpe (trial_inventory.csv)"
            ),
        ),
        TOP20_2022_TRIALS: scope_summary(
            flagged.loc[flagged[TOP20_2022_TRIALS], "annualized_sharpe"],
            unscored=len(unscored_in_scope),
            description=(
                "all_trials rows with universe == 'Top20' and window_start == '2022-01-01' "
                "(top20_2022_trials == True), plus configurations without a Sharpe in that scope"
            ),
        ),
    }

    output_dir = ensure_dir(args.output_dir)
    columns = [
        "study", "config_id", "annualized_sharpe", "window_start", "window_end", "cost_bps", "universe",
        ALL_TRIALS, TOP20_2022_TRIALS, "duplicate_of", "family", "source", "source_column", "note",
    ]
    flagged[columns].to_csv(output_dir / "trial_sharpes.csv", index=False)
    relisted = len(src.csv("reports/phase_momentum_multiple_testing_2022/candidate_sharpes.csv"))
    inventory = build_inventory(rows, flagged, unscored, primary, relisted=relisted)
    inventory.to_csv(output_dir / "trial_inventory.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest = {
        "script": "scripts/build_trial_inventory.py",
        "repository_head": src.git("rev-parse", "HEAD").decode().strip(),
        "april_commit": args.april_commit,
        "april_commit_resolved": src.git("rev-parse", args.april_commit).decode().strip(),
        "bull_scan_commit": args.bull_scan_commit,
        "bull_scan_commit_resolved": src.git("rev-parse", args.bull_scan_commit).decode().strip(),
        "research_md": str(args.research_md),
        "research_md_sha256": hashlib.sha256(research_text.encode("utf-8")).hexdigest(),
        "research_md_anchors_found": anchors,
        "reference_cost_bps": REFERENCE_COST_BPS,
        "sharpe_decimals": SHARPE_DECIMALS,
        "periods_per_year": PERIODS_PER_YEAR,
        "scope_top20_2022": {"universe": SCOPE_UNIVERSE, "window_start": SCOPE_START},
        "processing_order": list(PROCESSING_ORDER),
        "study_primary_cost_bps": primary,
        "rows_read": int(len(rows)),
        "rows_at_primary_cost": int(len(flagged)),
        "repeated_rows_skipped": int(repeated_rows),
        "unscored_configurations": [u.__dict__ for u in unscored],
        "sources": dict(sorted(src.read.items())),
        "outputs": ["trial_inventory.csv", "trial_sharpes.csv", "summary.json", "manifest.json", "README.md"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    write_readme(
        output_dir,
        summary=summary,
        flagged=flagged,
        unscored=unscored,
        anchors=anchors,
        april_commit=args.april_commit,
        bull_commit=args.bull_scan_commit,
        head=manifest["repository_head"],
        uncommitted=sorted(
            label for label, info in src.read.items() if info["origin"] in UNCOMMITTED_ORIGINS
        ),
    )
    for scope, stats in summary.items():
        print(
            f"{scope}: n_trials={stats['n_trials']} n_with_sharpe={stats['n_with_sharpe']} "
            f"mean={stats['sharpe_mean_annualized']:.4f} std={stats['sharpe_std_annualized']:.4f}"
        )
    print(f"Wrote trial inventory to {output_dir}")


if __name__ == "__main__":
    main()
