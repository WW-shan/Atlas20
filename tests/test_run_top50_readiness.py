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
        "audit": {"passed": True, "hard_failures": [], "warnings": []},
        "input_files": {
            "panel": "sha256:" + "1" * 64,
            "metadata": "sha256:" + "2" * 64,
            "symbol_map": "sha256:" + "3" * 64,
        },
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
        warmup_members={"coin-2"},
        live_members={"coin-2"},
        python="/venv/python",
        oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
        warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
        end=pd.Timestamp("2026-11-17", tz="UTC"),
    )

    assert len(commands) == 7
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
    assert all(
        "--symbols coin-2" in command
        for command in joined
        if "merge_bitget_derivatives_shards.py" not in command
    )
    assert not any("coin-1" in command for command in joined)


def test_backfill_planner_rejects_an_unselected_member(tmp_path) -> None:
    from scripts.run_top50_readiness import build_backfill_commands

    with pytest.raises(ValueError, match="not selected"):
        build_backfill_commands(
            session=_session(tmp_path),
            selection=_selection(2),
            warmup_members={"bitcoin"},
            live_members=set(),
            python="/venv/python",
            oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
            warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
            end=pd.Timestamp("2026-11-17", tz="UTC"),
        )


def test_backfill_warmup_market_fetches_the_required_continuity_bar(
    tmp_path,
) -> None:
    from scripts.run_top50_readiness import build_backfill_commands

    commands = build_backfill_commands(
        session=_session(tmp_path),
        selection=_selection(2),
        warmup_members={"coin-2"},
        live_members=set(),
        python="/venv/python",
        oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
        warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
        end=pd.Timestamp("2026-11-17", tz="UTC"),
    )

    market_command = next(
        command
        for command in commands
        if "download_bitget_derivatives_data.py" in " ".join(command)
        and command[command.index("--types") + 1] == "market"
    )
    end_value = market_command[market_command.index("--end") + 1]
    assert end_value == "2026-09-21T01:00:00+00:00"


def test_backfill_reconciles_metadata_after_mark_gap_repairs(tmp_path) -> None:
    from scripts.run_top50_readiness import build_backfill_commands

    commands = build_backfill_commands(
        session=_session(tmp_path),
        selection=_selection(2),
        warmup_members={"coin-2"},
        live_members={"coin-2"},
        python="/venv/python",
        oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
        warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
        end=pd.Timestamp("2026-11-17", tz="UTC"),
    )

    reconcile = [
        command
        for command in commands
        if "merge_bitget_derivatives_shards.py" in " ".join(command)
    ]
    assert len(reconcile) == 2
    output_dirs = {
        command[command.index("--output-dir") + 1] for command in reconcile
    }
    assert output_dirs == {
        str(tmp_path / "data/raw/warmup"),
        str(tmp_path / "data/raw/live"),
    }
    assert commands[-1] in reconcile


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


