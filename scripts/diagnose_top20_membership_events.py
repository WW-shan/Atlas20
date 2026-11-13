"""Diagnose point-in-time Top20 membership entry and exit events.

This is an event study only: no portfolio, no order, and no live-state change.
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

from scripts.run_phase_momentum import _load_market  # noqa: E402

DEFAULT_START = "2021-01-01"
DEFAULT_END = "2026-11-12"
CONFIRMATION_DAYS = (3, 7, 14)
FORWARD_DAYS = (7, 14, 28, 56)
COOLDOWN_DAYS = 30
SAMPLE_WINDOWS: dict[str, tuple[str, str]] = {
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-11-12"),
}


def membership_matrix(
    universe: pd.DataFrame,
    *,
    index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Return a daily boolean coin-by-date Top20 membership matrix."""
    frame = universe.copy()
    frame["rebalance_date"] = pd.to_datetime(frame["rebalance_date"], utc=True)
    frame["present"] = True
    matrix = (
        frame.pivot_table(
            index="rebalance_date",
            columns="coin_id",
            values="present",
            aggfunc="max",
        )
        .reindex(index, fill_value=False)
        .fillna(False)
        .astype(bool)
        .sort_index()
    )
    return matrix


def detect_membership_events(
    present: pd.DataFrame,
    *,
    confirmation_days: int,
    cooldown_days: int = COOLDOWN_DAYS,
) -> pd.DataFrame:
    """Detect confirmed entry and exit events with per-coin cooldown."""
    if confirmation_days < 1:
        raise ValueError("confirmation_days must be positive")
    if cooldown_days < 0:
        raise ValueError("cooldown_days must be non-negative")
    if not present.index.is_monotonic_increasing:
        raise ValueError("present index must be sorted")
    in_confirmed = (
        present.rolling(confirmation_days, min_periods=confirmation_days).sum()
        == confirmation_days
    )
    out_confirmed = (
        (~present).rolling(confirmation_days, min_periods=confirmation_days).sum()
        == confirmation_days
    )
    previous_in = in_confirmed.shift(1, fill_value=False)
    previous_out = out_confirmed.shift(1, fill_value=False)
    ever_in: set[str] = set()
    ever_out: set[str] = set()
    last_event: dict[tuple[str, str], pd.Timestamp] = {}
    rows: list[dict[str, Any]] = []
    for date in present.index:
        for coin in present.columns:
            is_in = bool(present.loc[date, coin])
            if is_in:
                ever_in.add(str(coin))
            else:
                ever_out.add(str(coin))
            for event_type, transition, confirmed in (
                ("entry", in_confirmed.loc[date, coin] and not previous_in.loc[date, coin], in_confirmed),
                ("exit", out_confirmed.loc[date, coin] and not previous_out.loc[date, coin], out_confirmed),
            ):
                if event_type == "entry" and str(coin) not in ever_out:
                    continue
                if event_type == "exit" and str(coin) not in ever_in:
                    continue
                if not bool(transition) or not bool(confirmed.loc[date, coin]):
                    continue
                key = (str(coin), event_type)
                previous = last_event.get(key)
                if previous is not None and (date - previous).days < cooldown_days:
                    continue
                last_event[key] = date
                rows.append(
                    {
                        "coin_id": str(coin),
                        "event_date": date,
                        "event_type": event_type,
                        "confirmation_days": confirmation_days,
                    }
                )
    return pd.DataFrame(rows, columns=["coin_id", "event_date", "event_type", "confirmation_days"])


