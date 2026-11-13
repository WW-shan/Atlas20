"""Diagnose whether Bitcoin shocks lead lagging PIT Top20 alts intraday.

This is a predictive diagnostic, not a tradable backtest.  It uses validated
Binance 30-minute bars, strict point-in-time Top20 membership and only reports
cross-sectional rank correlations and spread statistics.  No orders are sent.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections.abc import Mapping
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

from scripts.analyze_intraday_execution_timing import load_30m_bars  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-09-30"
SIGNAL_WINDOWS = (1, 2, 4, 8)
FUTURE_HORIZONS = (1, 2, 4, 8)
SHOCK_BUCKETS = ("all", "abs_z_ge_1_5", "abs_z_ge_2_5")
BETA_WINDOW_BARS = 30 * 48
MIN_BETA_OBSERVATIONS = 20 * 48
BETA_CLIP = (0.0, 4.0)
MIN_CROSS_SECTION = 8
BPS = 10_000.0
PERIODS: dict[str, tuple[str, str]] = {
    "full": ("2022-01-01", "2026-09-30"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-30"),
}


def _utc_index(values: Any) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(values, utc=True))
    return index.sort_values()


def build_price_panels(
    bars: Mapping[str, pd.DataFrame],
    *,
    index: pd.DatetimeIndex | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Align per-coin 30m opens and closes into UTC wide panels."""
    opens: dict[str, pd.Series] = {}
    closes: dict[str, pd.Series] = {}
    for coin, frame in bars.items():
        times = _utc_index(frame["open_time"])
        opens[str(coin)] = pd.Series(
            pd.to_numeric(frame["open"], errors="coerce").to_numpy(dtype=float),
            index=times,
            name=str(coin),
        )
        closes[str(coin)] = pd.Series(
            pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float),
            index=times,
            name=str(coin),
        )
    open_frame = pd.concat(opens, axis=1, sort=True).sort_index()
    close_frame = pd.concat(closes, axis=1, sort=True).sort_index()
    if index is not None:
        open_frame = open_frame.reindex(index)
        close_frame = close_frame.reindex(index)
    return open_frame, close_frame


def build_membership(
    universe: pd.DataFrame,
    *,
    index: pd.DatetimeIndex,
    assets: list[str],
) -> pd.DataFrame:
    """Forward-fill point-in-time Top20 membership onto 30m bar timestamps."""
    frame = universe.copy()
    frame["rebalance_date"] = pd.to_datetime(frame["rebalance_date"], utc=True)
    frame["present"] = True
    daily = (
        frame.pivot_table(
            index="rebalance_date",
            columns="coin_id",
            values="present",
            aggfunc="max",
        )
        .fillna(False)
        .astype(bool)
        .sort_index()
    )
    daily = daily.reindex(columns=assets, fill_value=False)
    bar_dates = pd.DatetimeIndex(index).normalize()
    expanded = daily.reindex(bar_dates, method="ffill")
    expanded.index = index
    return expanded.fillna(False).astype(bool)


