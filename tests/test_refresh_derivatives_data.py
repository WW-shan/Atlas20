from __future__ import annotations

import fcntl
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from scripts import refresh_derivatives_data


RECEIPT_TEST_NOW = datetime(2026, 11, 14, 1, 4, tzinfo=timezone.utc)
RECEIPT_TEST_PREPARED_AT = "2026-11-14T01:00:00+00:00"


def test_refresh_commands_are_profile_bound_and_never_trade(tmp_path: Path) -> None:
    commands = refresh_derivatives_data.build_refresh_commands(
        make_command="/usr/bin/make",
        project_root=tmp_path,
        include_top50_readiness=True,
    )

    assert commands == [
        ["/usr/bin/make", "derivatives-live-data"],
        ["/usr/bin/make", "top50-readiness-unlocked"],
        ["/usr/bin/make", "top50-readiness-check"],
        ["/usr/bin/make", "derivatives-ls104-signal"],
        ["/usr/bin/make", "audit-data-chain"],
        ["/usr/bin/make", "audit-data-ls104"],
        ["/usr/bin/make", "audit-symbols-ls104"],
        ["/usr/bin/make", "audit-contract-specs-ls104"],
        ["/usr/bin/make", "audit-signal-ls104"],
    ]
    assert not any("execute_live_plan.py" in " ".join(command) for command in commands)
    assert not any("derivatives-notify" in " ".join(command) for command in commands)


def test_execution_required_mark_time_targets_the_upcoming_execution_bar() -> None:
    required = refresh_derivatives_data.execution_required_mark_time(
        {
            "signal_end_date": "2026-11-19",
            "execution_utc": "01:05",
        }
    )

    assert required == pd.Timestamp("2026-11-20T00:00:00Z")


def test_finalize_default_mark_wait_leaves_time_for_the_0105_audits() -> None:
    args = refresh_derivatives_data._parse_args(["--finalize-execution"])

    assert args.mark_wait_seconds == 120.0
    assert args.mark_poll_seconds == 15.0


def test_intraday_refresh_does_not_rebuild_the_daily_top50(tmp_path: Path) -> None:
    commands = refresh_derivatives_data.build_refresh_commands(
        make_command="/usr/bin/make",
        project_root=tmp_path,
        include_top50_readiness=False,
    )

    assert ["/usr/bin/make", "top50-readiness-unlocked"] not in commands
    assert ["/usr/bin/make", "top50-readiness-check"] in commands
    assert commands.index(["/usr/bin/make", "top50-readiness-check"]) < commands.index(
        ["/usr/bin/make", "derivatives-ls104-signal"]
    )
    assert commands[0] == ["/usr/bin/make", "derivatives-live-data"]
    assert ["/usr/bin/make", "derivatives-ls104-signal"] in commands


def test_refresh_dry_run_does_not_start_make(tmp_path: Path, monkeypatch) -> None:
    called = False

    def fail_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("dry-run must not execute make")

    monkeypatch.setattr(refresh_derivatives_data.subprocess, "run", fail_run)

    code = refresh_derivatives_data.main(
        [
            "--dry-run",
            "--project-root",
            str(tmp_path),
            "--lock-file",
            str(tmp_path / "execution.lock"),
        ]
    )

    assert code == 0
    assert called is False


