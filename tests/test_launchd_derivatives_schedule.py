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
    # The panel refresh fires at 08:30 Beijing (00:30 UTC); the trade must
    # wait until after that refresh and its 08:50 catch-up.
    assert min(_scheduled_utc_times(EXECUTE_PLIST)) > (0, 50)


def test_derivatives_job_retries_failed_runs_inside_the_catchup_window():
    times = _scheduled_utc_times(EXECUTE_PLIST)

    assert times == [(1, 5), (1, 35), (3, 5), (3, 35), (4, 35), (6, 35)]
    assert max(times) <= (7, 5)


def test_refresh_precedes_the_final_retry_after_the_0400_utc_settlement():
    refresh_times = _scheduled_utc_times(
        PROJECT_ROOT / "ops" / "com.atlas20.derivatives-refresh.plist"
    )

    # The 14:35 Beijing retry is 06:35 UTC.  With the one-hour publication
    # allowance, the 04:00 UTC settlement becomes mandatory at 05:00 UTC.
    # A refresh at 05:05 UTC must therefore exist and finish before the retry.
    assert (5, 5) in refresh_times
    assert (6, 35) > (5, 5)


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
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    assert payload["RunAtLoad"] is True
    assert "scripts/live_chain_preflight.py" in script
    assert "--check window" in script
    assert '--manifest-file "$MANIFEST_FILE"' in script
    assert '--state-file "$STATE_FILE"' in script
    assert "scripts/live_chain_preflight.py --check panel" in script
    assert "scripts/refresh_daily_data.py" in script


def test_execute_wrapper_rechecks_complete_data_after_self_healing():
    """A refresh that skipped or still left a partial day must not trade."""

    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    assert script.count("scripts/live_chain_preflight.py --check panel") >= 2
    assert "--force" in script[script.index("scripts/refresh_daily_data.py") :]
    assert script.index("scripts/refresh_daily_data.py") < script.rindex(
        "scripts/live_chain_preflight.py --check panel"
    )


def test_execute_wrapper_sources_credentials_and_runs_the_live_chain():
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )
    # Credentials live outside the repo; the wrapper is the one place that
    # loads them and must fail closed when they are missing.
    assert "bitget.env" in script
    assert "telegram.env" in script
    assert "exit 1" in script
    assert "/usr/bin/make derivatives-live" in script
    # No secrets may be committed into the wrapper itself.
    assert "ATLAS20_BITGET_API_KEY=" not in script
    assert "ATLAS20_TELEGRAM_BOT_TOKEN=" not in script


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


def test_wrapper_offers_a_manual_late_catchup_that_launchd_never_uses():
    """Only a human may drop the window; the scheduled fires must obey it.

    The window gate would otherwise make the documented manual catch-up
    (`ops/run_derivatives_daily.sh`) a silent no-op outside 01:05-07:05 UTC.
    """

    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )
    payload = plistlib.loads(EXECUTE_PLIST.read_bytes())

    assert '[ "${1:-}" = "--force" ]' in script
    assert "live_chain_preflight.py" in script
    assert "--check window --force" in script
    assert '--manifest-file "$MANIFEST_FILE"' in script
    assert '--state-file "$STATE_FILE"' in script
    assert "--allow-late-execution" in script
    # launchd passes the wrapper path and nothing else, so every scheduled or
    # RunAtLoad fire goes through the window.
    assert len(payload["ProgramArguments"]) == 2


def test_wrapper_runs_the_full_data_chain_audit_before_execution() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    assert "/usr/bin/make audit-data-chain" in script


def test_execute_fallback_rebuilds_top50_readiness_before_the_signal() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    fallback_start = script.index('if [ "$receipt_status" -ne 0 ]; then')
    live_data_at = script.index('/usr/bin/make derivatives-live-data', fallback_start)
    signal_at = script.index('/usr/bin/make "$SIGNAL_TARGET"', live_data_at)
    readiness_at = script.index("/usr/bin/make top50-readiness", fallback_start)

    assert live_data_at < readiness_at
    assert readiness_at < signal_at
    assert "--notify" not in script[readiness_at:signal_at]


