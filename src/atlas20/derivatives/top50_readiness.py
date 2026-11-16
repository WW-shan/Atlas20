"""Fail-closed Top50 data-readiness primitives.

The module selects the executable CMC cohort without inventing a second data
format.  Ranking happens elsewhere through the production universe builder;
this layer only consumes that ranking, the current Bitget symbol map and the
existing raw evidence trees.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
import hashlib
import json
import math
from typing import Any

import pandas as pd

from atlas20.config import load_config
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data

TOP50_SIZE = 50
TOP20_SIZE = 20
VENUE_UNAVAILABLE = "VENUE_UNAVAILABLE"


@dataclass(frozen=True)
class SelectionMember:
    final_rank: int
    original_rank: int
    coin_id: str
    symbol: str
    bitget_symbol: str
    panel_symbol: str


@dataclass(frozen=True)
class SelectionSkip:
    original_rank: int
    coin_id: str
    symbol: str
    reason: str


@dataclass(frozen=True)
class Top50Selection:
    as_of: date
    candidate_count: int
    members: tuple[SelectionMember, ...]
    skipped: tuple[SelectionSkip, ...]
    source_fingerprint: str


def _normalise_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _json_records(frame: pd.DataFrame, sort_by: str) -> list[dict[str, Any]]:
    records = frame.sort_values(sort_by, kind="stable").to_dict("records")
    return [
        {str(key): value for key, value in record.items()}
        for record in records
    ]


def _source_fingerprint(ranked: pd.DataFrame, symbol_map: pd.DataFrame) -> str:
    payload = {
        "ranked": _json_records(ranked, "universe_rank"),
        "map": _json_records(symbol_map, "coin_id"),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def select_executable_top50(
    ranked: pd.DataFrame,
    symbol_map: pd.DataFrame,
    *,
    as_of: date,
    size: int = TOP50_SIZE,
) -> Top50Selection:
    """Select ``size`` mapped members, skipping only absent venue contracts.

    A missing or non-normal Bitget contract does not consume a Top50 slot.  A
    selected contract with incomplete data is deliberately *not* handled here:
    it must block the readiness audit instead of silently promoting rank 51.
    """

    required_ranked = {"coin_id", "symbol", "universe_rank"}
    missing_ranked = required_ranked.difference(ranked.columns)
    if missing_ranked:
        raise ValueError(f"ranked is missing columns {sorted(missing_ranked)}")
    required_map = {"coin_id", "bitget_symbol", "contract_status"}
    missing_map = required_map.difference(symbol_map.columns)
    if missing_map:
        raise ValueError(f"symbol_map is missing columns {sorted(missing_map)}")
    if size <= 0:
        raise ValueError("size must be positive")

    ranked_work = ranked.copy()
    ranked_work["coin_id"] = ranked_work["coin_id"].map(_normalise_text)
    ranked_work["symbol"] = ranked_work["symbol"].map(_normalise_text)
    if ranked_work["coin_id"].eq("").any():
        raise ValueError("ranked contains an empty coin_id")
    if ranked_work["coin_id"].duplicated().any():
        raise ValueError("ranked contains a duplicate coin_id")
    ranked_work["universe_rank"] = pd.to_numeric(
        ranked_work["universe_rank"], errors="coerce"
    )
    if ranked_work["universe_rank"].isna().any():
        raise ValueError("ranked contains an invalid universe_rank")
    ranked_work["universe_rank"] = ranked_work["universe_rank"].astype(int)
    if ranked_work["universe_rank"].duplicated().any():
        raise ValueError("ranked contains a duplicate universe_rank")

    map_work = symbol_map.copy()
    map_work["coin_id"] = map_work["coin_id"].map(_normalise_text)
    if map_work["coin_id"].duplicated().any():
        raise ValueError("symbol_map contains a duplicate coin_id")
    mapping = map_work.set_index("coin_id", drop=False)

    members: list[SelectionMember] = []
    skipped: list[SelectionSkip] = []
    used_symbols: set[str] = set()
    for row in ranked_work.sort_values("universe_rank", kind="stable").to_dict(
        "records"
    ):
        original_rank = int(row["universe_rank"])
        coin_id = str(row["coin_id"])
        symbol = str(row["symbol"]).upper()
        mapped = mapping.loc[coin_id] if coin_id in mapping.index else None
        venue_symbol = (
            ""
            if mapped is None
            else _normalise_text(mapped.get("bitget_symbol")).upper()
        )
        status = (
            ""
            if mapped is None
            else _normalise_text(mapped.get("contract_status")).lower()
        )
        if status != "normal" or not venue_symbol:
            skipped.append(
                SelectionSkip(
                    original_rank=original_rank,
                    coin_id=coin_id,
                    symbol=symbol,
                    reason=VENUE_UNAVAILABLE,
                )
            )
            continue
        if venue_symbol in used_symbols:
            raise ValueError(
                f"duplicate Bitget contract {venue_symbol} in executable top{size}"
            )
        used_symbols.add(venue_symbol)
        members.append(
            SelectionMember(
                final_rank=len(members) + 1,
                original_rank=original_rank,
                coin_id=coin_id,
                symbol=symbol,
                bitget_symbol=venue_symbol,
                panel_symbol=(
                    ""
                    if mapped is None
                    else _normalise_text(mapped.get("panel_symbol"))
                ),
            )
        )
        if len(members) == size:
            break

    if len(members) != size:
        raise ValueError(
            f"ranked pool has only {len(members)} executable member(s), require {size}"
        )

    return Top50Selection(
        as_of=as_of,
        candidate_count=len(ranked_work),
        members=tuple(members),
        skipped=tuple(skipped),
        source_fingerprint=_source_fingerprint(ranked_work, map_work),
    )


@dataclass(frozen=True)
class CoverageEvidence:
    first: str | None
    last: str | None
    rows: int
    missing_intervals: int
    failures: tuple[str, ...]


def _utc_stamp(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _read_ohlc(
    path: Path,
    *,
    label: str,
    now: pd.Timestamp | None,
) -> tuple[pd.DatetimeIndex, pd.DataFrame, list[str], int]:
    if not path.is_file():
        return (
            pd.DatetimeIndex([]),
            pd.DataFrame(),
            [f"missing {label} file {path}"],
            0,
        )
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return (
            pd.DatetimeIndex([]),
            pd.DataFrame(),
            [f"unreadable {label} file: {exc}"],
            0,
        )
    required = {"open_time", "open", "high", "low", "close"}
    missing = required.difference(frame.columns)
    if missing:
        return (
            pd.DatetimeIndex([]),
            pd.DataFrame(),
            [f"missing {label} OHLC columns {sorted(missing)}"],
            len(frame),
        )

    failures: list[str] = []
    raw_times = pd.to_datetime(frame["open_time"], utc=True, errors="coerce")
    numeric = frame.loc[:, ["open", "high", "low", "close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    invalid_row = raw_times.isna() | numeric.isna().any(axis=1)
    if invalid_row.any():
        failures.append(f"{int(invalid_row.sum())} invalid {label} row(s)")
    valid = ~invalid_row
    times = pd.DatetimeIndex(raw_times.loc[valid])
    clean = numeric.loc[valid].copy()
    clean.index = times
    clean = clean.sort_index()
    sorted_times = pd.DatetimeIndex(times).sort_values()
    if not pd.DatetimeIndex(raw_times.dropna()).is_monotonic_increasing:
        failures.append(f"{label} open_time is not monotonic")
    if sorted_times.duplicated().any():
        failures.append(
            f"{int(sorted_times.duplicated().sum())} duplicate {label} timestamp(s)"
        )
    if not clean.empty:
        if (clean <= 0.0).any().any():
            failures.append(f"non-positive {label} price")
        invalid_ohlc = (
            clean["high"]
            < clean.loc[:, ["open", "close", "low"]].max(axis=1)
        ) | (
            clean["low"]
            > clean.loc[:, ["open", "close", "high"]].min(axis=1)
        )
        if invalid_ohlc.any():
            failures.append(f"invalid {label} OHLC relationship")
    if now is not None:
        moment = _utc_stamp(now)
        future = sorted_times[sorted_times > moment]
        if len(future):
            failures.append(
                f"{len(future)} future {label} timestamp(s), first {future[0]}"
            )
    return sorted_times, clean.sort_index(), failures, len(frame)


def _missing_failures(label: str, missing: pd.DatetimeIndex) -> list[str]:
    return [f"missing {label} {stamp.isoformat()}" for stamp in missing[:20]]


def check_panel_history(
    panel: pd.DataFrame,
    *,
    coin_id: str,
    latest_day: date,
) -> CoverageEvidence:
    """Check one coin's CMC rows from its first real print to the CMC close."""

    required = {"date", "coin_id", "price", "volume_usd", "market_cap"}
    missing_columns = required.difference(panel.columns)
    if missing_columns:
        return CoverageEvidence(
            None,
            None,
            0,
            0,
            (f"panel missing columns {sorted(missing_columns)}",),
        )
    selected = panel.loc[panel["coin_id"].astype(str).eq(str(coin_id))].copy()
    if selected.empty:
        return CoverageEvidence(None, None, 0, 0, ("missing CMC history",))

    failures: list[str] = []
    selected["date"] = (
        pd.to_datetime(selected["date"], utc=True, errors="coerce").dt.normalize()
    )
    if selected["date"].isna().any():
        failures.append(f"{int(selected['date'].isna().sum())} invalid CMC date row(s)")
    if selected["date"].duplicated().any():
        failures.append(
            f"{int(selected['date'].duplicated().sum())} duplicate CMC date row(s)"
        )
    for column in ("price", "volume_usd", "market_cap"):
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
    price = selected["price"]
    volume = selected["volume_usd"]
    market_cap = selected["market_cap"]
    if (~price.map(math.isfinite) | (price <= 0.0)).any():
        failures.append("non-positive/non-finite CMC price")
    if (~volume.map(math.isfinite) | (volume < 0.0)).any():
        failures.append("negative/non-finite CMC volume")
    if (~market_cap.map(math.isfinite) | (market_cap <= 0.0)).any():
        failures.append("non-positive/non-finite CMC market cap")

    dates = pd.DatetimeIndex(selected["date"].dropna().sort_values().unique())
    if dates.empty:
        return CoverageEvidence(
            None,
            None,
            len(selected),
            0,
            tuple(failures + ["no valid CMC dates"]),
        )
    latest = pd.Timestamp(latest_day)
    if _utc_stamp(dates.max()) > _utc_stamp(latest):
        failures.append(f"CMC series contains a future date after {latest_day}")
    expected = pd.date_range(dates.min(), _utc_stamp(latest), freq="D")
    missing = expected.difference(dates)
    failures.extend(_missing_failures("CMC day", missing))
    if dates.max().date() != latest_day:
        failures.append(f"CMC series ends {dates.max().date()}, require {latest_day}")
    return CoverageEvidence(
        first=dates.min().isoformat(),
        last=dates.max().isoformat(),
        rows=len(selected),
        missing_intervals=len(missing),
        failures=tuple(failures),
    )


