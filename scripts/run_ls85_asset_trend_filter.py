"""Run the pre-registered LS85 per-asset 200D trend filter on frozen LS57."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.derivatives.signals import (  # noqa: E402
    combine_long_with_cash_budgeted_short,
    scale_long_targets,
)
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_derivatives_backtest import (  # noqa: E402
    _funding_for_source,
    _long_targets_from_build,
    _restrict_targets,
)
from scripts.run_h5_regime_short_router import (  # noqa: E402
    FROZEN_CONFIG,
    LS57_CANDIDATE_ID,
    build_long_targets_for_trial,
    build_short_targets_for_trial,
)
from scripts.run_ls81_core_major_funding_carry import (  # noqa: E402
    _run_engine,
    _sample_metrics,
    _scenario_config,
    _summary_row,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402

TRIAL_ID = "PR2026-11-LS85-LS57-ASSET-TREND-200D"


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def filter_long_targets_by_asset_ma(
    targets: Mapping[pd.Timestamp, pd.Series],
    *,
    prices: pd.DataFrame,
    ma_days: int = 200,
) -> tuple[dict[pd.Timestamp, pd.Series], pd.DataFrame]:
    """Drop long legs below their own trailing SMA; leave freed weight in cash."""
    if ma_days < 2:
        raise ValueError("ma_days must be at least two")
    price_frame = prices.copy()
    price_frame.index = pd.DatetimeIndex([_as_utc(value) for value in price_frame.index])
    price_frame = price_frame[~price_frame.index.duplicated(keep="last")].sort_index()
    moving_average = price_frame.rolling(ma_days, min_periods=ma_days).mean()
    filtered: dict[pd.Timestamp, pd.Series] = {}
    audit_rows: list[dict[str, Any]] = []
    for raw_date, raw_target in sorted(targets.items(), key=lambda item: _as_utc(item[0])):
        date = _as_utc(raw_date)
        target = pd.to_numeric(pd.Series(raw_target), errors="coerce").fillna(0.0)
        target.index = target.index.astype(str)
        if (target < 0.0).any():
            raise ValueError("long targets must be non-negative")
        close_history = price_frame.loc[:date]
        ma_history = moving_average.loc[:date]
        if close_history.empty or ma_history.empty:
            filtered[date] = target.astype(float).sort_index()
            audit_rows.append(
                {
                    "date": date,
                    "filtered_weight": 0.0,
                    "cash_weight": 0.0,
                    "missing_ma_count": int(len(target)),
                    "filtered_assets": "",
                }
            )
            continue
        close = close_history.iloc[-1]
        moving = ma_history.iloc[-1]
        output = target.copy()
        filtered_assets: list[str] = []
        missing_ma_count = 0
        filtered_weight = 0.0
        for asset in target.index:
            weight = float(target.loc[asset])
            if weight <= 0.0:
                continue
            if asset not in close.index or asset not in moving.index:
                missing_ma_count += 1
                continue
            close_value = float(close.loc[asset])
            ma_value = float(moving.loc[asset])
            if not np.isfinite(close_value) or not np.isfinite(ma_value):
                missing_ma_count += 1
                continue
            if close_value < ma_value:
                output.loc[asset] = 0.0
                filtered_weight += weight
                filtered_assets.append(asset)
        output = output[output.abs() > 1e-15].sort_index()
        filtered[date] = output
        audit_rows.append(
            {
                "date": date,
                "filtered_weight": filtered_weight,
                "cash_weight": filtered_weight,
                "missing_ma_count": missing_ma_count,
                "filtered_assets": ",".join(filtered_assets),
            }
        )
    return filtered, pd.DataFrame(audit_rows)


def _report(
    summary: pd.DataFrame,
    filter_audit: pd.DataFrame,
    *,
    trial_id: str,
    ma_days: int,
) -> str:
    lines = [
        f"# {trial_id}",
        "",
        "- Base: frozen LS57",
        f"- New rule: drop a long leg when signal-day close is below its own {ma_days}D SMA",
        "- No redistribution; freed weight remains cash; short router unchanged",
        "",
        "## Runs",
        "",
        dataframe_to_markdown(
            summary[
                [
                    "label",
                    "cost_bps",
                    "funding_scenario",
                    "full_multiple",
                    "full_sharpe",
                    "full_max_drawdown",
                    "validation_multiple",
                    "validation_sharpe",
                    "max_observed_gross",
                    "gross_breach_hours",
                    "liquidation_count",
                ]
            ].reset_index(drop=True)
        ),
        "",
        "## Filter audit",
        "",
        f"- Events with at least one filtered leg: {int((filter_audit['filtered_weight'] > 0).sum()) if not filter_audit.empty else 0}",
        f"- Total filtered/cash weight: {float(filter_audit['filtered_weight'].sum()) if not filter_audit.empty else 0.0:.6f}",
        f"- Missing-MA leg observations: {int(filter_audit['missing_ma_count'].sum()) if not filter_audit.empty else 0}",
        "",
        "## Decision",
        "",
    ]
    base20 = summary.loc[
        (summary["label"] == "LS57 baseline")
        & (summary["cost_bps"] == 20.0)
        & (summary["funding_scenario"] == "normal")
    ]
    filtered20 = summary.loc[
        (~summary["base"])
        & (summary["cost_bps"] == 20.0)
        & (summary["funding_scenario"] == "normal")
    ]
    if base20.empty or filtered20.empty:
        lines.append("Normal 20bps baseline/filtered run is incomplete.")
    else:
        base = base20.iloc[0]
        candidate = filtered20.iloc[0]
        passed = (
            candidate["full_multiple"] >= base["full_multiple"]
            and candidate["full_sharpe"] >= base["full_sharpe"]
            and candidate["full_max_drawdown"] >= base["full_max_drawdown"] + 0.02
            and candidate["validation_multiple"] >= base["validation_multiple"]
            and candidate["validation_sharpe"] >= base["validation_sharpe"]
            and candidate["liquidation_count"] == 0
            and candidate["gross_breach_hours"] == 0
        )
        lines.append(
            f"20bps full: base {base['full_multiple']:.4f}x / {base['full_sharpe']:.4f} / "
            f"{base['full_max_drawdown']:.4%}; filtered {candidate['full_multiple']:.4f}x / "
            f"{candidate['full_sharpe']:.4f} / {candidate['full_max_drawdown']:.4%}."
        )
        lines.append("Primary 20bps gate: **PASS**." if passed else "Primary 20bps gate: **FAIL**.")
        if passed:
            lines.append("Research-only gate passed; cost/adverse/rolling checks remain required.")
    lines.extend(["", "Research output only; no orders sent.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", default=TRIAL_ID)
    parser.add_argument("--warmup-start", default="2021-01-01")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_20261009"))
    parser.add_argument("--market-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_market_20261009"))
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--costs-bps", default="20,50,100")
    parser.add_argument("--funding-scenarios", default="normal,two-sided-adverse-3x")
    parser.add_argument("--ma-days", type=int, default=200)
    parser.add_argument("--long-buffer", type=float, default=float(FROZEN_CONFIG["long_buffer"]))
    parser.add_argument("--target-gross", type=float, default=float(FROZEN_CONFIG["max_total_gross"]))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    costs = [float(value) for value in args.costs_bps.split(",") if value.strip()]
    scenarios = [value.strip() for value in args.funding_scenarios.split(",") if value.strip()]
    if not costs or not scenarios:
        parser.error("costs and funding scenarios must be non-empty")
    if any(value < 0.0 for value in costs):
        parser.error("costs must be non-negative")
    if args.ma_days < 2:
        parser.error("ma-days must be at least two")
    if not 0.0 < args.long_buffer < 1.0:
        parser.error("long-buffer must be in (0, 1)")
    if not 0.0 < args.target_gross <= float(FROZEN_CONFIG["max_total_gross"]):
        parser.error("target-gross must be positive and no greater than the frozen cap")
    start = pd.Timestamp(args.start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    if start >= end:
        parser.error("start-date must precede end-date")

    _, market, universe, index = _load_market(
        args.config,
        start_date=args.warmup_start,
        end_date=args.end_date,
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_raw = _long_targets_from_build(built, index)
    mark_symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    market_symbol_map = pd.read_csv(args.market_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, mark_symbol_map)
    market_candles = load_mark_candles(args.market_dir, market_symbol_map, candle_type="market")
    trade_available = set(mark_candles).intersection(market_candles)
    restricted, _ = _restrict_targets(long_raw, trade_available, market_candles)
    long_targets = scale_long_targets(
        restricted,
        leverage=float(FROZEN_CONFIG["h5_leverage"]),
        max_gross=float(FROZEN_CONFIG["h5_leverage"]),
    )
    funding = _funding_for_source(
        "binance-proxy",
        raw_dir=args.raw_dir,
        binance_dir=args.binance_funding_dir,
        symbol_map=mark_symbol_map,
        coins=set(market.price.columns),
    )
    funding = funding.dropna(how="all").loc[:, funding.notna().any(axis=0)]
    funding_intervals: dict[str, float] = {}
    if "fund_interval" in mark_symbol_map.columns:
        for record in mark_symbol_map.to_dict("records"):
            interval = pd.to_numeric(record.get("fund_interval"), errors="coerce")
            if pd.notna(interval) and float(interval) > 0.0:
                funding_intervals[str(record["coin_id"])] = float(interval)

    long_targets, long_audit = build_long_targets_for_trial(
        trial_id=LS57_CANDIDATE_ID,
        long_targets=long_targets,
        funding_rates=funding,
        universe=universe,
        available=trade_available,
        prices=market.price,
    )
    short_targets, _, _, _ = build_short_targets_for_trial(
        trial_id=LS57_CANDIDATE_ID,
        market=market,
        universe=universe,
        index=index,
        long_raw=long_raw,
        long_targets=long_targets,
        funding=funding,
        available=trade_available,
        mark_candles=market_candles,
        start_date=args.warmup_start,
        profit_lock_audit=long_audit,
    )
    base_targets, base_audit = combine_long_with_cash_budgeted_short(
        long_targets,
        short_targets,
        max_total_gross=float(args.target_gross),
    )
    filtered_long, filter_audit = filter_long_targets_by_asset_ma(
        long_targets,
        prices=market.price,
        ma_days=int(args.ma_days),
    )
    filtered_targets, filtered_audit = combine_long_with_cash_budgeted_short(
        filtered_long,
        short_targets,
        max_total_gross=float(args.target_gross),
    )

    rows: list[dict[str, Any]] = []
    result_frames: dict[str, pd.DataFrame] = {}
    event_frames: dict[str, dict[str, pd.DataFrame]] = {}
    for scenario in scenarios:
        stress, multiplier = _scenario_config(scenario)
        for cost in costs:
            for label, targets, audit, base in (
                ("LS57 baseline", base_targets, base_audit, True),
                (f"{args.trial_id} {args.ma_days}D filter", filtered_targets, filtered_audit, False),
            ):
                result = _run_engine(
                    mark_candles=mark_candles,
                    market_candles=market_candles,
                    targets=targets,
                    funding=funding,
                    funding_intervals=funding_intervals,
                    funding_missing_policy="skip",
                    funding_stress=stress,
                    funding_multiplier=multiplier,
                    cost_bps=cost,
                    long_buffer=float(args.long_buffer),
                    target_gross=float(args.target_gross),
                    start_time=start,
                    end_time=end,
                )
                key = f"{'base' if base else 'filtered'}_{scenario}_{cost:g}"
                result_frames[key] = pd.DataFrame(
                    {
                        "daily_return": result.daily_returns,
                        "gross_exposure": result.gross_exposure.reindex(result.daily_returns.index),
                    }
                )
                event_frames[key] = {
                    "liquidations": result.liquidations,
                    "mark_carries": result.mark_carries,
                }
                rows.append(
                    _summary_row(
                        label=label,
                        allocation=0.0,
                        cost_bps=cost,
                        scenario=scenario,
                        result=result,
                        target_audit=audit,
                        long_buffer=float(args.long_buffer),
                        target_gross=float(args.target_gross),
                        base=base,
                    )
                )
    summary = pd.DataFrame(rows)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "run_summary.csv", index=False)
    filter_audit.to_csv(output_dir / "filter_audit.csv", index=False)
    pd.DataFrame(base_audit).to_csv(output_dir / "base_target_gross.csv", index_label="date")
    pd.DataFrame(filtered_audit).to_csv(output_dir / "filtered_target_gross.csv", index_label="date")
    for key, frame in result_frames.items():
        frame.to_csv(output_dir / f"daily_{key}.csv", index_label="date")
    for key, frames in event_frames.items():
        for name, frame in frames.items():
            frame.to_csv(output_dir / f"{name}_{key}.csv", index=False)
    manifest = {
        "trial_id": args.trial_id,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "warmup_start": args.warmup_start,
        "costs_bps": costs,
        "funding_scenarios": scenarios,
        "ma_days": int(args.ma_days),
        "long_buffer": float(args.long_buffer),
        "target_gross": float(args.target_gross),
        "filtered_to_cash": True,
        "gross_cap": float(FROZEN_CONFIG["max_total_gross"]),
        "orders_sent": False,
        "raw_ledgers_retained": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        _report(summary, filter_audit, trial_id=args.trial_id, ma_days=int(args.ma_days)),
        encoding="utf-8",
    )
    print(f"wrote {output_dir}; runs={len(summary)}")
    print(
        summary[
            [
                "label",
                "cost_bps",
                "funding_scenario",
                "full_multiple",
                "full_sharpe",
                "full_max_drawdown",
                "validation_multiple",
                "validation_sharpe",
                "liquidation_count",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
