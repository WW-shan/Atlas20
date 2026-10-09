"""Run revised long-only derivatives trials on the hourly proxy.

This is a Phase 2 design diagnostic, not a Bitget headline backtest.  It uses
the Binance/Gate hourly mark proxy until the Bitget full-history download is
complete and applies the revised 50% long liquidation buffer identified by
the margin calibration.
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

TRIALS = {
    "PR2026-10-D-L125-V2": 1.25,
    "PR2026-10-D-L150-V2": 1.50,
    "PR2026-10-D-L200-V2": 2.00,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--hourly-root", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_proxy_trials"))
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
    return_columns: dict[str, pd.Series] = {}
    for trial_id, leverage in TRIALS.items():
        scaled = scale_long_targets(restricted, leverage=leverage, max_gross=leverage)
        result = run_derivative_backtest(
            marks,
            scaled,
            funding_rates=None,
            config=DerivativeBacktestConfig(
                initial_capital=1.0,
                taker_fee_bps=float(args.cost_bps),
                slippage_bps=0.0,
                liquidation_slippage_bps=5.0,
                long_buffer=0.50,
                short_buffer=0.50,
                fee_buffer=0.005,
                maintenance_margin_rate=0.01,
                max_margin_utilization=0.85,
                max_gross_exposure=leverage,
                funding_missing_policy="skip",
                missing_mark_policy="carry",
                missing_mark_max_carry_hours=3,
            ),
            start_time=pd.Timestamp(args.start_date, tz="UTC"),
            end_time=pd.Timestamp(args.end_date, tz="UTC") + pd.Timedelta(days=1),
        )
        metrics = _metrics_from_returns(result.daily_returns)
        return_columns[trial_id] = result.daily_returns
        rows.append(
            {
                "trial_id": trial_id,
                "mark_source": "binance_or_gate_1h_proxy",
                "leverage": leverage,
                "long_buffer": 0.50,
                "cost_bps": float(args.cost_bps),
                "liquidation_count": int(len(result.liquidations)),
                "max_gross_exposure": float(result.gross_exposure.max()),
                "fees_total": float(result.trades["fee"].sum()) if not result.trades.empty else 0.0,
                **metrics,
            }
        )
        print(rows[-1])
    output_dir = ensure_dir(args.output_dir)
    pd.DataFrame(rows).to_csv(output_dir / "proxy_trials.csv", index=False)
    pd.DataFrame(return_columns).to_csv(output_dir / "daily_returns.csv", index_label="date")
    (output_dir / "proxy_trials.json").write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote proxy trials to {output_dir}")


if __name__ == "__main__":
    main()
