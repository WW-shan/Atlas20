"""Backtest the frozen intraday BTC lead-lag hypothesis without live effects.

This implements the pre-registered LS64 family.  It trades extreme BTC shocks
against the relative gap of point-in-time Top20 alts, with a fixed slot budget
so gross exposure never exceeds one.  It sends no orders and does not modify
the live target.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.analyze_intraday_execution_timing import load_30m_bars  # noqa: E402
from scripts.run_intraday_btc_leadlag_diagnostic import (  # noqa: E402
    BETA_CLIP,
    BETA_WINDOW_BARS,
    MIN_BETA_OBSERVATIONS,
    MIN_CROSS_SECTION,
    build_membership,
    build_price_panels,
    signal_window_return,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-09-30"
COSTS_PER_SIDE = (6.0, 12.0, 20.0)
SHOCK_THRESHOLD = 2.5
QUANTILE = 0.20
BASE_COST = 6.0
SAMPLE_WINDOWS: dict[str, tuple[str, str]] = {
    "full": ("2022-01-01", "2026-09-30"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-30"),
}


@dataclass(frozen=True)
class LeadLagVariant:
    variant_id: str
    signal_bars: int
    future_bars: int


VARIANTS = (
    LeadLagVariant("LL_1_4", 1, 4),
    LeadLagVariant("LL_2_4", 2, 4),
    LeadLagVariant("LL_2_8", 2, 8),
    LeadLagVariant("LL_4_8", 4, 8),
)


@dataclass(frozen=True)
class TradeEvent:
    variant_id: str
    signal_position: int
    entry_position: int
    exit_position: int
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    z: float
    long_assets: tuple[str, ...]
    short_assets: tuple[str, ...]


def _prepare_market(
    *,
    config: str,
    start_date: str,
    end_date: str,
    bar_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bars = load_30m_bars(bar_dir)
    if "bitcoin" not in bars:
        raise SystemExit("Bitcoin 30m bars are required")
    target_assets = sorted([coin for coin in bars if coin != "bitcoin"], key=str.casefold)
    _, _, universe, _ = _load_market(
        config,
        start_date=start_date,
        end_date=end_date,
    )
    btc_times = pd.DatetimeIndex(pd.to_datetime(bars["bitcoin"]["open_time"], utc=True))
    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(hours=23, minutes=59)
    bar_index = btc_times[(btc_times >= start_ts) & (btc_times <= end_ts)].sort_values()
    open_frame, close_frame = build_price_panels(bars, index=bar_index)
    assets = [
        asset
        for asset in target_assets
        if asset in open_frame.columns and asset in close_frame.columns
    ]
    open_frame = open_frame[["bitcoin", *assets]]
    close_frame = close_frame[["bitcoin", *assets]]
    membership = build_membership(
        universe,
        index=pd.DatetimeIndex(close_frame.index),
        assets=assets,
    )
    returns = (
        np.log(close_frame.where(close_frame > 0.0) / close_frame.where(close_frame > 0.0).shift(1))
        .replace([np.inf, -np.inf], np.nan)
    )
    btc_returns = returns["bitcoin"]
    market_var = btc_returns.rolling(BETA_WINDOW_BARS, min_periods=MIN_BETA_OBSERVATIONS).var(ddof=1)
    alpha_cov = returns[assets].rolling(
        BETA_WINDOW_BARS,
        min_periods=MIN_BETA_OBSERVATIONS,
    ).cov(btc_returns)
    beta = alpha_cov.div(market_var, axis=0).replace([np.inf, -np.inf], np.nan)
    beta = beta.clip(*BETA_CLIP)
    bar_returns = (close_frame[assets] / open_frame[assets].where(open_frame[assets] > 0.0) - 1.0)
    return open_frame, close_frame, membership, beta, bar_returns


def _select_cross_section(
    gap_row: pd.Series,
    eligible: pd.Series,
    quantile: float = QUANTILE,
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """Select low-gap long and high-gap short names for one signal bar."""
    if not 0.0 < quantile < 0.5:
        raise ValueError("quantile must be in (0, 0.5)")
    common = eligible & gap_row.notna() & np.isfinite(gap_row)
    assets = common.index[common]
    if len(assets) < MIN_CROSS_SECTION:
        return None
    gap = gap_row.loc[assets].astype(float)
    if gap.nunique() < 2:
        return None
    leg_count = max(1, int(np.ceil(len(gap) * quantile)))
    long_assets = tuple(
        sorted((str(asset) for asset in gap.nsmallest(leg_count).index), key=str.casefold)
    )
    short_assets = tuple(
        sorted((str(asset) for asset in gap.nlargest(leg_count).index), key=str.casefold)
    )
    if set(long_assets) & set(short_assets):
        return None
    return long_assets, short_assets


def build_signal_gap(
    *,
    variant: LeadLagVariant,
    close_frame: pd.DataFrame,
    beta: pd.DataFrame,
    assets: list[str],
) -> tuple[pd.DataFrame, pd.Series]:
    """Return the beta-adjusted cross-sectional gap and normalized BTC shock."""
    signal_returns = signal_window_return(close_frame, variant.signal_bars)[assets]
    btc_shock = signal_window_return(
        close_frame[["bitcoin"]], variant.signal_bars
    )["bitcoin"]
    shock_std = btc_shock.rolling(
        BETA_WINDOW_BARS,
        min_periods=MIN_BETA_OBSERVATIONS,
    ).std(ddof=1)
    shock_z = (btc_shock / shock_std).replace([np.inf, -np.inf], np.nan)
    gap = signal_returns.sub(beta.mul(btc_shock, axis=0))
    return gap, shock_z


def build_events(
    *,
    variant: LeadLagVariant,
    close_frame: pd.DataFrame,
    beta: pd.DataFrame,
    membership: pd.DataFrame,
    assets: list[str],
) -> list[TradeEvent]:
    """Build capacity-constrained signal events for one frozen cell."""
    gap, shock_z = build_signal_gap(
        variant=variant,
        close_frame=close_frame,
        beta=beta,
        assets=assets,
    )
    events: list[TradeEvent] = []
    active_exits: list[int] = []
    for position in range(len(close_frame)):
        # A tranche exiting at this bar's close frees its slot for the next
        # bar's open, which is when a newly accepted signal would enter.
        active_exits = [value for value in active_exits if value > position]
        entry_position = position + 1
        exit_position = position + variant.future_bars
        if exit_position >= len(close_frame):
            continue
        z = shock_z.iloc[position]
        if not np.isfinite(z) or abs(float(z)) < SHOCK_THRESHOLD:
            continue
        if len(active_exits) >= variant.future_bars:
            continue
        selected = _select_cross_section(gap.iloc[position], membership.iloc[position])
        if selected is None:
            continue
        long_assets, short_assets = selected
        events.append(
            TradeEvent(
                variant_id=variant.variant_id,
                signal_position=position,
                entry_position=entry_position,
                exit_position=exit_position,
                signal_time=pd.Timestamp(close_frame.index[position]),
                entry_time=pd.Timestamp(close_frame.index[entry_position]),
                exit_time=pd.Timestamp(close_frame.index[exit_position]),
                z=float(z),
                long_assets=long_assets,
                short_assets=short_assets,
            )
        )
        active_exits.append(exit_position)
    return events


def simulate_events(
    *,
    events: Iterable[TradeEvent],
    bar_returns: pd.DataFrame,
    n_bars: int,
    future_bars: int,
    cost_bps_per_side: float,
    tranche_gross: float | None = None,
) -> dict[str, Any]:
    """Run one capacity-constrained tranche portfolio and return bar returns."""
    if cost_bps_per_side < 0.0 or not np.isfinite(cost_bps_per_side):
        raise ValueError("cost_bps_per_side must be finite and non-negative")
    bar_pnl = np.zeros(n_bars, dtype=float)
    active_gross = np.zeros(n_bars, dtype=float)
    asset_pnl: dict[str, float] = defaultdict(float)
    missing = 0
    turnover = 0.0
    event_list = list(events)
    tranche_gross = (
        1.0 / float(future_bars)
        if tranche_gross is None
        else float(tranche_gross)
    )
    if not np.isfinite(tranche_gross) or not 0.0 < tranche_gross <= 1.0:
        raise ValueError("tranche_gross must be finite and in (0, 1]")
    cost = float(cost_bps_per_side) / 10_000.0
    for event in event_list:
        long_weight = 0.5 * tranche_gross / len(event.long_assets)
        short_weight = 0.5 * tranche_gross / len(event.short_assets)
        for position in range(event.entry_position, event.exit_position + 1):
            active_gross[position] += tranche_gross
            row = bar_returns.iloc[position]
            for asset in event.long_assets:
                value = row.get(asset, np.nan)
                if not np.isfinite(value):
                    missing += 1
                    continue
                pnl = long_weight * float(value)
                bar_pnl[position] += pnl
                asset_pnl[asset] += pnl
            for asset in event.short_assets:
                value = row.get(asset, np.nan)
                if not np.isfinite(value):
                    missing += 1
                    continue
                pnl = -short_weight * float(value)
                bar_pnl[position] += pnl
                asset_pnl[asset] += pnl
        bar_pnl[event.entry_position] -= tranche_gross * cost
        bar_pnl[event.exit_position] -= tranche_gross * cost
        turnover += 2.0 * tranche_gross
    return {
        "bar_returns": pd.Series(bar_pnl, index=bar_returns.index, dtype=float),
        "active_gross": pd.Series(active_gross, index=bar_returns.index, dtype=float),
        "asset_pnl": dict(asset_pnl),
        "missing_return_observations": missing,
        "turnover": turnover,
        "events": event_list,
    }


def _daily_returns(bar_returns: pd.Series) -> pd.Series:
    clean = pd.to_numeric(bar_returns, errors="coerce").fillna(0.0)
    daily = (1.0 + clean).resample("1D").prod() - 1.0
    index = pd.DatetimeIndex(daily.index)
    daily.index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    return daily.fillna(0.0)


def _sample_metrics(
    daily: pd.Series,
    bitcoin: pd.Series,
    *,
    variant_id: str,
    cost_bps: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample, (start, end) in SAMPLE_WINDOWS.items():
        lower = pd.Timestamp(start, tz="UTC")
        upper = pd.Timestamp(end, tz="UTC")
        segment = daily.loc[(daily.index >= lower) & (daily.index <= upper)]
        btc = bitcoin.loc[(bitcoin.index >= lower) & (bitcoin.index <= upper)]
        metrics = _metrics_from_returns(segment)
        btc_metrics = _metrics_from_returns(btc)
        rows.append(
            {
                "variant_id": variant_id,
                "sample": sample,
                "cost_bps_per_side": cost_bps,
                "days": len(segment),
                **metrics,
                "bitcoin_multiple": btc_metrics["multiple"],
                "bitcoin_sharpe": btc_metrics["sharpe"],
                "bitcoin_max_drawdown": btc_metrics["max_drawdown"],
            }
        )
    return rows


def _tier(
    *,
    full_6: Mapping[str, float],
    discovery_6: Mapping[str, float],
    validation_6: Mapping[str, float],
    full_12: Mapping[str, float],
) -> str:
    if (
        float(full_6["sharpe"]) > 1.0
        and float(full_6["max_drawdown"]) > -0.30
        and float(discovery_6["sharpe"]) > 0.5
        and float(validation_6["sharpe"]) > 0.5
        and float(full_12["multiple"]) > 1.0
    ):
        return "candidate-for-shadow"
    if float(full_12["multiple"]) > 1.0:
        return "watch"
    return "rejected-now"


def _report(
    metrics: pd.DataFrame,
    variants: pd.DataFrame,
    *,
    start: str,
    end: str,
) -> str:
    base = metrics.loc[metrics["cost_bps_per_side"] == BASE_COST].copy()
    base["series"] = base["variant_id"]
    table = base[
        [
            "series",
            "sample",
            "days",
            "multiple",
            "cagr",
            "sharpe",
            "max_drawdown",
            "bitcoin_multiple",
            "bitcoin_sharpe",
        ]
    ].sort_values(["series", "sample"], kind="stable")
    summary = variants[
        [
            "variant_id",
            "tier",
            "events",
            "average_active_gross",
            "max_active_gross",
            "turnover",
            "missing_return_observations",
            "full_multiple_6",
            "full_sharpe_6",
            "full_mdd_6",
            "validation_sharpe_6",
            "full_multiple_12",
        ]
    ].copy()
    lines = [
        "# Intraday BTC shock lead-lag backtest",
        "",
        "- status: research backtest only; no orders; no live changes",
        f"- sample: {start} → {end}",
        "- execution: signal close -> next 30m open; hold 2h or 4h; gross <= 1.0x",
        "- costs: 6/12/20bps per one-way gross turnover; funding excluded",
        "- discovery: 2022-01-01 → 2023-12-31; validation: 2024-01-01 → 2026-09-30",
        "",
        "## Variant summary",
        "",
        dataframe_to_markdown(summary.reset_index(drop=True)),
        "",
        "## 6bps sample metrics",
        "",
        dataframe_to_markdown(table.reset_index(drop=True)),
        "",
        "## Interpretation guardrail",
        "",
        "This uses Binance 30m OHLC as a fill proxy, fixed slot sizing, equal-weight "
        "quintile legs, zero-filled missing asset bars with a reported count, and no funding. "
        "A positive result is not an executable order or a live approval. Before promotion it "
        "still needs Bitget order-book/trade-tape fills, minimum-size and partial-fill tests, "
        "funding at 8h settlement boundaries, and a fresh OOS window that was not used in the "
        "LS63 diagnostic.",
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
            "the registered backtest expects 2022-01-01 → 2026-09-30; "
            "register a new study for another window"
        )

    open_frame, close_frame, membership, beta, bar_returns = _prepare_market(
        config=args.config,
        start_date=args.start_date,
        end_date=args.end_date,
        bar_dir=args.bar_dir,
    )
    assets = list(bar_returns.columns)
    bitcoin_daily = (
        close_frame["bitcoin"].resample("1D").last().pct_change(fill_method=None).fillna(0.0)
    )
    bitcoin_index = pd.DatetimeIndex(bitcoin_daily.index)
    bitcoin_daily.index = (
        bitcoin_index.tz_localize("UTC")
        if bitcoin_index.tz is None
        else bitcoin_index.tz_convert("UTC")
    )

    results: dict[str, dict[float, dict[str, Any]]] = {}
    events_by_variant: dict[str, list[TradeEvent]] = {}
    for variant in VARIANTS:
        events = build_events(
            variant=variant,
            close_frame=close_frame,
            beta=beta,
            membership=membership,
            assets=assets,
        )
        events_by_variant[variant.variant_id] = events
        results[variant.variant_id] = {}
        for cost in COSTS_PER_SIDE:
            results[variant.variant_id][cost] = simulate_events(
                events=events,
                bar_returns=bar_returns,
                n_bars=len(bar_returns),
                future_bars=variant.future_bars,
                cost_bps_per_side=cost,
            )

    # The ensemble allocates one quarter of capital to each frozen cell.  It
    # never adds gross: every component has gross <= 1 and the weighted average
    # therefore remains <= 1.
    for cost in COSTS_PER_SIDE:
        component_returns = [
            results[variant.variant_id][cost]["bar_returns"]
            for variant in VARIANTS
        ]
        results["LL_ENSEMBLE"] = results.get("LL_ENSEMBLE", {})
        results["LL_ENSEMBLE"][cost] = {
            "bar_returns": sum(component_returns) / len(component_returns),
            "active_gross": sum(
                results[variant.variant_id][cost]["active_gross"]
                for variant in VARIANTS
            )
            / len(VARIANTS),
            "asset_pnl": {
                asset: sum(
                    results[variant.variant_id][cost]["asset_pnl"].get(asset, 0.0)
                    for variant in VARIANTS
                )
                / len(VARIANTS)
                for asset in assets
            },
            "missing_return_observations": sum(
                results[variant.variant_id][cost]["missing_return_observations"]
                for variant in VARIANTS
            ),
            "turnover": sum(
                results[variant.variant_id][cost]["turnover"]
                for variant in VARIANTS
            )
            / len(VARIANTS),
            "events": [],
        }

    metric_rows: list[dict[str, Any]] = []
    daily_columns: dict[str, pd.Series] = {}
    for series_id, cost_map in results.items():
        for cost, result in cost_map.items():
            daily = _daily_returns(result["bar_returns"])
            daily_columns[f"{series_id}__cost{cost:g}"] = daily
            metric_rows.extend(
                _sample_metrics(
                    daily,
                    bitcoin_daily,
                    variant_id=series_id,
                    cost_bps=cost,
                )
            )
    metrics = pd.DataFrame(metric_rows)
    daily_frame = pd.DataFrame(daily_columns).sort_index().fillna(0.0)

    variant_rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        result_6 = results[variant.variant_id][6.0]
        full_6 = metrics.loc[
            (metrics["variant_id"] == variant.variant_id)
            & (metrics["sample"] == "full")
            & (metrics["cost_bps_per_side"] == 6.0)
        ].iloc[0]
        discovery_6 = metrics.loc[
            (metrics["variant_id"] == variant.variant_id)
            & (metrics["sample"] == "discovery")
            & (metrics["cost_bps_per_side"] == 6.0)
        ].iloc[0]
        validation_6 = metrics.loc[
            (metrics["variant_id"] == variant.variant_id)
            & (metrics["sample"] == "validation")
            & (metrics["cost_bps_per_side"] == 6.0)
        ].iloc[0]
        full_12 = metrics.loc[
            (metrics["variant_id"] == variant.variant_id)
            & (metrics["sample"] == "full")
            & (metrics["cost_bps_per_side"] == 12.0)
        ].iloc[0]
        variant_rows.append(
            {
                "variant_id": variant.variant_id,
                "signal_bars": variant.signal_bars,
                "future_bars": variant.future_bars,
                "tier": _tier(
                    full_6=full_6,
                    discovery_6=discovery_6,
                    validation_6=validation_6,
                    full_12=full_12,
                ),
                "events": len(events_by_variant[variant.variant_id]),
                "average_active_gross": float(result_6["active_gross"].mean()),
                "max_active_gross": float(result_6["active_gross"].max()),
                "turnover": float(result_6["turnover"]),
                "missing_return_observations": int(
                    result_6["missing_return_observations"]
                ),
                "full_multiple_6": float(full_6["multiple"]),
                "full_sharpe_6": float(full_6["sharpe"]),
                "full_mdd_6": float(full_6["max_drawdown"]),
                "validation_sharpe_6": float(validation_6["sharpe"]),
                "full_multiple_12": float(full_12["multiple"]),
            }
        )
    ensemble_full_6 = metrics.loc[
        (metrics["variant_id"] == "LL_ENSEMBLE")
        & (metrics["sample"] == "full")
        & (metrics["cost_bps_per_side"] == 6.0)
    ].iloc[0]
    ensemble_discovery_6 = metrics.loc[
        (metrics["variant_id"] == "LL_ENSEMBLE")
        & (metrics["sample"] == "discovery")
        & (metrics["cost_bps_per_side"] == 6.0)
    ].iloc[0]
    ensemble_validation_6 = metrics.loc[
        (metrics["variant_id"] == "LL_ENSEMBLE")
        & (metrics["sample"] == "validation")
        & (metrics["cost_bps_per_side"] == 6.0)
    ].iloc[0]
    ensemble_full_12 = metrics.loc[
        (metrics["variant_id"] == "LL_ENSEMBLE")
        & (metrics["sample"] == "full")
        & (metrics["cost_bps_per_side"] == 12.0)
    ].iloc[0]
    ensemble_result = results["LL_ENSEMBLE"][6.0]
    variant_rows.append(
        {
            "variant_id": "LL_ENSEMBLE",
            "signal_bars": None,
            "future_bars": None,
            "tier": _tier(
                full_6=ensemble_full_6,
                discovery_6=ensemble_discovery_6,
                validation_6=ensemble_validation_6,
                full_12=ensemble_full_12,
            ),
            "events": sum(len(value) for value in events_by_variant.values()),
            "average_active_gross": float(ensemble_result["active_gross"].mean()),
            "max_active_gross": float(ensemble_result["active_gross"].max()),
            "turnover": float(ensemble_result["turnover"]),
            "missing_return_observations": int(ensemble_result["missing_return_observations"]),
            "full_multiple_6": float(ensemble_full_6["multiple"]),
            "full_sharpe_6": float(ensemble_full_6["sharpe"]),
            "full_mdd_6": float(ensemble_full_6["max_drawdown"]),
            "validation_sharpe_6": float(ensemble_validation_6["sharpe"]),
            "full_multiple_12": float(ensemble_full_12["multiple"]),
        }
    )
    variants_frame = pd.DataFrame(variant_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "metrics": output_dir / "sample_metrics.csv",
        "variants": output_dir / "variant_summary.csv",
        "daily": output_dir / "daily_returns.csv",
        "events": output_dir / "events.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")

    event_rows: list[dict[str, Any]] = []
    for variant_id, events in events_by_variant.items():
        for event in events:
            event_rows.append(
                {
                    **asdict(event),
                    "long_assets": "|".join(event.long_assets),
                    "short_assets": "|".join(event.short_assets),
                }
            )
    metrics.to_csv(files["metrics"], index=False)
    variants_frame.to_csv(files["variants"], index=False)
    daily_frame.to_csv(files["daily"], index=True)
    pd.DataFrame(event_rows).to_csv(files["events"], index=False)
    files["report"].write_text(
        _report(metrics, variants_frame, start=args.start_date, end=args.end_date),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS64-INTRADAY-BTC-LEADLAG",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "variants": [asdict(variant) for variant in VARIANTS],
        "ensemble": True,
        "shock_threshold": SHOCK_THRESHOLD,
        "quantile": QUANTILE,
        "costs_per_side": list(COSTS_PER_SIDE),
        "base_cost_per_side": BASE_COST,
        "funding_included": False,
        "orders_sent": False,
        "bar_count": int(len(bar_returns)),
        "asset_count": len(assets),
        "assets": assets,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir} with {len(variants_frame)} variants")


if __name__ == "__main__":
    main()
