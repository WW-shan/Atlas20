"""Tests for the persisted bull-offense finalist research script."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.run_bull_offense_finalist import (
    FINALIST,
    SWEEP_ASSET_MA,
    SWEEP_BTC_MA,
    SWEEP_HOLD,
    SWEEP_LOOKBACK,
    SWEEP_TARGET_VOL,
    _neighbourhood_stats,
    _parse_cost_levels,
    _rolling_starts,
    _vol_exposure,
)


def test_finalist_cell_is_inside_the_swept_grid() -> None:
    """The champion must be a cell the sweep actually tested.

    If the documented finalist drifted outside the enumerated grid, the
    plateau/neighbour evidence in the report would silently describe a
    different strategy than the one being deep-dived.
    """
    assert FINALIST["hold_count"] in SWEEP_HOLD
    assert FINALIST["lookback"] in SWEEP_LOOKBACK
    assert FINALIST["btc_trend_ma"] in SWEEP_BTC_MA
    assert FINALIST["asset_stop_ma"] in SWEEP_ASSET_MA
    assert FINALIST["target_vol"] in SWEEP_TARGET_VOL


def test_finalist_is_unlevered() -> None:
    """Research is unlevered by mandate; the champion must not exceed 1x."""
    assert FINALIST["hold_count"] >= 1
    assert FINALIST["target_vol"] > 0


def _vol_frame(values: dict[str, list[float]]) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(next(iter(values.values()))), freq="D")
    return pd.DataFrame(values, index=index)


def test_vol_exposure_scales_down_but_never_levers_up() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    vol = pd.DataFrame({"aaa": [0.4, 2.0], "bbb": [np.nan, 0.4]}, index=index)
    targets = {
        index[0]: pd.Series({"aaa": 1.0}),
        index[1]: pd.Series({"aaa": 1.0}),
    }

    exposure = _vol_exposure(targets, vol, target_vol=0.8)

    # 0.8 / 0.4 = 2.0 would be leverage, so it is capped at 1.0.
    assert exposure[index[0]] == pytest.approx(1.0)
    # 0.8 / 2.0 = 0.4 de-risks.
    assert exposure[index[1]] == pytest.approx(0.4)


def test_vol_exposure_is_zero_for_flat_and_missing_targets() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    vol = pd.DataFrame({"aaa": [0.5, 0.5, 0.5]}, index=index)
    targets = {
        index[0]: pd.Series(dtype=float),
        index[1]: pd.Series({"aaa": 1.0}),
        # index[2] is deliberately absent from the vol frame.
    }

    exposure = _vol_exposure(targets, vol.loc[index[:2]], target_vol=0.8)

    assert exposure[index[0]] == 0.0
    assert exposure[index[1]] == pytest.approx(1.0)


def test_rolling_starts_compares_strategy_against_btc() -> None:
    index = pd.date_range("2024-01-01", periods=400, freq="D")
    strategy = pd.Series(0.002, index=index)
    btc = pd.Series(0.001, index=index)

    rows = _rolling_starts(strategy, btc, cost_bps=20.0, min_days=180)

    assert rows, "expected at least one rolling window"
    first = rows[0]
    assert first["cost_bps"] == 20.0
    assert first["multiple"] > first["btc_multiple"]
    assert first["ratio"] == pytest.approx(first["multiple"] / first["btc_multiple"])
    assert first["days"] >= 180
    assert all(row["ratio"] > 1.0 for row in rows)


def test_neighbourhood_stats_flags_isolated_cells() -> None:
    """A cell whose neighbours all fail must not look like a plateau."""
    rows = []
    for hold in (1, 2):
        for lookback in (21, 30):
            rows.append(
                {
                    "hold_count": hold,
                    "lookback": lookback,
                    "btc_ma": 50,
                    "asset_ma": 50,
                    "target_vol": 0.8,
                    # Only the (1, 21) cell beats BTC.
                    "beats_btc_total": bool(hold == 1 and lookback == 21),
                    "sharpe": 2.0 if (hold == 1 and lookback == 21) else 0.1,
                    "total_return": 10.0 if (hold == 1 and lookback == 21) else 0.2,
                }
            )
    sweep = pd.DataFrame(rows)

    scored = _neighbourhood_stats(sweep)
    isolated = scored[(scored["hold_count"] == 1) & (scored["lookback"] == 21)].iloc[0]
    # Every neighbour of (1, 21) is a loser, so the plateau evidence is weak.
    assert isolated["neighbour_beats_share"] == 0.0
    assert isolated["plateau_score"] < 1.0

    # (2, 21) neighbours (2, 30) and (1, 21); exactly one of them wins.
    mixed = scored[(scored["hold_count"] == 2) & (scored["lookback"] == 21)].iloc[0]
    assert mixed["neighbour_beats_share"] == pytest.approx(0.5)

    # (2, 30) neighbours (2, 21) and (1, 30); both lose.
    interior = scored[(scored["hold_count"] == 2) & (scored["lookback"] == 30)].iloc[0]
    assert interior["neighbour_beats_share"] == 0.0


def test_neighbourhood_stats_handles_empty_sweep() -> None:
    empty = pd.DataFrame()
    assert _neighbourhood_stats(empty).empty


def test_parse_cost_levels_accepts_real_world_single_side_costs() -> None:
    """A taker fee net of rebate plus slippage is a normal single-side input."""
    assert _parse_cost_levels("5,8,10.5") == (5.0, 8.0, 10.5)
    assert _parse_cost_levels(" 11 ") == (11.0,)


def test_parse_cost_levels_rejects_empty_and_negative() -> None:
    with pytest.raises(ValueError):
        _parse_cost_levels("")
    with pytest.raises(ValueError):
        _parse_cost_levels("-1")
    with pytest.raises(ValueError):
        _parse_cost_levels("abc")
