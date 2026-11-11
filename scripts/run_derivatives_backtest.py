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
from typing import Any

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

TRIAL_RULES: dict[str, dict[str, Any]] = {
    "PR2026-10-D-L125": {"leverage": 1.25, "short_asset": None, "short_weight": 0.0},
    "PR2026-10-D-L150": {"leverage": 1.50, "short_asset": None, "short_weight": 0.0},
    "PR2026-10-D-L200": {"leverage": 2.00, "short_asset": None, "short_weight": 0.0},
    "PR2026-10-D-SBTC25": {"leverage": 1.25, "short_asset": "bitcoin", "short_weight": 0.25},
    "PR2026-10-D-SBTC50": {"leverage": 1.25, "short_asset": "bitcoin", "short_weight": 0.50},
    "PR2026-10-D-SWEAK25": {"leverage": 1.25, "short_asset": "weakest", "short_weight": 0.25},
    "PR2026-10-D-SWEAK50": {"leverage": 1.25, "short_asset": "weakest", "short_weight": 0.50},
    # 2026-11 reversal-short research family: the short leg is opened only
    # under the same BTC-bear and funding gates as the failed additive overlay.
    # R = replace the long book with a small short; F = only short when H5 is
    # already entirely in cash. No parameter sweep is allowed inside this family.
    "PR2026-11-RS-R-BTC25": {
        "leverage": 1.25,
        "short_asset": "bitcoin",
        "short_weight": 0.25,
        "short_mode": "replace",
    },
    "PR2026-11-RS-R-WEAK25": {
        "leverage": 1.25,
        "short_asset": "weakest",
        "short_weight": 0.25,
        "short_mode": "replace",
    },
    "PR2026-11-RS-F-BTC25": {
        "leverage": 1.25,
        "short_asset": "bitcoin",
        "short_weight": 0.25,
        "short_mode": "flat-only",
    },
    "PR2026-11-RS-F-WEAK25": {
        "leverage": 1.25,
        "short_asset": "weakest",
        "short_weight": 0.25,
        "short_mode": "flat-only",
    },
    # 2026-11 round 2: two fixed fast-BTC trend-short trials. The horizon is
    # pre-registered; do not add nearby windows as an implicit parameter sweep.
    "PR2026-11-RS2-A-BTC28": {
        "leverage": 1.25,
        "short_asset": "bitcoin",
        "short_weight": 0.25,
        "short_mode": "additive",
        "bear_ma_window": 50,
        "bear_return_window": 28,
    },
    "PR2026-11-RS2-F-BTC28": {
        "leverage": 1.25,
        "short_asset": "bitcoin",
        "short_weight": 0.25,
        "short_mode": "flat-only",
        "bear_ma_window": 50,
        "bear_return_window": 28,
    },
    "PR2026-11-RS3-X-WEAK14": {
        "leverage": 1.25,
        "short_asset": "weakest",
        "short_weight": 0.25,
        "short_mode": "cross-sectional",
        "cross_sectional_lookback": 14,
        "cross_sectional_rebalance_days": 7,
    },
    "PR2026-11-RS4-X-WEAK4": {
        "leverage": 1.25,
        "short_asset": "weakest",
        "short_weight": 0.25,
        "short_mode": "cross-sectional",
        "cross_sectional_lookback": 14,
        "cross_sectional_rebalance_days": 7,
        "cross_sectional_short_count": 4,
    },
    "PR2026-11-RS5-X-WEAK4-SB75": {
        "leverage": 1.25,
        "short_asset": "weakest",
        "short_weight": 0.25,
        "short_mode": "cross-sectional",
        "cross_sectional_lookback": 14,
        "cross_sectional_rebalance_days": 7,
        "cross_sectional_short_count": 4,
        "short_buffer": 0.75,
    },
    "PR2026-11-RS6-X-WEAK4-STOP20": {
        "leverage": 1.25,
        "short_asset": "weakest",
        "short_weight": 0.25,
        "short_mode": "cross-sectional",
        "cross_sectional_lookback": 14,
        "cross_sectional_rebalance_days": 7,
        "cross_sectional_short_count": 4,
        "short_stop_loss_pct": 0.20,
    },
    "PR2026-11-RS7-X-WEAK4-HOLD8-STOP20": {
        "leverage": 1.25,
        "short_asset": "weakest",
        "short_weight": 0.25,
        "short_mode": "cross-sectional",
        "cross_sectional_lookback": 14,
        "cross_sectional_rebalance_days": 7,
        "cross_sectional_short_count": 4,
        "cross_sectional_hold_rank": 8,
        "short_stop_loss_pct": 0.20,
    },
    "PR2026-11-LS11-H5-WEAK4-BEAR200-STOP20": {
        "leverage": 1.25,
        "short_asset": "weakest",
        "short_weight": 0.25,
        "short_mode": "cross-sectional",
        "cross_sectional_lookback": 14,
        "cross_sectional_rebalance_days": 7,
        "cross_sectional_short_count": 4,
        "cross_sectional_btc_ma_window": 200,
        "short_stop_loss_pct": 0.20,
    },
}
STOP_TRIALS: dict[str, dict[str, Any]] = {
    "PR2026-10-D-S-BTC25-STOP20": {"short_asset": "bitcoin", "short_weight": 0.25},
    "PR2026-10-D-S-WEAK25-STOP20": {"short_asset": "weakest", "short_weight": 0.25},
}
COST_TRIALS: dict[str, dict[str, Any]] = {
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


def _short_mark_available(
    mark_candles: dict[str, pd.DataFrame],
    asset: str,
    date: pd.Timestamp,
) -> bool:
    """Keep a short out of dates where its own fill mark is unavailable."""
    return _has_execution_mark(mark_candles, asset, date)


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
    parser.add_argument(
        "--end-date",
        default="2026-09-21",
        help="exclusive end of the frozen evaluation window (UTC)",
    )
    parser.add_argument("--trial-id", default="PR2026-10-D-L125")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--short-buffer", type=float, default=0.50)
    parser.add_argument(
        "--short-stop-loss-pct",
        type=float,
        default=None,
        help="optional adverse short mark move that closes the leg before liquidation",
    )
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
    parser.add_argument(
        "--funding-stress",
        choices=("none", "long-adverse", "short-adverse"),
        default="none",
        help="keep only the funding sign that hurts the stated side; use only as a stress band",
    )
    parser.add_argument("--funding-multiplier", type=float, default=1.0)
    parser.add_argument(
        "--funding-missing-policy",
        choices=("error", "skip", "carry_last", "stress_median"),
        default="error",
        help="error is the production default; skip is only for an explicitly labelled proxy stress run",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/bitget_derivatives/merged_20261009"),
        help="merged Bitget mark tree; the bare data/raw/bitget_derivatives directory is only a downloader shard root",
    )
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
    if args.funding_multiplier < 0.0:
        raise SystemExit("--funding-multiplier must be non-negative")

    funding = _funding_for_source(
        args.funding_source,
        raw_dir=args.raw_dir,
        binance_dir=args.binance_funding_dir,
        symbol_map=symbol_map,
        coins=set(market.price.columns),
    )
    if not funding.empty:
        funding = funding.dropna(how="all").loc[:, funding.notna().any(axis=0)]
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in symbol_map.columns:
        for record in symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)
    # Funding coverage is not a prerequisite for holding a long mark position
    # under the explicitly labelled proxy/skip convention. Restricting the whole
    # H5 book to the intersection with the funding columns would silently
    # replace assets with cash and make a short-overlay comparison invalid.
    available = available_marks
    restricted, dropped = _restrict_targets(long_targets, available, mark_candles)
    short_asset = rule["short_asset"]
    short_weight = float(rule["short_weight"])
    leverage = float(rule["leverage"])
    short_mode = str(rule.get("short_mode", "additive"))
    short_buffer = float(rule.get("short_buffer", args.short_buffer))
    short_stop_loss_pct = rule.get("short_stop_loss_pct", args.short_stop_loss_pct)
    max_gross = (
        leverage
        if short_mode in {"replace", "flat-only"}
        else leverage + short_weight
    )

    btc_ma_window = rule.get("cross_sectional_btc_ma_window")
    cross_sectional_entry_allowed = None
    if btc_ma_window is not None:
        btc_close = market.price["bitcoin"].copy()
        btc_close.index = pd.DatetimeIndex(
            [
                pd.Timestamp(value).tz_localize("UTC")
                if pd.Timestamp(value).tzinfo is None
                else pd.Timestamp(value).tz_convert("UTC")
                for value in btc_close.index
            ]
        )
        btc_close = btc_close[~btc_close.index.duplicated(keep="last")].sort_index()
        btc_ma = btc_close.rolling(
            int(btc_ma_window), min_periods=int(btc_ma_window)
        ).mean()

        def cross_sectional_entry_allowed(date: pd.Timestamp) -> bool:
            timestamp = pd.Timestamp(date)
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
            else:
                timestamp = timestamp.tz_convert("UTC")
            if timestamp not in btc_close.index:
                return False
            threshold = btc_ma.loc[timestamp]
            return bool(pd.notna(threshold) and float(btc_close.loc[timestamp]) < float(threshold))

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
        short_mode=short_mode,
        btc_asset="bitcoin",
        eligible=available,
        calendar=index if short_asset is not None else None,
        bear_ma_window=int(rule.get("bear_ma_window", 200)),
        bear_return_window=int(rule.get("bear_return_window", 30)),
        short_available=lambda asset, date: _short_mark_available(mark_candles, asset, date),
        cross_sectional_lookback=int(rule.get("cross_sectional_lookback", 14)),
        cross_sectional_rebalance_days=int(rule.get("cross_sectional_rebalance_days", 7)),
        cross_sectional_short_count=int(rule.get("cross_sectional_short_count", 1)),
        cross_sectional_hold_rank=(
            None
            if rule.get("cross_sectional_hold_rank") is None
            else int(rule["cross_sectional_hold_rank"])
        ),
        cross_sectional_anchor=args.start_date,
        cross_sectional_entry_allowed=cross_sectional_entry_allowed,
    )

    cfg = DerivativeBacktestConfig(
        initial_capital=1.0,
        taker_fee_bps=float(args.cost_bps),
        slippage_bps=0.0,
        liquidation_slippage_bps=5.0,
        long_buffer=float(args.long_buffer),
        short_buffer=short_buffer,
        short_stop_loss_pct=(
            None if short_stop_loss_pct is None else float(short_stop_loss_pct)
        ),
        max_gross_exposure=max_gross,
        funding_missing_policy=args.funding_missing_policy,
        funding_stress=args.funding_stress,
        funding_multiplier=float(args.funding_multiplier),
        missing_mark_policy=args.missing_mark_policy,
        missing_mark_max_carry_hours=int(args.missing_mark_max_carry_hours),
    )
    result = run_derivative_backtest(
        mark_candles,
        derivative_targets,
        funding_rates=funding if not funding.empty else None,
        funding_intervals_hours=funding_intervals if not funding.empty else None,
        config=cfg,
        start_time=pd.Timestamp(args.start_date, tz="UTC"),
        end_time=pd.Timestamp(args.end_date, tz="UTC"),
    )
    metrics = _metrics_from_returns(result.daily_returns)
    summary = {
        "trial_id": args.trial_id,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": float(args.cost_bps),
        "funding_source": args.funding_source,
        "funding_stress": args.funding_stress,
        "funding_multiplier": float(args.funding_multiplier),
        "funding_missing_policy": args.funding_missing_policy,
        "leverage": leverage,
        "short_asset": short_asset,
        "short_weight": short_weight,
        "short_mode": short_mode,
        "short_buffer": short_buffer,
        "cross_sectional_hold_rank": rule.get("cross_sectional_hold_rank"),
        "cross_sectional_btc_ma_window": rule.get("cross_sectional_btc_ma_window"),
        "short_stop_loss_pct": (
            None if short_stop_loss_pct is None else float(short_stop_loss_pct)
        ),
        "max_gross": max_gross,
        "available_marks": sorted(available_marks),
        "funding_columns": sorted(funding.columns.tolist()),
        "dropped_target_rows": int(len(dropped)),
        "liquidation_count": int(len(result.liquidations)),
        "stop_loss_count": int((result.trades.get("reason") == "stop_loss").sum()) if not result.trades.empty else 0,
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
                f"- Funding stress: `{args.funding_stress}` x {args.funding_multiplier:g}",
                f"- Terminal multiple: {metrics['multiple']:.4f}x",
                f"- Sharpe: {metrics['sharpe']:.4f}",
                f"- Max drawdown: {metrics['max_drawdown']:.4%}",
                f"- Liquidations: {summary['liquidation_count']}",
                f"- Short stop-losses: {summary['stop_loss_count']}",
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
