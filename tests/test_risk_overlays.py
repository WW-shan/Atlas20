from __future__ import annotations

import pandas as pd

from atlas20.signals.risk import btc_above_trailing_price
from atlas20.strategies.overlays import (
    apply_daily_asset_stop_overlay,
    apply_daily_risk_overlay,
)


def test_btc_trailing_price_confirmed_signal_requires_persistence() -> None:
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    price = pd.DataFrame({"bitcoin": [100, 100, 99, 98, 101, 102]}, index=dates, dtype=float)
    risk_on = btc_above_trailing_price(price, lookback_days=1, confirm_days=2)
    assert bool(risk_on.loc[dates[2]]) is True
    assert bool(risk_on.loc[dates[3]]) is False
    assert bool(risk_on.loc[dates[4]]) is False
    assert bool(risk_on.loc[dates[5]]) is True


def test_apply_daily_risk_overlay_adds_forced_exit_and_blocks_reentry_until_rebalance() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    base_targets = {
        dates[0]: pd.Series({"bitcoin": 1.0}),
        dates[3]: pd.Series({"bitcoin": 1.0}),
    }
    risk_on = pd.Series([True, False, False, True, True], index=dates)

    adjusted = apply_daily_risk_overlay(base_targets, risk_on)

    assert adjusted[dates[0]].iloc[0] == 1.0
    assert adjusted[dates[1]].sum() == 0.0
    assert adjusted[dates[3]].iloc[0] == 1.0


def test_apply_daily_risk_overlay_can_reenter_immediately_when_enabled() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    base_targets = {
        dates[0]: pd.Series({"bitcoin": 1.0}),
        dates[3]: pd.Series({"bitcoin": 0.5, "ethereum": 0.5}),
    }
    risk_on = pd.Series([True, False, True, True, True], index=dates)

    adjusted = apply_daily_risk_overlay(base_targets, risk_on, immediate_reentry=True)

    assert adjusted[dates[1]].sum() == 0.0
    assert adjusted[dates[2]].iloc[0] == 1.0


def test_apply_daily_risk_overlay_can_park_in_btc_and_seed_initial_position() -> None:
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    base_targets = {dates[2]: pd.Series({"ethereum": 1.0})}
    risk_on = pd.Series([True, False, False, True], index=dates)

    adjusted = apply_daily_risk_overlay(
        base_targets,
        risk_on,
        risk_off_target=pd.Series({"bitcoin": 1.0}),
        initial_target=pd.Series({"bitcoin": 1.0}),
    )

    assert adjusted[dates[0]]["bitcoin"] == 1.0
    assert adjusted[dates[1]]["bitcoin"] == 1.0
    assert adjusted[dates[2]]["bitcoin"] == 1.0
    assert adjusted[dates[2]].get("ethereum", 0.0) == 0.0


def test_daily_asset_stop_exits_between_rebalances_and_waits_for_next_schedule() -> None:
    dates = pd.date_range("2024-01-01", periods=7, freq="D")
    base_targets = {
        dates[0]: pd.Series({"a": 0.5, "b": 0.5}),
        dates[4]: pd.Series({"a": 0.5, "b": 0.5}),
    }
    trend = pd.DataFrame(
        {
            "a": [True, True, False, False, True, True, True],
            "b": [True, True, True, True, True, True, True],
        },
        index=dates,
    )

    adjusted = apply_daily_asset_stop_overlay(base_targets, trend)

    assert adjusted[dates[0]]["a"] == 0.5
    assert adjusted[dates[2]].get("a", 0.0) == 0.0
    assert adjusted[dates[2]]["b"] == 1.0
    assert adjusted[dates[4]]["a"] == 0.5
    assert adjusted[dates[4]]["b"] == 0.5


def test_daily_asset_stop_filters_initial_entries_and_can_go_fully_to_cash() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    base_targets = {dates[0]: pd.Series({"a": 0.5, "b": 0.5})}
    trend = pd.DataFrame(
        {
            "a": [False, False, False],
            "b": [False, False, False],
        },
        index=dates,
    )

    adjusted = apply_daily_asset_stop_overlay(base_targets, trend)

    assert adjusted[dates[0]].empty