def test_wrapper_runs_an_independent_post_execution_audit() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    execute_at = script.index("execution_status=0")
    post_execution = script[execute_at:]
    assert "scripts/execute_live_plan.py" in post_execution
    assert "run_monitor_audit" in post_execution
    assert "execution_status" in post_execution
    assert "monitor_status" in post_execution


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


def test_window_done_reconciles_stops_before_the_read_only_monitor() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )
    skip_block = script[
        script.index('if [ "$window_status" -eq 4 ]; then') : script.index(
            'elif [ "$window_status" -ne 0 ]; then'
        )
    ]

    reconcile_at = skip_block.index("scripts/execute_live_plan.py")
    assert "--protect-only" in skip_block[reconcile_at:]
    monitor_at = skip_block.index("run_monitor_audit")
    assert reconcile_at < monitor_at


def test_wrapper_exposes_the_ls104_profile_without_overwriting_ls45() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    assert "ATLAS20_TRACK_PROFILE" in script
    assert "ls104-g175-m090" in script
    assert "reports/ls45_live_g175/oos_targets.csv" in script
    assert "data/ls45_g175_execution_state.json" in script
    assert 'MARGIN_CAP="0.90"' in script
    assert 'LEVERAGE="4.0"' in script
    assert 'echo "Atlas20 track profile: $TRACK_PROFILE"' in script
    # A missing profile is a hard error: LS45 is an explicit rollback, never a
    # silent fallback when the project configuration is missing or damaged.
    assert 'TRACK_PROFILE="${ATLAS20_TRACK_PROFILE:-}"' in script
    assert 'TRACK_PROFILE="${ATLAS20_TRACK_PROFILE:-ls45-g125}"' not in script
    assert "missing ATLAS20_TRACK_PROFILE" in script


def test_wrapper_bootstraps_only_an_empty_ls104_execution_state() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    assert 'BOOTSTRAP_ARG="--bootstrap-track"' in script
    assert 'BOOTSTRAP_ARG=""' in script
    assert '[ "$TRACK_PROFILE" = "ls104-g175-m090" ]' in script
    assert '[ ! -e "$STATE_FILE" ]' in script
    assert 'TRACK_PROFILE="$TRACK_PROFILE"' in script
    assert "$BOOTSTRAP_ARG" in script


def test_wrapper_uses_profile_specific_kill_switches_and_one_global_lock() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    assert 'KILL_FILE="data/ls45_g125_execution.KILL"' in script
    assert 'KILL_FILE="data/ls45_g175_execution.KILL"' in script
    assert 'LOCK_FILE="data/derivatives_execution.lock"' in script
    assert '--kill-switch "$KILL_FILE"' in script
    assert '--lock-file "$LOCK_FILE"' in script
    assert (
        'PRIOR_ORDER_REGISTRY="reports/ls45_live_g175_live/prior_track_order_registry.json"'
        in script
    )
    assert '--prior-track-registry "$PRIOR_ORDER_REGISTRY"' in script
    assert "PRIOR_ORDER_ARG" not in script


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


def test_refresh_wrapper_passes_zsh_arguments_as_separate_words(
    tmp_path: Path,
) -> None:
    zsh = shutil.which("zsh")
    if zsh is None:
        return

    project = tmp_path / "project"
    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
    python.chmod(0o755)

    # Pin the wrapper's clock while preserving the exact production wrapper
    # text apart from the two date substitutions.  This is intentionally run
    # under zsh because that is how launchd invokes the script.
    wrapper_text = (PROJECT_ROOT / "ops" / "run_derivatives_refresh.sh").read_text(
        encoding="utf-8"
    )
    wrapper_text = wrapper_text.replace(
        'hour=$(date -u +%H)', 'hour=01'
    ).replace('minute=$(date -u +%M)', 'minute=03')
    wrapper = tmp_path / "run_derivatives_refresh.sh"
    wrapper.write_text(wrapper_text, encoding="utf-8")
    wrapper.chmod(0o755)

    result = subprocess.run(
        [zsh, str(wrapper)],
        cwd=PROJECT_ROOT,
        env={**os.environ, "ATLAS20_PROJECT_ROOT": str(project)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "scripts/refresh_derivatives_data.py",
        "--skip-if-fresh-receipt",
        "--panel-wait-seconds",
        "120",
        "--pre-execution",
        "--latest-start-utc",
        "01:05",
    ]


def test_refresh_wrapper_allows_a_bounded_0855_catch_up() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_refresh.sh").read_text(
        encoding="utf-8"
    )

    assert "date -u +%M" in script
    assert "--latest-start-utc 01:05" in script
    assert "panel_wait=120" in script
    assert "--skip-if-fresh-receipt" in script