def check_mark_coverage(
    path: Path,
    *,
    start: pd.Timestamp,
    required_end: pd.Timestamp,
    now: pd.Timestamp | None = None,
) -> CoverageEvidence:
    """Require every hourly mark bar from the contract start to a known end."""

    times, _clean, failures, rows = _read_ohlc(path, label="mark", now=now)
    start_utc = _utc_stamp(start)
    end_utc = _utc_stamp(required_end)
    if end_utc <= start_utc:
        raise ValueError("required_end must be after start")
    if times.empty:
        return CoverageEvidence(
            None,
            None,
            rows,
            0,
            tuple(failures + ["empty mark file"]),
        )
    unique_times = times.drop_duplicates()
    if unique_times.min() > start_utc:
        failures.append(f"mark starts {unique_times.min()}, require {start_utc}")
    expected = pd.date_range(start_utc, end_utc, freq="h", inclusive="left")
    missing = expected.difference(unique_times)
    failures.extend(_missing_failures("hour", missing))
    if unique_times.max() < end_utc - pd.Timedelta(hours=1):
        failures.append(
            f"mark ends {unique_times.max()}, require {end_utc - pd.Timedelta(hours=1)}"
        )
    return CoverageEvidence(
        first=unique_times.min().isoformat(),
        last=unique_times.max().isoformat(),
        rows=rows,
        missing_intervals=len(missing),
        failures=tuple(failures),
    )