def execution_future_return(
    open_prices: pd.DataFrame,
    close_prices: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    """Return log(next-open to close-h-bars-later) for every signal bar."""
    if horizon < 1:
        raise ValueError("horizon must be positive")
    entry = open_prices.shift(-1)
    exit_ = close_prices.shift(-horizon)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.log(exit_ / entry)
    return result.replace([np.inf, -np.inf], np.nan)


def signal_window_return(close_prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """Return log(close(t) / close(t-window)) for every signal bar."""
    if window < 1:
        raise ValueError("window must be positive")
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.log(close_prices / close_prices.shift(window))
    return result.replace([np.inf, -np.inf], np.nan)


def _mean_tstat(values: list[float]) -> tuple[float, float]:
    if len(values) < 2:
        return float("nan"), float("nan")
    array = np.asarray(values, dtype=float)
    standard_error = float(array.std(ddof=1) / np.sqrt(len(array)))
    if not np.isfinite(standard_error) or standard_error <= 0.0:
        return float(array.mean()), float("nan")
    return float(array.mean()), float(array.mean() / standard_error)


def _cell_statistics(
    *,
    signal_returns: pd.DataFrame,
    future_residual: pd.DataFrame,
    membership: pd.DataFrame,
    shock_z: pd.Series,
    horizon: int,
) -> dict[str, tuple[list[pd.Timestamp], list[float], list[float]]]:
    """Compute non-overlapping cross-sectional IC/spread observations.

    The matrix operations are row-wise: each sampled bar is one independent
    cross-section for its horizon, and rank correlations ignore missing or
    non-member assets.
    """
    if horizon < 1:
        raise ValueError("horizon must be positive")
    positions = np.arange(0, len(signal_returns), horizon)
    timestamps = pd.DatetimeIndex(signal_returns.index)[positions]
    gap = signal_returns.iloc[positions].reset_index(drop=True)
    future = future_residual.iloc[positions].reset_index(drop=True)
    eligible = membership.iloc[positions].reset_index(drop=True)
    valid = (
        eligible.to_numpy(dtype=bool)
        & np.isfinite(gap.to_numpy(dtype=float))
        & np.isfinite(future.to_numpy(dtype=float))
    )
    gap = gap.where(valid)
    future = future.where(valid)
    counts = valid.sum(axis=1)

    gap_ranks = gap.rank(axis=1, method="average")
    future_ranks = future.rank(axis=1, method="average")
    gap_centered = gap_ranks.sub(gap_ranks.mean(axis=1), axis=0)
    future_centered = future_ranks.sub(future_ranks.mean(axis=1), axis=0)
    numerator = (gap_centered * future_centered).sum(axis=1)
    denominator = np.sqrt((gap_centered**2).sum(axis=1)) * np.sqrt(
        (future_centered**2).sum(axis=1)
    )
    ic = (numerator / denominator.replace(0.0, np.nan)).to_numpy(dtype=float)

    low_cut = gap.quantile(0.20, axis=1)
    high_cut = gap.quantile(0.80, axis=1)
    low_future = future.where(gap.le(low_cut, axis=0)).mean(axis=1)
    high_future = future.where(gap.ge(high_cut, axis=0)).mean(axis=1)
    spread = ((low_future - high_future) * BPS).to_numpy(dtype=float)

    z_values = pd.to_numeric(shock_z.iloc[positions], errors="coerce").to_numpy(
        dtype=float
    )
    enough = counts >= MIN_CROSS_SECTION
    finite = np.isfinite(ic) & np.isfinite(spread)
    results: dict[str, tuple[list[pd.Timestamp], list[float], list[float]]] = {}
    for bucket in SHOCK_BUCKETS:
        if bucket == "all":
            bucket_mask = np.isfinite(z_values)
        elif bucket == "abs_z_ge_1_5":
            bucket_mask = np.isfinite(z_values) & (np.abs(z_values) >= 1.5)
        elif bucket == "abs_z_ge_2_5":
            bucket_mask = np.isfinite(z_values) & (np.abs(z_values) >= 2.5)
        else:  # pragma: no cover - guarded by the module constant
            raise ValueError(f"unknown shock bucket {bucket!r}")
        keep = enough & finite & bucket_mask
        results[bucket] = (
            [pd.Timestamp(value) for value in timestamps[keep]],
            ic[keep].tolist(),
            spread[keep].tolist(),
        )
    return results


def _period_rows(
    *,
    timestamp_index: pd.DatetimeIndex,
    ic_values: list[float],
    spread_values: list[float],
    start: str,
    end: str,
) -> dict[str, float | int]:
    timestamp_index = pd.DatetimeIndex(pd.to_datetime(timestamp_index, utc=True))
    lower = pd.Timestamp(start, tz="UTC")
    upper = pd.Timestamp(end, tz="UTC")
    mask = (timestamp_index >= lower) & (timestamp_index <= upper)
    if len(mask) != len(ic_values):
        raise ValueError("timestamp/index mismatch")
    selected_ic = [value for value, keep in zip(ic_values, mask, strict=True) if keep]
    selected_spread = [value for value, keep in zip(spread_values, mask, strict=True) if keep]
    ic_mean, ic_tstat = _mean_tstat(selected_ic)
    spread_mean, spread_tstat = _mean_tstat(selected_spread)
    return {
        "n_obs": len(selected_ic),
        "ic_mean": ic_mean,
        "ic_tstat": ic_tstat,
        "ic_negative_share": (
            float(np.mean(np.asarray(selected_ic) < 0.0)) if selected_ic else float("nan")
        ),
        "contrarian_spread_mean_bps": spread_mean,
        "spread_tstat": spread_tstat,
        "spread_positive_share": (
            float(np.mean(np.asarray(selected_spread) > 0.0))
            if selected_spread
            else float("nan")
        ),
    }


def _report(summary: pd.DataFrame, *, start: str, end: str) -> str:
    discovery = summary.loc[summary["sample"] == "discovery"].copy()
    discovery = discovery.dropna(subset=["contrarian_spread_mean_bps"])
    discovery = discovery.sort_values(
        "contrarian_spread_mean_bps", ascending=False, kind="stable"
    )
    selected = discovery.head(12)
    display = selected[
        [
            "signal_bars",
            "future_bars",
            "bucket",
            "n_obs",
            "ic_mean",
            "contrarian_spread_mean_bps",
            "spread_tstat",
            "spread_positive_share",
        ]
    ]
    selected_keys = list(
        selected[["signal_bars", "future_bars", "bucket"]].itertuples(
            index=False, name=None
        )
    )
    validation = summary.loc[summary["sample"] == "validation"].copy()
    key_order = {
        key: order
        for order, key in enumerate(
            summary.loc[summary["sample"] == "discovery"]
            .sort_values("contrarian_spread_mean_bps", ascending=False, kind="stable")
            [["signal_bars", "future_bars", "bucket"]]
            .itertuples(index=False, name=None)
        )
    }
    validation["_sort_order"] = [
        key_order.get((row.signal_bars, row.future_bars, row.bucket), len(key_order) + 1)
        for row in validation.itertuples(index=False)
    ]
    validation = validation.loc[
        validation[["signal_bars", "future_bars", "bucket"]]
        .apply(tuple, axis=1)
        .isin(selected_keys)
    ].sort_values("_sort_order", kind="stable")
    corroborated = 0
    if not selected.empty:
        joined = selected.merge(
            validation,
            on=["signal_bars", "future_bars", "bucket"],
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
        "# Intraday BTC shock lead-lag diagnostic",
        "",
        "- status: predictive diagnostic only; no orders; no costs",
        f"- sample: {start} → {end}",
        "- discovery: 2022-01-01 → 2023-12-31; validation: 2024-01-01 → 2026-09-30",
        "- bars: Binance 30m; beta: 30D rolling BTC beta, min 20D and clipped to [0,4]",
        "- signal windows: 1/2/4/8 bars; future horizons: 1/2/4/8 bars",
        "- shock buckets: all, |z|>=1.5, |z|>=2.5",
        "",
        "## Discovery-ranked cells",
        "",
        "The table ranks cells by discovery contrarian spread only. Validation is reported for the "
        "same cells and was not used to choose the signal windows or shock thresholds.",
        "",
        dataframe_to_markdown(display.reset_index(drop=True)),
        "",
        "## Validation rows for the same cells",
        "",
        "A cell is corroborated only if its IC is negative and its contrarian spread is positive in "
        f"both periods. Among the 12 discovery-ranked cells, **{corroborated}/12** meet that sign test.",
        "",
        dataframe_to_markdown(
            validation[
                [
                    "signal_bars",
                    "future_bars",
                    "bucket",
                    "n_obs",
                    "ic_mean",
                    "contrarian_spread_mean_bps",
                    "spread_tstat",
                    "spread_positive_share",
                ]
            ].reset_index(drop=True)
        ),
        "",
        "## Interpretation",
        "",
        "The contrarian spread is the equal-weight mean future beta-adjusted residual of the lowest-gap "
        "quintile minus the highest-gap quintile. It is not a tradable return: it assumes frictionless "
        "round trips, ignores queue/impact/funding and uses overlapping future windows only at the "
        "sampling step. A positive result must clear a separate backtest before any live integration.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--bar-dir", type=Path, default=Path("data/raw/binance_30m"))
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
            "the registered diagnostic expects 2022-01-01 → 2026-09-30; "
            "register a new study for another window"
        )

    bars = load_30m_bars(args.bar_dir)
    if "bitcoin" not in bars:
        raise SystemExit("Bitcoin 30m bars are required")
    target_assets = sorted(
        [coin for coin in bars if coin != "bitcoin"],
        key=str.casefold,
    )
    _, _, universe, _ = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    btc_times = _utc_index(bars["bitcoin"]["open_time"])
    start_ts = pd.Timestamp(args.start_date, tz="UTC")
    end_ts = pd.Timestamp(args.end_date, tz="UTC") + pd.Timedelta(hours=23, minutes=59)
    bar_index = btc_times[(btc_times >= start_ts) & (btc_times <= end_ts)]
    open_frame, close_frame = build_price_panels(bars, index=bar_index)
    # Keep only assets present in both the 30m cache and the panel universe.
    available_assets = [
        asset
        for asset in target_assets
        if asset in open_frame.columns and asset in close_frame.columns
    ]
    close_frame = close_frame[["bitcoin", *available_assets]]
    open_frame = open_frame[["bitcoin", *available_assets]]
    membership = build_membership(
        universe,
        index=pd.DatetimeIndex(close_frame.index),
        assets=available_assets,
    )
    returns = (
        np.log(close_frame.where(close_frame > 0.0) / close_frame.where(close_frame > 0.0).shift(1))
        .replace([np.inf, -np.inf], np.nan)
    )
    btc_returns = returns["bitcoin"]
    beta_window = BETA_WINDOW_BARS
    min_beta = MIN_BETA_OBSERVATIONS
    market_var = btc_returns.rolling(beta_window, min_periods=min_beta).var(ddof=1)
    alpha_returns = returns[available_assets]
    alpha_cov = alpha_returns.rolling(beta_window, min_periods=min_beta).cov(btc_returns)
    beta = alpha_cov.div(market_var, axis=0)
    beta = beta.replace([np.inf, -np.inf], np.nan).clip(*BETA_CLIP)

    summary_rows: list[dict[str, Any]] = []
    for signal_bars in SIGNAL_WINDOWS:
        signal_returns = signal_window_return(close_frame, signal_bars)[available_assets]
        btc_shock = signal_window_return(close_frame[["bitcoin"]], signal_bars)["bitcoin"]
        shock_std = btc_shock.rolling(beta_window, min_periods=min_beta).std(ddof=1)
        shock_z = (btc_shock / shock_std).replace([np.inf, -np.inf], np.nan)
        gap = signal_returns.sub(beta.mul(btc_shock, axis=0))
        for future_horizon in FUTURE_HORIZONS:
            future_btc = execution_future_return(
                open_frame[["bitcoin"]], close_frame[["bitcoin"]], future_horizon
            )["bitcoin"]
            future_assets = execution_future_return(
                open_frame[available_assets], close_frame[available_assets], future_horizon
            )
            future_residual = future_assets.sub(
                beta.mul(future_btc, axis=0)
            )
            cell_results = _cell_statistics(
                signal_returns=gap,
                future_residual=future_residual,
                membership=membership,
                shock_z=shock_z,
                horizon=future_horizon,
            )
            for bucket in SHOCK_BUCKETS:
                retained_times, ic_values, spread_values = cell_results[bucket]
                for sample_name, (start, end) in PERIODS.items():
                    period = _period_rows(
                        timestamp_index=pd.DatetimeIndex(retained_times),
                        ic_values=ic_values,
                        spread_values=spread_values,
                        start=start,
                        end=end,
                    )
                    summary_rows.append(
                        {
                            "signal_bars": signal_bars,
                            "future_bars": future_horizon,
                            "bucket": bucket,
                            "sample": sample_name,
                            **period,
                        }
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

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(files["summary"], index=False)
    files["report"].write_text(
        _report(summary, start=args.start_date, end=args.end_date),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS63-INTRADAY-BTC-LEADLAG-DIAGNOSTIC",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "signal_windows": list(SIGNAL_WINDOWS),
        "future_horizons": list(FUTURE_HORIZONS),
        "shock_buckets": list(SHOCK_BUCKETS),
        "beta_window_bars": BETA_WINDOW_BARS,
        "min_beta_observations": MIN_BETA_OBSERVATIONS,
        "beta_clip": list(BETA_CLIP),
        "min_cross_section": MIN_CROSS_SECTION,
        "assets": available_assets,
        "bars": int(len(close_frame)),
        "summaries": len(summary),
        "orders_sent": False,
        "costs_included": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir} with {len(summary)} summary rows")


if __name__ == "__main__":
    main()
