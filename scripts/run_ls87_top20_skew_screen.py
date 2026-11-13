"""Pre-registered PIT Top20 realized-skew event screen."""

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

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.diagnose_top20_membership_events import membership_matrix  # noqa: E402
from scripts.run_ls83_funding_settlement_screen import newey_west_t  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402

SCREEN_ID = "PR2026-11-LS87-PIT-TOP20-REALIZED-SKEW-SCREEN"
SAMPLE_WINDOWS = {
    "full": ("2022-01-01", "2026-09-20"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-20"),
}


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def build_pit_top20_skew_events(
    *,
    price: pd.DataFrame,
    present: pd.DataFrame,
    hourly_prices: pd.DataFrame,
    assets: Sequence[str],
    rebalance_days: int = 7,
    lookback_days: int = 30,
    horizon_days: int = 7,
    entry_hour: int = 3,
    min_assets: int = 6,
) -> pd.DataFrame:
    """Build weekly skew events using PIT membership and exact Bitget fills."""
    if rebalance_days < 1:
        raise ValueError("rebalance_days must be positive")
    if lookback_days < 3:
        raise ValueError("lookback_days must be at least three")
    if horizon_days < 1:
        raise ValueError("horizon_days must be positive")
    if min_assets < 2:
        raise ValueError("min_assets must be at least two")
    assets = tuple(str(asset) for asset in assets)
    price_frame = price.copy()
    price_frame.index = pd.DatetimeIndex([_as_utc(value).normalize() for value in price_frame.index])
    price_frame = price_frame[~price_frame.index.duplicated(keep="last")].sort_index()
    present_frame = present.copy()
    present_frame.index = pd.DatetimeIndex(
        [_as_utc(value).normalize() for value in present_frame.index]
    )
    present_frame = present_frame.reindex(price_frame.index).fillna(False).astype(bool)
    price_frame = price_frame.loc[:, [asset for asset in assets if asset in price_frame.columns]]
    skew = price_frame.pct_change(fill_method=None).rolling(
        lookback_days, min_periods=lookback_days
    ).skew()
    hourly = hourly_prices.sort_index()
    anchor = pd.Timestamp(price_frame.index[0]).normalize()
    rows: list[dict[str, Any]] = []
    for signal_date in price_frame.index:
        if (signal_date - anchor).days % rebalance_days:
            continue
        if signal_date not in skew.index or skew.loc[signal_date].isna().all():
            continue
        entry_time = signal_date + pd.Timedelta(days=1, hours=entry_hour)
        exit_time = entry_time + pd.Timedelta(days=horizon_days)
        if entry_time not in hourly.index or exit_time not in hourly.index:
            continue
        eligible: list[str] = []
        scores: dict[str, float] = {}
        for asset in assets:
            if asset not in price_frame.columns or asset not in hourly.columns:
                continue
            if asset not in present_frame.columns or not bool(present_frame.at[signal_date, asset]):
                continue
            score = skew.at[signal_date, asset]
            if not np.isfinite(float(score)):
                continue
            if not np.isfinite(float(hourly.at[entry_time, asset])) or not np.isfinite(
                float(hourly.at[exit_time, asset])
            ):
                continue
            eligible.append(asset)
            scores[asset] = float(score)
        if len(eligible) < min_assets:
            continue
        ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]))
        long_assets = [asset for asset, _ in ranked[:2]]
        short_assets = [asset for asset, _ in ranked[-2:]]
        forward_returns = hourly.loc[exit_time] / hourly.loc[entry_time] - 1.0
        long_return = float(forward_returns.loc[long_assets].mean())
        short_return = float(forward_returns.loc[short_assets].mean())
        row: dict[str, Any] = {
            "signal_date": signal_date,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "eligible_assets": ",".join(sorted(eligible)),
            "eligible_count": len(eligible),
            "long_assets": ",".join(long_assets),
            "short_assets": ",".join(short_assets),
            "long_return_7d": long_return,
            "short_return_7d": short_return,
            "spread_7d": long_return - short_return,
        }
        for asset in assets:
            if asset in scores:
                row[f"skew_{asset}"] = scores[asset]
                row[f"ret_{asset}_7d"] = float(forward_returns.loc[asset])
        rows.append(row)
    return pd.DataFrame(rows)


