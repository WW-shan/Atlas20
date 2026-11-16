from __future__ import annotations

import fcntl
from pathlib import Path

from scripts import refresh_derivatives_data


def test_refresh_commands_are_profile_bound_and_never_trade(tmp_path: Path) -> None:
    commands = refresh_derivatives_data.build_refresh_commands(
        make_command="/usr/bin/make",
        project_root=tmp_path,
    )

    assert commands == [
        ["/usr/bin/make", "derivatives-live-data", "derivatives-ls104-signal"],
        ["/usr/bin/make", "audit-data-chain"],
        ["/usr/bin/make", "audit-data-ls104"],
        ["/usr/bin/make", "audit-symbols-ls104"],
        ["/usr/bin/make", "audit-contract-specs-ls104"],
        ["/usr/bin/make", "audit-signal-ls104"],
    ]
    assert not any("execute_live_plan.py" in " ".join(command) for command in commands)
    assert not any("derivatives-notify" in " ".join(command) for command in commands)


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
    from datetime import datetime, timezone

    manifest = tmp_path / "reports" / "ls45_live_g175" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    payload = {
        "targets_sha256": "target-a",
        "data_fingerprint": "sha256:data",
        "fill_price_source": "bitget_market_1h_open",
        "market_fill_fingerprint": "sha256:fills",
        "execution_price_model": "market_1h_open_floor",
        "signal_end_date": "2026-11-14",
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    audit = tmp_path / "reports" / "ls45_live_g175" / "data_audit.json"
    audit.write_text("{}", encoding="utf-8")
    receipt = tmp_path / "prepared.json"
    receipt.write_text(
        json.dumps(
            {
                **payload,
                "prepared_at": datetime.now(timezone.utc).isoformat(),
                "manifest_sha256": refresh_derivatives_data._sha256(manifest),
                "audit_files": {
                    "reports/ls45_live_g175/data_audit.json": refresh_derivatives_data._sha256(
                        audit
                    )
                },
            }
        ),
        encoding="utf-8",
    )

    valid, reason = refresh_derivatives_data.check_prepare_receipt(
        receipt_path=receipt,
        manifest_path=manifest,
        max_age_minutes=30.0,
        project_root=tmp_path,
    )

    assert valid is True, reason


def test_prepare_receipt_rejects_a_changed_manifest(tmp_path: Path) -> None:
    import json
    from datetime import datetime, timezone

    manifest = tmp_path / "reports" / "ls45_live_g175" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    payload = {"targets_sha256": "target-a", "data_fingerprint": "sha256:data"}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    receipt = tmp_path / "prepared.json"
    receipt.write_text(
        json.dumps(
            {
                **payload,
                "prepared_at": datetime.now(timezone.utc).isoformat(),
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
    )

    assert valid is False
    assert "manifest hash" in reason or "targets_sha256" in reason


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
