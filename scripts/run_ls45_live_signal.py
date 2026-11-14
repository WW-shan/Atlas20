"""Build the LS45-G125 live target ledger from the frozen research engine.

This is a thin, explicit wrapper around ``run_derivatives_shadow.py``.  It uses
the LS45 candidate, caps total target gross at 1.25x, and writes the signed
target ledger used by ``plan_live_execution.py`` and ``execute_live_plan.py``.

The wrapper deliberately does not contain strategy parameters beyond the
frozen LS45 ID and the owner-requested 1.25x gross cap.  It never places orders.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHADOW_SCRIPT = "scripts/run_derivatives_shadow.py"
LS45_CANDIDATE_ID = "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
DEFAULT_OUTPUT_DIR = "reports/ls45_live_g125"
DEFAULT_RAW_DIR = "data/raw/bitget_derivatives/merged_oos_20261112"
DEFAULT_WARMUP_DIR = "data/raw/bitget_derivatives/merged_20261009"
DEFAULT_START = "2026-09-22"
DEFAULT_WARMUP_START = "2021-01-01"


def _validated_end_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("end_date must be an ISO date (YYYY-MM-DD)") from exc


def build_command(
    *,
    end_date: str | None = None,
    config: str = "config/base.yaml",
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> list[str]:
    """Return the exact shadow-runner command for the LS45-G125 ledger."""

    normalized_end = _validated_end_date(end_date)
    command = [
        sys.executable,
        SHADOW_SCRIPT,
        "--config",
        config,
        "--trial-id",
        LS45_CANDIDATE_ID,
        "--raw-dir",
        DEFAULT_RAW_DIR,
        "--warmup-raw-dir",
        DEFAULT_WARMUP_DIR,
        "--start-date",
        DEFAULT_START,
        "--warmup-start",
        DEFAULT_WARMUP_START,
        "--cost-bps",
        "20",
        "--capital",
        "1000",
        "--execution-hour",
        "1",
        "--execution-minute",
        "5",
        "--execution-price-snap",
        "floor",
        "--max-total-gross",
        "1.25",
        "--funding-source",
        "bitget-exact",
        "--funding-missing-policy",
        "skip",
        "--output-dir",
        output_dir,
    ]
    if normalized_end is not None:
        command.extend(["--end-date", normalized_end])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    try:
        command = build_command(
            end_date=args.end_date,
            config=args.config,
            output_dir=args.output_dir,
        )
    except ValueError as exc:
        parser.error(str(exc))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
