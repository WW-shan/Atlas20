from __future__ import annotations

import pandas as pd

from scripts.run_top20_convex_validation import (
    CandidateDefinition,
    build_candidate_definitions,
    compute_raw_convexity_score,
    compute_robust_convexity_score,
    select_validation_candidates,
)


def test_candidate_definitions_are_bounded_and_include_discovery_lane() -> None:
    candidates = build_candidate_definitions()
    family_ids = {candidate.family_id for candidate in candidates}

    assert isinstance(candidates[0], CandidateDefinition)
    assert "leader_momentum" in family_ids
    assert "ctrend_lite" in family_ids
    assert "champion_ablation" in family_ids
    assert len(candidates) < 2_500
    assert len({candidate.candidate_id for candidate in candidates}) == len(candidates)


def test_raw_convexity_score_prefers_higher_multiple_with_drawdown_penalty() -> None:
    strong = pd.Series(
        {
            "multiple": 100.0,
            "best_rolling_5y_multiple": 120.0,
            "hundred_x_hit_rate_5y": 0.50,
            "max_drawdown": -0.60,
        }
    )
    weak = pd.Series(
        {
            "multiple": 20.0,
            "best_rolling_5y_multiple": 25.0,
            "hundred_x_hit_rate_5y": 0.05,
            "max_drawdown": -0.50,
        }
    )

    assert compute_raw_convexity_score(strong) > compute_raw_convexity_score(weak)


def test_robust_convexity_score_penalizes_fragile_costly_candidate() -> None:
    robust = pd.Series(
        {
            "median_rolling_start_multiple": 40.0,
            "hundred_x_hit_rate_5y": 0.25,
            "max_drawdown": -0.55,
            "cost_survival_100bps": 0.70,
            "stability_score": 0.80,
            "annualized_turnover": 20.0,
        }
    )
    fragile = pd.Series(
        {
            "median_rolling_start_multiple": 60.0,
            "hundred_x_hit_rate_5y": 0.25,
            "max_drawdown": -0.78,
            "cost_survival_100bps": 0.20,
            "stability_score": 0.10,
            "annualized_turnover": 60.0,
        }
    )

    assert compute_robust_convexity_score(robust) > compute_robust_convexity_score(fragile)


def test_select_validation_candidates_keeps_champion_and_deduplicates() -> None:
    frame = pd.DataFrame(
        [
            {
                "candidate_id": "champion",
                "raw_convexity_score": 1.0,
                "robust_convexity_score": 1.0,
                "multiple": 2.0,
            },
            {
                "candidate_id": "raw_best",
                "raw_convexity_score": 5.0,
                "robust_convexity_score": 1.0,
                "multiple": 50.0,
            },
            {
                "candidate_id": "robust_best",
                "raw_convexity_score": 1.0,
                "robust_convexity_score": 5.0,
                "multiple": 30.0,
            },
            {
                "candidate_id": "also_good",
                "raw_convexity_score": 4.0,
                "robust_convexity_score": 4.0,
                "multiple": 26.0,
            },
        ]
    )

    selected = select_validation_candidates(
        frame,
        champion_candidate_id="champion",
        max_validation_candidates=3,
        min_multiple_for_validation=25.0,
    )

    assert selected == ["champion", "raw_best", "robust_best"]