def test_refresh_skips_when_the_execution_lock_is_held(
    tmp_path: Path, monkeypatch
) -> None:
    lock_path = tmp_path / "execution.lock"
    handle = lock_path.open("a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    called = False

    def fail_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("a busy execution lock must skip refresh")

    monkeypatch.setattr(refresh_derivatives_data.subprocess, "run", fail_run)

    try:
        code = refresh_derivatives_data.main(
            [
                "--project-root",
                str(tmp_path),
                "--lock-file",
                str(lock_path),
                "--execution-lock-wait-seconds",
                "0",
                "--skip-panel-wait",
            ]
        )
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

    assert code == 0
    assert called is False


def test_fresh_receipt_short_circuits_before_the_pre_execution_cutoff(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        refresh_derivatives_data,
        "check_prepare_receipt",
        lambda **_kwargs: (True, "prepare receipt is valid (1.0m old)"),
    )

    def fail_if_cutoff_is_evaluated(_args):
        raise AssertionError("a fresh receipt must be checked before the cut-off")

    monkeypatch.setattr(
        refresh_derivatives_data,
        "_pre_execution_too_late",
        fail_if_cutoff_is_evaluated,
    )

    code = refresh_derivatives_data.main(
        [
            "--skip-if-fresh-receipt",
            "--pre-execution",
            "--project-root",
            str(tmp_path),
            "--lock-file",
            str(tmp_path / "execution.lock"),
        ]
    )

    assert code == 0


def test_check_lock_distinguishes_busy_and_free(tmp_path: Path) -> None:
    lock_path = tmp_path / "execution.lock"
    handle = lock_path.open("a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert (
            refresh_derivatives_data.main(
                [
                    "--check-lock",
                    "--lock-file",
                    str(lock_path),
                    "--project-root",
                    str(tmp_path),
                ]
            )
            == 3
        )
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

    assert (
        refresh_derivatives_data.main(
            [
                "--check-lock",
                "--lock-file",
                str(lock_path),
                "--project-root",
                str(tmp_path),
            ]
        )
        == 0
    )


def test_prepare_receipt_validates_manifest_and_audit_files(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "reports" / "ls45_live_g175" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    payload = {
        "targets_sha256": "target-a",
        "data_fingerprint": "sha256:data",
        "fill_price_source": "bitget_market_1h_open",
        "market_fill_fingerprint": "sha256:fills",
        "execution_price_model": "market_1h_open_floor",
        "signal_end_date": "2026-11-14",
        "last_mark": "2026-11-13 23:00:00+00:00",
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    audits = {}
    for name in refresh_derivatives_data.AUDIT_FILE_NAMES:
        audit = tmp_path / name
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text("{}", encoding="utf-8")
        audits[name] = refresh_derivatives_data._sha256(audit)
    receipt = tmp_path / "prepared.json"
    receipt.write_text(
        json.dumps(
            {
                **payload,
                "prepared_at": RECEIPT_TEST_PREPARED_AT,
                "track": refresh_derivatives_data.RECEIPT_TRACK,
                "manifest_path": str(manifest),
                "manifest_sha256": refresh_derivatives_data._sha256(manifest),
                "audit_files": audits,
            }
        ),
        encoding="utf-8",
    )

    valid, reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=RECEIPT_TEST_NOW,
    )

    assert valid is True, reason


def test_prepare_receipt_rejects_the_pre_execution_mark_after_the_fill_boundary(
    tmp_path: Path,
) -> None:
    """A receipt prepared before 01:05 cannot prove the 00:00 execution bar."""

    import json

    manifest = tmp_path / "reports" / "ls45_live_g175" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    payload = {
        "targets_sha256": "target-a",
        "data_fingerprint": "sha256:data",
        "fill_price_source": "bitget_market_1h_open",
        "market_fill_fingerprint": "sha256:fills",
        "execution_price_model": "market_1h_open_floor",
        "signal_end_date": "2026-11-14",
        "last_mark": "2026-11-13 23:00:00+00:00",
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    audits = {}
    for name in refresh_derivatives_data.AUDIT_FILE_NAMES:
        audit = tmp_path / name
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text("{}", encoding="utf-8")
        audits[name] = refresh_derivatives_data._sha256(audit)
    receipt = tmp_path / "prepared.json"
    receipt.write_text(
        json.dumps(
            {
                **payload,
                "prepared_at": "2026-11-14T00:55:00+00:00",
                "track": refresh_derivatives_data.RECEIPT_TRACK,
                "manifest_path": str(manifest),
                "manifest_sha256": refresh_derivatives_data._sha256(manifest),
                "audit_files": audits,
            }
        ),
        encoding="utf-8",
    )

    before_fill, before_reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=datetime(2026, 11, 14, 1, 4, tzinfo=timezone.utc),
    )
    at_fill, at_fill_reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc),
    )
    finalize_base, finalize_reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=datetime(2026, 11, 14, 1, 5, tzinfo=timezone.utc),
        require_current_mark=False,
    )

    assert before_fill is True, before_reason
    assert at_fill is False
    assert "last_mark" in at_fill_reason
    assert "2026-11-14T00:00:00" in at_fill_reason
    assert finalize_base is True, finalize_reason


