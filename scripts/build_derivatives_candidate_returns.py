"""Build a strict common-sample return matrix for derivatives diagnostics.

Each input is a CSV with a date index in the first column and one or more
candidate return columns.  The files must cover exactly the same dates: a
missing day is a hard error rather than a silent inner join, because a
different sample can change Sharpe, drawdown, and multiple-testing results.
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

from atlas20.logging_utils import ensure_dir


def _load_returns(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"{path}: no return rows")
    date_column = frame.columns[0]
    dates = pd.to_datetime(frame.pop(date_column), utc=True, errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{path}: {int(dates.isna().sum())} row(s) have no parseable date")
    if dates.duplicated().any():
        duplicates = dates.loc[dates.duplicated()].dt.strftime("%Y-%m-%d").unique()
        raise ValueError(f"{path}: duplicate date(s) {list(duplicates[:5])}")
    returns = frame.set_axis(pd.DatetimeIndex(dates, name="date"), axis=0).sort_index()
    returns = returns.apply(pd.to_numeric, errors="coerce")
    if returns.columns.has_duplicates:
        duplicates = returns.columns[returns.columns.duplicated()].tolist()
        raise ValueError(f"{path}: duplicate candidate column(s) {duplicates}")
    if any(name == "" for name in returns.columns):
        raise ValueError(f"{path}: candidate column names must be non-empty")
    if returns.isna().any().any():
        missing = returns.isna().sum()
        raise ValueError(f"{path}: non-finite values in {missing[missing > 0].to_dict()}")
    return returns


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, action="append", required=True, help="daily-return CSV; repeatable")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    frames = [_load_returns(path) for path in args.input]
    reference = frames[0].index
    for path, frame in zip(args.input[1:], frames[1:], strict=True):
        if not frame.index.equals(reference):
            missing = reference.difference(frame.index)
            extra = frame.index.difference(reference)
            raise ValueError(
                f"{path}: return dates differ from {args.input[0]}; "
                f"missing={len(missing)} extra={len(extra)}"
            )

    combined = pd.concat(frames, axis=1)
    if combined.columns.has_duplicates:
        duplicates = combined.columns[combined.columns.duplicated()].tolist()
        raise ValueError(f"candidate columns overlap across inputs: {duplicates}")
    combined = combined.sort_index()
    output_dir = ensure_dir(args.output.parent)
    combined.to_csv(args.output, index_label="date")
    manifest = {
        "inputs": [str(path) for path in args.input],
        "candidates": combined.columns.tolist(),
        "rows": int(len(combined)),
        "start": combined.index.min().isoformat(),
        "end": combined.index.max().isoformat(),
    }
    (output_dir / f"{args.output.stem}.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
