from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_momentum_funding_states import (
    FUNDING_STATE_COLUMNS,
    coverage_table,
    funding_state_frame,
    load_funding,
    monthly_frame,
)
from scripts.download_funding_rates import _months, _perp_symbol


def _write_funding(path, rates: list[float], start: str = "2024-01-01") -> None:
    stamps = pd.date_range(start, periods=len(rates), freq="8h", tz="UTC")
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    millis = ((stamps - epoch) // pd.Timedelta(milliseconds=1)).astype("int64")
    pd.DataFrame(
        {
            "calc_time": millis,
            "funding_interval_hours": 8,
            "last_funding_rate": rates,
        }
    ).to_csv(path, index=False)


def _universe(index: pd.DatetimeIndex, members: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"rebalance_date": np.repeat(index, len(members)), "coin_id": members * len(index)}
    )


def test_months_range_is_inclusive() -> None:
    assert _months("2020-09", "2020-11") == ["2020-09", "2020-10", "2020-11"]


def test_perp_symbol_maps_thousand_unit_tokens_and_rejects_gate_only_pairs() -> None:
    assert _perp_symbol("shiba-inu", "SHIBUSDT") == "1000SHIBUSDT"
    assert _perp_symbol("pepe", "PEPEUSDT") == "1000PEPEUSDT"
    assert _perp_symbol("bitcoin", "BTCUSDT") == "BTCUSDT"
    assert _perp_symbol("kaspa", "KAS_USDT") == "KASUSDT"
    with pytest.raises(KeyError):
        _perp_symbol("okb", "OKB_USDT")


def test_load_funding_sums_the_days_payments(tmp_path) -> None:
    # Two days of three 8-hour payments each.
    _write_funding(tmp_path / "bitcoin.csv", [0.0001, 0.0002, 0.0003, -0.0001, 0.0, 0.0001])

    funding = load_funding(tmp_path)

    daily = funding["bitcoin"]
    assert daily.loc[pd.Timestamp("2024-01-01")] == pytest.approx(0.0006)
    assert daily.loc[pd.Timestamp("2024-01-02")] == pytest.approx(0.0)


def test_funding_state_frame_aggregates_members_in_basis_points(tmp_path) -> None:
    # 200 days so the 126-day minimum for the dispersion ratio is reached.
    index = pd.date_range("2024-01-01", periods=200, freq="D")
    members = [f"coin{number}" for number in range(1, 7)]
    for number, coin in enumerate(members, start=1):
        # Daily funding of number bps per day, three 8-hour payments.
        _write_funding(tmp_path / f"{coin}.csv", [number * 1e-4 / 3] * (3 * 200))
    funding = load_funding(tmp_path)

    states, members_used = funding_state_frame(_universe(index, members), index, funding)

    expected_mean = float(np.mean([number for number in range(1, 7)]))  # 3.5 bps
    assert states["funding_level"].iloc[-1] == pytest.approx(expected_mean)
    assert states["funding_positive_share"].iloc[-1] == pytest.approx(1.0)
    # Constant cross-sectional dispersion over time, so the ratio to its own
    # trailing median is exactly one.
    assert states["funding_disp_ratio"].iloc[-1] == pytest.approx(1.0)
    assert members_used.iloc[-1] == 6.0


def test_funding_state_frame_respects_the_member_floor(tmp_path) -> None:
    index = pd.date_range("2024-01-01", periods=10, freq="D")
    members = ["coin1", "coin2", "coin3"]
    for coin in members:
        _write_funding(tmp_path / f"{coin}.csv", [1e-4] * (3 * 10))
    funding = load_funding(tmp_path)

    states, members_used = funding_state_frame(_universe(index, members), index, funding)

    assert members_used.iloc[-1] == 3.0
    assert np.isnan(states["funding_level"].iloc[-1])


def test_monthly_frame_reads_funding_states_before_the_month() -> None:
    index = pd.date_range("2024-01-01", periods=90, freq="D")
    port = pd.Series(0.001, index=index)
    btc = pd.Series(0.002, index=index)
    funding = pd.DataFrame(0.0, index=index, columns=FUNDING_STATE_COLUMNS)
    funding.loc["2024-02-20", "funding_level"] = 9.0
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

    monthly = monthly_frame(port, btc, funding, legacy)

    assert monthly.loc["2024-03-31", "funding_level"] == pytest.approx(0.0)
    assert monthly["excess"].iloc[-1] < 0


def test_coverage_table_counts_member_days_and_missing_coins() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    members = ["coin1", "coin2"]
    funding = {"coin1": pd.Series(dtype=float)}
    used = pd.Series([2.0, 1.0], index=index)

    coverage = coverage_table(_universe(index, members), index, funding, used)

    values = dict(zip(coverage["metric"], coverage["value"], strict=True))
    assert values["coins with funding history"] == 1.0
    assert values["members without funding history"] == 1.0
    assert values["member-days with funding"] == 3.0
    assert values["member-day coverage"] == pytest.approx(0.75)
