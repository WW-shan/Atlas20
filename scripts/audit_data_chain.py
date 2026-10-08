"""End-to-end audit of the research data chain.

Run this before trusting a backtest or wiring the pipeline to real money:

    .venv/bin/python scripts/audit_data_chain.py --config config/base.yaml

Every check prints PASS/FAIL with the evidence behind it. A FAIL is a data or
mechanics defect; a WARN is a gap that is understood and deliberate, so it must
be priced in by hand rather than fixed by the pipeline - for example CMC rows
whose market cap does not equal price x supply, and the point-in-time Top-N
members the panel cannot carry (a coin delisted from CoinGecko, or one excluded
as a stablecoin, still displaces a real constituent on the days it qualified).
A WARN never hides a FAIL: ``check`` records a failing condition as FAIL
whatever its ``warn`` flag says.

The panel, metadata and data-quality checks all run on the *persisted* build
(the files the strategy scripts load); an in-memory rebuild only proves that
build is still reproducible from the raw cache. The audit reads data/ and
never writes to it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.backtest.engine import cap_and_normalize, run_backtest  # noqa: E402
from atlas20.config import FrictionConfig, latest_completed_utc_day, load_config, load_sector_config  # noqa: E402
from atlas20.data.coinmarketcap import CoinMarketCapClient  # noqa: E402
from atlas20.data.completeness import assess_last_day  # noqa: E402
from atlas20.data.processor import (  # noqa: E402
    ENDED_FEED_GRACE_DAYS,
    build_processed_datasets,
    load_candidate_assets,
)
from atlas20.logging_utils import configure_logging, get_logger  # noqa: E402
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data  # noqa: E402

RESULTS: list[tuple[str, str, str]] = []
LOGGER = get_logger(__name__)


def check(name: str, ok: bool, detail: str, warn: bool = False) -> None:
    """Record one result. A failing condition is always a FAIL.

    ``warn`` only marks a *passing* check as a deliberate, understood gap. It
    used to override ``ok`` outright, which is how the freshness check reported
    a 30-day-stale panel as WARN and the interior-gap check a 41-day hole as
    WARN - neither could ever fail the audit.
    """
    RESULTS.append((name, "FAIL" if not ok else ("WARN" if warn else "PASS"), detail))


# The provider finalizes day D's close some hours after 00:00 UTC on D+1, so a
# panel may trail the latest completed UTC day by one day while that happens.
MAX_PANEL_LAG_DAYS = 1


def panel_freshness(
    last_date: pd.Timestamp,
    *,
    now: pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> tuple[bool, str]:
    """Is the panel's last day the latest completed UTC day (or one before)?

    Measured in UTC because CMC's candles close at 00:00 UTC. The local date
    used before is a day ahead of UTC for eight hours a day on this host
    (Asia/Shanghai), which printed "2d old" for a panel that was current. A
    pinned ``end_date`` caps the reference, since the panel is cut there on
    purpose. A row *after* the reference belongs to a UTC day that has not
    closed, which can only be a partial print.
    """
    reference = latest_completed_utc_day(now)
    if end_date is not None:
        reference = min(reference, pd.Timestamp(end_date).normalize())
    last = pd.Timestamp(last_date).normalize()
    behind = (reference - last).days
    detail = (
        f"last date={last.date()}, latest completed UTC day={reference.date()} "
        f"({behind}d behind; limit {MAX_PANEL_LAG_DAYS}d)"
    )
    if behind < 0:
        return False, detail + "; the panel holds a UTC day that has not closed yet"
    return behind <= MAX_PANEL_LAG_DAYS, detail


# An interior run longer than this stops looking like a provider outage day and
# starts looking like a broken feed.
MAX_INTERIOR_GAP_RUN_DAYS = 10


def interior_gaps(
    panel: pd.DataFrame,
    *,
    start: pd.Timestamp,
    max_run_days: int = MAX_INTERIOR_GAP_RUN_DAYS,
    explained_missing: Mapping[str, Collection[pd.Timestamp]] | None = None,
) -> tuple[bool, str, bool]:
    """Days a series is missing inside its own span, as ``(ok, detail, warn)``.

    CMC simply does not publish some days inside a series (2022-07-31 is
    missing for LINK, CRV and KCS alike - a provider outage day, not a coin
    event). prepare_market_data carries those at the last observed price and
    applies the cumulative move on the next print, so they distort timing by a
    day rather than inventing a price: named, they are a WARN. A run longer
    than ``max_run_days`` is a broken feed and FAILs - the check used to
    report a 41-day hole as WARN because ``warn`` overrode ``ok``. Only gaps
    on or after ``start`` (the traded window) count.

    ``explained_missing`` names the days the processor *deliberately* dropped,
    by coin id or symbol: a documented price-level corruption block such as
    HT's 34 corrupt prints. A long run is excused from the FAIL only when
    every day in it is explained *and* the feed has ended - the asset cannot
    rank after that point, so the hole cannot reach a traded window - while a
    long hole with any unexplained day, or on a live feed, still FAILs.
    """
    explained = {
        str(key): {pd.Timestamp(day).normalize() for day in days} for key, days in (explained_missing or {}).items()
    }

    def documented_days(coin_id: object, symbol: str) -> set[pd.Timestamp]:
        for key in (str(coin_id), symbol):
            if key in explained:
                return explained[key]
        return set()

    symbol_by_coin = (
        panel.drop_duplicates("coin_id").set_index("coin_id")["symbol"].to_dict() if "symbol" in panel else {}
    )
    panel_last = pd.Timestamp(panel["date"].max()).normalize()
    gap_report: list[str] = []
    broken: list[str] = []
    excused: list[str] = []
    for coin_id, group in panel.sort_values(["coin_id", "date"]).groupby("coin_id"):
        symbol = str(symbol_by_coin.get(coin_id, coin_id))
        dates = pd.DatetimeIndex(pd.to_datetime(group["date"]))
        missing = pd.date_range(dates.min(), dates.max(), freq="D").difference(dates)
        missing = missing[missing >= pd.Timestamp(start)]
        if len(missing) == 0:
            continue
        # Group consecutive missing days into runs.
        runs: list[list[pd.Timestamp]] = []
        current: list[pd.Timestamp] = [missing[0]]
        for previous, following in zip(missing[:-1], missing[1:], strict=False):
            if (following - previous).days == 1:
                current.append(following)
            else:
                runs.append(current)
                current = [following]
        runs.append(current)
        removed = documented_days(coin_id, symbol)
        removed_here = [day for day in missing if day in removed]
        feed_ended = pd.Timestamp(dates.max()).normalize() < panel_last
        long_runs = [run for run in runs if len(run) > max_run_days]
        unexcused = [run for run in long_runs if not (feed_ended and set(run) <= removed)]
        label = f"{symbol} ({len(missing)}d, longest run {max(len(run) for run in runs)}d"
        if removed_here:
            label += f", {len(removed_here)}d documented corruption removals"
        label += ")"
        gap_report.append(label)
        if unexcused:
            broken.append(label)
        elif long_runs:
            excused.append(label)
    detail = "assets with gaps in the traded window: " + (", ".join(gap_report) or "none")
    if broken:
        detail += f"; runs longer than {max_run_days}d (broken feed): " + ", ".join(broken)
    if excused:
        detail += (
            f"; runs longer than {max_run_days}d explained by documented corruption removals on an "
            "ended feed that can no longer rank (WARN, not a silent pass): " + ", ".join(excused)
        )
    return not broken, detail, bool(gap_report)


def _window_span_days(filename: str) -> int:
    """Days between the start and end recorded in a CMC cache filename."""
    parts = Path(filename).stem.split("_")
    if len(parts) != 3:
        return 0
    try:
        return int((int(parts[2]) - int(parts[1])) / 86_400)
    except ValueError:
        return 0


# ------------------------------------------------------ one build, audited
#
# The strategy scripts read the *persisted* build (panel_daily.csv and
# metadata.csv, e.g. run_phase_momentum.py), and data_quality.csv records the
# screening that produced it. The audit used to run its panel checks on an
# in-memory rebuild while its cross-check and watchlist checks read
# data_quality.csv, so after a refused or failed build it certified a mix of
# two states - neither of which was necessarily what a strategy would load.
#
# Design: the three persisted files are audited as one set, because they are
# what gets consumed. A consistency check proves they came out of the same
# build (same coin set, written back to back), and a separate drift check
# rebuilds the panel in memory from the raw cache and compares it with the
# persisted one, so a refused, failed or skipped rebuild shows up as a FAIL
# instead of being silently certified. ``build_processed_datasets`` returns no
# quality table, so the rebuild can be compared on the panel only.

PROCESSED_ARTIFACTS = ("panel_daily.csv", "metadata.csv", "data_quality.csv")
# One build writes the three files back to back (seconds for a 175k-row
# panel); files written further apart than this came from different builds.
MAX_BUILD_WRITE_SPREAD_SECONDS = 600
_DRIFT_COLUMNS = ("price", "volume_usd", "market_cap")
_ONE_BUILD_CHECK = "processed: persisted artifacts are one build"
_DRIFT_CHECK = "processed: an in-memory rebuild reproduces the persisted panel"


@dataclass(frozen=True)
class PersistedBuild:
    """The processed artifacts a strategy actually loads."""

    panel: pd.DataFrame
    metadata: pd.DataFrame
    quality: pd.DataFrame
    written_at: dict[str, float]


def load_persisted_build(processed_dir: Path) -> tuple[PersistedBuild | None, str]:
    """Read the persisted set exactly as the strategy scripts do."""
    missing = [name for name in PROCESSED_ARTIFACTS if not (processed_dir / name).exists()]
    if missing:
        return None, f"missing persisted artifact(s) {missing} in {processed_dir}"
    try:
        panel = pd.read_csv(processed_dir / "panel_daily.csv")
        metadata = pd.read_csv(processed_dir / "metadata.csv").set_index("coin_id")
        quality = pd.read_csv(processed_dir / "data_quality.csv")
        panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
        return None, f"unreadable persisted artifact in {processed_dir}: {exc}"
    written_at = {name: (processed_dir / name).stat().st_mtime for name in PROCESSED_ARTIFACTS}
    return PersistedBuild(panel, metadata, quality, written_at), ""


def persisted_build_consistency(build: PersistedBuild) -> tuple[bool, str]:
    """Did panel_daily.csv, metadata.csv and data_quality.csv come from one build?

    One build appends a metadata row for exactly the coins it writes to the
    panel, and data_quality.csv marks those coins ``included_in_panel``. An
    admitted coin may still be absent from the panel when its whole history
    ends before the panel window (the build trims to the window and skips an
    empty result), so that case is explained rather than counted.
    """
    panel_ids = set(build.panel["coin_id"].astype(str))
    metadata_ids = set(build.metadata.index.astype(str))
    quality = build.quality
    included = (
        quality["included_in_panel"].fillna(False).astype(bool)
        if "included_in_panel" in quality.columns
        else pd.Series(False, index=quality.index)
    )
    admitted = quality.loc[included]
    admitted_ids = set(admitted["coin_id"].astype(str))
    problems: list[str] = []
    if metadata_ids != panel_ids:
        problems.append(
            f"metadata.csv vs panel: only in metadata={sorted(metadata_ids - panel_ids)[:5]}, "
            f"only in panel={sorted(panel_ids - metadata_ids)[:5]}"
        )
    not_admitted = sorted(panel_ids - admitted_ids)
    if not_admitted:
        problems.append(f"panel coins data_quality.csv did not admit={not_admitted[:5]}")
    panel_start = build.panel["date"].min()
    absent = admitted[~admitted["coin_id"].astype(str).isin(panel_ids)]
    if "latest_date" in absent.columns:
        ended_before = pd.to_datetime(absent["latest_date"], errors="coerce") < panel_start
        absent = absent[~ended_before.fillna(False)]
    if not absent.empty:
        problems.append(f"admitted by data_quality.csv but absent from the panel={absent['coin_id'].astype(str).tolist()[:5]}")
    spread = max(build.written_at.values()) - min(build.written_at.values())
    if spread > MAX_BUILD_WRITE_SPREAD_SECONDS:
        oldest = min(build.written_at, key=build.written_at.__getitem__)
        problems.append(f"files written {spread / 3600:.1f}h apart (oldest: {oldest})")
    detail = f"{len(panel_ids)} coin(s) in panel_daily/metadata/data_quality; written within {spread:.0f}s"
    return not problems, detail + ("; " + "; ".join(problems) if problems else "")


def panel_drift(persisted: pd.DataFrame, rebuilt: pd.DataFrame) -> tuple[bool, str]:
    """Does a rebuild from the raw cache reproduce the persisted panel exactly?"""
    key = ["date", "coin_id"]
    columns = [column for column in _DRIFT_COLUMNS if column in persisted.columns and column in rebuilt.columns]

    def _prepared(frame: pd.DataFrame) -> pd.DataFrame:
        prepared = frame[key + columns].copy()
        prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
        prepared["coin_id"] = prepared["coin_id"].astype(str)
        for column in columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce").astype(float)
        return prepared

    left, right = _prepared(persisted), _prepared(rebuilt)
    merged = left.merge(right, on=key, how="outer", suffixes=("_persisted", "_rebuild"), indicator=True)
    only_persisted = int((merged["_merge"] == "left_only").sum())
    only_rebuild = int((merged["_merge"] == "right_only").sum())
    both = merged[merged["_merge"] == "both"]
    examples: list[str] = []
    differing = 0
    for column in columns:
        old, new = both[f"{column}_persisted"], both[f"{column}_rebuild"]
        changed = ~pd.Series(np.isclose(old, new, rtol=1e-9, atol=0.0, equal_nan=True), index=both.index)
        differing += int(changed.sum())
        for index in both.index[changed][: max(0, 3 - len(examples))]:
            examples.append(
                f"{both.at[index, 'coin_id']}@{both.at[index, 'date'].date()} {column} "
                f"{old[index]:.6g}->{new[index]:.6g}"
            )
    persisted_ids, rebuilt_ids = set(left["coin_id"]), set(right["coin_id"])

    def _span(frame: pd.DataFrame) -> str:
        return f"{frame['date'].min().date()}..{frame['date'].max().date()}" if not frame.empty else "empty"

    detail = (
        f"persisted {len(left)} rows ({_span(left)}), rebuild {len(right)} rows ({_span(right)}); "
        f"coins only in the persisted panel={sorted(persisted_ids - rebuilt_ids)[:5]}, "
        f"only in the rebuild={sorted(rebuilt_ids - persisted_ids)[:5]}; "
        f"rows only in the persisted panel={only_persisted}, rows only in the rebuild={only_rebuild}; "
        f"differing cells={differing}" + (f" (e.g. {', '.join(examples)})" if examples else "")
    )
    return not (only_persisted or only_rebuild or differing), detail


def audit_processed_build(
    config,
    *,
    rebuild: Callable[[], tuple[pd.DataFrame, pd.DataFrame]],
) -> PersistedBuild | None:
    """Load the persisted build, prove it is one build, and check it for drift.

    Every later check runs on the returned set. ``None`` means there is no
    usable persisted build, which is itself recorded as a FAIL.
    """
    build, problem = load_persisted_build(config.resolve_path(config.paths.processed_dir))
    if build is None:
        check(_ONE_BUILD_CHECK, False, problem)
        return None
    ok, detail = persisted_build_consistency(build)
    check(_ONE_BUILD_CHECK, ok, detail)
    try:
        rebuilt_panel, _ = rebuild()
    except Exception as exc:  # noqa: BLE001 - any failure is the finding
        check(_DRIFT_CHECK, False, f"the in-memory rebuild failed, so the persisted panel cannot be reproduced: {exc}")
    else:
        drift_ok, drift_detail = panel_drift(build.panel, rebuilt_panel)
        check(_DRIFT_CHECK, drift_ok, drift_detail)
    return build


# ------------------------------------------------ engine: missing returns
#
# Three explicit policies exist. ``error`` aborts on any missing return of a
# held coin. ``carry`` marks a held coin at its last close through a provider
# gap *inside its printed range* for at most ``missing_return_max_carry_days``
# and records every carried day in ``BacktestResult.gap_carries`` - CMC has no
# row for chainlink on 2022-07-31 and six pipeline strategies hold it that day.
# ``fill`` substitutes ``missing_return_fill``; it is an opt-in for
# sensitivity work and the only policy reported as a WARN. Under every policy
# an ended feed is sold at its last print rather than carried flat.


def _probe_friction(friction: FrictionConfig) -> FrictionConfig:
    return friction.model_copy(update={"fee_bps": 0.0, "slippage_bps": 0.0, "max_weight_per_coin": 1.0})


def missing_return_policy(friction: FrictionConfig) -> tuple[bool, str, bool]:
    """``(ok, detail, warn)`` for the configured missing-return policy."""
    policy = friction.missing_return_policy
    if policy == "error":
        description = "any missing return of a held coin aborts the run"
    elif policy == "carry":
        description = (
            f"a held coin is marked at its last close through a provider gap inside its printed range "
            f"for at most {friction.missing_return_max_carry_days} day(s), every carried day is recorded "
            "in gap_carries, a longer gap aborts the run"
        )
    else:
        description = (
            f"missing returns are replaced by missing_return_fill={friction.missing_return_fill} "
            "(explicit sensitivity opt-in)"
        )
    detail = f"policy={policy}: {description}; ended feeds are sold at their last print"
    return True, detail, policy == "fill"


def engine_missing_return_probe(friction: FrictionConfig) -> tuple[bool, str]:
    """Probe the engine under the configured policy with synthetic holdings.

    (a) a holding whose feed ends is liquidated at its last print; (b) a
    one-day gap inside the printed range is carried and recorded (``carry``)
    or aborts the run (``error``); (c) a gap one day longer than
    ``missing_return_max_carry_days`` aborts the run. ``fill`` replaces
    missing returns by design, so (b) and (c) expect the run to complete.
    """
    policy = friction.missing_return_policy
    probe_friction = _probe_friction(friction)
    sectors = pd.Series({"a": "Other"})
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    targets = {dates[0]: pd.Series({"a": 1.0})}

    def _run(returns: pd.DataFrame):
        return run_backtest("probe", returns, targets, sectors, probe_friction, 100.0)

    try:
        ended = _run(pd.DataFrame({"a": [0.0, 0.10, float("nan"), float("nan")]}, index=dates))
        liquidated = float(ended.weights.loc[dates[2], "a"]) == 0.0
    except Exception as exc:  # noqa: BLE001 - a raise is the finding
        liquidated = False
        LOGGER.warning("Ended-feed probe failed: %s", exc)

    parts = [f"ended feed liquidated={liquidated}"]
    one_day_ok = False
    try:
        carried_run = _run(pd.DataFrame({"a": [0.0, float("nan"), 0.05, 0.05]}, index=dates))
    except ValueError:
        one_day_ok = policy == "error"
        parts.append(f"1-day interior gap refused={policy == 'error'}")
    else:
        if policy == "carry":
            carries = getattr(carried_run, "gap_carries", pd.DataFrame())
            recorded = bool(
                not carries.empty
                and ((carries["asset"] == "a") & (carries["event"] == "carried") & (carries["date"] == dates[1])).any()
            )
            one_day_ok = recorded
            parts.append(f"1-day interior gap carried and recorded in gap_carries={recorded}")
        elif policy == "error":
            parts.append("1-day interior gap refused=False")
        else:
            one_day_ok = True
            parts.append("1-day interior gap filled (fill policy)")

    limit = int(friction.missing_return_max_carry_days)
    long_dates = pd.date_range("2024-01-01", periods=limit + 3, freq="D")
    long_returns = pd.DataFrame({"a": [0.0] + [float("nan")] * (limit + 1) + [0.05]}, index=long_dates)
    try:
        run_backtest("probe", long_returns, {long_dates[0]: pd.Series({"a": 1.0})}, sectors, probe_friction, 100.0)
        long_refused = False
    except ValueError:
        long_refused = True
    long_ok = long_refused if policy in ("error", "carry") else not long_refused
    label = f"{limit + 1}-day gap refused={long_refused}"
    parts.append(label if policy in ("error", "carry") else f"{label} (fill policy fills it)")
    return bool(liquidated and one_day_ok and long_ok), f"policy={policy}; " + ", ".join(parts)


def leverage_refusal_probe(friction: FrictionConfig) -> tuple[bool, str]:
    """Atlas20 is unlevered spot: the engine must refuse a gross cap above 1.0.

    The engine charges no funding cost, so a levered book would be funded for
    free; run_backtest therefore rejects ``max_gross_exposure > 1``. Probe
    that refusal rather than trusting it.
    """
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    try:
        run_backtest(
            "leverage-probe",
            pd.DataFrame({"a": [0.0, 0.01, 0.01]}, index=dates),
            {dates[0]: pd.Series({"a": 1.0})},
            pd.Series({"a": "Other"}),
            _probe_friction(friction),
            100.0,
            gross_target_exposure=2.0,
            max_gross_exposure=2.0,
        )
    except ValueError as exc:
        return True, f"a 2x gross cap is refused ({exc}); no leverage can be modelled, so no funding cost is owed"
    return False, "a 2x gross cap was accepted: a levered book would be funded for free (no borrow/funding cost is modelled)"


# ------------------------------------------------------ universe: the dates
#
# The universe checks used to sample a 7-day grid, which hits only 10 of the
# 69 month-end rebalance dates - and the phase-momentum champion re-ranks the
# Top 20 every day. Every real decision date is checked now: each configured
# rebalance frequency plus every day (building the universe for all ~2,100
# days takes about eight seconds).


def universe_audit_dates(
    index: pd.DatetimeIndex,
    config,
    *,
    include_daily: bool = True,
) -> tuple[list[pd.Timestamp], dict[str, int]]:
    """Every date on which a strategy can pick a portfolio, with per-source counts."""
    start = pd.Timestamp(config.start_timestamp)
    dates: set[pd.Timestamp] = set()
    counts: dict[str, int] = {}
    for name, value in config.rebalancing.frequencies.items():
        scheduled = [pd.Timestamp(day) for day in get_rebalance_dates(index, start, name, value)]
        counts[name] = len(scheduled)
        dates.update(scheduled)
    if include_daily:
        daily = [pd.Timestamp(day) for day in index[index >= start]]
        counts["daily"] = len(daily)
        dates.update(daily)
    return sorted(dates), counts


def _members(universe: pd.DataFrame) -> tuple[pd.DatetimeIndex, pd.Index]:
    return pd.DatetimeIndex(pd.to_datetime(universe["rebalance_date"])).normalize(), pd.Index(universe["coin_id"])


def _labels(universe: pd.DataFrame, mask: np.ndarray) -> list[str]:
    dates, coins = _members(universe)
    return [f"{coin}@{day.date()}" for coin, day in zip(coins[mask], dates[mask], strict=True)]


def ranks_use_same_day_cap(universe: pd.DataFrame, market_cap: pd.DataFrame) -> tuple[bool, str]:
    """Point-in-time: every member ranks on its market cap *for that date*."""
    dates, coins = _members(universe)
    rows = market_cap.index.get_indexer(dates)
    columns = market_cap.columns.get_indexer(coins)
    found = (rows >= 0) & (columns >= 0)
    actual = np.full(len(universe), np.nan)
    actual[found] = market_cap.to_numpy(dtype=float)[rows[found], columns[found]]
    ranked = pd.to_numeric(universe["market_cap"], errors="coerce").to_numpy(dtype=float)
    tolerance = np.maximum(1.0, np.abs(actual) * 1e-6)
    mismatched = np.isnan(actual) | ~(np.abs(actual - ranked) <= tolerance)
    offenders = _labels(universe, mismatched)
    return not offenders, f"{len(universe)} member-row(s) checked; mismatched rows={offenders[:5]} ({len(offenders)})"


def ranks_without_raw_cap(universe: pd.DataFrame, panel: pd.DataFrame) -> tuple[bool, str]:
    """Members whose rank leans on a forward-filled market cap.

    prepare_market_data forward-fills market cap by up to three days, so a
    feed that has ended (EOS -> Vaulta, MKR -> SKY) or skipped a day stays
    "rankable" on a stale cap. A member needs a real, positive provider cap on
    the rebalance date itself.
    """
    raw = panel.assign(date=pd.to_datetime(panel["date"]).dt.normalize()).set_index(["date", "coin_id"])["market_cap"]
    raw = pd.to_numeric(raw[~raw.index.duplicated(keep="last")], errors="coerce")
    dates, coins = _members(universe)
    values = raw.reindex(pd.MultiIndex.from_arrays([dates, coins])).to_numpy(dtype=float)
    stale = np.isnan(values) | (values <= 0)
    offenders = _labels(universe, stale)
    return not offenders, f"stale-ranked members={offenders[:5]} ({len(offenders)} of {len(universe)})"


# ------------------------------------------------ price-level corruption
#
# CMC served Huobi Token at ~1/250,000th of its price for 34 days while every
# row stayed internally consistent. The processor drops such blocks before the
# panel is written, and the audit used to re-run the same filter on the
# already-filtered panel - so it reported 0 rows by construction while 34 had
# been removed. The removals are now read from the processor's per-asset
# ``level_corruption_rows`` column (or, for an older data_quality.csv without
# it, counted by re-running the filter on the unfiltered raw CMC history),
# and the re-run on the persisted panel is kept for what it can still prove:
# that no corrupted block survived into the file a strategy loads.


def level_corruption_mask(prices: pd.Series) -> pd.Series:
    """Rows far (>20x) from two agreeing outer rings (31-60 days either side).

    The audit's own copy of the processor's filter: a trending market has
    rings that disagree and is never flagged, only a reverted level shift is.
    """
    prices = prices.astype(float)
    before = prices.shift(31).rolling(30, min_periods=15).median()
    after = prices.shift(-61).rolling(30, min_periods=15).median()
    agree = (before / after).between(1 / 3, 3)
    ratio = prices / ((before * after) ** 0.5)
    return (agree & ((ratio > 20) | (ratio < 1 / 20))).fillna(False).astype(bool)


def level_corruption_report(
    panel: pd.DataFrame,
    quality: pd.DataFrame,
    *,
    raw_histories: Callable[[], dict[str, pd.Series]],
) -> tuple[bool, str, bool]:
    """``(ok, detail, warn)``: FAIL if corruption is still in the panel, WARN if some was removed."""
    remaining: list[str] = []
    for coin_id, group in panel.groupby("coin_id"):
        series = group.sort_values("date").set_index("date")["price"]
        for day in series.index[level_corruption_mask(series).to_numpy()]:
            remaining.append(f"{coin_id}@{pd.Timestamp(day).date()}")

    if "level_corruption_rows" in quality.columns:
        counts = pd.to_numeric(quality["level_corruption_rows"], errors="coerce").fillna(0).astype(int)
        labels = quality["symbol"] if "symbol" in quality.columns else quality["coin_id"]
        removed = {str(label): int(count) for label, count in zip(labels, counts, strict=True) if count > 0}
        source = "data_quality.csv level_corruption_rows"
    else:
        removed = {}
        for label, prices in raw_histories().items():
            count = int(level_corruption_mask(prices.sort_index()).sum())
            if count:
                removed[str(label)] = count
        source = "the filter re-run on the unfiltered raw CMC history (data_quality.csv has no level_corruption_rows)"
    total = sum(removed.values())
    named = ", ".join(f"{label} ({count})" for label, count in sorted(removed.items(), key=lambda item: -item[1]))
    detail = (
        f"removed before the panel was written: {total} row(s)"
        + (f" - {named}" if named else "")
        + f", per {source}; still in the persisted panel: {len(remaining)} row(s)"
        + (f" {remaining[:6]}" if remaining else "")
    )
    return not remaining, detail, bool(total)


def raw_cmc_price_histories(config, raw_dir: Path) -> dict[str, pd.Series]:
    """Every screened coin's CMC close, merged from the cache but *unfiltered*.

    Mirrors the processor's input to its level filter: the fetch-order merge
    of the cache, trimmed to the first day with a real market cap. Read-only.
    """
    candidates = load_candidate_assets(config)
    client = CoinMarketCapClient(config.providers.coinmarketcap, raw_dir)
    histories: dict[str, pd.Series] = {}
    for row in candidates.itertuples(index=False):
        cmc_id = getattr(row, "cmc_id", None)
        if cmc_id is None or pd.isna(cmc_id):
            continue
        history = client.cached_history(int(cmc_id))
        if history.empty:
            continue
        history = history.assign(date=pd.to_datetime(history["date"], utc=True).dt.tz_localize(None).dt.normalize())
        first_supply = history.loc[pd.to_numeric(history["market_cap"], errors="coerce") > 0, "date"].min()
        if pd.notna(first_supply):
            history = history[history["date"] >= first_supply]
        histories[str(getattr(row, "symbol", cmc_id)).upper()] = history.set_index("date")["close"].astype(float)
    return histories


def parse_date_ranges(text: object) -> set[pd.Timestamp]:
    """Parse ``2025-02-05..2025-02-28, 2025-03-02..2025-03-11`` back into days."""
    if not isinstance(text, str) or not text.strip():
        return set()
    days: set[pd.Timestamp] = set()
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            if ".." in chunk:
                first, last = (part.strip() for part in chunk.split("..", 1))
                days.update(pd.date_range(pd.Timestamp(first).normalize(), pd.Timestamp(last).normalize(), freq="D"))
            else:
                days.add(pd.Timestamp(chunk).normalize())
        except ValueError:
            LOGGER.warning("Ignoring an unparsable level_corruption_dates range: %r", chunk)
    return days


def documented_removal_dates(
    quality: pd.DataFrame,
    *,
    raw_histories: Callable[[], dict[str, pd.Series]] | None = None,
) -> dict[str, set[pd.Timestamp]]:
    """Days the processor deliberately dropped as price-level corruption.

    The interior-gap check must be able to tell HT's documented corrupt prints
    (dropped before the panel was written, ``level_corruption_rows``=34) from
    an unexplained hole. ``level_corruption_dates`` carries the exact days; a
    build without usable dates falls back to re-running the audit's copy of
    the filter on the unfiltered raw CMC history, keyed by symbol because
    that is how the raw cache is keyed.
    """
    if "level_corruption_rows" not in quality.columns and "level_corruption_dates" not in quality.columns:
        return {}
    counts = (
        pd.to_numeric(quality["level_corruption_rows"], errors="coerce").fillna(0).astype(int)
        if "level_corruption_rows" in quality.columns
        else pd.Series(1, index=quality.index)
    )
    mapping: dict[str, set[pd.Timestamp]] = {}
    unresolved: list[tuple[str, str]] = []
    for row, count in zip(quality.itertuples(index=False), counts, strict=True):
        if count <= 0:
            continue
        key = str(row.coin_id)
        days = parse_date_ranges(getattr(row, "level_corruption_dates", ""))
        if days:
            mapping[key] = days
        else:
            unresolved.append((key, str(getattr(row, "symbol", key))))
    if unresolved and raw_histories is not None:
        raw = raw_histories()
        for key, symbol in unresolved:
            prices = raw.get(symbol)
            if prices is None or prices.empty:
                continue
            ordered = prices.sort_index()
            mask = level_corruption_mask(ordered)
            mapping[key] = {pd.Timestamp(day).normalize() for day in ordered.index[mask.to_numpy()]}
    return mapping


# A market-cap-ended legacy ticker (EOS -> Vaulta, MKR -> SKY) can outlive
# every venue that still quotes it: CMC keeps printing a legacy price while
# ``marketCap`` is 0, and the rolling independent cache no longer reaches the
# last rankable day. The processor keeps such an asset's frozen history - the
# point-in-time universe must not be rewritten - and marks it
# ``crosscheck_historical_unverified``. For the audit that marker is a WARN,
# never a pass: the asset cannot rank after its market-cap end, so it cannot
# be selected, and no live venue is left to check it against. A live asset
# without a source, or *any* asset whose overlapping prints are proven to
# disagree, still FAILs.


def _historical_only_mask(admitted: pd.DataFrame) -> pd.Series:
    if "crosscheck_historical_unverified" not in admitted.columns:
        return pd.Series(False, index=admitted.index)
    return admitted["crosscheck_historical_unverified"].fillna(False).astype(bool)


def _overlap_days(value: object) -> int:
    return int(value) if pd.notna(value) else 0


def admitted_agreement_check(admitted: pd.DataFrame) -> tuple[bool, str, bool]:
    """``(ok, detail, warn)``: does every admitted asset agree with the second source?

    Historical-only assets are reported apart from proven disagreements: they
    WARN (kept for the point-in-time universe, never rankable after their
    market-cap feed ended), while disagreement the provider data actually
    proves still FAILs.
    """
    passed = admitted["crosscheck_passed"].fillna(False).astype(bool)
    historical = _historical_only_mask(admitted)
    disagreeing = admitted[~passed & ~historical]
    historical_only = admitted[historical]
    detail = (
        f"{len(admitted)} admitted, verified={int(passed.sum())}; "
        f"still disagreeing={disagreeing['symbol'].tolist()[:5]}"
    )
    if not historical_only.empty:
        detail += (
            "; market-cap feed ended with no verifiable current overlap (historical-only, never "
            f"rankable after the feed end)={historical_only['symbol'].tolist()}"
        )
    return disagreeing.empty, detail, not historical_only.empty


def admitted_source_check(admitted: pd.DataFrame) -> tuple[bool, str, bool]:
    """``(ok, detail, warn)``: every *live* admitted asset has an independent source.

    A historical-only asset WARNs - no current venue quotes it any more, so
    the overlap can no longer be repaired - while a live asset without a
    source is a defect the audit still FAILs.
    """
    verified = (
        admitted["crosscheck_verified"].fillna(False).astype(bool)
        if "crosscheck_verified" in admitted.columns
        else pd.Series(True, index=admitted.index)
    )
    historical = _historical_only_mask(admitted)
    missing = admitted[~verified & ~historical]
    historical_only = admitted[historical]
    detail = f"assets without a usable independent source={missing['symbol'].tolist()[:5]}"
    if not historical_only.empty:
        detail += (
            "; historical-only assets whose source can no longer be reached (market-cap feed ended, "
            f"never rankable after it)={historical_only['symbol'].tolist()}"
        )
    return missing.empty, detail, not historical_only.empty


def ended_overlap_check(admitted: pd.DataFrame, *, min_overlap_days: int) -> tuple[bool, str, bool] | None:
    """``(ok, detail, warn)``: ended feeds verify on the overlap they do have.

    ``None`` means the build is too old to carry the ended-feed columns. A
    historical-only asset has no overlap left to verify, so it WARNs; an ended
    feed with a *provable* comparison that falls below the floor FAILs.
    """
    if "crosscheck_primary_ended" not in admitted.columns:
        return None
    ended = admitted[admitted["crosscheck_primary_ended"].fillna(False).astype(bool)]
    if ended.empty:
        return None
    tails = pd.to_numeric(ended.get("crosscheck_unverified_tail_days"), errors="coerce").fillna(0)
    overlap = pd.to_numeric(ended.get("crosscheck_overlap_days"), errors="coerce").fillna(0)
    historical = _historical_only_mask(ended)
    weak = overlap < min_overlap_days
    weak_live = weak & ~historical
    labels = []
    for row, tail in zip(ended.itertuples(), tails, strict=False):
        provider = row.crosscheck_confirmed_by
        provider = provider if isinstance(provider, str) and provider else "no provider"
        labels.append(
            f"{row.symbol} ({_overlap_days(row.crosscheck_overlap_days)}d overlap vs {provider}, "
            f"{int(tail)}d unverifiable tail)"
        )
    detail = "ended feed(s) verified over an overlap: " + ", ".join(labels)
    if weak_live.any():
        detail += f"; below the {min_overlap_days}d floor: " + ", ".join(ended.loc[weak_live, "symbol"].tolist())
    historical_weak = weak & historical
    if historical_weak.any():
        detail += (
            "; historical-only assets with no reachable overlap (market-cap feed ended, never "
            f"rankable after it): {ended.loc[historical_weak, 'symbol'].tolist()}"
        )
    return not weak_live.any(), detail, bool(weak.any())


def last_day_completeness(panel: pd.DataFrame) -> tuple[bool, str]:
    """Is the panel's newest day a finished provider day? See ``assess_last_day``.

    The processor only drops a newest day that too few assets have; a day
    every asset has, but only partially, gets through and can reshuffle the
    Top 20 through the liquidity gate.
    """
    verdict = assess_last_day(panel)
    return verdict.complete, verdict.describe()


# A cached window at least this long is a backfill request, not a tail pull.
BACKFILL_SPAN_DAYS = 300


def empty_tail_windows(
    empty: list[str],
    last_print_by_coin: dict[int, pd.Timestamp],
    *,
    grace_days: int = ENDED_FEED_GRACE_DAYS,
) -> tuple[bool, str]:
    """Is every empty CMC *tail* window explained by a series that has ended?

    A short window that came back empty is expected for a delisted or migrated
    coin: its feed stopped (MATIC on 2025-03-24), so a tail pull has nothing to
    add. For a live coin the same empty file is a provider failure. The check
    used to test only the window length - the same condition as the backfill
    check before it - so it passed by construction and never asked whether
    the series had ended. Now the coin's last real print (across every
    non-empty cache window) must precede the window's end by more than the
    processor's ended-feed grace period. Backfill-sized windows are left to
    the backfill check.
    """
    tails = [name for name in empty if _window_span_days(name) < BACKFILL_SPAN_DAYS]
    ended: set[str] = set()
    unexplained: list[str] = []
    for name in tails:
        coin_text, _, end_text = Path(name).stem.split("_")
        coin_id = int(coin_text)
        window_end = pd.Timestamp(int(end_text), unit="s").normalize()
        last = last_print_by_coin.get(coin_id)
        if last is None:
            unexplained.append(f"{name} (no cached rows at all)")
        elif pd.Timestamp(last).normalize() >= window_end - pd.Timedelta(days=grace_days):
            unexplained.append(f"{name} (last print {pd.Timestamp(last).date()}: the series is live)")
        else:
            ended.add(f"{coin_id} (ended {pd.Timestamp(last).date()})")
    detail = (
        f"empty tail windows={len(tails)}; ended series={sorted(ended) or 'none'}; "
        f"empty tails the series does not explain={unexplained[:5] or 'none'}"
    )
    return not unexplained, detail


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the Atlas20 data chain")
    parser.add_argument("--config", default="config/base.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging("ERROR")
    raw_dir = config.resolve_path(config.paths.raw_dir)

    # ---------------------------------------------------------------- cache
    cache_dir = raw_dir / "coinmarketcap" / "history"
    cache_files = sorted(cache_dir.glob("*.json"))
    corrupt: list[str] = []
    empty: list[str] = []
    windows: dict[int, list[tuple[int, int]]] = {}
    last_print: dict[int, pd.Timestamp] = {}
    for path in cache_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            corrupt.append(path.name)
            continue
        if not payload:
            empty.append(path.name)
            continue
        coin_id, start_ts, end_ts = path.stem.split("_")
        windows.setdefault(int(coin_id), []).append((int(start_ts), int(end_ts)))
        opened = [str(row.get("timeOpen"))[:10] for row in payload if isinstance(row, dict) and row.get("timeOpen")]
        if opened:
            newest = pd.Timestamp(max(opened))
            last_print[int(coin_id)] = max(newest, last_print.get(int(coin_id), newest))

    check("cmc cache: every file parses", not corrupt, f"{len(cache_files)} files, corrupt={corrupt[:5]}")
    # A short empty window is a tail refresh for a series that has ended (a
    # delisted or migrated coin has nothing to add), which is expected. An
    # empty *backfill* window means a full-history request came back with
    # nothing, and the filename alone would then convince ensure_history that
    # the coin is covered.
    empty_backfills = [name for name in empty if _window_span_days(name) >= BACKFILL_SPAN_DAYS]
    check(
        "cmc cache: no empty backfill windows",
        not empty_backfills,
        f"{len(empty)} empty window(s), backfill-sized={empty_backfills[:5]}",
    )
    tails_ok, tails_detail = empty_tail_windows(empty, last_print)
    check("cmc cache: empty tail windows are only for ended series", tails_ok, tails_detail)
    check(
        "cmc cache: one full window per coin",
        all(any(s <= 1577836800 for s, _ in w) for w in windows.values()),
        f"{len(windows)} coins with cached history",
    )

    for venue, label in (("gateio", "Gate.io"), ("binance", "Binance")):
        venue_dir = raw_dir / venue / "candles"
        venue_files = sorted(venue_dir.glob("*.json")) if venue_dir.exists() else []
        venue_corrupt: list[str] = []
        venue_empty: list[str] = []
        for path in venue_files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                venue_corrupt.append(path.name)
                continue
            if not payload or not isinstance(payload, list):
                venue_empty.append(path.name)
        check(
            f"{venue} cache: every file parses",
            not venue_corrupt,
            f"{len(venue_files)} files, corrupt={venue_corrupt[:5]}",
        )
        if venue == "gateio":
            check(
                f"{venue} cache: no empty payloads",
                not venue_empty,
                f"{len(venue_files)} files, empty={venue_empty[:5]}",
            )
        else:
            # Binance legitimately answers [] for a pair it does not carry
            # (BGB, HTX, KCS, OKB, CRO) or one it delisted before the cached
            # window opens (XMR, EOS). Caching that negative result on purpose
            # keeps the daily refresh from re-asking for a name that will never
            # appear. The failure mode worth catching is the opposite one: a
            # venue-wide block or outage would answer [] for *every* pair and
            # silently remove the venue's vote, so require most cached pairs to
            # carry data.
            carried = len(venue_files) - len(venue_empty)
            check(
                f"{venue} cache: venue-wide empty responses are ruled out",
                carried >= max(10, len(venue_files) // 2),
                f"{carried}/{len(venue_files)} cached pair(s) carry data; "
                f"unlisted/delisted={sorted(name.split('_', 1)[0] for name in venue_empty)}",
            )
        check(
            f"{venue} cache: populated for the venue vote",
            bool(venue_files),
            f"{len(venue_files)} cached pair window(s) from {label}",
        )

    # A venue vote is evidence only when the day behind it traded.  The
    # retired Binance.US feed proved the cost of counting a $2/day print: it
    # disagreed with CMC by double digits and blocked healthy assets.  The
    # floor is applied when the candles are read, so the invariant to audit is
    # that the newest *certifying* day of every pair clears it.
    binance_floor = float(config.providers.binance.min_daily_dollar_volume)
    binance_dir = raw_dir / "binance" / "candles"
    thin_rows: list[str] = []
    covered_pairs: set[str] = set()
    for path in sorted(binance_dir.glob("*.json")) if binance_dir.exists() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, list) or not payload:
            continue
        latest_row: list | None = None
        liquid_days = 0
        for row in payload:
            if not isinstance(row, (list, tuple)) or len(row) < 8:
                continue
            try:
                volume = float(row[7])
            except (TypeError, ValueError):
                continue
            if volume >= binance_floor:
                liquid_days += 1
                if latest_row is None or int(row[0]) > int(latest_row[0]):
                    latest_row = list(row)
        if liquid_days:
            covered_pairs.add(path.stem.split("_", 1)[0])
        else:
            thin_rows.append(path.name)
    check(
        "binance cache: every cached pair has a day above the volume floor",
        not thin_rows,
        f"pairs with no liquid day={thin_rows[:5]} (floor=${binance_floor:,.0f}/day)",
    )
    check(
        "binance cache: covers a meaningful share of the panel",
        len(covered_pairs) >= 50,
        f"{len(covered_pairs)} pair(s) with liquid history",
    )

    pap_cache_dir = raw_dir / "coinpaprika" / "history"
    pap_files = sorted(pap_cache_dir.glob("*.json")) if pap_cache_dir.exists() else []
    pap_corrupt: list[str] = []
    pap_empty: list[str] = []
    for path in pap_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pap_corrupt.append(path.name)
            continue
        if not payload or not isinstance(payload, list):
            pap_empty.append(path.name)
    check(
        "coinpaprika cache: every file parses",
        not pap_corrupt,
        f"{len(pap_files)} files, corrupt={pap_corrupt[:5]}",
    )
    check(
        "coinpaprika cache: no empty payloads",
        not pap_empty,
        f"empty={pap_empty[:5]}",
    )

    # ---------------------------------------------------------------- panel
    # Every check below runs on the persisted build a strategy would load; the
    # rebuild only feeds the drift check (see ``audit_processed_build``).
    build = audit_processed_build(
        config,
        rebuild=lambda: build_processed_datasets(
            config,
            load_sector_config(config.resolve_path("config/sectors.yaml")),
            persist=False,
        ),
    )
    if build is None:
        return _report()
    panel, metadata, quality = build.panel, build.metadata, build.quality
    panel = panel.sort_values(["coin_id", "date"])

    dupes = int(panel.duplicated(subset=["date", "coin_id"]).sum())
    check("panel: no duplicate (date, coin)", dupes == 0, f"duplicates={dupes}")

    bad_price = int((panel["price"] <= 0).sum() + panel["price"].isna().sum())
    check("panel: all prices positive", bad_price == 0, f"offending rows={bad_price}")

    bad_vol = int((panel["volume_usd"] < 0).sum() + panel["volume_usd"].isna().sum())
    check("panel: volume non-negative", bad_vol == 0, f"offending rows={bad_vol}")

    nonfinite_price = int((~np.isfinite(panel[["price", "volume_usd"]].to_numpy(dtype=float))).sum())
    check("panel: price and volume are finite", nonfinite_price == 0, f"non-finite cells={nonfinite_price}")

    missing_cap = int(panel["market_cap"].isna().sum())
    unrankable_share = missing_cap / max(len(panel), 1)
    if unrankable_share > 0.05:
        check("panel: unrankable rows are rare", False, f"{missing_cap} rows without a real market cap ({unrankable_share:.2%})")
    else:
        check(
            "panel: unrankable rows are rare",
            True,
            f"{missing_cap} rows ({unrankable_share:.2%}) carry no market cap and can never be ranked",
        )

    # Every coin's history must start where its real supply starts.
    def first_row_has_supply(frame: pd.DataFrame) -> bool:
        first = frame.iloc[0]
        return bool(pd.notna(first["market_cap"]) and first["market_cap"] > 0)

    offenders = [c for c, g in panel.groupby("coin_id") if not first_row_has_supply(g)]
    check(
        "panel: history starts at first real circulation",
        not offenders,
        f"coins starting without supply={offenders[:5]}",
    )

    # Marvecap must equal price x supply (provider rounding tolerance).
    worst_supply_gap = 0.0
    checked_supply = 0
    supply_gap_rows = 0
    worst_supply_label = ""
    for path in cache_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload:
            quote = row.get("quote") or {}
            close, cap, supply = quote.get("close"), quote.get("marketCap"), quote.get("circulatingSupply")
            if not close or not cap or not supply:
                continue
            checked_supply += 1
            gap = abs(cap - close * supply) / cap
            if gap > 0.01:
                supply_gap_rows += 1
            if gap > worst_supply_gap:
                worst_supply_gap = gap
                worst_supply_label = f"{path.stem.split('_', 1)[0]}@{str(row.get('timeOpen', ''))[:10]}"
    check(
        "provider: market_cap == price * supply",
        True,
        f"rows >1%={supply_gap_rows}/{checked_supply}, worst={worst_supply_gap:.4%} "
        f"({worst_supply_label or 'none'}); rankings use CMC's reported market cap directly",
        warn=worst_supply_gap > 0.01,
    )

    # Bad prints: single-day reversions and month-long level corruption.
    spikes: list[tuple[str, str]] = []
    for coin_id, g in panel.groupby("coin_id"):
        s = g.set_index("date")["price"].astype(float)
        prev, nxt = s.shift(1), s.shift(-1)
        agrees = (prev / nxt).between(0.5, 2)
        ratio = s / prev
        flagged = agrees & ((ratio > 3) | (ratio < 1 / 3)) & prev.notna() & nxt.notna()
        for date in s.index[flagged]:
            spikes.append((coin_id, str(date.date())))
    check("panel: no single-day bad prints", not spikes, f"flagged={spikes[:5]}")

    level_ok, level_detail, level_warn = level_corruption_report(
        panel, quality, raw_histories=lambda: raw_cmc_price_histories(config, raw_dir)
    )
    check("panel: no reverted price-level corruption", level_ok, level_detail, warn=level_warn)

    # --------------------------------------------------- independent source
    # ``quality`` is data_quality.csv of the same persisted build as ``panel``.
    if "crosscheck_passed" in quality.columns:
        admitted = quality[quality["included_in_panel"].fillna(False)]
        rejected = quality[~quality["included_in_panel"].fillna(False)]
        agreement_ok, agreement_detail, agreement_warn = admitted_agreement_check(admitted)
        check(
            "cross-check: every admitted asset agrees with an independent provider",
            agreement_ok,
            agreement_detail,
            warn=agreement_warn,
        )
        source_ok, source_detail, source_warn = admitted_source_check(admitted)
        check(
            "cross-check: independent source available for every admitted asset",
            source_ok,
            source_detail,
            warn=source_warn,
        )
        if "crosscheck_latest_primary_covered" in admitted.columns:
            # A live series must be corroborated at its newest print. An ended
            # series cannot be - no venue still quotes a delisted pair - so it
            # is verified on the overlap instead, and the days of its tail that
            # rest on CMC alone are reported rather than hidden.
            ended_flag = (
                admitted["crosscheck_primary_ended"].fillna(False).astype(bool)
                if "crosscheck_primary_ended" in admitted.columns
                else pd.Series(False, index=admitted.index)
            )
            live = admitted[~ended_flag]
            uncovered = live[~live["crosscheck_latest_primary_covered"].fillna(False).astype(bool)]
            check(
                "cross-check: independent source covers the latest primary print",
                uncovered.empty,
                f"{len(live)} live asset(s) checked; latest-date-uncovered={uncovered['symbol'].tolist()[:5]}",
            )
            ended_verdict = ended_overlap_check(
                admitted, min_overlap_days=config.data_quality.cross_check_min_overlap_days
            )
            if ended_verdict is not None:
                ended_ok, ended_detail, ended_warn = ended_verdict
                check(
                    "cross-check: ended series verify on their overlap",
                    ended_ok,
                    ended_detail,
                    warn=ended_warn,
                )
        else:
            check(
                "cross-check: independent source covers the latest primary print",
                False,
                "data_quality.csv lacks crosscheck_latest_primary_covered; "
                "a stale overlap could certify a current bad print",
            )
        check(
            "cross-check: unverified assets are refused",
            bool(config.data_quality.require_cross_check),
            f"require_cross_check={config.data_quality.require_cross_check}",
        )
        effective_column = (
            "crosscheck_effective_median_gap"
            if "crosscheck_effective_median_gap" in admitted.columns
            else "crosscheck_median_gap"
        )
        worst = float(admitted[effective_column].max()) if not admitted.empty else float("nan")
        check(
            "cross-check: effective provider noise stays small",
            worst <= config.data_quality.cross_check_max_median_gap,
            f"worst effective median gap among admitted assets={worst:.4%}",
        )
        if "crosscheck_third_source_checked" in quality.columns:
            third_checked = quality[quality["crosscheck_third_source_checked"].fillna(False).astype(bool)]
            confirmed = third_checked[
                third_checked["crosscheck_confirmed_by"]
                .fillna("")
                .isin(["gateio", "binance", "coingecko", "coinpaprika"])
            ]
            source_known = third_checked["crosscheck_third_source"].fillna("").ne("") if "crosscheck_third_source" in third_checked else pd.Series(False, index=third_checked.index)
            check(
                "cross-check: third-source adjudications are explicit",
                bool(confirmed["crosscheck_third_source_checked"].all()) if not confirmed.empty else True,
                "third-source checks="
                f"{len(third_checked)}, CMC confirmed by third source={len(confirmed)}",
            )
            check(
                "cross-check: every third-source check names its provider",
                bool(source_known.all()) if not third_checked.empty else True,
                f"unnamed third-source checks={int((~source_known).sum())}",
            )
            usable = third_checked[
                pd.to_numeric(third_checked.get("crosscheck_third_source_overlap_days"), errors="coerce")
                >= config.data_quality.cross_check_min_overlap_days
            ]
            check(
                "cross-check: disputed assets have a usable third-source window",
                len(usable) == len(third_checked),
                f"usable third-source windows={len(usable)}/{len(third_checked)}",
            )
        if not rejected.empty:
            blocked = rejected[
                rejected["crosscheck_passed"].fillna(False) == False  # noqa: E712
            ].head(5)
            check(
                "cross-check: rejected assets are reported, not silent",
                True,
                "blocked by the independent-source check: "
                + ", ".join(
                    f"{row.symbol} ({row.crosscheck_reason}: {1.0 + row.crosscheck_median_gap:.1f}x)"
                    for row in blocked.itertuples()
                ),
            )
    else:
        check(
            "cross-check: second provider comparison present",
            False,
            "data_quality.csv has no cross-check columns; recent CMC prints are unverified",
        )

    # ------------------------------------------------------ feed continuity
    symbol_by_coin = (
        panel.drop_duplicates("coin_id").set_index("coin_id")["symbol"].to_dict() if "symbol" in panel else {}
    )
    last_date = panel["date"].max()
    early_end = panel.groupby("coin_id")["date"].max()
    early_end = early_end[early_end < last_date]
    ended_names = ", ".join(
        f"{symbol_by_coin.get(coin_id, coin_id)} (to {pd.Timestamp(ts).date()})"
        for coin_id, ts in early_end.items()
    )
    check(
        "feed: ended feeds are named, not silent",
        True,
        f"{len(early_end)} ended feed(s): {ended_names or 'none'}. These are delistings or "
        "token migrations; the engine liquidates the position at the last print "
        "instead of carrying it flat (verified below). Their unverifiable tails are "
        "reported by the cross-check section.",
        warn=bool(len(early_end)),
    )

    # Interior provider gaps: short, named outage days WARN; a broken feed FAILs,
    # unless the missing days are documented corruption removals on an ended feed
    # (HT), which can no longer place the asset in a traded window.
    gaps_ok, gaps_detail, gaps_warn = interior_gaps(
        panel,
        start=config.start_timestamp,
        explained_missing=documented_removal_dates(
            quality, raw_histories=lambda: raw_cmc_price_histories(config, raw_dir)
        ),
    )
    check("feed: interior provider gaps are short and named", gaps_ok, gaps_detail, warn=gaps_warn)

    stale_runs: list[tuple[str, int]] = []
    for coin_id, g in panel.sort_values(["coin_id", "date"]).groupby("coin_id"):
        prices = g["price"].reset_index(drop=True)
        unchanged = prices.diff() == 0
        longest = int(unchanged.groupby((~unchanged).cumsum()).cumsum().max() or 0)
        if longest >= 5:
            stale_runs.append((coin_id, longest))
    check(
        "feed: no frozen price runs",
        not stale_runs,
        f"assets with >=5 identical consecutive closes={stale_runs[:5]}",
    )

    # ------------------------------------------------------------- universe
    market = prepare_market_data(panel, metadata, config)
    backtest_returns = market.returns.loc[config.start_timestamp : config.end_timestamp]
    audit_dates, date_counts = universe_audit_dates(backtest_returns.index, config)
    universe = build_rebalance_universe(market, audit_dates, config)
    coverage = ", ".join(f"{name}={count}" for name, count in date_counts.items())

    # Point-in-time: nothing may rank with a future market cap.
    lookahead_ok, lookahead_detail = ranks_use_same_day_cap(universe, market.market_cap)
    check(
        "universe: ranks use the same-day market cap only",
        lookahead_ok,
        f"{len(audit_dates)} decision date(s) ({coverage}); {lookahead_detail}",
    )

    monotonic = bool(
        universe.groupby("rebalance_date")["market_cap"].apply(lambda s: s.is_monotonic_decreasing).all()
    )
    check("universe: sorted by market cap descending", monotonic, f"{universe['rebalance_date'].nunique()} rebalance snapshots")

    size_ok = bool((universe.groupby("rebalance_date").size() <= config.universe.universe_size).all())
    check("universe: never exceeds universe_size", size_ok, f"max={int(universe.groupby('rebalance_date').size().max())}")

    # Survivorship. The candidate pool is seeded from *today's* listings, so a
    # coin can only reach the panel if it was onboarded while it was still hot.
    # A name that has since slid down those listings is therefore the one most
    # likely to be absent - and for a momentum strategy those are exactly the
    # blow-ups that decide the drawdown. Recompute the real point-in-time Top-N
    # straight from the raw CMC cache (every coin ever fetched, ranked by CMC's
    # own market cap) and name anything the panel does not carry.
    id_map_path = raw_dir / "coinmarketcap" / "id_map.json"
    symbol_by_id: dict[int, str] = {}
    if id_map_path.exists():
        for symbol, coin_id in json.loads(id_map_path.read_text(encoding="utf-8")).items():
            symbol_by_id.setdefault(int(coin_id), str(symbol).upper())
    for symbol, coin_id in config.universe.cmc_symbol_aliases.items():
        symbol_by_id.setdefault(int(coin_id), str(symbol).upper())

    cap_frames: list[pd.DataFrame] = []
    for path in cache_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else (payload.get("quotes") or [])
        coin_id = int(path.stem.split("_", 1)[0])
        records = [
            {
                "date": str(row.get("timeOpen"))[:10],
                "cmc_id": coin_id,
                "symbol": symbol_by_id.get(coin_id, str(coin_id)),
                "market_cap": (row.get("quote") or {}).get("marketCap"),
            }
            for row in rows
            if isinstance(row, dict)
        ]
        if records:
            cap_frames.append(pd.DataFrame(records))

    missing_members: dict[str, int] = {}
    if cap_frames:
        caps = pd.concat(cap_frames, ignore_index=True)
        caps = caps[caps["market_cap"].notna() & (caps["market_cap"] > 0)]
        caps["date"] = pd.to_datetime(caps["date"])
        caps = caps.sort_values("market_cap", ascending=False).drop_duplicates(["date", "cmc_id"])
        caps["rank"] = caps.groupby("date").cumcount() + 1
        true_top = caps[caps["rank"] <= config.universe.universe_size]
        # Only decision dates matter: those are the days a strategy actually
        # picks a portfolio. That is the same set every universe check uses -
        # each configured rebalance frequency plus every day, because the
        # phase-momentum champion re-ranks daily - not a sampled grid.
        true_top = true_top[true_top["date"].isin(set(audit_dates))]
        # Compare against the *panel*, not the ranked universe. A coin that is
        # in the panel but fails the liquidity/turnover gate was filtered for
        # tradability on purpose and the next name was promoted deliberately.
        # Only a name the panel cannot carry at all is a survivorship hole.
        panel_symbols = {str(value).upper() for value in panel["symbol"].unique()}
        absent = true_top[~true_top["symbol"].str.upper().isin(panel_symbols)]
        missing_members = {str(k): int(v) for k, v in absent.groupby("symbol").size().sort_values(ascending=False).items()}

    check(
        "universe: no real Top-N member is missing (survivorship)",
        True,
        "absent=" + (", ".join(f"{symbol} ({days}d)" for symbol, days in list(missing_members.items())[:6]) or "none"),
        warn=bool(missing_members),
    )

    # The check above can only see coins that were fetched at least once, so a
    # name that never resolved a CoinMarketCap id is invisible to it. Every id
    # on the curated historical watchlist therefore has to reach the panel, or
    # be explicitly recorded as un-onboardable with a reason and a cost. This
    # is the guard that was missing when MATIC - Top-20 on 123 of the 215
    # rebalance dates - dropped out of the pool without a single warning.
    # "Onboarded" means the coin reached the screening stage with real history
    # - not that it survived it. A name the cross-check refuses (CEL, HT) is a
    # deliberate, recorded decision, while a name that never resolved an id or
    # never got fetched is the silent hole this check exists to catch.
    screened_coin_ids = {str(value).lower() for value in quality["coin_id"].unique()}
    excused = {str(key).lower(): str(value) for key, value in config.universe.legacy_unavailable.items()}
    unknown_excuses = sorted(set(excused) - {str(value).lower() for value in config.universe.legacy_candidate_ids})
    legacy_missing = sorted(
        coin_id
        for coin_id in config.universe.legacy_candidate_ids
        if coin_id.lower() not in screened_coin_ids and coin_id.lower() not in excused
    )
    refused = quality[
        quality["coin_id"].astype(str).str.lower().isin({value.lower() for value in config.universe.legacy_candidate_ids})
        & ~quality["included_in_panel"].fillna(False).astype(bool)
    ]
    check(
        "universe: every legacy watchlist coin is onboarded or excused",
        not legacy_missing,
        f"{len(config.universe.legacy_candidate_ids)} watchlist coin(s); never onboarded and "
        f"unexcused={legacy_missing[:6]}; onboarded but refused by the cross-check="
        f"{refused['symbol'].tolist()[:5]}",
    )
    check(
        "universe: excused watchlist coins are declared with a reason",
        not unknown_excuses and all(reason.strip() for reason in excused.values()),
        "excused="
        + (", ".join(f"{key}" for key in sorted(excused)) or "none")
        + (f"; excuses for non-watchlist ids={unknown_excuses}" if unknown_excuses else ""),
        warn=bool(excused),
    )

    # A member's rank must come from a same-day market cap, on every decision
    # date - not just the ones a sampled grid happens to hit.
    stale_ok, stale_detail = ranks_without_raw_cap(universe, panel)
    check("universe: no rank leans on a forward-filled market cap", stale_ok, stale_detail)

    # ------------------------------------------------------------- engine
    # The per-coin cap has to be a real constraint, not a no-op.
    cap_probe = cap_and_normalize(pd.Series({"a": 0.6, "b": 0.4}), 0.35)
    cap_ok = bool(cap_probe.max() <= 0.35 + 1e-12 and cap_probe.sum() <= 1.0 + 1e-12)
    check(
        "engine: per-coin cap is enforced",
        cap_ok,
        f"cap(0.6/0.4, 0.35) -> max={float(cap_probe.max()):.3f} sum={float(cap_probe.sum()):.3f}",
    )

    # --------------------------------------------------------------- engine
    backtest_returns = market.returns.loc[config.start_timestamp : config.end_timestamp]
    terminal_missing = 0
    for column in backtest_returns.columns:
        observed = market.raw_price.loc[backtest_returns.index, column]
        last_observed = observed.last_valid_index()
        if last_observed is not None:
            # Returns after the last observed provider print are the dangerous
            # tail case: a delisted/halted asset must not be carried flat.
            terminal_missing += int(backtest_returns.loc[last_observed:, column].isna().sum())
    # ``error`` and ``carry`` are explicit, fail-closed policies (PASS); only
    # ``fill`` - the sensitivity opt-in - is a WARN, here and under "modelling".
    policy_ok, policy_detail, policy_warn = missing_return_policy(config.frictions)
    check(
        "engine: missing returns fail closed",
        policy_ok,
        f"{policy_detail}; terminal missing return cells={terminal_missing}",
        warn=policy_warn,
    )
    # Terminal missing returns are only safe when the engine actually exits
    # them, and interior gaps only when the configured policy really carries
    # (and records) or refuses them. Probe the engine under that policy.
    probe_ok, probe_detail = engine_missing_return_probe(config.frictions)
    check(
        "engine: ended feeds are liquidated, interior gaps follow the configured policy",
        probe_ok,
        f"terminal missing return cells={terminal_missing}; {probe_detail}",
    )

    fresh, freshness_detail = panel_freshness(market.price.index.max(), end_date=config.end_date)
    check("freshness: panel reaches the latest completed UTC day", fresh, freshness_detail)
    complete, completeness_detail = last_day_completeness(panel)
    check("freshness: the last panel day is a finished provider day", complete, completeness_detail)

    # ------------------------------------------------------------ modelling
    # The engine charges fees+slippage on turnover only - no borrow or funding
    # cost - so leverage must be impossible rather than merely unpriced.
    leverage_ok, leverage_detail = leverage_refusal_probe(config.frictions)
    check("modelling: leverage is refused (unlevered spot only)", leverage_ok, leverage_detail)
    check(
        "modelling: missing returns are explicitly handled",
        policy_ok,
        policy_detail + ". No halted or delisted holding is silently marked flat.",
        warn=policy_warn,
    )

    return _report()


def _report() -> int:
    """Print every recorded result; exit status 1 when anything FAILed."""
    width = max(len(n) for n, _, _ in RESULTS)
    print(f"\nAtlas20 data-chain audit - {len(RESULTS)} checks\n" + "=" * (width + 30))
    failures = 0
    for name, status, detail in RESULTS:
        if status == "FAIL":
            failures += 1
        print(f"[{status}] {name.ljust(width)}  {detail}")
    print("=" * (width + 30))
    print(f"PASS={sum(1 for _, s, _ in RESULTS if s == 'PASS')} "
          f"WARN={sum(1 for _, s, _ in RESULTS if s == 'WARN')} FAIL={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
