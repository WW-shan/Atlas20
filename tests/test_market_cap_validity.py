"""Zero or missing market caps must never enter the universe.

CoinMarketCap returns ``marketCap: 0`` (or null) for several assets it tracks
without supply data, e.g. WhiteBIT Coin. Treating 0 as a real value lets those
assets rank inside the Top-N and displaces genuine constituents, so invalid
market caps must be treated as missing.
"""

from __future__ import annotations

import pandas as pd

from atlas20.config import load_config
from atlas20.universe.builder import MarketDataBundle, build_rebalance_universe


def _bundle(market_caps: dict[str, float], price: float = 100.0, volume: float = 1e9) -> MarketDataBundle:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    cols = list(market_caps)
    price_df = pd.DataFrame({c: [price] * 3 for c in cols}, index=idx)
    cap_df = pd.DataFrame({c: [market_caps[c]] * 3 for c in cols}, index=idx)
    return MarketDataBundle(
        raw_price=price_df,
        price=price_df,
        returns=price_df.pct_change().fillna(0.0),
        market_cap=cap_df,
        volume=pd.DataFrame({c: [volume] * 3 for c in cols}, index=idx),
        history_count=pd.DataFrame({c: [365] * 3 for c in cols}, index=idx),
        metadata=pd.DataFrame(
            {"symbol": cols, "name": cols, "sector": ["Other"] * len(cols)},
            index=pd.Index(cols, name="coin_id"),
        ),
    )


def test_zero_market_cap_is_excluded_from_universe() -> None:
    config = load_config("config/base.yaml")
    market = _bundle({"good": 5e9, "zero_cap": 0.0})

    universe = build_rebalance_universe(
        market, [market.price.index[0]], config
    )

    assert "zero_cap" not in set(universe["coin_id"])
    assert "good" in set(universe["coin_id"])


def test_negative_market_cap_is_excluded() -> None:
    config = load_config("config/base.yaml")
    market = _bundle({"good": 5e9, "neg_cap": -1.0})

    universe = build_rebalance_universe(market, [market.price.index[0]], config)

    assert "neg_cap" not in set(universe["coin_id"])


def test_zero_cap_asset_does_not_displace_real_constituent() -> None:
    """A zero-cap asset must not occupy one of the N slots."""
    config = load_config("config/base.yaml")
    config.universe.universe_size = 2
    market = _bundle({"big": 9e9, "mid": 5e9, "zero_cap": 0.0})

    universe = build_rebalance_universe(market, [market.price.index[0]], config)

    assert set(universe["coin_id"]) == {"big", "mid"}


def test_low_turnover_low_volume_asset_is_excluded() -> None:
    """A huge market cap backed by a thin float must not rank into the Top-N.

    Rain (RAIN) carried a ~$9.7B market cap while trading ~$30M/day (~0.3%
    turnover), so it ranked ~15th on paper but could not be traded in size.
    """
    config = load_config("config/base.yaml")
    config.universe.universe_size = 2
    # rain-like: $9.7B cap, $30M volume -> 0.3% turnover, well under the $200M floor
    market = _bundle({"rain_like": 9.7e9, "real": 5e9}, volume=1e9)
    market.volume["rain_like"] = 30e6

    universe = build_rebalance_universe(market, [market.price.index[0]], config)

    assert "rain_like" not in set(universe["coin_id"])
    assert "real" in set(universe["coin_id"])


def test_low_turnover_megacap_with_large_absolute_volume_is_kept() -> None:
    """The absolute-volume floor protects real mega-caps with low turnover.

    Binance Coin legitimately runs below 1% turnover but trades billions per
    day, so a pure turnover gate would wrongly drop it.
    """
    config = load_config("config/base.yaml")
    config.universe.universe_size = 2
    # bnb-like: $100B cap, $500M volume -> 0.5% turnover, but >= $200M absolute
    market = _bundle({"bnb_like": 100e9, "real": 5e9}, volume=1e9)
    market.volume["bnb_like"] = 500e6

    universe = build_rebalance_universe(market, [market.price.index[0]], config)

    assert "bnb_like" in set(universe["coin_id"])


def test_turnover_gate_is_off_when_ratio_is_zero() -> None:
    config = load_config("config/base.yaml")
    config.universe.min_turnover_ratio = 0.0
    config.universe.universe_size = 2
    market = _bundle({"rain_like": 9.7e9, "real": 5e9}, volume=1e9)
    market.volume["rain_like"] = 30e6

    universe = build_rebalance_universe(market, [market.price.index[0]], config)

    assert "rain_like" in set(universe["coin_id"])
