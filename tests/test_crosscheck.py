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


def test_ended_primary_verifies_on_overlap_when_the_venue_stops_first() -> None:
    """A delisted series has no current print to protect.

    MATIC's provider feed stops on 2025-03-24 and Binance stops quoting it on
    2024-09-10, so the venue can never reach the primary's last print. The
    overlap is still evidence about the price level - it is what catches a
    Huobi-Token-style error - so an ended series is verified there, and the
    caller records the days that rest on the primary provider alone.
    """
    primary = _frame(120, 100.0, "price")
    venue = _frame(60, 100.5, "cg_price")

    strict = compare_daily_prices(primary, venue)
    relaxed = compare_daily_prices(primary, venue, require_latest_coverage=False)

    assert not strict.passed and strict.reason == "secondary_stale"
    assert relaxed.passed
    assert relaxed.overlap_days == 60


def test_ended_primary_still_rejects_a_level_error() -> None:
    """Relaxing freshness must not relax the actual price comparison."""
    primary = _frame(120, 100.0, "price")
    venue = _frame(60, 2.5, "cg_price")

    result = compare_daily_prices(primary, venue, require_latest_coverage=False)

    assert not result.passed
    assert result.reason in {"median_price_gap", "catastrophic_print"}


def test_ended_primary_still_needs_a_real_overlap() -> None:
    primary = _frame(120, 100.0, "price")
    venue = _frame(5, 100.0, "cg_price")

    result = compare_daily_prices(primary, venue, require_latest_coverage=False)

    assert not result.passed
    assert result.reason == "insufficient_overlap"


def _with_block(days: int, *, start: int, length: int, factor: float, level: float = 1.0) -> np.ndarray:
    prices = np.full(days, level, dtype=float)
    prices[start : start + length] *= factor
    return prices


def test_venue_catches_a_multi_week_block_the_aggregator_tolerances_let_through() -> None:
    """A 16-day block at 2.9x sits below the 3x sustained gap and the 5x
    catastrophic gap, so the aggregator tolerances pass it. A correctly
    aligned exchange venue agrees with CMC to ~0.09% on a healthy day, so the
    same block is unambiguous there."""
    primary = _frame(400, _with_block(400, start=300, length=16, factor=2.9), "price")
    venue = _frame(400, 1.0, "gate_price")

    aggregator = compare_daily_prices(primary, venue, secondary_column="gate_price")
    exchange = compare_daily_prices(primary, venue, secondary_column="gate_price", exchange_venue=True)

    assert aggregator.passed, "aggregator tolerances are unchanged"
    assert not exchange.passed
    assert exchange.reason == "venue_sustained_disagreement"
    assert exchange.longest_disagreement_run == 16


def test_venue_catches_a_block_that_is_64_percent_too_low() -> None:
    primary = _frame(400, _with_block(400, start=200, length=20, factor=0.36), "price")
    venue = _frame(400, 1.0, "binance_price")

    result = compare_daily_prices(primary, venue, secondary_column="binance_price", exchange_venue=True)

    assert not result.passed
    assert result.reason == "venue_sustained_disagreement"


def test_venue_catches_the_last_five_days_thirty_percent_high() -> None:
    primary = _frame(400, _with_block(400, start=395, length=5, factor=1.30), "price")
    venue = _frame(400, 1.0, "gate_price")

    result = compare_daily_prices(primary, venue, secondary_column="gate_price", exchange_venue=True)

    assert not result.passed
    assert result.reason == "venue_sustained_disagreement"


def test_short_venue_dislocation_is_not_a_data_error() -> None:
    """FLOW on Binance is the worst healthy venue pair in the cache: it
    traded up to 43% away from CMC, but never more than 25% apart on more
    than two consecutive days. A three-day dislocation must still pass."""
    prices = np.full(400, 1.0)
    prices[100:103] = 1.27
    prices[250:252] = [1.43, 1.30]
    primary = _frame(400, prices, "price")
    venue = _frame(400, 1.0, "binance_price")

    result = compare_daily_prices(primary, venue, secondary_column="binance_price", exchange_venue=True)

    assert result.passed, result
    assert result.longest_disagreement_run == 3


def test_recent_window_stops_a_long_overlap_from_diluting_a_block() -> None:
    """The overlap grows with every cached fetch. A 40-day 3.5x block is 4%
    of a 1,000-day overlap - under the 5% sustained share - but 11% of the
    most recent year, which is the window the tolerances were calibrated on."""
    primary = _frame(1000, _with_block(1000, start=800, length=40, factor=3.5), "price")
    source = _frame(1000, 1.0, "cg_price")

    whole = compare_daily_prices(primary, source)
    recent = compare_daily_prices(primary, source, recent_days=365)

    assert whole.passed, "documents the dilution the recent window fixes"
    assert not recent.passed
    assert recent.reason == "sustained_disagreement"


