"""Daily data freshness detection and API surfacing."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path

from atlas20.api import data_freshness as freshness_module
from atlas20.api.data_freshness import evaluate_data_freshness, freshness_alert, write_refresh_state
from atlas20.api.settings import Settings


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "data_root": tmp_path,
        "daily_refresh_enabled": True,
        "daily_refresh_hour_utc": 2,
        "daily_refresh_minute_utc": 0,
        "daily_refresh_grace_minutes": 60,
        "data_freshness_max_primary_lag_days": 2,
        "data_freshness_max_no_advance_days": 2,
        "data_freshness_min_primary_coverage": 0.9,
    }
    values.update(overrides)
    return Settings(**values)


def _write_cmc_days(root: Path, days: list[str], *, coin_id: int = 1) -> None:
    directory = root / "raw" / "coinmarketcap" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    payload = [{"timeOpen": f"{day}T00:00:00.000Z", "quote": {"close": 1.0, "marketCap": 1.0}} for day in days]
    (directory / f"{coin_id}_0_0.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_cmc_day(root: Path, day: str, *, coin_id: int = 1) -> None:
    _write_cmc_days(root, [day], coin_id=coin_id)


def _write_coingecko_day(root: Path, day: str) -> None:
    directory = root / "raw" / "coingecko" / "market_chart"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)
    payload = {"prices": [[timestamp, 1.0]]}
    (directory / "bitcoin_365d.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_binance_day(root: Path, day: str, *, pair: str = "BTCUSDT") -> None:
    """Binance caches klines as arrays keyed by millisecond open time."""
    directory = root / "raw" / "binance" / "candles"
    directory.mkdir(parents=True, exist_ok=True)
    opened = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)
    row = [opened, "0", "0", "0", "1", "1", opened + 86_399_999, "1000000", 1, "0", "0", "0"]
    (directory / f"{pair}_2025-08-17_2026-09-21.json").write_text(json.dumps([row]), encoding="utf-8")


def _write_gate_day(root: Path, day: str, *, pair: str = "BTC_USDT") -> None:
    """Gate.io caches the same shape, but in seconds rather than milliseconds."""
    directory = root / "raw" / "gateio" / "candles"
    directory.mkdir(parents=True, exist_ok=True)
    opened = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())
    row = [opened, "1", "1", "1", "1", "1", "true"]
    (directory / f"{pair}_400.json").write_text(json.dumps([row]), encoding="utf-8")


def test_source_dates_read_both_exchange_venues(tmp_path):
    """Gate.io reports seconds and Binance milliseconds; both must land on the
    right day rather than a day in 1970 or 58000."""
    _write_gate_day(tmp_path, "2026-09-20")
    _write_binance_day(tmp_path, "2026-09-21")

    dates = freshness_module._source_dates(tmp_path / "raw")

    assert dates["gateio"].isoformat() == "2026-09-20"
    assert dates["binance"].isoformat() == "2026-09-21"


def test_missing_refresh_after_deadline_is_reported(tmp_path):
    settings = _settings(tmp_path)
    now = datetime(2026, 9, 21, 4, 0, tzinfo=timezone.utc)

    status = evaluate_data_freshness(settings, now=now)

    assert status["status"] == "missing"
    assert status["deadline"] == "2026-09-21T03:00:00Z"


def test_refresh_before_deadline_is_pending_not_failed(tmp_path):
    settings = _settings(tmp_path)
    now = datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc)

    status = evaluate_data_freshness(settings, now=now)

    assert status["status"] == "pending"


def test_completed_refresh_today_is_ok(tmp_path):
    settings = _settings(tmp_path)
    _write_cmc_day(tmp_path, "2026-09-19")
    _write_coingecko_day(tmp_path, "2026-09-20")
    write_refresh_state(
        settings,
        run_id="btk_9001",
        status="completed",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert status["status"] == "ok"
    assert status["latest_primary_date"] == "2026-09-19"
    assert status["latest_independent_date"] == "2026-09-20"
    assert status["last_success_at"] == "2026-09-21T02:10:00Z"


def test_primary_data_lag_beyond_limit_is_stale(tmp_path):
    settings = _settings(tmp_path, data_freshness_max_primary_lag_days=2)
    _write_cmc_day(tmp_path, "2026-09-17")
    write_refresh_state(
        settings,
        run_id="btk_9002",
        status="completed",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert status["status"] == "stale"
    assert "lag" in status["reason"]


def test_a_panel_one_day_old_is_stale_by_default(tmp_path):
    """The default lag budget must be one day, not two.

    CMC finalises day D's close after 00:00 UTC on D+1, so a healthy feed
    always carries yesterday. A date one further day back means the ranks being
    traded were computed from a day-old panel - the exact failure the daily
    refresh exists to prevent - and it must not read as healthy just because
    today's job reported "completed".
    """
    settings = Settings(
        data_root=tmp_path,
        daily_refresh_enabled=True,
        daily_refresh_hour_utc=2,
        daily_refresh_minute_utc=0,
        daily_refresh_grace_minutes=60,
    )
    _write_cmc_day(tmp_path, "2026-09-19")
    write_refresh_state(
        settings,
        run_id="btk_9010",
        status="completed",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert settings.data_freshness_max_primary_lag_days == 1
    assert status["status"] == "stale"
    assert "lag" in status["reason"]


def test_primary_data_date_in_the_future_is_stale(tmp_path):
    settings = _settings(tmp_path)
    _write_cmc_day(tmp_path, "2026-09-22")
    write_refresh_state(
        settings,
        run_id="btk_9008",
        status="completed",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert status["status"] == "stale"
    assert "future" in status["reason"]


def test_primary_date_requires_coverage_across_cached_assets(tmp_path):
    settings = _settings(tmp_path, data_freshness_min_primary_coverage=0.9)
    _write_cmc_days(tmp_path, ["2026-09-19", "2026-09-20"], coin_id=1)
    _write_cmc_day(tmp_path, "2026-09-19", coin_id=2)
    write_refresh_state(
        settings,
        run_id="btk_9009",
        status="completed",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert status["latest_primary_date"] == "2026-09-19"


def test_repeated_no_advance_is_stalled(tmp_path):
    settings = _settings(tmp_path, data_freshness_max_no_advance_days=1)
    _write_cmc_day(tmp_path, "2026-09-19")
    write_refresh_state(
        settings,
        run_id="btk_9003",
        status="completed",
        now=datetime(2026, 9, 20, 2, 10, tzinfo=timezone.utc),
    )
    write_refresh_state(
        settings,
        run_id="btk_9004",
        status="completed",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert status["status"] == "stalled"
    assert status["no_advance_days"] == 1


def test_same_day_catchup_retry_does_not_double_count_no_advance(tmp_path):
    settings = _settings(tmp_path, data_freshness_max_no_advance_days=2)
    _write_cmc_day(tmp_path, "2026-09-19")
    write_refresh_state(
        settings,
        run_id="btk_9011",
        status="completed",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )
    write_refresh_state(
        settings,
        run_id="btk_9012",
        status="completed",
        now=datetime(2026, 9, 21, 6, 10, tzinfo=timezone.utc),
    )

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 6, 30, tzinfo=timezone.utc))

    assert status["status"] == "ok"
    assert status["no_advance_days"] == 0


def test_failed_refresh_today_is_reported_immediately(tmp_path):
    settings = _settings(tmp_path)
    _write_cmc_day(tmp_path, "2026-09-19")
    write_refresh_state(
        settings,
        run_id="btk_9005",
        status="failed",
        error="provider timeout",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert status["status"] == "failed"
    assert "provider timeout" in status["reason"]


def test_freshness_alert_is_emitted_for_bad_status(tmp_path):
    settings = _settings(tmp_path)
    _write_cmc_day(tmp_path, "2026-09-19")
    write_refresh_state(
        settings,
        run_id="btk_9006",
        status="failed",
        error="provider timeout",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    alert = freshness_alert(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert alert is not None
    assert alert["id"] == "data_freshness"
    assert alert["severity"] == "rose"
    assert "provider timeout" in alert["meta"]


def test_evaluate_uses_heartbeat_without_rescanning_raw_data(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _write_cmc_day(tmp_path, "2026-09-19")
    write_refresh_state(
        settings,
        run_id="btk_9007",
        status="completed",
        now=datetime(2026, 9, 21, 2, 10, tzinfo=timezone.utc),
    )

    def fail_scan(_: Path):
        raise AssertionError("readiness must not rescan the raw cache")

    monkeypatch.setattr(freshness_module, "_source_dates", fail_scan)
    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert status["status"] == "ok"
    assert status["latest_primary_date"] == "2026-09-19"


def test_corrupt_refresh_state_is_reported_without_raising(tmp_path):
    settings = _settings(tmp_path)
    path = freshness_module.freshness_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    status = evaluate_data_freshness(settings, now=datetime(2026, 9, 21, 4, 0, tzinfo=timezone.utc))

    assert status["status"] == "missing"


def test_watchdog_log_includes_structured_freshness_state(tmp_path, caplog):
    settings = _settings(tmp_path, daily_refresh_enabled=False)

    with caplog.at_level(logging.INFO, logger="atlas20.api.data_freshness"):
        freshness_module.log_data_freshness(settings, now=datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc))

    assert caplog.records[-1].data_freshness["status"] == "disabled"
