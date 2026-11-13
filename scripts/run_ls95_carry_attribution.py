"""LS95: standalone attribution of the LS82 core8 funding-carry sleeve.

The sleeve is rerun without the LS57 base, using the frozen LS82 carry schedule
and the same Bitget mark/market and Binance funding inputs.  This is a
diagnostic, not a new strategy or a live signal.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

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
from scripts.run_derivatives_backtest import _funding_for_source  # noqa: E402
from scripts.run_ls81_core_major_funding_carry import CORE8, _run_engine  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

TRIAL_ID = "PR2026-11-LS95-LS82-CARRY-ATTRIBUTION"
START = pd.Timestamp("2022-01-01", tz="UTC")
END = pd.Timestamp("2026-09-21", tz="UTC")
COST_BPS = 20.0
ALLOCATION = 0.25
RAW_DIR = Path("data/raw/bitget_derivatives/merged_20261009")
MARKET_DIR = Path("data/raw/bitget_derivatives/merged_market_20261009")
BINANCE_DIR = Path("data/raw/binance_funding")
CARRY_SCHEDULE = Path("reports/ls82_core8_carry_risk_2026/carry_schedule.csv")


def signed_position_frame(
    trades: pd.DataFrame,
    *,
    index: pd.DatetimeIndex,
    assets: Sequence[str],
) -> pd.DataFrame:
    """Replay trade ledgers into signed quantities on an hourly mark index."""
    required = {"timestamp", "asset", "side", "action", "quantity"}
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError(f"trade ledger missing columns: {missing}")
    if not isinstance(index, pd.DatetimeIndex) or index.empty:
        raise ValueError("position index must be a non-empty DatetimeIndex")
    frame = trades.loc[:, list(required)].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    if frame["timestamp"].isna().any():
        raise ValueError("trade ledger has unparseable timestamps")
    side_sign = np.where(frame["side"].astype(str).str.lower().eq("long"), 1.0, -1.0)
    action = frame["action"].astype(str).str.lower()
    if not action.isin({"open", "increase", "reduce", "close"}).all():
        raise ValueError("trade ledger has unsupported actions")
    action_sign = np.where(action.isin({"open", "increase"}), 1.0, -1.0)
    quantity = pd.to_numeric(frame["quantity"], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(quantity).all() or (quantity < 0.0).any():
        raise ValueError("trade quantities must be finite and non-negative")
    frame["signed_quantity"] = quantity * side_sign * action_sign
    events = (
        frame.groupby(["timestamp", "asset"])["signed_quantity"]
        .sum()
        .unstack(fill_value=0.0)
        .reindex(columns=list(assets), fill_value=0.0)
        .sort_index()
    )
    positions = events.reindex(index, method=None).fillna(0.0).cumsum()
    if not np.isfinite(positions.to_numpy(dtype=float)).all():
        raise ValueError("replayed positions contain non-finite values")
    return positions


def load_scaled_schedule(
    path: Path,
    *,
    assets: Sequence[str],
    allocation: float,
) -> dict[pd.Timestamp, pd.Series]:
    """Load the frozen raw carry schedule and scale it to the sleeve allocation."""
    if not 0.0 < allocation <= 1.0:
        raise ValueError("allocation must be in (0, 1]")
    frame = pd.read_csv(path, index_col=0)
    if frame.empty:
        raise ValueError(f"{path}: empty carry schedule")
    index = pd.DatetimeIndex(pd.to_datetime(frame.index, errors="coerce", utc=True))
    if index.isna().any() or index.duplicated().any():
        raise ValueError(f"{path}: schedule dates are invalid or duplicated")
    frame.index = index.sort_values()
    frame = frame.reindex(columns=list(assets))
    targets: dict[pd.Timestamp, pd.Series] = {}
    for timestamp, row in frame.sort_index().iterrows():
        values = row.dropna()
        if values.empty:
            targets[timestamp] = pd.Series(dtype=float)
            continue
        target = values.reindex(list(assets), fill_value=0.0).astype(float) * float(allocation)
        if not np.isfinite(target.to_numpy(dtype=float)).all():
            raise ValueError(f"{path}: schedule contains non-finite weights")
        if float(target.abs().sum()) > float(allocation) + 1e-12:
            raise ValueError(f"{path}: scaled schedule exceeds allocation")
        targets[timestamp] = target.sort_index()
    return targets


def _group_ledger(frame: pd.DataFrame, value: str, *, assets: Sequence[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    required = {"timestamp", "asset", value}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"ledger missing columns: {missing}")
    ledger = frame.loc[:, ["timestamp", "asset", value]].copy()
    ledger["timestamp"] = pd.to_datetime(ledger["timestamp"], utc=True)
    grouped = (
        ledger.groupby(["timestamp", "asset"])[value]
        .sum()
        .unstack(fill_value=0.0)
        .reindex(columns=list(assets), fill_value=0.0)
    )
    return grouped.reindex(index).fillna(0.0)


def attribute_carry_sleeve(
    *,
    result: Any,
    mark_candles: Mapping[str, pd.DataFrame],
    assets: Sequence[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    """Replay the standalone sleeve and aggregate PnL by asset, year and side."""
    prices = pd.DataFrame(
        {asset: mark_candles[asset]["close"] for asset in assets}
    ).sort_index()
    prices = prices.loc[(prices.index >= start) & (prices.index < end)]
    if prices.empty:
        raise ValueError("mark price panel is empty")
    positions = signed_position_frame(result.trades, index=prices.index, assets=assets)
    price_pnl = positions.shift(1).fillna(0.0) * prices.diff().fillna(0.0)
    funding = _group_ledger(result.funding, "amount", assets=assets, index=prices.index)
    fees = _group_ledger(result.trades, "fee", assets=assets, index=prices.index)
    net = price_pnl + funding - fees

    daily = net.resample("1D").sum()
    daily = daily.reindex(result.daily_returns.index).fillna(0.0)
    engine_equity = (1.0 + result.daily_returns).cumprod().shift(1).fillna(1.0)
    attributed_return = daily.sum(axis=1) / engine_equity.reindex(daily.index)
    validation_correlation = float(attributed_return.corr(result.daily_returns.reindex(daily.index)))

    asset_summary = pd.DataFrame(
        {
            "price_pnl": price_pnl.sum(),
            "funding_pnl": funding.sum(),
            "fees": fees.sum(),
        }
    ).rename_axis("asset").reset_index()
    asset_summary["net_pnl"] = (
        asset_summary["price_pnl"] + asset_summary["funding_pnl"] - asset_summary["fees"]
    )

    asset_year = (
        net.groupby(net.index.year).sum().T.rename_axis("asset").reset_index()
    )
    asset_year = asset_year.melt(id_vars="asset", var_name="year", value_name="net_pnl")

    long_price = price_pnl.where(positions.shift(1).fillna(0.0) > 0.0, 0.0).resample("1D").sum().sum(axis=1)
    short_price = price_pnl.where(positions.shift(1).fillna(0.0) < 0.0, 0.0).resample("1D").sum().sum(axis=1)
    funding_by_side = (
        result.funding.assign(timestamp=pd.to_datetime(result.funding["timestamp"], utc=True))
        .groupby([pd.Grouper(key="timestamp", freq="1D"), "side"])["amount"]
        .sum()
        .unstack(fill_value=0.0)
    )
    fees_by_side = (
        result.trades.assign(timestamp=pd.to_datetime(result.trades["timestamp"], utc=True))
        .groupby([pd.Grouper(key="timestamp", freq="1D"), "side"])["fee"]
        .sum()
        .unstack(fill_value=0.0)
    )
    long_daily = (
        long_price
        + funding_by_side.get("long", pd.Series(0.0, index=long_price.index)).reindex(long_price.index).fillna(0.0)
        - fees_by_side.get("long", pd.Series(0.0, index=long_price.index)).reindex(long_price.index).fillna(0.0)
    )
    short_daily = (
        short_price
        + funding_by_side.get("short", pd.Series(0.0, index=short_price.index)).reindex(short_price.index).fillna(0.0)
        - fees_by_side.get("short", pd.Series(0.0, index=short_price.index)).reindex(short_price.index).fillna(0.0)
    )
    side_year = pd.DataFrame({"long": long_daily, "short": short_daily}).groupby(
        lambda index: index.year
    ).sum().rename_axis("year").reset_index()
    side_summary = pd.DataFrame(
        {
            "side": ["long", "short"],
            "net_pnl": [float(long_daily.sum()), float(short_daily.sum())],
        }
    )

    year_summary = pd.DataFrame(
        {
            "year": sorted(net.index.year.unique()),
            "net_pnl": net.groupby(net.index.year).sum().sum(axis=1).reindex(
                sorted(net.index.year.unique()), fill_value=0.0
            ).to_numpy(),
            "engine_return": result.daily_returns.groupby(result.daily_returns.index.year).apply(
                lambda values: float((1.0 + values).prod() - 1.0)
            ).reindex(sorted(net.index.year.unique()), fill_value=0.0).to_numpy(),
        }
    )
    carry_daily = pd.DataFrame(
        {
            "daily_return": result.daily_returns.reindex(daily.index),
            "equity": (1.0 + result.daily_returns).cumprod().reindex(daily.index),
            "gross_exposure": result.gross_exposure.reindex(daily.index),
            "attributed_price_pnl": price_pnl.resample("1D").sum().sum(axis=1).reindex(daily.index),
            "attributed_funding_pnl": funding.resample("1D").sum().sum(axis=1).reindex(daily.index),
            "attributed_fees": fees.resample("1D").sum().sum(axis=1).reindex(daily.index),
            "attributed_net_pnl": daily.sum(axis=1),
            "attributed_return": attributed_return,
        }
    )
    return {
        "carry_daily": carry_daily,
        "asset_summary": asset_summary.sort_values("net_pnl", ascending=False).reset_index(drop=True),
        "asset_year": asset_year,
        "side_year": side_year,
        "side_summary": side_summary,
        "year_summary": year_summary,
        "validation_correlation": validation_correlation,
    }


def classify_attribution(
    *,
    asset_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    side_summary: pd.DataFrame,
    validation_correlation: float,
) -> str:
    """Classify where the standalone carry sleeve's PnL came from."""
    if not np.isfinite(validation_correlation) or validation_correlation <= 0.95:
        return "inconclusive"
    total = float(asset_summary["net_pnl"].sum())
    if total <= 0.0:
        return "inconclusive"
    largest_positive = float(asset_summary["net_pnl"].max())
    largest_drag = max(0.0, -float(asset_summary["net_pnl"].min()))
    if largest_positive / total > 0.50 or largest_drag / total > 0.50:
        return "asset-concentrated"
    if float(year_summary["net_pnl"].max()) / total > 0.70:
        return "year-concentrated"
    if float(side_summary["net_pnl"].max()) / total > 0.80:
        return "side-concentrated"
    return "diversified"