def placebo_pit_top20_skew(
    events: pd.DataFrame,
    *,
    assets: Sequence[str],
    horizon: int = 7,
    iterations: int = 2000,
    seed: int = 20261113,
) -> pd.Series:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    rng = np.random.default_rng(seed)
    simulated = np.empty(int(iterations), dtype=float)
    for iteration in range(int(iterations)):
        spreads: list[float] = []
        for record in events.to_dict("records"):
            eligible = str(record["eligible_assets"]).split(",")
            if len(eligible) < 4:
                continue
            choice = rng.choice(len(eligible), size=4, replace=False)
            long_assets = [eligible[index] for index in choice[:2]]
            short_assets = [eligible[index] for index in choice[2:]]
            long_return = float(
                np.mean([record[f"ret_{asset}_{horizon}d"] for asset in long_assets])
            )
            short_return = float(
                np.mean([record[f"ret_{asset}_{horizon}d"] for asset in short_assets])
            )
            spreads.append(long_return - short_return)
        simulated[iteration] = float(np.mean(spreads)) if spreads else float("nan")
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


def _load_bitget_hourly(
    market_dir: Path,
    *,
    symbol_map: pd.DataFrame,
    coins: Sequence[str],
) -> pd.DataFrame:
    candles = load_mark_candles(
        market_dir,
        symbol_map,
        coins=coins,
        candle_type="market",
    )
    series = {
        asset: frame["close"].astype(float) for asset, frame in candles.items() if "close" in frame
    }
    return pd.DataFrame(series).sort_index()


def _report(summary: pd.DataFrame, placebo: pd.DataFrame, events: pd.DataFrame) -> str:
    lines = [
        f"# {SCREEN_ID}",
        "",
        "- PIT CMC Top20 membership; Bitget market candle required for execution",
        "- 30D daily-return realized skew; long two lowest, short two highest",
        "- Weekly 7D hold; entry D+1 03:00 UTC; exit +7D",
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
        f"- Events: {len(events)}",
        f"- Median eligible assets: {events['eligible_count'].median() if not events.empty else 'none'}",
        "",
        "## Decision",
        "",
    ]
    validation = summary.loc[summary["sample"] == "validation"]
    discovery = summary.loc[summary["sample"] == "discovery"]
    if validation.empty or discovery.empty:
        lines.append("Insufficient validation/discovery events; screen incomplete.")
    else:
        val = validation.iloc[0]
        disc = discovery.iloc[0]
        passed = (
            val["net_mean_50bps"] > 0.0
            and val["t_stat"] >= 2.0
            and np.sign(val["net_mean_50bps"]) == np.sign(disc["net_mean_50bps"])
            and val["n"] >= 150
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
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--warmup-start", default="2021-01-01")
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
    _, market, universe, _ = _load_market(
        args.config,
        start_date=args.warmup_start,
        end_date=args.end_date,
    )
    index = pd.DatetimeIndex([_as_utc(value).normalize() for value in market.price.index])
    price = market.price.copy()
    price.index = index
    present = membership_matrix(universe, index=index)
    symbol_map = pd.read_csv(args.market_dir / "symbol_map.csv")
    hourly = _load_bitget_hourly(
        args.market_dir,
        symbol_map=symbol_map,
        coins=list(price.columns),
    )
    events = build_pit_top20_skew_events(
        price=price,
        present=present,
        hourly_prices=hourly,
        assets=list(price.columns),
    )
    events = events.loc[(events["signal_date"] >= start) & (events["signal_date"] < end)].copy()
    if events.empty:
        raise SystemExit("no complete PIT Top20 skew events in the requested window")
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
        simulated = placebo_pit_top20_skew(
            sample_events,
            assets=list(price.columns),
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
        "start_date": args.start_date,
        "end_date": args.end_date,
        "universe": "PIT CMC Top20",
        "signal_source": "CMC daily price",
        "execution_source": "Bitget market candle",
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
