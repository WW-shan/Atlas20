from __future__ import annotations

from datetime import date
from pathlib import Path

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


def test_rank_current_candidates_uses_production_point_in_time_builder(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import rank_current_candidates

    dates = pd.date_range("2026-07-01", "2026-11-15", freq="D", tz="UTC")
    rows = []
    metadata_rows = []
    for index in range(1, 62):
        coin_id = f"coin-{index:02d}"
        symbol = f"C{index:02d}"
        metadata_rows.append(
            {
                "coin_id": coin_id,
                "symbol": symbol,
                "name": f"Coin {index:02d}",
                "sector": "Other",
                "category_list": "[]",
            }
        )
        for day in dates:
            rows.append(
                {
                    "date": day,
                    "coin_id": coin_id,
                    "symbol": symbol,
                    "price": 1.0,
                    "volume_usd": 50_000_000.0,
                    "market_cap": float(10_000 - index * 10),
                }
            )
    panel_path = tmp_path / "panel_daily.csv"
    metadata_path = tmp_path / "metadata.csv"
    pd.DataFrame(rows).to_csv(panel_path, index=False)
    pd.DataFrame(metadata_rows).to_csv(metadata_path, index=False)

    ranked = rank_current_candidates(
        config_path=Path(__file__).resolve().parents[1] / "config" / "base.yaml",
        panel_path=panel_path,
        metadata_path=metadata_path,
        as_of=date(2026, 11, 15),
        limit=60,
    )

    assert len(ranked) == 60
    assert ranked["universe_rank"].tolist() == list(range(1, 61))
    assert ranked["coin_id"].tolist()[:3] == ["coin-01", "coin-02", "coin-03"]
    assert "coin-61" not in set(ranked["coin_id"])


def _ohlc(times: list[str]) -> pd.DataFrame:
    index = pd.to_datetime(times, utc=True)
    return pd.DataFrame(
        {
            "open_time": index,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
        }
    )


def test_panel_coverage_rejects_missing_completed_day() -> None:
    from atlas20.derivatives.top50_readiness import check_panel_history

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-03"], utc=True),
            "coin_id": ["bitcoin", "bitcoin"],
            "price": [1.0, 1.0],
            "volume_usd": [10.0, 10.0],
            "market_cap": [100.0, 100.0],
        }
    )

    result = check_panel_history(panel, coin_id="bitcoin", latest_day=date(2026, 1, 3))

    assert result.missing_intervals == 1
    assert any("missing CMC day 2026-01-02" in item for item in result.failures)


def test_mark_coverage_rejects_interior_gap(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_mark_coverage

    path = tmp_path / "BTC_mark.csv"
    _ohlc(
        [
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T03:00:00Z",
        ]
    ).to_csv(path, index=False)

    result = check_mark_coverage(
        path,
        start=pd.Timestamp("2026-01-01T00:00:00Z"),
        required_end=pd.Timestamp("2026-01-01T04:00:00Z"),
    )

    assert result.missing_intervals == 1
    assert any("missing hour 2026-01-01T02:00:00+00:00" in item for item in result.failures)


def test_market_coverage_requires_one_usable_floor_bar_per_execution_day(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_market_execution_coverage

    path = tmp_path / "BTC_market.csv"
    _ohlc(["2026-01-01T01:00:00Z", "2026-01-03T01:00:00Z"]).to_csv(path, index=False)

    result = check_market_execution_coverage(
        path,
        required_first_day=date(2026, 1, 1),
        end_day=date(2026, 1, 3),
    )

    assert result.missing_intervals == 1
    assert any("2026-01-02" in item for item in result.failures)


def test_market_alignment_rejects_an_inside_timestamp_without_mark(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_market_alignment

    mark = tmp_path / "BTC_mark.csv"
    market = tmp_path / "BTC_market.csv"
    _ohlc(
        ["2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z", "2026-01-01T03:00:00Z"]
    ).to_csv(mark, index=False)
    _ohlc(
        ["2026-01-01T01:00:00Z", "2026-01-01T02:30:00Z", "2026-01-01T03:00:00Z"]
    ).to_csv(market, index=False)

    result = check_market_alignment(market, (mark,))

    assert result.missing_intervals == 1
    assert any("2026-01-01T02:30:00+00:00" in item for item in result.failures)


def test_funding_coverage_uses_the_declared_contract_interval(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_funding_coverage

    path = tmp_path / "BTC_funding.csv"
    pd.DataFrame(
        {
            "funding_time": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T04:00:00Z",
                "2026-01-01T12:00:00Z",
            ],
            "funding_rate": [0.0001, 0.0001, 0.0001],
        }
    ).to_csv(path, index=False)

    result = check_funding_coverage(
        path,
        required_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        required_end=pd.Timestamp("2026-01-01T12:00:00Z"),
        interval_hours=4.0,
    )

    assert result.missing_intervals == 1
    assert any("irregular funding interval" in item for item in result.failures)