def test_finalize_execution_fetches_only_the_required_mark_tail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import json

    project = tmp_path / "project"
    manifest_path = project / "reports" / "ls45_live_g175" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    targets_path = project / "reports" / "ls45_live_g175" / "oos_targets.csv"
    targets_path.write_text("signal_date,asset,target_weight\n2026-11-13,x,0\n", encoding="utf-8")
    audit_names = refresh_derivatives_data.AUDIT_FILE_NAMES
    audits = {}
    for name in audit_names:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        audits[name] = refresh_derivatives_data._sha256(path)
    payload = {
        "targets_sha256": refresh_derivatives_data._sha256(targets_path),
        "data_fingerprint": "sha256:old-data",
        "fill_price_source": "bitget_market_1h_open",
        "market_fill_fingerprint": "sha256:fills",
        "execution_price_model": "market_1h_open_floor",
        "signal_end_date": "2026-11-13",
        "last_mark": "2026-11-12T23:00:00+00:00",
        "raw_dir": str(tmp_path / "raw"),
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    receipt_path = project / "reports" / "ls45_live_g175_live" / "prepared.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(
            {
                **payload,
                "prepared_at": RECEIPT_TEST_PREPARED_AT,
                "track": refresh_derivatives_data.RECEIPT_TRACK,
                "manifest_path": str(manifest_path),
                "manifest_sha256": refresh_derivatives_data._sha256(manifest_path),
                "audit_files": audits,
            }
        ),
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_run(command, *, project_root):
        del project_root
        command = list(command)
        commands.append(command)
        script = command[1]
        if script.endswith("audit_derivatives_data.py"):
            audit = {
                "passed": True,
                "hard_failures": [],
                "warnings": [],
                "provenance": {"fingerprint": "sha256:new-data"},
                "summary": {"last_mark": "2026-11-14T00:00:00+00:00"},
            }
            (project / "reports" / "ls45_live_g175" / "data_audit.json").write_text(
                json.dumps(audit), encoding="utf-8"
            )
        elif script.endswith("audit_signal_equivalence.py"):
            (project / "reports" / "ls45_live_g175_live" / "signal_equivalence.json").write_text(
                json.dumps({"passed": True}), encoding="utf-8"
            )
        return 0

    monkeypatch.setattr(refresh_derivatives_data, "_run_checked", fake_run)
    args = SimpleNamespace(
        receipt_out=receipt_path,
        max_age_minutes=30.0,
        execution_lock_wait_seconds=0.1,
        mark_wait_seconds=120.0,
        mark_poll_seconds=15.0,
    )

    code = refresh_derivatives_data._finalize_execution(
        args,
        project_root=project,
        lock_path=project / "data" / "execution.lock",
        now=RECEIPT_TEST_NOW,
    )

    assert code == 0
    assert any(
        "--mark-tail-only" in command
        and "--skip-funding" in command
        and "--required-mark-time" in command
        and command[command.index("--required-mark-time") + 1]
        == "2026-11-14T00:00:00+00:00"
        for command in commands
    )
    assert not any("run_ls45_live_signal.py" in " ".join(command) for command in commands)
    updated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated_manifest["last_mark"] == "2026-11-14T00:00:00+00:00"
    assert updated_manifest["data_fingerprint"] == "sha256:new-data"
    updated_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert updated_receipt["last_mark"] == "2026-11-14T00:00:00+00:00"
    assert updated_receipt["data_fingerprint"] == "sha256:new-data"


