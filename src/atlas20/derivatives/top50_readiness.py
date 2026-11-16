"""Fail-closed Top50 data-readiness primitives.

The module selects the executable CMC cohort without inventing a second data
format.  Ranking happens elsewhere through the production universe builder;
this layer only consumes that ranking, the current Bitget symbol map and the
existing raw evidence trees.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
import hashlib
import json
import math
from typing import Any

import pandas as pd

from atlas20.config import load_config
from atlas20.derivatives.data_audit import (
    DataAuditReport,
    audit_derivatives_data,
    required_last_mark_time,
)
from atlas20.logging_utils import atomic_write_text
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


def write_scoped_audit_inputs(
    *,
    output_dir: Path,
    selection: Top50Selection,
    panel_path: Path,
    symbol_map_path: Path,
) -> tuple[Path, Path]:
    """Write the exact panel and map slices consumed by the existing audit."""

    wanted = {member.coin_id for member in selection.members}
    panel = pd.read_csv(panel_path)
    mapping = pd.read_csv(symbol_map_path)
    for label, frame in (("panel", panel), ("symbol map", mapping)):
        if "coin_id" not in frame.columns:
            raise ValueError(f"{label} has no coin_id column")
        observed = set(frame["coin_id"].astype(str))
        missing = wanted.difference(observed)
        if missing:
            raise ValueError(
                f"scoped {label} does not cover selected member(s): "
                + ", ".join(sorted(missing))
            )
    scoped_panel = panel.loc[panel["coin_id"].astype(str).isin(wanted)].copy()
    scoped_map = mapping.loc[mapping["coin_id"].astype(str).isin(wanted)].copy()
    if scoped_map["coin_id"].astype(str).duplicated().any():
        raise ValueError("scoped symbol map contains a duplicate coin_id")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    panel_out = output_dir / "panel_top50.csv"
    map_out = output_dir / "symbol_map_top50.csv"
    scoped_panel.to_csv(panel_out, index=False)
    scoped_map.to_csv(map_out, index=False)
    return panel_out, map_out


def audit_selected_top50(
    *,
    raw_dir: Path,
    scoped_panel: Path,
    scoped_symbol_map: Path,
    selection: Top50Selection,
    now: pd.Timestamp,
) -> DataAuditReport:
    """Run the existing derivatives audit over only the selected members."""

    assets = {member.coin_id for member in selection.members}
    return audit_derivatives_data(
        raw_dir,
        scoped_panel,
        scoped_symbol_map,
        now=_utc_stamp(now).to_pydatetime(),
        expected_panel_day=selection.as_of,
        min_panel_assets=len(selection.members),
        required_leverage_assets=assets,
        required_funding_assets=assets,
        required_leverage=4.0,
        require_all_funding_fresh=True,
    )


def audit_failures_by_member(
    report: DataAuditReport,
    selection: Top50Selection,
) -> dict[str, list[str]]:
    """Attribute audit failures to selected members or to the global inputs."""

    failures: dict[str, list[str]] = {
        member.coin_id: [] for member in selection.members
    }
    failures["global"] = []
    selected = set(failures).difference({"global"})
    for check in report.checks:
        if bool(check.get("passed")):
            continue
        name = str(check.get("name") or "")
        detail = str(check.get("detail") or "")
        rendered = f"{name}: {detail}"
        parts = name.split(".", 2)
        asset = parts[1] if len(parts) == 3 and parts[0] in {
            "contracts",
            "funding",
            "marks",
        } else ""
        if asset in selected:
            failures[asset].append(rendered)
        else:
            failures["global"].append(rendered)
    if not report.passed and not report.checks:
        failures["global"].append("audit failed without detailed checks")
    return failures


def _coverage_payload(coverage: CoverageEvidence) -> dict[str, object]:
    return {
        "first": coverage.first,
        "last": coverage.last,
        "rows": coverage.rows,
        "missing_intervals": coverage.missing_intervals,
        "failures": list(coverage.failures),
    }


def _contract_open_day(map_row: pd.Series | dict[str, object]) -> date | None:
    raw = map_row.get("open_time")
    try:
        stamp = pd.Timestamp(raw)
    except (TypeError, ValueError):
        return None
    if pd.isna(stamp):
        return None
    return _utc_stamp(stamp).date()


def collect_member_evidence(
    *,
    member: SelectionMember,
    map_row: pd.Series | dict[str, object],
    panel: pd.DataFrame,
    warmup_mark_path: Path,
    warmup_market_path: Path,
    live_mark_path: Path,
    live_market_path: Path,
    funding_path: Path,
    warmup_start: pd.Timestamp,
    warmup_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    latest_signal_day: date,
    now: pd.Timestamp,
) -> dict[str, object]:
    """Collect JSON-safe evidence for one mapped Top50 member."""

    failures: list[str] = []
    open_day = _contract_open_day(map_row)
    if open_day is None:
        failures.append("contract open_time is missing or invalid")
        open_day = min(_utc_stamp(warmup_start).date(), latest_signal_day)
    warmup_expected_day = max(_utc_stamp(warmup_start).date(), open_day)
    live_expected_day = max(_utc_stamp(oos_start).date(), open_day)
    required_last = required_last_mark_time(_utc_stamp(now).to_pydatetime())
    live_end = required_last + pd.Timedelta(hours=1)

    cmc = check_panel_history(
        panel,
        coin_id=member.coin_id,
        latest_day=latest_signal_day,
    )
    warmup_mark = check_mark_coverage(
        warmup_mark_path,
        start=pd.Timestamp(warmup_expected_day, tz="UTC"),
        required_end=_utc_stamp(warmup_end),
        now=_utc_stamp(now),
    )
    live_mark = check_mark_coverage(
        live_mark_path,
        start=pd.Timestamp(live_expected_day, tz="UTC"),
        required_end=live_end,
        now=_utc_stamp(now),
    )
    warmup_market = check_market_execution_coverage(
        warmup_market_path,
        required_first_day=warmup_expected_day,
        end_day=_utc_stamp(warmup_end).date(),
        now=_utc_stamp(now),
    )
    live_market = check_market_execution_coverage(
        live_market_path,
        required_first_day=live_expected_day,
        end_day=latest_signal_day + pd.Timedelta(days=1),
        now=_utc_stamp(now),
    )
    warmup_alignment = check_market_alignment(warmup_market_path, (warmup_mark_path,))
    live_alignment = check_market_alignment(
        live_market_path, (warmup_mark_path, live_mark_path)
    )
    try:
        interval_hours = float(map_row.get("fund_interval"))
    except (TypeError, ValueError):
        interval_hours = float("nan")
    funding = check_funding_coverage(
        funding_path,
        required_start=pd.Timestamp(live_expected_day, tz="UTC"),
        required_end=required_last,
        interval_hours=interval_hours,
        now=_utc_stamp(now),
    )

    evidence = {
        "cmc": cmc,
        "warmup_mark": warmup_mark,
        "warmup_market": warmup_market,
        "live_mark": live_mark,
        "live_market": live_market,
        "funding": funding,
    }
    for label, coverage in evidence.items():
        failures.extend(f"{label}: {item}" for item in coverage.failures)
    failures.extend(f"warmup_market_alignment: {item}" for item in warmup_alignment.failures)
    failures.extend(f"live_market_alignment: {item}" for item in live_alignment.failures)

    return {
        "final_rank": member.final_rank,
        "original_rank": member.original_rank,
        "coin_id": member.coin_id,
        "symbol": member.symbol,
        "bitget_symbol": member.bitget_symbol,
        "panel_symbol": member.panel_symbol,
        "contract_open_time": None if open_day is None else open_day.isoformat(),
        "cmc": _coverage_payload(cmc),
        "warmup_mark": _coverage_payload(warmup_mark),
        "warmup_market": _coverage_payload(warmup_market),
        "live_mark": _coverage_payload(live_mark),
        "live_market": _coverage_payload(live_market),
        "funding": _coverage_payload(funding),
        "warmup_market_alignment": _coverage_payload(warmup_alignment),
        "live_market_alignment": _coverage_payload(live_alignment),
        "audit_failures": [],
        "status": "READY" if not failures else "BLOCKED",
        "failure_details": failures,
    }


def _payload_fingerprint(payload: dict[str, object]) -> str:
    canonical_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"fingerprint", "generated_at"}
    }
    canonical = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assess_selection(
    *,
    selection: Top50Selection,
    panel_path: Path,
    symbol_map_path: Path,
    raw_dir: Path,
    warmup_mark_dir: Path,
    warmup_market_dir: Path,
    reports_dir: Path,
    warmup_start: pd.Timestamp,
    warmup_end: pd.Timestamp,
    oos_start: pd.Timestamp,
    latest_signal_day: date,
    now: pd.Timestamp,
) -> tuple[dict[str, object], set[str]]:
    """Collect member evidence, apply the existing audit and build Top20."""

    panel = pd.read_csv(panel_path)
    mapping = pd.read_csv(symbol_map_path)
    wanted = {member.coin_id for member in selection.members}
    mapping = mapping.loc[mapping["coin_id"].astype(str).isin(wanted)].copy()
    if set(mapping["coin_id"].astype(str)) != wanted:
        raise ValueError("symbol map does not cover every selected member")
    mapping = mapping.set_index("coin_id", drop=False)
    scoped_panel, scoped_map = write_scoped_audit_inputs(
        output_dir=Path(reports_dir) / "audit_inputs",
        selection=selection,
        panel_path=panel_path,
        symbol_map_path=symbol_map_path,
    )
    audit_report = audit_selected_top50(
        raw_dir=raw_dir,
        scoped_panel=scoped_panel,
        scoped_symbol_map=scoped_map,
        selection=selection,
        now=now,
    )
    audit_failures = audit_failures_by_member(audit_report, selection)
    members: list[dict[str, object]] = []
    for member in selection.members:
        map_row = mapping.loc[member.coin_id]
        symbol = member.bitget_symbol
        evidence = collect_member_evidence(
            member=member,
            map_row=map_row,
            panel=panel,
            warmup_mark_path=Path(warmup_mark_dir) / "candles" / f"{symbol}_mark.csv",
            warmup_market_path=Path(warmup_market_dir)
            / "candles"
            / f"{symbol}_market.csv",
            live_mark_path=Path(raw_dir) / "candles" / f"{symbol}_mark.csv",
            live_market_path=Path(raw_dir) / "candles" / f"{symbol}_market.csv",
            funding_path=Path(raw_dir) / "funding" / f"{member.coin_id}.csv",
            warmup_start=warmup_start,
            warmup_end=warmup_end,
            oos_start=oos_start,
            latest_signal_day=latest_signal_day,
            now=now,
        )
        member_audit_failures = list(audit_failures.get(member.coin_id, []))
        global_audit_failures = list(audit_failures.get("global", []))
        audit_detail = member_audit_failures + global_audit_failures
        evidence["audit_failures"] = audit_detail
        if audit_detail:
            details = list(evidence["failure_details"])
            details.extend(f"audit: {item}" for item in audit_detail)
            evidence["failure_details"] = details
            evidence["status"] = "BLOCKED"
        members.append(evidence)

    top20 = [dict(item) for item in members[:TOP20_SIZE]]
    ready = (
        len(members) == TOP50_SIZE
        and len(top20) == TOP20_SIZE
        and all(item["status"] == "READY" for item in members)
    )
    audit_payload = audit_report.as_dict()
    audit_summary = {
        "passed": audit_report.passed,
        "hard_failures": list(audit_report.hard_failures),
        "warnings": list(audit_report.warnings),
        "provenance": dict(audit_report.provenance),
        "summary": dict(audit_report.summary),
    }
    payload: dict[str, object] = {
        "as_of": selection.as_of.isoformat(),
        "generated_at": _utc_stamp(now).isoformat(),
        "ready": ready,
        "candidate_count": selection.candidate_count,
        "source_fingerprint": selection.source_fingerprint,
        "latest_signal_day": latest_signal_day.isoformat(),
        "warmup_start": _utc_stamp(warmup_start).isoformat(),
        "warmup_end": _utc_stamp(warmup_end).isoformat(),
        "oos_start": _utc_stamp(oos_start).isoformat(),
        "members": members,
        "top20": top20,
        "skipped": [
            {
                "original_rank": item.original_rank,
                "coin_id": item.coin_id,
                "symbol": item.symbol,
                "reason": item.reason,
            }
            for item in selection.skipped
        ],
        "audit": audit_summary,
        "audit_detail": audit_payload,
    }
    blocked = {
        str(item["coin_id"])
        for item in members
        if item["status"] != "READY"
    }
    return payload, blocked


def publish_readiness_payload(
    *,
    reports_dir: Path,
    payload: dict[str, object],
    audit_payload: dict[str, object],
) -> dict[str, Path]:
    """Atomically publish current evidence and only current-day ready pointers."""

    body = dict(payload)
    members = body.get("members")
    top20 = body.get("top20")
    if not isinstance(members, list) or not isinstance(top20, list):
        raise ValueError("readiness payload must contain members and top20 lists")
    if bool(body.get("ready")):
        if len(members) != TOP50_SIZE:
            raise ValueError("ready payload must contain exactly 50 members")
        if len(top20) != TOP20_SIZE:
            raise ValueError("ready payload must contain exactly 20 top20 members")
        if any(item.get("status") != "READY" for item in members):
            raise ValueError("ready payload contains a non-READY member")
    body["fingerprint"] = _payload_fingerprint(body)
    text = json.dumps(body, indent=2, sort_keys=True, default=str) + "\n"
    reports_dir = Path(reports_dir)
    history = reports_dir / "history" / f"{body['as_of']}.json"
    latest = reports_dir / "latest.json"
    top50_path = reports_dir / "top50.csv"
    top20_path = reports_dir / "top20.csv"
    audit_path = reports_dir / "audit" / f"{body['as_of']}.json"
    atomic_write_text(history, text)
    atomic_write_text(latest, text)
    atomic_write_text(
        audit_path,
        json.dumps(audit_payload, indent=2, sort_keys=True, default=str) + "\n",
    )
    pd.DataFrame(members).to_csv(top50_path, index=False)
    pd.DataFrame(top20).to_csv(top20_path, index=False)
    paths = {
        "history": history,
        "latest": latest,
        "top50": top50_path,
        "top20": top20_path,
        "audit": audit_path,
        "latest_ready": reports_dir / "latest_ready.json",
    }
    if bool(body["ready"]):
        ready_history = reports_dir / "ready" / f"{body['as_of']}.json"
        atomic_write_text(ready_history, text)
        atomic_write_text(paths["latest_ready"], text)
        paths["ready_history"] = ready_history
    else:
        paths["latest_ready"].unlink(missing_ok=True)
    return paths


EVENTS = (
    "TOP50_ENTER",
    "TOP50_DATA_READY",
    "TOP50_DATA_BLOCKED",
    "TOP20_ENTER",
)


def _default_state() -> dict[str, object]:
    return {
        "version": 1,
        "initialized": False,
        "last_as_of": None,
        "members": [],
        "top20": [],
        "member_status": {},
        "notifications": {"sent_keys": {}, "pending": {}},
    }


def load_state(path: Path) -> dict[str, object]:
    """Load the readiness state, returning a deterministic empty baseline."""

    path = Path(path)
    if not path.is_file():
        return _default_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"top50 state is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("top50 state must be a JSON object")
    state = _default_state()
    state.update(payload)
    notifications = state.get("notifications")
    if not isinstance(notifications, dict):
        notifications = {}
    sent_keys = notifications.get("sent_keys")
    pending = notifications.get("pending")
    state["notifications"] = {
        "sent_keys": sent_keys if isinstance(sent_keys, dict) else {},
        "pending": pending if isinstance(pending, dict) else {},
    }
    return state


def write_state(path: Path, state: dict[str, object]) -> None:
    atomic_write_text(
        Path(path),
        json.dumps(state, indent=2, sort_keys=True, default=str) + "\n",
    )


def notification_key(event: str, coin_id: str, as_of: str) -> str:
    if event not in EVENTS:
        raise ValueError(f"unsupported event {event}")
    return f"{event}|{coin_id}|{as_of}"


def format_event_message(event: dict[str, str]) -> str:
    lines = [
        f"Atlas20 Top50 {event['event']}",
        f"日期: {event['as_of']}",
        f"币种: {event['symbol']} ({event['coin_id']})",
        f"状态: {event['status']}",
    ]
    if event["event"] == "TOP50_ENTER":
        lines.append("开始构建/审核完整数据。")
    elif event["event"] == "TOP50_DATA_READY":
        lines.append("数据完整，进入 Top20 时可直接构建信号。")
    elif event["event"] == "TOP50_DATA_BLOCKED":
        lines.append("数据审核失败，该币不能进入新风险。")
    elif event["event"] == "TOP20_ENTER":
        lines.append("已进入 Top20；READY 时无需临时下载历史数据。")
    if event["event"] in {"TOP50_DATA_BLOCKED", "TOP20_ENTER"} and event["status"] != "READY":
        lines.append("未进入信号；禁止用第 51 名掩盖数据故障。")
    if event.get("details"):
        lines.extend(["", "缺口:", event["details"]])
    return "\n".join(lines)


def _event(
    event_type: str,
    *,
    coin_id: str,
    symbol: str,
    as_of: str,
    status: str,
    failure_details: object,
) -> dict[str, str]:
    details: list[str] = []
    if isinstance(failure_details, list):
        details = [str(item) for item in failure_details]
    rendered = "\n".join(details[:5])
    if len(details) > 5:
        rendered += f"\n... {len(details) - 5} more"
    return {
        "event": event_type,
        "coin_id": coin_id,
        "symbol": symbol,
        "as_of": as_of,
        "status": status,
        "details": rendered,
        "key": notification_key(event_type, coin_id, as_of),
    }


def build_notification_events(
    previous: dict[str, object],
    payload: dict[str, object],
    *,
    initialized: bool,
) -> tuple[dict[str, str], ...]:
    """Build membership and status-change events without a first-run flood."""

    if not initialized:
        return ()
    as_of = str(payload.get("as_of") or "")
    if not as_of:
        raise ValueError("readiness payload has no as_of")
    previous_members = {str(item) for item in previous.get("members", [])}
    previous_top20 = {str(item) for item in previous.get("top20", [])}
    raw_status = previous.get("member_status")
    previous_status = raw_status if isinstance(raw_status, dict) else {}
    members = payload.get("members")
    top20 = payload.get("top20")
    if not isinstance(members, list) or not isinstance(top20, list):
        raise ValueError("readiness payload must contain member lists")

    events: list[dict[str, str]] = []
    for item in members:
        if not isinstance(item, dict):
            continue
        coin_id = str(item.get("coin_id") or "")
        if not coin_id:
            continue
        status = str(item.get("status") or "BLOCKED")
        symbol = str(item.get("symbol") or "")
        is_new = coin_id not in previous_members
        if is_new:
            events.append(
                _event(
                    "TOP50_ENTER",
                    coin_id=coin_id,
                    symbol=symbol,
                    as_of=as_of,
                    status=status,
                    failure_details=item.get("failure_details"),
                )
            )
        if is_new or str(previous_status.get(coin_id) or "") != status:
            event_type = (
                "TOP50_DATA_READY" if status == "READY" else "TOP50_DATA_BLOCKED"
            )
            events.append(
                _event(
                    event_type,
                    coin_id=coin_id,
                    symbol=symbol,
                    as_of=as_of,
                    status=status,
                    failure_details=item.get("failure_details"),
                )
            )
    for item in top20:
        if not isinstance(item, dict):
            continue
        coin_id = str(item.get("coin_id") or "")
        if coin_id and coin_id not in previous_top20:
            events.append(
                _event(
                    "TOP20_ENTER",
                    coin_id=coin_id,
                    symbol=str(item.get("symbol") or ""),
                    as_of=as_of,
                    status=str(item.get("status") or "BLOCKED"),
                    failure_details=item.get("failure_details"),
                )
            )
    return tuple(events)


def queue_notification_events(
    state: dict[str, object],
    events: Iterable[dict[str, str]],
) -> None:
    notifications = state.setdefault(
        "notifications", {"sent_keys": {}, "pending": {}}
    )
    if not isinstance(notifications, dict):
        raise ValueError("state notifications must be an object")
    sent_keys = notifications.setdefault("sent_keys", {})
    pending = notifications.setdefault("pending", {})
    if not isinstance(sent_keys, dict) or not isinstance(pending, dict):
        raise ValueError("state notification ledgers must be objects")
    for event in events:
        key = str(event["key"])
        if key not in sent_keys:
            pending.setdefault(key, dict(event))


def record_notification_result(
    state: dict[str, object],
    event: dict[str, str],
    *,
    sent: bool,
    error: str | None,
    sent_at: str | None,
) -> None:
    notifications = state.setdefault(
        "notifications", {"sent_keys": {}, "pending": {}}
    )
    if not isinstance(notifications, dict):
        raise ValueError("state notifications must be an object")
    sent_keys = notifications.setdefault("sent_keys", {})
    pending = notifications.setdefault("pending", {})
    if not isinstance(sent_keys, dict) or not isinstance(pending, dict):
        raise ValueError("state notification ledgers must be objects")
    key = str(event["key"])
    if sent:
        pending.pop(key, None)
        sent_keys[key] = {"sent_at": sent_at}
    else:
        pending[key] = {
            **event,
            "last_error": error,
            "attempted_at": sent_at,
        }


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
    "EVENTS",
    "TOP20_SIZE",
    "TOP50_SIZE",
    "VENUE_UNAVAILABLE",
    "SelectionMember",
    "SelectionSkip",
    "Top50Selection",
    "assess_selection",
    "audit_failures_by_member",
    "audit_selected_top50",
    "build_notification_events",
    "check_funding_coverage",
    "check_mark_coverage",
    "check_market_alignment",
    "check_market_execution_coverage",
    "check_panel_history",
    "collect_member_evidence",
    "format_event_message",
    "load_state",
    "notification_key",
    "publish_readiness_payload",
    "queue_notification_events",
    "rank_current_candidates",
    "record_notification_result",
    "select_executable_top50",
    "write_scoped_audit_inputs",
    "write_state",
]
