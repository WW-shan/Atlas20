from __future__ import annotations

import pandas as pd

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