def test_recent_window_keeps_checking_an_old_block() -> None:
    """Restricting the level tests to the recent year must not let an older
    block through: the whole overlap is still tested as well."""
    primary = _frame(1000, _with_block(1000, start=100, length=80, factor=3.5), "price")
    source = _frame(1000, 1.0, "cg_price")

    result = compare_daily_prices(primary, source, recent_days=365)

    assert not result.passed
    assert result.reason == "sustained_disagreement"


# --------------------------------------------------------------------------
# Multi-source adjudication: every independent source votes.


def _source(name: str, frame: pd.DataFrame, column: str):
    from atlas20.data.crosscheck import IndependentSource

    return IndependentSource(name, frame, column)


def test_a_passing_source_does_not_hide_other_sources_disagreement() -> None:
    """CMC=250, Gate=Binance=100, CoinGecko=250. Ranking sources by "passes
    first" let CoinGecko certify CMC and discarded two exchange venues that
    agree with each other against it."""
    from atlas20.data.crosscheck import adjudicate_sources

    primary = _frame(120, 250.0, "price")
    decision = adjudicate_sources(
        primary,
        [
            _source("gateio", _frame(120, 100.0, "gate_price"), "gate_price"),
            _source("binance", _frame(120, 100.0, "binance_price"), "binance_price"),
            _source("coingecko", _frame(120, 250.0, "cg_price"), "cg_price"),
        ],
    )

    assert not decision.passed
    assert decision.reason == "cmc_isolated"
    assert set(decision.verdicts) == {"gateio", "binance", "coingecko"}
    assert decision.verdicts["coingecko"].passed
    assert not decision.verdicts["gateio"].passed


def _old_block_sources(with_binance: bool):
    """A 25-day 3.5x CMC block ~13 months back. The exchange venues cache 404
    days and see it; CoinGecko's 365-day chart starts after it."""
    days = 404
    primary = _frame(days, _with_block(days, start=10, length=25, factor=3.5), "price")
    sources = [_source("gateio", _frame(days, 1.0, "gate_price"), "gate_price")]
    if with_binance:
        sources.append(_source("binance", _frame(days, 1.0, "binance_price"), "binance_price"))
    chart = _frame(days, 1.0, "cg_price").iloc[-365:]
    sources.append(_source("coingecko", chart, "cg_price"))
    return primary, sources


def test_a_source_that_cannot_see_the_disputed_days_cannot_confirm_cmc() -> None:
    from atlas20.data.crosscheck import UNVERIFIED_REASONS, adjudicate_sources

    primary, sources = _old_block_sources(with_binance=False)

    decision = adjudicate_sources(primary, sources)

    assert decision.verdicts["coingecko"].passed, "CoinGecko never saw the block"
    assert not decision.verdicts["gateio"].passed
    assert not decision.passed
    assert decision.reason == "secondary_disagreement_unresolved"
    assert decision.reason not in UNVERIFIED_REASONS


def test_a_second_venue_that_sees_the_same_block_isolates_cmc() -> None:
    from atlas20.data.crosscheck import adjudicate_sources

    primary, sources = _old_block_sources(with_binance=True)

    decision = adjudicate_sources(primary, sources)

    assert not decision.passed
    assert decision.reason == "cmc_isolated"


def test_tie_break_must_agree_with_cmc_on_the_disputed_days_not_just_overall() -> None:
    """A 16-day 2.9x block trips the venue test but passes the aggregator
    tolerances, so CoinGecko "passes" in aggregate while quoting the same
    prices as the venue on exactly the disputed days. That is a vote against
    CMC, not a confirmation."""
    from atlas20.data.crosscheck import adjudicate_sources

    primary = _frame(400, _with_block(400, start=300, length=16, factor=2.9), "price")
    decision = adjudicate_sources(
        primary,
        [
            _source("gateio", _frame(400, 1.0, "gate_price"), "gate_price"),
            _source("coingecko", _frame(400, 1.0, "cg_price").iloc[-365:], "cg_price"),
        ],
    )

    assert decision.verdicts["coingecko"].passed
    assert not decision.passed
    assert decision.reason == "cmc_isolated"


