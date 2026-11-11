# ruff: noqa: E402
"""Audit Binance/Bybit funding coverage for saved short episodes.

This is a read-only diagnostic. It does not evaluate returns, create a strategy
trial, or change the live book. It answers one question before any new trial:
is a second funding venue available and aligned often enough to define a
conservative cross-venue carry signal?
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

DEFAULT_EPISODES = Path(
    "reports/derivatives_track_h5_regime_short_router/"
    "bear_funding_sign_audit/episode_funding_sign.csv"
)
DEFAULT_BYBIT_DIR = Path("data/raw/alternative_funding/bybit")
DEFAULT_OUTPUT_DIR = Path("reports/derivatives_track_cross_venue_funding_audit")


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _mean_recent_funding(
    series: pd.Series | None,
    as_of: pd.Timestamp,
    *,
    settlements: int = 3,
) -> float:
    if series is None or series.empty:
        return float("nan")
    index = pd.DatetimeIndex(series.index)
    mask = index.floor("min") <= _as_utc(as_of).floor("min")
    if not mask.any():
        return float("nan")
    values = pd.to_numeric(series.loc[mask], errors="coerce").dropna().iloc[-settlements:]
    if len(values) < settlements:
        return float("nan")
    return float(values.mean())


def build_cross_venue_audit(
    episodes: pd.DataFrame,
    bybit_rates: Mapping[str, pd.Series],
) -> pd.DataFrame:
    frame = episodes.copy()
    if "entry_time" in frame.columns:
        frame["signal_date"] = (
            pd.to_datetime(frame["entry_time"], utc=True).dt.normalize()
            - pd.Timedelta(days=1)
        )
    elif "entry_date" in frame.columns:
        frame["signal_date"] = pd.to_datetime(frame["entry_date"], utc=True)
    else:
        raise ValueError("episodes need entry_time or entry_date")
    frame["binance_mean_3"] = pd.to_numeric(
        frame["funding_mean_3"] if "funding_mean_3" in frame.columns else np.nan,
        errors="coerce",
    )
    frame["bybit_mean_3"] = [
        _mean_recent_funding(bybit_rates.get(str(asset)), signal_date)
        for asset, signal_date in zip(frame["asset"], frame["signal_date"], strict=True)
    ]
    frame["bybit_available"] = frame["bybit_mean_3"].notna()
    frame["both_available"] = frame["binance_mean_3"].notna() & frame["bybit_available"]
    frame["both_positive"] = (
        frame["both_available"]
        & (frame["binance_mean_3"] > 0.0)
        & (frame["bybit_mean_3"] > 0.0)
    )
    frame["same_sign"] = frame["both_available"] & (
        np.sign(frame["binance_mean_3"]) == np.sign(frame["bybit_mean_3"])
    )
    columns = [
        "asset",
        "signal_date",
        "entry_regime",
        "binance_mean_3",
        "bybit_mean_3",
        "bybit_available",
        "both_available",
        "both_positive",
        "same_sign",
    ]
    return frame[columns].reset_index(drop=True)


def summarize_cross_venue_audit(audit: pd.DataFrame) -> dict[str, object]:
    if audit.empty:
        return {
            "total_episodes": 0,
            "bybit_available": 0,
            "bybit_coverage": 0.0,
            "bear_episodes": 0,
            "bear_bybit_available": 0,
            "bear_both_positive": 0,
            "bear_same_sign": 0,
            "non_bear_episodes": 0,
            "non_bear_bybit_available": 0,
            "non_bear_both_positive": 0,
            "non_bear_same_sign": 0,
        }
    bear = audit.loc[audit["entry_regime"] == "bear"]
    non_bear = audit.loc[audit["entry_regime"] == "non_bear"]
    return {
        "total_episodes": int(len(audit)),
        "bybit_available": int(audit["bybit_available"].sum()),
        "bybit_coverage": float(audit["bybit_available"].mean()),
        "bear_episodes": int(len(bear)),
        "bear_bybit_available": int(bear["bybit_available"].sum()),
        "bear_both_positive": int(bear["both_positive"].sum()),
        "bear_same_sign": int(bear["same_sign"].sum()),
        "non_bear_episodes": int(len(non_bear)),
        "non_bear_bybit_available": int(non_bear["bybit_available"].sum()),
        "non_bear_both_positive": int(non_bear["both_positive"].sum()),
        "non_bear_same_sign": int(non_bear["same_sign"].sum()),
    }


def _load_bybit_rates(path: Path) -> dict[str, pd.Series]:
    rates: dict[str, pd.Series] = {}
    for csv_path in sorted(path.glob("*.csv")):
        frame = pd.read_csv(csv_path)
        if frame.empty or not {"funding_time", "funding_rate"}.issubset(frame.columns):
            continue
        index = pd.to_datetime(frame["funding_time"], utc=True, errors="coerce")
        values = pd.to_numeric(frame["funding_rate"], errors="coerce")
        series = pd.Series(values.to_numpy(dtype=float), index=index).dropna()
        series = series[~series.index.duplicated(keep="last")].sort_index()
        if not series.empty:
            rates[csv_path.stem] = series
    return rates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=Path, default=DEFAULT_EPISODES)
    parser.add_argument("--bybit-dir", type=Path, default=DEFAULT_BYBIT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    episodes = pd.read_csv(args.episodes)
    audit = build_cross_venue_audit(episodes, _load_bybit_rates(args.bybit_dir))
    summary = summarize_cross_venue_audit(audit)
    output_dir = ensure_dir(args.output_dir)
    audit.to_csv(output_dir / "episode_cross_venue_funding.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = [
        "# Cross-venue funding coverage audit",
        "",
        "Read-only diagnostic; no returns are evaluated and no strategy trial is created.",
        "",
        f"- episodes: {summary['total_episodes']}",
        f"- Bybit coverage: {summary['bybit_available']} / {summary['total_episodes']} "
        f"({summary['bybit_coverage']:.1%})",
        f"- bear episodes: {summary['bear_episodes']}, Bybit available "
        f"{summary['bear_bybit_available']}, both positive {summary['bear_both_positive']}, "
        f"same sign {summary['bear_same_sign']}",
        f"- non-bear episodes: {summary['non_bear_episodes']}, Bybit available "
        f"{summary['non_bear_bybit_available']}, both positive {summary['non_bear_both_positive']}, "
        f"same sign {summary['non_bear_same_sign']}",
        "",
        "Bybit values use the mean of the last three settlements at or before the signal date; "
        "missing Bybit history is never filled.",
        "",
        dataframe_to_markdown(audit.head(20)),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote cross-venue funding audit to {output_dir}")


if __name__ == "__main__":
    main()
