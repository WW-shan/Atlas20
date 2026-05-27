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
from tests.conftest import write_alpha_btc_report_csvs


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
    # Real DB runs without output artifacts should not borrow the mock champion curve.
    assert derived.equity_overlay.series == []

    assert get_run_detail(db_session, "btk_NONEXIST") is None


def test_get_run_detail_reads_equity_curve_from_run_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
):
    from atlas20.api.services import get_run_detail

    report_root = tmp_path / "reports"
    run_dir = report_root / "app_runs" / "btk_0146"
    run_dir.mkdir(parents=True)
    (run_dir / "equity_curve.csv").write_text(
        "date,Mean Reversion v2,BTC_BH__always_on\n"
        "2026-01-01,100,100\n"
        "2026-01-02,150,110\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    detail = get_run_detail(db_session, "btk_0146")

    assert detail is not None
    assert [point.ts for point in detail.equity_overlay.series] == ["2026-01-01", "2026-01-02"]
    assert detail.equity_overlay.series[0].atlas == 0
    assert detail.equity_overlay.series[0].btc == 0
    assert detail.equity_overlay.series[1].atlas == 50
    assert detail.equity_overlay.series[1].btc == 10


def test_get_run_detail_reads_tab_artifacts_and_kpi_from_run_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
):
    from atlas20.api.services import get_run_detail

    report_root = tmp_path / "reports"
    run_dir = report_root / "app_runs" / "btk_0146"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.csv").write_text(
        "strategy,total_return,cagr,sharpe,sortino,max_drawdown,calmar,monthly_win_rate,"
        "annualized_turnover,avg_turnover,average_holdings\n"
        "Mean Reversion v2,0.55,0.11,2.22,3.33,-0.12,0.92,0.64,1.5,0.25,4\n",
        encoding="utf-8",
    )
    (run_dir / "equity_curve.csv").write_text(
        "date,Mean Reversion v2,BTC_BH__always_on\n"
        "2026-01-01,100,100\n"
        "2026-01-02,155,105\n",
        encoding="utf-8",
    )
    (run_dir / "drawdowns.csv").write_text(
        "date,Mean Reversion v2,BTC_BH__always_on\n"
        "2026-01-01,0,0\n"
        "2026-01-02,-0.12,-0.05\n",
        encoding="utf-8",
    )
    (run_dir / "daily_returns.csv").write_text(
        "date,Mean Reversion v2,BTC_BH__always_on\n"
        "2026-01-01,0,0\n"
        "2026-01-02,0.02,0.01\n",
        encoding="utf-8",
    )
    (run_dir / "turnover_summary.csv").write_text(
        "strategy,annualized_turnover,avg_turnover_per_rebalance,average_holdings\n"
        "Mean Reversion v2,1.5,0.25,4\n"
        "Other Strategy,2.5,0.5,8\n",
        encoding="utf-8",
    )
    (run_dir / "selection_history.csv").write_text(
        "rebalance_date,strategy,coin_id,coin_rank,coin_score,coin_weight\n"
        "2026-01-15,Mean Reversion v2,solana,1,0.91,0.5\n"
        "2026-01-15,Mean Reversion v2,bitcoin,2,0.88,0.5\n"
        "2026-01-15,Other Strategy,ethereum,1,0.8,1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    detail = get_run_detail(db_session, "btk_0146")

    assert detail is not None
    assert detail.selected_strategy == "Mean Reversion v2"
    assert detail.kpi.cagr == 0.11
    assert detail.kpi.sharpe == 2.22
    assert detail.kpi.sortino == 3.33
    assert detail.kpi.max_dd == -0.12
    assert detail.kpi.calmar == 0.92
    assert detail.kpi.win_rate == 0.64
    assert [point.atlas for point in detail.drawdown_series] == [0, -12]
    assert [point.btc for point in detail.return_series] == [0, 1]
    assert detail.turnover_rows[0].strategy == "Mean Reversion v2"
    assert detail.turnover_rows[0].annualized_turnover == 1.5
    assert [row.coin_id for row in detail.trade_rows] == ["solana", "bitcoin"]


def test_list_runs_uses_artifact_metrics_and_selected_strategy_for_history_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
):
    run = RunsRepo(db_session).create(
        Run(
            run_id="btk_9997",
            strategy="Mean Reversion v2",
            strategy_family="Other",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="completed",
            return_pct=9.0,
            sharpe=9.0,
            max_dd=-0.99,
            spark="[]",
            created_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
        )
    )
    report_root = tmp_path / "reports"
    run_dir = report_root / "app_runs" / run.run_id
    run_dir.mkdir(parents=True)
    (run_dir / "summary.csv").write_text(
        "strategy,total_return,cagr,sharpe,sortino,max_drawdown,calmar,monthly_win_rate\n"
        "Other Leader,0.50,0.20,1.00,1.50,-0.10,2.00,0.40\n"
        "Mean Reversion v2,0.21,0.11,1.23,1.77,-0.15,0.73,0.33\n",
        encoding="utf-8",
    )
    (run_dir / "equity_curve.csv").write_text(
        "date,Mean Reversion v2,BTC_BH__always_on\n"
        "2026-01-01,100,100\n"
        "2026-01-02,105,101\n"
        "2026-01-03,110,102\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    rows, total = list_runs(db_session, q="btk_9997", date_range="all")

    assert total == 1
    assert rows[0].strategy == "Mean Reversion v2"
    assert rows[0].selected_strategy == "Mean Reversion v2"
    assert rows[0].return_pct == 0.21
    assert rows[0].sharpe == 1.23
    assert rows[0].max_dd == -0.15
    assert rows[0].spark == [0.0, 5.0, 10.0]


@pytest.mark.parametrize(
    ("sort", "first_id"),
    [
        ("recent", "r2"),
        ("oldest", "r3"),
        ("size", "r3"),
        ("type", "r3"),
    ],
)
def test_list_reports_sorts_archive(sort: str, first_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    get_settings.cache_clear()

    rows = list_reports(sort)

    assert rows[0].id == first_id


def test_list_reports_discovers_report_files_when_db_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
):
    report_root = tmp_path / "reports"
    latest = report_root / "latest"
    latest.mkdir(parents=True)
    digest = latest / "atlas20_report.md"
    digest.write_text("# Real report\n", encoding="utf-8")
    png = latest / "equity_curves.png"
    png.write_bytes(b"png")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    reports = list_reports("recent", db_session)

    titles = [report.title for report in reports]
    assert any("atlas20_report.md" in title for title in titles)
    assert any(report.thumbnail == "equity" for report in reports)
    assert all(report.id not in {"r1", "r2", "r3", "r4", "r5", "r6"} for report in reports)


def test_list_reports_sorts_discovered_report_files_by_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
):
    report_root = tmp_path / "reports"
    latest = report_root / "latest"
    latest.mkdir(parents=True)
    (latest / "small.md").write_text("small\n", encoding="utf-8")
    (latest / "large.csv").write_text("x" * 100, encoding="utf-8")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    get_settings.cache_clear()

    reports = list_reports("size", db_session)

    assert reports[0].title == "large.csv"


