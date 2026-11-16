"""Build a frozen live long/short target ledger from the research engine.

This is a thin, explicit wrapper around ``run_derivatives_shadow.py``.  It uses
the LS45 signal construction and can layer the LS104 short-scale/gross/margin
profile on top.  The selected profile writes the signed target ledger used by
``plan_live_execution.py`` and ``execute_live_plan.py``.

The wrapper deliberately contains only the profile pins; it never places
orders.
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
LS104_OUTPUT_DIR = "reports/ls45_live_g175"
DEFAULT_RAW_DIR = "data/raw/bitget_derivatives/merged_oos_20261112"
DEFAULT_WARMUP_DIR = "data/raw/bitget_derivatives/merged_20261009"
DEFAULT_WARMUP_MARKET_DIR = "data/raw/bitget_derivatives/merged_market_20261009"
DEFAULT_TOP50_READINESS = "reports/top50_data_readiness/latest_ready.json"
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
    output_dir: str | None = None,
    track: str = "ls45-g125",
    allow_final_provisional_fill: bool = False,
    top50_readiness: str | None = None,
    top50_fingerprint: str | None = None,
    require_top50_current_inputs: bool = True,
) -> list[str]:
    """Return the exact shadow-runner command for the selected live profile."""

    normalized_end = _validated_end_date(end_date)
    if track not in {"ls45-g125", "ls104-g175-m090"}:
        raise ValueError(f"unsupported track: {track}")
    is_ls104 = track == "ls104-g175-m090"
    resolved_output = (
        output_dir
        or (LS104_OUTPUT_DIR if is_ls104 else DEFAULT_OUTPUT_DIR)
    )
    command = [
        sys.executable,
        SHADOW_SCRIPT,
        "--config",
        config,
        "--trial-id",
        LS45_CANDIDATE_ID,
        "--tracked-spec",
        (
            "PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090"
            if is_ls104
            else "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
        ),
        "--short-scale",
        "2.0" if is_ls104 else "1.0",
        "--raw-dir",
        DEFAULT_RAW_DIR,
        "--warmup-raw-dir",
        DEFAULT_WARMUP_DIR,
        "--market-raw-dir",
        DEFAULT_RAW_DIR,
        "--warmup-market-raw-dir",
        DEFAULT_WARMUP_MARKET_DIR,
        "--require-market-fills",
        "--start-date",
        DEFAULT_START,
        "--warmup-start",
        DEFAULT_WARMUP_START,
        "--cost-bps",
        "20",
        "--max-margin-utilization",
        "0.90" if is_ls104 else "0.85",
        "--venue-leverage",
        "4.0" if is_ls104 else "2.0",
        "--capital",
        "1000",
        "--engine-capital",
        "500",
        "--execution-hour",
        "1",
        "--execution-minute",
        "5",
        "--execution-price-snap",
        "floor",
        "--contract-specs-from-symbol-map",
        "--min-rebalance-usdt",
        "5",
        "--normalize-isolated-margin",
        "daily",
        "--max-total-gross",
        "1.75" if is_ls104 else "1.25",
        "--funding-source",
        "bitget-exact",
        "--funding-missing-policy",
        # Live parity must not silently charge zero when an expected Bitget
        # settlement is absent.  The research runner keeps skip available for
        # explicitly labelled proxy diagnostics only.
        "error",
        "--output-dir",
        resolved_output,
    ]
    if allow_final_provisional_fill:
        command.append("--allow-final-provisional-fill")
    if normalized_end is not None:
        command.extend(["--end-date", normalized_end])
    readiness_path = top50_readiness
    if is_ls104 and readiness_path is None:
        readiness_path = DEFAULT_TOP50_READINESS
    if readiness_path is not None:
        command.extend(["--top50-readiness", readiness_path])
    if top50_fingerprint is not None:
        if readiness_path is None:
            raise ValueError("top50_fingerprint requires top50_readiness")
        command.extend(["--expected-top50-fingerprint", top50_fingerprint])
    if is_ls104 and require_top50_current_inputs:
        command.append("--require-top50-current-inputs")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--track",
        choices=("ls45-g125", "ls104-g175-m090"),
        default="ls45-g125",
    )
    parser.add_argument(
        "--allow-final-provisional-fill",
        action="store_true",
        help="allow the newest signal to use the last observed bar before 01:00 publishes",
    )
    args = parser.parse_args()
    try:
        command = build_command(
            end_date=args.end_date,
            config=args.config,
            output_dir=args.output_dir,
            track=args.track,
            allow_final_provisional_fill=bool(args.allow_final_provisional_fill),
        )
    except ValueError as exc:
        parser.error(str(exc))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
