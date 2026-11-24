"""The macOS launchd jobs must trade and check *after* the close, not before.

launchd reads ``StartCalendarInterval`` in the host's local time zone, not
UTC. The checked-in plists target this workstation (Asia/Shanghai, UTC+8). The
primary fire is now 09:05 Beijing = 01:05 UTC, the live fast path, with
01:35/03:05/03:35/04:35/06:35 UTC fires retained as fallback and catch-up. Getting this conversion wrong would silently trade a day
early, so the schedule is pinned here the same way the refresh and probe jobs
are; the read-only monitor follows the same rule one window later.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import plistlib
from pathlib import Path
import shutil
import subprocess
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXECUTE_PLIST = PROJECT_ROOT / "ops" / "com.atlas20.derivatives-execute.plist"
MONITOR_PLIST = PROJECT_ROOT / "ops" / "com.atlas20.live-monitor.plist"
# The zone of the machine the checked-in plists are installed on.
PLIST_LOCAL_ZONE = ZoneInfo("Asia/Shanghai")


def _scheduled_utc_times(plist_path: Path) -> list[tuple[int, int]]:
    payload = plistlib.loads(plist_path.read_bytes())
    raw = payload["StartCalendarInterval"]
    entries = raw if isinstance(raw, list) else [raw]
    times = []
    for entry in entries:
        local = datetime(
            2026, 1, 15, entry["Hour"], entry["Minute"], tzinfo=PLIST_LOCAL_ZONE
        )
        utc = local.astimezone(timezone.utc)
        times.append((utc.hour, utc.minute))
    return times


def _scheduled_utc_time(plist_path: Path) -> tuple[int, int]:
    times = _scheduled_utc_times(plist_path)
    assert len(times) == 1
    return times[0]


def test_derivatives_job_fires_at_documented_utc_time():
    assert _scheduled_utc_times(EXECUTE_PLIST)[0] == (1, 5)


def test_monitor_fires_after_the_daily_rebalance():
    execute = max(_scheduled_utc_times(EXECUTE_PLIST))
    monitor = _scheduled_utc_time(MONITOR_PLIST)
    assert monitor == (11, 0)
    assert monitor > execute, "the read-only check must see a finished rebalance"


def test_derivatives_job_runs_after_the_daily_refresh():
    # The data and signal nodes fire at 00:30 and 00:35 UTC; the single
    # execution attempt follows at 01:05.
    assert min(_scheduled_utc_times(EXECUTE_PLIST)) > (0, 35)


def test_derivatives_job_has_one_execution_attempt_per_day() -> None:
    assert _scheduled_utc_times(EXECUTE_PLIST) == [(1, 5)]


def test_data_node_builds_the_top50_and_top20_pool_before_signal() -> None:
    """The Top50 data pull is required; only the duplicate retry job is gone."""

    data = (PROJECT_ROOT / "ops" / "run_derivatives_data.sh").read_text(encoding="utf-8")
    inner = (PROJECT_ROOT / "ops" / "run_derivatives_data_inner.sh").read_text(encoding="utf-8")
    signal = (PROJECT_ROOT / "ops" / "run_derivatives_signal.sh").read_text(encoding="utf-8")
    data_at = inner.index("/usr/bin/make top50-readiness-unlocked")
    check_at = inner.index("/usr/bin/make top50-readiness-check")
    assert data_at < check_at
    assert "scripts/run_node_deadline.py" in data
    assert "00:50:00+00:00" in data
    assert "scripts/refresh_daily_data.py" in inner
    assert " --force " not in inner
    assert "--wait-seconds 300" in inner
    assert "/usr/bin/make derivatives-live-data" in inner
    assert inner.index("/usr/bin/make derivatives-live-data") < inner.index(
        "/usr/bin/make top50-readiness-unlocked"
    )
    assert '/usr/bin/make "$SIGNAL_TARGET"' in signal
    assert "top50-readiness" not in signal
    # The repository may retain the legacy plist for rollback documentation,
    # but it must not be installed or referenced by the four-node schedule.
    assert "com.atlas20.top50-readiness" not in data
    assert "com.atlas20.top50-readiness" not in signal


def test_data_node_runs_once_before_the_signal_node() -> None:
    data_plist = PROJECT_ROOT / "ops" / "com.atlas20.daily-refresh.plist"
    signal_plist = PROJECT_ROOT / "ops" / "com.atlas20.derivatives-refresh.plist"
    assert _scheduled_utc_times(data_plist) == [(0, 30)]
    assert _scheduled_utc_times(signal_plist) == [(0, 35)]

    data = (PROJECT_ROOT / "ops" / "run_derivatives_data.sh").read_text(encoding="utf-8")
    inner = (PROJECT_ROOT / "ops" / "run_derivatives_data_inner.sh").read_text(encoding="utf-8")
    signal = (PROJECT_ROOT / "ops" / "run_derivatives_signal.sh").read_text(encoding="utf-8")
    assert "scripts/run_node_deadline.py" in data
    assert "scripts/refresh_daily_data.py" in inner
    assert "/usr/bin/make derivatives-live-data" in inner
    assert "scripts/execute_live_plan.py" not in inner
    assert '/usr/bin/make "$SIGNAL_TARGET"' in signal
    assert "scripts/execute_live_plan.py" not in signal
    assert "finalize" not in inner
    assert "finalize" not in signal


def test_monitor_is_the_only_post_execution_node() -> None:
    monitor = PROJECT_ROOT / "ops" / "com.atlas20.live-monitor.plist"
    assert _scheduled_utc_times(monitor) == [(11, 0)]
    script = (PROJECT_ROOT / "ops" / "run_live_monitor.sh").read_text(encoding="utf-8")
    assert "scripts/monitor_live_track.py" in script
    assert "scripts/execute_live_plan.py" not in script
    assert "refresh_daily_data.py" not in script


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
            return line[len(prefix) : -1]
    raise AssertionError(f"{wrapper_path.name} does not declare PROJECT_ROOT")


def _assert_launchd_contract(
    plist_path: Path, wrapper_path: Path, log_name: str, *, run_at_load: bool
) -> None:
    payload = plistlib.loads(plist_path.read_bytes())
    project_root = _wrapper_project_root(wrapper_path)
    assert payload["ProgramArguments"] == [
        "/bin/zsh",
        f"{project_root}/ops/{wrapper_path.name}",
    ]
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
        run_at_load=False,
    )


def test_monitor_plist_runs_the_wrapper_outside_shell_rc_files():
    _assert_launchd_contract(
        MONITOR_PLIST,
        PROJECT_ROOT / "ops" / "run_live_monitor.sh",
        "atlas20-live-monitor.log",
        run_at_load=False,
    )


def test_monitor_wrapper_is_read_only_and_notify_only():
    script = (PROJECT_ROOT / "ops" / "run_live_monitor.sh").read_text(encoding="utf-8")
    assert "bitget.env" in script
    assert "telegram.env" in script
    assert "scripts/monitor_live_track.py" in script
    assert "--notify" in script
    # The monitor must never place orders or run the trading chain.
    assert "execute-plan-live" not in script
    assert "place-order" not in script
    assert "ATLAS20_BITGET_API_KEY=" not in script
    assert "ATLAS20_TELEGRAM_BOT_TOKEN=" not in script


def test_monitor_wrapper_follows_the_persisted_track_profile():
    script = (PROJECT_ROOT / "ops" / "run_live_monitor.sh").read_text(encoding="utf-8")

    assert 'TRACK_ENV="$PROJECT_ROOT/config/track.env"' in script
    assert 'TRACK_ENV="$CONFIG_DIR/track.env"' not in script
    assert "ls104-g175-m090" in script
    assert "reports/ls45_live_g175/oos_targets.csv" in script
    assert "data/ls45_g175_execution_state.json" in script
    assert "prior_track_order_registry.json" in script
    assert "--prior-track-registry" in script


KEEP_AWAKE_PLIST = PROJECT_ROOT / "ops" / "com.atlas20.keep-awake.plist"


def test_keep_awake_agent_is_a_login_persistent_system_sleep_guard():
    payload = plistlib.loads(KEEP_AWAKE_PLIST.read_bytes())

    assert payload["Label"] == "com.atlas20.keep-awake"
    assert payload["ProgramArguments"] == ["/usr/bin/caffeinate", "-dimsu"]
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert payload["ThrottleInterval"] == 30
    assert payload["StandardOutPath"] == payload["StandardErrorPath"]
    assert payload["StandardOutPath"].endswith("Library/Logs/atlas20-keep-awake.log")


def test_persisted_track_profile_is_versioned_inside_the_project() -> None:
    profile_file = PROJECT_ROOT / "config" / "track.env"

    assert profile_file.is_file()
    profile_lines = [
        line.strip()
        for line in profile_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert profile_lines == ["ATLAS20_TRACK_PROFILE=ls104-g175-m090"]
    for wrapper in ("run_derivatives_daily.sh", "run_live_monitor.sh"):
        script = (PROJECT_ROOT / "ops" / wrapper).read_text(encoding="utf-8")
        assert 'TRACK_ENV="$PROJECT_ROOT/config/track.env"' in script
        assert 'TRACK_ENV="$CONFIG_DIR/track.env"' not in script


def test_ls104_maintenance_targets_are_profile_bound() -> None:
    expected = {
        "protect-live-ls104": "--protect-only",
        "reconcile-live-ls104": "--reconcile-only",
    }

    for target, mode in expected.items():
        command = subprocess.check_output(
            ["make", "-n", target],
            cwd=PROJECT_ROOT,
            text=True,
        )
        assert "PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090" in command
        assert "data/ls45_g175_execution_state.json" in command
        assert "reports/ls45_live_g175_live/journal.csv" in command
        assert mode in command


def test_wrappers_fail_closed_without_a_track_profile(tmp_path: Path) -> None:
    project = tmp_path / "project"
    config = tmp_path / "credentials"
    project.mkdir()
    config.mkdir()
    (config / "bitget.env").write_text("", encoding="utf-8")
    (config / "telegram.env").write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "ATLAS20_PROJECT_ROOT": str(project),
        "ATLAS20_CONFIG_DIR": str(config),
    }
    env.pop("ATLAS20_TRACK_PROFILE", None)
    shells = [shutil.which("sh") or "/bin/sh"]
    zsh = shutil.which("zsh")
    if zsh is not None:
        shells.append(zsh)

    wrapper_shells = {
        "run_derivatives_daily.sh": shells,
        "run_live_monitor.sh": [zsh] if zsh is not None else shells,
    }
    for wrapper, selected_shells in wrapper_shells.items():
        for shell in selected_shells:
            result = subprocess.run(
                [shell, str(PROJECT_ROOT / "ops" / wrapper)],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1, (
                f"{wrapper} under {Path(shell).name} must refuse to run without a profile: "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
            assert "missing ATLAS20_TRACK_PROFILE" in result.stderr


def test_data_node_does_not_fail_or_rebuild_when_an_execution_already_holds_the_lock() -> None:
    """Signal can safely run on the completed artifacts after execution exists."""

    inner = (PROJECT_ROOT / "ops" / "run_derivatives_data_inner.sh").read_text(
        encoding="utf-8"
    )

    assert "another Atlas20 execution holds" in inner
    assert "signal already completed" in inner
    assert 'echo "another Atlas20 process holds $LOCK_FILE; refusing data refresh" >&2' not in inner
