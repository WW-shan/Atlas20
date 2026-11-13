"""Daily-frequency BTC shock relative-gap diagnostic for Atlas20.

The diagnostic asks whether a point-in-time Top20 alt that lagged a BTC shock
catches up over the next one to ten days.  It is a gross event study only: no
orders, no funding and no live-state changes.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_intraday_btc_leadlag_diagnostic import (  # noqa: E402
    _cell_statistics,
    _period_rows,
    build_membership,
    signal_window_return,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-11-12"
SIGNAL_DAYS = (1, 3, 5, 10)
FUTURE_DAYS = (1, 3, 5, 10)
SHOCK_BUCKETS = ("all", "abs_z_ge_2_0", "abs_z_ge_2_5")
TAIL_FRACTIONS = (0.10, 0.20)
BETA_WINDOW_DAYS = 120
MIN_BETA_OBSERVATIONS = 90
ROUND_TRIP_COST_BPS = 40.0
BUFFER_BPS = 10.0
PERIODS: dict[str, tuple[str, str]] = {
    "full": ("2022-01-01", "2026-11-12"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-11-12"),
}


def _utc_index(values: Any) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(values, utc=True))
    return index.sort_values()


def _future_close_return(close: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Return log(close(t+1+h)/close(t+1)); entry is next close."""
    if horizon < 1:
        raise ValueError("horizon must be positive")
    with np.errstate(divide="ignore", invalid="ignore"):
        values = np.log(close.shift(-(horizon + 1)) / close.shift(-1))
    return values.replace([np.inf, -np.inf], np.nan)


def _cell_tier(
    *,
    discovery_ic: float,
    validation_ic: float,
    discovery_spread: float,
    validation_spread: float,
) -> str:
    if (
        discovery_ic < 0.0
        and validation_ic < 0.0
        and discovery_spread > ROUND_TRIP_COST_BPS + BUFFER_BPS
        and validation_spread > ROUND_TRIP_COST_BPS + BUFFER_BPS
    ):
        return "candidate-for-backtest"
    if (
        discovery_ic < 0.0
        and validation_ic < 0.0
        and discovery_spread > 0.0
        and validation_spread > 0.0
    ):
        return "watch"
    return "rejected-now"


