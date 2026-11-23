from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_data_refresh_timer_precedes_the_signal_attempts() -> None:
    timer = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer").read_text(encoding="utf-8")
    service = (ROOT / "ops" / "systemd" / "atlas20-data-refresh.service").read_text(
        encoding="utf-8"
    )

    assert timer.count("OnCalendar=") == 1
    assert "OnCalendar=*-*-* 00:30:00 UTC" in timer
    assert "Persistent=false" in timer
    assert "Unit=atlas20-data-refresh.service" in timer
    assert "ExecStart=/bin/sh /opt/atlas20/ops/run_derivatives_data.sh" in service
    assert "make refresh-data" not in service
    assert "launchd" not in timer.lower()
    assert "launchd" not in service.lower()


def test_prepare_timer_lands_before_the_single_execution_attempt() -> None:
    timer = (ROOT / "ops" / "systemd" / "atlas20-derivatives-refresh.timer").read_text(encoding="utf-8")
    assert "OnCalendar=*-*-* 00:35:00 UTC" in timer
    assert "Persistent=false" in timer
    assert "01:00:00 UTC" not in timer
    assert "00:55:00 UTC" not in timer


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

    assert "Persistent=false" in timer
    assert "ExecStart=/bin/sh /opt/atlas20/ops/run_derivatives_daily.sh" in service
    assert "make derivatives-live-data" not in service
    assert "ATLAS20_PROJECT_ROOT=/opt/atlas20" in service
    assert "ATLAS20_CONFIG_DIR=/etc/atlas20" in service
    # The wrapper has to be POSIX sh for that ExecStart to work on Ubuntu.
    assert wrapper.startswith("#!/bin/sh")
    assert "print -u2" not in wrapper


def test_derivatives_execute_has_one_attempt_and_no_replay() -> None:
    timer = (ROOT / "ops" / "systemd" / "atlas20-derivatives-execute.timer").read_text(encoding="utf-8")
    assert timer.count("OnCalendar=") == 1
    assert "OnCalendar=*-*-* 01:05:00 UTC" in timer
    assert "Persistent=false" in timer
    assert "01:35:00" not in timer
    assert "06:35:00" not in timer


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
    assert "$(MAKE) audit-data-chain" in live
    assert "$(MAKE) audit-symbols" in live
    assert "$(MAKE) audit-signal" in live
    assert "scripts/execute_live_plan.py --live --notify --require-isolated" in live


def test_daily_execution_wrapper_does_not_rebuild_data_or_signal() -> None:
    wrapper = (ROOT / "ops" / "run_derivatives_daily.sh").read_text(encoding="utf-8")
    data = (ROOT / "ops" / "run_derivatives_data.sh").read_text(encoding="utf-8")
    signal = (ROOT / "ops" / "run_derivatives_signal.sh").read_text(encoding="utf-8")
    assert "scripts/execute_live_plan.py" in wrapper
    assert "scripts/refresh_daily_data.py" not in wrapper
    assert "/usr/bin/make derivatives-live-data" not in wrapper
    assert "finalize" not in wrapper
    assert "no automatic catch-up" in wrapper
    assert "scripts/refresh_daily_data.py" in data
    assert "/usr/bin/make derivatives-live-data" in data
    assert '/usr/bin/make "$SIGNAL_TARGET"' in signal
    assert "scripts/execute_live_plan.py" not in data
    assert "scripts/execute_live_plan.py" not in signal


def test_derivatives_signal_fallback_rebuilds_and_audits_before_notifying() -> None:
    service = (
        ROOT / "ops" / "systemd" / "atlas20-derivatives-signal.service"
    ).read_text(encoding="utf-8")

    assert "audit-data-chain audit-data-ls104 audit-signal-ls104 derivatives-notify-ls104" in service


def test_makefile_refresh_target_runs_only_the_ls104_data_chain() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    target = makefile.split("derivatives-refresh-ls104:", 1)[1].split("\n\n", 1)[0]

    assert "scripts/refresh_derivatives_data.py" in target
    assert "execute_live_plan.py" not in target


def test_derivatives_refresh_is_a_separate_non_trading_prepare_job() -> None:
    timer = (ROOT / "ops" / "systemd" / "atlas20-derivatives-refresh.timer").read_text(
        encoding="utf-8"
    )
    service = (ROOT / "ops" / "systemd" / "atlas20-derivatives-refresh.service").read_text(
        encoding="utf-8"
    )
    wrapper = (ROOT / "ops" / "run_derivatives_signal.sh").read_text(
        encoding="utf-8"
    )

    assert "OnCalendar=*-*-* 00:35:00 UTC" in timer
    assert timer.count("OnCalendar=") == 1
    assert "Unit=atlas20-derivatives-refresh.service" in timer
    assert "ExecStart=/bin/sh /opt/atlas20/ops/run_derivatives_signal.sh" in service
    assert "scripts/execute_live_plan.py" not in service
    assert "scripts/execute_live_plan.py" not in wrapper
    assert "scripts/refresh_daily_data.py" not in wrapper
    assert "/usr/bin/make derivatives-live-data" not in wrapper
    assert '/usr/bin/make "$SIGNAL_TARGET"' in wrapper


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
    assert (
        "derivatives-live-data derivatives-ls104-signal audit-data-chain "
        "audit-data-ls104 audit-signal-ls104 derivatives-notify-ls104"
    ) in service
    # The single data node must run before the notification timer.
    assert "00:30:00 UTC" in (
        ROOT / "ops" / "systemd" / "atlas20-data-refresh.timer"
    ).read_text(encoding="utf-8")


def test_ls104_make_target_uses_an_isolated_kill_switch_and_global_lock() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ls104 = makefile.split("derivatives-live-ls104:", 1)[1].split("\n\n", 1)[0]

    assert "LS104_KILL ?= data/ls45_g175_execution.KILL" in makefile
    assert "LS104_LOCK ?= data/derivatives_execution.lock" in makefile
    assert "--kill-switch $(LS104_KILL)" in ls104
    assert "--lock-file $(LS104_LOCK)" in ls104
    assert "AUDIT_SYMBOL_OUT=reports/ls45_live_g175_live/venue_symbol_audit.json" in ls104


def test_ls104_make_target_bootstraps_an_absent_state_file_once() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ls104 = makefile.split("derivatives-live-ls104:", 1)[1].split("\n\n", 1)[0]

    assert "LS104_BOOTSTRAP_ARG = $(if $(wildcard $(LS104_STATE)),,--bootstrap-track)" in makefile
    assert "$(LS104_BOOTSTRAP_ARG)" in ls104


def test_ls104_audit_ignores_only_the_exact_prior_track_order_registry() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    audit = makefile.split("audit-live-ls104:", 1)[1].split("\n\n", 1)[0]

    assert (
        "LS104_PRIOR_ORDER_REGISTRY ?= "
        "reports/ls45_live_g175_live/prior_track_order_registry.json"
    ) in makefile
    assert "--prior-track-registry $(LS104_PRIOR_ORDER_REGISTRY)" in audit
