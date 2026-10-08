from __future__ import annotations

import scripts.build_phase_momentum_extended_candidates as build_ext
from scripts.run_phase_momentum_hypotheses import trial_by_id


def test_h3_columns_are_registered_breadth_blends() -> None:
    # The extended PBO matrix must append the pre-registered H3 blend and its
    # 0.45/0.55 neighbourhood, not hand-written specs.
    assert build_ext.H3_COLUMNS == {
        "h3_breadth_045": "PR2026-10-H3-T45",
        "h3_breadth_050": "PR2026-10-H3",
        "h3_breadth_055": "PR2026-10-H3-T55",
    }
    for column, trial_id in build_ext.H3_COLUMNS.items():
        trial = trial_by_id(trial_id)
        assert len(trial.books) == 2
        book_a, book_b = trial.books
        assert book_a[0].breadth_threshold is None
        assert book_b[0].breadth_threshold == {
            "h3_breadth_045": 0.45,
            "h3_breadth_050": 0.50,
            "h3_breadth_055": 0.55,
        }[column]
        assert book_a[1] == book_b[1] == 0.5


def test_h5_columns_are_registered_dispersion_blends() -> None:
    assert build_ext.H5_COLUMNS == {
        "h5_disp_p60": "PR2026-10-H5-T60",
        "h5_disp_p75": "PR2026-10-H5",
        "h5_disp_p90": "PR2026-10-H5-T90",
    }
    for column, trial_id in build_ext.H5_COLUMNS.items():
        trial = trial_by_id(trial_id)
        assert len(trial.books) == 2
        book_a, book_b = trial.books
        expected = {"h5_disp_p60": 0.60, "h5_disp_p75": 0.75, "h5_disp_p90": 0.90}[column]
        assert book_a[0].dispersion_target_percentile == expected
        # book B keeps the H3 breadth co-gate on top of the dispersion overlay.
        assert book_b[0].dispersion_target_percentile == expected
        assert book_b[0].breadth_threshold == 0.50
        assert book_a[1] == book_b[1] == 0.5


def test_appended_columns_cover_both_families() -> None:
    assert build_ext.APPENDED_COLUMNS == {**build_ext.H3_COLUMNS, **build_ext.H5_COLUMNS}
    assert build_ext.APPENDED_COLUMNS["h5_disp_p75"] == "PR2026-10-H5"
