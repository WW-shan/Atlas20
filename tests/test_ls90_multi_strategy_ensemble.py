from __future__ import annotations

import pandas as pd
import pytest


def test_no_rebalance_ensemble_uses_compounded_subaccounts() -> None:
    from scripts.run_ls90_multi_strategy_ensemble import combine_no_rebalance

    index = pd.date_range("2022-01-01", periods=3, freq="1D", tz="UTC")
    returns = pd.DataFrame(
        {"a": [0.0, 0.10, 0.0], "b": [0.0, 0.0, 0.10]},
        index=index,
    )

    portfolio = combine_no_rebalance(returns, weights={"a": 0.5, "b": 0.5})

    assert portfolio.iloc[0] == pytest.approx(0.0)
    assert portfolio.iloc[1] == pytest.approx(0.05)
    assert portfolio.iloc[2] == pytest.approx(1.10 / 1.05 - 1.0)


def test_no_rebalance_ensemble_rejects_missing_weights() -> None:
    from scripts.run_ls90_multi_strategy_ensemble import combine_no_rebalance

    returns = pd.DataFrame({"a": [0.0, 0.01]}, index=pd.date_range("2022-01-01", periods=2, tz="UTC"))
    with pytest.raises(ValueError, match="weights"):
        combine_no_rebalance(returns, weights={"a": 1.0, "b": 0.0})
