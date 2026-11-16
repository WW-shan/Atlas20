from __future__ import annotations

from datetime import date
import json
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


def test_selection_skips_a_duplicate_contract_and_backfills() -> None:
    from atlas20.derivatives.top50_readiness import select_executable_top50

    ranked = _ranked(51)
    mapping = _mapped(ranked, set())
    mapping.loc[1, "bitget_symbol"] = mapping.loc[0, "bitget_symbol"]
    result = select_executable_top50(ranked, mapping, as_of=date(2026, 11, 15))

    assert len(result.members) == 50
    assert result.members[-1].original_rank == 51
    assert [(row.original_rank, row.reason) for row in result.skipped] == [
        (2, "DUPLICATE_CONTRACT")
    ]


def test_selection_rejects_duplicate_coin_or_rank() -> None:
    from atlas20.derivatives.top50_readiness import select_executable_top50

    ranked = _ranked(50)
    ranked.loc[1, "coin_id"] = ranked.loc[0, "coin_id"]
    with pytest.raises(ValueError, match="duplicate coin_id"):
        select_executable_top50(ranked, _mapped(ranked, set()), as_of=date(2026, 11, 15))


def test_selection_rejects_fractional_universe_rank() -> None:
    from atlas20.derivatives.top50_readiness import select_executable_top50

    ranked = _ranked(50)
    ranked["universe_rank"] = ranked["universe_rank"].astype(float)
    ranked.loc[0, "universe_rank"] = 1.5

    with pytest.raises(ValueError, match="invalid universe_rank"):
        select_executable_top50(
            ranked,
            _mapped(_ranked(50), set()),
            as_of=date(2026, 11, 15),
        )


def test_selection_requires_sequential_source_ranks() -> None:
    from atlas20.derivatives.top50_readiness import select_executable_top50

    ranked = _ranked(50)
    ranked["universe_rank"] = range(2, 52)

    with pytest.raises(ValueError, match="sequential universe_rank"):
        select_executable_top50(
            ranked,
            _mapped(ranked, set()),
            as_of=date(2026, 11, 15),
        )


def _write_ready_payload(
    tmp_path: Path,
    *,
    as_of: str = "2026-11-15",
) -> tuple[Path, Path, Path, Path]:
    from atlas20.derivatives import top50_readiness as readiness

    panel = tmp_path / "panel_daily.csv"
    metadata = tmp_path / "metadata.csv"
    symbol_map = tmp_path / "symbol_map.csv"
    panel.write_text("date,coin_id\n2026-11-15,coin-1\n", encoding="utf-8")
    metadata.write_text("coin_id\ncoin-1\n", encoding="utf-8")
    symbol_map.write_text("coin_id,bitget_symbol\ncoin-1,C1USDT\n", encoding="utf-8")

    members = [
        {
            "final_rank": index,
            "original_rank": index,
            "coin_id": f"coin-{index}",
            "symbol": f"C{index}",
            "bitget_symbol": f"C{index}USDT",
            "panel_symbol": f"C{index}",
            "status": "READY",
            "failure_details": [],
        }
        for index in range(1, 51)
    ]
    payload = {
        "as_of": as_of,
        "ready": True,
        "members": members,
        "top20": [dict(item) for item in members[:20]],
        "skipped": [],
        "audit": {"passed": True, "hard_failures": [], "warnings": []},
        "source_fingerprint": "sha256:" + "d" * 64,
    }
    payload["input_files"] = {
        "panel": readiness._file_sha256(panel),
        "metadata": readiness._file_sha256(metadata),
        "symbol_map": readiness._file_sha256(symbol_map),
    }
    payload["fingerprint"] = readiness._payload_fingerprint(payload)
    path = tmp_path / "latest_ready.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, panel, metadata, symbol_map


