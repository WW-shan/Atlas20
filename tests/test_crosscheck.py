"""The panel is single-sourced, so recent prints must be verified elsewhere.

CoinMarketCap served Huobi Token at ~$0.000002 instead of ~$0.5 for 34
consecutive days in early 2025. Every row satisfied
``market_cap == price * circulating_supply``, so nothing inside CMC could
reveal it - only an independent provider can.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from atlas20.data.crosscheck import compare_daily_prices


def _frame(days: int, price: float | np.ndarray, column: str) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    values = np.full(days, price) if np.isscalar(price) else np.asarray(price, dtype=float)
    return pd.DataFrame({"date": dates, column: values})


def test_agreeing_sources_pass() -> None:
    result = compare_daily_prices(_frame(120, 100.0, "price"), _frame(120, 100.5, "cg_price"))

    assert result.passed
    assert result.reason == "ok"
    assert result.overlap_days == 120


def test_corrupted_block_is_caught() -> None:
    """A 40-day block at 1/250000th of the real price must fail."""
    prices = np.full(120, 0.5)
    prices[40:80] = 0.000002
    result = compare_daily_prices(_frame(120, prices, "price"), _frame(120, 0.5, "cg_price"))

    assert not result.passed
    assert result.reason in {"sustained_disagreement", "catastrophic_print"}
    assert result.disagreeing_share > 0.3
    assert result.worst_gap > 1000


def test_one_day_stale_print_is_caught() -> None:
    prices = np.full(120, 100.0)
    prices[-1] = 1.0
    result = compare_daily_prices(_frame(120, prices, "price"), _frame(120, 100.0, "cg_price"))

    assert not result.passed
    assert result.reason == "latest_price_gap"


def test_single_catastrophic_print_is_caught() -> None:
    """One day off by 1,000x, surrounded by agreement - a stale or mis-scaled
    print. A share-based test would average this away."""
    prices = np.full(365, 1.0)
    prices[200] = 0.0001
    result = compare_daily_prices(_frame(365, prices, "price"), _frame(365, 1.0, "cg_price"))

    assert not result.passed
    assert result.reason == "catastrophic_print"


def test_short_overlap_is_rejected_rather_than_trusted() -> None:
    result = compare_daily_prices(_frame(10, 100.0, "price"), _frame(10, 100.0, "cg_price"))

    assert not result.passed
    assert result.reason == "insufficient_overlap"


def test_missing_secondary_source_is_not_silently_accepted() -> None:
    result = compare_daily_prices(_frame(120, 100.0, "price"), pd.DataFrame())

    assert not result.passed
    assert result.reason == "no_overlap"


def test_normal_market_noise_passes() -> None:
    """Providers quote slightly different aggregates; 5% disagreement is fine."""
    rng = np.random.default_rng(7)
    primary = 100.0 * (1 + rng.normal(0, 0.01, 200))
    secondary = primary * (1 + rng.normal(0, 0.02, 200))
    result = compare_daily_prices(_frame(200, primary, "price"), _frame(200, secondary, "cg_price"))

    assert result.passed, result
