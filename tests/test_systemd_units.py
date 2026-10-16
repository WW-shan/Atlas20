from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_data_refresh_timer_precedes_the_signal_attempts() -> None:
    timer = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer").read_text(encoding="utf-8")
    service = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.service").read_text(
        encoding="utf-8"
    )

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
    """A primary run a reboot killed must be repaired before 03:05 UTC."""

    timer = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer").read_text(encoding="utf-8")

    assert "OnCalendar=*-*-* 02:55:00 UTC" in timer
    assert timer.index("02:30:00") < timer.index("02:55:00")


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
    assert "make derivatives-oos-data" not in service
    assert "ATLAS20_PROJECT_ROOT=/opt/atlas20" in service
    assert "ATLAS20_CONFIG_DIR=/etc/atlas20" in service
    # The wrapper has to be POSIX sh for that ExecStart to work on Ubuntu.
    assert wrapper.startswith("#!/bin/sh")
    assert "print -u2" not in wrapper


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

    assert "OnCalendar=*-*-* 02:00:00 UTC" in timer
    assert "OnCalendar=*-*-* 03:00:00 UTC" in timer
    assert "Unit=atlas20-derivatives-signal.service" in timer
    assert "derivatives-oos-data derivatives-oos derivatives-notify" in service
    # The data-refresh timer must run before the 03:00 catch-up attempt.
    assert "02:30:00 UTC" in (
        ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer"
    ).read_text(encoding="utf-8")
