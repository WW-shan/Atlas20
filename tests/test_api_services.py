from copy import deepcopy

import pytest

from atlas20.api import mock_data
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


def test_get_run_detail_only_returns_canonical_detail():
    from atlas20.api.services import get_run_detail

    assert get_run_detail("btk_0142") is not None
    assert get_run_detail("btk_0144") is None


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
