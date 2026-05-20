from datetime import datetime, timedelta, timezone
import os

from atlas20.api import mock_data, services
from atlas20.api.settings import get_settings


def _clear_data_sources_cache(monkeypatch):
    monkeypatch.setattr(services, "_DATA_SOURCES_CACHE", None, raising=False)


def _write_raw_file(path, mtime: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    ts = mtime.timestamp()
    os.utime(path, (ts, ts))


def test_get_data_sources_falls_back_when_raw_root_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    _clear_data_sources_cache(monkeypatch)

    sources = services.get_data_sources()

    assert [source.model_dump() for source in sources] == mock_data.fallback_data_sources


def test_get_data_sources_reads_raw_provider_mtimes(tmp_path, monkeypatch):
    fixed_now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    raw_root = tmp_path / "raw"
    _write_raw_file(raw_root / "coingecko" / "snapshots" / "markets.json", fixed_now - timedelta(seconds=30))
    _write_raw_file(raw_root / "cryptocompare" / "histoday" / "BTC.json", fixed_now - timedelta(hours=2))
    _write_raw_file(raw_root / "binance" / "ticks.json", fixed_now - timedelta(days=2))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(services, "utc_now", lambda: fixed_now)
    get_settings.cache_clear()
    _clear_data_sources_cache(monkeypatch)

    sources = {source.id: source for source in services.get_data_sources()}

    assert sources["coingecko"].status == "healthy"
    assert sources["coingecko"].last_sync_seconds == 30
    assert sources["cryptocompare"].status == "degraded"
    assert sources["binance"].status == "error"
    assert sources["coinbase"].last_sync_seconds == 999999


def test_get_data_sources_uses_five_minute_cache(tmp_path, monkeypatch):
    fixed_now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    raw_file = tmp_path / "raw" / "coingecko" / "snapshots" / "markets.json"
    _write_raw_file(raw_file, fixed_now - timedelta(seconds=30))
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(services, "utc_now", lambda: fixed_now)
    get_settings.cache_clear()
    _clear_data_sources_cache(monkeypatch)

    first = {source.id: source for source in services.get_data_sources()}
    _write_raw_file(raw_file, fixed_now - timedelta(days=2))
    second = {source.id: source for source in services.get_data_sources()}
    monkeypatch.setattr(services, "utc_now", lambda: fixed_now + timedelta(seconds=301))
    third = {source.id: source for source in services.get_data_sources()}

    assert first["coingecko"].status == "healthy"
    assert second["coingecko"].status == "healthy"
    assert third["coingecko"].status == "error"


def test_get_data_sources_recomputes_when_data_root_changes_inside_cache_ttl(tmp_path, monkeypatch):
    fixed_now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _write_raw_file(root_a / "raw" / "coingecko" / "snapshots" / "markets.json", fixed_now - timedelta(seconds=30))
    _write_raw_file(root_b / "raw" / "coingecko" / "snapshots" / "markets.json", fixed_now - timedelta(days=2))
    monkeypatch.setattr(services, "utc_now", lambda: fixed_now)
    _clear_data_sources_cache(monkeypatch)

    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(root_a))
    get_settings.cache_clear()
    first = {source.id: source for source in services.get_data_sources()}
    monkeypatch.setenv("ATLAS20_DATA_ROOT", str(root_b))
    get_settings.cache_clear()
    second = {source.id: source for source in services.get_data_sources()}

    assert first["coingecko"].status == "healthy"
    assert second["coingecko"].status == "error"
