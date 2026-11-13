from __future__ import annotations

import pandas as pd
import pytest


def test_asset_trend_filter_zeroes_only_legs_below_ma() -> None:
    from scripts.run_ls85_asset_trend_filter import filter_long_targets_by_asset_ma

    dates = pd.date_range("2022-01-01", periods=230, freq="1D", tz="UTC")
    prices = pd.DataFrame(
        {
            "a": pd.Series(range(100, 330), index=dates, dtype=float),
            "b": [100.0] * 229 + [1.0],
        },
        index=dates,
    )
    prices.loc[dates[220], "b"] = 1.0
    targets = {
        dates[220]: pd.Series({"a": 0.6, "b": 0.4}),
    }

    filtered, audit = filter_long_targets_by_asset_ma(
        targets,
        prices=prices,
        ma_days=200,
    )

    assert filtered[dates[220]].to_dict() == {"a": 0.6}
    assert audit.iloc[0]["filtered_weight"] == pytest.approx(0.4)
    assert audit.iloc[0]["cash_weight"] == pytest.approx(0.4)


def test_asset_trend_filter_keeps_leg_when_ma_missing() -> None:
    from scripts.run_ls85_asset_trend_filter import filter_long_targets_by_asset_ma

    dates = pd.date_range("2022-01-01", periods=10, freq="1D", tz="UTC")
    prices = pd.DataFrame({"a": range(10)}, index=dates, dtype=float)
    targets = {dates[8]: pd.Series({"a": 0.5})}

    filtered, audit = filter_long_targets_by_asset_ma(
        targets,
        prices=prices,
        ma_days=200,
    )

    assert filtered[dates[8]].to_dict() == {"a": 0.5}
    assert audit.iloc[0]["missing_ma_count"] == 1
