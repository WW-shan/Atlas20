"""Validate the isolated-margin engine against the frozen H5 spot path.

This diagnostic uses Binance/Gate hourly candles as a mark-price proxy while
the Bitget full-history download is still in progress.  It is not a Bitget
candidate result and must not be reported as one.  Its only purpose is to
check execution timing, turnover accounting, and the 1.0x long path against
the production spot engine.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def _load_hourly_proxy(root: Path, coverage_path: Path) -> dict[str, pd.DataFrame]:
    if not coverage_path.exists():
        raise SystemExit(f"missing hourly coverage file: {coverage_path}")
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    loaded: dict[str, pd.DataFrame] = {}
    for coin_id, record in coverage.items():
        if not isinstance(record, dict) or not record.get("available"):
            continue
        pair = str(record.get("pair", ""))
        if not pair:
            continue
        path = root / f"{pair}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        required = {"open_time", "open", "high", "low", "close"}
        if frame.empty or not required.issubset(frame.columns):
            continue
        frame = frame.copy()
        frame.index = pd.to_datetime(frame["open_time"], utc=True, errors="coerce")
        frame = frame.loc[:, ["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
        frame = frame[~frame.index.duplicated(keep="last")].dropna().sort_index()
        if not frame.empty:
            loaded[str(coin_id)] = frame
    return loaded


def _long_targets(built, index: pd.DatetimeIndex) -> dict[pd.Timestamp, pd.Series]:
    result: dict[pd.Timestamp, pd.Series] = {}
    for date, weights in built.targets.items():
        timestamp = pd.Timestamp(date)
        if timestamp not in index:
            continue
        exposure = built.exposures.get(timestamp)
        if exposure is None:
            continue
        result[timestamp] = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--hourly-root", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_engine_validation"))
    args = parser.parse_args()
    configure_logging("ERROR")

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    _, _, built, trial_id = _resolve_build(market, universe, index, None)
    targets = _long_targets(built, index)
    marks = _load_hourly_proxy(args.hourly_root, args.hourly_root / "coverage.json")
    available = set(marks)
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
        for date, weights in targets.items()
    }
    restricted_built = SimpleNamespace(
        targets=restricted,
        exposures={
            date: float(weights.sum())
            for date, weights in restricted.items()
        },
    )
    restricted_spot = _production_result(
        config,
        market,
        restricted_built,
        index,
        cost_bps=float(args.cost_bps),
    )
    result = run_derivative_backtest(
        marks,
        restricted,
        funding_rates=None,
        config=DerivativeBacktestConfig(
            initial_capital=1.0,
            taker_fee_bps=float(args.cost_bps),
            slippage_bps=0.0,
            liquidation_slippage_bps=5.0,
            max_gross_exposure=1.0,
            funding_missing_policy="skip",
            missing_mark_policy="carry",
            missing_mark_max_carry_hours=3,
        ),
    )
    spot = _production_result(config, market, built, index, cost_bps=float(args.cost_bps))
    metrics = _metrics_from_returns(result.daily_returns)
    spot_metrics = _metrics_from_returns(spot.daily_returns)
    restricted_spot_metrics = _metrics_from_returns(restricted_spot.daily_returns)
    summary = {
        "trial_id": trial_id,
        "mark_source": "binance_or_gate_1h_proxy",
        "warning": "diagnostic only; not a Bitget mark-price result",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": float(args.cost_bps),
        "available_mark_assets": sorted(available),
        "derivatives": metrics,
        "spot_h5": spot_metrics,
        "restricted_spot_h5": restricted_spot_metrics,
        "terminal_ratio_derivatives_over_restricted_spot": metrics["multiple"] / restricted_spot_metrics["multiple"],
        "terminal_ratio_derivatives_over_spot": metrics["multiple"] / spot_metrics["multiple"],
        "liquidation_count": int(len(result.liquidations)),
    }
    output_dir = ensure_dir(args.output_dir)
    result.daily_returns.to_csv(output_dir / "daily_returns.csv", header=True)
    result.equity_curve.to_csv(output_dir / "equity_curve.csv", header=True)
    result.trades.to_csv(output_dir / "trades.csv", index=False)
    result.liquidations.to_csv(output_dir / "liquidations.csv", index=False)
    result.mark_carries.to_csv(output_dir / "mark_carries.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote engine validation to {output_dir}")


if __name__ == "__main__":
    main()