def check_market_execution_coverage(
    path: Path,
    *,
    required_first_day: date,
    end_day: date,
    execution_utc: time = time(1, 5),
    max_lag_minutes: float = 60.0,
    now: pd.Timestamp | None = None,
) -> CoverageEvidence:
    """Require a usable floor market bar for each T+1 execution day."""

    if max_lag_minutes < 0.0:
        raise ValueError("max_lag_minutes must be non-negative")
    times, _clean, failures, rows = _read_ohlc(path, label="market", now=now)
    if times.empty:
        return CoverageEvidence(
            None,
            None,
            rows,
            0,
            tuple(failures + ["empty market file"]),
        )
    unique_times = times.drop_duplicates()
    if unique_times.min().date() > required_first_day:
        failures.append(
            "market starts "
            f"{unique_times.min().date()}, require {required_first_day} or the "
            "contract listing day"
        )
    missing_days: list[date] = []
    max_lag = pd.Timedelta(minutes=float(max_lag_minutes))
    for day in pd.date_range(required_first_day, end_day, freq="D", tz="UTC"):
        target = day + pd.Timedelta(
            hours=execution_utc.hour,
            minutes=execution_utc.minute,
        )
        earlier = unique_times[unique_times <= target]
        if earlier.empty or target - earlier[-1] > max_lag:
            missing_days.append(day.date())
    failures.extend(
        f"missing market execution coverage {day.isoformat()}" for day in missing_days
    )
    return CoverageEvidence(
        first=unique_times.min().isoformat(),
        last=unique_times.max().isoformat(),
        rows=rows,
        missing_intervals=len(missing_days),
        failures=tuple(failures),
    )


