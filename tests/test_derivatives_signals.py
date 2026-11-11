from __future__ import annotations

import pandas as pd
import pytest

from atlas20.derivatives.signals import (
    bear_regime,
    build_derivative_targets,
    funding_filter,
    scale_long_targets,
    weakest_top20,
)


def test_scale_long_targets_applies_leverage_and_gross_cap() -> None:
    targets = {pd.Timestamp("2026-01-01", tz="UTC"): pd.Series({"BTC": 0.8, "ETH": 0.2})}

    scaled = scale_long_targets(targets, leverage=1.25, max_gross=1.25)

    assert scaled[pd.Timestamp("2026-01-01", tz="UTC")].sum() == pytest.approx(1.25)
    assert scaled[pd.Timestamp("2026-01-01", tz="UTC")]["BTC"] == pytest.approx(1.0)


def test_scale_long_targets_caps_above_max_gross() -> None:
    targets = {pd.Timestamp("2026-01-01", tz="UTC"): pd.Series({"BTC": 1.0})}

    scaled = scale_long_targets(targets, leverage=2.0, max_gross=1.25)

    assert scaled[pd.Timestamp("2026-01-01", tz="UTC")]["BTC"] == pytest.approx(1.25)


def test_bear_regime_requires_below_ma_and_negative_30d_return() -> None:
    index = pd.date_range("2025-01-01", periods=260, freq="D", tz="UTC")
    close = pd.Series(100.0, index=index)
    close.iloc[-30:] = 80.0

    regime = bear_regime(close, ma_window=200, return_window=30)

    assert bool(regime.iloc[-1]) is True
    assert bool(regime.iloc[210]) is False


def test_funding_filter_fails_closed_when_fewer_than_three_settlements() -> None:
    funding = pd.DataFrame(
        {"BTC": [0.0001, 0.0001]},
        index=pd.DatetimeIndex(["2026-01-01T00:00:00Z", "2026-01-01T08:00:00Z"]),
    )

    assert funding_filter(funding, "BTC", as_of=pd.Timestamp("2026-01-02T00:00:00Z")) is False


def test_funding_filter_uses_mean_of_last_three_settlements() -> None:
    funding = pd.DataFrame(
        {"BTC": [-0.00005, 0.0001, 0.0001]},
        index=pd.DatetimeIndex(
            [
                "2026-01-01T00:00:00Z",
                "2026-01-01T08:00:00Z",
                "2026-01-01T16:00:00Z",
            ]
        ),
    )

    assert funding_filter(
        funding,
        "BTC",
        as_of=pd.Timestamp("2026-01-02T00:00:00Z"),
        threshold=-0.0001,
    ) is True


def test_funding_filter_matches_a_coin_id_case_insensitively() -> None:
    funding = pd.DataFrame(
        {"bitcoin": [0.0001, 0.0001, 0.0001]},
        index=pd.DatetimeIndex(
            [
                "2026-01-01T00:00:00Z",
                "2026-01-01T08:00:00Z",
                "2026-01-01T16:00:00Z",
            ]
        ),
    )

    assert funding_filter(funding, "BITCOIN", as_of=pd.Timestamp("2026-01-02T00:00:00Z")) is True


def test_weakest_top20_uses_only_members_and_30d_return() -> None:
    index = pd.date_range("2026-01-01", periods=31, freq="D", tz="UTC")
    prices = pd.DataFrame(
        {
            "BTC": [100.0] * 31,
            "ETH": [100.0] * 31,
            "SOL": [100.0] * 31,
        },
        index=index,
    )
    prices.loc[index[-1], "ETH"] = 80.0
    prices.loc[index[-1], "SOL"] = 70.0
    universe = pd.DataFrame(
        {
            "rebalance_date": [index[-1]] * 2,
            "coin_id": ["BTC", "ETH"],
        }
    )

    assert weakest_top20(prices, universe, index[-1], eligible={"BTC", "ETH", "SOL"}) == "ETH"


