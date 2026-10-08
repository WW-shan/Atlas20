from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_momentum_flow_states import (
    FLOW_STATE_COLUMNS,
    _ratio_to_median,
    _verdicts,
    flow_state_frame,
    information_table,
    monthly_frame,
    separation_table,
    tercile_table,
)


@dataclass
class _Market:
    returns: pd.DataFrame
    volume: pd.DataFrame
    market_cap: pd.DataFrame


def _synthetic(days: int = 300, coins: int = 6):
    index = pd.date_range("2024-01-01", periods=days, freq="D")
    columns = [f"coin{number}" for number in range(coins)]
    columns[0] = "bitcoin"
    rng = np.random.default_rng(7)
    returns = pd.DataFrame(rng.normal(0.0, 0.01, size=(days, coins)), index=index, columns=columns)
    market_cap = pd.DataFrame(
        {column: np.full(days, 1_000.0 * (position + 1)) for position, column in enumerate(columns)},
        index=index,
    )
    volume = pd.DataFrame(
        {column: np.full(days, 100.0 * (position + 1)) for position, column in enumerate(columns)},
        index=index,
    )
    market = _Market(returns=returns, volume=volume, market_cap=market_cap)
    universe = pd.DataFrame(
        {"rebalance_date": list(index), "coin_id": [columns] * days},
    ).explode("coin_id")
    weights = pd.DataFrame(0.0, index=index, columns=columns)
    weights["bitcoin"] = 0.5
    return index, columns, market, universe, weights


def test_ratio_to_median_is_relative_to_its_own_trailing_history() -> None:
    index = pd.date_range("2024-01-01", periods=400, freq="D")
    series = pd.Series(1.0, index=index)
    series.iloc[-1] = 2.0

    ratio = _ratio_to_median(series)

    assert np.isnan(ratio.iloc[0])
    assert ratio.iloc[-2] == pytest.approx(1.0)
    # The last day is twice the trailing median of the strictly earlier days.
    assert ratio.iloc[-1] > 1.9


def test_flow_state_frame_aggregates_only_point_in_time_members() -> None:
    index, columns, market, universe, weights = _synthetic()
    # Drop the last coin from the universe every day: its huge volume must not
    # leak into the aggregate turnover.
    universe = universe[universe["coin_id"] != columns[-1]]
    market.volume[columns[-1]] = 10_000.0

    flow = flow_state_frame(market, universe, index, weights)

    member_volume = market.volume[[column for column in columns if column != columns[-1]]].sum(axis=1)
    member_mcap = market.market_cap[[column for column in columns if column != columns[-1]]].sum(axis=1)
    assert flow["turnover"].iloc[-1] == pytest.approx(float(member_volume.iloc[-1] / member_mcap.iloc[-1]))
    # HHI and BTC share are shares of the members only.
    assert 0.0 < flow["mcap_hhi"].iloc[-1] < 1.0
    assert flow["btc_share"].iloc[-1] > 0.0
    # Member volumes are 100..500, so the three largest carry 1200/1500.
    assert flow["volume_top3_share"].iloc[-1] == pytest.approx(0.8)


def test_flow_state_frame_leaves_a_day_without_members_empty() -> None:
    index, columns, market, universe, weights = _synthetic(days=10)
    universe = universe[universe["rebalance_date"] != index[-1]]

    flow = flow_state_frame(market, universe, index, weights)

    assert flow[list(FLOW_STATE_COLUMNS)].loc[index[-1]].isna().all()


