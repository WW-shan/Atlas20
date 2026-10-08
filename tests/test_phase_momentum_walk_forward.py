from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_phase_momentum_walk_forward import PRE_SPECIFIED_POOL, _candidate_pool, _summary_row


def test_pool_is_the_pre_specified_neighbourhood() -> None:
    assert PRE_SPECIFIED_POOL[0] == "primary"
    assert len(PRE_SPECIFIED_POOL) == 25
    assert not any(name.startswith(("trend_", "parameter_ensemble")) for name in PRE_SPECIFIED_POOL)


def test_candidate_pool_refuses_missing_candidates() -> None:
    returns = pd.DataFrame({"primary": [0.01, 0.02]})

    with pytest.raises(ValueError, match="rebalance_1d"):
        _candidate_pool(returns, ("primary", "rebalance_1d"))


def test_candidate_pool_counts_identical_series_once() -> None:
    returns = pd.DataFrame(
        {
            "primary": [0.01, -0.02, 0.03],
            "fixed_stop_40": [0.01, -0.02, 0.03],
            "rebalance_1d": [0.02, 0.0, 0.01],
            "trend_50": [0.05, 0.05, 0.05],
        }
    )

    pool, duplicates = _candidate_pool(returns, ("primary", "fixed_stop_40", "rebalance_1d"))

    assert pool == ["primary", "rebalance_1d"]
    assert duplicates == {"fixed_stop_40": "primary"}


def test_summary_row_counts_every_chained_day_and_the_starting_capital() -> None:
    # A chained out-of-sample path has no engine "day 0": both days are real.
    dates = pd.date_range("2023-01-01", periods=2, freq="D")

    row = _summary_row("chain", pd.Series([-0.10, 0.05], index=dates))

    assert row["days"] == 2
    assert row["start"] == dates[0]
    assert row["multiple"] == pytest.approx(0.945)
    assert row["cagr"] == pytest.approx(0.945 ** (365 / 2) - 1.0)
    assert row["max_drawdown"] == pytest.approx(-0.10)
