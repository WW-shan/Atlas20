"""The wrapper's preflight CLI must block or allow for the documented reasons.

Exit code 0 means "go", exit code 3 means "a documented reason says do not
trade".  The wrapper skips quietly on 3 and lets anything else abort the job,
so a crash can never be mistaken for a deliberate skip.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.live_chain_preflight import BLOCKED, main


def _write_panel(
    path: Path,
    days: list[str],
    *,
    last_volume_factor: float = 1.0,
    assets: int = 20,
) -> Path:
    rows = []
    for day in days:
        factor = last_volume_factor if day == days[-1] else 1.0
        for index in range(assets):
            rows.append(
                {
                    "date": day,
                    "coin_id": f"coin-{index}",
                    "volume_usd": 100.0 * factor,
                    "market_cap": 1_000.0,
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _write_state(path: Path, key: str, status: str) -> Path:
    path.write_text(json.dumps({"last_key": key, "last_status": status}), encoding="utf-8")
    return path


def test_panel_check_blocks_when_the_panel_lags(tmp_path: Path) -> None:
    panel = _write_panel(tmp_path / "panel.csv", ["2026-10-13", "2026-10-14"])

    code = main(["--check", "panel", "--panel", str(panel), "--now", "2026-10-16T03:05:00+00:00"])

    assert code == BLOCKED


def test_panel_check_allows_when_the_panel_is_current(tmp_path: Path) -> None:
    panel = _write_panel(
        tmp_path / "panel.csv",
        [f"2026-10-{day:02d}" for day in range(8, 16)],
    )

    code = main(["--check", "panel", "--panel", str(panel), "--now", "2026-10-16T03:05:00+00:00"])

    assert code == 0


def test_panel_check_blocks_a_partial_last_day(tmp_path: Path) -> None:
    panel = _write_panel(
        tmp_path / "panel.csv",
        [f"2026-10-{day:02d}" for day in range(8, 16)],
        last_volume_factor=0.3,
    )

    code = main(["--check", "panel", "--panel", str(panel), "--now", "2026-10-16T03:05:00+00:00"])

    assert code == BLOCKED


def test_panel_check_blocks_a_narrow_panel(tmp_path: Path) -> None:
    panel = _write_panel(
        tmp_path / "panel.csv",
        [f"2026-10-{day:02d}" for day in range(8, 16)],
        assets=10,
    )

    code = main(["--check", "panel", "--panel", str(panel), "--now", "2026-10-16T03:05:00+00:00"])

    assert code == BLOCKED


def test_window_check_blocks_before_the_fill_point(tmp_path: Path) -> None:
    state = _write_state(tmp_path / "state.json", "spec|2026-10-14|2026-10-15", "ok")

    code = main(["--check", "window", "--state-file", str(state), "--now", "2026-10-16T01:04:00+00:00"])

    assert code == BLOCKED


def test_window_check_allows_a_reboot_catchup_after_the_fill_point(tmp_path: Path) -> None:
    state = _write_state(tmp_path / "state.json", "spec|2026-10-14|2026-10-15", "ok")

    code = main(["--check", "window", "--state-file", str(state), "--now", "2026-10-16T04:00:00+00:00"])

    assert code == 0


def test_window_check_blocks_when_today_already_traded(tmp_path: Path) -> None:
    state = _write_state(tmp_path / "state.json", "spec|2026-10-15|2026-10-16", "ok")

    code = main(["--check", "window", "--state-file", str(state), "--now", "2026-10-16T04:00:00+00:00"])

    assert code == BLOCKED


def test_window_check_retries_a_failed_day(tmp_path: Path) -> None:
    state = _write_state(tmp_path / "state.json", "spec|2026-10-15|2026-10-16", "failed")

    code = main(["--check", "window", "--state-file", str(state), "--now", "2026-10-16T04:00:00+00:00"])

    assert code == 0


def test_window_check_retries_when_the_target_book_changed(tmp_path: Path) -> None:
    state = _write_state(
        tmp_path / "state.json",
        "spec|2026-10-15|target-a|2026-10-16",
        "ok",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"targets_sha256": "target-b"}), encoding="utf-8")

    code = main(
        [
            "--check",
            "window",
            "--state-file",
            str(state),
            "--manifest-file",
            str(manifest),
            "--now",
            "2026-10-16T04:00:00+00:00",
        ]
    )

    assert code == 0


def test_window_check_blocks_when_the_target_book_is_unchanged(tmp_path: Path) -> None:
    state = _write_state(
        tmp_path / "state.json",
        "spec|2026-10-15|target-a|2026-10-16",
        "ok",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"targets_sha256": "target-a"}), encoding="utf-8")

    code = main(
        [
            "--check",
            "window",
            "--state-file",
            str(state),
            "--manifest-file",
            str(manifest),
            "--now",
            "2026-10-16T04:00:00+00:00",
        ]
    )

    assert code == BLOCKED


def test_window_check_blocks_outside_the_catchup_budget(tmp_path: Path) -> None:
    state = _write_state(tmp_path / "state.json", "spec|2026-10-14|2026-10-15", "ok")

    code = main(["--check", "window", "--state-file", str(state), "--now", "2026-10-16T12:00:00+00:00"])

    assert code == BLOCKED


def test_force_overrides_window_but_not_data_completeness(tmp_path: Path) -> None:
    panel = _write_panel(tmp_path / "panel.csv", ["2026-10-13"])
    state = _write_state(tmp_path / "state.json", "spec|2026-10-15|2026-10-16", "ok")

    assert (
        main(
            [
                "--check",
                "window",
                "--force",
                "--state-file",
                str(state),
                "--now",
                "2026-10-16T23:00:00+00:00",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--check",
                "panel",
                "--force",
                "--panel",
                str(panel),
                "--now",
                "2026-10-16T23:00:00+00:00",
            ]
        )
        == BLOCKED
    )
