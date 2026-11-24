from __future__ import annotations

import subprocess
import time
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

import pytest

from scripts import run_node_deadline


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_finished_command_does_not_arm_the_deadline(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    deadline = datetime.now(timezone.utc) + timedelta(minutes=1)

    result = subprocess.run(
        run_node_deadline.command(
            deadline_utc=deadline.isoformat(),
            command=["/bin/sh", "-c", f"printf ok > {marker}"],
        ),
        check=False,
    )

    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8") == "ok"


def test_crossed_deadline_terminates_the_whole_command_group(tmp_path: Path) -> None:
    marker = tmp_path / "continued"
    deadline = datetime.now(timezone.utc) + timedelta(seconds=1)

    result = subprocess.run(
        run_node_deadline.command(
            deadline_utc=deadline.isoformat(),
            command=[
                "/bin/sh",
                "-c",
                f"sleep 3; printf continued > {marker}",
            ],
        ),
        check=False,
    )

    assert result.returncode == 3
    time.sleep(1)
    assert not marker.exists()


def test_already_crossed_deadline_never_starts_the_command(tmp_path: Path) -> None:
    marker = tmp_path / "started"
    deadline = datetime.now(timezone.utc) - timedelta(seconds=1)

    result = subprocess.run(
        run_node_deadline.command(
            deadline_utc=deadline.isoformat(),
            command=["/bin/sh", "-c", f"printf started > {marker}"],
        ),
        check=False,
    )

    assert result.returncode == 3
    assert not marker.exists()


def test_data_wrapper_returns_the_deadline_failure_status(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "ATLAS20_PROJECT_ROOT": str(PROJECT_ROOT),
        "ATLAS20_DATA_DEADLINE_UTC": "2026-11-24T00:50:00+00:00",
        "ATLAS20_TRACK_PROFILE": "ls104-g175-m090",
    }

    result = subprocess.run(
        ["/bin/sh", str(PROJECT_ROOT / "ops" / "run_derivatives_data.sh")],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    assert "refusing to start" in result.stderr


def test_nonzero_exit_is_propagated() -> None:
    deadline = datetime.now(timezone.utc) + timedelta(minutes=1)
    result = subprocess.run(
        run_node_deadline.command(
            deadline_utc=deadline.isoformat(),
            command=["/bin/sh", "-c", "exit 7"],
        ),
        check=False,
    )

    assert result.returncode == 7


def test_command_rejects_an_invalid_clock() -> None:
    with pytest.raises(ValueError):
        run_node_deadline.command(
            deadline_utc="not-a-time",
            command=["/bin/true"],
        )
