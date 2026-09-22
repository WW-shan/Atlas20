"""Independently audit every phase-momentum selection against the Top20 snapshot."""

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
from atlas20.strategies.phase_momentum import PhaseMomentumSpec, build_phase_momentum_targets  # noqa: E402

from scripts.run_phase_momentum import _load_market  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_selection_audit_2022"))
    args = parser.parse_args()

    configure_logging("ERROR")
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    built = build_phase_momentum_targets(market, universe, index, spec=PhaseMomentumSpec())
    history = built.selection_history.copy()
    history["signal_date"] = pd.to_datetime(history["signal_date"]).dt.normalize()
    universe = universe.copy()
    universe["rebalance_date"] = pd.to_datetime(universe["rebalance_date"]).dt.normalize()
    membership = (
        universe.groupby("rebalance_date")["coin_id"]
        .apply(lambda values: set(values.astype(str)))
        .to_dict()
    )
    universe_sizes = (
        universe.groupby("rebalance_date")["coin_id"]
        .nunique()
        .rename("universe_size")
        .reset_index()
    )

    rows: list[dict[str, object]] = []
    selected = history[history["selected_asset"].astype(str).ne("")].copy()
    for row in selected.itertuples(index=False):
        signal_date = pd.Timestamp(row.signal_date)
        asset = str(row.selected_asset)
        snapshot = membership.get(signal_date, set())
        in_snapshot = asset in snapshot
        has_price = asset in market.price.columns and signal_date in market.price.index and pd.notna(
            market.price.at[signal_date, asset]
        )
        rows.append(
            {
                "signal_date": signal_date,
                "signal_name": row.signal_name,
                "phase_offset": row.phase_offset,
                "selected_asset": asset,
                "in_point_in_time_top20": in_snapshot,
                "has_price": bool(has_price),
                "snapshot_size": len(snapshot),
                "is_rain": asset == "rain",
                "is_stablecoin": asset
                in {
                    "tether",
                    "usd-coin",
                    "dai",
                    "true-usd",
                    "usdd",
                    "frax",
                    "paypal-usd",
                },
            }
        )

    audit = pd.DataFrame(rows)
    violations = audit[
        (~audit["in_point_in_time_top20"])
        | (~audit["has_price"])
        | audit["is_rain"]
        | audit["is_stablecoin"]
    ].copy()
    summary = {
        "selection_rows": int(len(audit)),
        "violations": int(len(violations)),
        "missing_price_rows": int((~audit["has_price"]).sum()) if not audit.empty else 0,
        "outside_top20_rows": int((~audit["in_point_in_time_top20"]).sum()) if not audit.empty else 0,
        "rain_rows": int(audit["is_rain"].sum()) if not audit.empty else 0,
        "stablecoin_rows": int(audit["is_stablecoin"].sum()) if not audit.empty else 0,
        "max_universe_size": int(universe_sizes["universe_size"].max()) if not universe_sizes.empty else 0,
        "min_universe_size": int(universe_sizes["universe_size"].min()) if not universe_sizes.empty else 0,
    }

    output_dir = ensure_dir(args.output_dir)
    audit.to_csv(output_dir / "selection_audit.csv", index=False)
    universe_sizes.to_csv(output_dir / "universe_sizes.csv", index=False)
    pd.DataFrame([summary]).to_csv(output_dir / "summary.csv", index=False)
    lines = [
        "# Phase-Momentum Selection Audit",
        "",
        "Every non-empty selection is checked against the point-in-time Top20 snapshot",
        "used by the strategy. A violation means the selected asset was absent from that",
        "snapshot, had no price, was Rain, or was a stablecoin.",
        "",
        "## Summary",
        "",
        dataframe_to_markdown(pd.DataFrame([summary])),
        "",
        "## Violations",
        "",
        dataframe_to_markdown(violations.head(100) if not violations.empty else violations),
        "",
        "## Universe size",
        "",
        dataframe_to_markdown(universe_sizes.describe(include="all")),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "spec": {
            "rebalance_days": 3,
            "phase_offsets": [0, 1, 2],
            "hold_rank": 2,
            "btc_ma_window": 100,
            "btc_confirm_days": 2,
            "target_volatility": 0.8,
            "vol_window": 60,
        },
        "summary": summary,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(pd.DataFrame([summary]).to_string(index=False))
    print(f"Wrote selection audit to {output_dir}")


if __name__ == "__main__":
    main()
