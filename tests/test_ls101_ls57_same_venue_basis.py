from __future__ import annotations

import pandas as pd
import pytest


def test_combine_waits_for_first_complete_sleeve_day() -> None:
    from scripts.run_ls101_ls57_same_venue_basis import combine_ls57_same_venue_basis

    index = pd.date_range("2024-01-01", periods=3, tz="UTC")
    result = combine_ls57_same_venue_basis(
        ls57_returns=pd.Series([0.10, 0.00, 0.00], index=index),
        ls57_gross=pd.Series([0.45, 0.45, 1.45], index=index),
        basis_returns=pd.Series([0.00, 0.01, 0.01], index=index),
        basis_active=pd.Series([False, True, True], index=index),
        allocation=1.0,
        gross_cap=1.45,
        sleeve_gross=1.0,
        scale_cost_bps=10.0,
    )

    assert result["scale"].tolist() == pytest.approx([0.0, 1.0, 0.0])
    assert result["combined_return"].tolist() == pytest.approx([0.10, 0.009, -0.001])
    assert result["combined_gross"].tolist() == pytest.approx([0.45, 1.45, 1.45])


def test_combine_refuses_a_base_book_above_the_hard_cap() -> None:
    from scripts.run_ls101_ls57_same_venue_basis import combine_ls57_same_venue_basis

    index = pd.date_range("2024-01-01", periods=2, tz="UTC")
    with pytest.raises(ValueError, match="hard cap"):
        combine_ls57_same_venue_basis(
            ls57_returns=pd.Series([0.0, 0.0], index=index),
            ls57_gross=pd.Series([1.50, 1.50], index=index),
            basis_returns=pd.Series([0.0, 0.0], index=index),
            basis_active=pd.Series([True, True], index=index),
            allocation=1.0,
            gross_cap=1.45,
            sleeve_gross=1.0,
            scale_cost_bps=10.0,
        )
