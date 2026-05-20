"""Sentry tests monkeypatch sentry_sdk.init to avoid accidental real SDK initialization."""

from fastapi.testclient import TestClient

from atlas20.api.app import create_app
from atlas20.api.settings import get_settings


def _configure_env(tmp_path, monkeypatch, sentry_dsn: str | None = None) -> None:
    report_root = tmp_path / "reports"
    data_root = tmp_path / "data"
    report_root.mkdir()
    data_root.mkdir()
    monkeypatch.setenv("ATLAS20_REPORT_ROOT", str(report_root))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(data_root))
    monkeypatch.setenv("ATLAS20_DB_URL", f"sqlite:///{(tmp_path / 'sentry.sqlite').as_posix()}")
    if sentry_dsn is None:
        monkeypatch.delenv("ATLAS20_SENTRY_DSN", raising=False)
    else:
        monkeypatch.setenv("ATLAS20_SENTRY_DSN", sentry_dsn)
    get_settings.cache_clear()


def test_sentry_not_initialized_without_dsn(tmp_path, monkeypatch) -> None:
    import sentry_sdk

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    _configure_env(tmp_path, monkeypatch)

    with TestClient(create_app()):
        pass

    assert calls == []


def test_sentry_initializes_with_expected_kwargs(tmp_path, monkeypatch) -> None:
    import sentry_sdk

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    _configure_env(tmp_path, monkeypatch, "https://fake@example.com/1")

    with TestClient(create_app()):
        pass

    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["dsn"] == "https://fake@example.com/1"
    assert kwargs["environment"] == "dev"
    assert kwargs["traces_sample_rate"] == 0.0
    assert kwargs["send_default_pii"] is False
    assert callable(kwargs["before_send"])
    assert [type(item).__name__ for item in kwargs["integrations"]] == ["FastApiIntegration"]


def test_sentry_before_send_redacts_sensitive_headers(tmp_path, monkeypatch) -> None:
    import sentry_sdk

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    _configure_env(tmp_path, monkeypatch, "https://fake@example.com/1")

    with TestClient(create_app()):
        pass

    callback = calls[0]["before_send"]
    event = {"request": {"headers": {"X-API-Key": "real-key", "Accept": "application/json"}}}
    scrubbed = callback(event, {})

    assert scrubbed["request"]["headers"]["X-API-Key"] == "***REDACTED***"
    assert scrubbed["request"]["headers"]["Accept"] == "application/json"
