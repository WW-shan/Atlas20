"""Is the newest panel day a finished provider day?

The processor only drops a day whose asset *coverage* is low. A day that every
asset has, but only partially - volumes at 30-50% because CoinMarketCap had
not finalized it - passes that gate, and it moves the Top 20: on the
2026-09-23 panel that simulation swaps Monero out for Bittensor through the
liquidity gate. ``assess_last_day`` compares the last day's per-asset volume
and market-cap coverage with the trailing seven days and refuses a day that
looks partial.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from atlas20.data.completeness import assess_last_day

_WEDNESDAY = pd.Timestamp("2026-09-23")
_SATURDAY = pd.Timestamp("2026-09-26")


def _panel(last_day: pd.Timestamp, *, coins: int = 30, days: int = 40, noise: bool = True) -> pd.DataFrame:
    """A healthy long panel: per-coin volume levels, a weekend dip, daily noise."""
    rng = np.random.default_rng(20260923)
    dates = pd.date_range(end=last_day, periods=days, freq="D")
    base = rng.uniform(5e7, 5e9, coins)
    caps = rng.uniform(1e9, 1e12, coins)
    rows = []
    for position, day in enumerate(dates):
        weekend = 0.75 if day.dayofweek >= 5 else 1.0
        market = float(rng.lognormal(0.0, 0.1)) if noise else 1.0
        for coin in range(coins):
            idiosyncratic = float(rng.lognormal(0.0, 0.25)) if noise else 1.0
            rows.append(
                {
                    "date": day,
                    "coin_id": f"coin-{coin:02d}",
                    "volume_usd": base[coin] * weekend * market * idiosyncratic,
                    "market_cap": caps[coin] * (1.0 + 0.001 * position),
                }
            )
    return pd.DataFrame(rows)


def _scale_last_day(panel: pd.DataFrame, factor: np.ndarray | float) -> pd.DataFrame:
    scaled = panel.copy()
    last = scaled["date"] == scaled["date"].max()
    scaled.loc[last, "volume_usd"] = scaled.loc[last, "volume_usd"].to_numpy() * factor
    return scaled


def test_a_healthy_last_day_is_complete() -> None:
    result = assess_last_day(_panel(_WEDNESDAY))

    assert result.complete, result.describe()
    assert result.date == _WEDNESDAY
    assert result.assets == 30
    assert result.market_cap_coverage == pytest.approx(1.0)


def test_a_uniformly_partial_last_day_fails() -> None:
    """Every coin's volume at 30-50%: the provider had not finalized the day."""
    panel = _panel(_WEDNESDAY)
    factors = np.random.default_rng(1).uniform(0.3, 0.5, 30)

    result = assess_last_day(_scale_last_day(panel, factors))

    assert not result.complete
    assert result.median_volume_ratio < 0.6
    assert any("volume" in reason for reason in result.reasons)
    assert "2026-09-23" in result.describe()


def test_missing_market_caps_on_the_last_day_fail() -> None:
    panel = _panel(_WEDNESDAY)
    last = panel["date"] == _WEDNESDAY
    dropped = panel.loc[last, "coin_id"].isin([f"coin-{coin:02d}" for coin in range(6)])
    panel.loc[last & dropped.reindex(panel.index, fill_value=False), "market_cap"] = np.nan

    result = assess_last_day(panel)

    assert not result.complete
    assert result.market_cap_coverage == pytest.approx(24 / 30)
    assert any("market cap" in reason for reason in result.reasons)


def test_a_coin_missing_from_the_last_day_counts_against_both_measures() -> None:
    panel = _panel(_WEDNESDAY)
    absent = (panel["date"] == _WEDNESDAY) & panel["coin_id"].isin([f"coin-{coin:02d}" for coin in range(20)])

    result = assess_last_day(panel[~absent])

    assert not result.complete
    assert result.market_cap_coverage == pytest.approx(10 / 30)


def test_the_volume_floor_depends_on_the_day_of_week() -> None:
    """A Saturday at half the trailing median is an ordinary weekend; a
    Wednesday at half is not (weekday floor 0.60, weekend floor 0.43)."""
    saturday = assess_last_day(_scale_last_day(_panel(_SATURDAY, noise=False), 0.5 / 0.75))
    wednesday = assess_last_day(_scale_last_day(_panel(_WEDNESDAY, noise=False), 0.5))

    assert saturday.median_volume_ratio == pytest.approx(0.5)
    assert saturday.complete, saturday.describe()
    assert wednesday.median_volume_ratio == pytest.approx(0.5)
    assert not wednesday.complete


def test_a_quiet_but_finished_weekday_is_complete() -> None:
    result = assess_last_day(_scale_last_day(_panel(_WEDNESDAY, noise=False), 0.7))

    assert result.complete, result.describe()


def test_too_little_trailing_history_cannot_be_certified() -> None:
    result = assess_last_day(_panel(_WEDNESDAY, days=5))

    assert not result.complete
    assert any("cannot assess" in reason for reason in result.reasons)


def test_an_asset_that_did_not_trade_through_the_trailing_week_is_not_scored() -> None:
    """A coin without a full trailing week (a new listing, an ended feed) has
    no baseline, so it neither helps nor hurts the verdict."""
    panel = _panel(_WEDNESDAY)
    newcomer = pd.DataFrame(
        {"date": [_WEDNESDAY], "coin_id": ["newcomer"], "volume_usd": [1.0], "market_cap": [np.nan]}
    )

    result = assess_last_day(pd.concat([panel, newcomer], ignore_index=True))

    assert result.complete, result.describe()
    assert result.assets == 30


def test_string_dates_from_the_persisted_csv_are_accepted() -> None:
    panel = _panel(_WEDNESDAY)
    panel["date"] = panel["date"].dt.strftime("%Y-%m-%d")

    assert assess_last_day(panel).date == _WEDNESDAY
