"""Leave-one-signal and leave-one-phase-out checks for the primary strategy."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PRIMARY_SIGNAL_SPECS,
    PhaseMomentumSpec,
    build_phase_momentum_targets,
)

from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_leave_one_out_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    rows: list[dict[str, object]] = []
    for removed in PRIMARY_SIGNAL_SPECS:
        signals = tuple(spec for spec in PRIMARY_SIGNAL_SPECS if spec.name != removed.name)
        built = build_phase_momentum_targets(
            market,
            universe,
            index,
            signal_specs=signals,
            spec=PhaseMomentumSpec(),
        )
        result = _production_result(config, market, built, index, cost_bps=args.cost_bps)
        rows.append(
            {
                "variant": f"remove_signal_{removed.name}",
                "kind": "signal",
                **_metrics_from_returns(result.daily_returns),
            }
        )
    for removed_offset in (0, 1, 2):
        offsets = tuple(offset for offset in (0, 1, 2) if offset != removed_offset)
        built = build_phase_momentum_targets(
            market,
            universe,
            index,
            spec=PhaseMomentumSpec(phase_offsets=offsets),
        )
        result = _production_result(config, market, built, index, cost_bps=args.cost_bps)
        rows.append(
            {
                "variant": f"remove_phase_{removed_offset}",
                "kind": "phase",
                **_metrics_from_returns(result.daily_returns),
            }
        )

    summary = pd.DataFrame(rows).sort_values("multiple", ascending=False)
    output_dir = ensure_dir(args.output_dir)
    summary.to_csv(output_dir / "summary.csv", index=False)
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": args.cost_bps,
        "signals": [spec.name for spec in PRIMARY_SIGNAL_SPECS],
        "phases": [0, 1, 2],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                "# Phase-Momentum Leave-One-Signal and Leave-One-Phase-Out",
                "",
                "Each variant removes one signal family or one calendar phase from the fixed primary strategy.",
                "",
                "## Summary",
                "",
                dataframe_to_markdown(summary),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"Wrote leave-one-out report to {output_dir}")


if __name__ == "__main__":
    main()
