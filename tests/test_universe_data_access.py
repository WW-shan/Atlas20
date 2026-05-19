from __future__ import annotations

import pytest

from atlas20.api.data_access.universe import (
    load_data_alerts_from_processed,
    load_universe_timeline_from_processed,
)
from atlas20.api.schemas import UniverseTimelinePayload
from atlas20.api.settings import Settings


REBALANCE_HEADER = (
    "coin_id,price,market_cap,volume_usd,history_days,symbol,name,sector,"
    "rebalance_date,universe_rank"
)
DATA_QUALITY_HEADER = (
    "symbol,validation_passed,validation_reason,latest_overlap_date,latest_price_gap,"
    "median_price_gap,price_correlation,included_in_panel"
)


def _write_rebalance_csv(data_root, rows: list[str]) -> None:
    processed = data_root / "processed"
    processed.mkdir(parents=True)
    processed.joinpath("rebalance_universe.csv").write_text(
        "\n".join([REBALANCE_HEADER, *rows]),
        encoding="utf-8",
    )


def _rebalance_row(symbol: str, rebalance_date: str, universe_rank: int) -> str:
    coin_id = symbol.lower()
    return f"{coin_id},1,1000,100,30,{symbol},{symbol},Layer1,{rebalance_date},{universe_rank}"


def _write_data_quality_csv(data_root, rows: list[str]) -> None:
    processed = data_root / "processed"
    processed.mkdir(parents=True)
    processed.joinpath("data_quality.csv").write_text(
        "\n".join([DATA_QUALITY_HEADER, *rows]),
        encoding="utf-8",
    )


def _quality_row(
    symbol: str,
    validation_passed: bool,
    validation_reason: str,
    latest_overlap_date: str,
    latest_price_gap: float,
    price_correlation: float,
    included_in_panel: bool = True,
) -> str:
    return (
        f"{symbol},{validation_passed},{validation_reason},{latest_overlap_date},"
        f"{latest_price_gap},0.001,{price_correlation},{included_in_panel}"
    )


def test_load_universe_timeline_builds_segments_from_real_data(tmp_path):
    _write_rebalance_csv(
        tmp_path,
        [
            _rebalance_row("AAA", "2026-01-01", 1),
            _rebalance_row("BBB", "2026-01-01", 2),
            _rebalance_row("AAA", "2026-01-08", 1),
            _rebalance_row("CCC", "2026-01-08", 2),
            _rebalance_row("AAA", "2026-01-15", 1),
            _rebalance_row("BBB", "2026-01-15", 2),
            _rebalance_row("BBB", "2026-01-22", 1),
            _rebalance_row("CCC", "2026-01-22", 2),
        ],
    )

    payload = load_universe_timeline_from_processed(Settings(data_root=tmp_path))
    model = UniverseTimelinePayload.model_validate(payload)

    assert model.tokens == ["AAA", "BBB", "CCC"]
    assert model.segments[0].token == "AAA"
    assert model.segments[0].start == "2026-01-01"
    assert model.segments[0].end == "2026-01-15"
    assert model.range.start == "2026-01-01"
    assert model.range.end == "2026-01-22"


def test_load_universe_timeline_window_is_180d_from_latest(tmp_path):
    _write_rebalance_csv(
        tmp_path,
        [
            _rebalance_row("OLD", "2025-07-05", 1),
            _rebalance_row("NEW", "2026-01-21", 1),
        ],
    )

    payload = load_universe_timeline_from_processed(Settings(data_root=tmp_path))

    assert payload["tokens"] == ["NEW"]
    assert payload["range"] == {"start": "2026-01-21", "end": "2026-01-21"}


def test_load_universe_timeline_detects_major_rotation(tmp_path):
    _write_rebalance_csv(
        tmp_path,
        [
            *[_rebalance_row(symbol, "2026-01-01", index) for index, symbol in enumerate(["A", "B", "C", "D"], 1)],
            *[_rebalance_row(symbol, "2026-01-08", index) for index, symbol in enumerate(["E", "F", "G", "H"], 1)],
        ],
    )

    payload = load_universe_timeline_from_processed(Settings(data_root=tmp_path))

    assert payload["rotations"] == [{"ts": "2026-01-08", "label": "MAJOR ROTATION"}]


def test_load_universe_timeline_caps_tokens_at_20(tmp_path):
    rows = []
    rows.extend(_rebalance_row(f"T{index:02d}", "2026-01-01", 1) for index in range(1, 21))
    rows.extend(_rebalance_row(f"T{index:02d}", "2026-01-08", 1) for index in range(1, 21))
    rows.extend(_rebalance_row(f"T{index:02d}", "2026-01-15", 1) for index in range(1, 26))
    _write_rebalance_csv(tmp_path, rows)

    payload = load_universe_timeline_from_processed(Settings(data_root=tmp_path))

    assert len(payload["tokens"]) == 20
    assert payload["tokens"] == [f"T{index:02d}" for index in range(1, 21)]
    assert "T21" not in payload["tokens"]


def test_load_universe_timeline_missing_csv_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError, match="rebalance_universe.csv"):
        load_universe_timeline_from_processed(Settings(data_root=tmp_path))


def test_load_data_alerts_emits_validation_failures_first(tmp_path):
    _write_data_quality_csv(
        tmp_path,
        [
            _quality_row("ZED", True, "ok", "2026-01-02", 0.001, 0.970, True),
            _quality_row("AAA", False, "missing overlap", "2026-01-01", 0.001, 0.999, False),
        ],
    )

    alerts = load_data_alerts_from_processed(Settings(data_root=tmp_path))

    assert [alert["id"] for alert in alerts] == ["dq_aaa", "dq_zed"]
    assert alerts[0]["severity"] == "rose"
    assert alerts[0]["icon"] == "alert-triangle"
    assert alerts[0]["title"] == "AAA · missing overlap — review required"
    assert alerts[1]["severity"] == "cyan"
    assert alerts[1]["icon"] == "info"
    assert alerts[1]["title"] == "ZED · price correlation 0.970 below 0.98"
    assert "2026-01-01" in alerts[0]["meta"]
    assert "panel included: no" in alerts[0]["meta"]


def test_load_data_alerts_returns_empty_for_clean_data(tmp_path):
    _write_data_quality_csv(
        tmp_path,
        [
            _quality_row("AAA", True, "ok", "2026-01-01", 0.001, 0.999, True),
            _quality_row("BBB", True, "ok", "2026-01-01", 0.005, 0.980, True),
        ],
    )

    assert load_data_alerts_from_processed(Settings(data_root=tmp_path)) == []


def test_load_data_alerts_caps_at_12(tmp_path):
    _write_data_quality_csv(
        tmp_path,
        [
            _quality_row(f"T{index:02d}", False, "bad row", "2026-01-01", 0.001, 0.999, True)
            for index in range(15)
        ],
    )

    alerts = load_data_alerts_from_processed(Settings(data_root=tmp_path))

    assert len(alerts) == 12
    assert [alert["id"] for alert in alerts] == [f"dq_t{index:02d}" for index in range(12)]
