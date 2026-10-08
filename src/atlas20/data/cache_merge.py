"""Merge overlapping provider cache windows so the newest fetch wins.

Every provider client caches one JSON file per requested window, and the daily
refresh re-requests overlapping windows: a CoinMarketCap tail refresh returns
~400 rows whatever its start, and the venue clients cache a fresh 400-day
window every day. Almost every date therefore sits in several files (43,939
overlapping CMC rows on 2026-09-24), and which copy survives the merge decides
the value the panel and the cross-check see.

The loaders used to concatenate the files in filename order and then call
``sort_values("date")``. pandas' default quicksort is not stable, so
``drop_duplicates(keep="last")`` kept whichever copy the sort left last - on a
synthetic revised tail the new value survived on 209 of 398 dates and the stale
one on the other 189. Filename order was not fetch order either: a forced full
re-download is the newest fetch, but its name (the earliest start epoch) sorts
before every tail window.

The merge below tags each file with its fetch position and sorts on
``(date, fetch position)``, so the newest fetch wins by construction. Duplicates
whose values differ are counted and described rather than silently resolved,
because a disagreement between two fetches of the same day is exactly what a
provider revision - or a provisional print cached before the day was final -
looks like.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_FETCH_ORDER = "_fetch_order"
_MAX_EXAMPLES = 3


def fetch_ordered(paths: Iterable[Path]) -> list[Path]:
    """Return cache files oldest fetch first.

    A cache file is written exactly when its window is fetched (a forced
    refresh rewrites it in place), so its modification time *is* the fetch
    time; the name only breaks ties on coarse-grained filesystems. Copying the
    cache without preserving timestamps (``cp -r`` rather than ``cp -p`` or
    ``rsync -a``) scrambles this order - the conflict report then names every
    date whose value depends on it.
    """
    return sorted(paths, key=lambda path: (path.stat().st_mtime_ns, path.name))


@dataclass(frozen=True)
class FetchOrderMerge:
    """A merged cache plus the evidence about its duplicated dates."""

    frame: pd.DataFrame
    duplicate_dates: int
    conflicting_dates: int
    examples: tuple[str, ...]


def _same(left: pd.Series, right: pd.Series) -> pd.Series:
    """Element-wise equality that treats two missing values as equal."""
    return (left == right) | (left.isna() & right.isna())


def merge_by_fetch_order(
    frames: Sequence[pd.DataFrame],
    *,
    value_columns: Sequence[str],
    date_column: str = "date",
    columns: Sequence[str] | None = None,
) -> FetchOrderMerge:
    """Merge per-fetch frames given oldest fetch first; the newest fetch wins.

    ``frames`` must already be cleaned row by row: an invalid row (no price, a
    non-positive close) is not a fetch's answer for that date, so an older
    valid copy is allowed to stand in for it. Rows within one frame keep their
    order, so a duplicate inside a single payload resolves deterministically
    to its later row.
    """
    output_columns = list(columns) if columns is not None else None
    usable = [frame for frame in frames if not frame.empty]
    if not usable:
        empty = pd.DataFrame(columns=output_columns if output_columns is not None else [date_column, *value_columns])
        return FetchOrderMerge(empty, 0, 0, ())

    stacked = pd.concat(
        [frame.assign(**{_FETCH_ORDER: position}) for position, frame in enumerate(usable)],
        ignore_index=True,
    )
    stacked = stacked.sort_values([date_column, _FETCH_ORDER], kind="mergesort").reset_index(drop=True)

    duplicated = stacked[stacked.duplicated(date_column, keep=False)]
    duplicate_dates = int(duplicated[date_column].nunique())
    conflicting_dates = 0
    examples: list[str] = []
    if duplicate_dates:
        numeric = duplicated[[date_column]].copy()
        for column in value_columns:
            numeric[column] = pd.to_numeric(duplicated[column], errors="coerce").astype(float)
        # Align every copy with the newest copy of its date. ``groupby.last``
        # would skip a missing value and compare against an older copy instead.
        newest = (
            numeric.drop_duplicates(date_column, keep="last")
            .set_index(date_column)
            .reindex(numeric[date_column])
            .set_axis(numeric.index)
        )
        differs = pd.Series(False, index=numeric.index)
        for column in value_columns:
            differs |= ~_same(numeric[column], newest[column])
        conflicted = numeric.loc[differs, date_column]
        conflicting_dates = int(conflicted.nunique())
        for day in conflicted.drop_duplicates().head(_MAX_EXAMPLES):
            copies = numeric[numeric[date_column] == day]
            changed = [
                f"{column} {copies[column].iloc[0]:.6g}->{copies[column].iloc[-1]:.6g}"
                for column in value_columns
                if copies[column].nunique(dropna=False) > 1
            ]
            label = pd.Timestamp(day).date().isoformat()
            examples.append(f"{label}: " + ", ".join(changed) + f" ({len(copies)} copies, oldest->newest)")

    merged = stacked.drop_duplicates(date_column, keep="last").drop(columns=[_FETCH_ORDER])
    if output_columns is not None:
        merged = merged[output_columns]
    return FetchOrderMerge(merged.reset_index(drop=True), duplicate_dates, conflicting_dates, tuple(examples))


def describe_conflicts(result: FetchOrderMerge) -> str:
    """One log-ready line describing the conflicting duplicates of a merge."""
    return (
        f"{result.conflicting_dates} of {result.duplicate_dates} duplicated date(s) conflict "
        f"between cached fetches; the newest fetch was kept"
        + (f" (e.g. {'; '.join(result.examples)})" if result.examples else "")
    )


__all__ = ["FetchOrderMerge", "describe_conflicts", "fetch_ordered", "merge_by_fetch_order"]
