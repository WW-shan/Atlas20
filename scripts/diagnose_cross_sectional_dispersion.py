"""Does cross-sectional dispersion predict this strategy's forward returns?

External evidence (Makgolo and Zhang, 2026, SSRN 6648082) finds that the
cross-sectional dispersion of crypto returns predicts momentum breakdowns
better than BTC volatility, and that scaling exposure by dispersion cut a
cross-sectional crypto momentum book's max drawdown from -42.5% to -17.1%.
This script tests the *mechanism* on the project's own frozen Top20 book before
any rule is proposed: it buckets the strategy's forward returns by the
dispersion regime and reports the spread.  It changes no rule and selects
nothing.
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

from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402

HORIZONS = (1, 5, 21)
DEFAULT_MEASURES = ("trailing_21d", "trailing_7d", "daily")


def _membership(universe: pd.DataFrame, index: pd.DatetimeIndex) -> dict[pd.Timestamp, list[str]]:
    by_date = {
        pd.Timestamp(date): group["coin_id"].astype(str).tolist()
        for date, group in universe.groupby("rebalance_date")
    }
    return {pd.Timestamp(date): by_date.get(pd.Timestamp(date), []) for date in index}


def _dispersion(
    price: pd.DataFrame,
    index: pd.DatetimeIndex,
    members: dict[pd.Timestamp, list[str]],
    *,
    kind: str,
) -> pd.Series:
    """Cross-sectional dispersion of the point-in-time Top20 each day."""
    if kind == "daily":
        panel = price.pct_change()
    else:
        window = int(kind.split("_")[1].removesuffix("d"))
        panel = price / price.shift(window) - 1.0
    values: dict[pd.Timestamp, float] = {}
    for date in index:
        coin_ids = members.get(pd.Timestamp(date), [])
        if not coin_ids:
            values[pd.Timestamp(date)] = float("nan")
            continue
        row = pd.to_numeric(panel.loc[date, coin_ids], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
        row = row.dropna()
        values[pd.Timestamp(date)] = float(row.std(ddof=1)) if len(row) >= 5 else float("nan")
    return pd.Series(values, dtype=float).sort_index()


def _forward(returns: pd.Series, horizon: int) -> pd.Series:
    """Strategy forward return from D to D+horizon (the T+1 book's move)."""
    future = returns.shift(-1)
    log1p = np.log1p(future.clip(lower=-0.999999))
    return np.expm1(log1p.rolling(horizon).sum().shift(-(horizon - 1)))


def _bucket_table(
    dispersion: pd.Series,
    forward: pd.Series,
    *,
    quantiles: int,
) -> pd.DataFrame:
    frame = pd.DataFrame({"dispersion": dispersion, "forward": forward}).dropna()
    if frame.empty:
        return pd.DataFrame()
    frame["bucket"] = pd.qcut(frame["dispersion"], quantiles, labels=False, duplicates="drop")
    grouped = frame.groupby("bucket")
    rows = []
    for bucket, group in grouped:
        rows.append(
            {
                "bucket": int(bucket),
                "days": int(len(group)),
                "dispersion_median": float(group["dispersion"].median()),
                "forward_mean": float(group["forward"].mean()),
                "forward_median": float(group["forward"].median()),
                "positive_share": float((group["forward"] > 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--trial-id", default="PR2026-10-H3")
    parser.add_argument("--quantiles", type=int, default=5)
    parser.add_argument("--measures", default=",".join(DEFAULT_MEASURES))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_dispersion_diagnostic"),
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

    measures = [m.strip() for m in args.measures.split(",") if m.strip()]
    rows: list[dict[str, object]] = []
    tables: dict[str, pd.DataFrame] = {}
    for measure in measures:
        dispersion = _dispersion(market.price, index, members, kind=measure)
        for horizon in HORIZONS:
            forward = _forward(returns, horizon)
            frame = pd.DataFrame({"dispersion": dispersion, "forward": forward}).dropna()
            if len(frame) < 50:
                continue
            # Spearman = Pearson on ranks; scipy is not a project dependency.
            corr = float(frame["dispersion"].rank().corr(frame["forward"].rank()))
            table = _bucket_table(dispersion, forward, quantiles=args.quantiles)
            tables[f"{measure}_h{horizon}"] = table
            if not table.empty:
                top = table.iloc[-1]
                rest = table.iloc[:-1]
                rest_mean = float(
                    np.average(rest["forward_mean"], weights=rest["days"])
                ) if not rest.empty else float("nan")
                rows.append(
                    {
                        "measure": measure,
                        "horizon_days": horizon,
                        "days": int(len(frame)),
                        "spearman_corr": corr,
                        "top_bucket_forward_mean": float(top["forward_mean"]),
                        "rest_forward_mean": rest_mean,
                        "top_minus_rest": float(top["forward_mean"]) - rest_mean,
                        "top_bucket_positive_share": float(top["positive_share"]),
                    }
                )

    output_dir = ensure_dir(args.output_dir)
    summary = pd.DataFrame(rows)
    summary.to_csv(output_dir / "dispersion_summary.csv", index=False)
    for name, table in tables.items():
        table.to_csv(output_dir / f"buckets_{name}.csv", index=False)
    manifest = {
        "config": args.config,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "cost_bps": args.cost_bps,
        "trial_id": args.trial_id,
        "quantiles": args.quantiles,
        "measures": measures,
        "horizons": list(HORIZONS),
        "interpretation": (
            "Diagnostic only: forward returns of the frozen book bucketed by cross-sectional "
            "dispersion. A negative top-minus-rest spread supports the external momentum-breakdown "
            "mechanism; it does not by itself justify a rule change."
        ),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = [
        "# Cross-sectional dispersion diagnostic",
        "",
        f"Book: `{args.trial_id}` at {args.cost_bps:g} bps. Sample: "
        f"{args.start_date} .. {args.end_date}.",
        "",
        "`top_minus_rest` is the mean forward return of the top dispersion bucket minus "
        "the day-weighted mean of the rest. The external mechanism predicts it is negative.",
        "",
        dataframe_to_markdown(summary),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Wrote dispersion diagnostic to {output_dir}")


if __name__ == "__main__":
    main()
