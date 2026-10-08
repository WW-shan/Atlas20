"""Pre-registered 2026-10 hypotheses H2-H4 for the phase-momentum champion.

The rules, parameters, kill criteria and outcome tiers are fixed in
``docs/research/literature_review_2026-09.md`` section 4 (H1 is not run: it
needs the owner's sign-off on the "signals at the close" rule).  Nothing here
is tuned: every trial is registered in the append-only ledger
``reports/research_trial_inventory/preregistered_trials.csv`` before it runs,
the runner refuses a trial whose registered rules or spec differ from the
code, and results are appended to the ledger instead of rewriting it.

Trials (all strict point-in-time Top20, long-only spot, gross <= 1):

* B   - the champion (``PhaseMomentumSpec`` defaults, ``PRIMARY_SIGNAL_SPECS``)
        rerun in this harness; the baseline, not a new trial.
* H2  - equal-weight ensemble of the MA50/100/150/200 BTC gates.
* H3  - 50/50 blend of the champion and the champion with the Top20 breadth
        co-gate (breadth >= 0.50), formed at the target level: 24 sleeves
        at 1/24 each, executed and charged by the production engine.
* H4  - top-quintile sleeves: 4 coins per sleeve, top-8 hold band.
* H2 diagnostics - the four single-window gates (MA50/100/150/200) at +3h;
        never promotable.

Common protocol (review section 4.0): 2022-01-01 to 2026-09-21; 2, 20, 50 and
100 bps; fills at lag 0, lag 1 day and +3 hours after the signal close under
both missing-candle policies, deciding on the worse one; the 2020-10 to
2021-12 stress window at lag 0 and lag 1 only.  Deflated Sharpe, White Reality
Check and the terminal-wealth bootstrap reuse
``scripts/run_phase_momentum_multiple_testing.py`` and its settings.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.backtest.engine import BacktestResult  # noqa: E402
from atlas20.backtest.intraday import (  # noqa: E402
    MISSING_FILL_POLICIES,
    load_hourly_bars,
    observed_fill_mask,
    pre_fill_returns,
)
from atlas20.config import ResearchConfig  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.regime import build_regime_frame  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PRIMARY_SIGNAL_SPECS,
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    build_parameter_ensemble_targets,
    build_phase_momentum_targets,
    parameter_ensemble_sleeve_weights,
)
from atlas20.universe.builder import MarketDataBundle, build_rebalance_universe  # noqa: E402

from scripts.run_phase_momentum import (  # noqa: E402
    _load_market,
    _production_result,
    _rolling_worst,
    _yearly_returns,
)
from scripts.run_phase_momentum_execution_lag import _observed_weight_share  # noqa: E402
from scripts.run_phase_momentum_multiple_testing import (  # noqa: E402
    COMPARABLE_SCOPE,
    _dedupe_identical_columns,
    _deflated_sharpe,
    _expected_max_sharpe,
    _project_scopes,
    _reality_check,
    _require_common_sample,
    _stationary_bootstrap_indices,
)
from scripts.run_phase_momentum_regime_breakdown import (  # noqa: E402
    _lagged_regime_labels,
    _regime_table,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

REVIEW = "docs/research/literature_review_2026-09.md"
DEFAULT_LEDGER = Path("reports/research_trial_inventory/preregistered_trials.csv")
DEFAULT_OUTPUT = Path("reports/phase_momentum_hypotheses_2026_10")
MAIN_WINDOW = ("2022-01-01", "2026-09-21")
STRESS_WINDOW = ("2020-10-03", "2021-12-31")
COSTS = (2.0, 20.0, 50.0, 100.0)
DECISION_COST = 20.0
DIRECTION_COSTS = (2.0, 50.0)
FILL_HOURS = 3
LAG_FILLS = {"lag0": 0, "lag1": 1}
HOUR_FILLS = {f"h{FILL_HOURS}_{policy}": policy for policy in MISSING_FILL_POLICIES}
MAIN_FILLS = (*LAG_FILLS, *HOUR_FILLS)
# The project's existing bootstrap settings (run_phase_momentum_multiple_testing.py defaults).
BOOTSTRAP_COUNT = 1000
BOOTSTRAP_BLOCK = 20
BOOTSTRAP_SEED = 20260923
ENTRANT_DAYS = 30
MEMBERSHIP_LOOKBACK_DAYS = 60
MDD_IMPROVEMENT = 0.05
MDD_TOLERANCE = 0.02
CHAMPION_D1D = 0.52
TARGET_MULTIPLE = 20.0
DSR_PASS = 0.95

LEDGER_COLUMNS = [
    "trial_id",
    "hypothesis",
    "role",
    "counts_as_trial",
    "rule",
    "kill_criterion",
    "spec",
    "spec_sha256",
    "parameters_sources",
    "protocol",
    "deviation_notes",
    "registered_at_utc",
    "registration_sha256",
    "status",
    "recorded_at_utc",
    "result_path",
    "result",
]
REGISTRATION_FIELDS = (
    "trial_id",
    "hypothesis",
    "role",
    "counts_as_trial",
    "rule",
    "kill_criterion",
    "spec",
    "parameters_sources",
    "protocol",
    "deviation_notes",
)

PROTOCOL = (
    "Review section 4.0. Window 2022-01-01..2026-09-21 on data/processed/panel_daily.csv with strict point-in-time "
    "CMC Top20 (scripts/run_phase_momentum.py::_load_market); stress window 2020-10-03..2021-12-31 at lag 0 and "
    "lag 1 only. Costs 2/20/50/100 bps (fee_bps = cost, slippage 0: the engine's cost per unit of one-way "
    "turnover). Fills: lag 0 (signal close), lag 1 day, and +3h = the close of the Binance 1h candle opening "
    "02:00 UTC (atlas20.backtest.intraday.pre_fill_returns, fill_hours=3, 5% open-gap check) under both "
    "missing-candle policies day_close and prior_close. Worse policy: for each trial and cost, the policy with "
    "the lower terminal multiple; all of that trial's metrics at that cost are read under it. D3h = M(+3h worse) "
    "/ M(lag 0) and D1d = M(lag 1) / M(lag 0) at the same cost. Kill criteria are evaluated at 20 bps with +3h "
    "fills (worse policy) and repeated at 2 and 50 bps; a pass needs the same verdict at all three; 100 bps is "
    "reported. Deflated Sharpe with run_phase_momentum_multiple_testing.py (_deflated_sharpe, "
    "_expected_max_sharpe, scopes top20_2022_trials and all_trials of reports/research_trial_inventory/"
    "summary.json, which counts this ledger's counted trials) on the 20 bps +3h worse-policy daily returns; the "
    "tier uses top20_2022_trials. White Reality Check: stationary bootstrap (_stationary_bootstrap_indices, "
    "1000 draws, block 20, seed 20260923) over every return series of this round at that setting, vs zero and vs "
    "BTC buy-and-hold, with single-step p-values per trial (the best trial's p equals _reality_check). "
    "Terminal-wealth ratio vs B: paired stationary bootstrap with the same settings. Also reported: CAGR, "
    "Sharpe, MDD, one-year rolling worst/median multiple, yearly returns, lagged bull/non-bull split "
    "(run_phase_momentum_regime_breakdown.py), multiple without the best calendar year, turnover, and the "
    "entrant attribution (daily per-coin contributions of the engine's book, classed at the signal date as "
    "entrant = inside a Top20 membership spell that began at most 29 days earlier, incumbent = older spell, "
    "non_member = held while outside that day's Top20). Tiers (review 4.0): rejected if the kill criterion fails; "
    "tier 3 (champion candidate) only with M >= 20 at 20 bps +3h worse policy, DSR >= 0.95 and every AGENTS.md "
    "gate (the gates beyond this script are not run in this round); otherwise a pass is tier 2 (risk variant "
    "recorded)."
)


@dataclass(frozen=True)
class Trial:
    """One ledger entry: rules, spec and role of a pre-registered run."""

    trial_id: str
    hypothesis: str
    role: str
    counts_as_trial: bool
    books: tuple[tuple[PhaseMomentumSpec, float], ...]
    rule: str
    kill_criterion: str
    parameters_sources: str
    deviation_notes: str
    fills: tuple[str, ...]
    stress: bool


CHAMPION_RULE = (
    "Champion: PhaseMomentumSpec defaults (3-day checks in phases 0/1/2; incumbent kept while in the sleeve's "
    "Top2 and replaced only at its check; immediate exit when it leaves the day's Top20; BTC close >= its 100D SMA "
    "with 2-day confirmation, fail-closed after warm-up; 80% target volatility on 60D realised volatility, capped "
    "at 1; weight tolerance 0.05) x PRIMARY_SIGNAL_SPECS (4 signals) = 12 single-coin sleeves at 1/12 each, "
    "executed by the production engine."
)


def _single_window(window: int) -> Trial:
    return Trial(
        trial_id=f"PR2026-10-H2-D{window}",
        hypothesis="H2 diagnostic",
        role="diagnostic",
        counts_as_trial=False,
        books=((PhaseMomentumSpec(btc_ma_window=window), 1.0),),
        rule=(
            f"Declared H2 diagnostic: the champion with the single BTC gate window MA{window} (2-day "
            "confirmation), rerun at +3h under both missing-candle policies at 2/20/50/100 bps. Never promotable."
            + (" Same spec as the champion (B)." if window == 100 else "")
        ),
        kill_criterion="none (diagnostic; enters the H2 kill criterion as one of the four single-window variants)",
        parameters_sources=(
            "Review section 4 H2 'Test': the four single-window variants, already in the ledger at lag 0 "
            "(reports/phase_momentum_2022/parameter_neighborhood.csv: btc_ma_50/150/200 and the primary)."
        ),
        deviation_notes="none; re-run of an existing configuration at +3h, not a new trial",
        fills=tuple(HOUR_FILLS),
        stress=False,
    )


TRIALS: tuple[Trial, ...] = (
    Trial(
        trial_id="PR2026-10-B",
        hypothesis="baseline",
        role="baseline",
        counts_as_trial=False,
        books=((PhaseMomentumSpec(), 1.0),),
        rule=CHAMPION_RULE + " Baseline B of review section 4.0, rerun in this harness with the same fill rules.",
        kill_criterion="none (baseline)",
        parameters_sources="RESEARCH.md champion; reports/phase_momentum_2022 (23.09x at 20 bps, lag 0).",
        deviation_notes="none; re-run of the champion, not a new trial",
        fills=MAIN_FILLS,
        stress=True,
    ),
    Trial(
        trial_id="PR2026-10-H2",
        hypothesis="H2",
        role="primary",
        counts_as_trial=True,
        books=((PhaseMomentumSpec(btc_ma_windows=(50, 100, 150, 200)), 1.0),),
        rule=(
            "H2 ensemble of BTC gate windows: the MA100 gate is replaced by the equal-weight average of four gates; "
            "gate k is on when BTC's close is at or above its w_k-day SMA with the champion's 2-day confirmation and "
            "fail-closed-after-warm-up rule, w_k in {50, 100, 150, 200}; g(D) = gates on / 4 in {0, .25, .5, .75, 1}; "
            "each sleeve's target weight = g(D) x min(1, 0.80 / sigma60) (the 0.05 weight tolerance applies to that "
            "weight); g(D) = 0 sends the sleeves to cash with the champion's risk-off reset (re-entry at rank 1 once "
            "g > 0); selection otherwise exactly as the champion. Spec: PhaseMomentumSpec(btc_ma_windows=(50, 100, "
            "150, 200))."
        ),
        kill_criterion=(
            "Reject if, at 20 bps with +3h fills (worse policy), M(H2) < median of M(single-window MA50/100/150/200) "
            "under the same settings (each at its own worse policy), or MDD(H2) < MDD(B) - 0.02. Same verdict "
            "required at 2 and 50 bps. A pass below 20x is recorded as a risk variant (RESEARCH.md then states that "
            "the champion's 20x depends on the MA100 window). Neighbourhood if it passes: the four "
            "leave-one-window-out ensembles (not run in this round)."
        ),
        parameters_sources=(
            "Window set = the gate windows already in the champion's neighbourhood (parameter_neighborhood.csv); "
            "equal weights: [S17] ensemble construction and RESEARCH.md section 0.6; confirmation = champion's."
        ),
        deviation_notes="none",
        fills=MAIN_FILLS,
        stress=True,
    ),
    Trial(
        trial_id="PR2026-10-H3",
        hypothesis="H3",
        role="primary",
        counts_as_trial=True,
        books=(
            (PhaseMomentumSpec(), 0.5),
            (PhaseMomentumSpec(breadth_threshold=0.50, breadth_ma_window=50), 0.5),
        ),
        rule=(
            "H3 Top20 breadth co-gate, 50/50 blend. Book A = the champion (12 sleeves). Book B = the champion with "
            "the extra risk-on condition breadth(D) >= 0.50, breadth(D) = share of the point-in-time Top20 on D whose "
            "close is above its own 50-day SMA (coins without 50 days count as not above; _breadth_signal of "
            "scripts/run_momentum_event_breadth_overlay.py, copied verbatim as "
            "atlas20.strategies.phase_momentum.top20_breadth), no confirmation on breadth (as section 0.8); when "
            "the condition fails book B's sleeves go to cash with the risk-off reset. Portfolio 50% A + 50% B at the "
            "target level: all 24 sleeves aggregated at 1/24 each (build_parameter_ensemble_targets) and executed "
            "by the production engine."
        ),
        kill_criterion=(
            "Reject unless, at 20 bps with +3h fills (worse policy), all hold: MDD(H3) - MDD(B) >= 0.05, "
            "Sharpe(H3) > Sharpe(B), one-year rolling worst multiple(H3) > B's. Same verdict required at 2 and "
            "50 bps. A pass below 20x is a recorded risk variant. Neighbourhood if it passes: thresholds 0.45 and "
            "0.55 (not run in this round)."
        ),
        parameters_sources=(
            "50-day average, 0.50 threshold and 50/50 mix unchanged from the RESEARCH.md section 0.8 ablation "
            "(reports/momentum_event_breadth_overlay_2022; chosen there from a 5-point threshold grid and a 3-point "
            "mix grid already in the ledger)."
        ),
        deviation_notes=(
            "The review says 'rebalanced to 50/50 daily as in section 0.8'. Section 0.8 re-equalised the two books' "
            "daily returns without charging the trades (flagged as a free-rebalancing bug). Here the blend is formed "
            "at the target level: the production engine rebalances the whole book toward 50/50 at every target "
            "event (not daily) and charges that turnover at the run's cost; between events the two books drift."
        ),
        fills=MAIN_FILLS,
        stress=True,
    ),
    Trial(
        trial_id="PR2026-10-H4",
        hypothesis="H4",
        role="primary",
        counts_as_trial=True,
        books=((PhaseMomentumSpec(holdings_per_sleeve=4, hold_rank=8), 1.0),),
        rule=(
            "H4 top-quintile sleeves: each of the 12 sleeves targets the top 4 coins by its signal at each scheduled "
            "check; an incumbent is kept while it ranks in the top 8; empty slots are filled from the highest-ranked "
            "coins not already held; a coin that leaves the day's Top20 is sold at once and its slot refilled from "
            "that day's ranking; each held coin gets 1/4 of the sleeve's capital x min(1, 0.80 / its 60-day "
            "realised volatility). Gate, phases, 3-day checks, costs and the cap of 1 unchanged. Spec: "
            "PhaseMomentumSpec(holdings_per_sleeve=4, hold_rank=8)."
        ),
        kill_criterion=(
            "Reject unless, at 20 bps with +3h fills (worse policy), MDD(H4) - MDD(B) >= 0.05 and D1d(H4) > the "
            "champion's D1d, read as D1d(H4) > max(0.52, D1d(B) in this harness at the same cost). Same verdict "
            "required at 2 and 50 bps. A pass below 20x is a recorded risk variant. Neighbourhood if it passes: "
            "N = 3 with a top-6 band and N = 5 with a top-10 band (not run in this round)."
        ),
        parameters_sources=(
            "N = 4: top-quintile convention of cross-sectional crypto momentum ([S2], [S4], [S14]) applied to 20 "
            "coins; band = top two quintiles (8) keeps the champion's 1:2 entry/hold ratio (in-project choice on a "
            "narrow peak, disclosed in review section 3.2)."
        ),
        deviation_notes=(
            "Implementation choices the review leaves open, fixed here before running: (1) the champion's 0.05 "
            "weight tolerance applies to each coin's share of the sleeve's capital (1/4 x its volatility scaling), "
            "and any change of the held set is an event; (2) empty slots - at entry, after the risk-off reset and "
            "after an exit - are filled on any risk-on day, as the champion fills an empty sleeve; (3) the D1d "
            "threshold is read as max(0.52, D1d(B) in this harness)."
        ),
        fills=MAIN_FILLS,
        stress=True,
    ),
    *(_single_window(window) for window in (50, 100, 150, 200)),
)
PRIMARY_IDS = {"H2": "PR2026-10-H2", "H3": "PR2026-10-H3", "H4": "PR2026-10-H4"}
BASELINE_ID = "PR2026-10-B"
H2_DIAGNOSTIC_IDS = tuple(f"PR2026-10-H2-D{window}" for window in (50, 100, 150, 200))


def trial_by_id(trial_id: str) -> Trial:
    for trial in TRIALS:
        if trial.trial_id == trial_id:
            return trial
    raise KeyError(trial_id)


# --------------------------------------------------------------------------- ledger


class UnregisteredTrialError(RuntimeError):
    """A trial is missing from the ledger or differs from its registration."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def trial_spec(trial: Trial) -> dict[str, object]:
    """The exact construction a trial runs, as JSON-ready data."""
    return {
        "construction": "build_phase_momentum_targets"
        if len(trial.books) == 1
        else "build_parameter_ensemble_targets (equal book weights, 1/24 per sleeve)",
        "books": [
            {"weight": float(weight), "spec": json.loads(json.dumps(asdict(spec)))}
            for spec, weight in trial.books
        ],
        "signals": [
            {"name": signal.name, "window_weights": [[int(w), float(x)] for w, x in signal.window_weights]}
            for signal in PRIMARY_SIGNAL_SPECS
        ],
        "include_btc": True,
        "universe": "strict point-in-time CMC Top20",
        "fills": list(trial.fills),
        "costs_bps": list(COSTS),
        "stress_window": list(STRESS_WINDOW) if trial.stress else None,
        "main_window": list(MAIN_WINDOW),
    }