def forward_log_returns(price: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Return log(close(t+horizon)/close(t+1)) for each signal date t."""
    if horizon < 2:
        raise ValueError("horizon must be at least two observations")
    log_price = np.log(price.where(price > 0.0))
    return (log_price.shift(-horizon) - log_price.shift(-1)).replace(
        [np.inf, -np.inf], np.nan
    )


def top20_equal_weight_future(
    present: pd.DataFrame,
    future_returns: pd.DataFrame,
) -> pd.Series:
    """Average future return of the point-in-time Top20 members at each date."""
    aligned = future_returns.reindex(index=present.index, columns=present.columns)
    values = aligned.where(present).mean(axis=1)
    return values.astype(float)


def build_event_observations(
    *,
    events: pd.DataFrame,
    price: pd.DataFrame,
    present: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    """Attach raw, BTC-excess and Top20-excess forward returns to each event."""
    future = forward_log_returns(price, horizon)
    if "bitcoin" not in future.columns:
        raise ValueError("bitcoin price is required")
    btc = future["bitcoin"]
    top20 = top20_equal_weight_future(present, future)
    rows: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        date = pd.Timestamp(event.event_date)
        coin = str(event.coin_id)
        if date not in future.index or coin not in future.columns:
            continue
        raw = future.loc[date, coin]
        if not np.isfinite(raw) or not np.isfinite(btc.loc[date]) or not np.isfinite(top20.loc[date]):
            continue
        rows.append(
            {
                **event._asdict(),
                "horizon_days": horizon,
                "raw_return": float(raw),
                "btc_excess": float(raw - btc.loc[date]),
                "top20_excess": float(raw - top20.loc[date]),
            }
        )
    return pd.DataFrame(rows)


def summarise_events(observations: pd.DataFrame) -> pd.DataFrame:
    """Summarise event-level and event-day-level means by sample and type."""
    rows: list[dict[str, Any]] = []
    for (confirmation, event_type, horizon), group in observations.groupby(
        ["confirmation_days", "event_type", "horizon_days"], sort=True
    ):
        for sample, (start, end) in SAMPLE_WINDOWS.items():
            sample_group = group.loc[
                (group["event_date"] >= pd.Timestamp(start, tz="UTC"))
                & (group["event_date"] <= pd.Timestamp(end, tz="UTC"))
            ].copy()
            if sample_group.empty:
                continue
            sample_group["event_day"] = pd.to_datetime(sample_group["event_date"], utc=True)
            per_day = sample_group.groupby("event_day").agg(
                raw_return=("raw_return", "mean"),
                btc_excess=("btc_excess", "mean"),
                top20_excess=("top20_excess", "mean"),
                same_day_events=("coin_id", "size"),
            )
            usable_days = per_day.loc[per_day["same_day_events"] >= 3]
            if usable_days.empty:
                continue
            rows.append(
                {
                    "confirmation_days": int(confirmation),
                    "event_type": str(event_type),
                    "horizon_days": int(horizon),
                    "sample": sample,
                    "event_count": int(len(sample_group)),
                    "event_day_count": int(len(usable_days)),
                    "mean_raw_return": float(sample_group["raw_return"].mean()),
                    "mean_btc_excess": float(usable_days["btc_excess"].mean()),
                    "mean_top20_excess": float(usable_days["top20_excess"].mean()),
                    "positive_btc_share": float((sample_group["btc_excess"] > 0.0).mean()),
                    "positive_top20_share": float((sample_group["top20_excess"] > 0.0).mean()),
                }
            )
    return pd.DataFrame(rows)


def event_study_verdict(summary: pd.DataFrame) -> tuple[str, list[str]]:
    """Apply the frozen entry/exit sign and count rules."""
    if summary.empty:
        return "rejected", ["no usable event-day cells"]
    reasons: list[str] = []
    for confirmation, horizon in summary[["confirmation_days", "horizon_days"]].drop_duplicates().itertuples(index=False):
        subset = summary.loc[
            (summary["confirmation_days"] == confirmation)
            & (summary["horizon_days"] == horizon)
        ]
        entry = subset.loc[subset["event_type"] == "entry"].set_index("sample")
        exit_ = subset.loc[subset["event_type"] == "exit"].set_index("sample")
        if {"discovery", "validation"}.issubset(entry.index) and {"discovery", "validation"}.issubset(exit_.index):
            if (
                entry.loc["discovery", "mean_btc_excess"] > 0
                and entry.loc["validation", "mean_btc_excess"] > 0
                and exit_.loc["discovery", "mean_btc_excess"] < 0
                and exit_.loc["validation", "mean_btc_excess"] < 0
            ):
                reasons.append(f"m={confirmation}, h={horizon} passes sign stability")
    if reasons:
        return "candidate-for-backtest", reasons
    return "rejected", ["no m/h cell has stable entry-positive and exit-negative BTC excess"]


def _report(summary: pd.DataFrame, verdict: str, reasons: list[str]) -> str:
    display = summary.copy()
    display = display.sort_values(
        ["confirmation_days", "horizon_days", "event_type", "sample"],
        kind="stable",
    )
    return "\n".join(
        [
            "# PIT Top20 membership event diagnostic",
            "",
            "- status: event study only; no strategy, no orders, no live changes",
            "- entry: coin has been continuously in PIT Top20 for m days",
            "- exit: coin has been continuously outside PIT Top20 for m days; only after it was previously a member",
            "- forward return starts at next close; horizons 7/14/28/56 trading days",
            "- cell means require at least 3 same-day events; events are equally weighted within a day",
            "",
            "## Summary",
            "",
            dataframe_to_markdown(display) if not display.empty else "No usable cells.",
            "",
            f"## Verdict\n\n**{verdict}**",
            "",
            *[f"- {reason}" for reason in reasons],
            "",
            "## Guardrail",
            "",
            "This diagnostic does not establish a tradeable strategy. It ignores costs, funding, execution, capacity and overlapping event risk.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date >= args.end_date:
        parser.error("--start-date must be before --end-date")

    _, market, universe, raw_index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    index = pd.DatetimeIndex(pd.to_datetime(raw_index, utc=True)).sort_values()
    present = membership_matrix(universe, index=index)
    price = market.price.copy()
    price.index = pd.DatetimeIndex(pd.to_datetime(price.index, utc=True)).sort_values()
    price = price.reindex(index).sort_index()

    all_observations: list[pd.DataFrame] = []
    for confirmation in CONFIRMATION_DAYS:
        events = detect_membership_events(
            present,
            confirmation_days=confirmation,
            cooldown_days=COOLDOWN_DAYS,
        )
        for horizon in FORWARD_DAYS:
            observations = build_event_observations(
                events=events,
                price=price,
                present=present,
                horizon=horizon,
            )
            if not observations.empty:
                all_observations.append(observations)
    observations = (
        pd.concat(all_observations, ignore_index=True)
        if all_observations
        else pd.DataFrame()
    )
    summary = summarise_events(observations)
    verdict, reasons = event_study_verdict(summary)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "events": output_dir / "events.csv",
        "summary": output_dir / "event_summary.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")

    observations.to_csv(files["events"], index=False)
    summary.to_csv(files["summary"], index=False)
    files["report"].write_text(_report(summary, verdict, reasons), encoding="utf-8")
    manifest = {
        "candidate_family_id": "PR2026-11-LS71-TOP20-MEMBERSHIP-EVENT",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "confirmation_days": list(CONFIRMATION_DAYS),
        "forward_days": list(FORWARD_DAYS),
        "cooldown_days": COOLDOWN_DAYS,
        "sample_windows": {key: list(value) for key, value in SAMPLE_WINDOWS.items()},
        "min_same_day_events": 3,
        "verdict": verdict,
        "reasons": reasons,
        "orders_sent": False,
        "funding_included": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir}; verdict={verdict}; observation_rows={len(observations)}")


if __name__ == "__main__":
    main()
