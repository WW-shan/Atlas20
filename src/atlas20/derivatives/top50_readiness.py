"""Fail-closed Top50 data-readiness primitives.

The module selects the executable CMC cohort without inventing a second data
format.  Ranking happens elsewhere through the production universe builder;
this layer only consumes that ranking, the current Bitget symbol map and the
existing raw evidence trees.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from typing import Any

import pandas as pd

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


__all__ = [
    "TOP20_SIZE",
    "TOP50_SIZE",
    "VENUE_UNAVAILABLE",
    "SelectionMember",
    "SelectionSkip",
    "Top50Selection",
    "select_executable_top50",
]
