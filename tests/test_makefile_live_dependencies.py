from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _dry_run(target: str) -> str:
    return subprocess.check_output(
        ["make", "-n", target],
        cwd=PROJECT_ROOT,
        text=True,
    )


def test_ls45_signal_does_not_redownload_the_data_node_outputs() -> None:
    command = _dry_run("derivatives-ls45-signal")

    assert "scripts/run_ls45_live_signal.py" in command
    assert "scripts/download_bitget_derivatives_data.py" not in command


def test_combined_ls45_live_chain_still_downloads_once() -> None:
    command = _dry_run("derivatives-live")

    assert command.count("scripts/download_bitget_derivatives_data.py") == 1
    assert "scripts/run_ls45_live_signal.py" in command
