from __future__ import annotations

import pandas as pd
import pytest


def test_funding_pnl_sign_for_long_and_short() -> None:
    from scripts.run_ls57_churn_overlay_funding import funding_pnl

    index = pd.date_range("2022-01-01", periods=1, tz="UTC")
    weights = pd.DataFrame({"bitcoin": [0.5], "alt": [-0.5]}, index=index)
    rates = pd.DataFrame({"bitcoin": [0.01], "alt": [0.01]}, index=index)

    result = funding_pnl(weights, rates)

    assert result.iloc[0] == pytest.approx(0.0)


def test_funding_pnl_charges_positive_rate_to_long() -> None:
    from scripts.run_ls57_churn_overlay_funding import funding_pnl

    index = pd.date_range("2022-01-01", periods=1, tz="UTC")
    weights = pd.DataFrame({"bitcoin": [1.0]}, index=index)
    rates = pd.DataFrame({"bitcoin": [0.01]}, index=index)

    assert funding_pnl(weights, rates).iloc[0] == pytest.approx(-0.01)
