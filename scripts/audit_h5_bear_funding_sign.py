# ruff: noqa: E402

"""Audit entry-time funding for the frozen LS12 short episodes.

This is a read-only diagnostic. It does not create a strategy trial or change
the live book. The output supports the pre-registration of LS21, which asks
whether the bear weak-four sleeve should require strictly positive carry.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_derivatives_backtest import _funding_for_source
from scripts.run_phase_momentum import _load_market

DEFAULT_EPISODES = Path(
    "reports/derivatives_track_h5_regime_short_router/"
    "PR2026-11-LS12-H5-REGIME-SHORT-ROUTER/short_episode_attribution.csv"
)
DEFAULT_SLEEVE_AUDIT = Path(
    "reports/derivatives_track_h5_regime_short_router/"
    "PR2026-11-LS12-H5-REGIME-SHORT-ROUTER/sleeve_audit.csv"
)
DEFAULT_SYMBOL_MAP = Path("data/raw/bitget_derivatives/merged_20261009/symbol_map.csv")
DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_20261009")
DEFAULT_FUNDING_DIR = Path("data/raw/binance_funding")
DEFAULT_OUTPUT_DIR = Path(
    "reports/derivatives_track_h5_regime_short_router/bear_funding_sign_audit"
)


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _mean_recent_funding(
    funding: pd.DataFrame,
    asset: str,
    as_of: pd.Timestamp,
    *,
    settlements: int = 3,
) -> float:
    if asset not in funding.columns:
        return float("nan")
    series = pd.to_numeric(funding[asset], errors="coerce").dropna().sort_index()
    if series.empty:
        return float("nan")
    index = pd.DatetimeIndex(series.index)
    naive_dates = index.tz_localize(None) if index.tz is not None else index
    mask = naive_dates.normalize() <= as_of.tz_localize(None).normalize()
    if not mask.any():
        return float("nan")
    return float(series.loc[mask].iloc[-settlements:].mean())


def build_audit(
    episodes: pd.DataFrame,
    sleeve_audit: pd.DataFrame,
    funding: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = episodes.copy()
    frame["entry_time"] = pd.to_datetime(frame["entry_time"], utc=True)
    frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
    frame["entry_date"] = frame["entry_time"].dt.tz_localize(None).dt.normalize()
    frame["year"] = frame["entry_time"].dt.year

    regime = sleeve_audit.copy()
    regime["date"] = pd.to_datetime(regime["date"], utc=True).dt.tz_localize(None).dt.normalize()
    frame["entry_regime"] = frame["entry_date"].map(regime.set_index("date")["regime"])
    frame["funding_mean_3"] = [
        _mean_recent_funding(funding, str(row.asset), _as_utc(row.entry_date))
        for row in frame.itertuples()
    ]
    frame["positive_funding"] = frame["funding_mean_3"] > 0.0

    grouped = (
        frame.groupby(["entry_regime", "positive_funding"], dropna=False)[
            "net_pnl_pct_nav"
        ]
        .agg(["count", "sum", "mean", "median", "min", "max"])
        .reset_index()
    )
    yearly = (
        frame.groupby(["year", "entry_regime", "positive_funding"], dropna=False)[
            "net_pnl_pct_nav"
        ]
        .agg(["count", "sum", "mean", "median"])
        .reset_index()
    )
    summary = grouped.merge(
        yearly,
        on=["entry_regime", "positive_funding"],
        how="left",
        suffixes=("", "_by_year"),
    )
    return frame, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=Path, default=DEFAULT_EPISODES)
    parser.add_argument("--sleeve-audit", type=Path, default=DEFAULT_SLEEVE_AUDIT)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--binance-funding-dir", type=Path, default=DEFAULT_FUNDING_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    _, market, _, _ = _load_market(
        "config/base.yaml",
        start_date="2022-01-01",
        end_date="2026-09-21",
    )
    symbol_map = pd.read_csv(args.symbol_map)
    funding = _funding_for_source(
        "binance-proxy",
        raw_dir=args.raw_dir,
        binance_dir=args.binance_funding_dir,
        symbol_map=symbol_map,
        coins=set(market.price.columns),
    )
    episodes = pd.read_csv(args.episodes)
    sleeve_audit = pd.read_csv(args.sleeve_audit)
    detailed, summary = build_audit(episodes, sleeve_audit, funding)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    detailed.to_csv(args.output_dir / "episode_funding_sign.csv", index=False)
    summary.to_csv(args.output_dir / "summary_by_regime.csv", index=False)

    bear = detailed.loc[detailed["entry_regime"] == "bear"]
    positive = bear.loc[bear["positive_funding"]]
    non_positive = bear.loc[~bear["positive_funding"]]
    report = [
        "# LS12 bear-short funding-sign audit",
        "",
        "Read-only diagnostic; no strategy trial is created and the live book is unchanged.",
        "",
        f"- Bear episodes: {len(bear)}",
        f"- Positive 3-settlement mean funding: {len(positive)}",
        f"- Non-positive funding: {len(non_positive)}",
        f"- Positive-group episode PnL: {positive['net_pnl_pct_nav'].sum():.4f}% NAV",
        f"- Non-positive-group episode PnL: {non_positive['net_pnl_pct_nav'].sum():.4f}% NAV",
        "",
        "See `episode_funding_sign.csv` for the entry-level facts and "
        "`summary_by_regime.csv` for the complete grouped summary.",
    ]
    (args.output_dir / "README.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Wrote funding-sign audit to {args.output_dir}")


if __name__ == "__main__":
    main()
