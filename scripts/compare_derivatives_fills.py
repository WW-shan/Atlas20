"""Compare mark-price and market (last) price fills for the frozen book.

The mark candle is the settlement and liquidation reference, but a taker
order fills at the traded price.  This script lines up two already-recorded
runs of the same frozen specification - one filled at the mark open, one at
the Bitget market open - so the execution-price assumption can be judged on
evidence rather than assumed to be identical.
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

from atlas20.logging_utils import ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402


def _load(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"leverage", "scenario", "multiple", "sharpe", "max_drawdown"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mark-matrix", type=Path, required=True)
    parser.add_argument("--market-matrix", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    mark = _load(args.mark_matrix)
    market = _load(args.market_matrix)
    key = ["scenario", "leverage"]
    merged = mark.merge(market, on=key, suffixes=("_mark", "_market"))
    if merged.empty:
        raise SystemExit("the two matrices share no scenario/leverage rows")

    merged["multiple_ratio"] = merged["multiple_market"] / merged["multiple_mark"]
    merged["sharpe_delta"] = merged["sharpe_market"] - merged["sharpe_mark"]
    merged["mdd_delta"] = merged["max_drawdown_market"] - merged["max_drawdown_mark"]
    table = merged[
        [
            "scenario",
            "leverage",
            "multiple_mark",
            "multiple_market",
            "multiple_ratio",
            "sharpe_mark",
            "sharpe_market",
            "sharpe_delta",
            "max_drawdown_mark",
            "max_drawdown_market",
            "mdd_delta",
        ]
    ].sort_values(key)

    output_dir = ensure_dir(args.output_dir)
    table.to_csv(output_dir / "fill_price_comparison.csv", index=False)
    worst_ratio = float(table["multiple_ratio"].min())
    summary = {
        "rows": int(len(table)),
        "worst_multiple_ratio": worst_ratio,
        "median_multiple_ratio": float(table["multiple_ratio"].median()),
        "max_drawdown_worse_by": float(-table["mdd_delta"].max()),
        "verdict": (
            "market fills keep the conclusion"
            if worst_ratio >= 0.80
            else "market fills change the conclusion materially"
        ),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# Execution-price sensitivity: mark vs market fills",
        "",
        f"- mark matrix: `{args.mark_matrix}`",
        f"- market matrix: `{args.market_matrix}`",
        f"- worst market/mark terminal-multiple ratio: **{worst_ratio:.3f}**",
        f"- median ratio: {summary['median_multiple_ratio']:.3f}",
        f"- max-drawdown deterioration (worst row): {summary['max_drawdown_worse_by']:.2%}",
        "",
        dataframe_to_markdown(table),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote fill-price comparison to {output_dir}")


if __name__ == "__main__":
    main()
