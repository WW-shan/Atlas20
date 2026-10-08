"""Cross-provider validation of recent price history.

CoinMarketCap is the only source that feeds the panel, which makes it a single
point of failure: CMC served Huobi Token at ~$0.000002 instead of ~$0.5 for 34
consecutive days in early 2025, and every one of those rows was internally
consistent (``market_cap == price x supply``). A per-row integrity check cannot
see that; an independent provider can.

This module compares CMC's daily closes against every independent provider the
cache holds: the exchange venues Gate.io and Binance, and the aggregators
CoinGecko and CoinPaprika. Every source votes (``adjudicate_sources``). When
none disagrees, a passing source certifies CMC; when any source that can check
the data disagrees, the dispute is settled day by day on the disputed days,
with the other sources that actually quote them - a source that passes in
aggregate, or never saw those days, is no confirmation. A proven disagreement
is never reported as "unverified". It only ever *validates* - the panel's
prices stay 100% CMC - so a disagreement never silently rewrites history, it
just blocks the asset until a human looks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# CoinGecko's daily point for day D is its 00:00 UTC snapshot of D+1, i.e. D's
# close (see ``atlas20.data.coingecko.daily_closes_from_market_chart``).
# Thresholds calibrated on the live universe. Across 95 healthy assets the
# median provider gap tops out at 5.9%; Huobi Token, a genuinely broken CMC
# series, sits at 31%. The 1,085x "Celsius" gap once quoted here was not a CMC
# fault: the CEL alias pointed at Compound's CMC id, so it measured Compound's
# price against Celsius's (the alias is gone; see ``legacy_unavailable``). A
# per-day "how many days disagree" test is *not* usable at tight tolerances
# for an aggregator: CoinGecko's own history carries multi-week blocks 20-60%
# away from both CMC and the exchange venues (early 2026 on ~30 assets), which
# is why only exchange venues get the tight block test below.
MEDIAN_GAP_TOLERANCE = 0.10
LATEST_GAP_TOLERANCE = 0.35
# A sustained block: no healthy asset disagrees by 3x on more than 5% of days.
SUSTAINED_GAP = 2.0
MAX_SUSTAINED_SHARE = 0.05
# Exchange venues get a much stricter block test than aggregators. Gate.io and
# Binance quote the order books CMC itself aggregates, with the same UTC-day
# candles, and on the cached universe a healthy venue agrees with CMC to a
# 0.09% median gap and a ~1% 99th percentile. The worst healthy venue pair is
# FLOW on Binance during its January 2026 dislocation: up to 43% apart, but
# never more than 25% apart on more than two consecutive days (three days at
# 20%). A CMC error is persistent - Huobi Token was wrong for 34 straight days -
# so four consecutive overlap days more than 25% apart is a data error. The
# 3x/5x aggregator gaps let a 16-day 2.9x block, a 20-day block 64% too low
# and a +30% final week straight through against a correct venue.
VENUE_RUN_GAP = 0.25
VENUE_MAX_RUN_DAYS = 3
# Even a single day this far apart is a data error, not a move: both providers
# quote the same underlying move, so only a corrupted print produces it.
CATASTROPHIC_GAP = 5.0
MIN_OVERLAP_DAYS = 30
# The independent series must cover the primary provider's latest date.  A
# stale overlap can agree perfectly while saying nothing about the current
# print, which is exactly the blind spot that let a live CMC corruption block
# remain invisible until enough future data arrived.
MAX_LATEST_STALENESS_DAYS = 0
UNVERIFIED_REASONS = {
    "no_overlap",
    "insufficient_overlap",
    "secondary_stale",
    "latest_primary_unverified",
    "unverified",
}


@dataclass
class CrossCheckResult:
    """Agreement between the primary series and an independent provider."""

    passed: bool
    reason: str
    overlap_days: int
    median_gap: float
    latest_gap: float
    latest_overlap_date: pd.Timestamp | None
    disagreeing_share: float = 0.0
    worst_gap: float = float("nan")
    primary_latest_date: pd.Timestamp | None = None
    secondary_latest_date: pd.Timestamp | None = None
    latest_staleness_days: int | None = None
    latest_primary_covered: bool = False
    # The level tests evaluated on the most recent ``recent_days`` of the
    # overlap only (equal to the whole-overlap values when no window is set).
    recent_median_gap: float = float("nan")
    recent_disagreeing_share: float = 0.0
    # Longest run of consecutive overlap days more than ``VENUE_RUN_GAP``
    # apart; only an exchange venue is failed on it.
    longest_disagreement_run: int = 0
    # Days the *primary* stops before the independent source does. The
    # reverse of ``latest_staleness_days`` (which is clamped at zero): a CMC
    # feed that stalled while its venue kept printing used to look current.
    primary_lag_days: int | None = None
    # Pearson correlation of log closes over the overlap (NaN when either
    # series is flat or the overlap is shorter than three days).
    price_correlation: float = float("nan")


def _longest_run(mask: pd.Series) -> int:
    """Length of the longest run of consecutive True values."""
    longest = current = 0
    for flagged in mask.to_numpy(dtype=bool):
        current = current + 1 if flagged else 0
        longest = max(longest, current)
    return longest


def _daily_closes(frame: pd.DataFrame, price_column: str) -> pd.Series:
    if frame is None or frame.empty or price_column not in frame.columns:
        return pd.Series(dtype=float)
    prepared = frame[["date", price_column]].copy()
    # Providers mix timezone-aware UTC timestamps with naive dates.  Normalize
    # both to naive UTC dates before merging or pandas refuses to align them.
    prepared["date"] = (
        pd.to_datetime(prepared["date"], errors="coerce", utc=True)
        .dt.tz_convert(None)
        .dt.normalize()
    )
    prepared[price_column] = pd.to_numeric(prepared[price_column], errors="coerce")
    prepared = prepared.dropna()
    prepared = prepared[prepared[price_column] > 0]
    series = prepared.sort_values("date").groupby("date")[price_column].last()
    return series.astype(float)


def compare_daily_prices(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    *,
    primary_column: str = "price",
    secondary_column: str = "cg_price",
    min_overlap_days: int = MIN_OVERLAP_DAYS,
    max_median_gap: float = MEDIAN_GAP_TOLERANCE,
    max_latest_gap: float = LATEST_GAP_TOLERANCE,
    max_latest_staleness_days: int = MAX_LATEST_STALENESS_DAYS,
    require_latest_coverage: bool = True,
    exchange_venue: bool = False,
    recent_days: int | None = None,
) -> CrossCheckResult:
    """Compare two daily close series and require current primary coverage.

    The comparison only certifies the primary provider when the independent
    series reaches the primary provider's latest date.  A stale secondary
    series is useful for historical context but cannot validate today's print,
    so it fails with ``secondary_stale`` instead of passing on an old overlap.

    ``require_latest_coverage=False`` is for a primary series that has *ended*
    (a delisting or a token migration): there is no current print to protect,
    and every venue stops quoting such an asset at some point, so the check
    falls back to the overlap itself - the median, sustained, latest-overlap
    and catastrophic-print tests all still run, which is what catches a
    Huobi-Token-style level error. The uncovered tail is recorded by the caller
    rather than silently accepted.

    ``exchange_venue=True`` adds the venue block test (``VENUE_RUN_GAP`` for
    more than ``VENUE_MAX_RUN_DAYS`` consecutive days). ``recent_days`` repeats
    the median and sustained-share tests on the most recent part of the
    overlap: cached venue windows accumulate, so a whole-overlap share keeps
    shrinking as history is added and would eventually hide any block. The
    whole overlap is still tested too, so an older block is never let through.
    """
    left = _daily_closes(primary, primary_column)
    right = _daily_closes(secondary, secondary_column)

    primary_latest = pd.Timestamp(left.index.max()) if not left.empty else None
    secondary_latest = pd.Timestamp(right.index.max()) if not right.empty else None
    if primary_latest is not None and secondary_latest is not None:
        latest_staleness_days = max(int((primary_latest - secondary_latest).days), 0)
        primary_lag_days = max(int((secondary_latest - primary_latest).days), 0)
    else:
        latest_staleness_days = None
        primary_lag_days = None

    overlap = pd.concat({"primary": left, "secondary": right}, axis=1, sort=True).dropna()
    latest_primary_covered = primary_latest is not None and primary_latest in overlap.index

    if overlap.empty:
        return CrossCheckResult(
            False,
            "no_overlap",
            0,
            np.nan,
            np.nan,
            None,
            primary_latest_date=primary_latest,
            secondary_latest_date=secondary_latest,
            latest_staleness_days=latest_staleness_days,
            latest_primary_covered=False,
            primary_lag_days=primary_lag_days,
        )

    # Symmetric multiplicative gap. A plain relative difference saturates at
    # 100% whenever the bad print is the *lower* one, which would hide a print
    # that is 250,000x too small - exactly the Huobi Token failure mode.
    low = overlap["primary"].abs().clip(lower=1e-18)
    high = overlap["secondary"].abs().clip(lower=1e-18)
    relative_gap = pd.concat([low / high, high / low], axis=1).max(axis=1) - 1.0
    median_gap = float(relative_gap.median())
    latest_gap = float(relative_gap.iloc[-1])
    worst_gap = float(relative_gap.max())
    disagreeing_share = float((relative_gap > SUSTAINED_GAP).mean())
    days = int(len(overlap))
    latest_date = pd.Timestamp(overlap.index[-1])
    recent_gap = relative_gap
    if recent_days is not None:
        recent_gap = relative_gap[relative_gap.index > latest_date - pd.Timedelta(days=int(recent_days))]
    recent_median_gap = float(recent_gap.median()) if not recent_gap.empty else median_gap
    recent_disagreeing_share = (
        float((recent_gap > SUSTAINED_GAP).mean()) if not recent_gap.empty else disagreeing_share
    )
    longest_disagreement_run = _longest_run(relative_gap > VENUE_RUN_GAP)
    log_closes = np.log(overlap.clip(lower=1e-18))
    price_correlation = (
        float(log_closes["primary"].corr(log_closes["secondary"]))
        if days >= 3 and log_closes["primary"].std() > 0 and log_closes["secondary"].std() > 0
        else float("nan")
    )

    def verdict(passed: bool, reason: str) -> CrossCheckResult:
        return CrossCheckResult(
            passed,
            reason,
            days,
            median_gap,
            latest_gap,
            latest_date,
            disagreeing_share,
            worst_gap,
            primary_latest,
            secondary_latest,
            latest_staleness_days,
            latest_primary_covered,
            recent_median_gap,
            recent_disagreeing_share,
            longest_disagreement_run,
            primary_lag_days,
            price_correlation,
        )

    # "Too little overlap" is the only reason a source cannot check the data
    # at all. Everything it *can* check is checked before freshness: a stale
    # source cannot certify the current print, but a block it covers is still
    # a proven disagreement, never an unverified one.
    if days < min_overlap_days:
        return verdict(False, "insufficient_overlap")
    if max(median_gap, recent_median_gap) > max_median_gap:
        return verdict(False, "median_price_gap")
    if max(disagreeing_share, recent_disagreeing_share) > MAX_SUSTAINED_SHARE:
        return verdict(False, "sustained_disagreement")
    if exchange_venue and longest_disagreement_run > VENUE_MAX_RUN_DAYS:
        return verdict(False, "venue_sustained_disagreement")
    if latest_gap > max_latest_gap:
        return verdict(False, "latest_price_gap")
    if worst_gap > CATASTROPHIC_GAP:
        return verdict(False, "catastrophic_print")
    if require_latest_coverage and (
        secondary_latest is None
        or latest_staleness_days is None
        or latest_staleness_days > max_latest_staleness_days
    ):
        return verdict(False, "secondary_stale")
    if require_latest_coverage and not latest_primary_covered:
        return verdict(False, "latest_primary_unverified")
    return verdict(True, "ok")


@dataclass
class CrossCheckDecision:
    """Final multi-source decision for one primary series.

    ``verdicts`` holds every available source's own CMC comparison, keyed by
    source name. ``secondary`` is the comparison the decision turned on: the
    disagreeing source being adjudicated, or the confirming source when no
    source disagrees. ``tertiary`` is the tie-break that settled a dispute and
    ``secondary_vs_tertiary`` compares the two independent sources directly.
    ``confirmed_by`` names the provider that certifies CMC's current print.
    """

    passed: bool
    reason: str
    secondary: CrossCheckResult
    tertiary: CrossCheckResult | None = None
    secondary_vs_tertiary: CrossCheckResult | None = None
    tertiary_checked: bool = False
    confirmed_by: str | None = None
    verdicts: dict[str, CrossCheckResult] = field(default_factory=dict)
    secondary_source: str = ""
    tertiary_source: str = ""

    @property
    def overlap_days(self) -> int:
        return self.secondary.overlap_days

    @property
    def median_gap(self) -> float:
        return self.secondary.median_gap

    @property
    def latest_gap(self) -> float:
        return self.secondary.latest_gap

    @property
    def latest_overlap_date(self) -> pd.Timestamp | None:
        return self.secondary.latest_overlap_date

    @property
    def disagreeing_share(self) -> float:
        return self.secondary.disagreeing_share

    @property
    def worst_gap(self) -> float:
        return self.secondary.worst_gap

    @property
    def effective_result(self) -> CrossCheckResult:
        """The comparison that actually supports the decision.

        When a stale or disagreeing secondary is replaced by a passing
        tertiary vote, the tertiary comparison is the one that certifies the
        current primary print.
        """
        if self.confirmed_by is not None and self.tertiary is not None:
            return self.tertiary
        return self.secondary

    @property
    def latest_primary_date(self) -> pd.Timestamp | None:
        return self.effective_result.primary_latest_date

    @property
    def latest_secondary_date(self) -> pd.Timestamp | None:
        return self.effective_result.secondary_latest_date

    @property
    def latest_staleness_days(self) -> int | None:
        return self.effective_result.latest_staleness_days

    @property
    def latest_primary_covered(self) -> bool:
        return self.effective_result.latest_primary_covered

    @property
    def effective_median_gap(self) -> float:
        """Median gap of the provider pair that actually supported CMC."""
        return self.effective_result.median_gap


# Exchange venues get the venue block test; aggregators keep the looser
# tolerances their noisier snapshots need.
EXCHANGE_VENUES = frozenset({"gateio", "binance"})


@dataclass(frozen=True, eq=False)
class IndependentSource:
    """One independent price series offered to the adjudicator."""

    name: str
    frame: pd.DataFrame
    column: str

    @property
    def exchange_venue(self) -> bool:
        return self.name in EXCHANGE_VENUES


def _is_disagreement(result: CrossCheckResult) -> bool:
    """A source that could check the data and found it wrong."""
    return not result.passed and result.reason not in UNVERIFIED_REASONS


def _symmetric_gap(left: pd.Series, right: pd.Series) -> pd.Series:
    low = left.abs().clip(lower=1e-18)
    high = right.abs().clip(lower=1e-18)
    return pd.concat([low / high, high / low], axis=1).max(axis=1) - 1.0


@dataclass
class _DisputeOutcome:
    """How one disagreeing source's dispute with CMC was settled."""

    source: IndependentSource
    reason: str
    tie_break: IndependentSource | None = None
    confirmed_by: str | None = None

    @property
    def resolved(self) -> bool:
        return self.reason == "third_source_confirms_cmc"


