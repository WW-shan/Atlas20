from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from scripts.build_trial_inventory import (
    ALL_TRIALS,
    TOP20_2022_TRIALS,
    TrialRecorder,
    _fmt,
    assign_identities,
    flag_new_configurations,
    primary_costs,
    research_md_configurations,
    scope_summary,
    unclassified_report_dirs,
)

COLUMNS = ["study", "config_id", "universe", "window_start", "cost_bps", "annualized_sharpe", "lineage"]


def _trials(*rows: tuple[object, ...]) -> pd.DataFrame:
    frame = pd.DataFrame(list(rows), columns=COLUMNS)
    frame["identity"] = assign_identities(frame)
    return frame


def _flag(frame: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    return flag_new_configurations(frame, order).set_index(["study", "config_id", "universe"])


def test_repeat_of_an_earlier_study_is_not_new() -> None:
    frame = _trials(
        ("first", "a", "Top20", "2022-01-01", 20.0, 1.25, "first"),
        ("second", "a_again", "Top20", "2022-01-01", 20.0, 1.25 + 1e-12, "second"),
        ("second", "b", "Top20", "2022-01-01", 20.0, 0.75, "second"),
    )

    flagged = _flag(frame, ["first", "second"])

    assert bool(flagged.loc[("second", "a_again", "Top20"), ALL_TRIALS]) is False
    assert flagged.loc[("second", "a_again", "Top20"), "duplicate_of"] == "first:a"
    assert bool(flagged.loc[("second", "b", "Top20"), ALL_TRIALS]) is True
    assert int(flagged[TOP20_2022_TRIALS].sum()) == 2


def test_identical_returns_inside_one_study_count_separately() -> None:
    # Two liquidity tiers that never bind give the same returns; both were tried.
    frame = _trials(
        ("screen", "tier_a", "Top20", "2022-01-01", 20.0, 0.9, "screen"),
        ("screen", "tier_b", "Top20", "2022-01-01", 20.0, 0.9, "screen"),
    )

    flagged = _flag(frame, ["screen"])

    assert flagged[ALL_TRIALS].tolist() == [True, True]


def test_same_sharpe_on_another_cost_window_or_universe_is_new() -> None:
    frame = _trials(
        ("first", "a", "Top20", "2022-01-01", 20.0, 1.1, "first"),
        ("other_cost", "a", "Top20", "2022-01-01", 10.0, 1.1, "other_cost"),
        ("other_window", "a", "Top20", "2021-01-01", 20.0, 1.1, "other_window"),
        ("other_universe", "a", "Top50", "2022-01-01", 20.0, 1.1, "other_universe"),
    )

    flagged = flag_new_configurations(frame, ["first", "other_cost", "other_window", "other_universe"])

    assert flagged[ALL_TRIALS].all()
    assert flagged.loc[flagged["universe"] == "Top50", TOP20_2022_TRIALS].tolist() == [False]
    assert flagged.loc[flagged["window_start"] == "2021-01-01", TOP20_2022_TRIALS].tolist() == [False]


def test_rerun_of_the_same_grid_on_another_window_counts_once() -> None:
    frame = _trials(
        ("grid_2022", "cell", "Top20", "2022-01-01", 20.0, 0.8, "grid"),
        ("grid_2021", "cell", "Top20", "2021-01-01", 20.0, 1.9, "grid"),
        ("grid_2021", "extra_cell", "Top20", "2021-01-01", 20.0, 1.7, "grid"),
    )

    flagged = _flag(frame, ["grid_2022", "grid_2021"])

    assert bool(flagged.loc[("grid_2021", "cell", "Top20"), ALL_TRIALS]) is False
    assert flagged.loc[("grid_2021", "cell", "Top20"), "duplicate_of"] == "grid_2022:cell"
    assert bool(flagged.loc[("grid_2021", "extra_cell", "Top20"), ALL_TRIALS]) is True
    assert int(flagged[ALL_TRIALS].sum()) == 2


def test_scope_first_order_keeps_the_top20_2022_run_in_scope() -> None:
    # The 2021 run happened first in research order, but the configuration was
    # also tested on Top20 from 2022, so it must count in that scope.
    frame = _trials(
        ("early_2021", "cell", "Top20", "2021-01-01", 20.0, 1.5, "grid"),
        ("late_2022", "cell", "Top20", "2022-01-01", 20.0, 0.6, "grid"),
        ("late_2022", "cell", "Top50", "2022-01-01", 20.0, 0.7, "grid"),
    )

    flagged = _flag(frame, ["early_2021", "late_2022"])

    assert bool(flagged.loc[("late_2022", "cell", "Top20"), TOP20_2022_TRIALS]) is True
    assert bool(flagged.loc[("early_2021", "cell", "Top20"), ALL_TRIALS]) is False
    assert bool(flagged.loc[("late_2022", "cell", "Top50"), ALL_TRIALS]) is True
    assert int(flagged[ALL_TRIALS].sum()) == 2


def test_sharpe_match_on_a_shared_window_inherits_the_scope_configuration() -> None:
    # A 2021 re-run of an in-scope grid reproduces a pipeline strategy exactly:
    # the pipeline strategy is that in-scope configuration, not a new one.
    frame = _trials(
        ("ablation_2022", "X_bull__none", "Top20", "2022-01-01", 20.0, 0.4, "ablation"),
        ("ablation_2021", "X_bull__none", "Top20", "2021-01-01", 20.0, 0.47, "ablation"),
        ("pipeline", "X__bull_only", "Top20", "2021-01-01", 20.0, 0.47, "pipeline"),
        ("pipeline", "Y__bull_only", "Top20", "2021-01-01", 20.0, 0.55, "pipeline"),
    )

    flagged = _flag(frame, ["ablation_2022", "ablation_2021", "pipeline"])

    assert bool(flagged.loc[("pipeline", "X__bull_only", "Top20"), ALL_TRIALS]) is False
    assert flagged.loc[("pipeline", "X__bull_only", "Top20"), "duplicate_of"] == "ablation_2021:X_bull__none"
    assert bool(flagged.loc[("pipeline", "Y__bull_only", "Top20"), ALL_TRIALS]) is True
    assert int(flagged[ALL_TRIALS].sum()) == 2


def test_out_of_sample_meta_strategy_counts_overall_but_not_in_the_2022_scope() -> None:
    frame = _trials(("walk_forward", "select_best", "Top20", "2023-01-01", 20.0, 1.3, "walk_forward"))

    flagged = flag_new_configurations(frame, ["walk_forward"])

    assert flagged[ALL_TRIALS].tolist() == [True]
    assert flagged[TOP20_2022_TRIALS].tolist() == [False]


def test_study_missing_from_the_processing_order_is_an_error() -> None:
    frame = _trials(("unlisted", "a", "Top20", "2022-01-01", 20.0, 1.0, "unlisted"))

    with pytest.raises(ValueError, match="unlisted"):
        flag_new_configurations(frame, ["listed"])


def test_primary_cost_is_nearest_20_bps_covering_every_configuration() -> None:
    rows = pd.DataFrame(
        [
            ("full_grid", "a", 2.0, False), ("full_grid", "b", 2.0, False),
            ("full_grid", "a", 20.0, False), ("full_grid", "b", 20.0, False),
            ("full_grid", "a", 50.0, False),
            # 20 bps covers only the finalist, so the sweep cost wins.
            ("sweep", "a", 10.0, False), ("sweep", "b", 10.0, False), ("sweep", "a", 20.0, False),
            ("tie", "a", 15.0, False), ("tie", "a", 25.0, False),
            ("benchmark_ignored", "a", 2.0, False), ("benchmark_ignored", "btc", 20.0, True),
        ],
        columns=["study", "config_id", "cost_bps", "benchmark"],
    ).assign(universe="Top20")

    assert primary_costs(rows) == {"full_grid": 20.0, "sweep": 10.0, "tie": 25.0, "benchmark_ignored": 2.0}


def test_scope_summary_counts_unscored_trials_and_uses_the_sample_std() -> None:
    sharpes = pd.Series([0.2, 0.5, 0.5, 1.1])

    summary = scope_summary(sharpes, unscored=3, description="test scope")

    assert summary["n_trials"] == 7
    assert summary["n_with_sharpe"] == 4
    assert summary["n_distinct_sharpe_values"] == 3
    assert summary["sharpe_std_annualized"] == pytest.approx(float(np.std([0.2, 0.5, 0.5, 1.1], ddof=1)))
    assert summary["sharpe_std_per_period"] == pytest.approx(summary["sharpe_std_annualized"] / math.sqrt(365.0))
    assert summary["filter"] == "test scope"
    with pytest.raises(ValueError, match="two"):
        scope_summary(pd.Series([0.4]), unscored=0, description="too small")


def test_recorder_skips_exact_repeats_and_rejects_conflicts_or_missing_sharpe() -> None:
    recorder = TrialRecorder()
    kwargs = {"source": "s.csv", "column": "sharpe", "family": "f"}
    window = ("2022-01-01", "2026-09-21")

    recorder.add("study", "a", window, 20, "Top20", 1.0, **kwargs)
    recorder.add("study", "a", window, 20, "Top20", 1.0, **kwargs)
    recorder.add("study", "a", window, 20, "Top50", 0.5, **kwargs)

    assert len(recorder.rows) == 2
    assert recorder.repeated_rows == 1
    with pytest.raises(ValueError, match="conflicting"):
        recorder.add("study", "a", window, 20, "Top20", 1.1, **kwargs)
    with pytest.raises(ValueError, match="non-finite"):
        recorder.add("study", "b", window, 20, "Top20", float("nan"), **kwargs)


def test_unclassified_report_directories_are_listed() -> None:
    dirs = ["latest", "app_runs", "phase_momentum_live", "brand_new_study_2022"]

    assert unclassified_report_dirs(dirs, used_dirs={"latest"}) == ["brand_new_study_2022"]


def test_research_md_configurations_report_missing_anchor_text() -> None:
    configurations, anchors = research_md_configurations("MA50/confirm1–3 为 12.15x–13.79x")

    assert len(configurations) == 11
    assert all(item.window_start == "2022-01-01" and item.universe == "Top20" for item in configurations)
    assert anchors["MA50/confirm1–3"] is True
    assert anchors["MA200/confirm1–3"] is False


def test_parameter_values_format_stably() -> None:
    assert _fmt(14.0) == "14"
    assert _fmt(np.int64(3)) == "3"
    assert _fmt(0.5) == "0.5"
    assert _fmt(float("nan")) == "nan"
    assert _fmt("strict") == "strict"


# --------------------------------------------------------------------------- pre-registered ledger


class _FakeSources:
    """Minimal stand-in for ``Sources`` reading files under a temporary repo root."""

    def __init__(self, root) -> None:  # type: ignore[no-untyped-def]
        self.repo_root = root
        self.read: dict[str, dict[str, str]] = {}

    def csv(self, relative: str, **kwargs: object) -> pd.DataFrame:
        self.read[relative] = {"origin": "test", "sha256": ""}
        return pd.read_csv(self.repo_root / relative, **kwargs)  # type: ignore[arg-type]


def _write_ledger(root, rows: list[dict[str, str]]) -> None:  # type: ignore[no-untyped-def]
    from scripts.build_trial_inventory import PREREGISTERED_LEDGER
    from scripts.run_phase_momentum_hypotheses import LEDGER_COLUMNS

    path = root / PREREGISTERED_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{column: row.get(column, "") for column in LEDGER_COLUMNS} for row in rows]).to_csv(
        path, index=False
    )


