import json
import re

from fastapi.testclient import TestClient

from atlas20.api.app import create_app


UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


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
    records = [json.loads(line) for line in captured.out.splitlines() if line.startswith("{")]
    assert any(
        record["message"] == "request"
        and record["path"] == "/api/options"
        and record["request_id"] == "foo-123"
        for record in records
    )
