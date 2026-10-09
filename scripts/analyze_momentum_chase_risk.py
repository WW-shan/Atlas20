"""Does the frozen spec buy coins that have already run, and what happens next?

The live target on 2026-10-07 is a single coin, NEAR, which was up about 180%
in the five weeks before the book rotated into it.  That raises a question the
specification's own rules cannot answer: is entering after an extreme run a
good or a bad spot, historically?

This tool measures it on the frozen specification's own book.  For every day
the book is invested it records the largest holding's trailing 21-day return
(the move the momentum sleeves were chasing) and the strategy's forward 5, 10
and 21-day return, then buckets the days by that trailing return.  It is
hypothesis generation: no rule changes, no new trial.  The externally
documented prior is the MAX effect - extreme recent gains predict lower
subsequent returns (Bali, Cakici and Whitelaw, 2011, in equities; Li and
Urquhart, 2021, in crypto, where the review already lists it as S6).

Usage::

    .venv/bin/python scripts/analyze_momentum_chase_risk.py \
        --output-dir reports/phase_momentum_chase_risk
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

DEFAULT_TRIAL = "PR2026-10-H5"
HORIZONS = (5, 10, 21)
TRAILING_WINDOW = 21
BUCKETS = 5


def forward_frame(daily: pd.Series, horizons=HORIZONS) -> pd.DataFrame:
    """Forward cumulative return and worst drawdown over each horizon."""
    clean = pd.to_numeric(daily, errors="coerce").fillna(0.0)
    frame = pd.DataFrame(index=clean.index)
    for horizon in horizons:
        frame[f"forward_{horizon}d"] = (
            (1.0 + clean).rolling(horizon).apply(np.prod, raw=True).shift(-horizon) - 1.0
        )
    worst = []
    for position in range(len(clean)):
        window = clean.iloc[position + 1 : position + 1 + max(horizons)]
        if window.empty:
            worst.append(np.nan)
            continue
        path = (1.0 + window).cumprod()
        worst.append(float((path / path.cummax() - 1.0).min()))
    frame[f"forward_{max(horizons)}d_mdd"] = worst
    return frame


def daily_frame(
    market,
    weights: pd.DataFrame,
    daily: pd.Series,
    *,
    trailing_window: int = TRAILING_WINDOW,
) -> pd.DataFrame:
    """Largest holding, the run it was bought after, and what followed."""
    trailing = market.price / market.price.shift(trailing_window) - 1.0
    max_daily = market.returns.rolling(trailing_window, min_periods=trailing_window).max()
    invested = weights.sum(axis=1) > 0.0
    # Only invested rows have a largest holding; a fully-cash row is dropped
    # before idxmax so it cannot raise on an all-NaN slice.
    held = weights.loc[invested]
    largest = held.where(held.gt(0.0)).idxmax(axis=1)
    trailing_return = pd.Series(
        [trailing.loc[date, coin] if coin in trailing.columns else np.nan for date, coin in largest.items()],
        index=largest.index,
    )
    # The MAX construct of Bali, Cakici and Whitelaw (2011) and Li and Urquhart
    # et al. (2021): the largest single-day return the held coin just printed.
    max_daily_return = pd.Series(
        [max_daily.loc[date, coin] if coin in max_daily.columns else np.nan for date, coin in largest.items()],
        index=largest.index,
    )
    frame = pd.DataFrame(
        {
            "gross": held.sum(axis=1),
            "largest_coin": largest,
            "largest_weight": held.max(axis=1),
            "largest_trailing_21d": trailing_return,
            "largest_max_daily_21d": max_daily_return,
        }
    )
    frame = frame.join(forward_frame(daily).reindex(frame.index))
    # Average gross exposure over the same forward window, so the returns can be
    # read per unit of risk actually taken (the volatility target already cuts
    # exposure after a large run, which would otherwise explain the gap away).
    gross_daily = weights.sum(axis=1)
    frame["forward_gross"] = (
        gross_daily.rolling(max(HORIZONS)).mean().shift(-max(HORIZONS)).reindex(frame.index)
    )
    return frame


def bucket_table(
    frame: pd.DataFrame, *, buckets: int = BUCKETS, state: str = "largest_trailing_21d"
) -> pd.DataFrame:
    data = frame.dropna(subset=[state]).copy()
    data["bucket"] = pd.qcut(data[state], buckets, labels=False, duplicates="drop")
    rows = []
    for bucket, group in data.groupby("bucket"):
        row = {
            "bucket": int(bucket) + 1,
            "days": int(len(group)),
            "state_min": float(group[state].min()),
            "state_max": float(group[state].max()),
            "state_median": float(group[state].median()),
        }
        for horizon in HORIZONS:
            column = f"forward_{horizon}d"
            row[f"mean_{column}"] = float(group[column].mean())
            row[f"median_{column}"] = float(group[column].median())
            row[f"hit_{column}"] = float((group[column] > 0.0).mean())
        row[f"worst_{max(HORIZONS)}d_mdd"] = float(group[f"forward_{max(HORIZONS)}d_mdd"].min())
        rows.append(row)
    return pd.DataFrame(rows)


def extreme_vs_rest(
    frame: pd.DataFrame, *, quantile: float = 0.8, state: str = "largest_trailing_21d"
) -> tuple[pd.DataFrame, float]:
    """Forward returns after a top-quintile reading against everything else."""
    data = frame.dropna(subset=[state])
    threshold = float(data[state].quantile(quantile))
    extreme = data[data[state] >= threshold]
    rest = data[data[state] < threshold]
    rows = []
    for horizon in HORIZONS:
        column = f"forward_{horizon}d"
        left = extreme[column].dropna()
        right = rest[column].dropna()
        standard_error = float(
            np.sqrt(left.var(ddof=1) / len(left) + right.var(ddof=1) / len(right))
        )
        row = {
            "horizon_days": horizon,
            "extreme_days": int(len(left)),
            "rest_days": int(len(right)),
            "extreme_mean": float(left.mean()),
            "rest_mean": float(right.mean()),
            "difference": float(left.mean() - right.mean()),
            "welch_t": float((left.mean() - right.mean()) / standard_error)
            if standard_error
            else float("nan"),
            "extreme_hit_rate": float((left > 0.0).mean()),
            "rest_hit_rate": float((right > 0.0).mean()),
        }
        # Same comparison per unit of gross exposure, over days that were
        # actually invested in the forward window.
        invested_forward = data[data["forward_gross"] > 0.10]
        extreme_per = invested_forward[invested_forward[state] >= threshold]
        rest_per = invested_forward[invested_forward[state] < threshold]
        per_gross = lambda group: (group[column] / group["forward_gross"]).dropna()  # noqa: E731
        left_per, right_per = per_gross(extreme_per), per_gross(rest_per)
        per_error = float(
            np.sqrt(left_per.var(ddof=1) / len(left_per) + right_per.var(ddof=1) / len(right_per))
        )
        row["extreme_per_gross"] = float(left_per.mean())
        row["rest_per_gross"] = float(right_per.mean())
        row["difference_per_gross"] = float(left_per.mean() - right_per.mean())
        row["welch_t_per_gross"] = (
            float((left_per.mean() - right_per.mean()) / per_error) if per_error else float("nan")
        )
        rows.append(row)
    return pd.DataFrame(rows), threshold


def _report(
    frame: pd.DataFrame,
    buckets: pd.DataFrame,
    extreme: pd.DataFrame,
    max_buckets: pd.DataFrame,
    max_extreme: pd.DataFrame,
    threshold: float,
    max_threshold: float,
    *,
    trial_id: str,
    current: pd.Series,
    percentile: float,
    max_percentile: float,
) -> str:
    top = buckets.iloc[-1]
    bottom = buckets.iloc[0]
    lines = [
        f"# Does {trial_id} buy after extreme runs, and what follows?",
        "",
        "Hypothesis generation only: no rule changed, no trial registered.",
        f"Invested days: {len(frame)}; trailing window: {TRAILING_WINDOW} days; buckets: {BUCKETS}.",
        "",
        "`largest_trailing_21d` is the 21-day return of the largest holding on that day - the move",
        "the momentum sleeves were chasing. Forward columns are the strategy's own subsequent",
        "returns, so this measures the book's timing, not the coin's.",
        "",
        "## Current position",
        "",
        f"Latest invested day: **{frame.index[-1].date()}**, largest holding "
        f"`{current['largest_coin']}` at {current['largest_weight']:.3f} of capital, "
        f"gross {current['gross']:.3f}.",
        f"Its trailing 21-day return was {current['largest_trailing_21d']:+.1%}, in the "
        f"**{percentile:.0%} percentile** of every invested day in the sample; its largest "
        f"single-day return over that window was {current['largest_max_daily_21d']:+.1%} "
        f"({max_percentile:.0%} percentile).",
        "",
        "## Forward strategy returns by the run the book was chasing",
        "",
        dataframe_to_markdown(buckets),
        "",
        "## Top-quintile run against everything else",
        "",
        f"The most chased quintile starts at a trailing 21-day return of {threshold:+.0%}.",
        "",
        dataframe_to_markdown(extreme),
        "",
        "## The same test with the MAX construct of the external literature",
        "",
        "The crypto MAX-momentum result (Li and Urquhart et al., 2021, already source S6 of this",
        "review) is the opposite of the equity MAX effect: coins with the largest single-day",
        "return earn *higher* future returns. Here the same forward returns are bucketed by the",
        f"largest single-day return of the largest holding over the past {TRAILING_WINDOW} days.",
        f"The top quintile starts at {max_threshold:+.1%}.",
        "",
        dataframe_to_markdown(max_buckets),
        "",
        "Top quintile against the rest:",
        "",
        dataframe_to_markdown(max_extreme),
        "",
        "## Reading",
        "",
        f"The most chased bucket (bucket {int(top['bucket'])}) covers trailing 21-day returns of "
        f"{top['state_min']:+.0%} to {top['state_max']:+.0%}; the least chased covers "
        f"{bottom['state_min']:+.0%} to {bottom['state_max']:+.0%}.",
        "",
        "Any difference here is in-sample and conditional on the strategy having chosen to hold",
        "the coin at all. It is recorded to document what the specification's own timing looks",
        "like after a large run; it is not a rule, and changing the entry rule would be a new",
        "pre-registered trial.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", default=DEFAULT_TRIAL)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-10-07")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--trailing-window", type=int, default=TRAILING_WINDOW)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_chase_risk"))
    args = parser.parse_args()
    configure_logging("ERROR")

    _config, market, universe, index = _load_market(
        args.config, start_date=args.start_date, end_date=args.end_date
    )
    built = build_trial(trial_by_id(args.trial_id), market, universe, index)
    result = _production_result(_config, market, built, index, cost_bps=args.cost_bps)

    frame = daily_frame(market, result.weights, result.daily_returns, trailing_window=args.trailing_window)
    buckets = bucket_table(frame)
    extreme, threshold = extreme_vs_rest(frame)
    max_buckets = bucket_table(frame, state="largest_max_daily_21d")
    max_extreme, max_threshold = extreme_vs_rest(frame, state="largest_max_daily_21d")
    current = frame.iloc[-1]
    percentile = float((frame["largest_trailing_21d"] < current["largest_trailing_21d"]).mean())
    max_percentile = float(
        (frame["largest_max_daily_21d"] < current["largest_max_daily_21d"]).mean()
    )

    output_dir = ensure_dir(args.output_dir)
    frame.to_csv(output_dir / "daily_chase.csv", index_label="date")
    buckets.to_csv(output_dir / "chase_buckets.csv", index=False)
    extreme.to_csv(output_dir / "chase_extreme_vs_rest.csv", index=False)
    max_buckets.to_csv(output_dir / "max_daily_buckets.csv", index=False)
    max_extreme.to_csv(output_dir / "max_daily_extreme_vs_rest.csv", index=False)
    (output_dir / "report.md").write_text(
        _report(
            frame,
            buckets,
            extreme,
            max_buckets,
            max_extreme,
            threshold,
            max_threshold,
            trial_id=args.trial_id,
            current=current,
            percentile=percentile,
            max_percentile=max_percentile,
        ),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "script": "scripts/analyze_momentum_chase_risk.py",
                "trial_id": args.trial_id,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "cost_bps": args.cost_bps,
                "trailing_window": args.trailing_window,
                "invested_days": int(len(frame)),
                "extreme_threshold": threshold,
                "current_coin": str(current["largest_coin"]),
                "current_trailing_21d": float(current["largest_trailing_21d"]),
                "current_percentile": percentile,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(buckets[["bucket", "days", "state_median", "mean_forward_5d", "mean_forward_21d", "hit_forward_21d", "worst_21d_mdd"]].round(4).to_string(index=False))
    print()
    print(max_buckets[["bucket", "days", "state_median", "mean_forward_21d", "hit_forward_21d"]].round(4).to_string(index=False))
    print(f"current: {current['largest_coin']} trailing {current['largest_trailing_21d']:+.1%} (p{percentile*100:.0f})")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
