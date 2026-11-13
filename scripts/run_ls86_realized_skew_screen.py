"""Pre-registered core8 realized-skew / lottery-demand event screen."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.analytics.rolling import rolling_skew  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.run_ls83_funding_settlement_screen import newey_west_t  # noqa: E402
from scripts.run_ls84_volume_reversal_screen import _load_market_data  # noqa: E402

CORE8 = (
    "bitcoin",
    "ethereum",
    "solana",
    "ripple",
    "binancecoin",
    "dogecoin",
    "cardano",
    "avalanche-2",
)
SCREEN_ID = "PR2026-11-LS86-CORE8-REALIZED-SKEW-SCREEN"
SAMPLE_WINDOWS = {
    "full": ("2022-01-01", "2026-09-20"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-20"),
}


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def build_realized_skew_events(
    *,
    hourly_prices: pd.DataFrame,
    daily_close: pd.DataFrame,
    assets: Sequence[str],
    rebalance_days: int = 7,
    lookback_days: int = 30,
    horizon_days: int = 7,
    entry_hour: int = 3,
) -> pd.DataFrame:
    """Build weekly low-skew long / high-skew short events."""
    if rebalance_days < 1:
        raise ValueError("rebalance_days must be positive")
    if lookback_days < 3:
        raise ValueError("lookback_days must be at least three")
    if horizon_days < 1:
        raise ValueError("horizon_days must be positive")
    if entry_hour < 0 or entry_hour > 23:
        raise ValueError("entry_hour must be in [0, 23]")
    assets = tuple(str(asset) for asset in assets)
    missing = set(assets).difference(hourly_prices.columns).union(
        set(assets).difference(daily_close.columns)
    )
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    prices = hourly_prices.loc[:, list(assets)].apply(pd.to_numeric, errors="coerce").sort_index()
    close = daily_close.loc[:, list(assets)].apply(pd.to_numeric, errors="coerce").sort_index()
    close.index = pd.DatetimeIndex([_as_utc(value).normalize() for value in close.index])
    close = close[~close.index.duplicated(keep="last")].sort_index()
    daily_returns = close.pct_change(fill_method=None)
    skew = rolling_skew(daily_returns, window=lookback_days)
    eligible_dates = skew.dropna(how="any").index
    if eligible_dates.empty:
        return pd.DataFrame()
    anchor = pd.Timestamp(eligible_dates[0]).normalize()
    rows: list[dict[str, Any]] = []
    for signal_date in eligible_dates:
        signal_date = pd.Timestamp(signal_date).normalize()
        if (signal_date - anchor).days % rebalance_days:
            continue
        entry_time = signal_date + pd.Timedelta(days=1, hours=entry_hour)
        exit_time = entry_time + pd.Timedelta(days=horizon_days)
        if entry_time not in prices.index or exit_time not in prices.index:
            continue
        if prices.loc[entry_time].isna().any() or prices.loc[exit_time].isna().any():
            continue
        scores = skew.loc[signal_date]
        if scores.isna().any() or not np.isfinite(scores.to_numpy(dtype=float)).all():
            continue
        ranked = sorted(scores.items(), key=lambda item: (float(item[1]), str(item[0])))
        long_assets = [str(asset) for asset, _ in ranked[:2]]
        short_assets = [str(asset) for asset, _ in ranked[-2:]]
        forward_returns = prices.loc[exit_time] / prices.loc[entry_time] - 1.0
        long_return = float(forward_returns.loc[long_assets].mean())
        short_return = float(forward_returns.loc[short_assets].mean())
        row: dict[str, Any] = {
            "signal_date": signal_date,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "long_assets": ",".join(long_assets),
            "short_assets": ",".join(short_assets),
            "long_return_7d": long_return,
            "short_return_7d": short_return,
            "spread_7d": long_return - short_return,
        }
        for asset in assets:
            row[f"skew_{asset}"] = float(scores.loc[asset])
            row[f"ret_{asset}_7d"] = float(forward_returns.loc[asset])
        rows.append(row)
    return pd.DataFrame(rows)


def placebo_skew_reversal(
    events: pd.DataFrame,
    *,
    assets: Sequence[str],
    horizon: int = 7,
    iterations: int = 2000,
    seed: int = 20261113,
) -> pd.Series:
    """Randomize the two long/two short choices within the same universe."""
    if iterations < 1:
        raise ValueError("iterations must be positive")
    rng = np.random.default_rng(seed)
    returns = events[[f"ret_{asset}_{horizon}d" for asset in assets]].to_numpy(dtype=float)
    if len(returns) == 0:
        return pd.Series(dtype=float)
    simulated = np.empty(int(iterations), dtype=float)
    for iteration in range(int(iterations)):
        spreads = np.empty(len(returns), dtype=float)
        for event_index, event_returns in enumerate(returns):
            choice = rng.choice(len(assets), size=4, replace=False)
            spreads[event_index] = event_returns[choice[:2]].mean() - event_returns[choice[2:]].mean()
        simulated[iteration] = spreads.mean()
    return pd.Series(simulated, name=f"placebo_spread_{horizon}d")


def _sample_events(events: pd.DataFrame, sample: str) -> pd.DataFrame:
    start, end = SAMPLE_WINDOWS[sample]
    return events.loc[
        (events["signal_date"] >= pd.Timestamp(start, tz="UTC"))
        & (events["signal_date"] <= pd.Timestamp(end, tz="UTC"))
    ].copy()


def _metrics(values: pd.Series, *, cost_bps: float, horizon_days: int) -> dict[str, float]:
    series = pd.Series(values, dtype=float).dropna()
    if series.empty:
        return {
            "n": 0.0,
            "gross_mean": float("nan"),
            "net_mean": float("nan"),
            "cumulative": float("nan"),
            "max_drawdown": float("nan"),
            "t_stat": 0.0,
            "hit_rate": float("nan"),
        }
    net = series - 2.0 * float(cost_bps) / 10_000.0
    curve = (1.0 + net).cumprod()
    return {
        "n": float(len(series)),
        "gross_mean": float(series.mean()),
        "net_mean": float(net.mean()),
        "annualized_net_mean": float(net.mean() * (365.0 / horizon_days)),
        "cumulative": float(curve.iloc[-1] - 1.0),
        "max_drawdown": float((curve / curve.cummax() - 1.0).min()),
        "t_stat": newey_west_t(series, lags=1),
        "hit_rate": float((series > 0.0).mean()),
    }


def _report(summary: pd.DataFrame, placebo: pd.DataFrame, events: pd.DataFrame) -> str:
    lines = [
        f"# {SCREEN_ID}",
        "",
        "- Fixed core8; 30D daily-return realized skewness",
        "- Long two lowest skew / short two highest skew; weekly 7D hold",
        "- Entry at D+1 03:00 UTC; exit at +7D using Bitget market closes",
        "",
        "## Screen results",
        "",
        dataframe_to_markdown(summary.reset_index(drop=True)),
        "",
        "## Placebo",
        "",
        dataframe_to_markdown(placebo.reset_index(drop=True)),
        "",
        "## Decision",
        "",
    ]
    validation = summary.loc[
        (summary["sample"] == "validation") & (summary["horizon_days"] == 7)
    ]
    discovery = summary.loc[
        (summary["sample"] == "discovery") & (summary["horizon_days"] == 7)
    ]
    if validation.empty or discovery.empty:
        lines.append("Insufficient validation/discovery events; screen incomplete.")
    else:
        val = validation.iloc[0]
        disc = discovery.iloc[0]
        passed = (
            val["net_mean_50bps"] > 0.0
            and val["t_stat"] >= 2.0
            and np.sign(val["net_mean_50bps"]) == np.sign(disc["net_mean_50bps"])
        )
        lines.append(
            f"Validation 7D net mean at 50bps: {val['net_mean_50bps']:.6%}; "
            f"NW t={val['t_stat']:.4f}; discovery net mean: {disc['net_mean_50bps']:.6%}."
        )
        lines.append(
            "Screen **PASS**; engine trial required, not a live promotion."
            if passed
            else "Screen **FAIL**; do not build a portfolio trial from this event."
        )
    lines.extend(["", "Research output only; no orders sent or sanctioned.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--market-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_market_20261009"))
    parser.add_argument("--placebo-iterations", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    start = pd.Timestamp(args.start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    if start >= end:
        parser.error("start-date must precede end-date")
    symbol_map = pd.read_csv(args.market_dir / "symbol_map.csv")
    hourly, daily_close, _ = _load_market_data(
        args.market_dir,
        symbol_map=symbol_map,
        assets=CORE8,
    )
    events = build_realized_skew_events(
        hourly_prices=hourly,
        daily_close=daily_close,
        assets=CORE8,
        rebalance_days=7,
        lookback_days=30,
        horizon_days=7,
    )
    events = events.loc[(events["signal_date"] >= start) & (events["signal_date"] < end)].copy()
    if events.empty:
        raise SystemExit("no complete realized-skew events in the requested window")
    detail_rows: list[dict[str, Any]] = []
    for sample in SAMPLE_WINDOWS:
        sample_events = _sample_events(events, sample)
        for cost in (20.0, 50.0, 100.0):
            detail_rows.append(
                {
                    "sample": sample,
                    "horizon_days": 7,
                    "cost_bps": cost,
                    **_metrics(sample_events["spread_7d"], cost_bps=cost, horizon_days=7),
                }
            )
    detail = pd.DataFrame(detail_rows)
    compact_rows: list[dict[str, Any]] = []
    for sample in SAMPLE_WINDOWS:
        subset = detail.loc[detail["sample"] == sample].set_index("cost_bps")
        base = subset.loc[20.0]
        compact_rows.append(
            {
                "sample": sample,
                "horizon_days": 7,
                "n": int(base["n"]),
                "gross_mean": base["gross_mean"],
                "net_mean_20bps": subset.loc[20.0, "net_mean"],
                "net_mean_50bps": subset.loc[50.0, "net_mean"],
                "net_mean_100bps": subset.loc[100.0, "net_mean"],
                "cumulative_20bps": subset.loc[20.0, "cumulative"],
                "max_drawdown_20bps": subset.loc[20.0, "max_drawdown"],
                "t_stat": base["t_stat"],
                "hit_rate": base["hit_rate"],
            }
        )
    compact = pd.DataFrame(compact_rows)
    placebo_rows: list[dict[str, Any]] = []
    for sample in SAMPLE_WINDOWS:
        sample_events = _sample_events(events, sample)
        simulated = placebo_skew_reversal(
            sample_events,
            assets=CORE8,
            horizon=7,
            iterations=args.placebo_iterations,
        )
        actual = float(sample_events["spread_7d"].mean())
        placebo_rows.append(
            {
                "sample": sample,
                "actual_mean": actual,
                "placebo_mean": float(simulated.mean()) if not simulated.empty else float("nan"),
                "placebo_p95": float(simulated.quantile(0.95)) if not simulated.empty else float("nan"),
                "placebo_p_value": float((simulated >= actual).mean()) if not simulated.empty else float("nan"),
            }
        )
    placebo = pd.DataFrame(placebo_rows)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    events.to_csv(output_dir / "events.csv", index=False)
    compact.to_csv(output_dir / "screen_summary.csv", index=False)
    detail.to_csv(output_dir / "cost_detail.csv", index=False)
    placebo.to_csv(output_dir / "placebo_summary.csv", index=False)
    manifest = {
        "screen_id": SCREEN_ID,
        "universe": list(CORE8),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "lookback_days": 30,
        "rebalance_days": 7,
        "horizon_days": 7,
        "placebo_iterations": args.placebo_iterations,
        "orders_sent": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        _report(compact, placebo, events), encoding="utf-8"
    )
    print(compact.to_string(index=False))
    print(f"wrote {output_dir}; events={len(events)}")


if __name__ == "__main__":
    main()
