"""Run one pre-registered Bitget derivatives trial.

This is a research runner, not an order router.  It reconstructs the frozen
H5 long targets with the production strategy code, maps them onto Bitget mark
candles, optionally adds the pre-registered short overlay, and runs the
isolated-margin engine with explicit funding and hourly liquidation checks.
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

from atlas20.derivatives.data import (  # noqa: E402
    load_binance_funding,
    load_bitget_funding,
    load_mark_candles,
)
from atlas20.derivatives.engine import DerivativeBacktestConfig, run_derivative_backtest  # noqa: E402
from atlas20.derivatives.signals import build_derivative_targets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

TRIAL_RULES: dict[str, dict[str, object]] = {
    "PR2026-10-D-L125": {"leverage": 1.25, "short_asset": None, "short_weight": 0.0},
    "PR2026-10-D-L150": {"leverage": 1.50, "short_asset": None, "short_weight": 0.0},
    "PR2026-10-D-L200": {"leverage": 2.00, "short_asset": None, "short_weight": 0.0},
    "PR2026-10-D-SBTC25": {"leverage": 1.25, "short_asset": "bitcoin", "short_weight": 0.25},
    "PR2026-10-D-SBTC50": {"leverage": 1.25, "short_asset": "bitcoin", "short_weight": 0.50},
    "PR2026-10-D-SWEAK25": {"leverage": 1.25, "short_asset": "weakest", "short_weight": 0.25},
    "PR2026-10-D-SWEAK50": {"leverage": 1.25, "short_asset": "weakest", "short_weight": 0.50},
}
STOP_TRIALS = {
    "PR2026-10-D-S-BTC25-STOP20": {"short_asset": "bitcoin", "short_weight": 0.25},
    "PR2026-10-D-S-WEAK25-STOP20": {"short_asset": "weakest", "short_weight": 0.25},
}
COST_TRIALS = {
    "PR2026-10-D-L125-COST50": {"leverage": 1.25, "short_asset": None, "short_weight": 0.0},
    "PR2026-10-D-L125-COST100": {"leverage": 1.25, "short_asset": None, "short_weight": 0.0},
}


def _long_targets_from_build(built, index: pd.DatetimeIndex) -> dict[pd.Timestamp, pd.Series]:
    targets: dict[pd.Timestamp, pd.Series] = {}
    for date, weights in built.targets.items():
        timestamp = pd.Timestamp(date)
        if timestamp not in index:
            continue
        exposure = built.exposures.get(timestamp)
        if exposure is None:
            continue
        targets[timestamp] = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    return targets


def _has_execution_mark(
    mark_candles: dict[str, pd.DataFrame],
    asset: str,
    date: pd.Timestamp,
) -> bool:
    frame = mark_candles.get(asset)
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


def _restrict_targets(
    targets: dict[pd.Timestamp, pd.Series],
    available: set[str],
    mark_candles: dict[str, pd.DataFrame],
) -> tuple[dict[pd.Timestamp, pd.Series], pd.Series]:
    """Drop unavailable Bitget assets to cash without renormalizing the book."""
    restricted: dict[pd.Timestamp, pd.Series] = {}
    dropped_rows: list[dict[str, object]] = []
    for date, weights in targets.items():
        weights = pd.to_numeric(weights, errors="coerce").fillna(0.0)
        keep_mask = weights.index.isin(available) & pd.Index(
            [
                _has_execution_mark(mark_candles, str(asset), pd.Timestamp(date))
                for asset in weights.index
            ]
        )
        keep = weights[keep_mask]
        dropped = weights[~keep_mask]
        if not dropped.empty:
            dropped_rows.extend(
                {
                    "date": date,
                    "coin_id": coin_id,
                    "weight": float(weight),
                }
                for coin_id, weight in dropped.items()
                if abs(float(weight)) > 1e-15
            )
        restricted[date] = keep
    return restricted, pd.DataFrame(dropped_rows)


def _funding_for_source(
    source: str,
    *,
    raw_dir: Path,
    binance_dir: Path,
    symbol_map: pd.DataFrame,
    coins: set[str],
) -> pd.DataFrame:
    if source == "zero":
        return pd.DataFrame()
    if source == "binance-proxy":
        return load_binance_funding(binance_dir, coins=coins)
    if source == "bitget-exact":
        return load_bitget_funding(raw_dir, symbol_map, coins=coins)
    raise ValueError(f"unknown funding source {source!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--trial-id", default="PR2026-10-D-L125")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--short-buffer", type=float, default=0.50)
    parser.add_argument(
        "--missing-mark-policy",
        choices=("error", "carry", "exit_last"),
        default="error",
        help="error is the production default; carry/exit_last are diagnostics only",
    )
    parser.add_argument("--missing-mark-max-carry-hours", type=int, default=3)
    parser.add_argument(
        "--funding-source",
        choices=("zero", "binance-proxy", "bitget-exact"),
        default="zero",
        help="zero is only for engine validation; binance-proxy is not exact Bitget history",
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives"))
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_backtest"))
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
    available_marks = set(mark_candles)

    if args.trial_id in STOP_TRIALS:
        raise SystemExit(
            f"{args.trial_id} requires the pre-registered adverse-stop overlay, which is not "
            "implemented in this runner yet"
        )
    if args.trial_id in COST_TRIALS:
        rule = COST_TRIALS[args.trial_id]
    else:
        rule = TRIAL_RULES.get(args.trial_id)
    if rule is None:
        raise SystemExit(f"unknown or unimplemented trial id: {args.trial_id}")

    funding = _funding_for_source(
        args.funding_source,
        raw_dir=args.raw_dir,
        binance_dir=args.binance_funding_dir,
        symbol_map=symbol_map,
        coins=set(market.price.columns),
    )
    available = available_marks & (set(funding.columns) if not funding.empty else available_marks)
    restricted, dropped = _restrict_targets(long_targets, available, mark_candles)
    short_asset = rule["short_asset"]
    short_weight = float(rule["short_weight"])
    leverage = float(rule["leverage"])
    max_gross = leverage + short_weight

    derivative_targets = build_derivative_targets(
        restricted,
        btc_close=market.price["bitcoin"],
        universe=universe,
        prices=market.price,
        funding_rates=funding if not funding.empty else None,
        leverage=leverage,
        max_gross=max_gross,
        short_asset=short_asset,
        short_weight=short_weight,
        eligible=available,
    )

    cfg = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(args.long_buffer),
        short_buffer=float(args.short_buffer),
        max_gross_exposure=max_gross,
        funding_missing_policy="error",
        missing_mark_policy=args.missing_mark_policy,
        missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
    )
    result = run_derivative_backtest(
        mark_candles,
        derivative_targets,
        funding_rates=funding if not funding.empty else None,
        config=cfg,
    )
    metrics = _metrics_from_returns(result.daily_returns)
    summary = {
        "trial_id": args.trial_id,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": float(args.cost_bps),
        "funding_source": args.funding_source,
        "leverage": leverage,
        "short_asset": short_asset,
        "short_weight": short_weight,
        "max_gross": max_gross,
        "available_marks": sorted(available_marks),
        "funding_columns": sorted(funding.columns.tolist()),
        "dropped_target_rows": int(len(dropped)),
        "liquidation_count": int(len(result.liquidations)),
        "funding_total": float(result.funding["amount"].sum()) if not result.funding.empty else 0.0,
        "fees_total": float(result.trades["fee"].sum()) if not result.trades.empty else 0.0,
        "max_gross_exposure": float(result.gross_exposure.max()) if not result.gross_exposure.empty else 0.0,
        **metrics,
    }
    output_dir = ensure_dir(args.output_dir / args.trial_id)
    result.equity_curve.to_csv(output_dir / "equity_curve.csv", header=True)
    result.daily_returns.to_csv(output_dir / "daily_returns.csv", header=True)
    result.trades.to_csv(output_dir / "trades.csv", index=False)
    result.funding.to_csv(output_dir / "funding.csv", index=False)
    result.liquidations.to_csv(output_dir / "liquidations.csv", index=False)
    result.positions.to_csv(output_dir / "positions.csv", index=False)
    dropped.to_csv(output_dir / "dropped_targets.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                f"# {args.trial_id}",
                "",
                f"- Window: {args.start_date} to {args.end_date}",
                f"- Cost: {args.cost_bps:g} bps",
                f"- Funding source: `{args.funding_source}`",
                f"- Terminal multiple: {metrics['multiple']:.4f}x",
                f"- Sharpe: {metrics['sharpe']:.4f}",
                f"- Max drawdown: {metrics['max_drawdown']:.4%}",
                f"- Liquidations: {summary['liquidation_count']}",
                f"- Funding total: {summary['funding_total']:.6f}",
                f"- Fees total: {summary['fees_total']:.6f}",
                f"- Dropped target rows: {summary['dropped_target_rows']}",
                "",
                "This is a research output, not an order or a live approval.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote derivatives backtest to {output_dir}")


if __name__ == "__main__":
    main()
