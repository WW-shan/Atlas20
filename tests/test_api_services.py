from copy import deepcopy
from datetime import date
from datetime import datetime
from datetime import timezone

import pytest

from atlas20.api import mock_data
from atlas20.api import services
from atlas20.api.settings import get_settings
from atlas20.api.services import list_reports, list_runs, toggle_run_favorite


MUTABLE_FIXTURES = {
    "fallback_runs_queue": deepcopy(mock_data.fallback_runs_queue),
    "fallback_runs_list": deepcopy(mock_data.fallback_runs_list),
    "fallback_run_detail": deepcopy(mock_data.fallback_run_detail),
}


@pytest.fixture(autouse=True)
def restore_mock_data():
    yield
    mock_data.fallback_runs_queue[:] = deepcopy(MUTABLE_FIXTURES["fallback_runs_queue"])
    mock_data.fallback_runs_list[:] = deepcopy(MUTABLE_FIXTURES["fallback_runs_list"])
    mock_data.fallback_run_detail.clear()
    mock_data.fallback_run_detail.update(deepcopy(MUTABLE_FIXTURES["fallback_run_detail"]))


def test_list_runs_filters_by_query():
    rows, total = list_runs(q="ATLAS", date_range="all")

    assert total == 5
    assert rows
    assert all("ATLAS" in row.strategy for row in rows)


def test_list_runs_filters_by_status_chip():
    rows, total = list_runs(chips=["completed"], date_range="all")

    assert total == 10
    assert rows
    assert all(row.status == "completed" for row in rows)


def test_list_runs_filters_by_family_chip():
    rows, total = list_runs(chips=["ATLAS"], date_range="all")

    assert total == 5
    assert rows
    assert all(row.strategy_family == "ATLAS" for row in rows)


def test_list_runs_filters_by_combined_chips():
    rows, total = list_runs(chips=["ATLAS", "completed"], date_range="all")

    assert total == 4
    assert rows
    assert all(row.strategy_family == "ATLAS" and row.status == "completed" for row in rows)


def test_list_runs_filters_by_date_range_cutoff():
    mock_data.fallback_runs_list[-1]["created_at"] = "2026-05-01T00:00:00Z"

    rows, total = list_runs(date_range="7d")

    assert total == 13
    assert all(row.run_id != "btk_0135" for row in rows)


def test_today_uses_anchor_date_override(monkeypatch):
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", "2026-01-02")
    get_settings.cache_clear()

    assert services._today() == date(2026, 1, 2)


def test_today_fallback_uses_utc(monkeypatch):
    monkeypatch.delenv("ATLAS20_ANCHOR_DATE", raising=False)
    get_settings.cache_clear()
    seen_timezones = []

    class FrozenDateTime:
        @classmethod
        def now(cls, tz=None):
            seen_timezones.append(tz)
            return datetime(2026, 5, 19, 0, 30, tzinfo=tz)

    monkeypatch.setattr(services, "datetime", FrozenDateTime)

    assert services._today() == date(2026, 5, 19)
    assert seen_timezones == [timezone.utc]


def test_list_runs_paginates_rows():
    page_one, total = list_runs(date_range="all", page=1, page_size=5)
    page_two, _ = list_runs(date_range="all", page=2, page_size=5)

    assert total == 14
    assert len(page_one) == 5
    assert len(page_two) == 5
    assert page_one[-1].run_id == "btk_0144"
    assert page_two[0].run_id == "btk_0143"


def test_toggle_run_favorite_returns_to_original_value():
    original = mock_data.fallback_runs_list[6]["favorited"]

    first = toggle_run_favorite("btk_0142")
    second = toggle_run_favorite("btk_0142")

    assert first == {"run_id": "btk_0142", "favorited": (not original)}
    assert second == {"run_id": "btk_0142", "favorited": original}


def test_get_run_detail_returns_derived_kpi_for_listed_runs():
    from atlas20.api.services import get_run_detail

    canonical = get_run_detail("btk_0142")
    assert canonical is not None and canonical.kpi.sharpe == 3.42

    derived = get_run_detail("btk_0146")
    assert derived is not None
    # derived from row.sharpe=1.94, row.max_dd=-0.184, row.return_pct=0.416
    assert derived.kpi.sharpe == 1.94
    assert derived.kpi.max_dd == -0.184
    assert derived.kpi.cagr == 0.416
    # equity_overlay falls back to canonical series (mock backend simplification)
    assert len(derived.equity_overlay.series) > 0

    assert get_run_detail("btk_NONEXIST") is None


@pytest.mark.parametrize(
    ("sort", "first_id"),
    [
        ("recent", "r2"),
        ("oldest", "r3"),
        ("size", "r3"),
        ("type", "r3"),
    ],
)
def test_list_reports_sorts_archive(sort: str, first_id: str):
    rows = list_reports(sort)

    assert rows[0].id == first_id


def test_get_universe_timeline_falls_back_on_missing_data(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level("WARNING", logger="atlas20.api.services")

    payload = services.get_universe_timeline()

    assert payload.model_dump() == mock_data.fallback_universe_timeline
    assert "Falling back to mock universe timeline" in caplog.text


def test_get_data_alerts_falls_back_on_missing_data(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level("WARNING", logger="atlas20.api.services")

    alerts = services.get_data_alerts()

    assert [alert.model_dump() for alert in alerts] == mock_data.fallback_data_alerts
    assert "Falling back to mock data alerts" in caplog.text