def _report(summary: pd.DataFrame, *, start: str, end: str) -> str:
    discovery = summary.loc[summary["sample"] == "discovery"].copy()
    discovery = discovery.dropna(subset=["contrarian_spread_mean_bps"])
    discovery = discovery.sort_values(
        "contrarian_spread_mean_bps", ascending=False, kind="stable"
    )
    selected = discovery.head(16)
    keys = set(
        selected[["signal_days", "future_days", "bucket", "tail_fraction"]].itertuples(
            index=False, name=None
        )
    )
    validation = summary.loc[summary["sample"] == "validation"].copy()
    validation = validation.loc[
        validation[["signal_days", "future_days", "bucket", "tail_fraction"]]
        .apply(tuple, axis=1)
        .isin(keys)
    ]
    validation = validation.sort_values(
        "contrarian_spread_mean_bps", ascending=False, kind="stable"
    )
    display_cols = [
        "signal_days",
        "future_days",
        "bucket",
        "tail_fraction",
        "n_obs",
        "ic_mean",
        "contrarian_spread_mean_bps",
        "spread_tstat",
        "spread_positive_share",
        "tier",
    ]
    validation_cols = [column for column in display_cols if column != "tier"]
    corroborated = 0
    if not selected.empty:
        joined = selected.merge(
            validation,
            on=["signal_days", "future_days", "bucket", "tail_fraction"],
            suffixes=("_discovery", "_validation"),
        )
        if not joined.empty:
            corroborated = int(
                (
                    (joined["ic_mean_discovery"] < 0.0)
                    & (joined["ic_mean_validation"] < 0.0)
                    & (joined["contrarian_spread_mean_bps_discovery"] > 0.0)
                    & (joined["contrarian_spread_mean_bps_validation"] > 0.0)
                ).sum()
            )
    lines = [
        "# Daily BTC shock relative-gap diagnostic",
        "",
        "- status: gross event study only; no orders; no costs applied to the spread",
        f"- sample: {start} → {end}",
        "- discovery: 2022-01-01 → 2023-12-31; validation: 2024-01-01 → 2026-11-12",
        "- beta: 120D rolling BTC beta, minimum 90 daily returns",
        "- signal/future windows: 1/3/5/10 days; tails: 10% and 20%",
        "- shock buckets: all, |z|>=2.0, |z|>=2.5",
        f"- backtest cost buffer: round-trip {ROUND_TRIP_COST_BPS:g}bps + {BUFFER_BPS:g}bps",
        "",
        "## Discovery-ranked cells",
        "",
        "Cells are ranked by discovery contrarian spread only. Validation is shown for the same "
        "cells and was not used to choose the windows.",
        "",
        dataframe_to_markdown(selected[display_cols].reset_index(drop=True)),
        "",
        "## Validation for the same cells",
        "",
        f"Among the 16 discovery-ranked cells, **{corroborated}/16** have negative IC and positive "
        "contrarian spread in both periods.",
        "",
        dataframe_to_markdown(validation[validation_cols].reset_index(drop=True)),
        "",
        "## Interpretation",
        "",
        "Daily observations overlap for horizons above one day, so the t-stat is descriptive, not "
        "an independent-sample test. A candidate label requires the discovery and validation gross "
        "spread to exceed a 50bps combined cost-and-buffer threshold. Any candidate still needs a "
        "proper T+1 close backtest, funding, slippage and a non-overlapping event scheduler before "
        "it can be considered for live integration.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date >= args.end_date:
        parser.error("--start-date must be before --end-date")
    if args.start_date != DEFAULT_START or args.end_date != DEFAULT_END:
        parser.error(
            "the registered LS68 diagnostic expects 2022-01-01 → 2026-11-12; "
            "register a new study for another window"
        )

    _, market, universe, raw_index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    index = _utc_index([pd.Timestamp(value) for value in raw_index])
    close = market.price.copy()
    close.index = _utc_index([pd.Timestamp(value) for value in close.index])
    close = close[~close.index.duplicated(keep="last")].sort_index().reindex(index)
    returns = market.returns.copy()
    returns.index = _utc_index([pd.Timestamp(value) for value in returns.index])
    returns = returns[~returns.index.duplicated(keep="last")].sort_index().reindex(index)
    assets = [
        str(column)
        for column in close.columns
        if str(column) != "bitcoin" and str(column) in returns.columns
    ]
    if not assets:
        raise SystemExit("no alt assets available for the diagnostic")
    membership = build_membership(
        universe,
        index=index,
        assets=assets,
    )
    btc_return = returns["bitcoin"]
    market_var = btc_return.rolling(
        BETA_WINDOW_DAYS,
        min_periods=MIN_BETA_OBSERVATIONS,
    ).var(ddof=1)
    covariance = returns[assets].rolling(
        BETA_WINDOW_DAYS,
        min_periods=MIN_BETA_OBSERVATIONS,
    ).cov(btc_return)
    beta = covariance.div(market_var, axis=0)
    beta = beta.replace([np.inf, -np.inf], np.nan).clip(0.0, 4.0)

    summary_rows: list[dict[str, Any]] = []
    for signal_days in SIGNAL_DAYS:
        asset_signal = signal_window_return(close, signal_days)[assets]
        btc_signal = signal_window_return(close[["bitcoin"]], signal_days)["bitcoin"]
        shock_std = btc_signal.rolling(
            BETA_WINDOW_DAYS,
            min_periods=MIN_BETA_OBSERVATIONS,
        ).std(ddof=1)
        shock_z = (btc_signal / shock_std).replace([np.inf, -np.inf], np.nan)
        gap = asset_signal.sub(beta.mul(btc_signal, axis=0))
        for future_days in FUTURE_DAYS:
            future_asset = _future_close_return(close[assets], future_days)
            future_btc = _future_close_return(close[["bitcoin"]], future_days)["bitcoin"]
            future_residual = future_asset.sub(beta.mul(future_btc, axis=0))
            for tail_fraction in TAIL_FRACTIONS:
                observations = _cell_statistics(
                    signal_returns=gap,
                    future_residual=future_residual,
                    membership=membership,
                    shock_z=shock_z,
                    horizon=1,
                    tail_fraction=tail_fraction,
                    shock_buckets=SHOCK_BUCKETS,
                )
                for bucket in SHOCK_BUCKETS:
                    times, ic_values, spreads = observations[bucket]
                    for sample_name, (start, end) in PERIODS.items():
                        period = _period_rows(
                            timestamp_index=pd.DatetimeIndex(times),
                            ic_values=ic_values,
                            spread_values=spreads,
                            start=start,
                            end=end,
                        )
                        summary_rows.append(
                            {
                                "signal_days": signal_days,
                                "future_days": future_days,
                                "bucket": bucket,
                                "tail_fraction": tail_fraction,
                                "sample": sample_name,
                                **period,
                            }
                        )

    summary = pd.DataFrame(summary_rows)
    pivot = summary.pivot_table(
        index=["signal_days", "future_days", "bucket", "tail_fraction"],
        columns="sample",
        values=["ic_mean", "contrarian_spread_mean_bps"],
    )
    tiers: list[dict[str, Any]] = []
    for key, row in pivot.iterrows():
        tiers.append(
            {
                "signal_days": key[0],
                "future_days": key[1],
                "bucket": key[2],
                "tail_fraction": key[3],
                "tier": _cell_tier(
                    discovery_ic=float(row[("ic_mean", "discovery")]),
                    validation_ic=float(row[("ic_mean", "validation")]),
                    discovery_spread=float(
                        row[("contrarian_spread_mean_bps", "discovery")]
                    ),
                    validation_spread=float(
                        row[("contrarian_spread_mean_bps", "validation")]
                    ),
                ),
            }
        )
    summary = summary.merge(
        pd.DataFrame(tiers),
        on=["signal_days", "future_days", "bucket", "tail_fraction"],
        how="left",
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "cell_summary.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")

    summary.to_csv(files["summary"], index=False)
    files["report"].write_text(
        _report(summary, start=args.start_date, end=args.end_date),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS68-DAILY-BTC-SHOCK-LEADLAG",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "signal_days": list(SIGNAL_DAYS),
        "future_days": list(FUTURE_DAYS),
        "shock_buckets": list(SHOCK_BUCKETS),
        "tail_fractions": list(TAIL_FRACTIONS),
        "beta_window_days": BETA_WINDOW_DAYS,
        "min_beta_observations": MIN_BETA_OBSERVATIONS,
        "assets": assets,
        "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
        "buffer_bps": BUFFER_BPS,
        "orders_sent": False,
        "funding_included": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir} with {len(summary)} diagnostic rows")


if __name__ == "__main__":
    main()
