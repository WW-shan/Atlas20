from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_data_refresh_timer_precedes_the_signal_attempts() -> None:
    timer = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer").read_text(encoding="utf-8")
    service = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.service").read_text(
        encoding="utf-8"
    )

    assert "OnCalendar=*-*-* 00:30:00 UTC" in timer
    assert "OnCalendar=*-*-* 00:50:00 UTC" in timer
    assert "OnCalendar=*-*-* 02:30:00 UTC" in timer
    assert "OnCalendar=*-*-* 02:55:00 UTC" in timer
    assert "OnCalendar=*-*-* 06:30:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "Unit=atlas20-data-refresh.service" in timer
    # Go through the locked, skip-when-current wrapper: `make refresh-data`
    # would race the 02:55 catch-up into the same raw cache.
    assert "scripts/refresh_daily_data.py" in service
    assert "make refresh-data" not in service
    assert "launchd" not in timer.lower()
    assert "launchd" not in service.lower()


def test_data_refresh_catchup_lands_before_the_rebalance() -> None:
    """A primary run a reboot killed must be repaired before 01:05 UTC."""

    timer = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer").read_text(encoding="utf-8")

    assert "OnCalendar=*-*-* 00:50:00 UTC" in timer
    assert timer.index("00:30:00") < timer.index("00:50:00")


def test_derivatives_execute_runs_through_the_gated_wrapper() -> None:
    """systemd must not call `make` directly: that would skip every gate.

    Persistent=true replays a fire the machine was off for, which is the
    systemd equivalent of launchd's RunAtLoad; the wrapper's window gate is
    what keeps the replay from trading hours late or twice.
    """

    timer = (
        ROOT / "ops" / "systemd" / "atlas20-derivatives-execute.timer"
    ).read_text(encoding="utf-8")
    service = (
        ROOT / "ops" / "systemd" / "atlas20-derivatives-execute.service"
    ).read_text(encoding="utf-8")
    wrapper = (ROOT / "ops" / "run_derivatives_daily.sh").read_text(encoding="utf-8")

    assert "Persistent=true" in timer
    assert "ExecStart=/bin/sh /opt/atlas20/ops/run_derivatives_daily.sh" in service
    assert "make derivatives-live-data" not in service
    assert "ATLAS20_PROJECT_ROOT=/opt/atlas20" in service
    assert "ATLAS20_CONFIG_DIR=/etc/atlas20" in service
    # The wrapper has to be POSIX sh for that ExecStart to work on Ubuntu.
    assert wrapper.startswith("#!/bin/sh")
    assert "print -u2" not in wrapper


def test_derivatives_timer_retries_failed_runs_inside_the_catchup_window() -> None:
    timer = (
        ROOT / "ops" / "systemd" / "atlas20-derivatives-execute.timer"
    ).read_text(encoding="utf-8")

    for clock in ("01:05:00", "01:35:00", "03:05:00", "03:35:00", "04:35:00", "06:35:00"):
        assert f"OnCalendar=*-*-* {clock} UTC" in timer
    assert "OnCalendar=*-*-* 09:05:00 UTC" not in timer


def test_makefile_live_chain_runs_ls45_from_the_fresh_marks() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    live_data = makefile.split("derivatives-live-data:", 1)[1].split("\n\n", 1)[0]
    assert "DERIVATIVES_LIVE_RAW_DIR ?= data/raw/bitget_derivatives/merged_oos_20261112" in makefile
    assert "--output-dir $(DERIVATIVES_LIVE_RAW_DIR)" in live_data
    assert "--types mark" in live_data
    assert "--wait-for-live-mark-seconds $(DERIVATIVES_LIVE_MARK_WAIT_SECONDS)" in live_data
    assert "--wait-for-live-mark-poll-seconds $(DERIVATIVES_LIVE_MARK_POLL_SECONDS)" in live_data
    assert "--execution-utc 01:05" in live_data

    live_signal = makefile.split("derivatives-ls45-signal:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/run_ls45_live_signal.py" in live_signal

    live = makefile.split("derivatives-live:", 1)[1].split("\n\n", 1)[0]
    assert "$(MAKE) audit-symbols" in live
    assert "$(MAKE) audit-signal" in live
    assert "scripts/execute_live_plan.py --live --notify --require-isolated" in live


def test_daily_wrapper_uses_the_ls45_chain_only() -> None:
    wrapper = (ROOT / "ops" / "run_derivatives_daily.sh").read_text(encoding="utf-8")

    assert "/usr/bin/make derivatives-live" in wrapper
    assert "/usr/bin/make audit-symbols" in wrapper
    assert "/usr/bin/make audit-signal" in wrapper
    assert "derivatives-oos-data derivatives-oos execute-plan-live" not in wrapper


def test_makefile_refresh_target_rebuilds_the_panel() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    target = makefile.split("refresh-data:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/download_data.py" in target
    assert "scripts/build_datasets.py" in target


def test_derivatives_timer_refreshes_marks_before_notifying() -> None:
    timer = (ROOT / "ops" / "systemd" / "atlas20-derivatives-signal.timer").read_text(
        encoding="utf-8"
    )
    service = (ROOT / "ops" / "systemd" / "atlas20-derivatives-signal.service").read_text(
        encoding="utf-8"
    )

    assert "OnCalendar=*-*-* 03:45:00 UTC" in timer
    assert "OnCalendar=*-*-* 04:15:00 UTC" in timer
    assert "Unit=atlas20-derivatives-signal.service" in timer
    assert "derivatives-live-data derivatives-ls45-signal derivatives-notify" in service
    # The data-refresh timer must run before the 03:45 signal attempt.
    assert "00:50:00 UTC" in (
        ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer"
    ).read_text(encoding="utf-8")
