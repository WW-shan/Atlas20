"""Out-of-sample tracker for the frozen L125-V2 derivatives specification.

The frozen in-sample window ends at 2026-09-21 00:00 UTC.  Everything after
that is recorded here and is never used to choose a parameter: the H5
selection, the 1.25x leverage and the 50% isolated-margin long buffer are
frozen, and this script only converts them into a daily target book plus the
rebalance that the target implies.  Funding is reported as an upper bound
(zero) because no exact Bitget funding history exists for the period.
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

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.derivatives.engine import (  # noqa: E402
    DerivativeBacktestConfig,
    run_derivative_backtest,
)
from atlas20.derivatives.signals import scale_long_targets  # noqa: E402
from atlas20.logging_utils import ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_bitget_mark_matrix import _funding_intervals  # noqa: E402
from scripts.run_derivatives_backtest import _long_targets_from_build, _restrict_targets  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

TRACKED_SPEC = "PR2026-10-D-L125-V2"
OOS_START = "2026-09-22"


def _weights_table(targets: dict[pd.Timestamp, pd.Series], capital: float) -> pd.DataFrame:
    """Per-signal target book with the delta against the previous signal."""

    rows: list[dict[str, object]] = []
    previous: pd.Series | None = None
    for signal_time in sorted(targets):
        weights = targets[signal_time]
        if previous is not None:
            index = previous.index.union(weights.index)
            current = weights.reindex(index).fillna(0.0)
            delta = current - previous.reindex(index).fillna(0.0)
        else:
            index = weights.index
            current = weights.reindex(index).fillna(0.0)
            delta = current
        for asset in index:
            weight = float(current.loc[asset])
            change = float(delta.loc[asset])
            if abs(weight) <= 1e-15 and abs(change) <= 1e-15:
                continue
            rows.append(
                {
                    "signal_date": signal_time,
                    "execution_hint": signal_time.normalize() + pd.Timedelta(days=1, hours=3),
                    "asset": asset,
                    "target_weight": weight,
                    "target_notional_per_1k": weight * capital,
                    "change_weight": change,
                    "change_notional_per_1k": change * capital,
                    "action": (
                        "HOLD"
                        if abs(change) <= 1e-9
                        else ("BUY" if change > 0 else "SELL")
                    ),
                }
            )
        previous = weights
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--mark-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_oos_20261009"))
    parser.add_argument("--start-date", default=OOS_START)
    parser.add_argument(
        "--carry-days",
        type=int,
        default=3,
        help="run the engine this many days before the OOS start so the frozen book is carried in",
    )
    parser.add_argument(
        "--warmup-start",
        default="2021-01-01",
        help="panel start for signal warm-up; the evaluation still starts at --start-date",
    )
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--leverage", type=float, default=1.25)
    parser.add_argument("--long-buffer", type=float, default=0.50)
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_oos_2026"))
    args = parser.parse_args()

    start = pd.Timestamp(args.start_date, tz="UTC")
    signal_start = args.warmup_start
    symbol_map = pd.read_csv(args.mark_dir / "symbol_map.csv")
    marks = load_mark_candles(args.mark_dir, symbol_map)
    if not marks:
        raise SystemExit(f"no market candles found in {args.mark_dir}/candles")
    last_mark = max(frame.index.max() for frame in marks.values())
    end_date = args.end_date or str(pd.Timestamp(last_mark).normalize().date())
    first_mark = min(frame.index.min() for frame in marks.values())
    engine_start = max(start - pd.Timedelta(days=max(args.carry_days, 0)), pd.Timestamp(first_mark))
    config, market, universe, index = _load_market(
        args.config, start_date=signal_start, end_date=end_date
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    long_targets = _long_targets_from_build(built, index)
    available = set(marks)
    restricted, dropped = _restrict_targets(long_targets, available, marks)
    intervals = _funding_intervals(symbol_map)
    scaled = scale_long_targets(restricted, leverage=args.leverage, max_gross=args.leverage)

    end = pd.Timestamp(last_mark) + pd.Timedelta(hours=1)

    result = run_derivative_backtest(
        marks,
        scaled,
        funding_rates=None,
        funding_intervals_hours=None,
        config=DerivativeBacktestConfig(
            initial_capital=1.0,
            taker_fee_bps=float(args.cost_bps),
            slippage_bps=0.0,
            liquidation_slippage_bps=5.0,
            long_buffer=float(args.long_buffer),
            short_buffer=0.50,
            fee_buffer=0.005,
            maintenance_margin_rate=0.01,
            max_margin_utilization=0.85,
            max_gross_exposure=args.leverage,
            funding_missing_policy="error",
            missing_mark_policy="carry",
            missing_mark_max_carry_hours=3,
        ),
        start_time=engine_start,
        end_time=end,
    )

    oos_returns = result.daily_returns[result.daily_returns.index >= start]
    if pd.Timestamp(last_mark).hour < 23:
        # the final day is still forming; keep the tracked series to full days
        oos_returns = oos_returns[oos_returns.index < pd.Timestamp(last_mark).normalize()]
    if oos_returns.empty:
        raise SystemExit("no out-of-sample daily returns in the requested window")
    daily = oos_returns.rename("daily_return").to_frame()
    daily["nav_multiple"] = (1.0 + daily["daily_return"]).cumprod()
    daily = daily.reset_index(names="date")
    targets = _weights_table(
        {time: target for time, target in scaled.items() if time >= start},
        capital=float(args.capital),
    )
    metrics = _metrics_from_returns(oos_returns)

    output_dir = ensure_dir(args.output_dir)
    daily.to_csv(output_dir / "oos_daily.csv", index=False)
    targets.to_csv(output_dir / "oos_targets.csv", index=False)
    result.trades.to_csv(output_dir / "oos_trades.csv", index=False)
    if not result.liquidations.empty:
        result.liquidations.to_csv(output_dir / "oos_liquidations.csv", index=False)
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "tracked_spec": TRACKED_SPEC,
                "leverage": float(args.leverage),
                "long_buffer": float(args.long_buffer),
                "cost_bps": float(args.cost_bps),
                "funding": "zero (upper bound; no exact Bitget history)",
                "start": str(start),
                "engine_start": str(engine_start),
                "carry_days": int(args.carry_days),
                "end": str(end),
                "days": int(len(daily)),
                "mark_dir": str(args.mark_dir),
                "dropped_target_rows": int(len(dropped)),
                "liquidations": int(len(result.liquidations)),
                "metrics": metrics,
            },
            indent=2,
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )

    latest_signal = max(scaled) if scaled else None
    latest_rows = targets[targets["signal_date"] == latest_signal] if latest_signal is not None else targets
    lines = [
        f"# Derivatives Track OOS Tracker — {TRACKED_SPEC}",
        "",
        f"- window: {start} → {end} ({len(daily)} daily returns)",
        f"- frozen spec: H5 long book × {args.leverage:g}, isolated margin, long buffer {args.long_buffer:.0%}, 20 bps, T+1 +3h fills",
        "- funding: **zero (upper bound)** — no exact Bitget funding history exists for this period",
        "",
        "## Out-of-sample metrics",
        "",
        dataframe_to_markdown(pd.DataFrame([{"spec": TRACKED_SPEC, **metrics}])),
        "",
        "## Latest target book",
        "",
        f"- signal date: {latest_signal}",
        f"- capital reference: {args.capital:,.0f} units",
        "",
        dataframe_to_markdown(
            latest_rows[
                [
                    "asset",
                    "target_weight",
                    "target_notional_per_1k",
                    "change_weight",
                    "change_notional_per_1k",
                    "action",
                ]
            ]
        ),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "days": int(len(daily)), "end": str(end)}, indent=2, default=str))
    print(f"Wrote derivatives OOS tracker to {output_dir}")


if __name__ == "__main__":
    main()
