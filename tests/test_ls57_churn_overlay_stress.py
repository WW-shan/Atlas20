from __future__ import annotations

import pandas as pd
import pytest


def test_adverse_funding_charges_both_sides_under_any_rate_sign() -> None:
    from scripts.run_ls57_churn_overlay_stress import adverse_funding_pnl

    index = pd.date_range("2022-01-01", periods=2, tz="UTC")
    weights = pd.DataFrame(
        {"bitcoin": [1.0, 1.0], "alt": [-1.0, -1.0]},
        index=index,
    )
    rates = pd.DataFrame(
        {"bitcoin": [0.01, -0.01], "alt": [-0.01, 0.01]},
        index=index,
    )

    result = adverse_funding_pnl(weights, rates, multiplier=3.0)

    assert result.tolist() == pytest.approx([-0.06, -0.06])
