"""The research window's open end is anchored to UTC, never to the host clock.

CoinMarketCap closes its daily candles at 00:00 UTC. ``end_timestamp`` used to
be the *local* date, and this host runs on Asia/Shanghai (UTC+8): for eight
hours a day it named tomorrow's UTC date, so the CMC window ran into a day
that had not started and ``_lags_last_completed_day`` expected a close that
could not exist yet - forcing a tail re-pull on every run between 00:00 and
08:00 local time.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator

import pandas as pd
import pytest

from atlas20.config import current_utc_day, latest_completed_utc_day, load_config


@pytest.fixture
def host_zone() -> Iterator[Callable[[str], None]]:
    """Switch the process time zone for one test and restore it afterwards."""
    original = os.environ.get("TZ")

    def _set(zone: str) -> None:
        os.environ["TZ"] = zone
        time.tzset()

    yield _set
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


def _zone_whose_local_date_differs_from_utc() -> str:
    """A fixed-offset zone whose calendar date is not the UTC date right now."""
    # Etc/GMT-14 is UTC+14 and Etc/GMT+12 is UTC-12 (POSIX signs are inverted).
    return "Etc/GMT-14" if pd.Timestamp.now(tz="UTC").hour >= 12 else "Etc/GMT+12"


def test_end_timestamp_is_the_utc_calendar_day_not_the_host_day(host_zone: Callable[[str], None]) -> None:
    host_zone(_zone_whose_local_date_differs_from_utc())
    config = load_config("config/base.yaml")
    assert config.end_date is None

    expected = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    assert config.end_timestamp == expected
    assert config.end_timestamp.tzinfo is None


def test_an_explicit_end_date_is_left_alone() -> None:
    config = load_config("config/base.yaml")
    config.end_date = "2024-03-15"

    assert config.end_timestamp == pd.Timestamp("2024-03-15")


@pytest.mark.parametrize(
    "now",
    [
        pd.Timestamp("2026-09-24 17:30", tz="UTC"),
        # 01:30 in Shanghai is still the previous UTC day.
        pd.Timestamp("2026-09-25 01:30", tz="Asia/Shanghai"),
        # A naive clock reading is taken to be UTC.
        pd.Timestamp("2026-09-24 17:30"),
    ],
)
def test_current_and_latest_completed_utc_day(now: pd.Timestamp) -> None:
    assert current_utc_day(now) == pd.Timestamp("2026-09-24")
    assert latest_completed_utc_day(now) == pd.Timestamp("2026-09-23")


def test_the_utc_day_turns_over_at_utc_midnight() -> None:
    assert current_utc_day(pd.Timestamp("2026-09-24 23:59:59", tz="UTC")) == pd.Timestamp("2026-09-24")
    assert current_utc_day(pd.Timestamp("2026-09-25 00:00:00", tz="UTC")) == pd.Timestamp("2026-09-25")
    assert latest_completed_utc_day(pd.Timestamp("2026-09-25 00:00:00", tz="UTC")) == pd.Timestamp("2026-09-24")
