"""Diagnose maker-first fills for a frozen derivatives trade list.

This is an execution diagnostic, not a new alpha. It never sends orders and
never changes the live executor. The simulation asks whether a passive limit
placed inside the first available bar, followed by a bounded taker fallback,
would have lowered effective cost relative to the frozen 20 bps taker base.

The primary result uses Bitget mark candles, the same venue as the recorded
trades. Binance 30m bars are accepted as a cross-check but are explicitly a
different venue and are not treated as executable quotes.
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

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

DEFAULT_TRADES = (
    "reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/"
    "PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/trades.csv"
)
DEFAULT_RAW_DIR = Path("data/raw/bitget_derivatives/merged_20261009")
DEFAULT_INTRADAY_DIR = Path("data/raw/binance_30m")
DEFAULT_OUTPUT_DIR = Path("reports/derivatives_track_maker_execution_diagnostic")
BAR_COLUMNS = ("open", "high", "low", "close")


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _normalise_bar_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if "open_time" in frame.columns:
        index = pd.DatetimeIndex(pd.to_datetime(frame["open_time"], utc=True))
    else:
        index = pd.DatetimeIndex([_as_utc(value) for value in frame.index])
    result = frame.copy()
    result.index = index
    result = result[~result.index.duplicated(keep="last")].sort_index()
    missing = [column for column in BAR_COLUMNS if column not in result.columns]
    if missing:
        raise ValueError(f"bar frame is missing columns: {missing}")
    for column in BAR_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[list(BAR_COLUMNS)].isna().any().any():
        raise ValueError("bar frame contains non-finite OHLC values")
    return result


def load_bars(
    *,
    bar_source: str,
    raw_dir: Path,
    intraday_dir: Path,
) -> dict[str, pd.DataFrame]:
    if bar_source == "bitget-mark":
        symbol_map = pd.read_csv(raw_dir / "symbol_map.csv")
        raw = load_mark_candles(raw_dir, symbol_map)
        return {asset: _normalise_bar_frame(frame) for asset, frame in raw.items()}
    if bar_source == "binance-30m":
        from scripts.analyze_intraday_execution_timing import load_30m_bars

        raw = load_30m_bars(intraday_dir)
        return {asset: _normalise_bar_frame(frame) for asset, frame in raw.items()}
    raise ValueError("bar_source must be 'bitget-mark' or 'binance-30m'")


def trade_direction(side: object, action: object) -> str:
    """Return the order-book side for a signed derivatives trade."""
    normalized_side = str(side).strip().lower()
    normalized_action = str(action).strip().lower()
    if normalized_side not in {"long", "short"}:
        raise ValueError(f"unknown trade side: {side!r}")
    if normalized_action not in {"open", "close", "increase", "reduce"}:
        raise ValueError(f"unknown trade action: {action!r}")
    if (
        normalized_side == "long"
        and normalized_action in {"open", "increase"}
    ) or (
        normalized_side == "short"
        and normalized_action in {"close", "reduce"}
    ):
        return "buy"
    return "sell"


def _bar_at(frame: pd.DataFrame, timestamp: pd.Timestamp) -> int | None:
    times = pd.DatetimeIndex(frame.index)
    position = int(times.searchsorted(timestamp, side="left"))
    if position >= len(times) or times[position] != timestamp:
        return None
    return position


def simulate_trade(
    trade: Mapping[str, object],
    frame: pd.DataFrame,
    *,
    offset_bps: float,
    timeout_bars: int,
    through_bps: float,
    maker_fee_bps: float,
    taker_fee_bps: float,
    baseline_fee_bps: float,
) -> dict[str, object]:
    """Simulate one passive-first trade against a bar frame."""
    if offset_bps < 0.0 or through_bps < 0.0:
        raise ValueError("offset_bps and through_bps must be non-negative")
    if timeout_bars < 1:
        raise ValueError("timeout_bars must be positive")
    if min(maker_fee_bps, taker_fee_bps, baseline_fee_bps) < 0.0:
        raise ValueError("fee assumptions must be non-negative")
    if pd.isna(trade.get("timestamp")):
        raise ValueError("trade timestamp must be present")
    timestamp = _as_utc(trade["timestamp"])
    position = _bar_at(frame, timestamp)
    if position is None:
        return {
            "available": False,
            "asset": str(trade.get("asset", "")),
            "timestamp": timestamp,
            "side": trade_direction(trade.get("side"), trade.get("action")),
            "notional": float(trade.get("notional", 0.0)),
            "filled": False,
            "effective_cost_bps": np.nan,
            "improvement_bps": np.nan,
        }

    segment = frame.iloc[position : position + int(timeout_bars)]
    if len(segment) < int(timeout_bars):
        return {
            "available": False,
            "asset": str(trade.get("asset", "")),
            "timestamp": timestamp,
            "side": trade_direction(trade.get("side"), trade.get("action")),
            "notional": float(trade.get("notional", 0.0)),
            "filled": False,
            "effective_cost_bps": np.nan,
            "improvement_bps": np.nan,
        }

    direction = trade_direction(trade.get("side"), trade.get("action"))
    reference = float(segment.iloc[0]["open"])
    if reference <= 0.0:
        raise ValueError("bar open must be positive")
    if direction == "buy":
        limit = reference * (1.0 - offset_bps / 10_000.0)
        through = limit * (1.0 - through_bps / 10_000.0)
    else:
        limit = reference * (1.0 + offset_bps / 10_000.0)
        through = limit * (1.0 + through_bps / 10_000.0)

    filled = False
    fill_price = float("nan")
    for _, bar in segment.iterrows():
        if direction == "buy" and float(bar["low"]) <= through:
            filled = True
            fill_price = limit
            break
        if direction == "sell" and float(bar["high"]) >= through:
            filled = True
            fill_price = limit
            break
    if not filled:
        fill_price = float(segment.iloc[-1]["close"])
    fee_bps = maker_fee_bps if filled else taker_fee_bps
    if direction == "buy":
        price_edge_bps = (reference - fill_price) / reference * 10_000.0
    else:
        price_edge_bps = (fill_price - reference) / reference * 10_000.0
    effective_cost_bps = float(fee_bps - price_edge_bps)
    improvement_bps = float(baseline_fee_bps - effective_cost_bps)
    return {
        "available": True,
        "asset": str(trade.get("asset", "")),
        "timestamp": timestamp,
        "side": direction,
        "notional": float(trade.get("notional", 0.0)),
        "reference_price": reference,
        "limit_price": float(limit),
        "fill_price": fill_price,
        "filled": filled,
        "fee_bps": float(fee_bps),
        "price_edge_bps": float(price_edge_bps),
        "effective_cost_bps": effective_cost_bps,
        "improvement_bps": improvement_bps,
    }


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    total = float(weights.sum())
    if total <= 0.0:
        return float("nan")
    return float((values * weights).sum() / total)


def summarise(
    simulation: pd.DataFrame,
    *,
    total_notional: float,
    offset_bps: float,
    timeout_bars: int,
) -> dict[str, float | int]:
    available = simulation.loc[simulation["available"].astype(bool)].copy()
    covered = float(available["notional"].sum())
    if available.empty or covered <= 0.0:
        return {
            "offset_bps": float(offset_bps),
            "timeout_bars": int(timeout_bars),
            "trade_count": 0,
            "covered_notional": 0.0,
            "coverage": 0.0,
            "notional_fill_rate": 0.0,
            "effective_cost_bps": float("nan"),
            "price_edge_bps": float("nan"),
            "improvement_bps": float("nan"),
            "positive_improvement_share": float("nan"),
            "unfilled_notional_share": float("nan"),
            "unfilled_improvement_median_bps": float("nan"),
            "unfilled_improvement_p05_bps": float("nan"),
        }
    weights = available["notional"].astype(float)
    unfilled = available.loc[~available["filled"].astype(bool)]
    unfilled_weights = unfilled["notional"].astype(float)
    return {
        "offset_bps": float(offset_bps),
        "timeout_bars": int(timeout_bars),
        "trade_count": int(len(available)),
        "covered_notional": covered,
        "coverage": covered / float(total_notional) if total_notional > 0.0 else float("nan"),
        "notional_fill_rate": _weighted_mean(
            available["filled"].astype(float), weights
        ),
        "effective_cost_bps": _weighted_mean(
            available["effective_cost_bps"].astype(float), weights
        ),
        "price_edge_bps": _weighted_mean(
            available["price_edge_bps"].astype(float), weights
        ),
        "improvement_bps": _weighted_mean(
            available["improvement_bps"].astype(float), weights
        ),
        "positive_improvement_share": _weighted_mean(
            (available["improvement_bps"].astype(float) > 0.0).astype(float), weights
        ),
        "unfilled_notional_share": (
            float(unfilled_weights.sum() / covered) if covered > 0.0 else float("nan")
        ),
        "unfilled_improvement_median_bps": (
            float(unfilled["improvement_bps"].astype(float).median())
            if not unfilled.empty
            else float("nan")
        ),
        "unfilled_improvement_p05_bps": (
            float(unfilled["improvement_bps"].astype(float).quantile(0.05))
            if not unfilled.empty
            else float("nan")
        ),
    }


def _yearly_breakdown(simulation: pd.DataFrame) -> pd.DataFrame:
    available = simulation.loc[simulation["available"].astype(bool)].copy()
    if available.empty:
        return pd.DataFrame()
    available["year"] = pd.DatetimeIndex(available["timestamp"]).year
    rows: list[dict[str, object]] = []
    for year, group in available.groupby("year"):
        weights = group["notional"].astype(float)
        rows.append(
            {
                "year": int(year),
                "trade_count": int(len(group)),
                "notional": float(weights.sum()),
                "notional_fill_rate": _weighted_mean(
                    group["filled"].astype(float), weights
                ),
                "effective_cost_bps": _weighted_mean(
                    group["effective_cost_bps"].astype(float), weights
                ),
                "improvement_bps": _weighted_mean(
                    group["improvement_bps"].astype(float), weights
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("year")


def _asset_breakdown(simulation: pd.DataFrame) -> pd.DataFrame:
    available = simulation.loc[simulation["available"].astype(bool)].copy()
    if available.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for asset, group in available.groupby("asset"):
        weights = group["notional"].astype(float)
        rows.append(
            {
                "asset": str(asset),
                "trade_count": int(len(group)),
                "notional": float(weights.sum()),
                "notional_fill_rate": _weighted_mean(
                    group["filled"].astype(float), weights
                ),
                "effective_cost_bps": _weighted_mean(
                    group["effective_cost_bps"].astype(float), weights
                ),
                "improvement_bps": _weighted_mean(
                    group["improvement_bps"].astype(float), weights
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("improvement_bps", ascending=False)


def _side_breakdown(simulation: pd.DataFrame) -> pd.DataFrame:
    available = simulation.loc[simulation["available"].astype(bool)].copy()
    if available.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for side, group in available.groupby("side"):
        weights = group["notional"].astype(float)
        rows.append(
            {
                "side": str(side),
                "trade_count": int(len(group)),
                "notional": float(weights.sum()),
                "notional_fill_rate": _weighted_mean(
                    group["filled"].astype(float), weights
                ),
                "effective_cost_bps": _weighted_mean(
                    group["effective_cost_bps"].astype(float), weights
                ),
                "improvement_bps": _weighted_mean(
                    group["improvement_bps"].astype(float), weights
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("side")


def _parse_floats(value: str) -> tuple[float, ...]:
    parsed = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 0.0 for item in parsed):
        raise ValueError("expected a non-empty list of non-negative numbers")
    return parsed


def _parse_ints(value: str) -> tuple[int, ...]:
    parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item < 1 for item in parsed):
        raise ValueError("expected a non-empty list of positive integers")
    return parsed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trades-path", type=Path, default=Path(DEFAULT_TRADES))
    parser.add_argument("--bar-source", choices=("bitget-mark", "binance-30m"), default="bitget-mark")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--intraday-dir", type=Path, default=DEFAULT_INTRADAY_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--offsets-bps", default="2,5,10")
    parser.add_argument("--timeouts-bars", default="1,2,4")
    parser.add_argument("--through-bps", type=float, default=1.0)
    parser.add_argument("--maker-fee-bps", type=float, default=2.0)
    parser.add_argument("--taker-fee-bps", type=float, default=20.0)
    parser.add_argument("--baseline-fee-bps", type=float, default=20.0)
    parser.add_argument("--analysis-offset-bps", type=float, default=5.0)
    parser.add_argument("--analysis-timeout-bars", type=int, default=2)
    args = parser.parse_args(argv)

    offsets = _parse_floats(args.offsets_bps)
    timeouts = _parse_ints(args.timeouts_bars)
    if args.analysis_offset_bps not in offsets:
        parser.error("--analysis-offset-bps must appear in --offsets-bps")
    if args.analysis_timeout_bars not in timeouts:
        parser.error("--analysis-timeout-bars must appear in --timeouts-bars")
    if any(
        value < 0.0
        for value in (
            args.through_bps,
            args.maker_fee_bps,
            args.taker_fee_bps,
            args.baseline_fee_bps,
        )
    ):
        parser.error("fee and through-bps assumptions must be non-negative")

    configure_logging("ERROR")
    trades = pd.read_csv(args.trades_path)
    required = {"timestamp", "asset", "side", "action", "notional"}
    missing = required.difference(trades.columns)
    if missing:
        raise SystemExit(f"trades file is missing columns: {sorted(missing)}")
    trades["timestamp"] = pd.DatetimeIndex(pd.to_datetime(trades["timestamp"], utc=True))
    bars = load_bars(
        bar_source=args.bar_source,
        raw_dir=args.raw_dir,
        intraday_dir=args.intraday_dir,
    )
    total_notional = float(pd.to_numeric(trades["notional"], errors="coerce").fillna(0.0).sum())
    simulations: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []
    for offset in offsets:
        for timeout in timeouts:
            rows = [
                simulate_trade(
                    trade,
                    bars.get(str(trade["asset"]), pd.DataFrame()),
                    offset_bps=float(offset),
                    timeout_bars=int(timeout),
                    through_bps=float(args.through_bps),
                    maker_fee_bps=float(args.maker_fee_bps),
                    taker_fee_bps=float(args.taker_fee_bps),
                    baseline_fee_bps=float(args.baseline_fee_bps),
                )
                if str(trade["asset"]) in bars
                else {
                    "available": False,
                    "asset": str(trade["asset"]),
                    "timestamp": _as_utc(trade["timestamp"]),
                    "side": trade_direction(trade["side"], trade["action"]),
                    "notional": float(trade["notional"]),
                    "filled": False,
                    "effective_cost_bps": np.nan,
                    "improvement_bps": np.nan,
                }
                for _, trade in trades.iterrows()
            ]
            frame = pd.DataFrame(rows)
            frame["offset_bps"] = float(offset)
            frame["timeout_bars"] = int(timeout)
            simulations.append(frame)
            summaries.append(
                summarise(
                    frame,
                    total_notional=total_notional,
                    offset_bps=float(offset),
                    timeout_bars=int(timeout),
                )
            )
    summary = pd.DataFrame(summaries).sort_values(["offset_bps", "timeout_bars"])
    all_simulation = pd.concat(simulations, ignore_index=True)
    primary = all_simulation.loc[
        (all_simulation["offset_bps"] == float(args.analysis_offset_bps))
        & (all_simulation["timeout_bars"] == int(args.analysis_timeout_bars))
    ].copy()
    yearly = _yearly_breakdown(primary)
    assets = _asset_breakdown(primary)
    sides = _side_breakdown(primary)
    output_dir = ensure_dir(args.output_dir)
    summary.to_csv(output_dir / "summary.csv", index=False)
    yearly.to_csv(output_dir / "yearly_breakdown.csv", index=False)
    assets.to_csv(output_dir / "asset_breakdown.csv", index=False)
    sides.to_csv(output_dir / "side_breakdown.csv", index=False)
    primary_row = summary.loc[
        (summary["offset_bps"] == float(args.analysis_offset_bps))
        & (summary["timeout_bars"] == int(args.analysis_timeout_bars))
    ].iloc[0]
    manifest = {
        "trades_path": str(args.trades_path),
        "bar_source": args.bar_source,
        "raw_dir": str(args.raw_dir) if args.bar_source == "bitget-mark" else None,
        "intraday_dir": str(args.intraday_dir) if args.bar_source == "binance-30m" else None,
        "trade_count": int(len(trades)),
        "total_notional": total_notional,
        "through_bps": float(args.through_bps),
        "maker_fee_bps": float(args.maker_fee_bps),
        "taker_fee_bps": float(args.taker_fee_bps),
        "baseline_fee_bps": float(args.baseline_fee_bps),
        "analysis_offset_bps": float(args.analysis_offset_bps),
        "analysis_timeout_bars": int(args.analysis_timeout_bars),
        "primary": {str(key): value for key, value in primary_row.to_dict().items()},
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report_lines = [
        "# Maker-first execution diagnostic",
        "",
        f"- trades: **{len(trades)}**; notional: **{total_notional:.4f}**",
        f"- bar source: **{args.bar_source}**",
        f"- primary offset / timeout / through: **{args.analysis_offset_bps:g}bps / "
        f"{args.analysis_timeout_bars} bars / {args.through_bps:g}bps**",
        f"- assumptions: maker **{args.maker_fee_bps:g}bps**, taker "
        f"**{args.taker_fee_bps:g}bps**, baseline **{args.baseline_fee_bps:g}bps**",
        "",
        "## Sensitivity",
        "",
        dataframe_to_markdown(summary.reset_index(drop=True)),
        "",
        "## Primary yearly breakdown",
        "",
        dataframe_to_markdown(yearly.reset_index(drop=True)) if not yearly.empty else "_no covered trades_",
        "",
        "## Primary by side",
        "",
        dataframe_to_markdown(sides.reset_index(drop=True)) if not sides.empty else "_no covered trades_",
        "",
        "## Primary asset breakdown (top 10 by improvement)",
        "",
        dataframe_to_markdown(assets.head(10).reset_index(drop=True)) if not assets.empty else "_no covered trades_",
        "",
        "## Interpretation guardrails",
        "",
        "- Mark high/low is not a tradeable order book; touch-through is a proxy, not proven fill.",
        "- The result does not include queue position, partial fills, cancel latency, venue rejects, ADL or funding.",
        "- This is execution research only. It does not change LS57, LS23 or the live L125-V2 track.",
    ]
    (output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(
        f"wrote {output_dir}; primary coverage={primary_row['coverage']:.3f}, "
        f"fill={primary_row['notional_fill_rate']:.3f}, "
        f"effective_cost={primary_row['effective_cost_bps']:.2f}bps, "
        f"improvement={primary_row['improvement_bps']:.2f}bps"
    )


if __name__ == "__main__":
    main()
