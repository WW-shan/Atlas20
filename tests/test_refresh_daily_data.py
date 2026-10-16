"""The refresh job must be overlap-free and free on a day that needs no work.

Adding a catch-up fire close to the primary run means two refreshes can be in
flight at once; a slow primary must not race the catch-up into the same raw
cache.  A catch-up that finds the panel already current must also cost
nothing, which is what keeps the extra fire cheap.
"""

from __future__ import annotations

from filelock import FileLock
from pathlib import Path

import pandas as pd

from scripts import refresh_daily_data


def _write_panel(path: Path, days: list[str]) -> Path:
    pd.DataFrame({"date": days}).to_csv(path, index=False)
    return path


def _args(tmp_path: Path, panel: Path, **overrides) -> list[str]:
    argv = {
        "--panel": str(panel),
        "--lock": str(tmp_path / "refresh.lock"),
        "--now": "2026-10-16T03:05:00+00:00",
    }
    argv.update(overrides)
    return [item for pair in argv.items() for item in pair]


def test_current_panel_skips_the_download(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(refresh_daily_data, "run_refresh", calls.append)
    panel = _write_panel(tmp_path / "panel.csv", ["2026-10-14", "2026-10-15"])

    assert refresh_daily_data.main(_args(tmp_path, panel)) == 0
    assert calls == [], "a current panel must not pay for a redundant refresh"


def test_lagging_panel_refreshes(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(refresh_daily_data, "run_refresh", calls.append)
    panel = _write_panel(tmp_path / "panel.csv", ["2026-10-13", "2026-10-14"])

    assert refresh_daily_data.main(_args(tmp_path, panel)) == 0
    assert calls == ["config/base.yaml"]


def test_missing_panel_refreshes(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(refresh_daily_data, "run_refresh", calls.append)
    panel = tmp_path / "absent.csv"

    assert refresh_daily_data.main(_args(tmp_path, panel)) == 0
    assert calls == ["config/base.yaml"]


def test_sibling_refresh_blocks_a_second_download(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(refresh_daily_data, "run_refresh", calls.append)
    panel = _write_panel(tmp_path / "panel.csv", ["2026-10-14"])
    lock_path = tmp_path / "refresh.lock"

    held = FileLock(str(lock_path))
    held.acquire(timeout=0)
    try:
        code = refresh_daily_data.main(_args(tmp_path, panel))
    finally:
        held.release()

    assert code == 0
    assert calls == [], "a held lock must not start a second download"


def test_freshness_is_rechecked_after_the_lock_is_taken(tmp_path: Path, monkeypatch) -> None:
    """A run that waited on a sibling must not download the same day again."""

    calls: list[str] = []
    monkeypatch.setattr(refresh_daily_data, "run_refresh", calls.append)
    panel = _write_panel(tmp_path / "panel.csv", ["2026-10-14"])
    answers = iter([True, False])
    monkeypatch.setattr(
        refresh_daily_data, "panel_lags_last_completed_day", lambda *args, **kwargs: next(answers)
    )

    assert refresh_daily_data.main(_args(tmp_path, panel)) == 0
    assert calls == [], "the second check must see the sibling's fresh panel"


def test_panel_path_for_resolves_the_config_path() -> None:
    resolved = refresh_daily_data.panel_path_for("config/base.yaml")

    assert resolved.name == "panel_daily.csv"
    assert resolved.parent.name == "processed"
