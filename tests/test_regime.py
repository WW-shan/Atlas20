from __future__ import annotations

import pandas as pd
import pytest

from atlas20.config import load_config
from atlas20.signals.regime import build_regime_frame


def test_build_regime_frame_uses_btc_and_total_market_cap() -> None:
    config = load_config("config/base.yaml")
    config.regime.btc_ma_window = 3
    config.regime.tracked_total_mcap_ma_window = 3
    config.regime.use_tracked_alt_momentum = False

    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    price = pd.DataFrame({"bitcoin": [1, 1, 1, 2, 2, 2], "ethereum": [1, 1, 1, 1.5, 1.6, 1.7]}, index=dates)
    market_cap = pd.DataFrame({"bitcoin": [10, 10, 10, 20, 20, 20], "ethereum": [5, 5, 5, 7, 8, 9]}, index=dates)

    regime = build_regime_frame(price, market_cap, config)
    assert not bool(regime.loc[dates[2], "bull"])
    assert bool(regime.loc[dates[4], "bull"])


def _total_mcap_only_config(window: int = 3):
    config = load_config("config/base.yaml")
    config.regime.use_btc_ma = False
    config.regime.use_tracked_total_mcap_ma = True
    config.regime.tracked_total_mcap_ma_window = window
    config.regime.use_tracked_alt_momentum = False
    return config


def test_total_market_cap_does_not_jump_when_an_asset_enters_the_panel() -> None:
    """The panel was assembled with hindsight, so an asset's first print is not market growth.

    Summing every asset from its first print made the total jump on entry
    (ICP added +2.4% of the total on 2021-05-10) and flipped the flag to bull
    in a flat market.
    """
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    price = pd.DataFrame({"bitcoin": [1.0] * 8}, index=dates)
    market_cap = pd.DataFrame(
        {"bitcoin": [100.0] * 8, "newcoin": [float("nan")] * 5 + [50.0] * 3},
        index=dates,
    )

    regime = build_regime_frame(price, market_cap, _total_mcap_only_config())

    assert not regime["tracked_total_mcap_above_ma"].any()
    assert not regime["bull"].any()


def test_total_market_cap_does_not_drop_when_a_feed_stops() -> None:
    """A market-cap feed that stops (EOS, MKR, MATIC) is not a market decline."""
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    price = pd.DataFrame({"bitcoin": [1.0] * 8}, index=dates)
    market_cap = pd.DataFrame(
        {
            "bitcoin": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
            "eos": [50.0] * 5 + [float("nan")] * 3,
        },
        index=dates,
    )

    regime = build_regime_frame(price, market_cap, _total_mcap_only_config())

    assert regime["bull"].iloc[2:].all()
    # Chain-linked: each day grows by the market cap of assets present on both days.
    linked = regime["tracked_total_market_cap_linked"]
    assert linked.iloc[5] / linked.iloc[4] == pytest.approx(105.0 / 104.0)


def test_alt_momentum_ignores_an_asset_entering_the_panel() -> None:
    config = _total_mcap_only_config()
    config.regime.use_tracked_total_mcap_ma = False
    config.regime.use_tracked_alt_momentum = True
    config.regime.tracked_alt_mcap_momentum_window = 3
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    price = pd.DataFrame({"bitcoin": [1.0] * 8}, index=dates)
    market_cap = pd.DataFrame(
        {
            "bitcoin": [100.0] * 8,
            "ethereum": [50.0] * 8,
            "newcoin": [float("nan")] * 5 + [30.0] * 3,
        },
        index=dates,
    )

    regime = build_regime_frame(price, market_cap, config)

    assert not regime["tracked_alt_momentum_positive"].any()
