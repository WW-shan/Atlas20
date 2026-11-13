from __future__ import annotations

import pandas as pd
import pytest


def test_align_perp_mark_uses_latest_close_within_two_hours() -> None:
    from scripts.run_ls100_same_venue_basis import align_perp_mark

    target = pd.DatetimeIndex(["2024-01-02 00:00:00+00:00"])
    marks = pd.DataFrame(
        {
            "open_time": pd.to_datetime(["2024-01-01 21:00:00+00:00", "2024-01-01 22:00:00+00:00"]),
            "close": [100.0, 101.0],
        }
    )

    result = align_perp_mark(marks, target, max_staleness_hours=2.0)

    assert result.loc[target[0], "mark_close"] == pytest.approx(101.0)
    assert result.loc[target[0], "staleness_hours"] == pytest.approx(1.0)
    assert bool(result.loc[target[0], "available"]) is True


def test_align_perp_mark_marks_a_stale_bar_unavailable() -> None:
    from scripts.run_ls100_same_venue_basis import align_perp_mark

    target = pd.DatetimeIndex(["2024-01-02 00:00:00+00:00"])
    marks = pd.DataFrame(
        {
            "open_time": pd.to_datetime(["2024-01-01 19:00:00+00:00"]),
            "close": [100.0],
        }
    )

    result = align_perp_mark(marks, target, max_staleness_hours=2.0)

    assert pd.isna(result.loc[target[0], "mark_close"])
    assert result.loc[target[0], "staleness_hours"] == pytest.approx(4.0)
    assert bool(result.loc[target[0], "available"]) is False


def test_basis_daily_return_uses_per_leg_notional_and_funding() -> None:
    from scripts.run_ls100_same_venue_basis import basis_daily_return

    index = pd.date_range("2024-01-01", periods=3, tz="UTC")
    spot = pd.DataFrame({"bitcoin": [100.0, 110.0, 110.0]}, index=index)
    perp = pd.DataFrame({"bitcoin": [100.0, 105.0, 105.0]}, index=index)
    funding = pd.DataFrame({"bitcoin": [0.0, 0.01, 0.0]}, index=index)
    positions = pd.DataFrame({"bitcoin": [0.25, 0.25, 0.25]}, index=index)

    result = basis_daily_return(
        spot_close=spot,
        perp_close=perp,
        funding=funding,
        positions=positions,
    )

    assert result["basis_pnl"].iloc[1] == pytest.approx(0.0125)
    assert result["funding_pnl"].iloc[1] == pytest.approx(0.0025)
    assert result["daily_return"].iloc[1] == pytest.approx(0.015)


def test_funding_proxy_match_rejects_wrong_sign_and_large_gap() -> None:
    from scripts.run_ls100_same_venue_basis import funding_proxy_match

    assert funding_proxy_match(proxy=0.03, exact=0.02) is True
    assert funding_proxy_match(proxy=0.03, exact=-0.01) is False
    assert funding_proxy_match(proxy=0.03, exact=0.06) is False


def test_classify_same_venue_basis_requires_all_frozen_gates() -> None:
    from scripts.run_ls100_same_venue_basis import classify_same_venue_basis

    metrics = {
        "full_multiple_10bps": 1.15,
        "full_sharpe_10bps": 2.0,
        "full_mdd_10bps": -0.02,
        "full_multiple_20bps": 1.14,
        "validation_multiple_10bps": 1.10,
        "validation_sharpe_10bps": 2.8,
    }
    yearly = pd.Series([0.01, 0.02, 0.03, 0.01, 0.01], index=[2022, 2023, 2024, 2025, 2026])
    assets = pd.Series([0.05, 0.04], index=["bitcoin", "ethereum"])

    assert (
        classify_same_venue_basis(
            metrics=metrics,
            yearly_returns=yearly,
            asset_net_pnl=assets,
            funding_pnl=0.09,
            basis_pnl=0.01,
            coverage_ok=True,
            proxy_match=True,
        )
        == "pass"
    )
    assert (
        classify_same_venue_basis(
            metrics=metrics,
            yearly_returns=yearly,
            asset_net_pnl=assets,
            funding_pnl=0.09,
            basis_pnl=0.01,
            coverage_ok=True,
            proxy_match=False,
        )
        == "funding-proxy-mismatch"
    )
