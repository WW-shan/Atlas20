from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _ready_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    from atlas20.derivatives.top50_readiness import publish_readiness_payload

    reports = tmp_path / "reports"
    panel = tmp_path / "panel_daily.csv"
    metadata = tmp_path / "metadata.csv"
    symbol_map = tmp_path / "symbol_map.csv"
    panel.write_text("date,coin_id\n2026-11-22,coin-1\n", encoding="utf-8")
    metadata.write_text("coin_id\ncoin-1\n", encoding="utf-8")
    symbol_map.write_text("coin_id,bitget_symbol\ncoin-1,C1USDT\n", encoding="utf-8")
    members = [
        {
            "final_rank": index,
            "original_rank": index,
            "coin_id": f"coin-{index}",
            "symbol": f"C{index}",
            "bitget_symbol": f"C{index}USDT",
            "panel_symbol": f"C{index}",
            "status": "READY",
            "failure_details": [],
        }
        for index in range(1, 51)
    ]
    from atlas20.derivatives.top50_readiness import _file_sha256

    payload = {
        "as_of": "2026-11-22",
        "ready": True,
        "members": members,
        "top20": [dict(item) for item in members[:20]],
        "skipped": [],
        "audit": {"passed": True, "hard_failures": [], "warnings": []},
        "input_files": {
            "panel": _file_sha256(panel),
            "metadata": _file_sha256(metadata),
            "symbol_map": _file_sha256(symbol_map),
        },
    }
    publish_readiness_payload(
        reports_dir=reports,
        payload=payload,
        audit_payload={"passed": True},
    )
    return reports, panel, metadata, symbol_map


def test_data_receipt_binds_the_current_top50_pointer_and_inputs(tmp_path: Path) -> None:
    from scripts import data_ready_receipt

    reports, panel, metadata, symbol_map = _ready_inputs(tmp_path)
    receipt_path = tmp_path / "data_ready.json"
    now = pd.Timestamp("2026-11-23T00:45:00Z")

    receipt = data_ready_receipt.write_receipt(
        path=receipt_path,
        reports_dir=reports,
        panel_path=panel,
        metadata_path=metadata,
        symbol_map_path=symbol_map,
        now=now,
    )
    checked = data_ready_receipt.check_receipt(
        path=receipt_path,
        reports_dir=reports,
        panel_path=panel,
        metadata_path=metadata,
        symbol_map_path=symbol_map,
        now=pd.Timestamp("2026-11-23T00:50:00Z"),
        max_age_minutes=90.0,
    )

    assert receipt["ready"] is True
    assert receipt["as_of"] == "2026-11-22"
    assert checked["fingerprint"] == receipt["fingerprint"]


def test_data_receipt_rejects_a_receipt_from_the_previous_utc_day(
    tmp_path: Path,
) -> None:
    from scripts import data_ready_receipt

    reports, panel, metadata, symbol_map = _ready_inputs(tmp_path)
    receipt_path = tmp_path / "data_ready.json"
    data_ready_receipt.write_receipt(
        path=receipt_path,
        reports_dir=reports,
        panel_path=panel,
        metadata_path=metadata,
        symbol_map_path=symbol_map,
        now=pd.Timestamp("2026-11-22T00:45:00Z"),
    )

    with pytest.raises(ValueError, match="previous UTC day|stale"):
        data_ready_receipt.check_receipt(
            path=receipt_path,
            reports_dir=reports,
            panel_path=panel,
            metadata_path=metadata,
            symbol_map_path=symbol_map,
            now=pd.Timestamp("2026-11-23T00:50:00Z"),
            max_age_minutes=90.0,
        )


def test_data_receipt_rejects_changed_top50_inputs(tmp_path: Path) -> None:
    from scripts import data_ready_receipt

    reports, panel, metadata, symbol_map = _ready_inputs(tmp_path)
    receipt_path = tmp_path / "data_ready.json"
    data_ready_receipt.write_receipt(
        path=receipt_path,
        reports_dir=reports,
        panel_path=panel,
        metadata_path=metadata,
        symbol_map_path=symbol_map,
        now=pd.Timestamp("2026-11-23T00:45:00Z"),
    )
    panel.write_text("date,coin_id\n2026-11-22,coin-2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="panel.*hash|input"):
        data_ready_receipt.check_receipt(
            path=receipt_path,
            reports_dir=reports,
            panel_path=panel,
            metadata_path=metadata,
            symbol_map_path=symbol_map,
            now=pd.Timestamp("2026-11-23T00:50:00Z"),
            max_age_minutes=90.0,
        )


def test_data_node_publishes_receipt_after_top50_check() -> None:
    data = (Path(__file__).resolve().parents[1] / "ops/run_derivatives_data.sh").read_text(
        encoding="utf-8"
    )

    assert data.index("data_ready_receipt.py write") > data.index(
        "top50-readiness-check"
    )


def test_signal_node_waits_for_the_data_receipt_before_building_the_signal() -> None:
    signal = (
        Path(__file__).resolve().parents[1] / "ops/run_derivatives_signal.sh"
    ).read_text(encoding="utf-8")

    assert "data_ready_receipt.py check" in signal
    assert signal.index("data_ready_receipt.py check") < signal.index(
        '/usr/bin/make "$SIGNAL_TARGET"'
    )
    assert "--wait-seconds 900" in signal