def test_cycle_alerts_when_the_initial_baseline_is_blocked(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import load_state
    from scripts.run_top50_readiness import run_readiness_cycle

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    blocked_payload = _ready_payload()
    blocked_payload["ready"] = False
    blocked_payload["members"][0]["status"] = "BLOCKED"
    blocked_payload["members"][0]["failure_details"] = ["live_mark: missing hour"]
    blocked_payload["top20"][0]["status"] = "BLOCKED"
    blocked_payload["top20"][0]["failure_details"] = ["live_mark: missing hour"]
    sent: list[str] = []

    result = run_readiness_cycle(
        session=session,
        now=pd.Timestamp("2026-11-16T18:00:00Z"),
        notify=True,
        dry_run=False,
        runner=lambda _command: 0,
        send_message=sent.append,
        rank_fn=lambda **_kwargs: ranked,
        assess_fn=lambda **_kwargs: (blocked_payload, {"coin-1"}),
    )

    assert result["initialized_now"] is True
    assert [event["event"] for event in result["events"]] == ["TOP50_DATA_BLOCKED"]
    assert len(sent) == 1
    assert "TOP50_DATA_BLOCKED" in sent[0]
    state = load_state(session.state_path)
    assert state["notifications"]["pending"] == {}
    assert len(state["notifications"]["sent_keys"]) == 1


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
    assessment_calls: list[dict[str, object]] = []

    def assess(**kwargs):
        assessment_calls.append(kwargs)
        return assessments.pop(0)

    result = run_readiness_cycle(
        session=session,
        now=pd.Timestamp("2026-11-16T18:00:00Z"),
        notify=False,
        dry_run=False,
        runner=lambda command: commands.append(command) or 0,
        send_message=lambda _message: None,
        rank_fn=lambda **_kwargs: ranked,
        assess_fn=assess,
        now_fn=lambda: pd.Timestamp("2026-11-16T18:12:00Z"),
    )

    assert result["payload"]["ready"] is True
    assert len(commands) == 3
    assert not assessments
    assert len(assessment_calls) == 2
    assert assessment_calls[0]["now"] == pd.Timestamp("2026-11-16T18:00:00Z")
    assert assessment_calls[1]["now"] == pd.Timestamp("2026-11-16T18:12:00Z")
    assert assessment_calls[1]["latest_signal_day"] == date(2026, 11, 15)


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


def test_cycle_refuses_to_publish_an_older_as_of_than_state(tmp_path) -> None:
    from atlas20.derivatives.top50_readiness import write_state
    from scripts.run_top50_readiness import run_readiness_cycle

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    write_state(
        session.state_path,
        {
            "version": 1,
            "initialized": True,
            "last_as_of": "2026-11-15",
            "members": [f"coin-{index}" for index in range(1, 51)],
            "top20": [f"coin-{index}" for index in range(1, 21)],
            "member_status": {f"coin-{index}": "READY" for index in range(1, 51)},
            "notifications": {"sent_keys": {}, "pending": {}},
        },
    )
    old_payload = _ready_payload()
    old_payload["as_of"] = "2026-11-14"

    with pytest.raises(ValueError, match="older as_of"):
        run_readiness_cycle(
            session=session,
            now=pd.Timestamp("2026-11-15T18:00:00Z"),
            notify=False,
            dry_run=False,
            runner=lambda _command: 0,
            send_message=lambda _message: None,
            rank_fn=lambda **_kwargs: ranked,
            assess_fn=lambda **_kwargs: (old_payload, set()),
        )

    assert not (session.reports_dir / "latest.json").exists()


def test_main_refuses_a_stale_panel_without_acquiring_a_lock(tmp_path) -> None:
    from scripts.run_top50_readiness import main

    panel = tmp_path / "panel.csv"
    pd.DataFrame({"date": ["2026-11-14"], "coin_id": ["bitcoin"]}).to_csv(
        panel, index=False
    )

    with pytest.raises(SystemExit, match="panel does not carry"):
        main(
            [
                "--panel",
                str(panel),
                "--now",
                "2026-11-16T18:00:00Z",
                "--no-lock",
                "--dry-run",
            ]
        )


@pytest.mark.parametrize("dry_run", [False, True])
def test_main_skips_when_the_execution_lock_is_held(tmp_path, dry_run: bool) -> None:
    from filelock import FileLock
    from scripts.run_top50_readiness import main

    lock_path = tmp_path / "execution.lock"
    lock = FileLock(str(lock_path))
    lock.acquire(timeout=0)
    try:
        args = [
            "--lock-file",
            str(lock_path),
            "--wait-seconds",
            "0",
            "--now",
            "2026-11-16T18:00:00Z",
        ]
        if dry_run:
            args.append("--dry-run")
        code = main(args)
    finally:
        lock.release()

    assert code == 0


def test_notify_only_reports_failure_when_the_execution_lock_is_held(tmp_path) -> None:
    from filelock import FileLock
    from scripts.run_top50_readiness import main

    lock_path = tmp_path / "execution.lock"
    lock = FileLock(str(lock_path))
    lock.acquire(timeout=0)
    try:
        code = main(
            [
                "--notify-only",
                "--lock-file",
                str(lock_path),
                "--wait-seconds",
                "0",
                "--now",
                "2026-11-16T18:00:00Z",
            ]
        )
    finally:
        lock.release()

    assert code == 1


def test_notify_reports_failure_when_the_execution_lock_is_held(tmp_path) -> None:
    from filelock import FileLock
    from scripts.run_top50_readiness import main

    lock_path = tmp_path / "execution.lock"
    lock = FileLock(str(lock_path))
    lock.acquire(timeout=0)
    try:
        code = main(
            [
                "--notify",
                "--lock-file",
                str(lock_path),
                "--wait-seconds",
                "0",
                "--now",
                "2026-11-16T18:00:00Z",
            ]
        )
    finally:
        lock.release()

    assert code == 1


def test_backfill_planner_live_only_does_not_rebuild_warmup(tmp_path) -> None:
    from scripts.run_top50_readiness import build_backfill_commands

    commands = build_backfill_commands(
        session=_session(tmp_path),
        selection=_selection(2),
        warmup_members=set(),
        live_members={"coin-2"},
        python="/venv/python",
        oos_start=pd.Timestamp("2026-09-01", tz="UTC"),
        warmup_end=pd.Timestamp("2026-09-21", tz="UTC"),
        end=pd.Timestamp("2026-11-17", tz="UTC"),
    )

    assert len(commands) == 3
    assert all("warmup" not in " ".join(command) for command in commands)
    assert all(
        "--symbols coin-2" in " ".join(command)
        for command in commands
        if "merge_bitget_derivatives_shards.py" not in " ".join(command)
    )


def test_backfill_scope_treats_audit_funding_failure_as_live() -> None:
    from scripts.run_top50_readiness import _backfill_scopes

    payload = {
        "members": [
            {
                "coin_id": "coin-2",
                "failure_details": [
                    "audit: funding.coin-2.settlement_coverage: "
                    "missing 1 expected settlement(s)"
                ],
            }
        ]
    }

    warmup, live = _backfill_scopes(payload, {"coin-2"})

    assert warmup == set()
    assert live == {"coin-2"}


def test_cycle_backfills_live_for_structured_funding_failure(tmp_path) -> None:
    from scripts.run_top50_readiness import run_readiness_cycle

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    first = _ready_payload()
    first["ready"] = False
    first["members"][0]["status"] = "BLOCKED"
    first["members"][0]["failure_details"] = []
    first["members"][0]["funding"] = {
        "failures": ["funding ends before 2026-11-16T00:00:00Z"],
        "warnings": [],
    }
    assessments = [(first, {"coin-1"}), (_ready_payload(), set())]
    commands: list[list[str]] = []

    run_readiness_cycle(
        session=session,
        now=pd.Timestamp("2026-11-16T18:00:00Z"),
        notify=False,
        dry_run=False,
        runner=lambda command: commands.append(command) or 0,
        send_message=lambda _message: None,
        rank_fn=lambda **_kwargs: ranked,
        assess_fn=lambda **_kwargs: assessments.pop(0),
    )

    assert len(commands) == 3
    assert all("warmup" not in " ".join(command) for command in commands)


@pytest.mark.parametrize(
    ("failure_mode", "expected_message"),
    [("nonzero", "failed \\(1\\)"), ("raises", "raised RuntimeError: boom")],
)
def test_cycle_publishes_blocked_alert_before_raising_backfill_failure(
    tmp_path, failure_mode: str, expected_message: str
) -> None:
    import json
    from scripts.run_top50_readiness import run_readiness_cycle
    from atlas20.derivatives.top50_readiness import write_state

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    write_state(
        session.state_path,
        {
            "version": 1,
            "initialized": True,
            "members": [],
            "top20": [],
            "member_status": {},
            "notifications": {"sent_keys": {}, "pending": {}},
        },
    )
    first = _ready_payload()
    first["ready"] = False
    first["members"][0]["status"] = "BLOCKED"
    first["members"][0]["failure_details"] = []
    first["members"][0]["live_market"] = {
        "failures": ["missing market execution coverage"],
        "warnings": [],
    }
    assessments = [(first, {"coin-1"})]
    sent: list[str] = []

    def runner(_command: list[str]) -> int:
        if failure_mode == "raises":
            raise RuntimeError("boom")
        return 1

    with pytest.raises(RuntimeError, match=expected_message):
        run_readiness_cycle(
            session=session,
            now=pd.Timestamp("2026-11-16T18:00:00Z"),
            notify=True,
            dry_run=False,
            runner=runner,
            send_message=lambda message: sent.append(message),
            rank_fn=lambda **_kwargs: ranked,
            assess_fn=lambda **_kwargs: assessments.pop(0),
        )

    report = json.loads((session.reports_dir / "latest.json").read_text())
    assert report["ready"] is False
    assert report["members"][0]["status"] == "BLOCKED"
    assert report["top20"][0]["status"] == "BLOCKED"
    assert any(
        "backfill command" in detail
        for detail in report["members"][0]["failure_details"]
    )
    assert any(
        "backfill command" in detail
        for detail in report["top20"][0]["failure_details"]
    )
    assert session.state_path.is_file()
    assert any("TOP50_DATA_BLOCKED" in message for message in sent)
    assert not assessments


def test_notify_only_sends_pending_events_without_touching_market_data(
    tmp_path, monkeypatch
) -> None:
    import scripts.run_top50_readiness as runner
    from atlas20.derivatives.top50_readiness import load_state, write_state

    state_path = tmp_path / "top50-state.json"
    event = {
        "event": "TOP50_DATA_BLOCKED",
        "coin_id": "coin-1",
        "symbol": "C1",
        "as_of": "2026-11-15",
        "status": "BLOCKED",
        "details": "missing live market",
        "key": "TOP50_DATA_BLOCKED|coin-1|2026-11-15",
    }
    write_state(
        state_path,
        {
            "version": 1,
            "initialized": True,
            "members": ["coin-1"],
            "top20": [],
            "member_status": {"coin-1": "BLOCKED"},
            "notifications": {"sent_keys": {}, "pending": {event["key"]: event}},
        },
    )
    sent: list[str] = []
    monkeypatch.setattr(runner, "_send_telegram", lambda message, **_kwargs: sent.append(message))

    code = runner.main(
        [
            "--notify-only",
            "--no-lock",
            "--state-file",
            str(state_path),
            "--now",
            "2026-11-16T18:00:00Z",
        ]
    )

    assert code == 0
    assert len(sent) == 1
    state = load_state(state_path)
    assert state["notifications"]["pending"] == {}
    assert event["key"] in state["notifications"]["sent_keys"]


def test_pending_notifications_are_delivered_in_human_event_order() -> None:
    from scripts.run_top50_readiness import _deliver_pending_notifications

    events = {
        "TOP20_ENTER|coin-1|2026-11-15": "TOP20_ENTER",
        "TOP50_DATA_READY|coin-1|2026-11-15": "TOP50_DATA_READY",
        "TOP50_ENTER|coin-1|2026-11-15": "TOP50_ENTER",
    }
    pending = {
        key: {
            "event": event,
            "coin_id": "coin-1",
            "symbol": "C1",
            "as_of": "2026-11-15",
            "status": "READY",
            "details": "",
            "key": key,
        }
        for key, event in events.items()
    }
    state = {
        "version": 1,
        "notifications": {"sent_keys": {}, "pending": pending},
    }
    sent: list[str] = []

    failures = _deliver_pending_notifications(
        state=state,
        moment=pd.Timestamp("2026-11-16T18:00:00Z"),
        send_message=sent.append,
    )

    assert failures == []
    assert [message.splitlines()[0] for message in sent] == [
        "Atlas20 Top50 TOP50_ENTER",
        "Atlas20 Top50 TOP50_DATA_READY",
        "Atlas20 Top50 TOP20_ENTER",
    ]


def test_check_current_requires_todays_50_50_ready_pointer(tmp_path) -> None:
    import json
    from scripts.run_top50_readiness import main
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    reports = tmp_path / "reports"
    payload = _ready_payload()
    publish_readiness_payload(
        reports_dir=reports,
        payload=payload,
        audit_payload={"passed": True},
    )

    code = main(
        [
            "--check-current",
            "--reports-dir",
            str(reports),
            "--now",
            "2026-11-16T18:00:00Z",
        ]
    )
    assert code == 0

    stale = {**payload, "as_of": "2026-11-14"}
    stale["fingerprint"] = ""
    (reports / "latest_ready.json").write_text(json.dumps(stale), encoding="utf-8")
    code = main(
        [
            "--check-current",
            "--reports-dir",
            str(reports),
            "--now",
            "2026-11-16T18:00:00Z",
        ]
    )
    assert code == 1


def test_check_current_rejects_a_self_consistent_but_invalid_top20(tmp_path) -> None:
    import json
    from scripts.run_top50_readiness import main
    from atlas20.derivatives.top50_readiness import (
        _payload_fingerprint,
        publish_readiness_payload,
    )

    reports = tmp_path / "reports"
    publish_readiness_payload(
        reports_dir=reports,
        payload=_ready_payload(),
        audit_payload={"passed": True},
    )
    ready_path = reports / "latest_ready.json"
    payload = json.loads(ready_path.read_text())
    payload["top20"][0]["coin_id"] = "not-selected"
    payload["fingerprint"] = _payload_fingerprint(payload)
    ready_path.write_text(json.dumps(payload), encoding="utf-8")

    code = main(
        [
            "--check-current",
            "--reports-dir",
            str(reports),
            "--now",
            "2026-11-16T18:00:00Z",
        ]
    )

    assert code == 1


def test_check_current_rejects_a_ready_pointer_that_disagrees_with_latest(
    tmp_path,
) -> None:
    import json
    from scripts.run_top50_readiness import main
    from atlas20.derivatives.top50_readiness import (
        _payload_fingerprint,
        publish_readiness_payload,
    )

    reports = tmp_path / "reports"
    publish_readiness_payload(
        reports_dir=reports,
        payload=_ready_payload(),
        audit_payload={"passed": True},
    )
    blocked = _ready_payload()
    blocked["ready"] = False
    blocked["members"][0]["status"] = "BLOCKED"
    blocked["fingerprint"] = _payload_fingerprint(blocked)
    (reports / "latest.json").write_text(json.dumps(blocked), encoding="utf-8")

    code = main(
        [
            "--check-current",
            "--reports-dir",
            str(reports),
            "--now",
            "2026-11-16T18:00:00Z",
        ]
    )

    assert code == 1


def test_reassessment_exception_publishes_blocked_before_raising(tmp_path) -> None:
    import json
    from scripts.run_top50_readiness import run_readiness_cycle

    session = _session(tmp_path)
    ranked = _write_rank_inputs(session)
    first = _ready_payload()
    first["ready"] = False
    first["members"][0]["status"] = "BLOCKED"
    first["members"][0]["failure_details"] = []
    first["members"][0]["live_market"] = {
        "failures": ["missing market execution coverage"],
        "warnings": [],
    }
    calls = 0

    def assess(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return first, {"coin-1"}
        raise RuntimeError("audit exploded")

    with pytest.raises(RuntimeError, match="reassessment raised RuntimeError"):
        run_readiness_cycle(
            session=session,
            now=pd.Timestamp("2026-11-16T18:00:00Z"),
            notify=False,
            dry_run=False,
            runner=lambda _command: 0,
            send_message=lambda _message: None,
            rank_fn=lambda **_kwargs: ranked,
            assess_fn=assess,
            now_fn=lambda: pd.Timestamp("2026-11-16T18:10:00Z"),
        )

    report = json.loads((session.reports_dir / "latest.json").read_text())
    assert report["ready"] is False
    assert report["members"][0]["status"] == "BLOCKED"
    assert any(
        "reassessment raised RuntimeError: audit exploded" in item
        for item in report["members"][0]["failure_details"]
    )
    assert session.state_path.is_file()


def test_main_sends_a_global_alert_when_readiness_aborts(monkeypatch) -> None:
    import scripts.run_top50_readiness as runner

    monkeypatch.setattr(
        runner,
        "panel_lags_last_completed_day",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        runner,
        "run_readiness_cycle",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("rank exploded")),
    )
    sent: list[str] = []
    monkeypatch.setattr(
        runner,
        "_send_telegram",
        lambda message, **_kwargs: sent.append(message),
    )

    with pytest.raises(RuntimeError, match="rank exploded"):
        runner.main(
            [
                "--notify",
                "--dry-run",
                "--no-lock",
                "--now",
                "2026-11-16T18:00:00Z",
            ]
        )

    assert len(sent) == 1
    assert "Top50 readiness ERROR" in sent[0]
    assert "rank exploded" in sent[0]
