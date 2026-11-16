from __future__ import annotations

from datetime import date

import pandas as pd
import pytest


def _ranked(count: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "coin_id": [f"coin-{index}" for index in range(1, count + 1)],
            "symbol": [f"C{index}" for index in range(1, count + 1)],
            "universe_rank": range(1, count + 1),
        }
    )


def _mapped(ranked: pd.DataFrame, missing_ranks: set[int]) -> pd.DataFrame:
    rows = []
    for row in ranked.to_dict("records"):
        rank = int(row["universe_rank"])
        missing = rank in missing_ranks
        rows.append(
            {
                "coin_id": row["coin_id"],
                "panel_symbol": row["symbol"],
                "bitget_symbol": "" if missing else f"{row['symbol']}USDT",
                "contract_status": "missing" if missing else "normal",
            }
        )
    return pd.DataFrame(rows)


def test_selection_skips_missing_contracts_and_backfills_to_fifty() -> None:
    from atlas20.derivatives.top50_readiness import select_executable_top50

    ranked = _ranked(52)
    result = select_executable_top50(
        ranked,
        _mapped(ranked, {2, 7}),
        as_of=date(2026, 11, 15),
    )

    assert len(result.members) == 50
    assert [row.final_rank for row in result.members] == list(range(1, 51))
    assert [row.original_rank for row in result.members][-2:] == [51, 52]
    assert [(row.original_rank, row.reason) for row in result.skipped] == [
        (2, "VENUE_UNAVAILABLE"),
        (7, "VENUE_UNAVAILABLE"),
    ]


def test_selection_fails_closed_when_ranked_pool_cannot_fill_fifty() -> None:
    from atlas20.derivatives.top50_readiness import select_executable_top50

    ranked = _ranked(51)
    with pytest.raises(ValueError, match="only 49 executable"):
        select_executable_top50(
            ranked,
            _mapped(ranked, {2, 7}),
            as_of=date(2026, 11, 15),
        )


def test_selection_rejects_two_coin_ids_on_the_same_contract() -> None:
    from atlas20.derivatives.top50_readiness import select_executable_top50

    ranked = _ranked(50)
    mapping = _mapped(ranked, set())
    mapping.loc[1, "bitget_symbol"] = mapping.loc[0, "bitget_symbol"]
    with pytest.raises(ValueError, match="duplicate Bitget contract"):
        select_executable_top50(ranked, mapping, as_of=date(2026, 11, 15))


def test_selection_rejects_duplicate_coin_or_rank() -> None:
    from atlas20.derivatives.top50_readiness import select_executable_top50

    ranked = _ranked(50)
    ranked.loc[1, "coin_id"] = ranked.loc[0, "coin_id"]
    with pytest.raises(ValueError, match="duplicate coin_id"):
        select_executable_top50(ranked, _mapped(ranked, set()), as_of=date(2026, 11, 15))
