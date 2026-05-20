import json
import re
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from atlas20.api._time import utc_now
from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.repositories import RunsRepo
from atlas20.api.settings import get_settings


def _app(tmp_path, monkeypatch):
    report_root = tmp_path / "reports"
    data_root = tmp_path / "data"
    report_root.mkdir()
    data_root.mkdir()
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(data_root))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'metrics.sqlite').as_posix()}")
    get_settings.cache_clear()
    return create_app()


def _access_records(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{") and "atlas20.api.access" in line]


def _metric_value(body: str, name: str, label: str) -> float:
    pattern = re.compile(rf'^{name}\{{status="{label}"\}} (?P<value>[0-9.]+)$', re.MULTILINE)
    match = pattern.search(body)
    assert match is not None
    return float(match.group("value"))


def test_metrics_endpoint_exposes_prometheus_text(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "atlas20_backtests_total" in response.text


def test_completed_run_increments_backtest_counter(tmp_path, monkeypatch, db_session: Session) -> None:
    run_id = "btk_metrics_0001"
    db_session.add(
        Run(
            run_id=run_id,
            strategy="ATLAS Adaptive v4",
            strategy_family="ATLAS",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="running",
            started_at=utc_now() - timedelta(seconds=8),
        )
    )
    db_session.flush()

    with TestClient(_app(tmp_path, monkeypatch)) as client:
        before = _metric_value(client.get("/metrics").text, "atlas20_backtests_total", "completed")
        RunsRepo(db_session).update_metrics_from_completion(
            run_id,
            return_pct=0.42,
            sharpe=1.9,
            max_dd=-0.18,
            duration_s=8,
        )
        after = _metric_value(client.get("/metrics").text, "atlas20_backtests_total", "completed")

    assert after == before + 1


def test_metrics_and_readiness_are_excluded_from_access_log(tmp_path, monkeypatch, capsys) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        assert client.get("/metrics").status_code == 200
        assert client.get("/readyz").status_code == 200
    captured = capsys.readouterr()

    assert all(record["path"] not in {"/metrics", "/readyz"} for record in _access_records(captured.out))


def test_metrics_endpoint_includes_counter_help_and_type(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        body = client.get("/metrics").text

    assert "# HELP atlas20_backtests_total" in body
    assert "# TYPE atlas20_backtests_total counter" in body
