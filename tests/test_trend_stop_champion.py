from __future__ import annotations

import pandas as pd

from scripts.run_trend_stop_champion import confirmed_above_ma


def test_confirmed_above_ma_waits_for_consecutive_breaks() -> None:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    price = pd.DataFrame(
        {"a": [10.0, 11.0, 12.0, 11.0, 10.0, 9.0, 8.0, 9.0, 10.0, 11.0]},
        index=dates,
    )

    trend = confirmed_above_ma(price, window=3, confirm_days=3)

    # The moving average warms up over the first three observations.  The
    # confirmed exit cannot fire until three consecutive closes are below it.
    assert bool(trend.loc[dates[3], "a"]) is True
    assert bool(trend.loc[dates[4], "a"]) is True
    assert bool(trend.loc[dates[5], "a"]) is False
