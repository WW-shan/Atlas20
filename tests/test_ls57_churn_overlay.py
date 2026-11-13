from __future__ import annotations

import pandas as pd
import pytest


def test_scale_sleeve_respects_residual_gross() -> None:
    from scripts.run_ls57_churn_overlay import scale_sleeve_to_residual_gross

    index = pd.date_range("2022-01-01", periods=4, freq="D", tz="UTC")
    ls57_gross = pd.Series([1.3, 1.45, 0.2, 0.0], index=index)
    sleeve_gross = pd.Series([1.0, 1.0, 1.0, 1.0], index=index)

    frame = scale_sleeve_to_residual_gross(
        ls57_gross=ls57_gross,
        sleeve_gross=sleeve_gross,
        allocation=0.25,
        gross_cap=1.5,
    )

    assert frame["sleeve_scale"].tolist() == pytest.approx([0.2, 0.05, 0.25, 0.25])
    assert frame["combined_gross"].max() == pytest.approx(1.5)


def test_select_allocation_uses_largest_passing_not_best_raw_return() -> None:
    from scripts.run_ls57_churn_overlay import select_allocation

    summary = pd.DataFrame(
        [
            {"allocation": 0.10, "passes_all": True},
            {"allocation": 0.20, "passes_all": True},
            {"allocation": 0.25, "passes_all": False},
        ]
    )

    assert select_allocation(summary) == 0.20
