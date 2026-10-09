"""Calibrate the Binance funding proxy against Bitget's own funding history.

Bitget's public funding endpoint only reaches back about 90 days, so the
2022+ funding cost has to come from a proxy.  This script measures how far
off that proxy is on the window where both sources exist, which turns the
proxy from "unknown bias" into a measured multiple that the stress band can
be anchored to.
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


def _bitget_series(path: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or "funding_time" not in frame.columns:
        return None
    index = pd.to_datetime(frame["funding_time"], utc=True, errors="coerce")
    values = pd.to_numeric(frame["funding_rate"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index).dropna()
    return series[(series.index >= start) & (series.index < end)].sort_index()


def _binance_series(path: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or not {"calc_time", "last_funding_rate"}.issubset(frame.columns):
        return None
    index = pd.to_datetime(pd.to_numeric(frame["calc_time"], errors="coerce"), unit="ms", utc=True)
    values = pd.to_numeric(frame["last_funding_rate"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index).dropna()
    return series[(series.index >= start) & (series.index < end)].sort_index()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--symbol-map", type=Path, default=Path("data/raw/bitget_derivatives/symbol_map.csv"))
    parser.add_argument(
        "--bitget-funding-dir",
        type=Path,
        default=Path("data/raw/bitget_derivatives/funding_recent_20261009/funding"),
    )
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--start", default="2026-07-11")
    parser.add_argument("--end", default="2026-10-10")
    parser.add_argument("--min-rows", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_funding_calibration"))
    args = parser.parse_args()

    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    symbol_map = pd.read_csv(args.symbol_map)
    rows: list[dict[str, object]] = []
    for record in symbol_map.to_dict("records"):
        coin = str(record["coin_id"])
        bitget = _bitget_series(args.bitget_funding_dir / f"{coin}.csv", start, end)
        binance = _binance_series(args.binance_funding_dir / f"{coin}.csv", start, end)
        if bitget is None or binance is None:
            continue
        if len(bitget) < args.min_rows or len(binance) < args.min_rows:
            continue
        binance_sum = float(binance.sum())
        rows.append(
            {
                "coin_id": coin,
                "bitget_settlements": int(len(bitget)),
                "binance_settlements": int(len(binance)),
                "bitget_mean_rate": float(bitget.mean()),
                "binance_mean_rate": float(binance.mean()),
                "mean_rate_ratio": float(bitget.mean() / binance.mean()) if binance.mean() else float("nan"),
                "bitget_sum_rate": float(bitget.sum()),
                "binance_sum_rate": binance_sum,
                "sum_ratio": float(bitget.sum() / binance_sum) if binance_sum else float("nan"),
            }
        )

    if not rows:
        raise SystemExit("no overlapping Bitget/Binance funding observations found")
    table = pd.DataFrame(rows).sort_values("sum_ratio")
    output_dir = ensure_dir(args.output_dir)
    table.to_csv(output_dir / "funding_calibration.csv", index=False)
    summary = {
        "start": str(start),
        "end": str(end),
        "assets": int(len(table)),
        "median_sum_ratio": float(table["sum_ratio"].median()),
        "mean_sum_ratio": float(table["sum_ratio"].mean()),
        "median_mean_rate_ratio": float(table["mean_rate_ratio"].median()),
        "bitget_median_settlements": int(table["bitget_settlements"].median()),
        "binance_median_settlements": int(table["binance_settlements"].median()),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# Bitget vs Binance funding calibration",
        "",
        f"- window: {start.date()} → {end.date()} (the overlap where Bitget publishes funding)",
        f"- assets compared: {len(table)}",
        f"- median ratio of total funding paid (Bitget / Binance): **{summary['median_sum_ratio']:.3f}**",
        f"- median ratio of mean settlement rate: {summary['median_mean_rate_ratio']:.3f}",
        f"- median settlements in the window: Bitget {summary['bitget_median_settlements']}, Binance {summary['binance_median_settlements']}",
        "",
        "A ratio above 1 means the Binance proxy understates the real Bitget funding cost, so the",
        "proxy stress band should be anchored at this multiple rather than at 1.0x.",
        "",
        dataframe_to_markdown(table),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote funding calibration to {output_dir}")


if __name__ == "__main__":
    main()