def test_load_ready_top20_verifies_identity_and_current_inputs(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import load_ready_top20

    path, panel, metadata, symbol_map = _write_ready_payload(tmp_path)

    ready = load_ready_top20(
        path,
        expected_as_of=date(2026, 11, 15),
        panel_path=panel,
        metadata_path=metadata,
        symbol_map_path=symbol_map,
        require_current_inputs=True,
    )

    assert ready.as_of == date(2026, 11, 15)
    assert [member.coin_id for member in ready.members] == [
        f"coin-{index}" for index in range(1, 21)
    ]


def test_load_ready_top20_rejects_a_stale_universe(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import load_ready_top20

    path, _panel, _metadata, _symbol_map = _write_ready_payload(tmp_path)

    with pytest.raises(ValueError, match="does not match signal date"):
        load_ready_top20(path, expected_as_of=date(2026, 11, 16))


def test_load_ready_top20_rejects_changed_current_inputs(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import load_ready_top20

    path, panel, metadata, symbol_map = _write_ready_payload(tmp_path)
    panel.write_text("date,coin_id\n2026-11-15,coin-2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="panel input hash"):
        load_ready_top20(
            path,
            expected_as_of=date(2026, 11, 15),
            panel_path=panel,
            metadata_path=metadata,
            symbol_map_path=symbol_map,
            require_current_inputs=True,
        )


def test_bind_executable_top20_backfills_a_missing_contract_into_the_signal_universe() -> None:
    from atlas20.derivatives.top50_readiness import (
        ReadyTop20,
        SelectionMember,
        SelectionSkip,
        bind_executable_top20,
    )

    dates = pd.date_range("2026-11-13", periods=3, freq="D")
    universe = pd.DataFrame(
        [
            {
                "rebalance_date": day,
                "coin_id": f"coin-{rank}",
                "universe_rank": rank,
            }
            for day in dates
            for rank in range(1, 61)
        ]
    )
    executable = [rank for rank in range(1, 20)] + [21]
    ready = ReadyTop20(
        as_of=date(2026, 11, 15),
        fingerprint="sha256:" + "a" * 64,
        source_fingerprint="sha256:" + "b" * 64,
        source_path=Path("ready.json"),
        source_sha256="sha256:" + "c" * 64,
        members=tuple(
            SelectionMember(
                final_rank=final_rank,
                original_rank=original_rank,
                coin_id=f"coin-{original_rank}",
                symbol=f"C{original_rank}",
                bitget_symbol=f"C{original_rank}USDT",
                panel_symbol=f"C{original_rank}",
            )
            for final_rank, original_rank in enumerate(executable, start=1)
        ),
        skipped=(
            SelectionSkip(
                original_rank=20,
                coin_id="coin-20",
                symbol="C20",
                reason="VENUE_UNAVAILABLE",
            ),
        ),
        input_files={},
    )

    bound = bind_executable_top20(universe, ready)

    historical = bound.loc[bound["rebalance_date"] < pd.Timestamp("2026-11-15")]
    current = bound.loc[bound["rebalance_date"] == pd.Timestamp("2026-11-15")]
    assert historical.groupby("rebalance_date")["coin_id"].apply(list).map(
        lambda ids: ids == [f"coin-{rank}" for rank in range(1, 21)]
    ).all()
    assert current.sort_values("universe_rank")["coin_id"].tolist() == [
        f"coin-{rank}" for rank in executable
    ]
    assert current["universe_rank"].tolist() == list(range(1, 21))


def test_executable_top20_can_change_the_same_cycle_phase_signal_target() -> None:
    from atlas20.derivatives.top50_readiness import (
        ReadyTop20,
        SelectionMember,
        bind_executable_top20,
    )
    from atlas20.strategies.phase_momentum import (
        MomentumSignalSpec,
        PhaseMomentumSpec,
        build_phase_momentum_targets,
    )
    from atlas20.universe.builder import MarketDataBundle

    index = pd.date_range("2026-10-01", periods=30, freq="D")
    coins = [f"coin-{rank}" for rank in range(1, 61)]
    price = pd.DataFrame(index=index, columns=coins, dtype=float)
    for rank, coin in enumerate(coins, start=1):
        price[coin] = 100.0 + rank
    # Rank 21 is outside the ordinary CMC Top20 but displaces a missing
    # contract.  Its strong trend must be visible to the signal immediately.
    price["coin-21"] = pd.Series(
        [100.0 * (1.03 ** day) for day in range(len(index))], index=index
    )
    market = MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change().fillna(0.0),
        market_cap=price * 1_000_000.0,
        volume=pd.DataFrame(100_000_000.0, index=index, columns=coins),
        history_count=pd.DataFrame(300, index=index, columns=coins),
        metadata=pd.DataFrame({"sector": "Other"}, index=coins),
    )
    universe = pd.DataFrame(
        [
            {
                "rebalance_date": day,
                "coin_id": coin,
                "universe_rank": rank,
            }
            for day in index
            for rank, coin in enumerate(coins, start=1)
        ]
    )
    executable = [rank for rank in range(1, 20)] + [21]
    ready = ReadyTop20(
        as_of=index[-1].date(),
        fingerprint="sha256:" + "a" * 64,
        source_fingerprint="sha256:" + "b" * 64,
        source_path=Path("ready.json"),
        source_sha256="sha256:" + "c" * 64,
        members=tuple(
            SelectionMember(
                final_rank=final_rank,
                original_rank=original_rank,
                coin_id=f"coin-{original_rank}",
                symbol=f"C{original_rank}",
                bitget_symbol=f"C{original_rank}USDT",
                panel_symbol=f"C{original_rank}",
            )
            for final_rank, original_rank in enumerate(executable, start=1)
        ),
        skipped=(),
        input_files={},
    )
    bound = bind_executable_top20(universe, ready)

    built = build_phase_momentum_targets(
        market,
        bound,
        pd.DatetimeIndex(index),
        signal_specs=(MomentumSignalSpec("momentum-5d", ((5, 1.0),)),),
        spec=PhaseMomentumSpec(
            rebalance_days=1,
            phase_offsets=(0,),
            hold_rank=1,
            use_btc_gate=False,
            use_volatility_target=False,
            holdings_per_sleeve=1,
        ),
    )

    assert built.targets[index[-1]]["coin-21"] > 0.0


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


def test_mark_coverage_rejects_non_finite_ohlc_values(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_mark_coverage

    path = tmp_path / "BTC_mark.csv"
    frame = _ohlc(["2026-01-01T00:00:00Z"])
    frame.loc[0, "high"] = float("inf")
    frame.to_csv(path, index=False)

    result = check_mark_coverage(
        path,
        start=pd.Timestamp("2026-01-01T00:00:00Z"),
        required_end=pd.Timestamp("2026-01-01T01:00:00Z"),
    )

    assert any("invalid mark row" in item for item in result.failures)


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


def test_market_continuity_rejects_an_interior_page_boundary_gap(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_market_continuity

    path = tmp_path / "BTC_market.csv"
    _ohlc(
        [
            "2026-01-01T00:00:00Z",
            "2026-01-01T01:00:00Z",
            "2026-01-01T03:00:00Z",
        ]
    ).to_csv(path, index=False)

    result = check_market_continuity(
        path,
        required_last=pd.Timestamp("2026-01-01T03:00:00Z"),
    )

    assert result.missing_intervals == 1
    assert any("missing market hour 2026-01-01T02:00:00+00:00" in item for item in result.failures)


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


def test_funding_coverage_does_not_require_a_settlement_after_the_boundary(
    tmp_path,
) -> None:
    from atlas20.derivatives.top50_readiness import check_funding_coverage

    path = tmp_path / "BTC_funding.csv"
    pd.DataFrame(
        {
            "funding_time": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T08:00:00Z",
                "2026-01-01T16:00:00Z",
            ],
            "funding_rate": [0.0001, 0.0001, 0.0001],
        }
    ).to_csv(path, index=False)

    result = check_funding_coverage(
        path,
        required_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        required_end=pd.Timestamp("2026-01-01T23:00:00Z"),
        interval_hours=8.0,
    )

    assert result.failures == ()
    assert result.missing_intervals == 0


def test_funding_coverage_allows_the_first_new_listing_settlement(
    tmp_path,
) -> None:
    from atlas20.derivatives.top50_readiness import check_funding_coverage

    path = tmp_path / "NEW_funding.csv"
    pd.DataFrame(
        {
            "funding_time": [
                "2026-01-01T16:00:00Z",
                "2026-01-02T00:00:00Z",
            ],
            "funding_rate": [0.0001, 0.0001],
        }
    ).to_csv(path, index=False)

    result = check_funding_coverage(
        path,
        required_start=pd.Timestamp("2026-01-01T13:00:00Z"),
        required_end=pd.Timestamp("2026-01-02T00:00:00Z"),
        interval_hours=8.0,
    )

    assert result.failures == ()


def test_funding_coverage_rejects_a_first_settlement_beyond_one_interval(
    tmp_path,
) -> None:
    from atlas20.derivatives.top50_readiness import check_funding_coverage

    path = tmp_path / "LATE_funding.csv"
    pd.DataFrame(
        {
            "funding_time": ["2026-01-02T00:00:00Z"],
            "funding_rate": [0.0001],
        }
    ).to_csv(path, index=False)

    result = check_funding_coverage(
        path,
        required_start=pd.Timestamp("2026-01-01T13:00:00Z"),
        required_end=pd.Timestamp("2026-01-02T00:00:00Z"),
        interval_hours=8.0,
    )

    assert any("funding starts more than one interval after" in item for item in result.failures)


def _selection(members: int = 2) -> object:
    from atlas20.derivatives.top50_readiness import SelectionMember, Top50Selection

    return Top50Selection(
        as_of=date(2026, 1, 1),
        candidate_count=members,
        members=tuple(
            SelectionMember(
                final_rank=index,
                original_rank=index,
                coin_id=f"coin-{index}",
                symbol=f"C{index}",
                bitget_symbol=f"C{index}USDT",
                panel_symbol=f"C{index}",
            )
            for index in range(1, members + 1)
        ),
        skipped=(),
        source_fingerprint="sha256:test",
    )


def test_scoped_audit_inputs_contain_exactly_selected_members(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import write_scoped_audit_inputs

    selection = _selection()
    panel = pd.DataFrame(
        {
            "date": ["2026-01-01"] * 3,
            "coin_id": ["coin-1", "coin-2", "coin-3"],
            "symbol": ["C1", "C2", "C3"],
        }
    )
    mapping = pd.DataFrame(
        {
            "coin_id": ["coin-1", "coin-2", "coin-3"],
            "panel_symbol": ["C1", "C2", "C3"],
            "bitget_symbol": ["C1USDT", "C2USDT", "C3USDT"],
            "contract_status": ["normal", "normal", "normal"],
        }
    )
    panel_path = tmp_path / "panel.csv"
    map_path = tmp_path / "symbol_map.csv"
    panel.to_csv(panel_path, index=False)
    mapping.to_csv(map_path, index=False)

    scoped_panel, scoped_map = write_scoped_audit_inputs(
        output_dir=tmp_path / "audit",
        selection=selection,
        panel_path=panel_path,
        symbol_map_path=map_path,
    )

    assert set(pd.read_csv(scoped_panel)["coin_id"]) == {"coin-1", "coin-2"}
    assert set(pd.read_csv(scoped_map)["coin_id"]) == {"coin-1", "coin-2"}


def test_publish_only_creates_latest_ready_for_complete_fifty(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    blocked = {
        "as_of": "2026-11-15",
        "ready": False,
        "members": [{"final_rank": 1, "coin_id": "bitcoin", "status": "READY"}],
        "top20": [{"final_rank": 1, "coin_id": "bitcoin", "status": "READY"}],
        "skipped": [],
    }
    paths = publish_readiness_payload(
        reports_dir=tmp_path,
        payload=blocked,
        audit_payload={"passed": False, "checks": []},
    )
    assert paths["history"].is_file()
    assert paths["latest"].is_file()
    assert paths["audit"].is_file()
    assert not paths["latest_ready"].exists()

    ready = {
        **blocked,
        "ready": True,
        "audit": {"passed": True, "hard_failures": [], "warnings": []},
        "input_files": {
            "panel": "sha256:" + "1" * 64,
            "metadata": "sha256:" + "2" * 64,
            "symbol_map": "sha256:" + "3" * 64,
        },
        "members": [
            {
                "final_rank": index,
                "coin_id": f"coin-{index}",
                "bitget_symbol": f"C{index}USDT",
                "status": "READY",
            }
            for index in range(1, 51)
        ],
        "top20": [
            {
                "final_rank": index,
                "coin_id": f"coin-{index}",
                "bitget_symbol": f"C{index}USDT",
                "status": "READY",
            }
            for index in range(1, 21)
        ],
    }
    paths = publish_readiness_payload(
        reports_dir=tmp_path,
        payload=ready,
        audit_payload={"passed": True, "checks": []},
    )
    assert paths["latest_ready"].is_file()
    assert paths["ready_history"].is_file()


def test_audit_failures_are_mapped_to_the_affected_member() -> None:
    from atlas20.derivatives.data_audit import DataAuditReport
    from atlas20.derivatives.top50_readiness import audit_failures_by_member

    report = DataAuditReport(
        passed=False,
        checks=[
            {"name": "marks.coin-1.recent_gap", "passed": False, "detail": "gap"},
            {"name": "funding.coin-2.manifest_matches", "passed": False, "detail": "lag"},
            {"name": "panel.last_completed_day", "passed": False, "detail": "stale"},
        ],
    )

    failures = audit_failures_by_member(report, _selection())

    assert failures["coin-1"] == ["marks.coin-1.recent_gap: gap"]
    assert failures["coin-2"] == ["funding.coin-2.manifest_matches: lag"]
    assert any(item.startswith("panel.last_completed_day") for item in failures["global"])


def test_collect_member_evidence_accepts_complete_real_shaped_files(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import collect_member_evidence

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01"], utc=True),
            "coin_id": ["coin-1"],
            "price": [1.0],
            "volume_usd": [10.0],
            "market_cap": [100.0],
        }
    )
    warmup_mark = tmp_path / "C1USDT_mark.csv"
    warmup_market = tmp_path / "C1USDT_market.csv"
    live_mark = tmp_path / "C1USDT_live_mark.csv"
    live_market = tmp_path / "C1USDT_live_market.csv"
    funding = tmp_path / "coin-1.csv"
    hourly = pd.date_range("2026-01-01", periods=24, freq="h", tz="UTC")
    live_hourly = pd.date_range("2026-01-01", periods=25, freq="h", tz="UTC")
    warmup_market_hourly = live_hourly
    _ohlc([stamp.isoformat() for stamp in hourly]).to_csv(warmup_mark, index=False)
    _ohlc([stamp.isoformat() for stamp in live_hourly]).to_csv(live_mark, index=False)
    _ohlc([stamp.isoformat() for stamp in warmup_market_hourly]).to_csv(
        warmup_market, index=False
    )
    _ohlc([stamp.isoformat() for stamp in live_hourly]).to_csv(
        live_market, index=False
    )
    pd.DataFrame(
        {
            "funding_time": pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T08:00:00Z",
                    "2026-01-01T16:00:00Z",
                    "2026-01-02T00:00:00Z",
                ],
                utc=True,
            ),
            "funding_rate": [0.0001] * 4,
        }
    ).to_csv(funding, index=False)
    map_row = pd.Series(
        {
            "coin_id": "coin-1",
            "panel_symbol": "C1",
            "bitget_symbol": "C1USDT",
            "contract_status": "normal",
            "open_time": "2026-01-01T00:00:00Z",
            "fund_interval": 8.0,
        }
    )

    evidence = collect_member_evidence(
        member=_selection().members[0],
        map_row=map_row,
        panel=panel,
        warmup_mark_path=warmup_mark,
        warmup_market_path=warmup_market,
        live_mark_path=live_mark,
        live_market_path=live_market,
        funding_path=funding,
        warmup_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        warmup_end=pd.Timestamp("2026-01-02T00:00:00Z"),
        oos_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        latest_signal_day=date(2026, 1, 1),
        # 00:35Z is the production 08:35 Beijing prepare time.  The upcoming
        # 01:00Z execution bar does not exist yet and must be checked by the
        # executor, not make the completed-day readiness audit fail.
        now=pd.Timestamp("2026-01-02T00:35:00Z"),
    )

    assert evidence["status"] == "READY", evidence["failure_details"]
    assert evidence["failure_details"] == []
    assert set(evidence["files"]) == {
        "warmup_mark",
        "warmup_market",
        "live_mark",
        "live_market",
        "funding",
    }
    assert all(str(value).startswith("sha256:") for value in evidence["files"].values())


def test_contract_open_time_preserves_listing_hour() -> None:
    from atlas20.derivatives.top50_readiness import _contract_open_timestamp

    stamp = _contract_open_timestamp({"open_time": "2026-01-01T12:00:00Z"})

    assert stamp == pd.Timestamp("2026-01-01T12:00:00Z")


def test_hourly_coverage_start_aligns_a_non_hour_listing() -> None:
    from atlas20.derivatives.top50_readiness import _hour_grid_start

    assert _hour_grid_start(
        pd.Timestamp("2026-01-01T12:34:00Z")
    ) == pd.Timestamp("2026-01-01T13:00:00Z")
    assert _hour_grid_start(
        pd.Timestamp("2026-01-01T12:00:00Z")
    ) == pd.Timestamp("2026-01-01T12:00:00Z")


def test_assess_selection_builds_ready_top20_from_ready_top50(
    tmp_path, monkeypatch
) -> None:
    import atlas20.derivatives.top50_readiness as readiness
    from atlas20.derivatives.data_audit import DataAuditReport

    selection = _selection(50)
    panel_rows = []
    map_rows = []
    warmup_mark_dir = tmp_path / "warmup" / "candles"
    warmup_market_dir = tmp_path / "warmup_market" / "candles"
    live_dir = tmp_path / "live"
    live_mark_dir = live_dir / "candles"
    funding_dir = live_dir / "funding"
    for directory in (warmup_mark_dir, warmup_market_dir, live_mark_dir, funding_dir):
        directory.mkdir(parents=True)
    hourly = pd.date_range("2026-01-01", periods=24, freq="h", tz="UTC")
    live_hourly = pd.date_range("2026-01-01", periods=25, freq="h", tz="UTC")
    warmup_market_hourly = live_hourly
    for member in selection.members:
        panel_rows.append(
            {
                "date": "2026-01-01",
                "coin_id": member.coin_id,
                "symbol": member.symbol,
                "price": 1.0,
                "volume_usd": 50_000_000.0,
                "market_cap": 1_000_000_000.0,
            }
        )
        map_rows.append(
            {
                "coin_id": member.coin_id,
                "panel_symbol": member.panel_symbol,
                "bitget_symbol": member.bitget_symbol,
                "contract_status": "normal",
                "open_time": "2026-01-01T00:00:00Z",
                "fund_interval": 8.0,
            }
        )
        _ohlc([stamp.isoformat() for stamp in hourly]).to_csv(
            warmup_mark_dir / f"{member.bitget_symbol}_mark.csv", index=False
        )
        _ohlc([stamp.isoformat() for stamp in live_hourly]).to_csv(
            live_mark_dir / f"{member.bitget_symbol}_mark.csv", index=False
        )
        _ohlc([stamp.isoformat() for stamp in warmup_market_hourly]).to_csv(
            warmup_market_dir / f"{member.bitget_symbol}_market.csv",
            index=False,
        )
        _ohlc([stamp.isoformat() for stamp in live_hourly]).to_csv(
            live_mark_dir / f"{member.bitget_symbol}_market.csv",
            index=False,
        )
        pd.DataFrame(
            {
                "funding_time": pd.to_datetime(
                    [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T08:00:00Z",
                        "2026-01-01T16:00:00Z",
                        "2026-01-02T00:00:00Z",
                    ],
                    utc=True,
                ),
                "funding_rate": [0.0001] * 4,
            }
        ).to_csv(funding_dir / f"{member.coin_id}.csv", index=False)
    panel_path = tmp_path / "panel.csv"
    metadata_path = tmp_path / "metadata.csv"
    map_path = tmp_path / "symbol_map.csv"
    pd.DataFrame(panel_rows).to_csv(panel_path, index=False)
    pd.DataFrame({"coin_id": [member.coin_id for member in selection.members]}).to_csv(
        metadata_path, index=False
    )
    pd.DataFrame(map_rows).to_csv(map_path, index=False)
    monkeypatch.setattr(
        readiness,
        "audit_selected_top50",
        lambda **_kwargs: DataAuditReport(passed=True, checks=[]),
    )

    payload, blocked = readiness.assess_selection(
        selection=selection,
        panel_path=panel_path,
        metadata_path=metadata_path,
        symbol_map_path=map_path,
        raw_dir=live_dir,
        warmup_mark_dir=warmup_mark_dir.parent,
        warmup_market_dir=warmup_market_dir.parent,
        reports_dir=tmp_path / "reports",
        warmup_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        warmup_end=pd.Timestamp("2026-01-02T00:00:00Z"),
        oos_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        latest_signal_day=date(2026, 1, 1),
        now=pd.Timestamp("2026-01-02T00:35:00Z"),
    )

    assert blocked == set()
    assert payload["ready"] is True
    assert len(payload["members"]) == 50
    assert len(payload["top20"]) == 20
    assert [item["final_rank"] for item in payload["top20"]] == list(range(1, 21))
    assert set(payload["input_files"]) == {"panel", "metadata", "symbol_map"}
    assert all(
        str(digest).startswith("sha256:") for digest in payload["input_files"].values()
    )


def _payload() -> dict[str, object]:
    return {
        "as_of": "2026-11-15",
        "ready": True,
        "members": [
            {
                "final_rank": 1,
                "coin_id": "bitcoin",
                "symbol": "BTC",
                "status": "READY",
                "failure_details": [],
            },
            {
                "final_rank": 2,
                "coin_id": "ethereum",
                "symbol": "ETH",
                "status": "READY",
                "failure_details": [],
            },
        ],
        "top20": [
            {
                "final_rank": 2,
                "coin_id": "ethereum",
                "symbol": "ETH",
                "status": "READY",
                "failure_details": [],
            }
        ],
    }


def test_first_run_initializes_without_fifty_messages() -> None:
    from atlas20.derivatives.top50_readiness import build_notification_events

    events = build_notification_events({}, _payload(), initialized=False)

    assert events == ()


def test_first_run_alerts_blocked_members_without_history_entries() -> None:
    from atlas20.derivatives.top50_readiness import build_notification_events

    payload = _payload()
    payload["ready"] = False
    payload["members"][1]["status"] = "BLOCKED"
    payload["members"][1]["failure_details"] = ["live_mark: missing hour"]
    payload["top20"][0]["status"] = "BLOCKED"
    payload["top20"][0]["failure_details"] = ["live_mark: missing hour"]

    events = build_notification_events({}, payload, initialized=False)

    assert [event["event"] for event in events] == ["TOP50_DATA_BLOCKED"]
    assert events[0]["coin_id"] == "ethereum"
    assert "missing hour" in events[0]["details"]


def test_new_top50_and_top20_members_emit_one_event_each() -> None:
    from atlas20.derivatives.top50_readiness import build_notification_events

    events = build_notification_events(
        {
            "members": ["bitcoin"],
            "top20": ["bitcoin"],
            "member_status": {"bitcoin": "READY"},
        },
        _payload(),
        initialized=True,
    )

    assert [event["event"] for event in events] == [
        "TOP50_ENTER",
        "TOP50_DATA_READY",
        "TOP20_ENTER",
    ]
    assert {event["coin_id"] for event in events} == {"ethereum"}
    assert len({event["key"] for event in events}) == 3


def test_member_status_change_emits_blocked_once() -> None:
    from atlas20.derivatives.top50_readiness import build_notification_events

    payload = _payload()
    payload["members"][1]["status"] = "BLOCKED"
    payload["members"][1]["failure_details"] = ["live_mark: missing hour"]
    payload["top20"][0]["status"] = "BLOCKED"
    events = build_notification_events(
        {
            "members": ["bitcoin", "ethereum"],
            "top20": ["ethereum"],
            "member_status": {"bitcoin": "READY", "ethereum": "READY"},
        },
        payload,
        initialized=True,
    )

    assert [event["event"] for event in events] == ["TOP50_DATA_BLOCKED"]
    assert "missing hour" in events[0]["details"]


def test_failed_delivery_stays_pending_and_success_is_deduplicated(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import (
        load_state,
        queue_notification_events,
        record_notification_result,
        write_state,
    )

    event = {
        "key": "TOP50_ENTER|ethereum|2026-11-15",
        "event": "TOP50_ENTER",
        "coin_id": "ethereum",
        "symbol": "ETH",
        "as_of": "2026-11-15",
        "status": "READY",
        "details": "",
    }
    state = {
        "version": 1,
        "notifications": {"sent_keys": {}, "pending": {}},
    }
    queue_notification_events(state, (event,))
    record_notification_result(
        state,
        event,
        sent=False,
        error="telegram down",
        sent_at="2026-11-15T10:00:00Z",
    )
    assert event["key"] in state["notifications"]["pending"]

    record_notification_result(
        state,
        event,
        sent=True,
        error=None,
        sent_at="2026-11-15T10:01:00Z",
    )
    assert event["key"] in state["notifications"]["sent_keys"]
    assert event["key"] not in state["notifications"]["pending"]

    path = tmp_path / "top50_state.json"
    write_state(path, state)
    assert load_state(path)["notifications"]["sent_keys"][event["key"]]


def test_unsent_status_events_are_superseded_by_the_latest_status() -> None:
    from atlas20.derivatives.top50_readiness import queue_notification_events

    blocked = {
        "key": "TOP50_DATA_BLOCKED|coin-1|2026-11-15",
        "event": "TOP50_DATA_BLOCKED",
        "coin_id": "coin-1",
        "symbol": "C1",
        "as_of": "2026-11-15",
        "status": "BLOCKED",
        "details": "missing funding",
    }
    top20 = {
        "key": "TOP20_ENTER|coin-1|2026-11-15",
        "event": "TOP20_ENTER",
        "coin_id": "coin-1",
        "symbol": "C1",
        "as_of": "2026-11-15",
        "status": "BLOCKED",
        "details": "missing funding",
    }
    enter = {
        **top20,
        "key": "TOP50_ENTER|coin-1|2026-11-15",
        "event": "TOP50_ENTER",
    }
    ready = {
        **blocked,
        "key": "TOP50_DATA_READY|coin-1|2026-11-15",
        "event": "TOP50_DATA_READY",
        "status": "READY",
        "details": "",
    }
    state = {
        "version": 1,
        "notifications": {
            "sent_keys": {},
            "pending": {
                blocked["key"]: blocked,
                enter["key"]: enter,
                top20["key"]: top20,
            },
        },
    }

    queue_notification_events(state, (ready,))

    pending = state["notifications"]["pending"]
    assert blocked["key"] not in pending
    assert pending[ready["key"]]["status"] == "READY"
    assert pending[enter["key"]]["status"] == "READY"
    assert pending[enter["key"]]["details"] == ""
    assert pending[top20["key"]]["status"] == "READY"
    assert pending[top20["key"]]["details"] == ""


def test_reconcile_pending_keeps_only_the_final_status_for_the_day() -> None:
    from atlas20.derivatives.top50_readiness import reconcile_notification_queue

    blocked = {
        "key": "TOP50_DATA_BLOCKED|coin-1|2026-11-15",
        "event": "TOP50_DATA_BLOCKED",
        "coin_id": "coin-1",
        "symbol": "C1",
        "as_of": "2026-11-15",
        "status": "BLOCKED",
        "details": "missing funding",
    }
    ready = {
        **blocked,
        "key": "TOP50_DATA_READY|coin-1|2026-11-15",
        "event": "TOP50_DATA_READY",
        "status": "READY",
        "details": "",
    }
    previous_day = {
        **blocked,
        "key": "TOP50_DATA_BLOCKED|coin-1|2026-11-14",
        "as_of": "2026-11-14",
    }
    already_sent = {
        **ready,
        "key": "TOP50_DATA_READY|coin-2|2026-11-15",
        "coin_id": "coin-2",
    }
    state = {
        "version": 1,
        "notifications": {
            "sent_keys": {already_sent["key"]: {"sent_at": "2026-11-16T09:45:00Z"}},
            "pending": {
                blocked["key"]: blocked,
                ready["key"]: ready,
                previous_day["key"]: previous_day,
                already_sent["key"]: already_sent,
            },
        },
    }
    payload = {
        "as_of": "2026-11-15",
        "members": [
            {
                "coin_id": "coin-1",
                "symbol": "C1",
                "status": "READY",
                "failure_details": [],
            }
        ],
        "top20": [],
    }

    reconcile_notification_queue(state, payload)

    pending = state["notifications"]["pending"]
    assert blocked["key"] not in pending
    assert ready["key"] in pending
    assert previous_day["key"] in pending
    assert already_sent["key"] not in pending


def test_reconcile_drops_unsent_entry_events_after_same_day_exit() -> None:
    from atlas20.derivatives.top50_readiness import reconcile_notification_queue

    enter = {
        "key": "TOP50_ENTER|coin-1|2026-11-15",
        "event": "TOP50_ENTER",
        "coin_id": "coin-1",
        "symbol": "C1",
        "as_of": "2026-11-15",
        "status": "READY",
        "details": "",
    }
    top20 = {
        **enter,
        "key": "TOP20_ENTER|coin-1|2026-11-15",
        "event": "TOP20_ENTER",
    }
    state = {
        "version": 1,
        "notifications": {
            "sent_keys": {},
            "pending": {enter["key"]: enter, top20["key"]: top20},
        },
    }

    reconcile_notification_queue(
        state,
        {"as_of": "2026-11-15", "members": [], "top20": []},
    )

    assert state["notifications"]["pending"] == {}


def test_new_listing_without_a_completed_live_bar_blocks_instead_of_raising(
    tmp_path,
) -> None:
    from atlas20.derivatives.top50_readiness import collect_member_evidence

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01"], utc=True),
            "coin_id": ["coin-1"],
            "price": [1.0],
            "volume_usd": [10.0],
            "market_cap": [100.0],
        }
    )
    warmup_mark = tmp_path / "C1USDT_mark.csv"
    warmup_market = tmp_path / "C1USDT_market.csv"
    live_mark = tmp_path / "C1USDT_live_mark.csv"
    live_market = tmp_path / "C1USDT_live_market.csv"
    funding = tmp_path / "coin-1.csv"
    _ohlc(["2026-01-02T01:00:00Z"]).to_csv(warmup_mark, index=False)
    _ohlc(["2026-01-02T01:00:00Z"]).to_csv(warmup_market, index=False)
    _ohlc(["2026-01-02T01:00:00Z"]).to_csv(live_mark, index=False)
    _ohlc(["2026-01-02T01:00:00Z"]).to_csv(live_market, index=False)
    pd.DataFrame(
        {
            "funding_time": pd.to_datetime(["2026-01-02T00:00:00Z"], utc=True),
            "funding_rate": [0.0001],
        }
    ).to_csv(funding, index=False)
    map_row = pd.Series(
        {
            "coin_id": "coin-1",
            "panel_symbol": "C1",
            "bitget_symbol": "C1USDT",
            "contract_status": "normal",
            "open_time": "2026-01-02T01:00:00Z",
            "fund_interval": 8.0,
        }
    )

    evidence = collect_member_evidence(
        member=_selection().members[0],
        map_row=map_row,
        panel=panel,
        warmup_mark_path=warmup_mark,
        warmup_market_path=warmup_market,
        live_mark_path=live_mark,
        live_market_path=live_market,
        funding_path=funding,
        warmup_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        warmup_end=pd.Timestamp("2026-01-02T00:00:00Z"),
        oos_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        latest_signal_day=date(2026, 1, 1),
        now=pd.Timestamp("2026-01-02T00:35:00Z"),
    )

    assert evidence["status"] == "BLOCKED"
    assert any("required completed mark start" in item for item in evidence["failure_details"])


def test_format_event_message_marks_blocked_top20_without_rank51_fallback() -> None:
    from atlas20.derivatives.top50_readiness import format_event_message

    message = format_event_message(
        {
            "key": "TOP20_ENTER|ethereum|2026-11-15",
            "event": "TOP20_ENTER",
            "coin_id": "ethereum",
            "symbol": "ETH",
            "as_of": "2026-11-15",
            "status": "BLOCKED",
            "details": "live_mark: missing hour",
        }
    )

    assert "TOP20_ENTER" in message
    assert "BLOCKED" in message
    assert "missing hour" in message
    assert "禁止用第 51 名" in message


def test_warmup_market_range_accepts_sparse_hourly_prints(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_market_file_range

    path = tmp_path / "BTC_market.csv"
    _ohlc(
        ["2026-01-01T01:00:00Z", "2026-01-10T01:00:00Z", "2026-01-20T01:00:00Z"]
    ).to_csv(path, index=False)

    result = check_market_file_range(
        path,
        required_first_day=date(2026, 1, 1),
        required_last_day=date(2026, 1, 20),
    )

    assert result.failures == ()


def test_collect_member_evidence_infers_start_when_contract_open_time_is_blank(
    tmp_path,
) -> None:
    from atlas20.derivatives.top50_readiness import collect_member_evidence

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01"], utc=True),
            "coin_id": ["coin-1"],
            "price": [1.0],
            "volume_usd": [10.0],
            "market_cap": [100.0],
        }
    )
    warmup_mark = tmp_path / "C1USDT_mark.csv"
    warmup_market = tmp_path / "C1USDT_market.csv"
    live_mark = tmp_path / "C1USDT_live_mark.csv"
    live_market = tmp_path / "C1USDT_live_market.csv"
    funding = tmp_path / "coin-1.csv"
    hourly = pd.date_range("2026-01-01T04:00:00Z", periods=20, freq="h")
    live_hourly = pd.date_range("2026-01-01T04:00:00Z", periods=21, freq="h")
    _ohlc([stamp.isoformat() for stamp in hourly]).to_csv(warmup_mark, index=False)
    _ohlc([stamp.isoformat() for stamp in live_hourly]).to_csv(live_mark, index=False)
    warmup_market_hourly = live_hourly
    _ohlc([stamp.isoformat() for stamp in warmup_market_hourly]).to_csv(
        warmup_market, index=False
    )
    _ohlc([stamp.isoformat() for stamp in live_hourly]).to_csv(
        live_market, index=False
    )
    pd.DataFrame(
        {
            "funding_time": pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T08:00:00Z",
                    "2026-01-01T16:00:00Z",
                    "2026-01-02T00:00:00Z",
                ],
                utc=True,
            ),
            "funding_rate": [0.0001] * 4,
        }
    ).to_csv(funding, index=False)
    map_row = pd.Series(
        {
            "coin_id": "coin-1",
            "panel_symbol": "C1",
            "bitget_symbol": "C1USDT",
            "contract_status": "normal",
            "open_time": None,
            "fund_interval": 8.0,
        }
    )

    evidence = collect_member_evidence(
        member=_selection().members[0],
        map_row=map_row,
        panel=panel,
        warmup_mark_path=warmup_mark,
        warmup_market_path=warmup_market,
        live_mark_path=live_mark,
        live_market_path=live_market,
        funding_path=funding,
        warmup_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        warmup_end=pd.Timestamp("2026-01-02T00:00:00Z"),
        oos_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        latest_signal_day=date(2026, 1, 1),
        now=pd.Timestamp("2026-01-02T00:35:00Z"),
    )

    assert evidence["status"] == "READY", evidence["failure_details"]
    assert evidence["contract_open_time"] == "2026-01-01"