def test_prepare_receipt_rejects_a_changed_top50_ready_pointer(
    tmp_path: Path,
) -> None:
    import hashlib
    import json

    manifest = tmp_path / "reports" / "ls45_live_g175" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    ready = tmp_path / "reports" / "top50_data_readiness" / "latest_ready.json"
    ready.parent.mkdir(parents=True)
    ready.write_text(
        json.dumps(
            {
                "ready": True,
                "as_of": "2026-11-14",
                "fingerprint": "sha256:" + "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    ready_sha = hashlib.sha256(ready.read_bytes()).hexdigest()
    executable_universe = {
        "as_of": "2026-11-14",
        "fingerprint": "sha256:" + "a" * 64,
        "source_sha256": "sha256:" + ready_sha,
        "input_files": {},
        "members": [],
        "skipped": [],
    }
    payload = {
        "targets_sha256": "target-a",
        "data_fingerprint": "sha256:data",
        "fill_price_source": "bitget_market_1h_open",
        "market_fill_fingerprint": "sha256:fills",
        "execution_price_model": "market_1h_open_floor",
        "signal_end_date": "2026-11-14",
        "last_mark": "2026-11-13 23:00:00+00:00",
        "executable_universe": executable_universe,
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    audits = {}
    for name in refresh_derivatives_data.AUDIT_FILE_NAMES:
        audit = tmp_path / name
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text("{}", encoding="utf-8")
        audits[name] = refresh_derivatives_data._sha256(audit)
    receipt = tmp_path / "prepared.json"
    receipt.write_text(
        json.dumps(
            {
                **payload,
                "prepared_at": RECEIPT_TEST_PREPARED_AT,
                "track": refresh_derivatives_data.RECEIPT_TRACK,
                "manifest_path": str(manifest),
                "manifest_sha256": refresh_derivatives_data._sha256(manifest),
                "audit_files": audits,
            }
        ),
        encoding="utf-8",
    )

    valid, _reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=RECEIPT_TEST_NOW,
    )
    assert valid is True

    ready.write_text(
        json.dumps(
            {
                "ready": True,
                "as_of": "2026-11-14",
                "fingerprint": "sha256:" + "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    valid, reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=RECEIPT_TEST_NOW,
    )

    assert valid is False
    assert "ready pointer" in reason.lower() or "readiness" in reason.lower()


def test_prepare_receipt_rejects_a_changed_manifest(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "reports" / "ls45_live_g175" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    payload = {
        "targets_sha256": "target-a",
        "data_fingerprint": "sha256:data",
        "fill_price_source": "bitget_market_1h_open",
        "market_fill_fingerprint": "sha256:fills",
        "execution_price_model": "market_1h_open_floor",
        "signal_end_date": "2026-11-14",
        "last_mark": "2026-11-13 23:00:00+00:00",
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    receipt = tmp_path / "prepared.json"
    receipt.write_text(
        json.dumps(
            {
                **payload,
                "prepared_at": RECEIPT_TEST_PREPARED_AT,
                "track": refresh_derivatives_data.RECEIPT_TRACK,
                "manifest_path": str(manifest),
                "manifest_sha256": refresh_derivatives_data._sha256(manifest),
                "audit_files": {},
            }
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps({**payload, "targets_sha256": "target-b"}), encoding="utf-8"
    )

    valid, reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=RECEIPT_TEST_NOW,
    )

    assert valid is False
    assert "manifest hash" in reason or "targets_sha256" in reason


def test_prepare_receipt_rejects_missing_audit_commitments(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "reports" / "ls45_live_g175" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    payload = {
        "targets_sha256": "target-a",
        "data_fingerprint": "sha256:data",
        "fill_price_source": "bitget_market_1h_open",
        "market_fill_fingerprint": "sha256:fills",
        "execution_price_model": "market_1h_open_floor",
        "signal_end_date": "2026-11-14",
        "last_mark": "2026-11-13 23:00:00+00:00",
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    receipt = tmp_path / "prepared.json"
    receipt.write_text(
        json.dumps(
            {
                **payload,
                "prepared_at": RECEIPT_TEST_PREPARED_AT,
                "track": refresh_derivatives_data.RECEIPT_TRACK,
                "manifest_path": str(manifest),
                "manifest_sha256": refresh_derivatives_data._sha256(manifest),
                "audit_files": {},
            }
        ),
        encoding="utf-8",
    )

    valid, reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=RECEIPT_TEST_NOW,
    )

    assert valid is False
    assert "audit_files are incomplete" in reason


def test_prepare_receipt_rejects_nonfinite_max_age(tmp_path: Path) -> None:
    valid, reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=tmp_path / "prepared.json",
        manifest_path=tmp_path / "manifest.json",
        max_age_minutes=float("nan"),
        project_root=tmp_path,
    )

    assert valid is False
    assert "max age" in reason


def test_prepare_receipt_reports_a_corrupt_manifest(tmp_path: Path) -> None:
    import json

    manifest = tmp_path / "reports" / "ls45_live_g175" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{not-json", encoding="utf-8")
    receipt = tmp_path / "prepared.json"
    receipt.write_text(
        json.dumps(
            {
                "prepared_at": RECEIPT_TEST_PREPARED_AT,
                "track": refresh_derivatives_data.RECEIPT_TRACK,
                "manifest_path": str(manifest),
            }
        ),
        encoding="utf-8",
    )

    valid, reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
        now=RECEIPT_TEST_NOW,
    )

    assert valid is False
    assert "manifest unreadable" in reason


def test_wait_for_current_panel_accepts_the_latest_completed_day(
    tmp_path: Path,
) -> None:
    from datetime import datetime, timezone
    import pandas as pd

    panel = tmp_path / "panel.csv"
    pd.DataFrame({"date": ["2026-11-14", "2026-11-15"]}).to_csv(panel, index=False)

    ok, reason = refresh_derivatives_data.wait_for_current_panel(
        panel_path=panel,
        lock_path=tmp_path / "panel.lock",
        wait_seconds=0.1,
        now=datetime(2026, 11, 16, 0, 10, tzinfo=timezone.utc),
    )

    assert ok is True, reason


def test_wait_for_current_panel_refuses_a_stale_panel(tmp_path: Path) -> None:
    from datetime import datetime, timezone
    import pandas as pd

    panel = tmp_path / "panel.csv"
    pd.DataFrame({"date": ["2026-11-14"]}).to_csv(panel, index=False)

    ok, reason = refresh_derivatives_data.wait_for_current_panel(
        panel_path=panel,
        lock_path=tmp_path / "panel.lock",
        wait_seconds=0.01,
        now=datetime(2026, 11, 16, 0, 10, tzinfo=timezone.utc),
    )

    assert ok is False
    assert "did not reach" in reason
