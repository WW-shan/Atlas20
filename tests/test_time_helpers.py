from __future__ import annotations

from datetime import date, datetime, timezone

from atlas20.api import _time
from atlas20.api.settings import get_settings


def test_today_honors_settings_anchor_date(monkeypatch):
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", "2026-01-02")
    get_settings.cache_clear()

    assert _time.today() == date(2026, 1, 2)


def test_today_falls_back_to_utc_date(monkeypatch):
    monkeypatch.delenv("ATLAS20_ANCHOR_DATE", raising=False)
    get_settings.cache_clear()
    seen_timezones = []

    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            seen_timezones.append(tz)
            return datetime(2026, 5, 20, 0, 30, tzinfo=tz)

    monkeypatch.setattr(_time, "datetime", FrozenDateTime)

    assert _time.today() == date(2026, 5, 20)
    assert seen_timezones == [timezone.utc]


def test_utc_now_iso_returns_z_suffix(monkeypatch):
    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 2, 3, 4, 5, 987654, tzinfo=tz)

    monkeypatch.setattr(_time, "datetime", FrozenDateTime)

    assert _time.utc_now_iso() == "2026-01-02T03:04:05Z"


def test_utc_now_returns_aware_utc_datetime(monkeypatch):
    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 2, 3, 4, 5, 987654, tzinfo=tz)

    monkeypatch.setattr(_time, "datetime", FrozenDateTime)

    value = _time.utc_now()

    assert value == datetime(2026, 1, 2, 3, 4, 5, 987654, tzinfo=timezone.utc)
    assert value.tzinfo is timezone.utc


def test_utc_iso_from_timestamp_formats_unix_epoch():
    assert _time.utc_iso_from_timestamp(0) == "1970-01-01T00:00:00Z"