def test_execute_wrapper_defers_when_a_prepare_still_holds_the_lock() -> None:
    script = (PROJECT_ROOT / "ops" / "run_derivatives_daily.sh").read_text(
        encoding="utf-8"
    )

    assert "--check-lock" in script
    assert "deferring this fire to the next retry" in script
    assert script.index("--check-lock") < script.index("derivatives-live-data")


def test_macos_derivatives_refresh_is_separate_and_does_not_trade() -> None:
    plist = PROJECT_ROOT / "ops" / "com.atlas20.derivatives-refresh.plist"
    text = plist.read_text(encoding="utf-8")
    assert "com.atlas20.derivatives-refresh" in text
    for local_time in (
        "<key>Hour</key>\n\t\t\t<integer>8</integer>",
        "<key>Hour</key>\n\t\t\t<integer>15</integer>",
        "<key>Hour</key>\n\t\t\t<integer>21</integer>",
        "<key>Hour</key>\n\t\t\t<integer>3</integer>",
    ):
        assert local_time in text
    for minute in ("35", "55"):
        assert f"<key>Minute</key>\n\t\t\t<integer>{minute}</integer>" in text
    assert "ops/run_derivatives_refresh.sh" in text
    assert "execute_live_plan.py" not in text
    assert "run_derivatives_daily.sh" not in text


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


def test_wrapper_passes_prior_registry_as_two_arguments_under_sh_and_zsh(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    config = tmp_path / "config"
    python_bin = project / ".venv" / "bin" / "python"
    python_bin.parent.mkdir(parents=True)
    config.mkdir()
    (config / "bitget.env").write_text("", encoding="utf-8")
    (config / "telegram.env").write_text("", encoding="utf-8")
    python_bin.write_text(
        """#!/bin/sh
case "$1" in
  scripts/live_chain_preflight.py) exit 4 ;;
  scripts/execute_live_plan.py) exit 0 ;;
  scripts/monitor_live_track.py)
    printf '%s\\n' "$@" > "$ATLAS20_MONITOR_ARGS_FILE"
    exit 0
    ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    python_bin.chmod(0o755)
    args_file = tmp_path / "monitor-args.txt"
    env = {
        **os.environ,
        "ATLAS20_PROJECT_ROOT": str(project),
        "ATLAS20_CONFIG_DIR": str(config),
        "ATLAS20_TRACK_PROFILE": "ls104-g175-m090",
        "ATLAS20_MONITOR_ARGS_FILE": str(args_file),
    }
    shells = [shutil.which("sh") or "/bin/sh"]
    zsh = shutil.which("zsh")
    if zsh is not None:
        shells.append(zsh)

    for shell in shells:
        subprocess.run(
            [shell, str(PROJECT_ROOT / "ops" / "run_derivatives_daily.sh")],
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        args = args_file.read_text(encoding="utf-8").splitlines()
        option_index = args.index("--prior-track-registry")
        assert args[option_index + 1] == (
            "reports/ls45_live_g175_live/prior_track_order_registry.json"
        )
        assert not any(arg.startswith("--prior-track-registry ") for arg in args), (
            f"{Path(shell).name} passed the option and path as one argument"
        )
