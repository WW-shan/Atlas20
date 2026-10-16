"""The macOS launchd jobs must trade and check *after* the close, not before.

launchd reads ``StartCalendarInterval`` in the host's local time zone, not
UTC. The checked-in plists target this workstation (Asia/Shanghai, UTC+8), so
an ``Hour`` of 11 fires at 03:05 UTC: five minutes after the model's T+1
03:00 UTC fill point and after the 02:30 UTC daily refresh has written the
panel. Getting this conversion wrong would silently trade a day early, so the
schedule is pinned here the same way the refresh and probe jobs are; the
read-only monitor follows the same rule one window later.
"""

from __future__ import annotations

from datetime import datetime, timezone
import plistlib
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXECUTE_PLIST = PROJECT_ROOT / "ops" / "com.atlas20.derivatives-execute.plist"
MONITOR_PLIST = PROJECT_ROOT / "ops" / "com.atlas20.live-monitor.plist"
# The zone of the machine the checked-in plists are installed on.
PLIST_LOCAL_ZONE = ZoneInfo("Asia/Shanghai")


def _scheduled_utc_time(plist_path: Path) -> tuple[int, int]:
    payload = plistlib.loads(plist_path.read_bytes())
    entry = payload["StartCalendarInterval"]
    local = datetime(2026, 1, 15, entry["Hour"], entry["Minute"], tzinfo=PLIST_LOCAL_ZONE)
    utc = local.astimezone(timezone.utc)
    return (utc.hour, utc.minute)


def test_derivatives_job_fires_at_documented_utc_time():
    assert _scheduled_utc_time(EXECUTE_PLIST) == (3, 5)


def test_monitor_fires_after_the_daily_rebalance():
    execute = _scheduled_utc_time(EXECUTE_PLIST)
    monitor = _scheduled_utc_time(MONITOR_PLIST)
    assert monitor == (11, 0)
    assert monitor > execute, "the read-only check must see a finished rebalance"


def test_derivatives_job_runs_after_the_daily_refresh():
    # The primary panel refresh fires at 10:30 Beijing (02:30 UTC); the trade
    # must not fire before the panel has for that day.
    assert _scheduled_utc_time(EXECUTE_PLIST) > (2, 30)


def _wrapper_project_root(wrapper_path: Path) -> str:
    """The deployed path the wrapper itself declares, e.g. /Users/ww/Project/Atlas20.

    The plists hard-code the path of the machine they are installed on, so a
    test running in a CI checkout (a different absolute path) must compare
    against what the checked-in wrapper declares, not against its own
    checkout root.
    """
    script = wrapper_path.read_text(encoding="utf-8")
    prefix = 'PROJECT_ROOT="'
    for line in script.splitlines():
        if line.startswith(prefix) and line.endswith('"'):
            return line[len(prefix):-1]
    raise AssertionError(f"{wrapper_path.name} does not declare PROJECT_ROOT")


def _assert_launchd_contract(
    plist_path: Path, wrapper_path: Path, log_name: str, *, run_at_load: bool
) -> None:
    payload = plistlib.loads(plist_path.read_bytes())
    project_root = _wrapper_project_root(wrapper_path)
    assert payload["ProgramArguments"] == ["/bin/zsh", f"{project_root}/ops/{wrapper_path.name}"]
    assert payload["WorkingDirectory"] == project_root
    assert Path(payload["ProgramArguments"][1]).name == wrapper_path.name
    assert payload["RunAtLoad"] is run_at_load
    assert payload["ThrottleInterval"] == 300
    assert payload["StandardOutPath"].startswith("/")
    assert payload["StandardOutPath"].endswith(f"Library/Logs/{log_name}")
    assert payload["StandardErrorPath"] == payload["StandardOutPath"]


def test_execute_plist_runs_the_wrapper_outside_shell_rc_files():
    _assert_launchd_contract(
        EXECUTE_PLIST,
        PROJECT_ROOT / "ops" / "run_derivatives_daily.sh",
        "atlas20-derivatives-execute.log",
        run_at_load=True,
    )


def test_monitor_plist_runs_the_wrapper_outside_shell_rc_files():
    _assert_launchd_contract(
        MONITOR_PLIST,
        PROJECT_ROOT / "ops" / "run_live_monitor.sh",
        "atlas20-live-monitor.log",
        run_at_load=False,
    )


def test_execute_job_catches_a_reboot_up_without_trading_twice():
    """RunAtLoad must be paired with the wrapper's window gate.

    Loading the job at boot is what catches up a day the machine was off for,
    but on its own it would also fire before the fill point and on every
    login, so the gate is part of the contract, not an optional extra.
    """

    payload = plistlib.loads(EXECUTE_PLIST.read_bytes())
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(encoding="utf-8")

    assert payload["RunAtLoad"] is True
    assert "scripts/live_chain_preflight.py --check window" in script
    assert "scripts/live_chain_preflight.py --check panel" in script
    assert "scripts/refresh_daily_data.py" in script


def test_execute_wrapper_sources_credentials_and_runs_the_live_chain():
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(encoding="utf-8")
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


def test_monitor_wrapper_is_read_only_and_notify_only():
    script = (PROJECT_ROOT / "ops" / "run_live_monitor.sh").read_text(encoding="utf-8")
    assert "bitget.env" in script
    assert "telegram.env" in script
    assert "monitor_live_track.py --notify" in script
    # The monitor must never place orders or run the trading chain.
    assert "execute-plan-live" not in script
    assert "place-order" not in script
    assert "ATLAS20_BITGET_API_KEY=" not in script
    assert "ATLAS20_TELEGRAM_BOT_TOKEN=" not in script

def test_wrapper_offers_a_manual_late_catchup_that_launchd_never_uses():
    """Only a human may drop the window; the scheduled fires must obey it.

    The window gate would otherwise make the documented manual catch-up
    (`ops/run_derivatives_daily.sh`) a silent no-op outside 03:05-09:05 UTC.
    """

    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(encoding="utf-8")
    payload = plistlib.loads(EXECUTE_PLIST.read_bytes())

    assert '"${1:-}" = "--force"' in script
    assert "force_args=(--force)" in script
    # launchd passes the wrapper path and nothing else, so every scheduled or
    # RunAtLoad fire goes through the window.
    assert len(payload["ProgramArguments"]) == 2
