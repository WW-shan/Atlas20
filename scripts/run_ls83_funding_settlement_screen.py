"""Pre-registered core8 funding-settlement event screen.

This is a screen, not an order router or a portfolio backtest.  It measures
whether the cross-section of funding rates at the 00:00 UTC settlement has
short-horizon predictive value after realistic Bitget market-close execution.
"""

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

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

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
SCREEN_ID = "PR2026-11-LS83-CORE8-FUNDING-SETTLEMENT-SCREEN"
SAMPLE_WINDOWS = {
    "full": ("2022-01-01", "2026-09-20"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-20"),
}


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _normalise_hourly_index(index: pd.Index) -> pd.DatetimeIndex:
    stamps = pd.DatetimeIndex([_as_utc(value) for value in index])
    return stamps.round("h")


def _normalise_funding(funding: pd.DataFrame) -> pd.DataFrame:
    normalized = funding.copy()
    normalized.index = _normalise_hourly_index(normalized.index)
    normalized = normalized[~normalized.index.duplicated(keep="last")].sort_index()
    return normalized.apply(pd.to_numeric, errors="coerce")


def build_settlement_events(
    *,
    prices: pd.DataFrame,
    funding: pd.DataFrame,
    assets: Sequence[str],
    horizons: Sequence[int],
    settlement_hour: int = 0,
    entry_delay_hours: int = 1,
) -> pd.DataFrame:
    """Build one row per non-missing 00:00 settlement event.

    The signal is the funding rate at the event timestamp.  Entry is delayed by
    ``entry_delay_hours``; every requested exit must have an exact hourly close
    for every asset, otherwise the event is skipped and counted by the caller.
    """
    if settlement_hour < 0 or settlement_hour > 23:
        raise ValueError("settlement_hour must be in [0, 23]")
    if entry_delay_hours < 1:
        raise ValueError("entry_delay_hours must be positive")
    if not horizons or any(int(horizon) <= 0 for horizon in horizons):
        raise ValueError("horizons must contain positive integers")
    assets = tuple(str(asset) for asset in assets)
    missing = set(assets).difference(prices.columns).union(set(assets).difference(funding.columns))
    if missing:
        raise ValueError(f"missing price/funding columns: {sorted(missing)}")

    price_frame = prices.loc[:, list(assets)].apply(pd.to_numeric, errors="coerce").sort_index()
    funding_frame = _normalise_funding(funding)
    event_index = funding_frame.index[
        (funding_frame.index.hour == settlement_hour)
        & (funding_frame.index.minute == 0)
        & (funding_frame.index.second == 0)
    ]
    rows: list[dict[str, Any]] = []
    for event_time in event_index:
        if event_time not in funding_frame.index:
            continue
        rates = pd.to_numeric(funding_frame.loc[event_time, list(assets)], errors="coerce")
        if rates.isna().any():
            continue
        entry_time = event_time + pd.Timedelta(hours=entry_delay_hours)
        if entry_time not in price_frame.index or price_frame.loc[entry_time].isna().any():
            continue
        exits = {int(h): entry_time + pd.Timedelta(hours=int(h)) for h in horizons}
        if any(exit_time not in price_frame.index for exit_time in exits.values()):
            continue
        if any(price_frame.loc[exit_time].isna().any() for exit_time in exits.values()):
            continue

        ranked = sorted(rates.items(), key=lambda item: (float(item[1]), str(item[0])))
        long_assets = [str(asset) for asset, _ in ranked[:2]]
        short_assets = [str(asset) for asset, _ in ranked[-2:]]
        entry_prices = price_frame.loc[entry_time]
        row: dict[str, Any] = {
            "event_time": event_time,
            "entry_time": entry_time,
            "long_assets": ",".join(long_assets),
            "short_assets": ",".join(short_assets),
        }
        for horizon, exit_time in exits.items():
            exit_prices = price_frame.loc[exit_time]
            returns = exit_prices / entry_prices - 1.0
            long_return = float(returns.loc[long_assets].mean())
            short_return = float(returns.loc[short_assets].mean())
            spread = long_return - short_return
            row[f"exit_{horizon}h"] = exit_time
            row[f"long_return_{horizon}h"] = long_return
            row[f"short_return_{horizon}h"] = short_return
            row[f"spread_{horizon}h"] = spread
            for asset in assets:
                row[f"ret_{asset}_{horizon}h"] = float(returns.loc[asset])
        rows.append(row)
    return pd.DataFrame(rows)


def newey_west_t(values: pd.Series | Sequence[float], *, lags: int = 3) -> float:
    """Newey-West t-stat for a mean, with a finite small-sample guard."""
    series = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(series) < 2:
        return 0.0
    array = series.to_numpy(dtype=float)
    centered = array - array.mean()
    gamma0 = float(np.dot(centered, centered) / len(array))
    variance = gamma0
    for lag in range(1, min(int(lags), len(array) - 1) + 1):
        covariance = float(np.dot(centered[lag:], centered[:-lag]) / len(array))
        variance += 2.0 * (1.0 - lag / (lags + 1.0)) * covariance
    if not np.isfinite(variance) or variance <= 0.0:
        return 0.0
    return float(array.mean() / np.sqrt(variance / len(array)))


def _sample_events(events: pd.DataFrame, sample: str) -> pd.DataFrame:
    start, end = SAMPLE_WINDOWS[sample]
    return events.loc[
        (events["event_time"] >= pd.Timestamp(start, tz="UTC"))
        & (events["event_time"] <= pd.Timestamp(end, tz="UTC"))
    ].copy()


def _metrics(values: pd.Series, *, cost_bps: float, horizon: int) -> dict[str, float]:
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
    gross_mean = float(series.mean())
    net = series - 2.0 * float(cost_bps) / 10_000.0
    cumulative = float((1.0 + net).prod() - 1.0)
    drawdown = (1.0 + net).cumprod() / (1.0 + net).cumprod().cummax() - 1.0
    return {
        "n": float(len(series)),
        "gross_mean": gross_mean,
        "net_mean": float(net.mean()),
        "annualized_net_mean": float(net.mean() * 365.0),
        "cumulative": cumulative,
        "max_drawdown": float(drawdown.min()),
        "t_stat": newey_west_t(series, lags=max(1, int(np.ceil(horizon / 8.0)))),
        "hit_rate": float((series > 0.0).mean()),
    }


def placebo_spread(
    events: pd.DataFrame,
    *,
    horizon: int,
    assets: Sequence[str],
    iterations: int = 2000,
    seed: int = 20261113,
) -> pd.Series:
    """Randomly reassign the two long/two short ranks within each event."""
    if iterations < 1:
        raise ValueError("iterations must be positive")
    rng = np.random.default_rng(seed)
    returns = events[[f"ret_{asset}_{horizon}h" for asset in assets]].to_numpy(dtype=float)
    if len(returns) == 0:
        return pd.Series(dtype=float)
    simulated = np.empty(int(iterations), dtype=float)
    for iteration in range(int(iterations)):
        spreads = np.empty(len(returns), dtype=float)
        for event_index, event_returns in enumerate(returns):
            choice = rng.choice(len(assets), size=4, replace=False)
            spreads[event_index] = event_returns[choice[:2]].mean() - event_returns[choice[2:]].mean()
        simulated[iteration] = spreads.mean()
    return pd.Series(simulated, name=f"placebo_spread_{horizon}h")


def _load_market_prices(
    market_dir: Path,
    *,
    symbol_map: pd.DataFrame,
    assets: Sequence[str],
) -> pd.DataFrame:
    mapping = symbol_map.set_index("coin_id")
    series: dict[str, pd.Series] = {}
    for asset in assets:
        if asset not in mapping.index:
            raise ValueError(f"missing symbol-map row for {asset}")
        symbol = str(mapping.loc[asset, "bitget_symbol"])
        path = market_dir / "candles" / f"{symbol}_market.csv"
        frame = pd.read_csv(path)
        if frame.empty or not {"open_time", "close"}.issubset(frame.columns):
            raise ValueError(f"invalid market candle file: {path}")
        index = _normalise_hourly_index(pd.to_datetime(frame["open_time"], utc=True))
        values = pd.Series(
            pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float),
            index=index,
            name=asset,
        )
        values = values[~values.index.duplicated(keep="last")].dropna().sort_index()
        series[asset] = values
    return pd.DataFrame(series).sort_index()