def check_market_alignment(
    market_path: Path,
    mark_paths: tuple[Path, ...],
) -> CoverageEvidence:
    """Every market bar inside mark coverage must share the mark timestamp."""

    if not Path(market_path).is_file():
        return CoverageEvidence(
            None,
            None,
            0,
            0,
            (f"missing market file {market_path}",),
        )
    try:
        market = pd.read_csv(market_path, usecols=["open_time"])
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return CoverageEvidence(None, None, 0, 0, (f"unreadable market file: {exc}",))
    market_times = pd.to_datetime(market["open_time"], utc=True, errors="coerce")
    if market_times.isna().any():
        return CoverageEvidence(
            None,
            None,
            len(market),
            0,
            ("invalid market open_time during alignment",),
        )
    market_index = pd.DatetimeIndex(market_times)
    failures: list[str] = []
    if market_index.duplicated().any():
        failures.append(
            f"{int(market_index.duplicated().sum())} duplicate market timestamp(s)"
        )
    mark_times: set[pd.Timestamp] = set()
    for path in mark_paths:
        if not Path(path).is_file():
            failures.append(f"missing mark file for alignment: {path}")
            continue
        try:
            marks = pd.read_csv(path, usecols=["open_time"])
        except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            failures.append(f"unreadable mark file for alignment: {exc}")
            continue
        parsed = pd.to_datetime(marks["open_time"], utc=True, errors="coerce").dropna()
        mark_times.update(pd.Timestamp(value) for value in parsed)
    if not mark_times:
        return CoverageEvidence(
            None,
            None,
            len(market_index),
            0,
            tuple(failures + ["no mark timestamps for market alignment"]),
        )
    low, high = min(mark_times), max(mark_times)
    inside = [
        pd.Timestamp(value)
        for value in market_index
        if low <= pd.Timestamp(value) <= high
    ]
    extra = sorted({value for value in inside if value not in mark_times})
    failures.extend(
        f"market timestamp has no mark bar: {stamp.isoformat()}" for stamp in extra[:20]
    )
    return CoverageEvidence(
        first=market_index.min().isoformat() if len(market_index) else None,
        last=market_index.max().isoformat() if len(market_index) else None,
        rows=len(market_index),
        missing_intervals=len(extra),
        failures=tuple(failures),
    )


