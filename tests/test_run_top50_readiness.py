from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest


def _selection(count: int = 2):
    from atlas20.derivatives.top50_readiness import SelectionMember, Top50Selection

    return Top50Selection(
        as_of=date(2026, 11, 15),
        candidate_count=count,
        members=tuple(
            SelectionMember(
                final_rank=index,
                original_rank=index,
                coin_id=f"coin-{index}",
                symbol=f"C{index}",
                bitget_symbol=f"C{index}USDT",
                panel_symbol=f"C{index}",
            )
            for index in range(1, count + 1)
        ),
        skipped=(),
        source_fingerprint="sha256:test",
    )


def _session(tmp_path: Path):
    from scripts.run_top50_readiness import ReadinessSession

    return ReadinessSession(
        project_root=tmp_path,
        config_path=tmp_path / "config/base.yaml",
        panel_path=tmp_path / "data/processed/panel_daily.csv",
        metadata_path=tmp_path / "data/processed/metadata.csv",
        raw_dir=tmp_path / "data/raw/live",
        warmup_mark_dir=tmp_path / "data/raw/warmup",
        warmup_market_dir=tmp_path / "data/raw/warmup_market",
        symbol_map_path=tmp_path / "data/raw/live/symbol_map.csv",
        state_path=tmp_path / "data/top50_readiness_state.json",
        reports_dir=tmp_path / "reports/top50_data_readiness",
        lock_path=tmp_path / "data/derivatives_execution.lock",
        oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
        warmup_start=pd.Timestamp("2022-01-01", tz="UTC"),
        warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
        universe_limit=60,
    )


def _ready_payload(count: int = 50) -> dict[str, object]:
    members = [
        {
            "final_rank": index,
            "original_rank": index,
            "coin_id": f"coin-{index}",
            "symbol": f"C{index}",
            "bitget_symbol": f"C{index}USDT",
            "status": "READY",
            "failure_details": [],
        }
        for index in range(1, count + 1)
    ]
    return {
        "as_of": "2026-11-15",
        "ready": count == 50,
        "members": members,
        "top20": [dict(item) for item in members[:20]],
        "skipped": [],
        "audit_detail": {"passed": True, "checks": []},
    }


def _write_rank_inputs(session, count: int = 50) -> pd.DataFrame:
    session.symbol_map_path.parent.mkdir(parents=True)
    ranked = pd.DataFrame(
        {
            "coin_id": [f"coin-{index}" for index in range(1, count + 1)],
            "symbol": [f"C{index}" for index in range(1, count + 1)],
            "universe_rank": range(1, count + 1),
        }
    )
    mapping = ranked.rename(columns={"symbol": "panel_symbol"}).copy()
    mapping["bitget_symbol"] = mapping["coin_id"].map(
        lambda coin: coin.replace("coin-", "C") + "USDT"
    )
    mapping["contract_status"] = "normal"
    mapping.to_csv(session.symbol_map_path, index=False)
    return ranked


def test_backfill_planner_uses_existing_downloaders_for_only_blocked_members(
    tmp_path,
) -> None:
    from scripts.run_top50_readiness import build_backfill_commands

    commands = build_backfill_commands(
        session=_session(tmp_path),
        selection=_selection(2),
        blocked_members={"coin-2"},
        python="/venv/python",
        oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
        warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
        end=pd.Timestamp("2026-11-17", tz="UTC"),
    )

    assert len(commands) == 5
    joined = [" ".join(command) for command in commands]
    assert any(
        "download_bitget_derivatives_data.py" in command
        and "warmup" in command
        and "--types mark" in command
        for command in joined
    )
    assert any(
        "download_bitget_derivatives_data.py" in command
        and "warmup_market" in command
        and "--types market" in command
        for command in joined
    )
    assert any(
        "download_bitget_derivatives_data.py" in command
        and "--output-dir" in command
        and str(tmp_path / "data/raw/live") in command
        and "--types mark,market" in command
        for command in joined
    )
    assert all("--symbols coin-2" in command for command in joined)
    assert not any("coin-1" in command for command in joined)


