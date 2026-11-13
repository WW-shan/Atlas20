from pathlib import Path

import pytest

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


def test_build_command_rejects_invalid_end_date() -> None:
    with pytest.raises(ValueError, match="end_date"):
        build_command(end_date="not-a-date")
