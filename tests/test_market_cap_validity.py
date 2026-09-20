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