def _registration(trial_id: str, counts: bool) -> dict[str, str]:
    spec = '{"main_window":["2022-01-01","2026-09-21"],"universe":"strict point-in-time CMC Top20"}'
    return {
        "trial_id": trial_id,
        "hypothesis": trial_id.rsplit("-", 1)[-1],
        "role": "primary" if counts else "baseline",
        "counts_as_trial": str(counts),
        "spec": spec,
        "status": "registered",
    }


def test_registered_ledger_trials_count_without_a_sharpe_until_they_run(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from scripts.build_trial_inventory import PREREGISTERED_STUDY, _load_preregistered_lane

    _write_ledger(
        tmp_path,
        [
            _registration("PR-B", False),
            _registration("PR-H2", True),
            _registration("PR-H3", True),
            _registration("PR-H4", True),
            _registration("PR-D50", False),
        ],
    )
    recorder = TrialRecorder()

    unscored = _load_preregistered_lane(_FakeSources(tmp_path), recorder)

    assert recorder.rows == []
    assert sorted(item.config_id for item in unscored) == ["PR-H2", "PR-H3", "PR-H4"]
    assert all(item.study == PREREGISTERED_STUDY for item in unscored)
    assert all(item.universe == "Top20" and item.window_start == "2022-01-01" for item in unscored)


def test_completed_ledger_trials_enter_with_their_lag0_20bps_sharpe(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from scripts.build_trial_inventory import PREREGISTERED_STUDY, _load_preregistered_lane

    result = "reports/phase_momentum_hypotheses_2026_10/runs.csv"
    (tmp_path / result).parent.mkdir(parents=True)
    runs = pd.DataFrame(
        [
            (trial, window, fill, cost, sharpe)
            for trial, sharpe in (("PR-H2", 1.2), ("PR-H3", 1.3), ("PR-H4", 1.1), ("PR-B", 1.43))
            for window in ("main", "stress")
            for fill in ("lag0", "lag1", "h3_day_close")
            for cost in (2.0, 20.0)
            for value in [sharpe + (0.0 if (window, fill, cost) == ("main", "lag0", 20.0) else 0.5)]
        ],
        columns=["trial_id", "window", "fill", "cost_bps", "sharpe"],
    )
    runs.to_csv(tmp_path / result, index=False)
    completed = [
        {"trial_id": trial, "status": "completed", "result_path": result}
        for trial in ("PR-B", "PR-H2", "PR-H3", "PR-H4")
    ]
    _write_ledger(
        tmp_path,
        [_registration("PR-B", False), _registration("PR-H2", True), _registration("PR-H3", True),
         _registration("PR-H4", True), *completed],
    )
    recorder = TrialRecorder()

    unscored = _load_preregistered_lane(_FakeSources(tmp_path), recorder)

    assert unscored == []
    frame = recorder.frame().set_index("config_id")
    assert sorted(frame.index) == ["PR-H2", "PR-H3", "PR-H4"]
    assert frame.loc["PR-H3", "annualized_sharpe"] == pytest.approx(1.3)
    assert set(frame["study"]) == {PREREGISTERED_STUDY}
    assert set(frame["cost_bps"]) == {20.0}
    assert set(frame["window_start"]) == {"2022-01-01"}


def test_missing_ledger_leaves_the_inventory_unchanged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from scripts.build_trial_inventory import _load_preregistered_lane

    recorder = TrialRecorder()

    assert _load_preregistered_lane(_FakeSources(tmp_path), recorder) == []
    assert recorder.rows == []


def test_preregistered_trials_are_new_configurations_in_the_top20_2022_scope() -> None:
    from scripts.build_trial_inventory import PREREGISTERED_STUDY, PROCESSING_ORDER, TOP20_2022_ORDER

    assert PREREGISTERED_STUDY in TOP20_2022_ORDER
    frame = _trials(
        ("phase_momentum_2022", "primary", "Top20", "2022-01-01", 20.0, 1.43, "phase_momentum_2022"),
        (PREREGISTERED_STUDY, "PR-H2", "Top20", "2022-01-01", 20.0, 1.2, PREREGISTERED_STUDY),
        (PREREGISTERED_STUDY, "PR-H3", "Top20", "2022-01-01", 20.0, 1.3, PREREGISTERED_STUDY),
    )

    flagged = _flag(frame, list(PROCESSING_ORDER))

    assert bool(flagged.loc[(PREREGISTERED_STUDY, "PR-H2", "Top20"), TOP20_2022_TRIALS])
    assert int(flagged[TOP20_2022_TRIALS].sum()) == 3
