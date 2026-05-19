from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlmodel import Session

from atlas20.api import mock_data
from atlas20.api import services
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import get_settings
from atlas20.api.services import (
    get_compare,
    get_options_payload,
    list_reports,
    list_runs,
    register_new_backtest,
    toggle_run_favorite,
)


def test_list_runs_filters_by_query(db_session: Session):
    rows, total = list_runs(db_session, q="ATLAS", date_range="all")

    assert total == 5
    assert rows
    assert all("ATLAS" in row.strategy for row in rows)


def test_list_runs_filters_by_status_chip(db_session: Session):
    rows, total = list_runs(db_session, chips=["completed"], date_range="all")

    assert total == 10
    assert rows
    assert all(row.status == "completed" for row in rows)


def test_list_runs_filters_by_family_chip(db_session: Session):
    rows, total = list_runs(db_session, chips=["ATLAS"], date_range="all")

    assert total == 5
    assert rows
    assert all(row.strategy_family == "ATLAS" for row in rows)


def test_list_runs_atlas_chip_excludes_non_family_decoy(db_session: Session):
    RunsRepo(db_session).create(
        Run(
            run_id="btk_9998",
            strategy="ATLAS_LIKE_DECOY",
            strategy_family="Other",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="completed",
            created_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        )
    )

    rows, total = list_runs(db_session, chips=["ATLAS"], date_range="all")

    assert total == 5
    assert rows
    assert all(row.strategy != "ATLAS_LIKE_DECOY" for row in rows)
    assert all(row.strategy_family == "ATLAS" for row in rows)


def test_list_runs_filters_by_combined_chips(db_session: Session):
    rows, total = list_runs(db_session, chips=["ATLAS", "completed"], date_range="all")

    assert total == 4
    assert rows
    assert all(row.strategy_family == "ATLAS" and row.status == "completed" for row in rows)


def test_list_runs_filters_by_favorited_chip(db_session: Session):
    rows, total = list_runs(db_session, chips=["favorited"], date_range="all")

    assert total == 2
    assert rows
    assert all(row.favorited for row in rows)


def test_list_runs_filters_by_strategy_substring_chip(db_session: Session):
    RunsRepo(db_session).create(
        Run(
            run_id="btk_9999",
            strategy="ALPHA_MOMENTUM_LEAD_v1",
            strategy_family="Other",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="completed",
            created_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        )
    )

    rows, total = list_runs(db_session, chips=["MOMENTUM_LEAD"], date_range="all")

    assert total == 1
    assert rows[0].strategy == "ALPHA_MOMENTUM_LEAD_v1"


def test_list_runs_filters_by_date_range_cutoff(db_session: Session):
    RunsRepo(db_session).update("btk_0135", created_at=datetime(2026, 5, 1, tzinfo=timezone.utc))

    rows, total = list_runs(db_session, date_range="7d")

    assert total == 13
    assert all(row.run_id != "btk_0135" for row in rows)


def test_list_runs_paginates_rows(db_session: Session):
    page_one, total = list_runs(db_session, date_range="all", page=1, page_size=5)
    page_two, _ = list_runs(db_session, date_range="all", page=2, page_size=5)

    assert total == 14
    assert len(page_one) == 5
    assert len(page_two) == 5
    assert page_one[-1].run_id == "btk_0144"
    assert page_two[0].run_id == "btk_0143"


def test_toggle_run_favorite_returns_to_original_value(db_session: Session):
    row = RunsRepo(db_session).get("btk_0142")
    assert row is not None
    original = row.favorited

    first = toggle_run_favorite(db_session, "btk_0142")
    second = toggle_run_favorite(db_session, "btk_0142")

    assert first == {"run_id": "btk_0142", "favorited": (not original)}
    assert second == {"run_id": "btk_0142", "favorited": original}


def test_get_run_detail_returns_derived_kpi_for_listed_runs(db_session: Session):
    from atlas20.api.services import get_run_detail

    canonical = get_run_detail(db_session, "btk_0142")
    assert canonical is not None and canonical.kpi.sharpe == 3.42
    assert canonical.kpi.sortino == mock_data.fallback_run_detail["kpi"]["sortino"]
    assert canonical.kpi.win_rate == mock_data.fallback_run_detail["kpi"]["win_rate"]
    assert canonical.kpi.calmar == mock_data.fallback_run_detail["kpi"]["calmar"]

    derived = get_run_detail(db_session, "btk_0146")
    assert derived is not None
    # derived from row.sharpe=1.94, row.max_dd=-0.184, row.return_pct=0.416
    assert derived.kpi.sharpe == 1.94
    assert derived.kpi.max_dd == -0.184
    assert derived.kpi.cagr == 0.416
    # equity_overlay falls back to canonical series (mock backend simplification)
    assert len(derived.equity_overlay.series) > 0

    assert get_run_detail(db_session, "btk_NONEXIST") is None


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


def test_load_options_falls_back_on_missing_data(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level("WARNING", logger="atlas20.api.services")

    payload = get_options_payload()

    assert payload.model_dump() == mock_data.fallback_options
    assert "Falling back to mock options" in caplog.text


def test_get_compare_falls_back_when_reports_missing(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level("WARNING", logger="atlas20.api.services")

    payload = get_compare(["atlas"], "YTD")

    assert payload.model_dump() == services._get_compare_mock(["atlas"], "YTD").model_dump()
    assert "Falling back to mock compare" in caplog.text


def test_get_compare_routes_anchor_through_today(monkeypatch):
    monkeypatch.delenv("ATLAS20_ANCHOR_DATE", raising=False)
    get_settings.cache_clear()
    anchor = date(2026, 5, 19)
    seen_anchor_dates = []

    def fake_load_compare_from_reports(settings, ids, range_):
        seen_anchor_dates.append(settings.anchor_date)
        return deepcopy(mock_data.fallback_compare)

    monkeypatch.setattr(services, "today", lambda: anchor)
    monkeypatch.setattr(services, "load_compare_from_reports", fake_load_compare_from_reports)

    payload = get_compare(["atlas"], "YTD")

    assert seen_anchor_dates == [anchor]
    assert set(payload.metrics.cagr) == set(mock_data.fallback_compare["metrics"]["cagr"])


def test_register_new_backtest_raises_when_base_yaml_missing(tmp_path: Path, monkeypatch, db_session: Session):
    settings = get_settings()
    monkeypatch.setattr(settings, "project_root", tmp_path)
    _, before_total = RunsRepo(db_session).list(date_cutoff=None)
    config = BacktestConfig.model_validate(
        {
            "preset": "ATLAS Adaptive v3",
            "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
            "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
            "allocation": {"positionPct": 5.0, "slots": 10},
            "costs": {"feeBps": 10, "slippageBps": 5},
        }
    )

    with pytest.raises(ValueError, match="base.yaml"):
        register_new_backtest(db_session, config)

    _, after_total = RunsRepo(db_session).list(date_cutoff=None)
    assert after_total == before_total
