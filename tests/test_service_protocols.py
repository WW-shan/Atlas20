from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from atlas20.api import mock_data
from atlas20.api.app import create_app
from atlas20.api.schemas import OverviewPayload
from atlas20.api.services import ConsoleService, MockConsoleService, RealConsoleService, get_console_service
from atlas20.api.settings import get_settings


def test_real_and_mock_console_services_satisfy_protocol() -> None:
    assert isinstance(RealConsoleService(), ConsoleService)
    assert isinstance(MockConsoleService(), ConsoleService)


def test_route_service_dependency_can_be_overridden(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'service-protocol.sqlite').as_posix()}")
    get_settings.cache_clear()

    class FakeOverviewService:
        def get_overview(self) -> OverviewPayload:
            payload = deepcopy(mock_data.fallback_overview)
            payload["champion"]["strategy"] = "FAKE_PROTOCOL"
            payload["champion"]["display_name"] = "Fake Protocol"
            return OverviewPayload.model_validate(payload)

    app = create_app()
    app.dependency_overrides[get_console_service] = FakeOverviewService

    with TestClient(app) as client:
        response = client.get("/api/overview")

    assert response.status_code == 200
    assert response.json()["champion"]["strategy"] == "FAKE_PROTOCOL"
