"""How many coins does the phase-momentum champion actually hold?

The specification is described as "12 one-coin sleeves", which reads as twelve
independent bets. This tool measures the *book* those sleeves add up to: the
distinct-coin count per day and the largest single-coin share of it.

It matters because AGENTS.md forbids a result that depends on one asset, and
because it decides whether the project's remaining lever is diversification
(lower return, lower risk) or concentration (the reverse). It is a measurement
tool: the specification, universe, costs and fills are the frozen champion's.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from scripts.run_phase_momentum import _production_result  # noqa: E402
from scripts.run_phase_momentum_hypotheses import (  # noqa: E402
    BASELINE_ID,
    MAIN_WINDOW,
    _load_market,
    build_trial,
    trial_by_id,
)


def book_concentration(weights: pd.DataFrame) -> pd.DataFrame:
    """Per day: gross exposure, distinct coins, largest coin's share of the book."""
    gross = weights.sum(axis=1)
    held = weights.gt(0.0)
    largest = weights.max(axis=1)
    frame = pd.DataFrame(
        {
            "gross_exposure": gross,
            "distinct_coins": held.sum(axis=1),
            "largest_weight": largest,
        }
    )
    frame["largest_share"] = frame["largest_weight"] / frame["gross_exposure"].replace(0.0, pd.NA)
    frame["hhi"] = ((weights.div(frame["gross_exposure"], axis=0).fillna(0.0)) ** 2).sum(axis=1)
    return frame


def summarise(frame: pd.DataFrame) -> dict[str, float]:
    """Headline numbers over the days the book was actually invested."""
    invested = frame[frame["gross_exposure"] > 0.0]
    if invested.empty:
        return {}
    return {
        "days": float(len(frame)),
        "invested_days": float(len(invested)),
        "avg_gross_exposure": float(frame["gross_exposure"].mean()),
        "avg_distinct_coins_invested": float(invested["distinct_coins"].mean()),
        "median_largest_share": float(invested["largest_share"].median()),
        "p75_largest_share": float(invested["largest_share"].quantile(0.75)),
        "share_days_top_coin_over_50pct": float((invested["largest_share"] >= 0.50).mean()),
        "share_days_top_coin_over_75pct": float((invested["largest_share"] >= 0.75).mean()),
        "share_days_single_coin": float((invested["distinct_coins"] == 1).mean()),
        "avg_book_hhi": float(invested["hhi"].mean()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--trial-id", default=BASELINE_ID)
    parser.add_argument("--output-dir", default="reports/phase_momentum_book_concentration")
    args = parser.parse_args()

    config, market, universe, index = _load_market(
        args.config, start_date=MAIN_WINDOW[0], end_date=MAIN_WINDOW[1]
    )
    configure_logging("ERROR")
    built = build_trial(trial_by_id(args.trial_id), market, universe, index)
    result = _production_result(config, market, built, index, cost_bps=args.cost_bps)

    frame = book_concentration(result.weights)
    summary = summarise(frame)
    output_dir = ensure_dir(Path(args.output_dir))
    frame.to_csv(output_dir / "daily_book.csv", index_label="date")

    lines = [
        "# Phase-momentum champion: how many coins is the book?",
        "",
        f"- Spec: `{args.trial_id}`, costs {args.cost_bps:g} bps, close fill, "
        f"{MAIN_WINDOW[0]} .. {MAIN_WINDOW[1]}.",
        "- `largest_share` is the biggest single coin's share of the invested book,",
        "  so 1.0 means the whole book is one coin.",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| days evaluated | {summary['days']:.0f} |",
        f"| days invested | {summary['invested_days']:.0f} |",
        f"| average gross exposure (all days) | {summary['avg_gross_exposure']:.1%} |",
        f"| **average distinct coins while invested** | **{summary['avg_distinct_coins_invested']:.2f}** |",
        f"| median largest-coin share of the book | {summary['median_largest_share']:.1%} |",
        f"| 75th percentile largest-coin share | {summary['p75_largest_share']:.1%} |",
        f"| invested days with the top coin >= 50% of the book | {summary['share_days_top_coin_over_50pct']:.1%} |",
        f"| invested days with the top coin >= 75% of the book | {summary['share_days_top_coin_over_75pct']:.1%} |",
        f"| invested days holding exactly one coin | {summary['share_days_single_coin']:.1%} |",
        f"| average book HHI | {summary['avg_book_hhi']:.3f} |",
        "",
        "Distinct-coin count while invested:",
        "",
        "| coins held | days |",
        "| ---: | ---: |",
    ]
    counts = frame.loc[frame["gross_exposure"] > 0.0, "distinct_coins"].value_counts().sort_index()
    lines += [f"| {int(coins)} | {int(days)} |" for coins, days in counts.items()]
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
