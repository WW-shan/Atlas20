"""Run the V2 long-only matrix on Bitget mark candles.

This is the Bitget mark-price reproduction step.  It deliberately keeps the
H5 selection frozen, applies the revised 50% long liquidation buffer, and
compares zero funding with explicit Binance-proxy adverse funding bands.
The funding bands are stress scenarios, not exact Bitget history.
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

from atlas20.derivatives.data import load_binance_funding, load_mark_candles  # noqa: E402
from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.derivatives.signals import scale_long_targets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

SCENARIOS = {
    "zero": (None, "none", 0.0, False),
    "zero-funding-universe": (None, "none", 0.0, True),
    "binance-proxy": ("binance-proxy", "none", 1.0, True),
    "binance-long-adverse-2x": ("binance-proxy", "long-adverse", 2.0, True),
    "binance-long-adverse-3x": ("binance-proxy", "long-adverse", 3.0, True),
}


def _leverages(value: str) -> list[float]:
    leverages = sorted({float(item) for item in value.split(",") if item.strip()})
    if not leverages or any(leverage <= 0.0 for leverage in leverages):
        raise argparse.ArgumentTypeError("--leverage must contain positive numbers")
    return leverages


def _funding_intervals(symbol_map: pd.DataFrame) -> dict[str, float]:
    intervals: dict[str, float] = {}
    if "fund_interval" not in symbol_map.columns:
        return intervals
    for record in symbol_map.to_dict("records"):
        interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
        if pd.notna(interval) and float(interval) > 0.0:
            intervals[str(record["coin_id"])] = float(interval)
    return intervals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument(
        "--end-date",
        default="2026-09-21",
        help="exclusive end of the frozen evaluation window (UTC)",
    )
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--leverage", type=_leverages, default=_leverages("1.25,1.5,2.0"))
    parser.add_argument(
        "--long-buffer",
        type=_leverages,
        default=_leverages("0.5"),
        help="isolated-margin long buffer; comma-separated values are swept",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=tuple(SCENARIOS),
        help="scenario to run; repeatable (default: all scenarios)",
    )
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument(
        "--missing-mark-policy",
        choices=("error", "carry", "exit_last"),
        default="carry",
    )
    parser.add_argument("--missing-mark-max-carry-hours", type=int, default=3)
    parser.add_argument(
        "--min-mark-assets",
        type=int,
        default=50,
        help="refuse to run the matrix on an obviously partial merged data tree",
    )
    parser.add_argument(
        "--funding-missing-policy",
        choices=("error", "skip", "carry_last", "stress_median"),
        default="error",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_bitget_mark"))
    args = parser.parse_args()
    configure_logging("ERROR")

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_targets = _long_targets_from_build(built, index)
    symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, symbol_map)
    if len(mark_candles) < args.min_mark_assets:
        raise SystemExit(
            f"only {len(mark_candles)} mark series found in {args.raw_dir}; "
            f"expected at least {args.min_mark_assets} (override with --min-mark-assets)"
        )
    available_marks = set(mark_candles)
    intervals = _funding_intervals(symbol_map)
    proxy_funding = load_binance_funding(args.binance_funding_dir, coins=set(market.price.columns))

    rows: list[dict[str, object]] = []
    return_columns: dict[str, pd.Series] = {}
    scenarios = args.scenario or list(SCENARIOS)
    for leverage in args.leverage:
      for long_buffer in args.long_buffer:
        for scenario in scenarios:
              funding_source, funding_stress, multiplier, restrict_to_funding = SCENARIOS[scenario]
              if funding_source is None:
                  funding = pd.DataFrame()
              else:
                  funding = proxy_funding.copy()
                  if funding_stress == "long-adverse":
                      funding = funding.clip(lower=0.0)
                  elif funding_stress == "short-adverse":
                      funding = funding.clip(upper=0.0)
                  if multiplier != 1.0:
                      funding = funding * multiplier
                  funding = funding.dropna(how="all").loc[:, funding.notna().any(axis=0)]
                  if funding.empty:
                      raise SystemExit(
                          f"scenario {scenario} has no usable funding columns in {args.binance_funding_dir}"
                      )
              available = available_marks
              if restrict_to_funding:
                  if proxy_funding.empty:
                      raise SystemExit(
                          f"scenario {scenario} requires Binance funding columns in "
                          f"{args.binance_funding_dir}"
                      )
                  available = available_marks & set(proxy_funding.columns)
              restricted, dropped = _restrict_targets(long_targets, available, mark_candles)
              scaled = scale_long_targets(restricted, leverage=leverage, max_gross=leverage)
              result = run_derivative_backtest(
                  mark_candles,
                  scaled,
                  funding_rates=funding if not funding.empty else None,
                  funding_intervals_hours=intervals if not funding.empty else None,
                  config=DerivativeBacktestConfig(
                      initial_capital=1.0,
                      taker_fee_bps=float(args.cost_bps),
                      slippage_bps=0.0,
                      liquidation_slippage_bps=5.0,
                      long_buffer=float(long_buffer),
                      short_buffer=0.50,
                      fee_buffer=0.005,
                      maintenance_margin_rate=0.01,
                      max_margin_utilization=0.85,
                      max_gross_exposure=leverage,
                      funding_missing_policy=args.funding_missing_policy,
                      missing_mark_policy=args.missing_mark_policy,
                      missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
                  ),
                  start_time=pd.Timestamp(args.start_date, tz="UTC"),
                  end_time=pd.Timestamp(args.end_date, tz="UTC"),
              )
              metrics = _metrics_from_returns(result.daily_returns)
              column = f"L{int(leverage * 100):03d}-{scenario}"
              return_columns[column] = result.daily_returns.rename(column)
              rows.append(
                  {
                      "scenario": scenario,
                      "mark_source": "bitget_mark",
                      "funding_source": funding_source or "zero",
                      "funding_stress": funding_stress,
                      "funding_multiplier": multiplier,
                      "restrict_to_funding": restrict_to_funding,
                      "leverage": leverage,
                      "long_buffer": float(long_buffer),
                      "cost_bps": float(args.cost_bps),
                      "missing_mark_policy": args.missing_mark_policy,
                      "funding_missing_policy": args.funding_missing_policy,
                      "available_mark_assets": len(available_marks),
                      "available_funding_assets": len(available),
                      "dropped_target_rows": int(len(dropped)),
                      "liquidation_count": int(len(result.liquidations)),
                      "max_gross_exposure": float(result.gross_exposure.max()),
                      "fees_total": float(result.trades["fee"].sum()) if not result.trades.empty else 0.0,
                      "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
                      **metrics,
                  }
              )
              print(rows[-1], flush=True)
    output_dir = ensure_dir(args.output_dir)
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "bitget_mark_matrix.csv", index=False)
    (output_dir / "bitget_mark_matrix.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8"
    )
    pd.DataFrame(return_columns).to_csv(output_dir / "daily_returns.csv", index_label="date")
    print(f"Wrote Bitget mark matrix to {output_dir}")


if __name__ == "__main__":
    main()