def _settle_dispute(
    disputant: IndependentSource,
    others: list[IndependentSource],
    closes: dict[str, pd.Series],
    primary: pd.Series,
    verdicts: dict[str, CrossCheckResult],
    *,
    day_tolerance: float,
) -> _DisputeOutcome:
    """Vote on the days a source disputes, with every source that saw them.

    The disputed days are the ones on which the disputant is more than
    ``day_tolerance`` away from CMC. Each other source votes only on the
    disputed days it actually quotes, and on each such day it sides with
    whichever of CMC and the disputant it is within ``day_tolerance`` of (and
    closer to). Two things follow that a whole-series pass/fail cannot give:

    * a source that never saw the disputed days cannot vote. CoinGecko's
      365-day chart used to "confirm" CMC against a Gate.io block 13 months
      back simply because the block was outside its window;
    * a source that passes in aggregate still votes against CMC if it quotes
      the disputant's prices on the disputed days - aggregator tolerances let
      a 16-day 2.9x block through, so "CoinGecko passes" is no confirmation.

    A dispute is settled in CMC's favour only when sources that pass their
    own full comparison side with CMC on *every* disputed day. Any source that
    sides with the disputant on most of the disputed days it saw isolates CMC.
    Anything else stays an unresolved disagreement - never "unverified".
    """
    theirs = closes[disputant.name]
    joint = pd.concat({"primary": primary, "disputant": theirs}, axis=1, sort=True).dropna()
    gaps = _symmetric_gap(joint["primary"], joint["disputant"])
    disputed = gaps.index[gaps > day_tolerance]
    if disputed.empty:
        # Every disagreement reason implies at least one day beyond the day
        # tolerance; fall back to the latest shared day defensively.
        disputed = gaps.index[-1:]

    confirmed: dict[str, pd.Index] = {}
    first_checker: IndependentSource | None = None
    for other in others:
        quotes = closes[other.name]
        seen = disputed.intersection(quotes.index)
        if seen.empty:
            continue
        if first_checker is None:
            first_checker = other
        to_primary = _symmetric_gap(primary.loc[seen], quotes.loc[seen])
        to_disputant = _symmetric_gap(theirs.loc[seen], quotes.loc[seen])
        sides_primary = (to_primary <= day_tolerance) & (to_primary < to_disputant)
        sides_disputant = (to_disputant <= day_tolerance) & (to_disputant < to_primary)
        if int(sides_disputant.sum()) * 2 > len(seen):
            return _DisputeOutcome(disputant, "cmc_isolated", tie_break=other)
        if verdicts[other.name].passed:
            confirmed[other.name] = seen[sides_primary.to_numpy()]

    if confirmed:
        covered = pd.Index([])
        for days in confirmed.values():
            covered = covered.union(days)
        if disputed.difference(covered).empty:
            best = max(confirmed, key=lambda name: len(confirmed[name]))
            tie_break = next(source for source in others if source.name == best)
            return _DisputeOutcome(disputant, "third_source_confirms_cmc", tie_break=tie_break, confirmed_by=best)
    if first_checker is not None:
        return _DisputeOutcome(disputant, "two_providers_disagree", tie_break=first_checker)
    return _DisputeOutcome(
        disputant,
        "secondary_disagreement_unresolved",
        tie_break=others[0] if others else None,
    )