def _report(
    *,
    metrics: Mapping[str, float],
    attribution: Mapping[str, Any],
    classification: str,
) -> str:
    asset = attribution["asset_summary"]
    side = attribution["side_summary"]
    year = attribution["year_summary"]
    lines = [
        f"# {TRIAL_ID}",
        "",
        "LS95 reruns only the LS82 carry sleeve, without the LS57 base, and attributes its price,",
        "funding and fee PnL by asset, year and side. It is a diagnostic, not a live signal.",
        "",
        "## Standalone sleeve",
        "",
        f"- Terminal multiple: **{metrics['multiple']:.4f}x**",
        f"- Sharpe: **{metrics['sharpe']:.4f}**",
        f"- Max drawdown: **{metrics['max_drawdown']:.4%}**",
        f"- Attribution/engine daily-return correlation: **{attribution['validation_correlation']:.4f}**",
        "- A correlation below 0.95 would make the attribution inconclusive.",
        "",
        "## Asset attribution",
        "",
        dataframe_to_markdown(asset),
        "",
        "## Side attribution",
        "",
        dataframe_to_markdown(side),
        "",
        "## Year attribution",
        "",
        dataframe_to_markdown(year),
        "",
        "## Asset-year net PnL",
        "",
        dataframe_to_markdown(attribution["asset_year"].pivot(index="asset", columns="year", values="net_pnl").reset_index()),
        "",
        "## Side-year net PnL",
        "",
        dataframe_to_markdown(attribution["side_year"]),
        "",
        "## Evidence classification",
        "",
        f"**{classification}**",
        "",
        "The classification only describes the historical source of the carry sleeve's PnL. It does",
        "not promote LS82, change the live track, or justify dropping an asset/year after the fact.",
        "",
        "Research output only; no orders sent.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--carry-schedule", type=Path, default=CARRY_SCHEDULE)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--market-dir", type=Path, default=MARKET_DIR)
    parser.add_argument("--binance-dir", type=Path, default=BINANCE_DIR)
    args = parser.parse_args(argv)
    configure_logging("ERROR")

    mark_symbol_map = pd.read_csv(args.raw_dir / "symbol_map.csv")
    market_symbol_map = pd.read_csv(args.market_dir / "symbol_map.csv")
    mark_candles = load_mark_candles(args.raw_dir, mark_symbol_map)
    market_candles = load_mark_candles(args.market_dir, market_symbol_map, candle_type="market")
    assets = list(CORE8)
    funding = _funding_for_source(
        "binance-proxy",
        raw_dir=args.raw_dir,
        binance_dir=args.binance_dir,
        symbol_map=mark_symbol_map,
        coins=set(assets),
    ).dropna(how="all")
    funding = funding.loc[:, funding.notna().any(axis=0)]
    if funding.empty:
        raise SystemExit("funding data is empty")
    intervals = {
        str(record["coin_id"]): float(record["fund_interval"])
        for record in mark_symbol_map.to_dict("records")
        if pd.notna(record.get("fund_interval")) and float(record.get("fund_interval")) > 0.0
    }
    targets = load_scaled_schedule(args.carry_schedule, assets=assets, allocation=ALLOCATION)
    result = _run_engine(
        mark_candles=mark_candles,
        market_candles=market_candles,
        targets=targets,
        funding=funding,
        funding_intervals=intervals,
        funding_missing_policy="skip",
        funding_stress="none",
        funding_multiplier=1.0,
        cost_bps=COST_BPS,
        long_buffer=0.60,
        target_gross=1.45,
        start_time=START,
        end_time=END,
    )
    metrics = {key: float(value) for key, value in _metrics_from_returns(result.daily_returns).items()}
    attribution = attribute_carry_sleeve(
        result=result,
        mark_candles=mark_candles,
        assets=assets,
        start=START,
        end=END,
    )
    classification = classify_attribution(
        asset_summary=attribution["asset_summary"],
        year_summary=attribution["year_summary"],
        side_summary=attribution["side_summary"],
        validation_correlation=float(attribution["validation_correlation"]),
    )

    output_dir = ensure_dir(args.output_dir)
    attribution["carry_daily"].to_csv(output_dir / "carry_daily.csv", index_label="date")
    attribution["asset_summary"].to_csv(output_dir / "asset_summary.csv", index=False)
    attribution["asset_year"].to_csv(output_dir / "asset_year_net.csv", index=False)
    attribution["side_year"].to_csv(output_dir / "side_year_net.csv", index=False)
    attribution["side_summary"].to_csv(output_dir / "side_summary.csv", index=False)
    attribution["year_summary"].to_csv(output_dir / "year_summary.csv", index=False)
    manifest = {
        "trial_id": TRIAL_ID,
        "carry_schedule": str(args.carry_schedule),
        "carry_schedule_sha256": hashlib.sha256(args.carry_schedule.read_bytes()).hexdigest(),
        "allocation": ALLOCATION,
        "cost_bps": COST_BPS,
        "start": str(START),
        "end": str(END),
        "assets": assets,
        "metrics": metrics,
        "validation_correlation": float(attribution["validation_correlation"]),
        "classification": classification,
        "orders_sent": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        _report(metrics=metrics, attribution=attribution, classification=classification),
        encoding="utf-8",
    )
    print(attribution["asset_summary"].to_string(index=False))
    print(attribution["side_summary"].to_string(index=False))
    print(f"validation correlation: {attribution['validation_correlation']:.6f}")
    print(f"classification: {classification}")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
