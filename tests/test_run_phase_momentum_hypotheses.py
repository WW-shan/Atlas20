"""Tests for the 2026-10 pre-registered hypothesis runner (ledger, verdicts, statistics)."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.run_phase_momentum_hypotheses import (
    LEDGER_COLUMNS,
    TRIALS,
    UnregisteredTrialError,
    append_ledger_rows,
    decision_table,
    entrant_classes,
    evaluate_kill_criteria,
    evaluate_neighbourhood,
    ledger_registration_row,
    outcome_tier,
    read_ledger,
    register_trials,
    require_registered,
    single_step_reality_check,
    terminal_wealth_bootstrap,
    trial_by_id,
    worse_policy_row,
)
from scripts.run_phase_momentum_multiple_testing import _reality_check


def _ledger(tmp_path: Path) -> Path:
    return tmp_path / "preregistered_trials.csv"


def test_registration_writes_one_row_per_trial_and_is_idempotent(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    written = register_trials(ledger, TRIALS, now="2026-09-25T00:00:00Z")
    again = register_trials(ledger, TRIALS, now="2026-09-26T00:00:00Z")

    rows = read_ledger(ledger)
    assert written == len(TRIALS)
    assert again == 0
    assert list(rows.columns) == LEDGER_COLUMNS
    assert (rows["status"] == "registered").sum() == len(TRIALS)
    assert set(rows["registered_at_utc"]) == {"2026-09-25T00:00:00Z"}
    counted = rows[rows["counts_as_trial"].astype(str) == "True"]["trial_id"].tolist()
    assert sorted(counted) == [
        "PR2026-10-H2",
        "PR2026-10-H2-LOO100",
        "PR2026-10-H2-LOO150",
        "PR2026-10-H2-LOO200",
        "PR2026-10-H2-LOO50",
        "PR2026-10-H3",
        "PR2026-10-H3-T45",
        "PR2026-10-H3-T55",
        "PR2026-10-H4",
        "PR2026-10-H5",
        "PR2026-10-H5-T60",
        "PR2026-10-H5-T90",
        "PR2026-10-H6",
        "PR2026-10-H6-T70",
        "PR2026-10-H6-T90",
    ]


def test_runner_refuses_a_trial_that_is_not_in_the_ledger(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    register_trials(ledger, TRIALS[:1], now="2026-09-25T00:00:00Z")

    require_registered(read_ledger(ledger), TRIALS[0])
    with pytest.raises(UnregisteredTrialError, match="not registered"):
        require_registered(read_ledger(ledger), trial_by_id("PR2026-10-H2"))


def test_runner_refuses_a_trial_whose_rules_changed_after_registration(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    register_trials(ledger, TRIALS, now="2026-09-25T00:00:00Z")
    rows = read_ledger(ledger)
    tampered = rows.copy()
    mask = tampered["trial_id"] == "PR2026-10-H4"
    tampered.loc[mask & (tampered["status"] == "registered"), "registration_sha256"] = "0" * 64

    with pytest.raises(UnregisteredTrialError, match="changed"):
        require_registered(tampered, trial_by_id("PR2026-10-H4"))
    with pytest.raises(UnregisteredTrialError):
        register_trials(ledger, (trial_by_id("PR2026-10-H4"),), now="x", existing=tampered)


def test_ledger_appends_results_without_rewriting_registrations(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    register_trials(ledger, TRIALS, now="2026-09-25T00:00:00Z")
    before = ledger.read_text(encoding="utf-8")

    append_ledger_rows(
        ledger,
        [
            {
                "trial_id": "PR2026-10-H2",
                "status": "completed",
                "recorded_at_utc": "2026-09-25T01:00:00Z",
                "result_path": "reports/x/runs.csv",
                "result": "M=1.0",
            }
        ],
    )

    after = ledger.read_text(encoding="utf-8")
    assert after.startswith(before)
    rows = read_ledger(ledger)
    assert rows.iloc[-1]["status"] == "completed"
    assert pd.isna(rows.iloc[-1]["rule"]) or rows.iloc[-1]["rule"] == ""
    with open(ledger, encoding="utf-8", newline="") as handle:
        assert len(list(csv.reader(handle))) == len(TRIALS) + 2


def test_registration_row_hashes_the_exact_spec() -> None:
    row = ledger_registration_row(trial_by_id("PR2026-10-H2"), now="t")

    assert '"btc_ma_windows":[50,100,150,200]' in row["spec"]
    assert len(row["spec_sha256"]) == 64
    h4 = ledger_registration_row(trial_by_id("PR2026-10-H4"), now="t")
    assert '"holdings_per_sleeve":4' in h4["spec"] and '"hold_rank":8' in h4["spec"]
    h3 = ledger_registration_row(trial_by_id("PR2026-10-H3"), now="t")
    assert '"breadth_threshold":0.5' in h3["spec"] and '"weight":0.5' in h3["spec"]
    assert "free-rebalancing" in h3["deviation_notes"]


def _runs(rows: list[tuple[str, str, float, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["trial_id", "fill", "cost_bps", "multiple", "sharpe", "max_drawdown", "rolling_1y_worst_multiple"],
    ).assign(window="main")


def _full_runs(values: dict[str, tuple[float, float, float, float, float, float]]) -> pd.DataFrame:
    """values: trial -> (M lag0, M lag1, M h3 day_close, M h3 prior_close, sharpe, mdd)."""
    rows = []
    for trial, (lag0, lag1, day_close, prior_close, sharpe, mdd) in values.items():
        for cost in (2.0, 20.0, 50.0, 100.0):
            rows.append((trial, "lag0", cost, lag0, sharpe, mdd, 0.7))
            rows.append((trial, "lag1", cost, lag1, sharpe, mdd, 0.7))
            rows.append((trial, "h3_day_close", cost, day_close, sharpe, mdd, 0.7))
            rows.append((trial, "h3_prior_close", cost, prior_close, sharpe, mdd - 0.01, 0.6))
    return _runs(rows)


def test_worse_policy_is_the_lower_multiple_and_carries_its_metrics() -> None:
    runs = _full_runs({"B": (23.0, 12.0, 19.5, 19.9, 1.37, -0.45)})

    row = worse_policy_row(runs, "B", 20.0)

    assert row["fill"] == "h3_day_close"
    assert row["multiple"] == 19.5
    assert row["max_drawdown"] == -0.45
    table = decision_table(runs, ["B"], 20.0).set_index("trial_id")
    assert table.loc["B", "d3h"] == pytest.approx(19.5 / 23.0)
    assert table.loc["B", "d1d"] == pytest.approx(12.0 / 23.0)


def test_kill_criteria_h2_uses_the_single_window_median_and_drawdown_tolerance() -> None:
    base = {
        "PR2026-10-B": (23.0, 12.0, 19.5, 19.9, 1.37, -0.45),
        "PR2026-10-H2-D50": (9.5, 5.0, 8.0, 8.2, 1.0, -0.5),
        "PR2026-10-H2-D100": (23.0, 12.0, 19.5, 19.9, 1.37, -0.45),
        "PR2026-10-H2-D150": (11.6, 6.0, 10.0, 10.1, 1.1, -0.5),
        "PR2026-10-H2-D200": (10.0, 5.0, 9.0, 9.2, 1.0, -0.5),
        "PR2026-10-H3": (18.0, 10.0, 15.0, 15.5, 1.5, -0.38),
        "PR2026-10-H4": (12.0, 9.0, 11.0, 11.5, 1.2, -0.39),
        # H5 only has to be present for the H5 family to be evaluable here.
        "PR2026-10-H5": (18.0, 10.0, 15.0, 15.5, 1.6, -0.38),
        # H6 is compared against H5; present for the H6 family to be evaluable.
        "PR2026-10-H6": (18.0, 10.0, 15.0, 15.5, 1.7, -0.38),
    }
    # H2: median of diagnostics at +3h worse = median(8.0, 19.5, 10.0, 9.0) = 9.5.
    passing = _full_runs({**base, "PR2026-10-H2": (14.0, 8.0, 12.0, 12.5, 1.3, -0.465)})
    failing_mdd = _full_runs({**base, "PR2026-10-H2": (14.0, 8.0, 12.0, 12.5, 1.3, -0.4701)})
    failing_median = _full_runs({**base, "PR2026-10-H2": (10.0, 8.0, 9.4, 9.45, 1.3, -0.40)})

    ok = evaluate_kill_criteria(passing).set_index("hypothesis").loc["H2"]
    bad_mdd = evaluate_kill_criteria(failing_mdd).set_index("hypothesis").loc["H2"]
    bad_median = evaluate_kill_criteria(failing_median).set_index("hypothesis").loc["H2"]

    assert bool(ok["pass_20bps"]) and bool(ok["verdict_pass"])
    assert not bool(bad_mdd["pass_20bps"]) and not bool(bad_mdd["verdict_pass"])
    assert not bool(bad_median["pass_20bps"])
    assert "median" in str(ok["criteria_20bps"])


def test_kill_criteria_h3_and_h4_need_every_endpoint_and_the_same_verdict_at_2_and_50_bps() -> None:
    values = {
        "PR2026-10-B": (23.0, 12.0, 19.5, 19.9, 1.37, -0.45),
        "PR2026-10-H2-D50": (9.5, 5.0, 8.0, 8.2, 1.0, -0.5),
        "PR2026-10-H2-D100": (23.0, 12.0, 19.5, 19.9, 1.37, -0.45),
        "PR2026-10-H2-D150": (11.6, 6.0, 10.0, 10.1, 1.1, -0.5),
        "PR2026-10-H2-D200": (10.0, 5.0, 9.0, 9.2, 1.0, -0.5),
        "PR2026-10-H2": (14.0, 8.0, 12.0, 12.5, 1.3, -0.46),
        # H3: drawdown 5.5 points better, higher Sharpe, higher rolling worst.
        "PR2026-10-H3": (18.0, 10.0, 15.0, 15.5, 1.5, -0.395),
        # H4: drawdown 6 points better and D1d = 9 / 12 = 0.75 > 0.52.
        "PR2026-10-H4": (12.0, 9.0, 11.0, 11.5, 1.2, -0.39),
        # H5: drawdown 8 points better than B, Sharpe and rolling worst above H3's.
        "PR2026-10-H5": (18.0, 10.0, 15.0, 15.5, 1.6, -0.37),
        # H6: higher Sharpe than H5, drawdown within 5 points, multiple >= 0.85 x H5.
        "PR2026-10-H6": (18.0, 10.0, 15.0, 15.5, 1.7, -0.36),
    }
    runs = _full_runs(values)
    runs.loc[(runs["trial_id"] == "PR2026-10-H3"), "rolling_1y_worst_multiple"] = 0.8
    runs.loc[(runs["trial_id"] == "PR2026-10-H5"), "rolling_1y_worst_multiple"] = 0.8
    runs.loc[(runs["trial_id"] == "PR2026-10-H6"), "rolling_1y_worst_multiple"] = 0.85

    table = evaluate_kill_criteria(runs).set_index("hypothesis")
    assert bool(table.loc["H3", "verdict_pass"])
    assert bool(table.loc["H4", "verdict_pass"])

    # The same H4 fails when its lag-1 multiple gives D1d <= 0.52.
    weak = runs.copy()
    weak.loc[(weak["trial_id"] == "PR2026-10-H4") & (weak["fill"] == "lag1"), "multiple"] = 6.0
    assert not bool(evaluate_kill_criteria(weak).set_index("hypothesis").loc["H4", "verdict_pass"])

    # A pass at 20 bps that flips at 50 bps is not a pass.
    flip = runs.copy()
    rows = (flip["trial_id"] == "PR2026-10-H3") & (flip["cost_bps"] == 50.0)
    flip.loc[rows, "sharpe"] = 1.0
    row = evaluate_kill_criteria(flip).set_index("hypothesis").loc["H3"]
    assert bool(row["pass_20bps"]) and not bool(row["pass_50bps"])
    assert not bool(row["verdict_pass"]) and not bool(row["direction_consistent"])


def test_neighbourhood_trials_drop_or_move_exactly_the_declared_parameter() -> None:
    loo = trial_by_id("PR2026-10-H2-LOO150")
    assert loo.role == "neighbourhood" and loo.counts_as_trial
    assert loo.books[0][0].btc_ma_windows == (50, 100, 200)
    assert "MA150 left out" in loo.rule

    t045 = trial_by_id("PR2026-10-H3-T45")
    assert t045.books[0][0].breadth_threshold is None  # book A stays the champion
    assert t045.books[1][0].breadth_threshold == 0.45
    assert t045.books[1][1] == 0.5
    t055 = trial_by_id("PR2026-10-H3-T55")
    assert t055.books[1][0].breadth_threshold == 0.55


def test_neighbourhood_ensembles_are_judged_by_their_parents_criterion() -> None:
    base = {
        "PR2026-10-B": (23.0, 12.0, 19.5, 19.9, 1.37, -0.45),
        "PR2026-10-H2-D50": (9.5, 5.0, 8.0, 8.2, 1.0, -0.5),
        "PR2026-10-H2-D100": (23.0, 12.0, 19.5, 19.9, 1.37, -0.45),
        "PR2026-10-H2-D150": (11.6, 6.0, 10.0, 10.1, 1.1, -0.5),
        "PR2026-10-H2-D200": (10.0, 5.0, 9.0, 9.2, 1.0, -0.5),
        # LOO50/LOO100/LOO150: 12.0 > the 9.5 median and MDD -0.46 >= -0.47 -> criterion kept.
        "PR2026-10-H2-LOO50": (14.0, 8.0, 12.0, 12.5, 1.3, -0.46),
        "PR2026-10-H2-LOO100": (14.0, 8.0, 12.0, 12.5, 1.3, -0.46),
        "PR2026-10-H2-LOO150": (14.0, 8.0, 12.0, 12.5, 1.3, -0.46),
        # LOO200: MDD -0.4701 breaks the 2-point tolerance -> criterion not kept.
        "PR2026-10-H2-LOO200": (14.0, 8.0, 12.0, 12.5, 1.3, -0.4701),
        # T045: 5.5-point drawdown improvement, higher Sharpe, higher rolling worst.
        "PR2026-10-H3-T45": (18.0, 10.0, 15.0, 15.5, 1.5, -0.395),
        # T055: same drawdown but Sharpe below B's -> criterion not kept.
        "PR2026-10-H3-T55": (18.0, 10.0, 15.0, 15.5, 1.2, -0.395),
        # H3 is the reference the H5 family is measured against.
        "PR2026-10-H3": (18.0, 10.0, 15.0, 15.5, 1.5, -0.395),
        # H5 is the reference H3 is measured against for the H5 family.
        "PR2026-10-H5": (18.0, 10.0, 15.0, 15.5, 1.6, -0.37),
        # H5-T60: 6-point drawdown improvement over B, Sharpe and rolling worst above H3.
        "PR2026-10-H5-T60": (18.0, 10.0, 15.0, 15.5, 1.55, -0.39),
        # H5-T90: drawdown still passes but Sharpe drops below H3's -> not kept.
        "PR2026-10-H5-T90": (18.0, 10.0, 15.0, 15.5, 1.45, -0.40),
        # H6 is the reference the H6 neighbourhoods are measured against.
        "PR2026-10-H6": (18.0, 10.0, 15.0, 15.5, 1.6, -0.37),
        # H6-T70: Sharpe above H5's, drawdown within 5 points of B's and
        # multiple >= 0.85 x H5's -> kept.
        "PR2026-10-H6-T70": (18.0, 10.0, 15.0, 15.5, 1.65, -0.40),
        # H6-T90: Sharpe below H5's -> not kept.
        "PR2026-10-H6-T90": (18.0, 10.0, 15.0, 15.5, 1.50, -0.40),
    }
    runs = _full_runs(base)
    runs.loc[runs["trial_id"].str.startswith("PR2026-10-H3-T"), "rolling_1y_worst_multiple"] = 0.8
    runs.loc[runs["trial_id"].str.startswith("PR2026-10-H5"), "rolling_1y_worst_multiple"] = 0.85
    runs.loc[runs["trial_id"] == "PR2026-10-H6-T70", "rolling_1y_worst_multiple"] = 0.87
    runs.loc[runs["trial_id"] == "PR2026-10-H6-T90", "rolling_1y_worst_multiple"] = 0.85
    runs.loc[runs["trial_id"] == "PR2026-10-H6", "rolling_1y_worst_multiple"] = 0.85
    runs.loc[runs["trial_id"] == "PR2026-10-H3", "rolling_1y_worst_multiple"] = 0.8

    table = evaluate_neighbourhood(runs).set_index("trial_id")

    assert bool(table.loc["PR2026-10-H2-LOO150", "verdict_pass"])
    assert not bool(table.loc["PR2026-10-H2-LOO200", "verdict_pass"])
    assert bool(table.loc["PR2026-10-H3-T45", "verdict_pass"])
    assert not bool(table.loc["PR2026-10-H3-T55", "verdict_pass"])
    assert bool(table.loc["PR2026-10-H5-T60", "verdict_pass"])
    assert not bool(table.loc["PR2026-10-H5-T90", "verdict_pass"])
    assert bool(table.loc["PR2026-10-H6-T70", "verdict_pass"])
    assert not bool(table.loc["PR2026-10-H6-T90", "verdict_pass"])
    assert "criterion kept" in table.loc["PR2026-10-H2-LOO150", "tier"]
    assert "NOT kept" in table.loc["PR2026-10-H2-LOO200", "tier"]


def test_outcome_tiers() -> None:
    assert outcome_tier(verdict_pass=False, multiple=30.0, dsr=0.99) == "rejected"
    assert outcome_tier(verdict_pass=True, multiple=15.0, dsr=0.99).startswith("tier 2")
    assert outcome_tier(verdict_pass=True, multiple=25.0, dsr=0.80).startswith("tier 2")
    assert outcome_tier(verdict_pass=True, multiple=25.0, dsr=0.96).startswith("tier 3")


def test_entrant_classes_follow_the_current_membership_spell() -> None:
    dates = pd.date_range("2024-01-01", periods=70, freq="D")
    member = pd.DataFrame(True, index=dates, columns=["old", "new", "flicker"])
    member.loc[: dates[19], "new"] = False  # enters on day 20
    member.loc[dates[40], "flicker"] = False  # leaves for one day, back on day 41

    classes = entrant_classes(member, window_days=30)

    assert classes.loc[dates[45], "old"] == "incumbent"  # member since before the sample: spell starts day 0
    assert classes.loc[dates[20], "new"] == "entrant"
    assert classes.loc[dates[49], "new"] == "entrant"
    assert classes.loc[dates[50], "new"] == "incumbent"
    assert classes.loc[dates[10], "new"] == "non_member"
    assert classes.loc[dates[40], "flicker"] == "non_member"
    assert classes.loc[dates[41], "flicker"] == "entrant"


def test_single_step_reality_check_matches_the_project_reality_check_for_the_best() -> None:
    rng = np.random.default_rng(3)
    returns = pd.DataFrame(
        {"a": rng.normal(0.001, 0.02, 400), "b": rng.normal(0.0005, 0.02, 400), "c": rng.normal(0.0, 0.02, 400)}
    )

    per_candidate = single_step_reality_check(returns, n_bootstrap=200, block_length=20, seed=7)
    project = _reality_check(returns, n_bootstrap=200, block_length=20, seed=7)

    best = returns.mean().idxmax()
    assert per_candidate[best] == pytest.approx(project["reality_check_p_value"])
    assert per_candidate[best] <= per_candidate.min() + 1e-12
    assert (per_candidate <= 1.0).all()


def test_terminal_wealth_bootstrap_of_identical_series_is_one() -> None:
    returns = pd.Series(np.random.default_rng(1).normal(0.001, 0.02, 300))

    same = terminal_wealth_bootstrap(returns, returns, n_bootstrap=100, block_length=20, seed=5)
    better = terminal_wealth_bootstrap(returns + 0.001, returns, n_bootstrap=100, block_length=20, seed=5)

    assert same["observed_ratio"] == pytest.approx(1.0)
    assert same["median_ratio"] == pytest.approx(1.0)
    assert better["share_above_one"] == pytest.approx(1.0)
    assert better["p05_ratio"] > 1.0
