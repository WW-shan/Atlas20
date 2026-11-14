#!/usr/bin/env python3
"""Audit the Bitget/CMC derivatives inputs used by the live LS45 chain."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pandas as pd  # noqa: E402

from atlas20.derivatives.data_audit import audit_derivatives_data  # noqa: E402
from atlas20.logging_utils import atomic_write_text, ensure_dir  # noqa: E402

DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_oos_20261112")
DEFAULT_PANEL = Path("data/processed/panel_daily.csv")
DEFAULT_TARGETS = Path("reports/ls45_live_g125/oos_targets.csv")
DEFAULT_MANIFEST = Path("reports/ls45_live_g125/manifest.json")
DEFAULT_JSON_OUT = Path("reports/ls45_live_g125/data_audit.json")
DEFAULT_MARKDOWN_OUT = Path("reports/ls45_live_g125/data_audit.md")


def _required_short_assets(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    frame = pd.read_csv(path)
    required = {"signal_date", "asset", "target_weight"}
    if not required.issubset(frame.columns) or frame.empty:
        return set()
    frame["signal_date"] = pd.to_datetime(frame["signal_date"], utc=True, format="mixed", errors="coerce")
    latest = frame["signal_date"].max()
    latest_book = frame.loc[frame["signal_date"] == latest]
    weights = pd.to_numeric(latest_book["target_weight"], errors="coerce")
    return set(latest_book.loc[weights < 0.0, "asset"].astype(str).str.lower())


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# Atlas20 derivatives data audit",
        "",
        f"- passed: **{report['passed']}**",
        f"- fingerprint: `{report['provenance'].get('fingerprint')}`",
        f"- hard failures: {len(report['hard_failures'])}",
        f"- warnings: {len(report['warnings'])}",
        "",
        "## Hard failures",
        "",
    ]
    failures = report["hard_failures"]
    lines.extend([f"- {item}" for item in failures] or ["- none"])
    lines += ["", "## Warnings", ""]
    warnings = report["warnings"]
    lines.extend([f"- {item}" for item in warnings] or ["- none"])
    lines += ["", "## Summary", "", "```json", json.dumps(report["summary"], indent=2, sort_keys=True, default=str), "```", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--symbol-map", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--targets-file", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument("--now", default=None, help="ISO timestamp; defaults to current UTC")
    parser.add_argument("--min-panel-assets", type=int, default=20)
    parser.add_argument(
        "--require-all-funding-fresh",
        action="store_true",
        help="require fresh funding for every normal contract, not only selected shorts",
    )
    args = parser.parse_args(argv)

    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    report = audit_derivatives_data(
        args.raw_dir,
        args.panel,
        args.symbol_map,
        args.manifest,
        now=now,
        min_panel_assets=int(args.min_panel_assets),
        required_short_assets=_required_short_assets(args.targets_file),
        require_all_funding_fresh=bool(args.require_all_funding_fresh),
    )
    payload = report.as_dict()
    ensure_dir(args.json_out.parent)
    atomic_write_text(args.json_out, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    ensure_dir(args.markdown_out.parent)
    atomic_write_text(args.markdown_out, _markdown(payload))
    print(
        f"derivatives data audit: {'PASS' if report.passed else 'FAIL'} "
        f"({len(report.hard_failures)} hard failure(s), {len(report.warnings)} warning(s))"
    )
    for item in report.hard_failures[:20]:
        print(f"  ❌ {item}")
    for item in report.warnings[:10]:
        print(f"  ⚠️ {item}")
    print(f"  fingerprint: {report.provenance.get('fingerprint')}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
