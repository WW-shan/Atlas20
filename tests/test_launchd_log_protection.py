"""Launchd logs must survive cleanup tools and still accept live appends."""

from __future__ import annotations

import os
import plistlib
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXECUTE_PLIST = ROOT / "ops" / "com.atlas20.derivatives-execute.plist"
PROTECT_PLIST = ROOT / "ops" / "com.atlas20.protect-live-logs.plist"
PROTECT_SCRIPT = ROOT / "ops" / "protect_live_logs.sh"

LOG_NAMES = (
    "atlas20-cmc-probe.log",
    "atlas20-daily-refresh.log",
    "atlas20-derivatives-execute.log",
    "atlas20-live-monitor.log",
    "atlas20-log-protect.log",
)

requires_macos_chflags = pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("chflags") is None,
    reason="append-only flags and chflags are macOS-specific",
)


def _run_protection_script(log_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(log_dir)
    env["ATLAS20_LOG_DIR"] = str(log_dir)
    return subprocess.run(
        ["/bin/sh", str(PROTECT_SCRIPT)],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )


def _clear_append_flags(log_dir: Path) -> None:
    for name in LOG_NAMES:
        path = log_dir / name
        if not path.exists():
            continue
        os.chflags(path, os.stat(path).st_flags & ~stat.UF_APPEND)


def test_launchd_job_reapplies_log_protection_at_load_and_periodically() -> None:
    payload = plistlib.loads(PROTECT_PLIST.read_bytes())
    deploy_root = plistlib.loads(EXECUTE_PLIST.read_bytes())["WorkingDirectory"]

    assert payload["Label"] == "com.atlas20.protect-live-logs"
    assert payload["ProgramArguments"] == [
        "/bin/sh",
        f"{deploy_root}/ops/{PROTECT_SCRIPT.name}",
    ]
    assert payload["WorkingDirectory"] == deploy_root
    assert payload["RunAtLoad"] is True
    assert 0 < payload["StartInterval"] <= 900
    assert Path(payload["StandardOutPath"]).name == "atlas20-log-protect.log"
    assert payload["StandardErrorPath"] == payload["StandardOutPath"]

    script = PROTECT_SCRIPT.read_text(encoding="utf-8")
    assert "chflags uappnd" in script
    for name in LOG_NAMES:
        assert name in script


@requires_macos_chflags
def test_protection_script_creates_every_launchd_log_as_append_only(tmp_path: Path) -> None:
    existing = tmp_path / LOG_NAMES[0]
    existing.write_text("existing\n", encoding="utf-8")

    try:
        result = _run_protection_script(tmp_path)

        assert result.stdout == ""
        assert result.stderr == ""
        for name in LOG_NAMES:
            path = tmp_path / name
            assert path.is_file()
            assert os.stat(path).st_flags & stat.UF_APPEND
        assert existing.read_text(encoding="utf-8") == "existing\n"
    finally:
        _clear_append_flags(tmp_path)

@requires_macos_chflags
def test_protected_log_accepts_appends_but_blocks_deletion(tmp_path: Path) -> None:
    _run_protection_script(tmp_path)
    log = tmp_path / LOG_NAMES[0]

    try:
        with log.open("a", encoding="utf-8") as handle:
            handle.write("launchd output\n")

        assert log.read_text(encoding="utf-8") == "launchd output\n"
        with pytest.raises(PermissionError):
            log.unlink()
        assert log.exists()
    finally:
        _clear_append_flags(tmp_path)


@requires_macos_chflags
def test_protection_script_is_idempotent_and_repairs_a_missing_file(tmp_path: Path) -> None:
    _run_protection_script(tmp_path)
    removed = tmp_path / LOG_NAMES[1]

    try:
        os.chflags(removed, os.stat(removed).st_flags & ~stat.UF_APPEND)
        removed.unlink()
        removed.write_text("recreated\n", encoding="utf-8")

        first = _run_protection_script(tmp_path)
        second = _run_protection_script(tmp_path)

        assert first.stdout == second.stdout == ""
        assert first.stderr == second.stderr == ""
        assert os.stat(removed).st_flags & stat.UF_APPEND
        assert removed.read_text(encoding="utf-8") == "recreated\n"
    finally:
        _clear_append_flags(tmp_path)
