import asyncio
import json
import logging
import re
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, select

from atlas20.api import _metrics
from atlas20.api import services_report
from atlas20.api._time import utc_now
from atlas20.api.app import create_app
from atlas20.api.db.models import Run
from atlas20.api.dependencies import ratelimit
from atlas20.api.repositories import RunsRepo, get_session
from atlas20.api.repositories.runs_repo import terminal_duration_seconds
from atlas20.api.settings import get_settings
from atlas20.api.worker.queue import WorkerQueue
from atlas20.api.worker.recovery import recover_stale_runs


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


def _app_with_session(tmp_path, monkeypatch, db_session: Session):
    app = _app(tmp_path, monkeypatch)

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return app


def _access_records(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{") and "atlas20.api.access" in line]


def _metric_value(body: str, name: str, label: str) -> float:
    pattern = re.compile(rf'^{name}\{{status="{label}"\}} (?P<value>[0-9.]+)$', re.MULTILINE)
    match = pattern.search(body)
    assert match is not None
    return float(match.group("value"))


def _report_metric_value(body: str, format_name: str, status: str) -> float:
    pattern = re.compile(
        rf'^atlas20_report_generations_total\{{format="{format_name}",status="{status}"\}} (?P<value>[0-9.]+)$',
        re.MULTILINE,
    )
    match = pattern.search(body)
    return float(match.group("value")) if match is not None else 0.0


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


def test_queue_cancel_increments_cancelled_backtest_counter(tmp_path, monkeypatch, db_session: Session) -> None:
    db_session.add(
        Run(
            run_id="btk_metrics_0002",
            strategy="ATLAS Adaptive v4",
            strategy_family="ATLAS",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="queued",
            requested_cancel=True,
        )
    )
    db_session.flush()

    with TestClient(_app(tmp_path, monkeypatch)) as client:
        before = _metric_value(client.get("/metrics").text, "atlas20_backtests_total", "cancelled")
        assert WorkerQueue(db_session).claim_one() is None
        after = _metric_value(client.get("/metrics").text, "atlas20_backtests_total", "cancelled")

    assert after == before + 1


def test_recovery_increments_failed_backtest_counter(tmp_path, monkeypatch, db_session: Session) -> None:
    now = utc_now()
    for existing in db_session.exec(select(Run).where(Run.status == "running")).all():
        existing.heartbeat_at = now
        db_session.add(existing)
    db_session.add(
        Run(
            run_id="btk_metrics_0003",
            strategy="ATLAS Adaptive v4",
            strategy_family="ATLAS",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="running",
            started_at=now - timedelta(seconds=10),
            heartbeat_at=now - timedelta(seconds=120),
        )
    )
    db_session.flush()

    with TestClient(_app(tmp_path, monkeypatch)) as client:
        before = _metric_value(client.get("/metrics").text, "atlas20_backtests_total", "failed")
        assert recover_stale_runs(db_session, stale_after_seconds=60) == 1
        after = _metric_value(client.get("/metrics").text, "atlas20_backtests_total", "failed")

    assert after == before + 1


def test_recover_my_own_stale_runs_emits_backtests_total(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify recover_my_own_stale_runs increments atlas20_backtests_total{status=failed}."""
    from atlas20.api.worker.recovery import recover_my_own_stale_runs

    del monkeypatch
    my_pid = 99999
    db_session.add(
        Run(
            run_id="btk_9999",
            strategy="ATLAS Adaptive v4",
            strategy_family="ATLAS",
            universe="Top-20",
            window_start=date(2024, 1, 1),
            window_end=date(2026, 5, 18),
            status="running",
            worker_pid=my_pid,
            heartbeat_at=utc_now() - timedelta(seconds=600),
            started_at=utc_now() - timedelta(seconds=900),
        )
    )
    db_session.commit()

    before = _metrics.BACKTESTS_TOTAL.labels(status="failed")._value.get()
    recovered = recover_my_own_stale_runs(db_session, my_pid)
    after = _metrics.BACKTESTS_TOTAL.labels(status="failed")._value.get()

    assert recovered == 1
    assert after == before + 1


def test_terminal_duration_semantics_drive_histogram_observation(monkeypatch) -> None:
    observed: list[float] = []
    monkeypatch.setattr(_metrics.BACKTEST_DURATION_SECONDS, "observe", observed.append)

    authoritative = SimpleNamespace(duration_s=42.5, started_at=utc_now() - timedelta(seconds=90))
    _metrics.record_backtest_terminal("completed", terminal_duration_seconds(authoritative))
    assert observed == [42.5]

    observed.clear()
    started_only = SimpleNamespace(duration_s=None, started_at=utc_now() - timedelta(seconds=10))
    _metrics.record_backtest_terminal("completed", terminal_duration_seconds(started_only))
    assert len(observed) == 1
    assert 9.0 <= observed[0] <= 12.0

    observed.clear()
    unknown = SimpleNamespace(duration_s=None, started_at=None)
    _metrics.record_backtest_terminal("completed", terminal_duration_seconds(unknown))
    assert observed == []


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


def test_record_report_generation_ignores_unknown_report_format(caplog) -> None:
    unknown_format = "__not_a_format__"

    assert all(
        sample.labels.get("format") != unknown_format
        for metric in _metrics.REPORT_GENERATIONS_TOTAL.collect()
        for sample in metric.samples
    )

    with caplog.at_level(logging.WARNING, logger="atlas20.api._metrics"):
        _metrics.record_report_generation(unknown_format, "completed")

    assert all(
        sample.labels.get("format") != unknown_format
        for metric in _metrics.REPORT_GENERATIONS_TOTAL.collect()
        for sample in metric.samples
    )
    assert "ignoring metric for unknown report format: __not_a_format__" in caplog.text


def test_record_report_generation_ignores_unknown_report_status(caplog) -> None:
    unknown_status = "in_progress"

    assert all(
        sample.labels.get("status") != unknown_status
        for metric in _metrics.REPORT_GENERATIONS_TOTAL.collect()
        for sample in metric.samples
    )

    with caplog.at_level(logging.WARNING, logger="atlas20.api._metrics"):
        _metrics.record_report_generation("markdown", unknown_status)

    assert all(
        sample.labels.get("status") != unknown_status
        for metric in _metrics.REPORT_GENERATIONS_TOTAL.collect()
        for sample in metric.samples
    )
    assert "ignoring metric for unknown report status: in_progress" in caplog.text


def test_generate_report_without_completed_run_records_skipped_metric(
    tmp_path, monkeypatch, db_session: Session
) -> None:
    for run in db_session.exec(select(Run).where(Run.status == "completed")).all():
        run.status = "failed"
        db_session.add(run)
    db_session.flush()

    with TestClient(_app_with_session(tmp_path, monkeypatch, db_session)) as client:
        before = _report_metric_value(client.get("/metrics").text, "markdown", "skipped")
        response = client.post("/api/reports/generate", json={"formats": ["markdown"]})
        after = _report_metric_value(client.get("/metrics").text, "markdown", "skipped")

    assert response.status_code == 202
    assert response.json()["status"] == "completed"
    assert response.json()["files"] == []
    assert response.json()["warnings"] == ["no completed run available for report generation"]
    assert after == before + 1


def test_generate_report_legacy_httpexception_fallback_records_skipped_metric(
    tmp_path, monkeypatch, db_session: Session
) -> None:
    """When req.run_id is None and the auto-selected run raises HTTPException
    during generation, the legacy fallback branch must still record skipped
    metrics (mirrors the no-run path's metric emission)."""
    from atlas20.api.routes import reports as reports_route
    from fastapi import HTTPException

    def _raise(*args, **kwargs):
        raise HTTPException(status_code=404, detail="run output missing")

    monkeypatch.setattr(reports_route, "generate_run_report_with_warnings", _raise)

    with TestClient(_app_with_session(tmp_path, monkeypatch, db_session)) as client:
        before = _report_metric_value(client.get("/metrics").text, "pdf", "skipped")
        response = client.post("/api/reports/generate", json={"formats": ["pdf"]})
        after = _report_metric_value(client.get("/metrics").text, "pdf", "skipped")

    assert response.status_code == 202
    assert response.json()["status"] == "completed"
    assert response.json()["files"] == []
    assert "generation skipped" in response.json()["warnings"][0]
    assert after == before + 1


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


def test_rate_limit_handler_does_not_emit_raw_path_for_unmatched_route(monkeypatch) -> None:
    recorded: list[str] = []
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/runs/btk_0142/cancel",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "client": ("testclient", 50000),
        }
    )

    monkeypatch.setattr(ratelimit, "record_rate_limit_hit", recorded.append)
    monkeypatch.setattr(
        ratelimit,
        "_rate_limit_exceeded_handler",
        lambda request, exc: JSONResponse({"error": "limited"}, status_code=429),
    )

    response = asyncio.run(ratelimit.rate_limit_exceeded_handler(request, object()))

    assert response.status_code == 429
    assert recorded == []


def test_rate_limit_metric_is_prewarmed_and_uses_templated_route(
    tmp_path, monkeypatch, db_session: Session
) -> None:
    with TestClient(_app_with_session(tmp_path, monkeypatch, db_session)) as client:
        initial_body = client.get("/metrics").text
        statuses = [client.post("/api/runs/btk_0148/cancel").status_code for _ in range(31)]
        body = client.get("/metrics").text

    assert 'atlas20_rate_limit_hits_total{route="unmatched"} 0.0' in initial_body
    assert statuses[:30] == [202] * 30
    assert statuses[30] == 429
    assert 'atlas20_rate_limit_hits_total{route="/api/runs/{run_id}/cancel"} 1.0' in body
    assert 'route="/api/runs/btk_0148/cancel"' not in body


def test_rate_limit_metric_failure_still_returns_429(
    monkeypatch, caplog
) -> None:
    route_path = "/api/runs/{run_id}/cancel"
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/runs/btk_0148/cancel",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "client": ("testclient", 50000),
            "route": SimpleNamespace(path=route_path),
        }
    )
    counter = _metrics.RATE_LIMIT_HITS_TOTAL.labels(route=route_path)

    def fail_inc() -> None:
        raise RuntimeError("counter unavailable")

    monkeypatch.setattr(counter, "inc", fail_inc)
    monkeypatch.setattr(
        ratelimit,
        "_rate_limit_exceeded_handler",
        lambda request, exc: JSONResponse({"error": "limited"}, status_code=429),
    )

    with caplog.at_level(logging.WARNING, logger="atlas20.api._metrics"):
        response = asyncio.run(ratelimit.rate_limit_exceeded_handler(request, object()))

    assert response.status_code == 429
    assert "failed to record rate limit metric" in caplog.text


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