def test_separation_table_drops_missing_values_state_by_state() -> None:
    index = pd.date_range("2024-01-01", periods=6, freq="ME")
    monthly = pd.DataFrame(
        {
            "ret": [-0.10, -0.09, 0.01, 0.02, 0.03, 0.04],
            "state_a": [1.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            # Every crash month is missing for state_b; the rest are present.
            "state_b": [np.nan, np.nan, 0.0, 1.0, 2.0, 3.0],
        },
        index=index,
    )

    table = separation_table(monthly, -0.08, ("state_a", "state_b"))

    assert int(table.loc["state_a", "crash_months"]) == 2
    # state_b is reported as unusable instead of dropping the crash months for
    # every other state, which is the defect Section 00.15 corrects.
    assert int(table.loc["state_b", "crash_months"]) == 0
    assert np.isnan(table.loc["state_b", "diff_over_rest_std"])


def test_information_table_signs_the_rank_correlation() -> None:
    index = pd.date_range("2024-01-01", periods=12, freq="ME")
    monthly = pd.DataFrame(
        {
            "excess": np.arange(12, dtype=float),
            "negative": -np.arange(12, dtype=float),
            "noise": np.zeros(12),
        },
        index=index,
    )

    table = information_table(monthly, ("negative", "noise"))

    assert table.loc["negative", "spearman"] == pytest.approx(-1.0)
    assert np.isnan(table.loc["noise", "spearman"])


def test_verdicts_require_all_three_pre_declared_conditions() -> None:
    separation = pd.DataFrame(
        {"diff_over_rest_std": [0.9, 0.9, 0.1]}, index=["passing", "flat", "weak"]
    )
    information = pd.DataFrame(
        {"spearman": [-0.30, 0.10, -0.30]}, index=["passing", "flat", "weak"]
    )
    terciles = pd.DataFrame(
        {
            "state": ["passing"] * 3 + ["flat"] * 3 + ["weak"] * 3,
            "bucket": [1, 2, 3] * 3,
            "mean_excess": [0.05, 0.01, -0.02, 0.04, 0.02, -0.01, 0.05, 0.01, -0.02],
        }
    )

    verdicts = _verdicts(separation, information, terciles, ("passing", "flat", "weak"))

    assert verdicts.loc["passing", "promote_to_h6"]
    # Everything but the IC clears for `flat`, and everything but the
    # separation clears for `weak`; neither is promoted.
    assert verdicts.loc["flat", "tercile_monotone"]
    assert verdicts.loc["flat", "passes_separation_bar"]
    assert not verdicts.loc["flat", "promote_to_h6"]
    assert verdicts.loc["weak", "passes_ic_bar"]
    assert not verdicts.loc["weak", "promote_to_h6"]


def test_monthly_frame_reads_flow_states_before_the_month() -> None:
    index = pd.date_range("2024-01-01", periods=90, freq="D")
    port = pd.Series(0.001, index=index)
    btc = pd.Series(0.002, index=index)
    flow = pd.DataFrame(0.0, index=index, columns=FLOW_STATE_COLUMNS)
    flow.loc["2024-02-29", "turnover_ratio"] = 9.99
    legacy = pd.DataFrame(
        {
            "gate_open": 1.0,
            "breadth": 0.5,
            "disp_ratio": 1.0,
            "mkt_vol": 0.6,
            "own63_before": 0.1,
            "gross": 0.3,
        },
        index=index,
    )

    monthly = monthly_frame(port, btc, flow.where(flow != 9.99, 0.0), legacy)

    assert monthly.index[0].is_month_end
    assert monthly.loc["2024-03-31", "turnover_ratio"] == pytest.approx(0.0)
    assert "turnover_ratio" in monthly.columns
    assert monthly["excess"].iloc[-1] < 0  # the strategy trails BTC in the fixture


def test_terciles_are_ordered_by_state() -> None:
    index = pd.date_range("2024-01-01", periods=12, freq="ME")
    monthly = pd.DataFrame(
        {
            "state": np.arange(12, dtype=float),
            "ret": np.arange(12, dtype=float) / 100.0,
            "btc": np.zeros(12),
            "excess": np.arange(12, dtype=float) / 100.0,
        },
        index=index,
    )

    terciles = tercile_table(monthly, ("state",))

    means = terciles.sort_values("bucket")["mean_excess"].tolist()
    assert means == sorted(means)
