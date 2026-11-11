# ruff: noqa: E402
"""Pair derivatives short trades into episodes and attribute net PnL.

This reads only saved engine outputs. It reconstructs average-cost short
episodes, applies trade fees and funding cashflows, and reports asset-level
concentration. It is a research attribution, not an execution ledger.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _equity_at(equity: pd.Series, timestamp: pd.Timestamp) -> float:
    candidates = equity.index[equity.index <= timestamp]
    if candidates.empty:
        return float("nan")
    return float(equity.loc[candidates[-1]])


def attribute(
    trades: pd.DataFrame,
    funding: pd.DataFrame,
    equity_curve: pd.DataFrame,
    liquidations: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    equity = equity_curve.iloc[:, 0].copy()
    equity.index = pd.DatetimeIndex([_as_utc(value) for value in equity.index])
    equity = pd.to_numeric(equity, errors="coerce").sort_index()

    events: list[dict[str, object]] = []
    for row in trades.loc[trades["side"].astype(str) == "short"].itertuples(index=False):
        events.append(
            {
                "timestamp": _as_utc(row.timestamp),
                "kind": "trade",
                "asset": str(row.asset),
                "action": str(row.action),
                "quantity": float(row.quantity),
                "price": float(row.price),
                "fee": float(row.fee),
                "reason": str(row.reason),
            }
        )
    for row in funding.itertuples(index=False):
        events.append(
            {
                "timestamp": _as_utc(row.timestamp),
                "kind": "funding",
                "asset": str(row.asset),
                "amount": float(row.amount),
            }
        )
    if liquidations is not None:
        for row in liquidations.loc[
            liquidations["side"].astype(str) == "short"
        ].itertuples(index=False):
            events.append(
                {
                    "timestamp": _as_utc(row.trigger_timestamp),
                    "kind": "liquidation",
                    "asset": str(row.asset),
                    "action": "close",
                    "quantity": float(row.quantity),
                    "price": float(row.execution_price),
                    "fee": 0.0,
                    "reason": "liquidation",
                }
            )
    kind_order = {"funding": 0, "liquidation": 1, "trade": 2}
    events.sort(key=lambda item: (item["timestamp"], kind_order[str(item["kind"])]))

    state: dict[str, dict[str, object]] = {}
    episodes: list[dict[str, object]] = []
    for event in events:
        asset = str(event["asset"])
        current = state.get(asset)
        if event["kind"] == "funding":
            if current is not None and float(current["quantity"]) > 1e-15:
                current["net_pnl"] = float(current["net_pnl"]) + float(event["amount"])
            continue

        action = str(event["action"])
        timestamp = pd.Timestamp(event["timestamp"])
        if current is None:
            current = {
                "quantity": 0.0,
                "average_entry": 0.0,
                "entry_time": timestamp,
                "entry_equity": _equity_at(equity, timestamp),
                "net_pnl": 0.0,
                "fees": 0.0,
            }
            state[asset] = current

        quantity = float(event["quantity"])
        price = float(event["price"])
        fee = float(event["fee"])
        current["fees"] = float(current["fees"]) + fee
        current["net_pnl"] = float(current["net_pnl"]) - fee

        if action in {"open", "increase"}:
            held = float(current["quantity"])
            total = held + quantity
            if total <= 0.0:
                raise ValueError(f"{asset}: non-positive short quantity after increase")
            current["average_entry"] = (
                held * float(current["average_entry"]) + quantity * price
            ) / total
            current["quantity"] = total
            if held <= 1e-15:
                current["entry_time"] = timestamp
                current["entry_equity"] = _equity_at(equity, timestamp)
            continue

        if action not in {"reduce", "close"}:
            raise ValueError(f"{asset}: unsupported short action {action}")
        held = float(current["quantity"])
        close_tolerance = max(1e-12, abs(held) * 1e-9)
        if quantity > held + close_tolerance:
            raise ValueError(f"{asset}: close quantity exceeds held quantity")
        quantity = held if action == "close" else min(quantity, held)
        current["net_pnl"] = float(current["net_pnl"]) + (
            float(current["average_entry"]) - price
        ) * quantity
        current["quantity"] = held - quantity
        if float(current["quantity"]) <= 1e-12:
            entry_equity = float(current["entry_equity"])
            net_pnl = float(current["net_pnl"])
            episodes.append(
                {
                    "asset": asset,
                    "entry_time": pd.Timestamp(current["entry_time"]),
                    "exit_time": timestamp,
                    "reason": str(event["reason"]),
                    "entry_equity": entry_equity,
                    "net_pnl": net_pnl,
                    "fees": float(current["fees"]),
                    "net_pnl_pct_nav": net_pnl / entry_equity * 100.0
                    if entry_equity > 0.0
                    else float("nan"),
                }
            )
            del state[asset]

    for asset, current in state.items():
        if float(current["quantity"]) > 1e-12:
            entry_equity = float(current["entry_equity"])
            net_pnl = float(current["net_pnl"])
            episodes.append(
                {
                    "asset": asset,
                    "entry_time": pd.Timestamp(current["entry_time"]),
                    "exit_time": pd.NaT,
                    "reason": "open_at_end",
                    "entry_equity": entry_equity,
                    "net_pnl": net_pnl,
                    "fees": float(current["fees"]),
                    "net_pnl_pct_nav": net_pnl / entry_equity * 100.0
                    if entry_equity > 0.0
                    else float("nan"),
                }
            )

    episode_frame = pd.DataFrame(episodes).sort_values(["entry_time", "asset"]).reset_index(drop=True)
    total = float(episode_frame["net_pnl"].sum()) if not episode_frame.empty else 0.0
    asset_frame = (
        episode_frame.groupby("asset")
        .agg(
            episodes=("asset", "size"),
            net_pnl=("net_pnl", "sum"),
            avg_pct_nav=("net_pnl_pct_nav", "mean"),
            worst_pct_nav=("net_pnl_pct_nav", "min"),
            best_pct_nav=("net_pnl_pct_nav", "max"),
        )
        .reset_index()
    )
    asset_frame["share"] = (
        asset_frame["net_pnl"] / total if abs(total) > 1e-15 else float("nan")
    )
    asset_frame = asset_frame.sort_values("net_pnl", ascending=False).reset_index(drop=True)
    summary = {
        "episodes": int(len(episode_frame)),
        "positive_episodes": int((episode_frame["net_pnl"] > 0.0).sum()),
        "negative_episodes": int((episode_frame["net_pnl"] < 0.0).sum()),
        "total_net_pnl": total,
        "total_pct_nav_sum": float(episode_frame["net_pnl_pct_nav"].sum()),
        "mean_pct_nav": float(episode_frame["net_pnl_pct_nav"].mean()),
        "median_pct_nav": float(episode_frame["net_pnl_pct_nav"].median()),
        "worst_pct_nav": float(episode_frame["net_pnl_pct_nav"].min()),
        "best_pct_nav": float(episode_frame["net_pnl_pct_nav"].max()),
        "max_asset_share": float(asset_frame["share"].max()) if not asset_frame.empty else 0.0,
        "top3_share": float(asset_frame["share"].head(3).sum()) if not asset_frame.empty else 0.0,
    }
    return episode_frame, asset_frame, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--funding", type=Path, required=True)
    parser.add_argument("--equity-curve", type=Path, required=True)
    parser.add_argument(
        "--liquidations",
        type=Path,
        default=None,
        help="optional engine liquidations.csv; short liquidations close episodes",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    episodes, assets, summary = attribute(
        pd.read_csv(args.trades),
        pd.read_csv(args.funding),
        pd.read_csv(args.equity_curve, index_col=0),
        pd.read_csv(args.liquidations) if args.liquidations is not None else None,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    episodes.to_csv(args.output_dir / "short_episode_attribution.csv", index=False)
    assets.to_csv(args.output_dir / "short_asset_attribution.csv", index=False)
    (args.output_dir / "short_attribution_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote short attribution to {args.output_dir}")


if __name__ == "__main__":
    main()
