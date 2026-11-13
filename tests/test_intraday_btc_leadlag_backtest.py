from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _event() -> object:
    from scripts.run_intraday_btc_leadlag_backtest import TradeEvent

    return TradeEvent(
        variant_id="test",
        signal_position=0,
        entry_position=1,
        exit_position=2,
        signal_time=pd.Timestamp("2026-01-01", tz="UTC"),
        entry_time=pd.Timestamp("2026-01-01 00:30", tz="UTC"),
        exit_time=pd.Timestamp("2026-01-01 01:00", tz="UTC"),
        z=3.0,
        long_assets=("A",),
        short_assets=("B",),
    )


def test_select_cross_section_uses_low_and_high_gap() -> None:
    from scripts.run_intraday_btc_leadlag_backtest import _select_cross_section

    gap = pd.Series(
        {
            "A": -0.05,
            "B": -0.04,
            "C": -0.03,
            "D": -0.02,
            "E": -0.01,
            "F": 0.01,
            "G": 0.02,
            "H": 0.03,
            "I": 0.04,
            "J": 0.05,
        }
    )
    eligible = pd.Series(True, index=gap.index)

    selected = _select_cross_section(gap, eligible)

    assert selected is not None
    long_assets, short_assets = selected
    assert long_assets == ("A", "B")
    assert short_assets == ("I", "J")


def test_simulate_events_charges_entry_and_exit_and_reports_missing() -> None:
    from scripts.run_intraday_btc_leadlag_backtest import simulate_events

    index = pd.date_range("2026-01-01", periods=4, freq="30min", tz="UTC")
    bar_returns = pd.DataFrame(
        {
            "A": [0.0, 0.01, 0.01, 0.0],
            "B": [0.0, -0.01, -0.01, 0.0],
        },
        index=index,
    )
    result = simulate_events(
        events=[_event()],
        bar_returns=bar_returns,
        n_bars=len(index),
        future_bars=2,
        cost_bps_per_side=6.0,
    )

    # gross = 1/2, each leg is half of that. Two bars of +1% long and -1%
    # short produce +1% on the 0.5-gross tranche, less 2 x 6bps on that gross.
    per_bar = 0.5 * 0.01 - 0.5 * 0.0006
    assert result["bar_returns"].iloc[1] == pytest.approx(per_bar)
    assert result["bar_returns"].iloc[2] == pytest.approx(per_bar)
    assert result["turnover"] == pytest.approx(1.0)


def test_simulate_events_counts_missing_asset_return() -> None:
    from scripts.run_intraday_btc_leadlag_backtest import simulate_events

    index = pd.date_range("2026-01-01", periods=4, freq="30min", tz="UTC")
    bar_returns = pd.DataFrame(
        {
            "A": [0.0, np.nan, 0.01, 0.0],
            "B": [0.0, -0.01, -0.01, 0.0],
        },
        index=index,
    )
    result = simulate_events(
        events=[_event()],
        bar_returns=bar_returns,
        n_bars=len(index),
        future_bars=2,
        cost_bps_per_side=0.0,
    )

    assert result["missing_return_observations"] == 1


def test_simulate_events_supports_a_full_gross_single_tranche() -> None:
    from scripts.run_intraday_btc_leadlag_backtest import simulate_events

    index = pd.date_range("2026-01-01", periods=4, freq="30min", tz="UTC")
    bar_returns = pd.DataFrame(
        {
            "A": [0.0, 0.01, 0.01, 0.0],
            "B": [0.0, -0.01, -0.01, 0.0],
        },
        index=index,
    )

    result = simulate_events(
        events=[_event()],
        bar_returns=bar_returns,
        n_bars=len(index),
        future_bars=2,
        cost_bps_per_side=0.0,
        tranche_gross=1.0,
    )

    assert result["bar_returns"].iloc[1] == pytest.approx(0.01)
    assert result["bar_returns"].iloc[2] == pytest.approx(0.01)
    assert result["turnover"] == pytest.approx(2.0)


def test_tier_requires_shadow_risk_and_cost_margin() -> None:
    from scripts.run_intraday_btc_leadlag_backtest import _tier

    assert (
        _tier(
            full_6={"sharpe": 1.2, "max_drawdown": -0.2},
            discovery_6={"sharpe": 0.6},
            validation_6={"sharpe": 0.7},
            full_12={"multiple": 1.1},
        )
        == "candidate-for-shadow"
    )
    assert (
        _tier(
            full_6={"sharpe": 0.8, "max_drawdown": -0.2},
            discovery_6={"sharpe": 0.6},
            validation_6={"sharpe": 0.7},
            full_12={"multiple": 1.1},
        )
        == "watch"
    )
    assert (
        _tier(
            full_6={"sharpe": 1.2, "max_drawdown": -0.2},
            discovery_6={"sharpe": 0.6},
            validation_6={"sharpe": 0.7},
            full_12={"multiple": 0.9},
        )
        == "rejected-now"
    )