def adjudicate_sources(
    primary: pd.DataFrame,
    sources: list[IndependentSource],
    *,
    primary_column: str = "price",
    min_overlap_days: int = MIN_OVERLAP_DAYS,
    max_median_gap: float = MEDIAN_GAP_TOLERANCE,
    max_latest_gap: float = LATEST_GAP_TOLERANCE,
    max_latest_staleness_days: int = MAX_LATEST_STALENESS_DAYS,
    require_latest_coverage: bool = True,
    recent_days: int | None = None,
) -> CrossCheckDecision:
    """Decide whether CMC is corroborated, letting every source vote.

    Every non-empty source is compared with CMC. The old rule took the first
    source that *passed* and discarded the rest, so CMC=250 against
    Gate=Binance=100 was admitted on CoinGecko's word. Now:

    * no source disagrees - CMC passes if any source passes ("ok"), and is
      "unverified" if none can check the current print;
    * any source disagrees - each dispute is settled on its own disputed days
      (see ``_settle_dispute``); CMC passes only if every dispute is settled
      in its favour ("third_source_confirms_cmc"). A proven disagreement is
      never reported as unverified, whatever state the other sources are in.

    ``sources`` is in preference order: it decides which passing source is
    named as the confirmation.
    """
    available = [source for source in sources if source.frame is not None and not source.frame.empty]

    def compare(
        left_frame: pd.DataFrame,
        right_frame: pd.DataFrame,
        *,
        left_column: str,
        right_column: str,
        exchange_venue: bool = False,
        window: int | None = None,
        latest_coverage: bool = require_latest_coverage,
    ) -> CrossCheckResult:
        return compare_daily_prices(
            left_frame,
            right_frame,
            primary_column=left_column,
            secondary_column=right_column,
            min_overlap_days=min_overlap_days,
            max_median_gap=max_median_gap,
            max_latest_gap=max_latest_gap,
            max_latest_staleness_days=max_latest_staleness_days,
            require_latest_coverage=latest_coverage,
            exchange_venue=exchange_venue,
            recent_days=window,
        )

    verdicts = {
        source.name: compare(
            primary,
            source.frame,
            left_column=primary_column,
            right_column=source.column,
            exchange_venue=source.exchange_venue,
            window=recent_days,
        )
        for source in available
    }

    disputants = [source for source in available if _is_disagreement(verdicts[source.name])]
    if not disputants:
        passing = [source for source in available if verdicts[source.name].passed]
        if passing:
            first = passing[0]
            return CrossCheckDecision(
                True,
                "ok",
                verdicts[first.name],
                confirmed_by=first.name,
                verdicts=verdicts,
                secondary_source=first.name,
            )
        if available:
            first = available[0]
            return CrossCheckDecision(
                False, "unverified", verdicts[first.name], verdicts=verdicts, secondary_source=first.name
            )
        empty = compare(primary, pd.DataFrame(), left_column=primary_column, right_column="price")
        return CrossCheckDecision(False, "unverified", empty, verdicts=verdicts)

    left = _daily_closes(primary, primary_column)
    closes = {source.name: _daily_closes(source.frame, source.column) for source in available}
    outcomes = [
        _settle_dispute(
            disputant,
            [source for source in available if source.name != disputant.name],
            closes,
            left,
            verdicts,
            day_tolerance=max_median_gap,
        )
        for disputant in disputants
    ]
    # Report the worst dispute: an isolated CMC first, then any unresolved one.
    deciding = next(
        (outcome for outcome in outcomes if outcome.reason == "cmc_isolated"),
        next((outcome for outcome in outcomes if not outcome.resolved), outcomes[0]),
    )
    tie_break = deciding.tie_break
    tertiary = verdicts[tie_break.name] if tie_break is not None else None
    secondary_vs_tertiary = None
    if tie_break is not None:
        secondary_vs_tertiary = compare(
            deciding.source.frame,
            tie_break.frame,
            left_column=deciding.source.column,
            right_column=tie_break.column,
            latest_coverage=False,
        )
    passed = all(outcome.resolved for outcome in outcomes)
    return CrossCheckDecision(
        passed,
        deciding.reason,
        verdicts[deciding.source.name],
        tertiary,
        secondary_vs_tertiary,
        tertiary_checked=tie_break is not None,
        confirmed_by=deciding.confirmed_by if passed else None,
        verdicts=verdicts,
        secondary_source=deciding.source.name,
        tertiary_source=tie_break.name if tie_break is not None else "",
    )


