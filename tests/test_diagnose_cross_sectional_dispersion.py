from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.diagnose_cross_sectional_dispersion import _dispersion, _forward, _membership


def _universe(index: pd.DatetimeIndex, coins: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"rebalance_date": date, "coin_id": coin} for date in index for coin in coins]
    )


def test_dispersion_is_the_cross_sectional_std_of_the_members() -> None:
    index = pd.date_range("2024-01-01", periods=6, freq="D")
    coins = [f"c{i}" for i in range(6)]
    # Every coin rises 1% a day except c0, which is flat.
    price = pd.DataFrame(
        {coin: 100.0 * (1.01 ** np.arange(len(index))) for coin in coins}, index=index
    )
    price["c0"] = 100.0
    members = _membership(_universe(index, coins), index)

    dispersion = _dispersion(price, index, members, kind="daily")

    # c0's daily return is 0; the other five share the same 1% return, so the
    # cross-sectional std of the day's returns is a known positive number.
    expected = float(pd.Series([0.0, 0.01, 0.01, 0.01, 0.01, 0.01]).std(ddof=1))
    assert dispersion.iloc[-1] == pytest.approx(expected)
    assert (dispersion.dropna() > 0).all()


def test_forward_return_spans_the_next_horizon() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D")
    returns = pd.Series([0.0, 0.10, 0.10, 0.10, 0.10], index=index)

    forward = _forward(returns, 2)

    # From 2024-01-01 the next two days compound to 1.10 * 1.10 - 1.
    assert forward.loc[index[0]] == pytest.approx(0.21)
    assert np.isnan(forward.loc[index[-1]])
