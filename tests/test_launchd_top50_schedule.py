from __future__ import annotations

import os
from pathlib import Path
import plistlib
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLIST = ROOT / "ops" / "com.atlas20.top50-readiness.plist"
WRAPPER = ROOT / "ops" / "run_top50_readiness.sh"


def test_top50_fallback_runs_once_after_the_daily_fill() -> None:
    payload = plistlib.loads(PLIST.read_bytes())

    assert payload["Label"] == "com.atlas20.top50-readiness"
    assert payload["ProgramArguments"] == [
        "/bin/zsh",
        "/Users/ww/Project/Atlas20/ops/run_top50_readiness.sh",
    ]
    assert payload["WorkingDirectory"] == "/Users/ww/Project/Atlas20"
    assert payload["StartCalendarInterval"] == [{"Hour": 9, "Minute": 45}]
    assert payload["RunAtLoad"] is False
    assert payload["ThrottleInterval"] == 300


def test_top50_wrapper_loads_only_telegram_credentials() -> None:
    text = WRAPPER.read_text(encoding="utf-8")

    assert "telegram.env" in text
    assert "bitget.env" not in text
    assert "execute_live_plan.py" not in text
    assert "--notify-only" in text
    assert "--check-current" in text
    assert 'MAKE_BIN="${ATLAS20_MAKE_BIN:-/usr/bin/make}"' in text
    assert '"$MAKE_BIN" top50-readiness ARGS=--notify' in text


def _run_wrapper(
    tmp_path: Path,
    *,
    notify_rc: int,
    check_rc: int,
    make_rc: int,
    shell: str = "/bin/sh",
    telegram_env: bool = True,
    broken_telegram_env: bool = False,
) -> tuple[subprocess.CompletedProcess[str], str, Path]:
    project = tmp_path / "project"
    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        """#!/bin/sh
printf 'python %s\\n' "$*" >> "$ATLAS20_TEST_LOG"
case "$*" in
  *--notify-only*) exit "$ATLAS20_TEST_NOTIFY_RC" ;;
  *--check-current*) exit "$ATLAS20_TEST_CHECK_RC" ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    python.chmod(0o755)

    make = tmp_path / "fake-make"
    make.write_text(
        """#!/bin/sh
printf 'make %s\\n' "$*" >> "$ATLAS20_TEST_LOG"
exit "$ATLAS20_TEST_MAKE_RC"
""",
        encoding="utf-8",
    )
    make.chmod(0o755)

    config = tmp_path / "config"
    config.mkdir()
    if telegram_env:
        (config / "telegram.env").write_text(
            "false\n" if broken_telegram_env else "ATLAS20_TELEGRAM_CHAT_ID=test\n",
            encoding="utf-8",
        )
    log = tmp_path / "calls.log"
    env = os.environ.copy()
    env.update(
        {
            "ATLAS20_PROJECT_ROOT": str(project),
            "ATLAS20_CONFIG_DIR": str(config),
            "ATLAS20_MAKE_BIN": str(make),
            "ATLAS20_TEST_LOG": str(log),
            "ATLAS20_TEST_NOTIFY_RC": str(notify_rc),
            "ATLAS20_TEST_CHECK_RC": str(check_rc),
            "ATLAS20_TEST_MAKE_RC": str(make_rc),
        }
    )
    completed = subprocess.run(
        [shell, str(WRAPPER)],
        capture_output=True,
        env=env,
        text=True,
        check=False,
    )
    return completed, log.read_text(encoding="utf-8") if log.exists() else "", log


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/zsh"])
def test_top50_wrapper_still_rebuilds_when_notification_retry_fails(
    tmp_path: Path, shell: str
) -> None:
    completed, calls, _log = _run_wrapper(
        tmp_path,
        notify_rc=9,
        check_rc=3,
        make_rc=0,
        shell=shell,
    )

    assert calls.splitlines() == [
        "python scripts/run_top50_readiness.py --notify-only",
        "python scripts/run_top50_readiness.py --check-current",
        "make top50-readiness ARGS=--notify",
    ]
    assert completed.returncode != 0
    assert "notify-only failed (9)" in completed.stderr


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/zsh"])
def test_top50_wrapper_skips_rebuild_when_current_pointer_is_ready(
    tmp_path: Path, shell: str
) -> None:
    completed, calls, _log = _run_wrapper(
        tmp_path,
        notify_rc=0,
        check_rc=0,
        make_rc=99,
        shell=shell,
    )

    assert completed.returncode == 0
    assert calls.splitlines() == [
        "python scripts/run_top50_readiness.py --notify-only",
        "python scripts/run_top50_readiness.py --check-current",
    ]


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/zsh"])
def test_top50_wrapper_propagates_rebuild_failure(
    tmp_path: Path, shell: str
) -> None:
    completed, calls, _log = _run_wrapper(
        tmp_path,
        notify_rc=0,
        check_rc=3,
        make_rc=7,
        shell=shell,
    )

    assert completed.returncode == 7
    assert calls.splitlines()[-1] == "make top50-readiness ARGS=--notify"


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/zsh"])
def test_top50_wrapper_repairs_data_when_telegram_env_is_missing(
    tmp_path: Path, shell: str
) -> None:
    completed, calls, _log = _run_wrapper(
        tmp_path,
        notify_rc=0,
        check_rc=3,
        make_rc=0,
        telegram_env=False,
        shell=shell,
    )

    assert calls.splitlines() == [
        "python scripts/run_top50_readiness.py --check-current",
        "make top50-readiness",
    ]
    assert completed.returncode != 0
    assert "missing Telegram environment" in completed.stderr


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/zsh"])
def test_top50_wrapper_repairs_data_when_telegram_env_fails_to_load(
    tmp_path: Path, shell: str
) -> None:
    completed, calls, _log = _run_wrapper(
        tmp_path,
        notify_rc=0,
        check_rc=3,
        make_rc=0,
        broken_telegram_env=True,
        shell=shell,
    )

    assert calls.splitlines() == [
        "python scripts/run_top50_readiness.py --check-current",
        "make top50-readiness",
    ]
    assert completed.returncode != 0
    assert "could not load Telegram environment" in completed.stderr
