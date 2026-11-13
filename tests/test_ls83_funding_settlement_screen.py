from __future__ import annotations

import pandas as pd
import pytest


def _synthetic_prices() -> pd.DataFrame:
    index = pd.date_range("2022-01-01", periods=48, freq="1h", tz="UTC")
    assets = ["a", "b", "c", "d", "e", "f", "g", "h"]
    prices = pd.DataFrame(100.0, index=index, columns=assets)
    for asset in ["a", "b"]:
        prices.loc[index >= pd.Timestamp("2022-01-01T09:00:00Z"), asset] = 101.0
    for asset in ["g", "h"]:
        prices.loc[index >= pd.Timestamp("2022-01-01T09:00:00Z"), asset] = 99.0
    return prices


def test_settlement_screen_uses_only_00_and_post_signal_prices() -> None:
    from scripts.run_ls83_funding_settlement_screen import build_settlement_events

    prices = _synthetic_prices()
    funding = pd.DataFrame(
        [[0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08]],
        index=[pd.Timestamp("2022-01-01T00:00:00Z")],
        columns=prices.columns,
    )

    events = build_settlement_events(
        prices=prices,
        funding=funding,
        assets=list(prices.columns),
        horizons=(8,),
        entry_delay_hours=1,
    )

    assert len(events) == 1
    row = events.iloc[0]
    assert row["event_time"] == pd.Timestamp("2022-01-01T00:00:00Z")
    assert row["entry_time"] == pd.Timestamp("2022-01-01T01:00:00Z")
    assert row["exit_8h"] == pd.Timestamp("2022-01-01T09:00:00Z")
    assert row["long_assets"] == "a,b"
    assert row["short_assets"] == "g,h"
    assert row["spread_8h"] == pytest.approx(0.02)


def test_settlement_screen_skips_missing_exact_exit() -> None:
    from scripts.run_ls83_funding_settlement_screen import build_settlement_events

    prices = _synthetic_prices().drop(pd.Timestamp("2022-01-01T09:00:00Z"))
    funding = pd.DataFrame(
        [[0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08]],
        index=[pd.Timestamp("2022-01-01T00:00:00Z")],
        columns=prices.columns,
    )

    events = build_settlement_events(
        prices=prices,
        funding=funding,
        assets=list(prices.columns),
        horizons=(8,),
        entry_delay_hours=1,
    )

    assert events.empty


def test_settlement_screen_newyey_west_t_is_finite() -> None:
    from scripts.run_ls83_funding_settlement_screen import newey_west_t

    values = pd.Series([0.01, 0.02, -0.01, 0.03, 0.00, 0.01])
    assert abs(newey_west_t(values, lags=2)) < 10.0
