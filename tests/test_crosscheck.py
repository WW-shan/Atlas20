"""The panel is single-sourced, so recent prints must be verified elsewhere.

CoinMarketCap served Huobi Token at ~$0.000002 instead of ~$0.5 for 34
consecutive days in early 2025. Every row satisfied
``market_cap == price * circulating_supply``, so nothing inside CMC could
reveal it - only an independent provider can.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from atlas20.data.crosscheck import adjudicate_daily_prices, compare_daily_prices


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


def test_third_source_adjudicates_celsius_as_cmc_outlier() -> None:
    """CoinGecko and CoinPaprika agree; CMC is the isolated provider."""
    days = 120
    primary = _frame(days, 20.0, "price")
    secondary = _frame(days, 0.006, "cg_price")
    tertiary = _frame(days, 0.0061, "pap_price")

    result = adjudicate_daily_prices(primary, secondary, tertiary)

    assert not result.passed
    assert result.reason == "cmc_isolated"
    assert result.tertiary_checked
    assert result.confirmed_by is None


def test_third_source_can_confirm_cmc_when_coingecko_is_outlier() -> None:
    """The Huobi-like case: CoinGecko's level is 30% away, while the third
    provider confirms CMC's level.  A noisy latest print must not override the
    median-level majority."""
    days = 120
    primary = _frame(days, 1.0, "price")
    secondary = _frame(days, 1.3, "cg_price")
    secondary.loc[secondary.index[-1], "cg_price"] = 0.1
    tertiary = _frame(days, 1.0, "pap_price")

    result = adjudicate_daily_prices(primary, secondary, tertiary)

    assert result.passed
    assert result.reason == "third_source_confirms_cmc"
    assert result.confirmed_by == "coinpaprika"
    assert result.effective_median_gap == 0.0


def test_third_source_catches_a_single_bad_cmc_print() -> None:
    """Both independent providers agree on the latest print, so CMC's
    one-day stale price is not accepted just because the medians agree."""
    days = 120
    primary = _frame(days, 1.0, "price")
    primary.loc[primary.index[-1], "price"] = 0.01
    secondary = _frame(days, 1.0, "cg_price")
    tertiary = _frame(days, 1.0, "pap_price")

    result = adjudicate_daily_prices(primary, secondary, tertiary)

    assert not result.passed
    assert result.reason == "cmc_isolated"


def test_third_source_identifies_a_bad_secondary_print() -> None:
    days = 120
    primary = _frame(days, 1.0, "price")
    secondary = _frame(days, 1.0, "cg_price")
    secondary.loc[secondary.index[-1], "cg_price"] = 0.01
    tertiary = _frame(days, 1.0, "pap_price")

    result = adjudicate_daily_prices(primary, secondary, tertiary)

    assert result.passed
    assert result.reason == "third_source_confirms_cmc"
    assert result.confirmed_by == "coinpaprika"


def test_disagreement_without_third_source_is_not_silently_accepted() -> None:
    result = adjudicate_daily_prices(_frame(120, 1.0, "price"), _frame(120, 2.0, "cg_price"))

    assert not result.passed
    assert result.reason == "secondary_disagreement_unresolved"
    assert not result.tertiary_checked


def test_third_source_must_pass_the_full_check_not_just_the_median() -> None:
    """Huobi-like: the third provider's median is close to CMC, but its latest
    print and sustained disagreement still fail.  That is not a confirmation."""
    days = 120
    primary = _frame(days, 1.0, "price")
    primary.loc[primary.index[-1], "price"] = 0.2
    secondary = _frame(days, 1.3, "cg_price")
    secondary.loc[secondary.index[-1], "cg_price"] = 0.2
    tertiary = _frame(days, 1.0, "pap_price")
    tertiary.loc[tertiary.index[-1], "pap_price"] = 0.05

    result = adjudicate_daily_prices(primary, secondary, tertiary)

    assert not result.passed
    assert result.reason == "two_providers_disagree"


def test_stale_secondary_cannot_verify_the_latest_primary_print() -> None:
    """A provider that stops 10 days early must not be treated as current."""
    primary = _frame(120, 100.0, "price")
    secondary = _frame(110, 100.0, "cg_price")

    result = compare_daily_prices(primary, secondary)

    assert not result.passed
    assert result.reason == "secondary_stale"
    assert result.latest_primary_covered is False
    assert result.latest_staleness_days == 10


def test_current_secondary_marks_the_latest_primary_print_covered() -> None:
    primary = _frame(120, 100.0, "price")
    secondary = _frame(120, 100.0, "cg_price")

    result = compare_daily_prices(primary, secondary)

    assert result.passed
    assert result.latest_primary_covered is True
    assert result.latest_staleness_days == 0
