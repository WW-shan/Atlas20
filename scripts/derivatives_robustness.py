"""Calendar and rolling robustness supplements for the derivatives track.

The derivatives track is judged on the same frozen window as the spot track,
so it needs the same calendar evidence: a yearly breakdown, best-year
removal, and the one-year rolling worst case for every candidate in the
Bitget mark return matrix.  Nothing here re-runs a backtest or touches a
parameter; it only re-slices the recorded daily returns.
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

from atlas20.logging_utils import ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_phase_momentum import _rolling_worst, _yearly_returns  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402


def _load_returns(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"{path}: no return rows")
    date_column = frame.columns[0]
    dates = pd.to_datetime(frame.pop(date_column), utc=True, errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{path}: unparseable date value")
    values = frame.set_axis(pd.DatetimeIndex(dates, name="date"), axis=0).sort_index()
    values = values.apply(pd.to_numeric, errors="coerce")
    if values.isna().any().any():
        raise ValueError(f"{path}: non-finite candidate returns")
    return values


def _yearly_table(returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for candidate in returns.columns:
        yearly = _yearly_returns(returns[candidate])
        for stamp, value in yearly.items():
            rows.append(
                {
                    "candidate": candidate,
                    "year": int(stamp.year),
                    "return": float(value),
                }
            )
    return pd.DataFrame(rows)


def _best_year_removal(returns: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for candidate in returns.columns:
        series = returns[candidate]
        for year in sorted(set(series.index.year)):
            remaining = series[series.index.year != year]
            rows.append(
                {
                    "candidate": candidate,
                    "removed_year": int(year),
                    "days": int(len(remaining)),
                    **_metrics_from_returns(remaining),
                }
            )
    return pd.DataFrame(rows)


def _rolling_table(returns: pd.DataFrame, window_days: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for candidate in returns.columns:
        series = returns[candidate]
        clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if len(clean) < window_days:
            worst_start = None
            worst = float("nan")
        else:
            multiples = (1.0 + clean).rolling(window_days).apply(np.prod, raw=True).dropna()
            worst = float(multiples.min())
            worst_start = multiples.idxmin() - pd.Timedelta(days=window_days - 1)
            worst_start = str(worst_start.date())
        rows.append(
            {
                "candidate": candidate,
                "window_days": window_days,
                "worst_start": worst_start,
                **_rolling_worst(series, window_days=window_days),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--returns", type=Path, required=True, help="candidate daily-return matrix")
    parser.add_argument("--window-days", type=int, default=365)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    returns = _load_returns(args.returns)
    yearly = _yearly_table(returns)
    best_year = _best_year_removal(returns)
    rolling = _rolling_table(returns, args.window_days)

    output_dir = ensure_dir(args.output_dir)
    returns.to_csv(output_dir / "candidate_returns.csv")
    yearly.to_csv(output_dir / "yearly_returns.csv", index=False)
    best_year.to_csv(output_dir / "best_year_removal.csv", index=False)
    rolling.to_csv(output_dir / "rolling_worst.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "candidates": list(returns.columns),
                "start": str(returns.index.min()),
                "end": str(returns.index.max()),
                "rows": int(len(returns)),
                "window_days": args.window_days,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    worst_year = yearly.groupby("candidate")["return"].min().rename("worst_year_return")
    lines = [
        "# Derivatives Track Calendar Robustness",
        "",
        f"- sample: {returns.index.min()} → {returns.index.max()} ({len(returns)} daily returns)",
        f"- candidates: {len(returns.columns)}",
        "",
        "## Yearly returns",
        "",
        dataframe_to_markdown(yearly.pivot(index="year", columns="candidate", values="return")),
        "",
        "## Worst single year per candidate",
        "",
        dataframe_to_markdown(worst_year.reset_index()),
        "",
        "## Best-year removal (terminal multiple after deleting each calendar year)",
        "",
        dataframe_to_markdown(best_year[["candidate", "removed_year", "days", "multiple", "sharpe"]]),
        "",
        f"## {args.window_days}-day rolling worst case",
        "",
        dataframe_to_markdown(rolling),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote derivatives robustness diagnostics to {output_dir}")


if __name__ == "__main__":
    main()
