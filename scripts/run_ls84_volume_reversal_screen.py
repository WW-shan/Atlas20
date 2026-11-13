"""Pre-registered core8 high-volume overreaction reversal screen."""

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
from scripts.run_ls83_funding_settlement_screen import newey_west_t  # noqa: E402

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
SCREEN_ID = "PR2026-11-LS84-CORE8-VOLUME-REVERSAL-SCREEN"
SAMPLE_WINDOWS = {
    "full": ("2022-01-01", "2026-09-20"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-20"),
}


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _normalise_hourly_index(index: pd.Index) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([_as_utc(value) for value in index]).round("h")


def build_volume_reversal_events(
    *,
    hourly_prices: pd.DataFrame,
    daily_close: pd.DataFrame,
    daily_volume: pd.DataFrame,
    assets: Sequence[str],
    horizons: Sequence[int] = (24, 72),
    lookback_days: int = 20,
    high_volume_count: int = 4,
    entry_hour: int = 3,
) -> pd.DataFrame:
    """Build daily high-volume reversal events with exact T+1 entry/exit."""
    if lookback_days < 2:
        raise ValueError("lookback_days must be at least two")
    if high_volume_count < 4 or high_volume_count > len(assets):
        raise ValueError("high_volume_count must be between four and the universe size")
    if not horizons or any(int(horizon) <= 0 for horizon in horizons):
        raise ValueError("horizons must contain positive integers")
    if entry_hour < 0 or entry_hour > 23:
        raise ValueError("entry_hour must be in [0, 23]")
    assets = tuple(str(asset) for asset in assets)
    for name, frame in (
        ("hourly_prices", hourly_prices),
        ("daily_close", daily_close),
        ("daily_volume", daily_volume),
    ):
        missing = set(assets).difference(frame.columns)
        if missing:
            raise ValueError(f"{name} missing columns: {sorted(missing)}")
    prices = hourly_prices.loc[:, list(assets)].apply(pd.to_numeric, errors="coerce").sort_index()
    close = daily_close.loc[:, list(assets)].apply(pd.to_numeric, errors="coerce").sort_index()
    volume = daily_volume.loc[:, list(assets)].apply(pd.to_numeric, errors="coerce").sort_index()
    close.index = pd.DatetimeIndex([_as_utc(value).normalize() for value in close.index])
    volume.index = pd.DatetimeIndex([_as_utc(value).normalize() for value in volume.index])
    close = close[~close.index.duplicated(keep="last")].sort_index()
    volume = volume[~volume.index.duplicated(keep="last")].sort_index()
    common_days = close.index.intersection(volume.index).sort_values()
    rows: list[dict[str, Any]] = []
    for position in range(lookback_days, len(common_days)):
        signal_day = pd.Timestamp(common_days[position])
        previous_day = pd.Timestamp(common_days[position - 1])
        history_days = common_days[position - lookback_days : position]
        if len(history_days) < lookback_days:
            continue
        if signal_day not in close.index or previous_day not in close.index:
            continue
        returns = close.loc[signal_day] / close.loc[previous_day] - 1.0
        if returns.isna().any():
            continue
        median_volume = volume.loc[history_days].median(axis=0, skipna=True)
        current_volume = volume.loc[signal_day]
        if (median_volume <= 0.0).any() or current_volume.isna().any():
            continue
        surprise = np.log(current_volume / median_volume)
        if not np.isfinite(surprise.to_numpy(dtype=float)).all():
            continue
        ranked_volume = sorted(surprise.items(), key=lambda item: (-float(item[1]), str(item[0])))
        high_volume_assets = [str(asset) for asset, _ in ranked_volume[:high_volume_count]]
        entry_time = signal_day + pd.Timedelta(days=1, hours=entry_hour)
        if entry_time not in prices.index or prices.loc[entry_time].isna().any():
            continue
        exits = {
            int(horizon): entry_time + pd.Timedelta(hours=int(horizon))
            for horizon in horizons
        }
        if any(exit_time not in prices.index for exit_time in exits.values()):
            continue
        if any(prices.loc[exit_time].isna().any() for exit_time in exits.values()):
            continue
        high_ranked = sorted(
            ((asset, float(returns.loc[asset])) for asset in high_volume_assets),
            key=lambda item: (item[1], item[0]),
        )
        long_assets = [asset for asset, _ in high_ranked[:2]]
        short_assets = [asset for asset, _ in high_ranked[-2:]]
        entry_prices = prices.loc[entry_time]
        row: dict[str, Any] = {
            "signal_date": signal_day,
            "entry_time": entry_time,
            "high_volume_assets": ",".join(high_volume_assets),
            "long_assets": ",".join(long_assets),
            "short_assets": ",".join(short_assets),
            "return_24h_long": float(returns.loc[long_assets].mean()),
            "return_24h_short": float(returns.loc[short_assets].mean()),
        }
        for horizon, exit_time in exits.items():
            returns_forward = prices.loc[exit_time] / entry_prices - 1.0
            long_return = float(returns_forward.loc[long_assets].mean())
            short_return = float(returns_forward.loc[short_assets].mean())
            row[f"exit_{horizon}h"] = exit_time
            row[f"long_return_{horizon}h"] = long_return
            row[f"short_return_{horizon}h"] = short_return
            row[f"spread_{horizon}h"] = long_return - short_return
            for asset in assets:
                row[f"ret_{asset}_{horizon}h"] = float(returns_forward.loc[asset])
        rows.append(row)
    return pd.DataFrame(rows)


def placebo_volume_reversal(
    events: pd.DataFrame,
    *,
    assets: Sequence[str],
    horizon: int,
    iterations: int = 2000,
    seed: int = 20261113,
) -> pd.Series:
    """Randomize the two long/two short choices inside each high-volume group."""
    if iterations < 1:
        raise ValueError("iterations must be positive")
    rng = np.random.default_rng(seed)
    simulated = np.empty(int(iterations), dtype=float)
    return_columns = {asset: f"ret_{asset}_{horizon}h" for asset in assets}
    for iteration in range(int(iterations)):
        spreads: list[float] = []
        for record in events.to_dict("records"):
            group = str(record["high_volume_assets"]).split(",")
            if len(group) < 4:
                continue
            choice = rng.choice(len(group), size=4, replace=False)
            long_assets = [group[index] for index in choice[:2]]
            short_assets = [group[index] for index in choice[2:]]
            long_return = float(np.mean([record[return_columns[asset]] for asset in long_assets]))
            short_return = float(np.mean([record[return_columns[asset]] for asset in short_assets]))
            spreads.append(long_return - short_return)
        simulated[iteration] = float(np.mean(spreads)) if spreads else float("nan")
    return pd.Series(simulated, name=f"placebo_spread_{horizon}h")


def _sample_events(events: pd.DataFrame, sample: str) -> pd.DataFrame:
    start, end = SAMPLE_WINDOWS[sample]
    return events.loc[
        (events["signal_date"] >= pd.Timestamp(start, tz="UTC"))
        & (events["signal_date"] <= pd.Timestamp(end, tz="UTC"))
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
    net = series - 2.0 * float(cost_bps) / 10_000.0
    net_curve = (1.0 + net).cumprod()
    return {
        "n": float(len(series)),
        "gross_mean": float(series.mean()),
        "net_mean": float(net.mean()),
        "annualized_net_mean": float(net.mean() * 365.0),
        "cumulative": float(net_curve.iloc[-1] - 1.0),
        "max_drawdown": float((net_curve / net_curve.cummax() - 1.0).min()),
        "t_stat": newey_west_t(series, lags=max(1, int(np.ceil(horizon / 24.0)))),
        "hit_rate": float((series > 0.0).mean()),
    }


def _load_market_data(
    market_dir: Path,
    *,
    symbol_map: pd.DataFrame,
    assets: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mapping = symbol_map.set_index("coin_id")
    closes: dict[str, pd.Series] = {}
    volumes: dict[str, pd.Series] = {}
    for asset in assets:
        symbol = str(mapping.loc[asset, "bitget_symbol"])
        path = market_dir / "candles" / f"{symbol}_market.csv"
        frame = pd.read_csv(path)
        if frame.empty or not {"open_time", "close", "quote_volume"}.issubset(frame.columns):
            raise ValueError(f"invalid market candle file: {path}")
        index = _normalise_hourly_index(pd.to_datetime(frame["open_time"], utc=True))
        close = pd.Series(
            pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float),
            index=index,
            name=asset,
        )
        volume = pd.Series(
            pd.to_numeric(frame["quote_volume"], errors="coerce").to_numpy(dtype=float),
            index=index,
            name=asset,
        )
        close = close[~close.index.duplicated(keep="last")].dropna().sort_index()
        volume = volume[~volume.index.duplicated(keep="last")].dropna().sort_index()
        closes[asset] = close
        volumes[asset] = volume
    hourly = pd.DataFrame(closes).sort_index()
    daily_close = hourly.resample("1D").last()
    daily_volume = pd.DataFrame(volumes).sort_index().resample("1D").sum(min_count=1)
    return hourly, daily_close, daily_volume


def _report(summary: pd.DataFrame, placebo: pd.DataFrame, events: pd.DataFrame) -> str:
    lines = [
        f"# {SCREEN_ID}",
        "",
        "- Fixed core8 universe; high-volume group = top 4 by 20D volume surprise",
        "- Signal = completed UTC daily return; entry = D+1 03:00 UTC market close",
        "- Long two lowest returns / short two highest returns inside the high-volume group",
        "",
        "## Screen results",
        "",
        dataframe_to_markdown(summary.reset_index(drop=True)),
        "",
        "## Placebo",
        "",
        dataframe_to_markdown(placebo.reset_index(drop=True)),
        "",
        "## Coverage",
        "",
        f"- Events retained: {len(events)}",
        f"- First event: {events['signal_date'].min() if not events.empty else 'none'}",
        f"- Last event: {events['signal_date'].max() if not events.empty else 'none'}",
        "",
        "## Decision",
        "",
    ]
    validation = summary.loc[
        (summary["sample"] == "validation") & (summary["horizon_hours"] == 24)
    ]
    discovery = summary.loc[
        (summary["sample"] == "discovery") & (summary["horizon_hours"] == 24)
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
            f"24h validation net mean at 50bps: {val['net_mean_50bps']:.6%}; "
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
    parser.add_argument("--placebo-iterations", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    start = pd.Timestamp(args.start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    if start >= end:
        parser.error("start-date must precede end-date")
    symbol_map = pd.read_csv(args.market_dir / "symbol_map.csv")
    hourly, daily_close, daily_volume = _load_market_data(
        args.market_dir,
        symbol_map=symbol_map,
        assets=CORE8,
    )
    events = build_volume_reversal_events(
        hourly_prices=hourly,
        daily_close=daily_close,
        daily_volume=daily_volume,
        assets=CORE8,
        horizons=(24, 72),
    )
    events = events.loc[
        (events["signal_date"] >= start) & (events["signal_date"] < end)
    ].copy()
    if events.empty:
        raise SystemExit("no complete volume-reversal events in the requested window")
    rows: list[dict[str, Any]] = []
    for sample in SAMPLE_WINDOWS:
        sample_events = _sample_events(events, sample)
        for horizon in (24, 72):
            for cost in (20.0, 50.0, 100.0):
                rows.append(
                    {
                        "sample": sample,
                        "horizon_hours": horizon,
                        "cost_bps": cost,
                        **_metrics(sample_events[f"spread_{horizon}h"], cost_bps=cost, horizon=horizon),
                    }
                )
    detail = pd.DataFrame(rows)
    compact_rows: list[dict[str, Any]] = []
    for sample in SAMPLE_WINDOWS:
        for horizon in (24, 72):
            subset = detail.loc[
                (detail["sample"] == sample) & (detail["horizon_hours"] == horizon)
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
        for horizon in (24, 72):
            simulated = placebo_volume_reversal(
                sample_events,
                assets=CORE8,
                horizon=horizon,
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
    detail.to_csv(output_dir / "cost_detail.csv", index=False)
    placebo.to_csv(output_dir / "placebo_summary.csv", index=False)
    manifest = {
        "screen_id": SCREEN_ID,
        "universe": list(CORE8),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "entry_hour_utc": 3,
        "lookback_days": 20,
        "high_volume_count": 4,
        "horizons_hours": [24, 72],
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