def test_build_derivative_targets_adds_short_only_in_bear_regime() -> None:
    dates = pd.date_range("2025-01-01", periods=260, freq="D", tz="UTC")
    btc = pd.Series(100.0, index=dates)
    btc.iloc[-30:] = 80.0
    prices = pd.DataFrame({"BTC": btc, "ETH": btc}, index=dates)
    prices.loc[dates[-1], "ETH"] = 70.0
    universe = pd.DataFrame(
        {
            "rebalance_date": [dates[-1], dates[-1]],
            "coin_id": ["BTC", "ETH"],
        }
    )
    long_targets = {dates[-1]: pd.Series({"BTC": 0.5, "ETH": 0.5})}
    funding = pd.DataFrame(
        {"BTC": [0.0001] * 3, "ETH": [0.0001] * 3},
        index=pd.DatetimeIndex(
            [
                dates[-2].replace(hour=0),
                dates[-2].replace(hour=8),
                dates[-2].replace(hour=16),
            ]
        ),
    )

    combined = build_derivative_targets(
        long_targets,
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="weakest",
        short_weight=0.25,
        eligible={"BTC", "ETH"},
    )

    target = combined[dates[-1]]
    assert target["ETH"] == pytest.approx(0.5 * 1.25 - 0.25)
    assert target["BTC"] == pytest.approx(0.5 * 1.25)


