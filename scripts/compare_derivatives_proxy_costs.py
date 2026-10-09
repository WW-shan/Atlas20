"""Compare proxy derivatives cost stress with the frozen H5 +3h spot path.

This is a diagnostic over already pre-registered variants.  It does not add a
candidate or change the strategy rules; it makes the cost-stress comparison
reproducible and ensures both sides use the same +3h day-close execution.
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

from atlas20.backtest.intraday import load_hourly_bars, pre_fill_returns  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def _costs(value: str) -> list[float]:
    costs = sorted({float(item) for item in value.split(",") if item.strip()})
    if not costs or any(cost < 0.0 for cost in costs):
        raise argparse.ArgumentTypeError("--costs must be a comma-separated list of non-negative numbers")
    return costs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--costs", type=_costs, default=_costs("6,8,11,20,50,100"))
    parser.add_argument("--hourly-dir", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--proxy-root", type=Path, default=Path("reports"))
    parser.add_argument("--proxy-trial-id", default="PR2026-10-D-L125-V2")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_proxy_cost_comparison"))
    args = parser.parse_args()
    configure_logging("ERROR")

    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    hourly = load_hourly_bars(args.hourly_dir)
    daily = market.returns.loc[index]
    pre_fill = pre_fill_returns(
        daily,
        hourly,
        fill_hours=3,
        missing_fill="day_close",
        reference_close=market.raw_price.reindex(index=index, columns=daily.columns),
    )

    rows: list[dict[str, object]] = []
    for cost in args.costs:
        spot = _production_result(
            config,
            market,
            built,
            index,
            cost_bps=float(cost),
            pre_fill=pre_fill.loc[index],
        )
        spot_metrics = _metrics_from_returns(spot.daily_returns)
        proxy_path = (
            args.proxy_root
            / f"derivatives_track_proxy_trials_{cost:g}bps"
            / "proxy_trials.csv"
        )
        proxy = pd.read_csv(proxy_path)
        match = proxy.loc[proxy["trial_id"] == args.proxy_trial_id]
        if len(match) != 1:
            raise ValueError(f"{proxy_path}: expected one {args.proxy_trial_id} row, found {len(match)}")
        derivative = match.iloc[0]
        rows.append(
            {
                "cost_bps": float(cost),
                "derivative_multiple": float(derivative["multiple"]),
                "derivative_sharpe": float(derivative["sharpe"]),
                "derivative_max_drawdown": float(derivative["max_drawdown"]),
                "h5_spot_multiple": float(spot_metrics["multiple"]),
                "h5_spot_sharpe": float(spot_metrics["sharpe"]),
                "h5_spot_max_drawdown": float(spot_metrics["max_drawdown"]),
                "multiple_ratio": float(derivative["multiple"]) / float(spot_metrics["multiple"]),
                "sharpe_ratio": float(derivative["sharpe"]) / float(spot_metrics["sharpe"]),
                "fill": "+3h day_close",
            }
        )
    frame = pd.DataFrame(rows)
    output_dir = ensure_dir(args.output_dir)
    frame.to_csv(output_dir / "cost_comparison.csv", index=False)
    (output_dir / "cost_comparison.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(frame.to_string(index=False))
    print(f"Wrote derivatives cost comparison to {output_dir}")


if __name__ == "__main__":
    main()
