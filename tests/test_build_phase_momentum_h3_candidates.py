from __future__ import annotations

import scripts.build_phase_momentum_h3_candidates as build_h3
from scripts.run_phase_momentum_hypotheses import trial_by_id


def test_h3_columns_are_registered_breadth_blends() -> None:
    # The extended PBO matrix must append the pre-registered H3 blend and its
    # 0.45/0.55 neighbourhood, not hand-written specs.
    assert build_h3.H3_COLUMNS == {
        "h3_breadth_045": "PR2026-10-H3-T45",
        "h3_breadth_050": "PR2026-10-H3",
        "h3_breadth_055": "PR2026-10-H3-T55",
    }
    for column, trial_id in build_h3.H3_COLUMNS.items():
        trial = trial_by_id(trial_id)
        assert len(trial.books) == 2
        book_a, book_b = trial.books
        # book A is the champion; book B adds the breadth co-gate.
        assert book_a[0].breadth_threshold is None
        assert book_b[0].breadth_threshold == {
            "h3_breadth_045": 0.45,
            "h3_breadth_050": 0.50,
            "h3_breadth_055": 0.55,
        }[column]
        assert book_a[1] == book_b[1] == 0.5