def test_warmup_market_range_allows_one_silent_listing_day(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_market_file_range

    path = tmp_path / "C1_market.csv"
    _ohlc(["2026-01-02T01:00:00Z", "2026-01-20T01:00:00Z"]).to_csv(
        path, index=False
    )

    result = check_market_file_range(
        path,
        required_first_day=date(2026, 1, 1),
        required_last_day=date(2026, 1, 20),
    )

    assert result.failures == ()


def test_panel_historical_bad_market_cap_is_a_warning_not_a_block() -> None:
    from atlas20.derivatives.top50_readiness import check_panel_history

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True),
            "coin_id": ["bitcoin", "bitcoin"],
            "price": [1.0, 1.0],
            "volume_usd": [10.0, 10.0],
            "market_cap": [0.0, 100.0],
        }
    )

    result = check_panel_history(panel, coin_id="bitcoin", latest_day=date(2026, 1, 2))

    assert result.failures == ()
    assert any("unrankable" in item for item in result.warnings)


def test_panel_historical_zero_volume_is_an_explicit_warning() -> None:
    from atlas20.derivatives.top50_readiness import check_panel_history

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True),
            "coin_id": ["aave", "aave"],
            "price": [1.0, 1.0],
            "volume_usd": [0.0, 10.0],
            "market_cap": [100.0, 100.0],
        }
    )

    result = check_panel_history(panel, coin_id="aave", latest_day=date(2026, 1, 2))

    assert result.failures == ()
    assert any("historical CMC volume" in item for item in result.warnings)


