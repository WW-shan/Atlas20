"""How much do venues differ in funding? Measured, per year, on real history.

The Bitget funding history only reaches ~90 days, so the 2022+ funding cost in
the derivatives backtest comes from a Binance proxy.  Bybit publishes funding
all the way back, which lets the *size and stability of a venue premium* be
measured instead of assumed: if a competitor venue tracks Binance closely for
five years, a measured Bitget premium is more likely to be a stable venue
effect than a one-off artefact of the 90-day window.

The comparison is sum-of-funding-rates per calendar year (the total cost a
long pays), computed per coin and then summarised across coins.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402


def _load_binance(path: Path) -> pd.Series | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or not {"calc_time", "last_funding_rate"}.issubset(frame.columns):
        return None
    index = pd.to_datetime(pd.to_numeric(frame["calc_time"], errors="coerce"), unit="ms", utc=True)
    values = pd.to_numeric(frame["last_funding_rate"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index).dropna()
    return series[~series.index.duplicated(keep="last")].sort_index()


def _load_generic(path: Path, time_column: str, rate_column: str) -> pd.Series | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or not {time_column, rate_column}.issubset(frame.columns):
        return None
    index = pd.to_datetime(frame[time_column], utc=True, errors="coerce")
    values = pd.to_numeric(frame[rate_column], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index).dropna()
    return series[~series.index.duplicated(keep="last")].sort_index()


def _ratio_table(
    coins: list[str],
    venues: dict[str, dict[str, pd.Series]],
    baseline: str,
    *,
    yearly: bool,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for name, series_map in venues.items():
        if name == baseline:
            continue
        for coin in coins:
            other = series_map.get(coin)
            base = venues[baseline].get(coin)
            if other is None or base is None:
                continue
            if yearly:
                years = sorted({int(stamp.year) for stamp in base.index})
                for year in years:
                    o = other[other.index.year == year]
                    b = base[base.index.year == year]
                    if len(o) < 20 or len(b) < 20:
                        continue
                    rows.append(
                        {
                            "venue": name,
                            "coin_id": coin,
                            "period": str(year),
                            "venue_sum": float(o.sum()),
                            "baseline_sum": float(b.sum()),
                            "sum_ratio": float(o.sum() / b.sum()) if b.sum() else np.nan,
                        }
                    )
            else:
                rows.append(
                    {
                        "venue": name,
                        "coin_id": coin,
                        "period": "full",
                        "venue_sum": float(other.sum()),
                        "baseline_sum": float(base.sum()),
                        "sum_ratio": float(other.sum() / base.sum()) if base.sum() else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--symbol-map", type=Path, default=Path("data/raw/bitget_derivatives/symbol_map.csv"))
    parser.add_argument("--binance-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--bybit-dir", type=Path, default=Path("data/raw/alternative_funding/bybit"))
    parser.add_argument("--bitget-dir", type=Path, default=Path("data/raw/bitget_derivatives/funding_recent_20261009/funding"))
    parser.add_argument("--bitget-start", default="2026-07-11")
    parser.add_argument("--bitget-end", default="2026-10-10")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/derivatives_track_funding_venue_premia"))
    args = parser.parse_args()

    symbol_map = pd.read_csv(args.symbol_map)
    coins = [str(item) for item in symbol_map["coin_id"].dropna().unique()]
    venues: dict[str, dict[str, pd.Series]] = {"binance": {}, "bybit": {}, "bitget": {}}
    for coin in coins:
        binance = _load_binance(args.binance_dir / f"{coin}.csv")
        if binance is not None:
            venues["binance"][coin] = binance
        bybit = _load_generic(args.bybit_dir / f"{coin}.csv", "funding_time", "funding_rate")
        if bybit is not None:
            venues["bybit"][coin] = bybit[bybit.index >= pd.Timestamp("2022-01-01", tz="UTC")]
        bitget = _load_generic(args.bitget_dir / f"{coin}.csv", "funding_time", "funding_rate")
        if bitget is not None:
            start = pd.Timestamp(args.bitget_start, tz="UTC")
            end = pd.Timestamp(args.bitget_end, tz="UTC")
            venues["bitget"][coin] = bitget[(bitget.index >= start) & (bitget.index < end)]

    common = sorted(set(venues["binance"]) & set(venues["bybit"]))
    if not common:
        raise SystemExit("no coin has both Binance and Bybit funding history")

    for name in ("bybit", "bitget"):
        for coin in common:
            base = venues["binance"][coin]
            other = venues[name].get(coin)
            if other is not None:
                pass

    yearly = _ratio_table(common, venues, "binance", yearly=True)
    bybit_yearly = yearly[yearly["venue"] == "bybit"]
    per_year = (
        bybit_yearly.groupby("period")["sum_ratio"]
        .agg(coins="size", median="median", p10=lambda s: s.quantile(0.10), p90=lambda s: s.quantile(0.90))
        .reset_index()
    )

    # Bitget only exists for the recent window: compare it with Bybit on the
    # same window so venue-vs-venue differences are measured like for like.
    start = pd.Timestamp(args.bitget_start, tz="UTC")
    end = pd.Timestamp(args.bitget_end, tz="UTC")
    window_rows: list[dict[str, object]] = []
    for coin in sorted(set(venues["bitget"]) & set(venues["binance"])):
        base = venues["binance"][coin]
        bybit = venues["bybit"].get(coin)
        bitget = venues["bitget"][coin]
        base_window = base[(base.index >= start) & (base.index < end)]
        if len(base_window) < 20 or len(bitget) < 20:
            continue
        row = {
            "coin_id": coin,
            "bitget_sum": float(bitget.sum()),
            "binance_sum": float(base_window.sum()),
            "bitget_over_binance": float(bitget.sum() / base_window.sum()) if base_window.sum() else np.nan,
        }
        if bybit is not None:
            bybit_window = bybit[(bybit.index >= start) & (bybit.index < end)]
            if len(bybit_window) >= 20:
                row["bybit_sum"] = float(bybit_window.sum())
                row["bybit_over_binance"] = (
                    float(bybit_window.sum() / base_window.sum()) if base_window.sum() else np.nan
                )
        window_rows.append(row)
    window = pd.DataFrame(window_rows)

    output_dir = ensure_dir(args.output_dir)
    per_year.to_csv(output_dir / "bybit_vs_binance_by_year.csv", index=False)
    bybit_yearly.to_csv(output_dir / "bybit_vs_binance_per_coin_year.csv", index=False)
    window.to_csv(output_dir / "recent_window_premia.csv", index=False)
    summary = {
        "coins_binance_and_bybit": len(common),
        "bybit_median_ratio_by_year": {
            str(row["period"]): float(row["median"]) for _, row in per_year.iterrows()
        },
        "recent_window_days": int((end - start).days),
        "recent_bitget_over_binance_median": float(window["bitget_over_binance"].median()) if not window.empty else None,
        "recent_bybit_over_binance_median": (
            float(window["bybit_over_binance"].median()) if "bybit_over_binance" in window else None
        ),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    lines = [
        "# Funding venue premia (Bybit and Bitget against Binance)",
        "",
        f"- coins with both Binance and Bybit history: {len(common)}",
        "- ratio = total funding paid over the period on that venue / the same on Binance",
        "",
        "## Bybit vs Binance by calendar year",
        "",
        dataframe_to_markdown(per_year),
        "",
        f"## Recent window ({start.date()} → {end.date()})",
        "",
        dataframe_to_markdown(window.sort_values("bitget_over_binance")),
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print(f"Wrote funding venue premia to {output_dir}")


if __name__ == "__main__":
    main()
