import os
from datetime import date
from datetime import datetime
from datetime import timezone

from atlas20.api import mock_data
from atlas20.api.services import get_featured_digest
from atlas20.api.settings import get_settings


SUMMARY_HEADER = (
    "strategy,total_return,cagr,annualized_volatility,sharpe,sortino,max_drawdown,"
    "calmar,monthly_win_rate,annualized_turnover,avg_turnover_per_rebalance,average_holdings"
)


def _write_report_csvs(report_root) -> None:
    latest = report_root / "latest"
    latest.mkdir(parents=True)
    latest.joinpath("strategy_summary.csv").write_text(
        "\n".join(
            [
                SUMMARY_HEADER,
                "ALPHA,0.50,0.20,0.30,1.70,2.00,-0.20,1.00,0.60,4.00,0.50,2.00",
                "BTC_BH__always_on,0.30,0.15,0.35,0.90,1.20,-0.30,0.50,0.52,0.20,1.00,1.00",
            ]
        ),
        encoding="utf-8",
    )
    latest.joinpath("daily_returns.csv").write_text(
        "\n".join(
            [
                ",ALPHA,BTC_BH__always_on",
                "2026-01-01,0.01,0.005",
                "2026-02-01,0.02,0.006",
                "2026-03-01,-0.01,-0.002",
                "2026-04-01,0.03,0.01",
                "2026-05-01,0.00,0.00",
                "2026-06-01,0.01,0.003",
            ]
        ),
        encoding="utf-8",
    )
    latest.joinpath("equity_curves.csv").write_text(
        "\n".join(
            [
                ",ALPHA,BTC_BH__always_on",
                "2026-01-01,101000,100500",
                "2026-02-01,103020,101103",
                "2026-03-01,101989.8,100900.8",
                "2026-04-01,105049.49,101909.81",
                "2026-05-01,105049.49,101909.81",
                "2026-06-01,106099.98,102215.54",
            ]
        ),
        encoding="utf-8",
    )


def _set_mtime(path, timestamp: datetime) -> None:
    epoch = timestamp.replace(tzinfo=timezone.utc).timestamp()
    path.touch()
    path.write_text("# Digest\n", encoding="utf-8")
    path.chmod(0o666)
    os.utime(path, (epoch, epoch))


def test_featured_digest_subtitle_contains_real_champion(tmp_path, monkeypatch):
    _write_report_csvs(tmp_path)
    _set_mtime(tmp_path / "latest" / "atlas20_report.md", datetime(2026, 6, 30, 12, 0))
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", date(2026, 6, 30).isoformat())
    get_settings.cache_clear()

    payload = get_featured_digest()

    assert "ALPHA" in payload.subtitle
    assert payload.generated_at == "2026-06-30T12:00:00Z"


def test_featured_digest_falls_back_when_no_markdown_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    get_settings.cache_clear()

    payload = get_featured_digest()

    assert payload.id == mock_data.fallback_featured_digest["id"]


def test_featured_digest_selects_newest_markdown_by_mtime(tmp_path, monkeypatch):
    _write_report_csvs(tmp_path)
    old_md = tmp_path / "latest" / "old.md"
    new_md = tmp_path / "archive" / "new.md"
    new_md.parent.mkdir()
    _set_mtime(old_md, datetime(2026, 6, 1, 12, 0))
    _set_mtime(new_md, datetime(2026, 6, 30, 12, 0))
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ATLAS20_ANCHOR_DATE", date(2026, 6, 30).isoformat())
    get_settings.cache_clear()

    payload = get_featured_digest()

    assert payload.id == "new"
    assert payload.generated_at == "2026-06-30T12:00:00Z"


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
