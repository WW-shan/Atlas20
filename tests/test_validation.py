"""Panel eligibility is decided by real provider coverage.

Every value in the panel comes from one CoinMarketCap snapshot, so the only
question left is whether there is enough of it. There is deliberately no
synthetic market-cap fallback: an asset with no supply history can never hold
a genuine Top-N rank, so it must not become rankable on invented numbers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from atlas20.config import load_config
from atlas20.data.validation import summarize_market_history


def _history(days: int, *, market_cap: float | None = 1_000.0) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "price": np.linspace(100.0, 150.0, days),
            "volume_usd": np.full(days, 1_000_000.0),
            "market_cap": np.full(days, market_cap) if market_cap is not None else np.nan,
        }
    )


def test_complete_history_passes() -> None:
    config = load_config("config/base.yaml")

    result = summarize_market_history(
        coin_id="bitcoin",
        symbol="BTC",
        name="Bitcoin",
        history=_history(120),
        quality_config=config.data_quality,
    )

    assert result.passed
    assert result.summary["validation_reason"] == "ok"
    assert result.summary["history_days"] == 120


def test_missing_market_cap_is_never_proxied() -> None:
    config = load_config("config/base.yaml")

    result = summarize_market_history(
        coin_id="no-supply-history",
        symbol="NONE",
        name="No Supply History",
        history=_history(120, market_cap=None),
        quality_config=config.data_quality,
    )

    assert not result.passed
    assert result.summary["validation_reason"] == "insufficient_market_cap_history"
    assert result.history["market_cap"].isna().all()


def test_short_history_is_rejected() -> None:
    config = load_config("config/base.yaml")

    result = summarize_market_history(
        coin_id="newcoin",
        symbol="NEW",
        name="New Coin",
        history=_history(10),
        quality_config=config.data_quality,
    )

    assert not result.passed
    assert result.summary["validation_reason"] == "insufficient_price_history"


def test_empty_history_is_rejected() -> None:
    config = load_config("config/base.yaml")

    result = summarize_market_history(
        coin_id="ghost",
        symbol="GHOST",
        name="Ghost",
        history=pd.DataFrame(),
        quality_config=config.data_quality,
    )

    assert not result.passed
    assert result.summary["validation_reason"] == "no_price_history"


def test_non_positive_prices_are_dropped() -> None:
    config = load_config("config/base.yaml")
    history = _history(3)
    history.loc[0, "price"] = 0.0

    result = summarize_market_history(
        coin_id="x",
        symbol="X",
        name="X",
        history=history,
        quality_config=config.data_quality,
    )

    assert len(result.history) == 2
    assert (result.history["price"] > 0).all()
