from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _bars(prices: list[tuple[float, float]]) -> pd.DataFrame:
    times = pd.date_range("2026-01-01", periods=len(prices), freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "open_time": times,
            "open": [open_ for open_, _ in prices],
            "close": [close for _, close in prices],
        }
    )


def test_execution_future_return_enters_at_next_bar_open() -> None:
    from scripts.run_intraday_btc_leadlag_diagnostic import execution_future_return

    opens = pd.DataFrame({"A": [100.0, 110.0, 120.0, 130.0]})
    closes = pd.DataFrame({"A": [105.0, 115.0, 125.0, 140.0]})

    result = execution_future_return(opens, closes, horizon=2)

    assert result.iloc[0, 0] == pytest.approx(np.log(125.0 / 110.0))
    assert result.iloc[1, 0] == pytest.approx(np.log(140.0 / 120.0))


def test_signal_window_return_uses_only_prior_closed_bars() -> None:
    from scripts.run_intraday_btc_leadlag_diagnostic import signal_window_return

    closes = pd.DataFrame({"A": [100.0, 110.0, 121.0, 133.1]})

    result = signal_window_return(closes, window=2)

    assert result.iloc[2, 0] == pytest.approx(np.log(121.0 / 100.0))
    assert result.iloc[3, 0] == pytest.approx(np.log(133.1 / 110.0))


def test_cell_statistics_identifies_a_reversal_relationship() -> None:
    from scripts.run_intraday_btc_leadlag_diagnostic import _cell_statistics

    index = pd.date_range("2026-01-01", periods=2, freq="30min", tz="UTC")
    values = [0.01, 0.02, 0.03, 0.04, -0.01, -0.02, -0.03, -0.04]
    signal = pd.DataFrame(
        {f"A{index}": [value, -value] for index, value in enumerate(values)},
        index=index,
    )
    future = -signal
    membership = pd.DataFrame(True, index=index, columns=signal.columns)
    shock = pd.Series(2.0, index=index)

    result = _cell_statistics(
        signal_returns=signal,
        future_residual=future,
        membership=membership,
        shock_z=shock,
        horizon=1,
    )
    times, ic_values, spreads = result["all"]

    assert len(times) == 2
    assert ic_values == pytest.approx([-1.0, -1.0])
    assert spreads[0] > 0.0
    assert spreads[1] > 0.0


def test_period_rows_is_inclusive() -> None:
    from scripts.run_intraday_btc_leadlag_diagnostic import _period_rows

    index = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    rows = _period_rows(
        timestamp_index=index,
        ic_values=[-0.1, -0.2, 0.3],
        spread_values=[1.0, 2.0, -1.0],
        start="2026-01-01",
        end="2026-01-02",
    )

    assert rows["n_obs"] == 2
    assert rows["ic_mean"] == pytest.approx(-0.15)
    assert rows["contrarian_spread_mean_bps"] == pytest.approx(1.5)