def test_other_venue_confirms_cmc_when_one_venue_is_the_outlier() -> None:
    from atlas20.data.crosscheck import adjudicate_sources

    primary = _frame(120, 250.0, "price")
    decision = adjudicate_sources(
        primary,
        [
            _source("gateio", _frame(120, 100.0, "gate_price"), "gate_price"),
            _source("binance", _frame(120, 250.0, "binance_price"), "binance_price"),
        ],
    )

    assert decision.passed
    assert decision.reason == "third_source_confirms_cmc"
    assert decision.confirmed_by == "binance"
    assert decision.secondary_source == "gateio"
    assert decision.tertiary_source == "binance"


def test_disagreement_with_a_stale_tie_break_is_not_downgraded_to_unverified() -> None:
    """The tie-break stopped before the disputed days. The disagreement is
    proven and stays a disagreement; it used to come back as
    ``third_source_insufficient_overlap``, an *unverified* reason, which an
    operator running with ``require_cross_check=False`` would admit."""
    from atlas20.data.crosscheck import UNVERIFIED_REASONS

    primary = _frame(120, _with_block(120, start=110, length=10, factor=2.0), "price")
    secondary = _frame(120, 1.0, "cg_price")
    stale_tertiary = _frame(100, 1.0, "pap_price")

    result = adjudicate_daily_prices(primary, secondary, stale_tertiary)

    assert not result.passed
    assert result.reason not in UNVERIFIED_REASONS
    assert result.reason == "secondary_disagreement_unresolved"


def test_unverified_secondary_does_not_mask_a_disagreeing_tertiary() -> None:
    """A stale secondary plus a tertiary that proves a 2x level error used to
    come back as ``unverified``."""
    from atlas20.data.crosscheck import UNVERIFIED_REASONS

    primary = _frame(120, 1.0, "price")
    stale_secondary = _frame(110, 1.0, "cg_price")
    tertiary = _frame(120, 2.0, "pap_price")

    result = adjudicate_daily_prices(primary, stale_secondary, tertiary)

    assert not result.passed
    assert result.reason not in UNVERIFIED_REASONS


def test_every_source_verdict_is_recorded_when_all_agree() -> None:
    from atlas20.data.crosscheck import adjudicate_sources

    primary = _frame(120, 1.0, "price")
    decision = adjudicate_sources(
        primary,
        [
            _source("gateio", _frame(120, 1.0, "gate_price"), "gate_price"),
            _source("binance", _frame(120, 1.0, "binance_price"), "binance_price"),
            _source("coingecko", _frame(110, 1.0, "cg_price"), "cg_price"),
        ],
    )

    assert decision.passed
    assert decision.reason == "ok"
    assert decision.confirmed_by == "gateio"
    assert decision.verdicts["coingecko"].reason == "secondary_stale"


def test_stale_source_that_proves_a_block_reports_the_disagreement() -> None:
    """Staleness only means the *latest* print cannot be certified. A source
    four days behind (most cached CoinGecko charts are) still proves a 3.5x
    block on the days it does cover, and that must not be downgraded to the
    unverified ``secondary_stale``."""
    from atlas20.data.crosscheck import UNVERIFIED_REASONS

    primary = _frame(120, _with_block(120, start=60, length=20, factor=3.5), "price")
    stale = _frame(116, 1.0, "cg_price")

    result = compare_daily_prices(primary, stale)

    assert not result.passed
    assert result.reason == "sustained_disagreement"
    assert result.reason not in UNVERIFIED_REASONS


def test_primary_behind_its_source_records_the_lag() -> None:
    """``latest_staleness_days`` only measures a source that is *behind* CMC
    (it was clamped at zero), so a CMC feed that stopped while its venue kept
    printing looked perfectly current."""
    primary = _frame(120, 1.0, "price")
    ahead = _frame(123, 1.0, "gate_price")

    result = compare_daily_prices(primary, ahead, secondary_column="gate_price", exchange_venue=True)

    assert result.passed, "the overlap agrees; the lag is reported, not a disagreement"
    assert result.latest_staleness_days == 0
    assert result.primary_lag_days == 3


def test_price_correlation_is_reported_on_the_overlap() -> None:
    days = 120
    trend = 100.0 * 1.01 ** np.arange(days)
    primary = _frame(days, trend, "price")
    rng = np.random.default_rng(3)
    close = _frame(days, trend * (1 + rng.normal(0, 0.002, days)), "gate_price")
    flat = _frame(days, 100.0 * (1 + rng.normal(0, 0.01, days)), "gate_price")

    tracking = compare_daily_prices(primary, close, secondary_column="gate_price")
    unrelated = compare_daily_prices(primary, flat, secondary_column="gate_price", max_median_gap=10.0)

    assert tracking.price_correlation > 0.999
    assert unrelated.price_correlation < 0.5
