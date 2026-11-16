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
        "members": [
            {"final_rank": index, "coin_id": f"coin-{index}", "status": "READY"}
            for index in range(1, 51)
        ],
        "top20": [
            {"final_rank": index, "coin_id": f"coin-{index}", "status": "READY"}
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
    _ohlc([stamp.isoformat() for stamp in hourly]).to_csv(warmup_mark, index=False)
    _ohlc([stamp.isoformat() for stamp in live_hourly]).to_csv(live_mark, index=False)
    _ohlc(["2026-01-01T01:00:00Z", "2026-01-02T01:00:00Z"]).to_csv(
        warmup_market, index=False
    )
    _ohlc(["2026-01-01T01:00:00Z", "2026-01-02T01:00:00Z"]).to_csv(
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
        now=pd.Timestamp("2026-01-02T18:00:00Z"),
    )

    assert evidence["status"] == "READY", evidence["failure_details"]
    assert evidence["failure_details"] == []


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
        _ohlc(
            ["2026-01-01T01:00:00Z", "2026-01-02T01:00:00Z"]
        ).to_csv(
            warmup_market_dir / f"{member.bitget_symbol}_market.csv",
            index=False,
        )
        _ohlc(
            ["2026-01-01T01:00:00Z", "2026-01-02T01:00:00Z"]
        ).to_csv(
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
    map_path = tmp_path / "symbol_map.csv"
    pd.DataFrame(panel_rows).to_csv(panel_path, index=False)
    pd.DataFrame(map_rows).to_csv(map_path, index=False)
    monkeypatch.setattr(
        readiness,
        "audit_selected_top50",
        lambda **_kwargs: DataAuditReport(passed=True, checks=[]),
    )

    payload, blocked = readiness.assess_selection(
        selection=selection,
        panel_path=panel_path,
        symbol_map_path=map_path,
        raw_dir=live_dir,
        warmup_mark_dir=warmup_mark_dir.parent,
        warmup_market_dir=warmup_market_dir.parent,
        reports_dir=tmp_path / "reports",
        warmup_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        warmup_end=pd.Timestamp("2026-01-02T00:00:00Z"),
        oos_start=pd.Timestamp("2026-01-01T00:00:00Z"),
        latest_signal_day=date(2026, 1, 1),
        now=pd.Timestamp("2026-01-02T18:00:00Z"),
    )

    assert blocked == set()
    assert payload["ready"] is True
    assert len(payload["members"]) == 50
    assert len(payload["top20"]) == 20
    assert [item["final_rank"] for item in payload["top20"]] == list(range(1, 21))


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
