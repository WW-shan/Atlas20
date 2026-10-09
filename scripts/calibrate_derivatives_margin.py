"""Calibrate isolated-margin buffers before the leverage trials.

This is a design-stage diagnostic.  It uses the available hourly mark proxy
until Bitget full-history coverage is complete, and it explicitly records the
margin buffer, leverage, liquidation count, and terminal path.  The result is
not a Bitget candidate backtest.
"""

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

from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.derivatives.signals import scale_long_targets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402
from scripts.validate_derivatives_engine import _load_hourly_proxy, _long_targets  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--hourly-root", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_margin_calibration"))
    args = parser.parse_args()
    configure_logging("ERROR")

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    base_targets = _long_targets(built, index)
    marks = _load_hourly_proxy(args.hourly_root, args.hourly_root / "coverage.json")

    def has_execution_mark(asset: str, date: pd.Timestamp) -> bool:
        frame = marks.get(asset)
        if frame is None:
            return False
        execution_time = pd.Timestamp(date)
        if execution_time.tzinfo is None:
            execution_time = execution_time.tz_localize("UTC")
        else:
            execution_time = execution_time.tz_convert("UTC")
        execution_time = execution_time.normalize() + pd.Timedelta(days=1, hours=3)
        if execution_time in frame.index:
            return True
        later = frame.index[frame.index >= execution_time]
        return bool(len(later) and later[0] - execution_time <= pd.Timedelta(hours=1))

    restricted = {
        date: weights[
            [
                asset
                for asset in weights.index
                if has_execution_mark(str(asset), pd.Timestamp(date))
            ]
        ]
        for date, weights in base_targets.items()
    }

    rows: list[dict[str, object]] = []
    for leverage in (1.0, 1.25):
        scaled = scale_long_targets(restricted, leverage=leverage, max_gross=leverage)
        for long_buffer in (0.40, 0.50, 0.60, 0.75):
            result = run_derivative_backtest(
                marks,
                scaled,
                funding_rates=None,
                config=DerivativeBacktestConfig(
                    initial_capital=1.0,
                    taker_fee_bps=float(args.cost_bps),
                    slippage_bps=0.0,
                    liquidation_slippage_bps=5.0,
                    long_buffer=long_buffer,
                    short_buffer=0.50,
                    fee_buffer=0.005,
                    maintenance_margin_rate=0.01,
                    max_margin_utilization=0.85,
                    funding_missing_policy="skip",
                    missing_mark_policy="carry",
            missing_mark_max_carry_hours=3,
                ),
            )
            metrics = _metrics_from_returns(result.daily_returns)
            rows.append(
                {
                    "trial_id": f"PR2026-10-D-CAL-MB{int(long_buffer * 100):02d}-L{int(leverage * 100):03d}",
                    "leverage": leverage,
                    "long_buffer": long_buffer,
                    "cost_bps": float(args.cost_bps),
                    "liquidation_count": int(len(result.liquidations)),
                    "max_gross_exposure": float(result.gross_exposure.max()),
                    "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
                    "fees_total": float(result.trades["fee"].sum()) if not result.trades.empty else 0.0,
                    **metrics,
                }
            )
            print(rows[-1])
    output_dir = ensure_dir(args.output_dir)
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "margin_calibration.csv", index=False)
    (output_dir / "margin_calibration.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Wrote margin calibration to {output_dir}")


if __name__ == "__main__":
    main()