def test_panel_latest_zero_volume_blocks() -> None:
    from atlas20.derivatives.top50_readiness import check_panel_history

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True),
            "coin_id": ["aave", "aave"],
            "price": [1.0, 1.0],
            "volume_usd": [10.0, 0.0],
            "market_cap": [100.0, 100.0],
        }
    )

    result = check_panel_history(panel, coin_id="aave", latest_day=date(2026, 1, 2))

    assert any("non-positive latest CMC volume" in item for item in result.failures)


def test_panel_latest_bad_market_cap_blocks() -> None:
    from atlas20.derivatives.top50_readiness import check_panel_history

    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True),
            "coin_id": ["bitcoin", "bitcoin"],
            "price": [1.0, 1.0],
            "volume_usd": [10.0, 10.0],
            "market_cap": [100.0, 0.0],
        }
    )

    result = check_panel_history(panel, coin_id="bitcoin", latest_day=date(2026, 1, 2))

    assert any("latest CMC market cap" in item for item in result.failures)


def test_warmup_market_late_trade_start_is_visible_but_not_a_hard_block(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import check_market_file_range

    path = tmp_path / "C1_market.csv"
    _ohlc(["2026-01-03T01:00:00Z", "2026-01-20T01:00:00Z"]).to_csv(
        path, index=False
    )

    result = check_market_file_range(
        path,
        required_first_day=date(2026, 1, 1),
        required_last_day=date(2026, 1, 20),
    )

    assert result.failures == ()
    assert any("starts later" in item for item in result.warnings)


def test_publish_fingerprint_ignores_audit_wall_clock(tmp_path) -> None:
    import json
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    payload = {
        "as_of": "2026-11-15",
        "ready": False,
        "members": [{"final_rank": 1, "coin_id": "bitcoin", "status": "READY"}],
        "top20": [{"final_rank": 1, "coin_id": "bitcoin", "status": "READY"}],
        "skipped": [],
        "audit": {
            "passed": True,
            "hard_failures": [],
            "warnings": [],
            "provenance": {"fingerprint": "sha256:files"},
            "summary": {"now": "2026-11-16T18:00:00Z", "publication_now": "A"},
        },
    }
    first = publish_readiness_payload(
        reports_dir=tmp_path / "first",
        payload=payload,
        audit_payload={"passed": True},
    )
    changed = {
        **payload,
        "audit": {
            **payload["audit"],
            "summary": {
                "now": "2026-11-16T19:00:00Z",
                "publication_now": "B",
            },
        },
    }
    second = publish_readiness_payload(
        reports_dir=tmp_path / "second",
        payload=changed,
        audit_payload={"passed": True},
    )

    first_payload = json.loads(first["latest"].read_text())
    second_payload = json.loads(second["latest"].read_text())
    assert first_payload["fingerprint"] == second_payload["fingerprint"]


def test_publish_fingerprint_commits_to_member_file_hashes(tmp_path) -> None:
    import json
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    payload = {
        "as_of": "2026-11-15",
        "ready": False,
        "members": [
            {
                "final_rank": 1,
                "coin_id": "bitcoin",
                "status": "READY",
                "files": {"live_market": "sha256:market-a"},
            }
        ],
        "top20": [{"final_rank": 1, "coin_id": "bitcoin", "status": "READY"}],
        "skipped": [],
    }
    first = publish_readiness_payload(
        reports_dir=tmp_path / "first",
        payload=payload,
        audit_payload={"passed": True},
    )
    changed = {
        **payload,
        "members": [
            {
                **payload["members"][0],
                "files": {"live_market": "sha256:market-b"},
            }
        ],
    }
    second = publish_readiness_payload(
        reports_dir=tmp_path / "second",
        payload=changed,
        audit_payload={"passed": True},
    )

    first_payload = json.loads(first["latest"].read_text())
    second_payload = json.loads(second["latest"].read_text())
    assert first_payload["fingerprint"] != second_payload["fingerprint"]


def test_publish_rejects_duplicate_ready_members(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    members = [
        {"final_rank": index, "coin_id": f"coin-{index}", "status": "READY"}
        for index in range(1, 51)
    ]
    members[1]["coin_id"] = members[0]["coin_id"]
    payload = {
        "as_of": "2026-11-15",
        "ready": True,
        "members": members,
        "top20": members[:20],
        "skipped": [],
    }

    with pytest.raises(ValueError, match="duplicate coin_id"):
        publish_readiness_payload(
            reports_dir=tmp_path,
            payload=payload,
            audit_payload={"passed": True},
        )


@pytest.mark.parametrize("field", ["coin_id", "bitget_symbol"])
def test_publish_rejects_empty_ready_member_identity(tmp_path, field: str) -> None:
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    members = [
        {
            "final_rank": index,
            "coin_id": f"coin-{index}",
            "bitget_symbol": f"C{index}USDT",
            "status": "READY",
        }
        for index in range(1, 51)
    ]
    members[0][field] = ""
    payload = {
        "as_of": "2026-11-15",
        "ready": True,
        "members": members,
        "top20": members[:20],
        "skipped": [],
    }

    with pytest.raises(ValueError, match="empty ready member"):
        publish_readiness_payload(
            reports_dir=tmp_path,
            payload=payload,
            audit_payload={"passed": True},
        )


def test_publish_rejects_fractional_ready_rank(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    members = [
        {
            "final_rank": index,
            "coin_id": f"coin-{index}",
            "bitget_symbol": f"C{index}USDT",
            "status": "READY",
        }
        for index in range(1, 51)
    ]
    members[0]["final_rank"] = 1.5
    payload = {
        "as_of": "2026-11-15",
        "ready": True,
        "members": members,
        "top20": members[:20],
        "skipped": [],
    }

    with pytest.raises(ValueError, match="final ranks are not sequential"):
        publish_readiness_payload(
            reports_dir=tmp_path,
            payload=payload,
            audit_payload={"passed": True},
        )


def test_publish_rejects_ready_payload_when_audit_did_not_pass(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    members = [
        {
            "final_rank": index,
            "coin_id": f"coin-{index}",
            "bitget_symbol": f"C{index}USDT",
            "status": "READY",
        }
        for index in range(1, 51)
    ]
    payload = {
        "as_of": "2026-11-15",
        "ready": True,
        "members": members,
        "top20": members[:20],
        "skipped": [],
        "audit": {"passed": False, "hard_failures": ["audit failed"]},
    }

    with pytest.raises(ValueError, match="audit did not pass"):
        publish_readiness_payload(
            reports_dir=tmp_path,
            payload=payload,
            audit_payload={"passed": False, "hard_failures": ["audit failed"]},
        )


def test_publish_rejects_ready_payload_without_input_file_commitments(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    members = [
        {
            "final_rank": index,
            "coin_id": f"coin-{index}",
            "bitget_symbol": f"C{index}USDT",
            "status": "READY",
        }
        for index in range(1, 51)
    ]
    payload = {
        "as_of": "2026-11-15",
        "ready": True,
        "members": members,
        "top20": members[:20],
        "skipped": [],
        "audit": {"passed": True, "hard_failures": [], "warnings": []},
    }

    with pytest.raises(ValueError, match="input file commitments"):
        publish_readiness_payload(
            reports_dir=tmp_path,
            payload=payload,
            audit_payload={"passed": True},
        )