def _short_overlay_fixture() -> tuple[pd.Timestamp, pd.Series, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2025-01-01", periods=260, freq="D", tz="UTC")
    btc = pd.Series(100.0, index=dates)
    btc.iloc[-30:] = 80.0
    prices = pd.DataFrame({"BTC": btc, "ETH": btc}, index=dates)
    prices.loc[dates[-1], "ETH"] = 70.0
    universe = pd.DataFrame(
        {"rebalance_date": [dates[-1], dates[-1]], "coin_id": ["BTC", "ETH"]}
    )
    funding = pd.DataFrame(
        {"BTC": [0.0001] * 3, "ETH": [0.0001] * 3},
        index=pd.DatetimeIndex(
            [
                dates[-2].replace(hour=0),
                dates[-2].replace(hour=8),
                dates[-2].replace(hour=16),
            ]
        ),
    )
    return dates[-1], btc, prices, universe, funding


def test_build_derivative_targets_replace_mode_goes_cash_plus_short_in_bear() -> None:
    date, btc, prices, universe, funding = _short_overlay_fixture()
    long_targets = {date: pd.Series({"BTC": 0.5, "ETH": 0.5})}

    combined = build_derivative_targets(
        long_targets,
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="weakest",
        short_weight=0.25,
        eligible={"BTC", "ETH"},
        short_mode="replace",
    )

    target = combined[date]
    assert target["ETH"] == pytest.approx(-0.25)
    assert target.get("BTC", 0.0) == pytest.approx(0.0)
    assert target.abs().sum() == pytest.approx(0.25)


def test_build_derivative_targets_flat_only_does_not_short_a_live_long_book() -> None:
    date, btc, prices, universe, funding = _short_overlay_fixture()
    long_targets = {date: pd.Series({"BTC": 0.5, "ETH": 0.5})}

    combined = build_derivative_targets(
        long_targets,
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="weakest",
        short_weight=0.25,
        eligible={"BTC", "ETH"},
        short_mode="flat-only",
    )

    target = combined[date]
    assert target["ETH"] == pytest.approx(0.5 * 1.25)
    assert target["BTC"] == pytest.approx(0.5 * 1.25)


def test_build_derivative_targets_flat_only_shorts_when_the_book_is_cash() -> None:
    date, btc, prices, universe, funding = _short_overlay_fixture()
    long_targets = {date: pd.Series(dtype=float)}

    combined = build_derivative_targets(
        long_targets,
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="weakest",
        short_weight=0.25,
        eligible={"BTC", "ETH"},
        short_mode="flat-only",
    )

    assert combined[date]["ETH"] == pytest.approx(-0.25)


def test_build_derivative_targets_rejects_an_unknown_short_mode() -> None:
    date, btc, prices, universe, funding = _short_overlay_fixture()

    with pytest.raises(ValueError, match="short_mode"):
        build_derivative_targets(
            {date: pd.Series({"BTC": 0.5})},
            btc_close=btc,
            universe=universe,
            prices=prices,
            funding_rates=funding,
            leverage=1.25,
            max_gross=1.5,
            short_asset="BTC",
            short_weight=0.25,
            short_mode="unknown",  # type: ignore[arg-type]
        )


def test_build_derivative_targets_skips_a_fixed_short_outside_eligible_universe() -> None:
    date, btc, prices, universe, funding = _short_overlay_fixture()

    combined = build_derivative_targets(
        {date: pd.Series(dtype=float)},
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.25,
        short_asset="BTC",
        short_weight=0.25,
        eligible={"ETH"},
        short_mode="flat-only",
    )

    assert combined[date].empty


def test_build_derivative_targets_requires_fixed_short_to_be_a_pit_top20_member() -> None:
    date, btc, prices, universe, funding = _short_overlay_fixture()
    # BTC is tradeable but the point-in-time universe contains only ETH.
    universe = universe.loc[universe["coin_id"].eq("ETH")].copy()

    combined = build_derivative_targets(
        {date: pd.Series(dtype=float)},
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.25,
        short_asset="BTC",
        short_weight=0.25,
        eligible={"BTC", "ETH"},
        short_mode="flat-only",
    )

    assert combined[date].empty


def test_build_derivative_targets_can_evaluate_short_regime_on_every_calendar_day() -> None:
    dates = pd.date_range("2025-01-01", periods=260, freq="D", tz="UTC")
    btc = pd.Series(100.0, index=dates)
    btc.iloc[-30:] = 80.0
    prices = pd.DataFrame({"BTC": btc, "ETH": btc}, index=dates)
    prices.loc[dates[-1], "ETH"] = 70.0
    universe = pd.DataFrame(
        {"rebalance_date": [dates[-1], dates[-1]], "coin_id": ["BTC", "ETH"]}
    )
    funding = pd.DataFrame(
        {"BTC": [0.0001] * 3, "ETH": [0.0001] * 3},
        index=pd.DatetimeIndex(
            [
                dates[-2].replace(hour=0),
                dates[-2].replace(hour=8),
                dates[-2].replace(hour=16),
            ]
        ),
    )
    # The H5 long book only has an event on the first day. The short regime
    # starts later, so the short must still be evaluated on the later date.
    long_targets = {dates[0]: pd.Series({"ETH": 1.0})}

    combined = build_derivative_targets(
        long_targets,
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="BTC",
        short_weight=0.25,
        eligible={"BTC", "ETH"},
        short_mode="additive",
        calendar=dates,
    )

    assert combined[dates[-1]]["BTC"] == pytest.approx(-0.25)
    assert combined[dates[-1]]["ETH"] == pytest.approx(1.25)


def test_build_derivative_targets_does_not_short_during_h5_warmup() -> None:
    dates = pd.date_range("2025-01-01", periods=260, freq="D", tz="UTC")
    btc = pd.Series(100.0, index=dates)
    btc.iloc[-30:] = 80.0
    prices = pd.DataFrame({"BTC": btc, "ETH": btc}, index=dates)
    universe = pd.DataFrame(
        {"rebalance_date": [dates[-1], dates[-1]], "coin_id": ["BTC", "ETH"]}
    )
    funding = pd.DataFrame(
        {"BTC": [0.0001] * 3, "ETH": [0.0001] * 3},
        index=pd.DatetimeIndex(
            [
                dates[-2].replace(hour=0),
                dates[-2].replace(hour=8),
                dates[-2].replace(hour=16),
            ]
        ),
    )
    long_targets = {dates[-1]: pd.Series(dtype=float)}

    combined = build_derivative_targets(
        long_targets,
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.25,
        short_asset="BTC",
        short_weight=0.25,
        eligible={"BTC", "ETH"},
        short_mode="flat-only",
        calendar=dates,
    )

    assert combined[dates[0]].empty


def test_build_derivative_targets_cross_sectional_short_excludes_long_book() -> None:
    dates = pd.date_range("2024-12-01", periods=45, freq="D", tz="UTC")
    signal_date = dates[21]
    btc = pd.Series(100.0, index=dates)
    prices = pd.DataFrame({"BTC": btc, "ETH": btc, "SOL": btc}, index=dates)
    prices.loc[signal_date, "BTC"] = 70.0
    prices.loc[signal_date, "SOL"] = 80.0
    universe = pd.DataFrame(
        {
            "rebalance_date": [dates[0]] * 3,
            "coin_id": ["BTC", "ETH", "SOL"],
        }
    )
    funding = pd.DataFrame(
        {"BTC": [0.0001] * 3, "ETH": [0.0001] * 3, "SOL": [0.0001] * 3},
        index=pd.DatetimeIndex(
            [
                dates[20].replace(hour=0),
                dates[20].replace(hour=8),
                dates[20].replace(hour=16),
            ]
        ),
    )
    long_targets = {dates[0]: pd.Series({"BTC": 0.5, "ETH": 0.5})}

    combined = build_derivative_targets(
        long_targets,
        btc_close=btc,
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="weakest",
        short_weight=0.25,
        eligible={"BTC", "ETH", "SOL"},
        short_mode="cross-sectional",
        calendar=dates,
        cross_sectional_lookback=14,
        cross_sectional_rebalance_days=7,
        cross_sectional_anchor=dates[0],
    )

    target = combined[signal_date]
    assert target["BTC"] == pytest.approx(0.625)
    assert target["ETH"] == pytest.approx(0.625)
    assert target["SOL"] == pytest.approx(-0.25)


def test_build_derivative_targets_cross_sectional_basket_splits_total_weight() -> None:
    dates = pd.date_range("2024-12-01", periods=45, freq="D", tz="UTC")
    signal_date = dates[21]
    prices = pd.DataFrame(
        {
            "BTC": 100.0,
            "ETH": 100.0,
            "SOL": 100.0,
            "ADA": 100.0,
        },
        index=dates,
    )
    prices.loc[signal_date, "BTC"] = 80.0
    prices.loc[signal_date, "SOL"] = 70.0
    prices.loc[signal_date, "ADA"] = 75.0
    universe = pd.DataFrame(
        {
            "rebalance_date": [dates[0]] * 4,
            "coin_id": ["BTC", "ETH", "SOL", "ADA"],
        }
    )
    funding = pd.DataFrame(
        {coin: [0.0001] * 3 for coin in ["BTC", "ETH", "SOL", "ADA"]},
        index=pd.DatetimeIndex(
            [
                dates[20].replace(hour=0),
                dates[20].replace(hour=8),
                dates[20].replace(hour=16),
            ]
        ),
    )

    combined = build_derivative_targets(
        {dates[0]: pd.Series({"ETH": 1.0})},
        btc_close=prices["BTC"],
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="weakest",
        short_weight=0.25,
        eligible={"BTC", "ETH", "SOL", "ADA"},
        short_mode="cross-sectional",
        calendar=dates,
        cross_sectional_lookback=14,
        cross_sectional_rebalance_days=7,
        cross_sectional_short_count=2,
        cross_sectional_anchor=dates[0],
    )

    target = combined[signal_date]
    assert target["SOL"] == pytest.approx(-0.125)
    assert target["ADA"] == pytest.approx(-0.125)
    assert "BTC" not in target.index


def _cross_sectional_hold_band_fixture(
    second_current: dict[str, float],
) -> tuple[
    pd.DatetimeIndex,
    pd.Timestamp,
    pd.Timestamp,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    dates = pd.date_range("2025-01-01", periods=20, freq="D", tz="UTC")
    first_signal = dates[7]
    second_signal = dates[14]
    assets = ["LONG", "A", "B", "C", "D", "E", "F"]
    prices = pd.DataFrame(100.0, index=dates, columns=assets)
    prices.loc[first_signal, ["A", "B", "C", "D", "E", "F"]] = [
        50.0,
        60.0,
        70.0,
        80.0,
        90.0,
        100.0,
    ]
    prices.loc[second_signal, list(second_current)] = list(second_current.values())
    universe = pd.DataFrame(
        {
            "rebalance_date": [dates[0]] * len(assets),
            "coin_id": assets,
        }
    )
    funding = pd.DataFrame(
        {asset: [0.0001] * 3 for asset in assets},
        index=pd.DatetimeIndex(
            [
                dates[0].replace(hour=0),
                dates[0].replace(hour=8),
                dates[0].replace(hour=16),
            ]
        ),
    )
    long_targets = {dates[0]: pd.Series({"LONG": 1.0})}
    return (
        dates,
        first_signal,
        second_signal,
        prices,
        universe,
        funding,
        long_targets,
    )


def test_cross_sectional_hold_band_retains_incumbents_inside_bottom_four_of_eight() -> None:
    (
        dates,
        first_signal,
        second_signal,
        prices,
        universe,
        funding,
        long_targets,
    ) = _cross_sectional_hold_band_fixture(
        {"A": 55.0, "B": 70.0, "C": 80.0, "D": 82.0, "E": 110.0, "F": 120.0}
    )

    combined = build_derivative_targets(
        long_targets,
        btc_close=prices["LONG"],
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="weakest",
        short_weight=0.25,
        eligible=set(prices.columns),
        short_mode="cross-sectional",
        calendar=dates,
        cross_sectional_lookback=7,
        cross_sectional_rebalance_days=7,
        cross_sectional_short_count=2,
        cross_sectional_hold_rank=4,
        cross_sectional_anchor=dates[0],
    )

    assert combined[first_signal]["A"] == pytest.approx(-0.125)
    assert combined[first_signal]["B"] == pytest.approx(-0.125)
    assert second_signal not in combined


def test_cross_sectional_hold_band_replaces_incumbents_outside_bottom_four_of_eight() -> None:
    (
        dates,
        first_signal,
        second_signal,
        prices,
        universe,
        funding,
        long_targets,
    ) = _cross_sectional_hold_band_fixture(
        {"A": 70.0, "B": 90.0, "C": 80.0, "D": 82.0, "E": 100.0, "F": 105.0}
    )

    combined = build_derivative_targets(
        long_targets,
        btc_close=prices["LONG"],
        universe=universe,
        prices=prices,
        funding_rates=funding,
        leverage=1.25,
        max_gross=1.5,
        short_asset="weakest",
        short_weight=0.25,
        eligible=set(prices.columns),
        short_mode="cross-sectional",
        calendar=dates,
        cross_sectional_lookback=7,
        cross_sectional_rebalance_days=7,
        cross_sectional_short_count=2,
        cross_sectional_hold_rank=4,
        cross_sectional_anchor=dates[0],
    )

    assert combined[first_signal]["A"] == pytest.approx(-0.125)
    assert combined[first_signal]["B"] == pytest.approx(-0.125)
    target = combined[second_signal]
    assert target["D"] == pytest.approx(-0.125)
    assert target["F"] == pytest.approx(-0.125)
    assert "A" not in target.index
    assert "B" not in target.index


def test_cross_sectional_hold_rank_cannot_be_smaller_than_entry_count() -> None:
    (
        dates,
        _,
        _,
        prices,
        universe,
        funding,
        long_targets,
    ) = _cross_sectional_hold_band_fixture(
        {"A": 55.0, "B": 70.0, "C": 80.0, "D": 82.0, "E": 110.0, "F": 120.0}
    )

    with pytest.raises(ValueError, match="cross_sectional_hold_rank"):
        build_derivative_targets(
            long_targets,
            btc_close=prices["LONG"],
            universe=universe,
            prices=prices,
            funding_rates=funding,
            leverage=1.25,
            max_gross=1.5,
            short_asset="weakest",
            short_weight=0.25,
            eligible=set(prices.columns),
            short_mode="cross-sectional",
            calendar=dates,
            cross_sectional_lookback=7,
            cross_sectional_rebalance_days=7,
            cross_sectional_short_count=2,
            cross_sectional_hold_rank=1,
            cross_sectional_anchor=dates[0],
        )


def test_combine_sleeve_targets_forward_fills_and_scales_all_sleeves() -> None:
    from atlas20.derivatives.signals import combine_sleeve_targets

    d1 = pd.Timestamp("2026-01-01", tz="UTC")
    d2 = pd.Timestamp("2026-01-02", tz="UTC")
    h5 = {d1: pd.Series({"bitcoin": 0.40})}
    h4 = {d1: pd.Series({"ethereum": 0.50})}
    short = {d2: pd.Series({"solana": 1.00})}

    combined = combine_sleeve_targets(
        {
            "h5": (h5, 1.0),
            "h4": (h4, 0.2),
            "sector_short": (short, -0.2),
        },
        max_gross=0.50,
    )

    assert combined[d1]["bitcoin"] == pytest.approx(0.40)
    assert combined[d1]["ethereum"] == pytest.approx(0.10)
    target = combined[d2]
    assert target["bitcoin"] == pytest.approx(0.40 * 0.50 / 0.70)
    assert target["ethereum"] == pytest.approx(0.10 * 0.50 / 0.70)
    assert target["solana"] == pytest.approx(-0.20 * 0.50 / 0.70)
    assert target.abs().sum() == pytest.approx(0.50)