def test_backfill_planner_rejects_an_unselected_member(tmp_path) -> None:
    from scripts.run_top50_readiness import build_backfill_commands

    with pytest.raises(ValueError, match="not selected"):
        build_backfill_commands(
            session=_session(tmp_path),
            selection=_selection(2),
            blocked_members={"bitcoin"},
            python="/venv/python",
            oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
            warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
            end=pd.Timestamp("2026-11-17", tz="UTC"),
        )


def test_cycle_initializes_state_without_notifications(tmp_path) -> None:
    from scripts.run_top50_readiness import run_readiness_cycle

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    commands: list[list[str]] = []
    sent: list[str] = []

    result = run_readiness_cycle(
        session=session,
        now=pd.Timestamp("2026-11-16T18:00:00Z"),
        notify=True,
        dry_run=False,
        runner=lambda command: commands.append(command) or 0,
        send_message=lambda message: sent.append(message),
        rank_fn=lambda **_kwargs: ranked,
        assess_fn=lambda **_kwargs: (_ready_payload(), set()),
    )

    assert result["initialized_now"] is True
    assert result["payload"]["ready"] is True
    assert sent == []
    assert commands == []
    assert session.state_path.is_file()
    assert (session.reports_dir / "latest_ready.json").is_file()


def test_cycle_notifies_only_a_new_top50_member_after_baseline(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import write_state
    from scripts.run_top50_readiness import run_readiness_cycle

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    previous = _ready_payload()
    previous["members"] = previous["members"][:-1]
    write_state(
        session.state_path,
        {
            "version": 1,
            "initialized": True,
            "members": [item["coin_id"] for item in previous["members"]],
            "top20": [item["coin_id"] for item in previous["top20"]],
            "member_status": {
                item["coin_id"]: item["status"] for item in previous["members"]
            },
            "notifications": {"sent_keys": {}, "pending": {}},
        },
    )
    sent: list[str] = []

    result = run_readiness_cycle(
        session=session,
        now=pd.Timestamp("2026-11-16T18:00:00Z"),
        notify=True,
        dry_run=False,
        runner=lambda _command: 0,
        send_message=lambda message: sent.append(message),
        rank_fn=lambda **_kwargs: ranked,
        assess_fn=lambda **_kwargs: (_ready_payload(), set()),
    )

    assert result["initialized_now"] is False
    assert [event["event"] for event in result["events"]] == [
        "TOP50_ENTER",
        "TOP50_DATA_READY",
    ]
    assert len(sent) == 2
    assert all("coin-50" in message for message in sent)


def test_cycle_backfills_once_then_reassesses(tmp_path) -> None:
    from scripts.run_top50_readiness import run_readiness_cycle

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    first = _ready_payload()
    first["ready"] = False
    first["members"][0]["status"] = "BLOCKED"
    first["members"][0]["failure_details"] = ["live_market: missing execution coverage"]
    assessments = [(first, {"coin-1"}), (_ready_payload(), set())]
    commands: list[list[str]] = []

    result = run_readiness_cycle(
        session=session,
        now=pd.Timestamp("2026-11-16T18:00:00Z"),
        notify=False,
        dry_run=False,
        runner=lambda command: commands.append(command) or 0,
        send_message=lambda _message: None,
        rank_fn=lambda **_kwargs: ranked,
        assess_fn=lambda **_kwargs: assessments.pop(0),
    )

    assert result["payload"]["ready"] is True
    assert len(commands) == 5
    assert not assessments


def test_cycle_no_backfill_stops_after_the_blocked_assessment(tmp_path) -> None:
    from scripts.run_top50_readiness import run_readiness_cycle

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    first = _ready_payload()
    first["ready"] = False
    first["members"][0]["status"] = "BLOCKED"
    first["members"][0]["failure_details"] = ["live_mark: missing hour"]
    commands: list[list[str]] = []

    result = run_readiness_cycle(
        session=session,
        now=pd.Timestamp("2026-11-16T18:00:00Z"),
        notify=False,
        dry_run=False,
        backfill=False,
        runner=lambda command: commands.append(command) or 0,
        send_message=lambda _message: None,
        rank_fn=lambda **_kwargs: ranked,
        assess_fn=lambda **_kwargs: (first, {"coin-1"}),
    )

    assert commands == []
    assert result["payload"]["ready"] is False
    assert result["blocked"] == ["coin-1"]
