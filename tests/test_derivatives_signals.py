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
        short_asset="bitcoin",
        short_weight=0.25,
        eligible={"ETH"},
        short_mode="flat-only",
    )

    assert combined[date].empty
