import json
import logging
import re
from datetime import date, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from atlas20.api import _metrics
from atlas20.api import services_report
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


def test_record_backtest_terminal_swallows_counter_errors(monkeypatch, caplog) -> None:
    counter = _metrics.BACKTESTS_TOTAL.labels(status="completed")

    def fail_inc() -> None:
        raise RuntimeError("counter unavailable")

    monkeypatch.setattr(counter, "inc", fail_inc)

    with caplog.at_level(logging.WARNING, logger="atlas20.api._metrics"):
        _metrics.record_backtest_terminal("completed", 42.0)

    assert "failed to record backtest terminal metric" in caplog.text


def test_unknown_report_format_is_rejected_without_custom_metric_label(
    tmp_path, monkeypatch, db_session: Session
) -> None:
    unknown_format = "__not_a_format__"
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        response = client.post("/api/reports/generate", json={"run_id": "btk_0142", "formats": [unknown_format]})
        assert response.status_code == 422

        with pytest.raises(HTTPException) as exc_info:
            services_report.generate_run_report_with_warnings(
                "btk_0142",
                {unknown_format},
                session=db_session,
                settings=get_settings(),
            )

        assert exc_info.value.status_code == 422
        assert f'format="{unknown_format}"' not in client.get("/metrics").text


def test_report_generation_metric_failure_is_logged_without_breaking_flow(
    tmp_path, monkeypatch, caplog, db_session: Session
) -> None:
    report_root = tmp_path / "reports"
    data_root = tmp_path / "data"
    report_root.mkdir()
    data_root.mkdir()
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(data_root))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'report-metric.sqlite').as_posix()}")
    get_settings.cache_clear()

    run_dir = report_root / "app_runs" / "btk_0142"
    run_dir.mkdir(parents=True)

    def fake_generate_markdown(run_id, run_dir_arg, run_params, settings):
        del run_id, run_params, settings
        path = run_dir_arg / "digest.md"
        path.write_text("# Digest\n", encoding="utf-8")
        return path

    def fail_inc() -> None:
        raise RuntimeError("counter unavailable")

    counter = _metrics.REPORT_GENERATIONS_TOTAL.labels(format="markdown", status="completed")
    monkeypatch.setattr(services_report, "_generate_markdown", fake_generate_markdown)
    monkeypatch.setattr(counter, "inc", fail_inc)

    with caplog.at_level(logging.WARNING, logger="atlas20.api._metrics"):
        result = services_report.generate_run_report_with_warnings(
            "btk_0142",
            {"markdown"},
            session=db_session,
            settings=get_settings(),
        )

    assert [file.kind for file in result.files] == ["markdown"]
    assert "failed to record report generation metric" in caplog.text


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
