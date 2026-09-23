"""Generate the latest target snapshot for the phase-momentum champion.

This is deliberately a signal-generation tool, not an order router.  It
reconstructs the point-in-time Top20 targets with the same production strategy
code used by the research report, then writes the most recent aggregate target
for the next T+1 execution window.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import date
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
from atlas20.signals.risk import btc_above_moving_average  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    build_phase_momentum_targets,
)

from scripts.run_phase_momentum import _load_market  # noqa: E402


def _resolve_as_of(market, as_of: pd.Timestamp | str | None) -> pd.Timestamp:
    index = pd.DatetimeIndex(market.price.index)
    if index.empty:
        raise ValueError("market price index is empty")
    if as_of is None:
        return pd.Timestamp(index.max()).normalize()
    requested = pd.Timestamp(as_of).normalize()
    eligible = index[index <= requested]
    if eligible.empty:
        raise ValueError(f"no market data on or before {requested.date()}")
    return pd.Timestamp(eligible[-1]).normalize()


def _sleeve_snapshot(
    built: PhaseMomentumBuildResult,
    as_of: pd.Timestamp,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for sleeve in built.sleeve_targets:
        history = sleeve.assets.loc[:as_of].dropna()
        if history.empty:
            continue
        target_date = pd.Timestamp(history.index[-1])
        asset = str(history.iloc[-1])
        weight = 0.0 if asset == "__cash__" else float(sleeve.weights.loc[target_date])
        rows.append(
            {
                "signal_name": sleeve.signal_name,
                "phase_offset": int(sleeve.phase_offset),
                "asset": asset,
                "weight": weight,
                "target_date": target_date.date().isoformat(),
            }
        )
    return rows


def _latest_signal_payload(
    market,
    built: PhaseMomentumBuildResult,
    spec: PhaseMomentumSpec,
    *,
    as_of: pd.Timestamp | str | None = None,
) -> dict[str, object]:
    resolved_as_of = _resolve_as_of(market, as_of)
    eligible_dates = sorted(
        pd.Timestamp(target_date)
        for target_date in built.targets
        if pd.Timestamp(target_date) <= resolved_as_of
    )
    if not eligible_dates:
        raise ValueError(f"strategy produced no targets on or before {resolved_as_of.date()}")
    target_date = eligible_dates[-1]
    target = built.targets[target_date]
    positive = target[target > 0.0].sort_values(ascending=False)
    gate = btc_above_moving_average(
        market.price,
        ma_window=spec.btc_ma_window,
        confirm_days=spec.btc_confirm_days,
    )
    return {
        "as_of": resolved_as_of.date().isoformat(),
        "latest_target_date": target_date.date().isoformat(),
        "btc_gate_open": bool(gate.get(resolved_as_of, False)),
        "targets": {str(asset): float(weight) for asset, weight in positive.items()},
        "gross_exposure": float(positive.sum()),
        "next_check_date": (resolved_as_of + pd.Timedelta(days=1)).date().isoformat(),
        "rule": (
            "Strict point-in-time Top20; four trailing-return signals x three "
            "calendar phases; hold while in Top2; BTC 100D MA + confirm2; "
            "60D volatility target at 80%; long-only spot, no leverage; T+1"
        ),
        "target_spec": {
            "rebalance_days": spec.rebalance_days,
            "phase_offsets": list(spec.phase_offsets),
            "hold_rank": spec.hold_rank,
            "btc_ma_window": spec.btc_ma_window,
            "btc_confirm_days": spec.btc_confirm_days,
            "target_volatility": spec.target_volatility,
            "vol_window": spec.vol_window,
        },
        "sleeves": _sleeve_snapshot(built, resolved_as_of),
    }


def _write_markdown(path: Path, payload: dict[str, object]) -> None:
    targets = payload["targets"]
    assert isinstance(targets, dict)
    target_lines = ["| Asset | Weight |", "| --- | ---: |"]
    if targets:
        for asset, weight in targets.items():
            target_lines.append(f"| {asset} | {float(weight):.6f} |")
    else:
        target_lines.append("| _cash_ | 0.000000 |")

    sleeve_lines = [
        "| Signal | Phase | Asset | Weight | Target date |",
        "| --- | ---: | --- | ---: | --- |",
    ]
    for sleeve in payload["sleeves"]:
        assert isinstance(sleeve, dict)
        sleeve_lines.append(
            "| {signal_name} | {phase_offset} | {asset} | {weight:.6f} | {target_date} |".format(
                signal_name=sleeve["signal_name"],
                phase_offset=sleeve["phase_offset"],
                asset=sleeve["asset"],
                weight=float(sleeve["weight"]),
                target_date=sleeve["target_date"],
            )
        )

    path.write_text(
        "\n".join(
            [
                "# Latest Phase-Momentum Signal",
                "",
                f"- As of: {payload['as_of']}",
                f"- Latest target date: {payload['latest_target_date']}",
                f"- BTC gate open: {payload['btc_gate_open']}",
                f"- Gross exposure: {float(payload['gross_exposure']):.6f}",
                f"- Next check date: {payload['next_check_date']}",
                f"- Rule: {payload['rule']}",
                "",
                "## Aggregate Targets",
                "",
                *target_lines,
                "",
                "## Current Sleeve Snapshot",
                "",
                *sleeve_lines,
                "",
                "This file is a signal snapshot only. It does not place orders.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--as-of", default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_live"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    _config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    spec = PhaseMomentumSpec()
    built = build_phase_momentum_targets(market, universe, index, spec=spec)
    payload = _latest_signal_payload(market, built, spec, as_of=args.as_of)
    output_dir = ensure_dir(args.output_dir)
    (output_dir / "latest_signal.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_markdown(output_dir / "latest_signal.md", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"Wrote latest signal to {output_dir}")


if __name__ == "__main__":
    main()
