from __future__ import annotations

import pandas as pd

from atlas20.config import load_config
from atlas20.data.validation import validate_and_blend_history


def test_validate_and_blend_history_prefers_direct_market_cap_and_recent_price() -> None:
    config = load_config("config/base.yaml")
    cc = pd.DataFrame(
        {
            "time": [1704067200, 1704153600, 1704240000],
            "close": [100.0, 110.0, 120.0],
            "volumeto": [1000.0, 1100.0, 1200.0],
        }
    )
    cg = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "cg_price": [101.0, 111.0, 121.0],
            "cg_market_cap": [10000.0, 11100.0, 12100.0],
            "cg_volume_usd": [900.0, 1000.0, 1100.0],
        }
    )

    result = validate_and_blend_history(
        coin_id="bitcoin",
        symbol="BTC",
        name="Bitcoin",
        cc_history=cc,
        cg_history=cg,
        current_market_cap=12100.0,
        quality_config=config.data_quality,
        use_proxy_market_caps=True,
    )

    assert result.passed
    assert result.blended_history["price_source"].eq("coingecko_recent").all()
    assert result.blended_history["market_cap_source"].eq("coingecko_direct").all()
    assert result.summary["overlap_days"] == 3
