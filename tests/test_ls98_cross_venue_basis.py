from __future__ import annotations

import pandas as pd
import pytest


def test_basis_daily_return_combines_hedged_spot_perp_and_funding() -> None:
    from scripts.run_ls98_cross_venue_basis import basis_daily_return

    index = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    spot_returns = pd.DataFrame({"bitcoin": [0.0, 0.10, 0.0]}, index=index)
    perp_returns = pd.DataFrame({"bitcoin": [0.0, 0.05, 0.0]}, index=index)
    funding = pd.DataFrame({"bitcoin": [0.0, 0.01, 0.0]}, index=index)
    positions = pd.DataFrame({"bitcoin": [0.5, 0.5, 0.5]}, index=index)

    result = basis_daily_return(
        spot_returns=spot_returns,
        perp_returns=perp_returns,
        funding=funding,
        positions=positions,
    )

    assert result["basis_pnl"].iloc[1] == pytest.approx(0.025)
    assert result["funding_pnl"].iloc[1] == pytest.approx(0.005)
    assert result["daily_return"].iloc[1] == pytest.approx(0.030)


def test_positive_funding_positions_do_not_use_future_settlements() -> None:
    from scripts.run_ls98_cross_venue_basis import positive_funding_positions

    index = pd.date_range("2024-01-01", periods=16, freq="D", tz="UTC")
    funding = pd.DataFrame({"bitcoin": [0.001] * len(index)}, index=index)

    positions = positive_funding_positions(
        funding,
        index=index,
        assets=["bitcoin"],
        lookback_days=7,
        rebalance_days=7,
        notional=0.5,
    )

    assert positions.loc[index[5], "bitcoin"] == 0.0
    assert positions.loc[index[7], "bitcoin"] == pytest.approx(0.5)
    assert positions.loc[index[8], "bitcoin"] == pytest.approx(0.5)


def test_basis_classification_flags_asset_concentration() -> None:
    from scripts.run_ls98_cross_venue_basis import classify_basis_evidence

    asset = pd.DataFrame(
        {"asset": ["bitcoin", "ethereum"], "net_pnl": [0.10, 0.01]}
    )
    year = pd.DataFrame({"year": [2022, 2023, 2024], "net_pnl": [0.02, 0.04, 0.05]})

    label = classify_basis_evidence(
        asset_summary=asset,
        year_summary=year,
        funding_pnl=0.06,
        basis_pnl=0.05,
    )

    assert label == "asset-concentrated"


def test_default_sleeve_has_one_x_actual_two_leg_gross() -> None:
    from scripts.run_ls98_cross_venue_basis import ASSETS, NOTIONAL_PER_LEG, basis_gross_exposure

    positions = pd.DataFrame(
        NOTIONAL_PER_LEG,
        index=pd.date_range("2024-01-01", periods=2, tz="UTC"),
        columns=ASSETS,
    )

    assert NOTIONAL_PER_LEG == pytest.approx(0.25)
    assert basis_gross_exposure(positions).tolist() == pytest.approx([1.0, 1.0])


def test_asset_summary_charges_both_spot_and_perp_legs() -> None:
    from scripts.run_ls98_cross_venue_basis import _asset_summary

    index = pd.date_range("2024-01-01", periods=3, tz="UTC")
    spot_returns = pd.DataFrame({"bitcoin": [0.0, 0.0, 0.0]}, index=index)
    perp_returns = pd.DataFrame({"bitcoin": [0.0, 0.0, 0.0]}, index=index)
    funding = pd.DataFrame({"bitcoin": [0.0, 0.0, 0.0]}, index=index)
    positions = pd.DataFrame({"bitcoin": [0.25, 0.25, 0.25]}, index=index)

    result = _asset_summary(
        spot_returns=spot_returns,
        perp_returns=perp_returns,
        funding=funding,
        positions=positions,
        cost_bps=10.0,
    )

    assert result.loc[0, "costs"] == pytest.approx(0.001)
    assert result.loc[0, "net_pnl"] == pytest.approx(-0.001)


def test_turnover_cost_scales_to_both_legs() -> None:
    from scripts.run_ls98_cross_venue_basis import basis_turnover_cost

    index = pd.date_range("2024-01-01", periods=3, tz="UTC")
    positions = pd.DataFrame({"bitcoin": [0.25, 0.25, 0.25]}, index=index)

    cost = basis_turnover_cost(positions, cost_bps=10.0)

    assert cost.sum() == pytest.approx(0.001)
