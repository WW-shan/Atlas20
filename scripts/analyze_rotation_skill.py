"""Does the rotation rule actually pick relative winners?

A concentrated rotation book can look great because one coin ran, so the
mechanism has to be tested separately from the P&L.  This script compares the
signal's forward book return with the equal-weight point-in-time Top20 basket
on the same next day, plus a rank-based hit rate: how often the coin the rule
rotates into lands in the best quintile of that basket's forward returns.

Convention: a signal on date t is scored against the return realised on the
next trading date, so nothing here uses information from the day it is
scored on.  No parameters are selected.
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

from scripts.run_derivatives_backtest import _long_targets_from_build  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_phase_momentum_live_signal import _resolve_build  # noqa: E402


def _newey_west_t(values: np.ndarray, lags: int = 5) -> float:
    clean = values[np.isfinite(values)]
    if clean.size < 30:
        return float("nan")
    mean = clean.mean()
    demeaned = clean - mean
    variance = float((demeaned**2).mean())
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1.0)
        covariance = float((demeaned[lag:] * demeaned[:-lag]).mean())
        variance += 2.0 * weight * covariance
    if variance <= 0:
        return float("nan")
    return float(mean / np.sqrt(variance / clean.size))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_rotation_skill_2022"))
    args = parser.parse_args()

    config, market, universe, index = _load_market(
        args.config, start_date=args.start_date, end_date=args.end_date
    )
    _, _, built, _ = _resolve_build(market, universe, index, None)
    targets = _long_targets_from_build(built, index)
    returns = market.returns

    membership: dict[pd.Timestamp, list[str]] = {}
    for date, block in universe.groupby("rebalance_date"):
        membership[pd.Timestamp(date)] = [str(item) for item in block["coin_id"]]

    dates = list(pd.DatetimeIndex(index).sort_values())
    rows: list[dict[str, object]] = []
    for position, signal_date in enumerate(dates[:-1]):
        target = targets.get(signal_date)
        forward_date = dates[position + 1]
        if target is None or target.empty:
            continue
        members = membership.get(forward_date) or membership.get(signal_date)
        if not members:
            continue
        forward = returns.reindex(index=[forward_date], columns=members).iloc[0]
        if forward.isna().all():
            continue
        weights = target.reindex(members).fillna(0.0)
        gross = float(weights.abs().sum())
        if gross <= 0.0:
            continue
        book = float((weights * forward).sum() / gross)
        basket = float(forward.mean())
        leader_asset = str(target.abs().idxmax())
        leader_return = float(forward.get(leader_asset, float("nan")))
        ranked = forward.dropna().sort_values(ascending=False)
        leader_rank = (
            int(ranked.index.get_loc(leader_asset)) + 1 if leader_asset in ranked.index else None
        )
        rows.append(
            {
                "signal_date": signal_date,
                "forward_date": forward_date,
                "gross": gross,
                "book_return": book,
                "basket_return": basket,
                "excess_return": book - basket,
                "leader_asset": leader_asset,
                "leader_return": leader_return,
                "leader_rank_in_basket": leader_rank,
                "basket_size": int(len(ranked)),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise SystemExit("no scored signal days in the requested window")
    frame["year"] = pd.DatetimeIndex(frame["signal_date"]).year
    excess = frame["excess_return"].to_numpy(dtype=float)
    hit = float((excess > 0).mean())
    top_quintile = frame["leader_rank_in_basket"] <= np.ceil(frame["basket_size"] / 5.0)
    summary = {
        "days": int(len(frame)),
        "mean_excess_daily": float(np.nanmean(excess)),
        "median_excess_daily": float(np.nanmedian(excess)),
        "annualised_excess": float(np.nanmean(excess) * 365.0),
        "hit_rate_excess_positive": hit,
        "newey_west_t": _newey_west_t(excess),
        "leader_in_top_quintile_rate": float(top_quintile.mean()),
        "mean_book_return_daily": float(frame["book_return"].mean()),
        "mean_basket_return_daily": float(frame["basket_return"].mean()),
    }
    yearly = (
        frame.groupby("year")
        .agg(
            days=("excess_return", "size"),
            mean_excess_daily=("excess_return", "mean"),
            hit_rate=("excess_return", lambda values: float((values > 0).mean())),
            leader_top_quintile=("leader_rank_in_basket", lambda values: float((values <= 4).mean())),
        )
        .reset_index()
    )
    output_dir = ensure_dir(args.output_dir)
    frame.to_csv(output_dir / "daily_selection_skill.csv", index=False)
    yearly.to_csv(output_dir / "yearly_selection_skill.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# Rotation selection skill",
        "",
        f"- window: {args.start_date} → {args.end_date}, {summary['days']} scored signal days",
        "- convention: signal on date t scored against the point-in-time Top20 basket return on the next trading date",
        "",
        dataframe_to_markdown(pd.DataFrame([summary])),
        "",
        "## By year",
        "",
        dataframe_to_markdown(yearly),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote rotation skill diagnostics to {output_dir}")


if __name__ == "__main__":
    main()
