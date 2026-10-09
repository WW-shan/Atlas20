"""Diagnostic short-overlay trials on the hourly proxy and Binance funding.

This is not a Bitget result: the mark path is Binance/Gate hourly and the
funding series is the Binance archive proxy that failed the Phase 1 overlap
gate.  It is used only to test whether the short-overlay implementation and
signal plumbing behave sensibly before the Bitget data and funding source are
resolved.
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

from atlas20.derivatives.data import load_binance_funding  # noqa: E402
from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.derivatives.signals import build_derivative_targets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402
from scripts.validate_derivatives_engine import _load_hourly_proxy, _long_targets  # noqa: E402

TRIALS = {
    "PR2026-10-D-SBTC25": ("bitcoin", 0.25),
    "PR2026-10-D-SBTC50": ("bitcoin", 0.50),
    "PR2026-10-D-SWEAK25": ("weakest", 0.25),
    "PR2026-10-D-SWEAK50": ("weakest", 0.50),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--hourly-root", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_proxy_shorts"))
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
    funding = load_binance_funding(args.funding_dir, coins=set(market.price.columns))
    available = set(marks) & set(funding.columns)

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
                if asset in available and has_execution_mark(str(asset), pd.Timestamp(date))
            ]
        ]
        for date, weights in base_targets.items()
    }

    rows: list[dict[str, object]] = []
    for trial_id, (short_asset, short_weight) in TRIALS.items():
        targets = build_derivative_targets(
            restricted,
            btc_close=market.price["bitcoin"],
            universe=universe,
            prices=market.price,
            funding_rates=funding,
            leverage=1.25,
            max_gross=1.25 + short_weight,
            short_asset=short_asset,
            short_weight=short_weight,
            eligible=available,
            btc_asset="bitcoin",
        )
        result = run_derivative_backtest(
            marks,
            targets,
            funding_rates=funding,
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
                max_gross_exposure=1.25 + short_weight,
                funding_missing_policy="skip",
                missing_mark_policy="carry",
            missing_mark_max_carry_hours=3,
            ),
        )
        metrics = _metrics_from_returns(result.daily_returns)
        rows.append(
            {
                "trial_id": trial_id,
                "mark_source": "binance_or_gate_1h_proxy",
                "funding_source": "binance_archive_proxy_failed_phase1_overlap",
                "leverage": 1.25,
                "long_buffer": 0.50,
                "short_asset": short_asset,
                "short_weight": short_weight,
                "cost_bps": float(args.cost_bps),
                "liquidation_count": int(len(result.liquidations)),
                "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
                "max_gross_exposure": float(result.gross_exposure.max()),
                **metrics,
            }
        )
        print(rows[-1])
    output_dir = ensure_dir(args.output_dir)
    pd.DataFrame(rows).to_csv(output_dir / "proxy_shorts.csv", index=False)
    (output_dir / "proxy_shorts.json").write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote proxy short diagnostics to {output_dir}")


if __name__ == "__main__":
    main()
