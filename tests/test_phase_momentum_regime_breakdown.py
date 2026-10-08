from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_phase_momentum_regime_breakdown import _lagged_regime_labels, _regime_table


def test_each_return_is_labelled_with_the_previous_close_regime() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    bull = pd.Series([True, True, False, False], index=index)

    labels = _lagged_regime_labels(bull, index[1:])

    # The 2024-01-03 close flips the state, but that close already contains
    # 2024-01-03's return, so that return still belongs to the bull state.
    assert labels.tolist() == [True, True, False]
    assert labels.index.equals(index[1:])


def test_lagged_regime_labels_refuse_a_window_without_prior_state() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    bull = pd.Series([True, True, False], index=index)

    with pytest.raises(ValueError, match="missing"):
        _lagged_regime_labels(bull, index)


def test_regime_table_splits_bull_and_non_bull_periods() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    returns = {
        "strategy": pd.Series([0.10, 0.05, -0.02, 0.01], index=index),
        "BTC": pd.Series([0.04, 0.03, -0.01, 0.00], index=index),
    }
    bull = pd.Series([True, True, False, False], index=index)

    table = _regime_table(returns, bull).set_index(["strategy", "regime"])

    assert table.loc[("strategy", "bull"), "days"] == 2
    assert table.loc[("strategy", "bull"), "total_multiple"] == pytest.approx(1.155)
    assert table.loc[("strategy", "non_bull"), "days"] == 2
    assert table.loc[("strategy", "non_bull"), "total_multiple"] == pytest.approx(0.9898)
    assert table.loc[("BTC", "bull"), "days"] == 2
    assert table.loc[("BTC", "non_bull"), "days"] == 2