def test_overview_data_source_real(tmp_path, monkeypatch):
    write_alpha_btc_report_csvs(tmp_path / "reports")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    get_settings.cache_clear()

    payload = services.get_overview()

    assert payload.data_source == "real"


def test_overview_data_source_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    get_settings.cache_clear()

    payload = services.get_overview()

    assert payload.data_source == "fallback"


def test_get_universe_timeline_falls_back_on_missing_data(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level("WARNING", logger="atlas20.api.services")

    payload = services.get_universe_timeline()

    assert payload.data_source == "fallback"
    dumped = payload.model_dump()
    dumped.pop("data_source", None)
    assert dumped == mock_data.fallback_universe_timeline
    assert "Falling back to mock universe timeline" in caplog.text


def test_universe_data_source_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    payload = services.get_universe_timeline()

    assert payload.data_source == "fallback"


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
    # Point project_root at an empty dir too so the config/*.yaml fallback
    # finds nothing and we get the pure mock-options payload. The default
    # project_root is the repo root, which has config/*.yaml that would
    # override mock presets with real preset slugs.
    monkeypatch.setenv("ATLAS20_PROJECT_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level("WARNING", logger="atlas20.api.services")

    payload = get_options_payload()

    assert payload.model_dump() == mock_data.fallback_options
    assert "Falling back to mock options" in caplog.text


def test_load_options_uses_config_yaml_slugs_when_reports_missing(tmp_path, monkeypatch, caplog):
    project_root = tmp_path / "project"
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True)
    for slug in ("base", "five_year_2020_2024"):
        (config_dir / f"{slug}.yaml").write_text("project_name: x\n", encoding="utf-8")
    (config_dir / "sectors.yaml").write_text("sectors: []\n", encoding="utf-8")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_PROJECT_ROOT", str(project_root))
    get_settings.cache_clear()
    caplog.set_level("WARNING", logger="atlas20.api.services")

    payload = get_options_payload()

    assert [preset.slug for preset in payload.presets] == ["base", "five_year_2020_2024"]
    assert [preset.display_name for preset in payload.presets] == ["Base Config", "Five Year 2020 2024"]
    assert "Falling back to mock options" in caplog.text


def test_get_compare_falls_back_when_reports_missing(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level("WARNING", logger="atlas20.api.services")

    payload = get_compare(["atlas"], "YTD")

    assert payload.model_dump() == services._get_compare_mock(["atlas"], "YTD").model_dump()
    assert "Falling back to mock compare" in caplog.text


def test_compare_data_source_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    payload = get_compare(["atlas"], "YTD")

    assert payload.data_source == "fallback"


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
