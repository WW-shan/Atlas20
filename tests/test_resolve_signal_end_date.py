from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.resolve_signal_end_date import resolve_signal_end_date


def _write_panel(path: Path, dates: list[str]) -> None:
    pd.DataFrame({"date": dates, "coin_id": ["bitcoin"] * len(dates)}).to_csv(
        path, index=False
    )


def _write_marks(raw_dir: Path, last: str) -> None:
    candles = raw_dir / "candles"
    candles.mkdir(parents=True)
    index = pd.date_range("2026-11-14T00:00:00Z", last, freq="1h")
    pd.DataFrame(
        {
            "open_time": index,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
        }
    ).to_csv(candles / "BTCUSDT_mark.csv", index=False)


def test_panel_day_is_used_before_the_0100_bar_when_panel_is_current(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    raw = tmp_path / "raw"
    _write_panel(panel, ["2026-11-13", "2026-11-14"])
    _write_marks(raw, "2026-11-15T00:00:00Z")

    resolved = resolve_signal_end_date(
        panel=panel,
        raw_dir=raw,
        now=datetime(2026, 11, 15, 0, 10, tzinfo=timezone.utc),
    )

    assert resolved == pd.Timestamp("2026-11-14", tz="UTC")


def test_mark_day_wins_when_panel_is_behind(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    raw = tmp_path / "raw"
    _write_panel(panel, ["2026-11-13"])
    _write_marks(raw, "2026-11-15T22:00:00Z")

    resolved = resolve_signal_end_date(
        panel=panel,
        raw_dir=raw,
        now=datetime(2026, 11, 15, 23, 56, tzinfo=timezone.utc),
    )

    assert resolved == pd.Timestamp("2026-11-13", tz="UTC")


def test_new_panel_day_is_evaluable_before_the_0100_bar_exists(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    raw = tmp_path / "raw"
    _write_panel(panel, ["2026-11-14", "2026-11-15"])
    _write_marks(raw, "2026-11-15T22:00:00Z")

    resolved = resolve_signal_end_date(
        panel=panel,
        raw_dir=raw,
        now=datetime(2026, 11, 16, 0, 10, tzinfo=timezone.utc),
    )

    assert resolved == pd.Timestamp("2026-11-15", tz="UTC")