def _load_funding(funding_dir: Path, *, assets: Sequence[str]) -> pd.DataFrame:
    series: dict[str, pd.Series] = {}
    for asset in assets:
        path = funding_dir / f"{asset}.csv"
        frame = pd.read_csv(path)
        if frame.empty or not {"calc_time", "last_funding_rate"}.issubset(frame.columns):
            raise ValueError(f"invalid funding file: {path}")
        index = pd.to_datetime(
            pd.to_numeric(frame["calc_time"], errors="coerce"),
            unit="ms",
            utc=True,
            errors="coerce",
        )
        values = pd.Series(
            pd.to_numeric(frame["last_funding_rate"], errors="coerce").to_numpy(dtype=float),
            index=index,
            name=asset,
        )
        values = values[~values.index.duplicated(keep="last")].dropna()
        series[asset] = values
    return pd.DataFrame(series).sort_index()


def _report(
    summary: pd.DataFrame,
    placebo: pd.DataFrame,
    events: pd.DataFrame,
) -> str:
    lines = [
        f"# {SCREEN_ID}",
        "",
        "- Fixed core8 universe; daily 00:00 UTC Binance funding settlement",
        "- Entry at event +1h; exits at +9h and +25h using Bitget market closes",
        "- Long two lowest funding, short two highest; no threshold or lookback scan",
        "",
        "## Screen results",
        "",
        dataframe_to_markdown(summary.reset_index(drop=True)),
        "",
        "## Placebo",
        "",
        dataframe_to_markdown(placebo.reset_index(drop=True)),
        "",
        "## Data coverage",
        "",
        f"- Events retained: {len(events)}",
        f"- First event: {events['event_time'].min() if not events.empty else 'none'}",
        f"- Last event: {events['event_time'].max() if not events.empty else 'none'}",
        "",
        "## Decision",
        "",
    ]
    validation = summary.loc[
        (summary["sample"] == "validation") & (summary["horizon_hours"] == 8)
    ]
    discovery = summary.loc[
        (summary["sample"] == "discovery") & (summary["horizon_hours"] == 8)
    ]
    if validation.empty or discovery.empty:
        lines.append("Insufficient validation/discovery events; screen is incomplete.")
    else:
        val = validation.iloc[0]
        disc = discovery.iloc[0]
        passed = (
            val["net_mean_50bps"] > 0.0
            and val["t_stat"] >= 2.0
            and np.sign(val["net_mean_50bps"]) == np.sign(disc["net_mean_50bps"])
        )
        lines.append(
            f"8h validation net mean at 50bps: {val['net_mean_50bps']:.6%}; "
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
    parser.add_argument(
        "--market-dir",
        type=Path,
        default=Path("data/raw/bitget_derivatives/merged_market_20261009"),
    )
    parser.add_argument("--funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--placebo-iterations", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    start = pd.Timestamp(args.start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    if start >= end:
        parser.error("start-date must precede end-date")
    symbol_map = pd.read_csv(args.market_dir / "symbol_map.csv")
    prices = _load_market_prices(args.market_dir, symbol_map=symbol_map, assets=CORE8)
    funding = _load_funding(args.funding_dir, assets=CORE8)
    events = build_settlement_events(
        prices=prices,
        funding=funding,
        assets=CORE8,
        horizons=(8, 24),
        settlement_hour=0,
        entry_delay_hours=1,
    )
    events = events.loc[
        (events["event_time"] >= start) & (events["event_time"] < end)
    ].copy()
    if events.empty:
        raise SystemExit("no complete settlement events in the requested window")

    rows: list[dict[str, Any]] = []
    for sample in SAMPLE_WINDOWS:
        sample_events = _sample_events(events, sample)
        for horizon in (8, 24):
            values = sample_events[f"spread_{horizon}h"]
            for cost in (20.0, 50.0, 100.0):
                metrics = _metrics(values, cost_bps=cost, horizon=horizon)
                rows.append(
                    {
                        "sample": sample,
                        "horizon_hours": horizon,
                        "cost_bps": cost,
                        **metrics,
                    }
                )
    summary = pd.DataFrame(rows)
    summary["net_mean_20bps"] = summary["net_mean"].where(summary["cost_bps"] == 20.0)
    summary["net_mean_50bps"] = summary["net_mean"].where(summary["cost_bps"] == 50.0)
    summary["net_mean_100bps"] = summary["net_mean"].where(summary["cost_bps"] == 100.0)
    # Keep one row per sample/horizon with all cost bands as explicit columns.
    compact_rows: list[dict[str, Any]] = []
    for sample in SAMPLE_WINDOWS:
        for horizon in (8, 24):
            subset = summary.loc[
                (summary["sample"] == sample) & (summary["horizon_hours"] == horizon)
            ].set_index("cost_bps")
            base = subset.loc[20.0]
            compact_rows.append(
                {
                    "sample": sample,
                    "horizon_hours": horizon,
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
        for horizon in (8, 24):
            simulated = placebo_spread(
                sample_events,
                horizon=horizon,
                assets=CORE8,
                iterations=args.placebo_iterations,
            )
            actual = float(sample_events[f"spread_{horizon}h"].mean())
            placebo_rows.append(
                {
                    "sample": sample,
                    "horizon_hours": horizon,
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
    summary.to_csv(output_dir / "cost_detail.csv", index=False)
    placebo.to_csv(output_dir / "placebo_summary.csv", index=False)
    manifest = {
        "screen_id": SCREEN_ID,
        "universe": list(CORE8),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "settlement_hour_utc": 0,
        "entry_delay_hours": 1,
        "horizons_hours": [8, 24],
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