def adjudicate_daily_prices(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    tertiary: pd.DataFrame | None = None,
    *,
    primary_column: str = "price",
    secondary_column: str = "cg_price",
    tertiary_column: str = "pap_price",
    secondary_source: str = "coingecko",
    tertiary_source: str = "coinpaprika",
    min_overlap_days: int = MIN_OVERLAP_DAYS,
    max_median_gap: float = MEDIAN_GAP_TOLERANCE,
    max_latest_gap: float = LATEST_GAP_TOLERANCE,
    max_latest_staleness_days: int = MAX_LATEST_STALENESS_DAYS,
    require_latest_coverage: bool = True,
    recent_days: int | None = None,
) -> CrossCheckDecision:
    """Two-source form of :func:`adjudicate_sources`, kept for callers that
    hold exactly a secondary and an optional tertiary series."""
    sources = [IndependentSource(secondary_source, secondary, secondary_column)]
    if tertiary is not None and not tertiary.empty:
        sources.append(IndependentSource(tertiary_source, tertiary, tertiary_column))
    return adjudicate_sources(
        primary,
        sources,
        primary_column=primary_column,
        min_overlap_days=min_overlap_days,
        max_median_gap=max_median_gap,
        max_latest_gap=max_latest_gap,
        max_latest_staleness_days=max_latest_staleness_days,
        require_latest_coverage=require_latest_coverage,
        recent_days=recent_days,
    )
