"""Fast read: does a point-in-time dispersion gate improve the frozen book?

The diagnostic (scripts/diagnose_cross_sectional_dispersion.py) shows the
strategy's forward returns fall sharply in the top cross-sectional-dispersion
quintile.  This script applies the cheapest tradable version of that finding -
go to cash when the dispersion percentile is extreme - to the frozen book's
daily returns and reports the effect.  It is a screening step, not a validated
rule: the exact gate still has to be pre-registered and rerun through the
production engine (which charges the entry/exit turnover this overlay ignores).
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.diagnose_cross_sectional_dispersion import _dispersion, _membership  # noqa: E402
from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402


def _metrics(returns: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").dropna()
    equity = (1.0 + clean).cumprod()
    drawdown = float((equity / equity.cummax() - 1.0).min())
    volatility = float(clean.std(ddof=0) * np.sqrt(365.0))
    return {
        "multiple": float(equity.iloc[-1]),
        "sharpe": float(clean.mean() * 365.0 / volatility) if volatility > 0 else 0.0,
        "max_drawdown": drawdown,
        "annualized_volatility": volatility,
    }


def _percentile(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window // 2).apply(
        lambda values: float((values[:-1] < values[-1]).mean()) if len(values) > 1 else np.nan,
        raw=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--trial-id", default="PR2026-10-H3")
    parser.add_argument("--measure", default="trailing_21d")
    parser.add_argument("--lookback", type=int, default=252)
    parser.add_argument("--thresholds", default="0.60,0.70,0.80,0.90")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_dispersion_overlay"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    config, market, universe, index = _load_market(
        args.config, start_date=args.start_date, end_date=args.end_date
    )
    trial = trial_by_id(args.trial_id)
    built = build_trial(trial, market, universe, index)
    returns = _production_result(config, market, built, index, cost_bps=args.cost_bps).daily_returns
    members = _membership(universe, index)
    dispersion = _dispersion(market.price, index, members, kind=args.measure)
    percentile = _percentile(dispersion, args.lookback)

    rows = [{"rule": "none", **{k: float(v) for k, v in _metrics(returns).items()}, "days_in_market": int((returns != 0).sum())}]
    for threshold in [float(t) for t in args.thresholds.split(",")]:
        # Known at D's close, so it gates D+1's return.
        gate = (percentile < threshold).astype(float)
        gated = returns * gate.shift(1)
        row = {
            "rule": f"cash when dispersion_pct >= {threshold:.2f}",
            **{k: float(v) for k, v in _metrics(gated).items()},
            "days_in_market": int((gate.shift(1).fillna(0.0) != 0).sum()),
        }
        rows.append(row)

    table = pd.DataFrame(rows)
    output_dir = ensure_dir(args.output_dir)
    table.to_csv(output_dir / "overlay_summary.csv", index=False)
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": args.cost_bps,
        "trial_id": args.trial_id,
        "measure": args.measure,
        "lookback": args.lookback,
        "thresholds": [float(t) for t in args.thresholds.split(",")],
        "note": (
            "Screening only: the gate zeroes the book's return on risk-off days and does not "
            "charge the extra entry/exit turnover. The production-engine version must be "
            "pre-registered before it is treated as a candidate."
        ),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                "# Dispersion overlay screening",
                "",
                f"Book `{args.trial_id}` at {args.cost_bps:g} bps, {args.start_date} .. {args.end_date}. "
                f"Dispersion = {args.measure} cross-sectional std of the point-in-time Top20; "
                f"percentile over {args.lookback} days; cash when the percentile is at/above the threshold.",
                "",
                dataframe_to_markdown(table),
                "",
                "Screening only - turnover is not charged here.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(table.to_string(index=False))
    print(f"Wrote dispersion overlay screening to {output_dir}")


if __name__ == "__main__":
    main()
