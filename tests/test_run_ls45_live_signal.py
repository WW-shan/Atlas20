import json
from pathlib import Path

import pytest

from atlas20.derivatives.live_chain import (
    LS45_G125_FROZEN_CONFIG,
    LS45_G125_MANIFEST_TOP_LEVEL,
    LS45_G125_SPEC,
    manifest_spec_issues,
)
from scripts.run_h5_regime_short_router import LS45_CANDIDATE_ID
from scripts.run_ls45_live_signal import build_command


def test_build_command_pins_ls45_and_g125() -> None:
    command = build_command(end_date="2026-11-13")

    assert command[0].endswith("python")
    assert "scripts/run_derivatives_shadow.py" in command
    assert command[command.index("--trial-id") + 1] == LS45_CANDIDATE_ID
    assert command[command.index("--max-total-gross") + 1] == "1.25"
    assert command[command.index("--funding-source") + 1] == "bitget-exact"
    assert command[command.index("--output-dir") + 1] == "reports/ls45_live_g125"
    assert command[command.index("--end-date") + 1] == "2026-11-13"


def test_build_command_pins_the_single_0105_execution_clock() -> None:
    command = build_command(end_date="2026-11-13")

    assert command[command.index("--execution-hour") + 1] == "1"
    assert command[command.index("--execution-minute") + 1] == "5"
    assert command[command.index("--execution-price-snap") + 1] == "floor"
    assert command[command.index("--normalize-isolated-margin") + 1] == "daily"
    assert command[command.index("--min-rebalance-usdt") + 1] == "5"
    assert command[command.index("--engine-capital") + 1] == "500"
    assert "--contract-specs-from-symbol-map" in command


def test_build_command_rejects_invalid_end_date() -> None:
    with pytest.raises(ValueError, match="end_date"):
        build_command(end_date="not-a-date")


def test_committed_manifest_carries_every_audit_freshness_field() -> None:
    path = Path("reports/ls45_live_g125/manifest.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    for key in (
        "tracked_spec",
        "execution_utc",
        "execution_price_model",
        "end_date",
        "last_mark",
        "staleness_hours",
        "index_end_date",
        "signal_end_date",
        "max_total_gross",
        "research_only",
        "frozen_config",
    ):
        assert key in payload
    assert payload["max_total_gross"] == 1.25
    assert payload["execution_utc"] == "01:05"
    assert payload["execution_price_model"] == "mark_1h_open_floor"
    assert payload["frozen_config"]["max_total_gross"] == 1.25


def test_committed_manifest_matches_the_live_spec_pin() -> None:
    path = Path("reports/ls45_live_g125/manifest.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert LS45_G125_SPEC == LS45_CANDIDATE_ID
    assert manifest_spec_issues(
        payload,
        expected_spec=LS45_G125_SPEC,
        expected_frozen_config=LS45_G125_FROZEN_CONFIG,
        expected_top_level=LS45_G125_MANIFEST_TOP_LEVEL,
    ) == []
