import os
from datetime import date
from datetime import datetime
from datetime import timezone

from atlas20.api import mock_data
from atlas20.api.services import get_featured_digest
from atlas20.api.settings import get_settings
from tests.conftest import write_alpha_btc_report_csvs


def _set_mtime(path, timestamp: datetime) -> None:
    epoch = timestamp.replace(tzinfo=timezone.utc).timestamp()
    path.touch()
    path.write_text("# Digest\n", encoding="utf-8")
    path.chmod(0o666)
    os.utime(path, (epoch, epoch))


def test_featured_digest_subtitle_contains_real_champion(tmp_path, monkeypatch):
    write_alpha_btc_report_csvs(tmp_path)
    _set_mtime(tmp_path / "latest" / "atlas20_report.md", datetime(2026, 6, 30, 12, 0))
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", date(2026, 6, 30).isoformat())
    get_settings.cache_clear()

    payload = get_featured_digest()

    assert "ALPHA" in payload.subtitle
    assert "—" in payload.title
    assert "ALPHA · YTD" in payload.subtitle
    assert payload.generated_at == "2026-06-30T12:00:00Z"


def test_featured_digest_falls_back_when_no_markdown_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    payload = get_featured_digest()

    assert payload.id == mock_data.fallback_featured_digest["id"]


def test_featured_digest_prefers_latest_markdown_over_unowned_archive_markdown(tmp_path, monkeypatch):
    write_alpha_btc_report_csvs(tmp_path)
    latest_md = tmp_path / "latest" / "atlas20_report.md"
    archive_md = tmp_path / "archive" / "newer_but_unowned.md"
    archive_md.parent.mkdir()
    _set_mtime(latest_md, datetime(2026, 6, 1, 12, 0))
    _set_mtime(archive_md, datetime(2026, 6, 30, 12, 0))
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", date(2026, 6, 30).isoformat())
    get_settings.cache_clear()

    payload = get_featured_digest()

    assert payload.id == "atlas20_report"
    assert payload.generated_at == "2026-06-01T12:00:00Z"


def test_featured_digest_falls_back_when_csv_is_malformed_even_if_markdown_exists(tmp_path, monkeypatch):
    latest = tmp_path / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("atlas20_report.md").write_text("# Digest\n", encoding="utf-8")
    latest.joinpath("strategy_summary.csv").write_text("strategy,sharpe\nALPHA,1.7", encoding="utf-8")
    latest.joinpath("daily_returns.csv").write_text(",ALPHA\n2026-01-01,0.01", encoding="utf-8")
    latest.joinpath("equity_curves.csv").write_text(",ALPHA\n2026-01-01,101000", encoding="utf-8")
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", date(2026, 6, 30).isoformat())
    get_settings.cache_clear()

    payload = get_featured_digest()

    assert payload.id == mock_data.fallback_featured_digest["id"]
