from pathlib import Path

from scripts import execute_live_plan, plan_live_execution, send_derivatives_signal
from scripts.run_h5_regime_short_router import LS45_CANDIDATE_ID


def test_live_defaults_are_pinned_to_ls45_g125() -> None:
    assert plan_live_execution.TRACKED_SPEC == LS45_CANDIDATE_ID
    assert send_derivatives_signal.TRACKED_SPEC == LS45_CANDIDATE_ID
    assert plan_live_execution.DEFAULT_TARGETS_FILE == Path(
        "reports/ls45_live_g125/oos_targets.csv"
    )
    assert execute_live_plan.DEFAULT_MANIFEST_FILE == Path(
        "reports/ls45_live_g125/manifest.json"
    )
    assert plan_live_execution.DEFAULT_SYMBOL_MAP == Path(
        "data/raw/bitget_derivatives/merged_oos_20261112/symbol_map.csv"
    )


def test_ls45_live_books_do_not_reuse_the_old_l125_ledger() -> None:
    assert "derivatives_track_oos_2026" not in str(execute_live_plan.DEFAULT_JOURNAL_FILE)
    assert "derivatives_track_oos_2026" not in str(execute_live_plan.DEFAULT_JSON_OUT)
    assert execute_live_plan.DEFAULT_STATE_FILE != Path(
        "data/derivatives_execution_state.json"
    )
