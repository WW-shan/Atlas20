"""The macOS launchd job must trade after the close, not before it.

launchd reads ``StartCalendarInterval`` in the host's local time zone, not
UTC. The checked-in plist targets this workstation (Asia/Shanghai, UTC+8), so
an ``Hour`` of 11 fires at 03:05 UTC: five minutes after the model's T+1
03:00 UTC fill point and after the 02:30 UTC daily refresh has written the
panel. Getting this conversion wrong would silently trade a day early, so the
schedule is pinned here the same way the refresh and probe jobs are.
"""

from __future__ import annotations

from datetime import datetime, timezone
import plistlib
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLIST_PATH = PROJECT_ROOT / "ops" / "com.atlas20.derivatives-execute.plist"
WRAPPER_PATH = PROJECT_ROOT / "ops" / "run_derivatives_daily.sh"
# The zone of the machine the checked-in plist is installed on.
PLIST_LOCAL_ZONE = ZoneInfo("Asia/Shanghai")


def _scheduled_utc_time() -> tuple[int, int]:
    payload = plistlib.loads(PLIST_PATH.read_bytes())
    entry = payload["StartCalendarInterval"]
    local = datetime(2026, 1, 15, entry["Hour"], entry["Minute"], tzinfo=PLIST_LOCAL_ZONE)
    utc = local.astimezone(timezone.utc)
    return (utc.hour, utc.minute)


def test_derivatives_job_fires_at_documented_utc_time():
    assert _scheduled_utc_time() == (3, 5)


def test_derivatives_job_runs_after_the_daily_refresh():
    # The primary panel refresh fires at 10:30 Beijing (02:30 UTC); the trade
    # must not fire before the panel has for that day.
    assert _scheduled_utc_time() > (2, 30)


def _wrapper_project_root() -> str:
    """The deployed path the wrapper itself declares, e.g. /Users/ww/Project/Atlas20.

    The plist hard-codes the path of the machine it is installed on, so a test
    running in a CI checkout (a different absolute path) must compare against
    what the checked-in wrapper declares, not against its own checkout root.
    """
    script = WRAPPER_PATH.read_text(encoding="utf-8")
    prefix = 'PROJECT_ROOT="'
    for line in script.splitlines():
        if line.startswith(prefix) and line.endswith('"'):
            return line[len(prefix):-1]
    raise AssertionError("wrapper does not declare PROJECT_ROOT")


def test_plist_runs_the_wrapper_outside_shell_rc_files():
    payload = plistlib.loads(PLIST_PATH.read_bytes())
    project_root = _wrapper_project_root()
    assert payload["ProgramArguments"] == [
        "/bin/zsh",
        f"{project_root}/ops/run_derivatives_daily.sh",
    ]
    assert payload["WorkingDirectory"] == project_root
    assert Path(payload["ProgramArguments"][1]).name == WRAPPER_PATH.name
    assert payload["RunAtLoad"] is False
    assert payload["ThrottleInterval"] == 300
    assert payload["StandardOutPath"].startswith("/")
    assert payload["StandardOutPath"].endswith(
        "Library/Logs/atlas20-derivatives-execute.log"
    )
    assert payload["StandardErrorPath"] == payload["StandardOutPath"]


def test_wrapper_sources_credentials_and_runs_the_live_chain():
    script = WRAPPER_PATH.read_text(encoding="utf-8")
    # Credentials live outside the repo; the wrapper is the one place that
    # loads them and must fail closed when they are missing.
    assert "bitget.env" in script
    assert "telegram.env" in script
    assert "exit 1" in script
    assert (
        "/usr/bin/make derivatives-oos-data derivatives-oos execute-plan-live"
        in script
    )
    # No secrets may be committed into the wrapper itself.
    assert "ATLAS20_BITGET_API_KEY=" not in script
    assert "ATLAS20_TELEGRAM_BOT_TOKEN=" not in script