def check_funding_coverage(
    path: Path,
    *,
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
    interval_hours: float,
    now: pd.Timestamp | None = None,
) -> CoverageEvidence:
    """Check exact Bitget settlements against the contract's declared cadence."""

    if not Path(path).is_file():
        return CoverageEvidence(None, None, 0, 0, (f"missing funding file {path}",))
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return CoverageEvidence(None, None, 0, 0, (f"unreadable funding file: {exc}",))
    required = {"funding_time", "funding_rate"}
    missing = required.difference(frame.columns)
    if missing:
        return CoverageEvidence(
            None,
            None,
            len(frame),
            0,
            (f"missing funding columns {sorted(missing)}",),
        )
    failures: list[str] = []
    raw_times = pd.to_datetime(frame["funding_time"], utc=True, errors="coerce")
    rates = pd.to_numeric(frame["funding_rate"], errors="coerce")
    invalid = raw_times.isna() | rates.isna() | ~rates.map(math.isfinite)
    if invalid.any():
        failures.append(f"{int(invalid.sum())} invalid funding row(s)")
    if not pd.DatetimeIndex(raw_times.dropna()).is_monotonic_increasing:
        failures.append("funding_time is not monotonic")
    times = pd.DatetimeIndex(raw_times.loc[~invalid]).sort_values()
    valid_rates = rates.loc[~invalid]
    if valid_rates.empty or times.empty:
        return CoverageEvidence(
            None,
            None,
            len(frame),
            0,
            tuple(failures + ["empty funding file"]),
        )
    if times.duplicated().any():
        failures.append(
            f"{int(times.duplicated().sum())} duplicate funding timestamp(s)"
        )
    if (valid_rates.abs() > 0.10).any():
        failures.append("funding rate exceeds 10% per settlement")
    if times.min() > _utc_stamp(required_start):
        failures.append(f"funding starts after {required_start}")
    if times.max() < _utc_stamp(required_end):
        failures.append(f"funding ends before {required_end}")
    if now is not None and times.max() > _utc_stamp(now):
        failures.append(f"future funding timestamp {times.max()}")
    if not math.isfinite(float(interval_hours)) or interval_hours <= 0.0:
        failures.append(f"invalid declared funding interval {interval_hours!r}")
        irregular = pd.Series(dtype="timedelta64[ns]")
    else:
        gaps = times.to_series().diff().dropna()
        irregular = gaps[gaps != pd.Timedelta(hours=float(interval_hours))]
        failures.extend(
            f"irregular funding interval {gap}" for gap in irregular.iloc[:20]
        )
    return CoverageEvidence(
        first=times.min().isoformat(),
        last=times.max().isoformat(),
        rows=len(frame),
        missing_intervals=len(irregular),
        failures=tuple(failures),
    )


def rank_current_candidates(
    *,
    config_path: Path,
    panel_path: Path,
    metadata_path: Path,
    as_of: date,
    limit: int,
) -> pd.DataFrame:
    """Rank the current CMC cohort with the production universe builder.

    ``limit`` is the candidate-pool width required by Top50 backfill.  It must
    not exceed the cached current-candidate width in ``base.yaml`` or a new
    Top50 could silently be built from a truncated catalog.
    """

    if limit <= 0:
        raise ValueError("limit must be positive")
    config = load_config(config_path).model_copy(deep=True)
    if limit > config.universe.current_top_n_candidates:
        raise ValueError(
            "requested ranking limit "
            f"{limit} exceeds current_top_n_candidates "
            f"{config.universe.current_top_n_candidates}"
        )
    config.universe.universe_size = int(limit)
    panel = pd.read_csv(panel_path)
    metadata = pd.read_csv(metadata_path).set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    day = pd.Timestamp(as_of).normalize()
    if getattr(market.price.index, "tz", None) is not None:
        day = day.tz_localize("UTC")
    if day not in market.price.index:
        raise ValueError(f"panel has no ranking row for {as_of}")
    ranked = build_rebalance_universe(market, [day], config)
    if ranked.empty:
        raise ValueError(f"no eligible CMC candidates on {as_of}")
    return ranked.sort_values("universe_rank", kind="stable").reset_index(drop=True)


__all__ = [
    "CoverageEvidence",
    "TOP20_SIZE",
    "TOP50_SIZE",
    "VENUE_UNAVAILABLE",
    "SelectionMember",
    "SelectionSkip",
    "Top50Selection",
    "check_funding_coverage",
    "check_mark_coverage",
    "check_market_alignment",
    "check_market_execution_coverage",
    "check_panel_history",
    "rank_current_candidates",
    "select_executable_top50",
]
