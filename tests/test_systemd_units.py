from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_data_refresh_timer_precedes_the_signal_attempts() -> None:
    timer = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer").read_text(encoding="utf-8")
    service = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.service").read_text(
        encoding="utf-8"
    )

    assert "OnCalendar=*-*-* 02:30:00 UTC" in timer
    assert "OnCalendar=*-*-* 06:30:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "Unit=atlas20-data-refresh.service" in timer
    assert "ExecStart=/usr/bin/make refresh-data" in service
    assert "launchd" not in timer.lower()
    assert "launchd" not in service.lower()


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
