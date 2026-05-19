import logging
from datetime import date

from atlas20.api import mock_data
from atlas20.api.services import get_overview
from atlas20.api.settings import get_settings
from tests.conftest import write_alpha_btc_report_csvs


def test_get_overview_returns_real_data_when_report_csvs_exist(tmp_path, monkeypatch):
    write_alpha_btc_report_csvs(tmp_path)
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", date(2026, 6, 30).isoformat())
    get_settings.cache_clear()

    payload = get_overview()

    assert payload.champion.strategy == "ALPHA"
    assert payload.hero_kpi.ytdReturn != mock_data.fallback_overview["hero_kpi"]["ytdReturn"]


def test_get_overview_falls_back_with_warning_when_report_root_is_empty(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level(logging.WARNING, logger="atlas20.api.services")

    payload = get_overview()

    assert payload.champion.strategy == mock_data.fallback_overview["champion"]["strategy"]
    assert "Falling back to mock overview" in caplog.text


def test_get_overview_falls_back_with_warning_when_csv_is_malformed(tmp_path, monkeypatch, caplog):
    latest = tmp_path / "latest"
    latest.mkdir()
    latest.joinpath("strategy_summary.csv").write_text("strategy,sharpe\nALPHA,1.7", encoding="utf-8")
    latest.joinpath("daily_returns.csv").write_text(",ALPHA\n2026-01-01,0.01", encoding="utf-8")
    latest.joinpath("equity_curves.csv").write_text(",ALPHA\n2026-01-01,101000", encoding="utf-8")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    get_settings.cache_clear()
    caplog.set_level(logging.WARNING, logger="atlas20.api.services")

    payload = get_overview()

    assert payload.champion.strategy == mock_data.fallback_overview["champion"]["strategy"]
    assert "Falling back to mock overview" in caplog.text
