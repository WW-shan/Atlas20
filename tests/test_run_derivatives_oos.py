from __future__ import annotations

import pandas as pd
import pytest

NOW = pd.Timestamp("2026-10-09 16:05", tz="UTC")


def test_signal_day_caps_at_last_completed_utc_day_even_with_fresh_marks() -> None:
    from scripts.run_derivatives_oos import resolve_signal_window

    # Marks are fresh (1h old) but the newest mark is *inside* the current UTC
    # day, so the signal must stay on the last completed day (10-08).
    signal_day, staleness = resolve_signal_window(
        pd.Timestamp("2026-10-09 15:00", tz="UTC"), now=NOW
    )

    assert signal_day == pd.Timestamp("2026-10-08", tz="UTC")
    assert staleness == pytest.approx(1.083, abs=0.01)


def test_signal_day_follows_marks_when_they_are_a_day_behind() -> None:
    from scripts.run_derivatives_oos import resolve_signal_window

    signal_day, _ = resolve_signal_window(
        pd.Timestamp("2026-10-08 15:00", tz="UTC"), now=NOW
    )

    assert signal_day == pd.Timestamp("2026-10-08", tz="UTC")


def test_requested_end_date_can_only_pull_the_signal_day_earlier() -> None:
    from scripts.run_derivatives_oos import resolve_signal_window

    early, _ = resolve_signal_window(
        pd.Timestamp("2026-10-09 15:00", tz="UTC"), now=NOW, requested_end="2026-10-05"
    )
    assert early == pd.Timestamp("2026-10-05", tz="UTC")

    later, _ = resolve_signal_window(
        pd.Timestamp("2026-10-09 15:00", tz="UTC"), now=NOW, requested_end="2026-11-01"
    )
    assert later == pd.Timestamp("2026-10-08", tz="UTC")


def test_stale_marks_fail_closed_unless_explicitly_allowed() -> None:
    from scripts.run_derivatives_oos import resolve_signal_window

    frozen = pd.Timestamp("2026-10-07 09:00", tz="UTC")

    with pytest.raises(ValueError, match="mark data is stale"):
        resolve_signal_window(frozen, now=NOW, max_staleness_hours=30.0)

    signal_day, staleness = resolve_signal_window(
        frozen, now=NOW, max_staleness_hours=30.0, allow_stale=True
    )
    assert signal_day == pd.Timestamp("2026-10-07", tz="UTC")
    assert staleness == pytest.approx(55.08, abs=0.05)
