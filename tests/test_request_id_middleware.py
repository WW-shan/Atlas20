import json
import re

from fastapi.testclient import TestClient

from atlas20.api.app import create_app


UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


def _json_records(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def _access_records(output: str) -> list[dict[str, object]]:
    return [record for record in _json_records(output) if record.get("logger") == "atlas20.api.access"]


def test_request_without_request_id_gets_generated_response_header():
    client = TestClient(create_app())

    response = client.get("/api/options")

    assert response.status_code == 200
    assert UUID_HEX_RE.fullmatch(response.headers["X-Request-ID"])


def test_request_with_request_id_echoes_response_header():
    client = TestClient(create_app())

    response = client.get("/api/options", headers={"X-Request-ID": "foo-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "foo-123"


def test_invalid_request_id_is_replaced():
    client = TestClient(create_app())

    response = client.get("/api/options", headers={"X-Request-ID": "bad request id"})

    assert response.status_code == 200
    assert UUID_HEX_RE.fullmatch(response.headers["X-Request-ID"])
    assert response.headers["X-Request-ID"] != "bad request id"


def test_generated_request_ids_are_unique():
    client = TestClient(create_app())

    first = client.get("/api/options")
    second = client.get("/api/options")

    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_request_id_is_written_to_access_log(capsys):
    client = TestClient(create_app())

    response = client.get("/api/options", headers={"X-Request-ID": "foo-123"})
    captured = capsys.readouterr()

    assert response.status_code == 200
    records = _access_records(captured.out)
    assert any(
        record["message"] == "request"
        and record["path"] == "/api/options"
        and record["request_id"] == "foo-123"
        for record in records
    )


def test_access_log_records_duration(capsys):
    client = TestClient(create_app())

    response = client.get("/api/options", headers={"X-Request-ID": "foo-123"})
    captured = capsys.readouterr()

    assert response.status_code == 200
    record = next(record for record in _access_records(captured.out) if record["path"] == "/api/options")
    assert isinstance(record["duration_ms"], float)
    assert record["duration_ms"] >= 0.0


def test_access_log_excludes_health_and_metrics(capsys):
    client = TestClient(create_app())

    health_response = client.get("/healthz", headers={"X-Request-ID": "health-123"})
    metrics_response = client.get("/metrics", headers={"X-Request-ID": "metrics-123"})
    captured = capsys.readouterr()

    assert health_response.status_code == 404
    assert metrics_response.status_code == 404
    assert all(record["path"] not in {"/healthz", "/metrics"} for record in _access_records(captured.out))


def test_access_log_omits_query_string(capsys):
    client = TestClient(create_app())

    response = client.get("/api/options?api_key=secret-token", headers={"X-Request-ID": "foo-123"})
    captured = capsys.readouterr()

    assert response.status_code == 200
    record = next(record for record in _access_records(captured.out) if record["path"] == "/api/options")
    assert "secret-token" not in json.dumps(record)