def ledger_registration_row(trial: Trial, *, now: str) -> dict[str, str]:
    spec = _canonical(trial_spec(trial))
    row = {
        "trial_id": trial.trial_id,
        "hypothesis": trial.hypothesis,
        "role": trial.role,
        "counts_as_trial": str(bool(trial.counts_as_trial)),
        "rule": trial.rule,
        "kill_criterion": trial.kill_criterion,
        "spec": spec,
        "spec_sha256": _sha256(spec),
        "parameters_sources": trial.parameters_sources,
        "protocol": PROTOCOL,
        "deviation_notes": trial.deviation_notes,
        "registered_at_utc": now,
        "status": "registered",
        "recorded_at_utc": now,
        "result_path": "",
        "result": "",
    }
    row["registration_sha256"] = _sha256(_canonical([row[field] for field in REGISTRATION_FIELDS]))
    return row


def read_ledger(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != LEDGER_COLUMNS:
        raise ValueError(f"{path}: unexpected ledger columns {list(frame.columns)}")
    return frame


def append_ledger_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Append rows; the file is never rewritten (registrations stay as written)."""
    new_file = not path.exists()
    if not new_file:
        with open(path, encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle))
        if header != LEDGER_COLUMNS:
            raise ValueError(f"{path}: unexpected ledger header {header}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        if new_file:
            writer.writeheader()
        for row in rows:
            unknown = set(row) - set(LEDGER_COLUMNS)
            if unknown:
                raise ValueError(f"unknown ledger fields {sorted(unknown)}")
            writer.writerow({column: row.get(column, "") for column in LEDGER_COLUMNS})


def _registrations(ledger: pd.DataFrame, trial_id: str) -> pd.DataFrame:
    return ledger[(ledger["trial_id"] == trial_id) & (ledger["status"] == "registered")]


def require_registered(ledger: pd.DataFrame, trial: Trial) -> None:
    """Refuse to run a trial that is not registered exactly as the code defines it."""
    rows = _registrations(ledger, trial.trial_id)
    if rows.empty:
        raise UnregisteredTrialError(f"{trial.trial_id} is not registered in the pre-registration ledger")
    if len(rows) > 1:
        raise UnregisteredTrialError(f"{trial.trial_id} is registered more than once")
    registered = rows.iloc[0]
    expected = ledger_registration_row(trial, now=str(registered["registered_at_utc"]))
    if registered["spec_sha256"] != expected["spec_sha256"]:
        raise UnregisteredTrialError(f"{trial.trial_id}: the spec changed after registration")
    stored = _sha256(_canonical([str(registered[field]) for field in REGISTRATION_FIELDS]))
    if registered["registration_sha256"] != expected["registration_sha256"] or stored != expected["registration_sha256"]:
        raise UnregisteredTrialError(f"{trial.trial_id}: the registered rules changed after registration")


def register_trials(
    path: Path,
    trials: tuple[Trial, ...],
    *,
    now: str,
    existing: pd.DataFrame | None = None,
) -> int:
    """Append a registration row for each trial not yet registered; never modify one."""
    ledger = read_ledger(path) if existing is None else existing
    rows: list[dict[str, str]] = []
    for trial in trials:
        if not _registrations(ledger, trial.trial_id).empty:
            require_registered(ledger, trial)
            continue
        rows.append(ledger_registration_row(trial, now=now))
    if rows:
        append_ledger_rows(path, rows)
    return len(rows)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- building and running


def build_trial(
    trial: Trial,
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
) -> PhaseMomentumBuildResult:
    if len(trial.books) == 1:
        return build_phase_momentum_targets(market, universe, index, spec=trial.books[0][0])
    weights = {float(weight) for _, weight in trial.books}
    if len(weights) != 1 or abs(sum(weight for _, weight in trial.books) - 1.0) > 1e-12:
        raise ValueError(f"{trial.trial_id}: multi-book trials must have equal book weights summing to 1")
    specs = tuple(spec for spec, _ in trial.books)
    sleeve_weights = parameter_ensemble_sleeve_weights(specs, signal_count=len(PRIMARY_SIGNAL_SPECS))
    if len(set(sleeve_weights)) != 1:
        raise ValueError(f"{trial.trial_id}: every sleeve must carry the same weight")
    return build_parameter_ensemble_targets(market, universe, index, parameter_specs=specs)


def entrant_classes(member: pd.DataFrame, *, window_days: int = ENTRANT_DAYS) -> pd.DataFrame:
    """Per date and coin: 'entrant' (spell began < window_days ago), 'incumbent' or 'non_member'."""
    member = member.fillna(False).astype(bool).sort_index()
    starts = pd.DataFrame(pd.NaT, index=member.index, columns=member.columns, dtype="datetime64[ns]")
    dates = pd.Series(member.index, index=member.index)
    for coin in member.columns:
        flags = member[coin]
        new_spell = flags & ~flags.shift(1, fill_value=False)
        starts[coin] = dates.where(new_spell).ffill().where(flags)
    age = (pd.DataFrame({coin: member.index for coin in member.columns}, index=member.index) - starts)
    days = age.apply(lambda column: column.dt.days)
    classes = pd.DataFrame("non_member", index=member.index, columns=member.columns, dtype=object)
    classes = classes.mask(member & (days < window_days), "entrant")
    classes = classes.mask(member & (days >= window_days), "incumbent")
    return classes


def membership_panel(
    config: ResearchConfig,
    market: MarketDataBundle,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Point-in-time Top20 membership from 60 days before the window to its end."""
    first = pd.Timestamp(index.min())
    pre_dates = [
        date
        for date in market.price.index
        if first - pd.Timedelta(days=MEMBERSHIP_LOOKBACK_DAYS) <= date < first
    ]
    frames = [universe[["rebalance_date", "coin_id"]]]
    if pre_dates:
        frames.insert(0, build_rebalance_universe(market, pre_dates, config)[["rebalance_date", "coin_id"]])
    combined = pd.concat(frames, ignore_index=True)
    combined["rebalance_date"] = pd.to_datetime(combined["rebalance_date"]).dt.normalize()
    member = (
        combined.assign(member=True)
        .pivot_table(index="rebalance_date", columns="coin_id", values="member", aggfunc="any")
        .reindex(columns=market.returns.columns)
    )
    full = pd.date_range(member.index.min(), pd.Timestamp(index.max()), freq="D")
    return member.reindex(full).fillna(False).astype(bool)


def entrant_attribution(
    result: BacktestResult,
    asset_returns: pd.DataFrame,
    classes: pd.DataFrame,
    *,
    fill_split: pd.DataFrame | None,
) -> dict[str, float]:
    """Sum of daily per-coin contributions by entrant class, from the engine's book.

    Mirrors the engine's accounting: on a day that follows a target, the book
    held overnight earns the move to the fill and the new target the rest of
    the day; otherwise the drifted book earns the day's return.  A return on
    day t is classed with the membership of the signal date t-1.
    """
    dates = pd.DatetimeIndex(asset_returns.index)
    columns = asset_returns.columns
    returns = asset_returns.reindex(columns=columns).to_numpy(dtype=float)
    returns = np.nan_to_num(returns, nan=0.0)
    split = None
    if fill_split is not None:
        split = fill_split.reindex(index=dates, columns=columns).to_numpy(dtype=float)
        split = np.where(np.isfinite(split), split, returns)
    end_weights = result.weights.reindex(index=dates, columns=columns).fillna(0.0).to_numpy(dtype=float)
    targets = result.rebalance_targets.reindex(columns=columns).fillna(0.0)
    class_frame = classes.reindex(index=dates, columns=columns).fillna("non_member").to_numpy(dtype=object)
    totals = {"entrant": 0.0, "incumbent": 0.0, "non_member": 0.0}
    previous = np.zeros(len(columns))
    for position, date in enumerate(dates):
        if position == 0:
            previous = end_weights[position]
            continue
        signal_date = dates[position - 1]
        day = returns[position]
        if signal_date in targets.index:
            new = targets.loc[signal_date].to_numpy(dtype=float)
            if split is not None:
                part = split[position]
                denominator = 1.0 + part
                safe = np.where(denominator > 0.0, denominator, 1.0)
                remaining = np.where(denominator > 0.0, (1.0 + day) / safe - 1.0, day)
                contribution = previous * part + new * remaining
            else:
                contribution = new * day
        else:
            contribution = previous * day
        labels = class_frame[position - 1]
        for label in totals:
            totals[label] += float(contribution[labels == label].sum())
        previous = end_weights[position]
    gross = sum(totals.values())
    return {
        **{f"{label}_contribution": value for label, value in totals.items()},
        **{f"{label}_share": (value / gross if gross else float("nan")) for label, value in totals.items()},
    }


def run_metrics(returns: pd.Series, result: BacktestResult | None = None) -> dict[str, object]:
    metrics: dict[str, object] = {**_metrics_from_returns(returns), **_rolling_worst(returns)}
    yearly = _yearly_returns(returns)
    best_year = int(yearly.idxmax().year) if not yearly.empty else None
    remaining = returns[returns.index.year != best_year] if best_year is not None else returns
    metrics.update(
        {
            "best_year": best_year,
            "best_year_return": float(yearly.max()) if not yearly.empty else float("nan"),
            "best_year_removed_multiple": float((1.0 + remaining).prod()),
            "days": int(len(returns)),
        }
    )
    if result is not None:
        years = max(len(returns) / 365.0, 1e-9)
        metrics["turnover_total"] = float(result.turnover.sum())
        metrics["turnover_annual"] = float(result.turnover.sum() / years)
        metrics["avg_gross_exposure"] = float(result.weights.sum(axis=1).mean())
    return metrics


# --------------------------------------------------------------------------- decision and statistics


def worse_policy_row(runs: pd.DataFrame, trial_id: str, cost: float) -> pd.Series:
    """The +3h run with the lower terminal multiple (ties: alphabetical fill)."""
    rows = runs[
        (runs["trial_id"] == trial_id)
        & (runs["window"] == "main")
        & (runs["fill"].isin(tuple(HOUR_FILLS)))
        & (runs["cost_bps"] == float(cost))
    ]
    if len(rows) != len(HOUR_FILLS):
        raise ValueError(f"{trial_id} at {cost:g} bps needs one +{FILL_HOURS}h run per missing-candle policy")
    return rows.sort_values(["multiple", "fill"], kind="mergesort").iloc[0]


def _fill_row(runs: pd.DataFrame, trial_id: str, fill: str, cost: float) -> pd.Series | None:
    rows = runs[
        (runs["trial_id"] == trial_id)
        & (runs["window"] == "main")
        & (runs["fill"] == fill)
        & (runs["cost_bps"] == float(cost))
    ]
    return rows.iloc[0] if len(rows) == 1 else None


def decision_table(runs: pd.DataFrame, trial_ids: list[str], cost: float) -> pd.DataFrame:
    """Metrics at +3h (worse policy) with the delay ratios, one row per trial."""
    rows: list[dict[str, object]] = []
    for trial_id in trial_ids:
        worse = worse_policy_row(runs, trial_id, cost)
        lag0 = _fill_row(runs, trial_id, "lag0", cost)
        lag1 = _fill_row(runs, trial_id, "lag1", cost)
        m_lag0 = float(lag0["multiple"]) if lag0 is not None else float("nan")
        m_lag1 = float(lag1["multiple"]) if lag1 is not None else float("nan")
        rows.append(
            {
                "trial_id": trial_id,
                "cost_bps": float(cost),
                "worse_policy": str(worse["fill"]),
                **{
                    column: worse[column]
                    for column in worse.index
                    if column not in {"trial_id", "cost_bps", "fill", "window"}
                },
                "multiple_lag0": m_lag0,
                "multiple_lag1": m_lag1,
                "d3h": float(worse["multiple"]) / m_lag0 if np.isfinite(m_lag0) and m_lag0 else float("nan"),
                "d1d": m_lag1 / m_lag0 if np.isfinite(m_lag0) and m_lag0 else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _criteria(hypothesis: str, runs: pd.DataFrame, cost: float) -> tuple[bool, list[str]]:
    table = decision_table(
        runs,
        [BASELINE_ID, PRIMARY_IDS[hypothesis]]
        + (list(H2_DIAGNOSTIC_IDS) if hypothesis == "H2" else []),
        cost,
    ).set_index("trial_id")
    base = table.loc[BASELINE_ID]
    hyp = table.loc[PRIMARY_IDS[hypothesis]]
    checks: list[tuple[str, bool]] = []
    if hypothesis == "H2":
        median = float(np.median([float(table.loc[trial, "multiple"]) for trial in H2_DIAGNOSTIC_IDS]))
        checks.append(
            (f"M(H2)={hyp['multiple']:.4f} >= median single-window M={median:.4f}", float(hyp["multiple"]) >= median)
        )
        floor = float(base["max_drawdown"]) - MDD_TOLERANCE
        checks.append(
            (
                f"MDD(H2)={hyp['max_drawdown']:.4f} >= MDD(B)-0.02={floor:.4f}",
                float(hyp["max_drawdown"]) >= floor,
            )
        )
    else:
        improvement = float(hyp["max_drawdown"]) - float(base["max_drawdown"])
        checks.append(
            (
                f"MDD improvement {improvement * 100:.2f} pp >= 5 pp "
                f"(MDD {hyp['max_drawdown']:.4f} vs B {base['max_drawdown']:.4f})",
                improvement >= MDD_IMPROVEMENT - 1e-12,
            )
        )
        if hypothesis == "H3":
            checks.append(
                (f"Sharpe {hyp['sharpe']:.4f} > B {base['sharpe']:.4f}", float(hyp["sharpe"]) > float(base["sharpe"]))
            )
            checks.append(
                (
                    f"rolling 1y worst {hyp['rolling_1y_worst_multiple']:.4f} > B "
                    f"{base['rolling_1y_worst_multiple']:.4f}",
                    float(hyp["rolling_1y_worst_multiple"]) > float(base["rolling_1y_worst_multiple"]),
                )
            )
        else:
            threshold = max(CHAMPION_D1D, float(base["d1d"]))
            checks.append(
                (
                    f"D1d {hyp['d1d']:.4f} > max(0.52, D1d(B)={base['d1d']:.4f})",
                    float(hyp["d1d"]) > threshold,
                )
            )
    return all(passed for _, passed in checks), [f"{text}: {'pass' if passed else 'FAIL'}" for text, passed in checks]


def evaluate_kill_criteria(runs: pd.DataFrame) -> pd.DataFrame:
    """Mechanical kill criteria at 20 bps, with the 2/50 bps direction check."""
    rows: list[dict[str, object]] = []
    for hypothesis in ("H2", "H3", "H4"):
        row: dict[str, object] = {"hypothesis": hypothesis, "trial_id": PRIMARY_IDS[hypothesis]}
        verdicts = {}
        for cost in (DECISION_COST, *DIRECTION_COSTS, 100.0):
            passed, details = _criteria(hypothesis, runs, cost)
            verdicts[cost] = passed
            row[f"pass_{cost:g}bps"] = passed
            row[f"criteria_{cost:g}bps"] = "; ".join(details)
        decisive = [verdicts[DECISION_COST], *(verdicts[cost] for cost in DIRECTION_COSTS)]
        row["direction_consistent"] = len(set(decisive)) == 1
        row["verdict_pass"] = all(decisive)
        rows.append(row)
    return pd.DataFrame(rows)


def outcome_tier(*, verdict_pass: bool, multiple: float, dsr: float) -> str:
    if not verdict_pass:
        return "rejected"
    if multiple >= TARGET_MULTIPLE and dsr >= DSR_PASS:
        return "tier 3 conditions met here (champion candidate only after every AGENTS.md gate)"
    reasons = []
    if multiple < TARGET_MULTIPLE:
        reasons.append(f"M {multiple:.2f}x < 20x")
    if dsr < DSR_PASS:
        reasons.append(f"DSR {dsr:.3f} < 0.95")
    return "tier 2: risk variant recorded (" + "; ".join(reasons) + ")"


def single_step_reality_check(
    returns: pd.DataFrame,
    *,
    n_bootstrap: int,
    block_length: int,
    seed: int,
) -> pd.Series:
    """White Reality Check p-value per candidate against the bootstrap maximum.

    Same resampling as ``_reality_check`` (same generator calls), so the best
    candidate's p-value is that function's p-value; every other candidate is
    compared with the same distribution of the maximum (single-step).
    """
    values = returns.to_numpy(dtype=float, copy=True)
    centered = values - np.nanmean(values, axis=0, keepdims=True)
    observed = np.nanmean(values, axis=0)
    rng = np.random.default_rng(seed)
    maxima = np.empty(n_bootstrap, dtype=float)
    for iteration in range(n_bootstrap):
        indices = _stationary_bootstrap_indices(values.shape[0], block_length=block_length, rng=rng)
        maxima[iteration] = float(np.nanmax(np.nanmean(centered[indices, :], axis=0)))
    p_values = [(float(np.sum(maxima >= mean)) + 1.0) / (n_bootstrap + 1.0) for mean in observed]
    return pd.Series(p_values, index=returns.columns, dtype=float)


def terminal_wealth_bootstrap(
    candidate: pd.Series,
    baseline: pd.Series,
    *,
    n_bootstrap: int,
    block_length: int,
    seed: int,
) -> dict[str, float]:
    """Paired stationary bootstrap of the terminal-wealth ratio candidate / baseline."""
    frame = pd.concat([candidate, baseline], axis=1).to_numpy(dtype=float)
    if not np.isfinite(frame).all():
        raise ValueError("terminal-wealth bootstrap needs finite returns on every day")
    logs = np.log1p(frame)
    difference = logs[:, 0] - logs[:, 1]
    rng = np.random.default_rng(seed)
    ratios = np.empty(n_bootstrap, dtype=float)
    for iteration in range(n_bootstrap):
        indices = _stationary_bootstrap_indices(len(difference), block_length=block_length, rng=rng)
        ratios[iteration] = float(np.exp(difference[indices].sum()))
    return {
        "observed_ratio": float(np.exp(difference.sum())),
        "median_ratio": float(np.median(ratios)),
        "p05_ratio": float(np.quantile(ratios, 0.05)),
        "p95_ratio": float(np.quantile(ratios, 0.95)),
        "share_above_one": float(np.mean(ratios > 1.0)),
        "bootstrap_count": float(n_bootstrap),
    }


# --------------------------------------------------------------------------- main run


def _column(trial_id: str, fill: str, cost: float) -> str:
    return f"{trial_id}|{fill}|{cost:g}"


def run_trials(
    args: argparse.Namespace,
    trials: tuple[Trial, ...],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Every registered run: metrics, 20 bps daily returns, attribution and run facts."""
    config, market, universe, index = _load_market(
        args.config, start_date=MAIN_WINDOW[0], end_date=MAIN_WINDOW[1]
    )
    hourly = load_hourly_bars(args.hourly_dir)
    daily = market.returns.loc[index]
    closes = market.raw_price.reindex(index=index, columns=daily.columns)
    pre_fills = {
        fill: pre_fill_returns(
            daily, hourly, fill_hours=FILL_HOURS, missing_fill=policy, reference_close=closes
        )
        for fill, policy in HOUR_FILLS.items()
    }
    observed = observed_fill_mask(daily, hourly, fill_hours=FILL_HOURS, reference_close=closes)
    fill_split = {fill: frame.where(frame.notna(), daily) for fill, frame in pre_fills.items()}
    classes = entrant_classes(membership_panel(config, market, universe, index))

    rows: list[dict[str, object]] = []
    returns: dict[str, pd.Series] = {}
    attribution: list[dict[str, object]] = []
    facts: dict[str, object] = {"hourly_coins": sorted(hourly), "builds": {}}
    builds: dict[str, PhaseMomentumBuildResult] = {}
    for trial in trials:
        key = _sha256(_canonical(trial_spec(trial)["books"]))
        if key not in builds:
            builds[key] = build_trial(trial, market, universe, index)
        built = builds[key]
        facts["builds"][trial.trial_id] = {  # type: ignore[index]
            "target_events": len(built.targets),
            "sleeves": len(built.sleeve_targets),
            **_build_facts(built),
        }
        for fill in trial.fills:
            for cost in COSTS:
                result = _production_result(
                    config,
                    market,
                    built,
                    index,
                    cost_bps=cost,
                    execution_lag_days=LAG_FILLS.get(fill, 0),
                    pre_fill=pre_fills.get(fill),
                )
                series = result.daily_returns
                row: dict[str, object] = {
                    "trial_id": trial.trial_id,
                    "window": "main",
                    "fill": fill,
                    "cost_bps": float(cost),
                    **run_metrics(series, result),
                    "observed_weight_share": _observed_weight_share(result, observed)
                    if fill in HOUR_FILLS
                    else float("nan"),
                }
                rows.append(row)
                if cost == DECISION_COST:
                    returns[_column(trial.trial_id, fill, cost)] = series
                    attribution.append(
                        {
                            "trial_id": trial.trial_id,
                            "fill": fill,
                            "cost_bps": float(cost),
                            **entrant_attribution(
                                result, daily, classes, fill_split=fill_split.get(fill)
                            ),
                            "costs_paid": float(result.turnover.sum() * cost / 10_000.0),
                        }
                    )
        print(f"ran {trial.trial_id}", flush=True)

    stress_config, stress_market, stress_universe, stress_index = _load_market(
        args.config, start_date=STRESS_WINDOW[0], end_date=STRESS_WINDOW[1]
    )
    for trial in trials:
        if not trial.stress:
            continue
        built = build_trial(trial, stress_market, stress_universe, stress_index)
        for fill, lag in LAG_FILLS.items():
            for cost in COSTS:
                result = _production_result(
                    stress_config, stress_market, built, stress_index, cost_bps=cost, execution_lag_days=lag
                )
                rows.append(
                    {
                        "trial_id": trial.trial_id,
                        "window": "stress",
                        "fill": fill,
                        "cost_bps": float(cost),
                        **run_metrics(result.daily_returns, result),
                    }
                )
    btc = market.returns["bitcoin"].reindex(index)
    returns["BTC"] = btc
    stress_btc = stress_market.returns["bitcoin"].reindex(stress_index).fillna(0.0)
    rows.append(
        {"trial_id": "BTC", "window": "main", "fill": "buy_and_hold", "cost_bps": 0.0, **run_metrics(btc.fillna(0.0))}
    )
    rows.append(
        {"trial_id": "BTC", "window": "stress", "fill": "buy_and_hold", "cost_bps": 0.0, **run_metrics(stress_btc)}
    )
    facts["main_days"] = int(len(index))
    facts["stress_days"] = int(len(stress_index))
    return pd.DataFrame(rows), pd.DataFrame(returns), pd.DataFrame(attribution), facts


def _build_facts(built: PhaseMomentumBuildResult) -> dict[str, object]:
    history = built.selection_history
    facts: dict[str, object] = {}
    if "gate_exposure" in history.columns:
        per_day = history.groupby("signal_date")["gate_exposure"].first()
        facts["gate_exposure_share_of_days"] = {
            f"{value:g}": float((per_day.round(10) == value).mean()) for value in (0.0, 0.25, 0.5, 0.75, 1.0)
        }
    if "breadth" in history.columns:
        per_day = history.groupby("signal_date")[["breadth"]].first()
        facts["breadth_below_threshold_share_of_days"] = float((per_day["breadth"].fillna(-1.0) < 0.5).mean())
    facts["risk_on_share_of_sleeve_days"] = float(history["risk_on"].astype(bool).mean())
    return facts


# --------------------------------------------------------------------------- evaluation


def _decision_returns(runs: pd.DataFrame, returns: pd.DataFrame, trial_id: str) -> pd.Series:
    fill = str(worse_policy_row(runs, trial_id, DECISION_COST)["fill"])
    return returns[_column(trial_id, fill, DECISION_COST)].rename(trial_id)


def evaluate(
    runs: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    trial_summary: Path,
    bull: pd.Series,
) -> dict[str, object]:
    trial_ids = [BASELINE_ID, *PRIMARY_IDS.values()]
    decision = pd.concat(
        [decision_table(runs, trial_ids, cost) for cost in COSTS],
        ignore_index=True,
    )
    diagnostics = pd.concat(
        [decision_table(runs, list(H2_DIAGNOSTIC_IDS), cost) for cost in COSTS], ignore_index=True
    )
    kill = evaluate_kill_criteria(runs)

    universe_ids = [BASELINE_ID, *PRIMARY_IDS.values(), *H2_DIAGNOSTIC_IDS]
    decision_returns = pd.concat([_decision_returns(runs, returns, trial) for trial in universe_ids], axis=1)
    decision_returns = _require_common_sample(decision_returns)
    btc = returns["BTC"].reindex(decision_returns.index)
    if not np.isfinite(btc.to_numpy(dtype=float)).all():
        raise ValueError("BTC benchmark returns are missing inside the evaluation window")

    scopes = _project_scopes(trial_summary)
    dsr_rows: list[dict[str, object]] = []
    for trial_id in trial_ids:
        for scope, count, sharpe_std in scopes:
            dsr_rows.append(
                {
                    "trial_id": trial_id,
                    "scope": scope,
                    "trial_count": count,
                    "trial_sharpe_std_annualized": sharpe_std * np.sqrt(365.0),
                    **_deflated_sharpe(
                        decision_returns[trial_id],
                        expected_max_sharpe=_expected_max_sharpe(count, sharpe_std),
                    ),
                }
            )
    dsr = pd.DataFrame(dsr_rows)

    unique, duplicates = _dedupe_identical_columns(decision_returns)
    reality_rows: list[dict[str, object]] = []
    for benchmark, frame in (("zero", unique), ("BTC buy-and-hold", unique.sub(btc, axis=0))):
        per_trial = single_step_reality_check(
            frame, n_bootstrap=BOOTSTRAP_COUNT, block_length=BOOTSTRAP_BLOCK, seed=BOOTSTRAP_SEED
        )
        best = _reality_check(frame, n_bootstrap=BOOTSTRAP_COUNT, block_length=BOOTSTRAP_BLOCK, seed=BOOTSTRAP_SEED)
        for trial_id in universe_ids:
            source = duplicates.get(trial_id, trial_id)
            reality_rows.append(
                {
                    "trial_id": trial_id,
                    "benchmark": benchmark,
                    "mean_daily_excess": float(frame[source].mean()),
                    "single_step_p_value": float(per_trial[source]),
                    "round_best_p_value": float(best["reality_check_p_value"]),
                    "identical_to": duplicates.get(trial_id, ""),
                }
            )
    reality = pd.DataFrame(reality_rows)

    bootstrap_rows = [
        {
            "trial_id": PRIMARY_IDS[hypothesis],
            **terminal_wealth_bootstrap(
                decision_returns[PRIMARY_IDS[hypothesis]],
                decision_returns[BASELINE_ID],
                n_bootstrap=BOOTSTRAP_COUNT,
                block_length=BOOTSTRAP_BLOCK,
                seed=BOOTSTRAP_SEED,
            ),
        }
        for hypothesis in PRIMARY_IDS
    ]
    bootstrap = pd.DataFrame(bootstrap_rows)

    yearly = pd.concat(
        [_yearly_returns(decision_returns[trial]).rename(trial) for trial in trial_ids]
        + [_yearly_returns(btc).rename("BTC")],
        axis=1,
    )
    yearly.index = yearly.index.year
    labels = _lagged_regime_labels(bull, pd.DatetimeIndex(decision_returns.index))
    regime = _regime_table(
        {**{trial: decision_returns[trial] for trial in trial_ids}, "BTC": btc}, labels
    )
    beats: list[dict[str, object]] = []
    for hypothesis, trial_id in PRIMARY_IDS.items():
        years_better = int((yearly[trial_id] > yearly[BASELINE_ID]).sum())
        regime_frame = regime.set_index(["strategy", "regime"])["total_multiple"]
        regimes_better = int(
            sum(
                float(regime_frame.loc[(trial_id, name)]) > float(regime_frame.loc[(BASELINE_ID, name)])
                for name in ("bull", "non_bull")
            )
        )
        beats.append(
            {
                "hypothesis": hypothesis,
                "trial_id": trial_id,
                "years_beating_B": years_better,
                "years": int(len(yearly)),
                "regimes_beating_B": regimes_better,
                "regimes": 2,
            }
        )

    top_dsr = dsr[dsr["scope"] == COMPARABLE_SCOPE].set_index("trial_id")["deflated_sharpe_probability"]
    at_decision = decision[decision["cost_bps"] == DECISION_COST].set_index("trial_id")
    kill = kill.copy()
    kill["multiple_20bps_3h_worse"] = [float(at_decision.loc[trial, "multiple"]) for trial in kill["trial_id"]]
    kill["dsr_top20_2022"] = [float(top_dsr.loc[trial]) for trial in kill["trial_id"]]
    kill["tier"] = [
        outcome_tier(verdict_pass=bool(row.verdict_pass), multiple=row.multiple_20bps_3h_worse, dsr=row.dsr_top20_2022)
        for row in kill.itertuples()
    ]
    return {
        "decision": decision,
        "diagnostics": diagnostics,
        "kill": kill,
        "dsr": dsr,
        "reality": reality,
        "bootstrap": bootstrap,
        "yearly": yearly,
        "regime": regime,
        "beats": pd.DataFrame(beats),
        "duplicates": duplicates,
        "decision_sample": {
            "rows": int(len(decision_returns)),
            "start": str(pd.Timestamp(decision_returns.index.min()).date()),
            "end": str(pd.Timestamp(decision_returns.index.max()).date()),
        },
        "scopes": scopes,
    }


def _fmt_table(frame: pd.DataFrame, columns: list[str]) -> str:
    present = [column for column in columns if column in frame.columns]
    return dataframe_to_markdown(frame[present]) if not frame.empty else "(none)"


def write_outputs(
    output_dir: Path,
    *,
    runs: pd.DataFrame,
    returns: pd.DataFrame,
    attribution: pd.DataFrame,
    evaluation: dict[str, object],
    manifest: dict[str, object],
) -> None:
    runs.to_csv(output_dir / "runs.csv", index=False)
    returns.to_csv(output_dir / "returns_20bps.csv", index_label="date", float_format="%.12g")
    attribution.to_csv(output_dir / "entrant_attribution.csv", index=False)
    for name in ("decision", "diagnostics", "kill", "dsr", "reality", "bootstrap", "regime", "beats"):
        frame = evaluation[name]
        assert isinstance(frame, pd.DataFrame)
        frame.to_csv(output_dir / f"{name}.csv", index=False)
    yearly = evaluation["yearly"]
    assert isinstance(yearly, pd.DataFrame)
    yearly.to_csv(output_dir / "yearly.csv", index_label="year")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    write_report(output_dir, runs=runs, attribution=attribution, evaluation=evaluation, manifest=manifest)


def write_report(
    output_dir: Path,
    *,
    runs: pd.DataFrame,
    attribution: pd.DataFrame,
    evaluation: dict[str, object],
    manifest: dict[str, object],
) -> None:
    decision = evaluation["decision"]
    kill = evaluation["kill"]
    dsr = evaluation["dsr"]
    reality = evaluation["reality"]
    bootstrap = evaluation["bootstrap"]
    regime = evaluation["regime"]
    beats = evaluation["beats"]
    yearly = evaluation["yearly"]
    diagnostics = evaluation["diagnostics"]
    assert isinstance(decision, pd.DataFrame) and isinstance(kill, pd.DataFrame)
    assert isinstance(dsr, pd.DataFrame) and isinstance(reality, pd.DataFrame)
    assert isinstance(bootstrap, pd.DataFrame) and isinstance(regime, pd.DataFrame)
    assert isinstance(beats, pd.DataFrame) and isinstance(yearly, pd.DataFrame)
    assert isinstance(diagnostics, pd.DataFrame)
    at20 = decision[decision["cost_bps"] == DECISION_COST]
    main = runs[runs["window"] == "main"]
    stress = runs[runs["window"] == "stress"]
    headline_columns = [
        "trial_id", "worse_policy", "multiple", "cagr", "sharpe", "max_drawdown", "rolling_1y_worst_multiple",
        "rolling_1y_median_multiple", "best_year_removed_multiple", "turnover_annual", "avg_gross_exposure",
        "multiple_lag0", "multiple_lag1", "d3h", "d1d",
    ]
    lines = [
        "# Pre-Registered Hypotheses H2-H4 (2026-10 round)",
        "",
        f"Rules, parameters, kill criteria and tiers: `{REVIEW}` section 4 (H1 not run; it needs the",
        "owner's sign-off on the signals-at-the-close rule). Every trial below was registered in",
        f"`{manifest['ledger']}` before it ran; the runner refuses unregistered or changed trials.",
        "Strict point-in-time Top20, long-only spot, gross exposure <= 1, cash as the only defensive asset.",
        "",
        "## Deviation stated before running",
        "",
        "- **H3 blend.** The review asks for the 50/50 portfolio 'rebalanced to 50/50 daily as in section 0.8'.",
        "  Section 0.8 re-equalised the books' daily returns without charging the trades (a free-rebalancing",
        "  bug). Here all 24 sleeves are aggregated at the target level at 1/24 each, so the production engine",
        "  rebalances toward 50/50 at every target event and charges that turnover.",
        "- **H4 details the review leaves open.** The 0.05 weight tolerance applies to each coin's share of",
        "  the sleeve's capital; empty slots are refilled on any risk-on day (as the champion refills an empty",
        "  sleeve); the D1d threshold is max(0.52, D1d(B) in this harness).",
        "",
        "## Verdicts (20 bps, +3h fills, worse missing-candle policy)",
        "",
        _fmt_table(
            kill,
            ["hypothesis", "pass_20bps", "pass_2bps", "pass_50bps", "pass_100bps", "direction_consistent",
             "verdict_pass", "multiple_20bps_3h_worse", "dsr_top20_2022", "tier"],
        ),
        "",
        "Kill-criterion evaluations at 20 bps:",
        "",
        *[f"- **{row.hypothesis}**: {row.criteria_20bps}" for row in kill.itertuples()],
        "",
        "Direction checks at 2 and 50 bps (100 bps reported only):",
        "",
        *[
            f"- **{row.hypothesis}** 2 bps: {row.criteria_2bps}; 50 bps: {row.criteria_50bps}; "
            f"100 bps: {row.criteria_100bps}"
            for row in kill.itertuples()
        ],
        "",
        "## Headline metrics at 20 bps (+3h, worse policy)",
        "",
        _fmt_table(at20, headline_columns),
        "",
        "## Every cost level (+3h, worse policy)",
        "",
        _fmt_table(
            decision,
            ["trial_id", "cost_bps", "worse_policy", "multiple", "sharpe", "max_drawdown",
             "rolling_1y_worst_multiple", "d3h", "d1d"],
        ),
        "",
        "## H2 single-window diagnostics (+3h, worse policy; never promotable)",
        "",
        _fmt_table(
            diagnostics,
            ["trial_id", "cost_bps", "worse_policy", "multiple", "sharpe", "max_drawdown", "rolling_1y_worst_multiple"],
        ),
        "",
        "## Multiple testing",
        "",
        "Deflated Sharpe (probability the true Sharpe exceeds the expected maximum of the scope's trials;",
        "0.95 passes), on the 20 bps +3h worse-policy returns "
        f"({evaluation['decision_sample']['rows']} days):",  # type: ignore[index]
        "",
        _fmt_table(
            dsr,
            ["trial_id", "scope", "trial_count", "trial_sharpe_std_annualized", "observed_sharpe",
             "expected_max_sharpe", "deflated_sharpe_probability"],
        ),
        "",
        "White Reality Check (stationary bootstrap, 1000 draws, block 20, seed 20260923) over every return",
        "series of this round (B, H2-H4 and the four single-window gates; identical series counted once).",
        "`single_step_p_value` compares each trial's mean with the bootstrap maximum over the round;",
        "`round_best_p_value` is `_reality_check` for the best trial.",
        "",
        _fmt_table(
            reality,
            ["trial_id", "benchmark", "mean_daily_excess", "single_step_p_value", "round_best_p_value", "identical_to"],
        ),
        "",
        "Terminal-wealth ratio against B (paired stationary bootstrap, same settings):",
        "",
        _fmt_table(
            bootstrap,
            ["trial_id", "observed_ratio", "median_ratio", "p05_ratio", "p95_ratio", "share_above_one"],
        ),
        "",
        "Calendar years and lagged regimes in which each hypothesis beats B (20 bps, +3h worse policy):",
        "",
        _fmt_table(beats, ["hypothesis", "years_beating_B", "years", "regimes_beating_B", "regimes"]),
        "",
        "## Yearly returns (20 bps, +3h, worse policy)",
        "",
        dataframe_to_markdown(yearly.reset_index()),
        "",
        "## Bull / non-bull split (regime known at the previous close)",
        "",
        _fmt_table(regime, ["strategy", "regime", "days", "total_multiple", "sharpe", "max_drawdown"]),
        "",
        "## Entrant attribution (20 bps)",
        "",
        "Sum of daily per-coin contributions of the engine's book (gross of costs), classed at the signal",
        "date: `entrant` = inside a Top20 membership spell that began at most 29 days earlier, `incumbent` =",
        "an older spell, `non_member` = held while outside that day's Top20 (exit lag).",
        "",
        _fmt_table(
            attribution,
            ["trial_id", "fill", "entrant_share", "incumbent_share", "non_member_share", "entrant_contribution",
             "incumbent_contribution", "non_member_contribution", "costs_paid"],
        ),
        "",
        "## All main-window runs",
        "",
        _fmt_table(
            main,
            ["trial_id", "fill", "cost_bps", "multiple", "cagr", "sharpe", "max_drawdown",
             "rolling_1y_worst_multiple", "rolling_1y_median_multiple", "best_year", "best_year_removed_multiple",
             "turnover_annual", "observed_weight_share"],
        ),
        "",
        f"## Stress window {STRESS_WINDOW[0]} to {STRESS_WINDOW[1]} (lag 0 and lag 1 only)",
        "",
        _fmt_table(
            stress,
            ["trial_id", "fill", "cost_bps", "multiple", "cagr", "sharpe", "max_drawdown", "rolling_1y_worst_multiple"],
        ),
        "",
        "## Build facts",
        "",
        "```json",
        json.dumps(manifest.get("run_facts", {}).get("builds", {}), indent=2),  # type: ignore[union-attr]
        "```",
        "",
        "## Reading the result",
        "",
        "- Kill criteria were applied mechanically; no parameter, window or threshold was changed after",
        "  the runs. The pre-declared neighbourhoods are run only after a pass, as new ledger trials.",
        "- None of these hypotheses can lift the Deflated Sharpe to 0.95 (review 4.0); the clean remedy is",
        "  data after 2026-09-21 that no trial has seen.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def _result_summary(kill_row: pd.Series | None, decision_row: pd.Series) -> str:
    text = (
        f"20bps +3h worse({decision_row['worse_policy']}): M={decision_row['multiple']:.4f} "
        f"Sharpe={decision_row['sharpe']:.4f} MDD={decision_row['max_drawdown']:.4f} "
        f"roll1y_worst={decision_row['rolling_1y_worst_multiple']:.4f} "
        f"D3h={decision_row['d3h']:.4f} D1d={decision_row['d1d']:.4f}"
    )
    if kill_row is not None:
        text += f"; verdict={'pass' if kill_row['verdict_pass'] else 'reject'}; tier={kill_row['tier']}"
    return text


def _ledger_result_rows(
    trials: tuple[Trial, ...],
    evaluation: dict[str, object],
    *,
    status: str,
    result_path: str,
    note: str,
) -> list[dict[str, str]]:
    decision = evaluation["decision"]
    diagnostics = evaluation["diagnostics"]
    kill = evaluation["kill"]
    assert isinstance(decision, pd.DataFrame) and isinstance(diagnostics, pd.DataFrame)
    assert isinstance(kill, pd.DataFrame)
    table = pd.concat([decision, diagnostics], ignore_index=True)
    table = table[table["cost_bps"] == DECISION_COST].drop_duplicates("trial_id").set_index("trial_id")
    kill_rows = kill.set_index("trial_id")
    now = _utc_now()
    rows: list[dict[str, str]] = []
    for trial in trials:
        registration = ledger_registration_row(trial, now="")
        rows.append(
            {
                "trial_id": trial.trial_id,
                "spec_sha256": registration["spec_sha256"],
                "status": status,
                "recorded_at_utc": now,
                "result_path": result_path,
                "result": _result_summary(
                    kill_rows.loc[trial.trial_id] if trial.trial_id in kill_rows.index else None,
                    table.loc[trial.trial_id],
                )
                + (f"; {note}" if note else ""),
            }
        )
    return rows


def _load_bull(config_path: str) -> pd.Series:
    config, market, _universe, _index = _load_market(
        config_path, start_date=MAIN_WINDOW[0], end_date=MAIN_WINDOW[1]
    )
    return build_regime_frame(market.price, market.market_cap, config)["bull"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--hourly-dir", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--trial-summary", type=Path, default=Path("reports/research_trial_inventory/summary.json"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--register", action="store_true", help="append missing registrations and stop")
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="recompute statistics and verdicts from the saved runs (e.g. after the inventory is rebuilt)",
    )
    args = parser.parse_args()
    configure_logging("ERROR")

    if args.register:
        written = register_trials(args.ledger, TRIALS, now=_utc_now())
        print(f"registered {written} trial(s) in {args.ledger}")
        return

    ledger = read_ledger(args.ledger)
    for trial in TRIALS:
        require_registered(ledger, trial)

    output_dir = ensure_dir(args.output_dir)
    result_path = str(output_dir / "runs.csv")
    if args.evaluate_only:
        runs = pd.read_csv(output_dir / "runs.csv")
        returns = pd.read_csv(output_dir / "returns_20bps.csv", parse_dates=["date"]).set_index("date")
        attribution = pd.read_csv(output_dir / "entrant_attribution.csv")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    else:
        append_ledger_rows(
            args.ledger,
            [
                {
                    "trial_id": trial.trial_id,
                    "spec_sha256": ledger_registration_row(trial, now="")["spec_sha256"],
                    "status": "running",
                    "recorded_at_utc": _utc_now(),
                    "result_path": result_path,
                    "result": "",
                }
                for trial in TRIALS
            ],
        )
        try:
            runs, returns, attribution, facts = run_trials(args, TRIALS)
        except Exception as error:
            append_ledger_rows(
                args.ledger,
                [
                    {
                        "trial_id": trial.trial_id,
                        "status": "failed",
                        "recorded_at_utc": _utc_now(),
                        "result": f"{type(error).__name__}: {error}"[:500],
                    }
                    for trial in TRIALS
                ],
            )
            raise
        manifest = {
            "script": "scripts/run_phase_momentum_hypotheses.py",
            "review": REVIEW,
            "config": args.config,
            "hourly_dir": str(args.hourly_dir),
            "main_window": list(MAIN_WINDOW),
            "stress_window": list(STRESS_WINDOW),
            "cost_bps": list(COSTS),
            "fills": list(MAIN_FILLS),
            "fill_hours": FILL_HOURS,
            "missing_fill_policies": list(MISSING_FILL_POLICIES),
            "bootstrap": {"count": BOOTSTRAP_COUNT, "block_length": BOOTSTRAP_BLOCK, "seed": BOOTSTRAP_SEED},
            "entrant_days": ENTRANT_DAYS,
            "trials": {trial.trial_id: trial_spec(trial) for trial in TRIALS},
            "run_facts": facts,
            "ran_at_utc": _utc_now(),
        }

    bull = _load_bull(args.config)
    evaluation = evaluate(runs, returns, trial_summary=args.trial_summary, bull=bull)
    ledger_bytes = args.ledger.read_bytes()
    manifest.update(
        {
            "ledger": str(args.ledger),
            "ledger_sha256_at_evaluation": hashlib.sha256(ledger_bytes).hexdigest(),
            "trial_summary": str(args.trial_summary),
            "trial_summary_sha256": hashlib.sha256(args.trial_summary.read_bytes()).hexdigest(),
            "trial_scopes": [
                {"scope": scope, "trial_count": count, "trial_sharpe_std_per_period": std}
                for scope, count, std in evaluation["scopes"]  # type: ignore[union-attr]
            ],
            "decision_sample": evaluation["decision_sample"],
            "identical_return_series": evaluation["duplicates"],
            "evaluated_at_utc": _utc_now(),
        }
    )
    write_outputs(
        output_dir, runs=runs, returns=returns, attribution=attribution, evaluation=evaluation, manifest=manifest
    )
    count = next(count for scope, count, _ in evaluation["scopes"] if scope == COMPARABLE_SCOPE)  # type: ignore[union-attr]
    append_ledger_rows(
        args.ledger,
        _ledger_result_rows(
            TRIALS,
            evaluation,
            status="evaluated" if args.evaluate_only else "completed",
            result_path=result_path,
            note=f"DSR scope {COMPARABLE_SCOPE} N={count}",
        ),
    )
    kill = evaluation["kill"]
    assert isinstance(kill, pd.DataFrame)
    print(kill[["hypothesis", "pass_20bps", "pass_2bps", "pass_50bps", "verdict_pass", "tier"]].to_string(index=False))
    print(f"Wrote pre-registered hypothesis results to {output_dir}")


if __name__ == "__main__":
    main()
