"""Follow-up LS66 backtest for the selected phase-0 lead-lag cells."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_intraday_btc_leadlag_backtest import (  # noqa: E402
    BASE_COST,
    COSTS_PER_SIDE,
    DEFAULT_END,
    DEFAULT_START,
    TradeEvent,
    _daily_returns,
    _prepare_market,
    _sample_metrics,
    _select_cross_section,
    _tier,
    build_signal_gap,
    simulate_events,
)

TAIL = 0.10
PHASE = 0


@dataclass(frozen=True)
class PhaseVariant:
    variant_id: str
    signal_bars: int
    future_bars: int
    shock_threshold: float


VARIANTS = (
    PhaseVariant("LL_P2_8_T30", 2, 8, 3.0),
    PhaseVariant("LL_P2_8_T35", 2, 8, 3.5),
    PhaseVariant("LL_P4_8_T30", 4, 8, 3.0),
    PhaseVariant("LL_P4_8_T35", 4, 8, 3.5),
)


def build_phase_events(
    *,
    variant: PhaseVariant,
    close_frame: pd.DataFrame,
    beta: pd.DataFrame,
    membership: pd.DataFrame,
    assets: list[str],
) -> list[TradeEvent]:
    gap, shock_z = build_signal_gap(
        variant=variant,
        close_frame=close_frame,
        beta=beta,
        assets=assets,
    )
    events: list[TradeEvent] = []
    for position in range(PHASE, len(close_frame), variant.future_bars):
        entry_position = position + 1
        exit_position = position + variant.future_bars
        if exit_position >= len(close_frame):
            continue
        z = shock_z.iloc[position]
        if not pd.notna(z) or abs(float(z)) < variant.shock_threshold:
            continue
        selected = _select_cross_section(
            gap.iloc[position],
            membership.iloc[position],
            quantile=TAIL,
        )
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
    return events


def _report(metrics: pd.DataFrame, variants: pd.DataFrame) -> str:
    base = metrics.loc[metrics["cost_bps_per_side"] == BASE_COST].copy()
    table = base[
        [
            "variant_id",
            "sample",
            "days",
            "multiple",
            "cagr",
            "sharpe",
            "max_drawdown",
            "bitcoin_multiple",
            "bitcoin_sharpe",
        ]
    ].sort_values(["variant_id", "sample"], kind="stable")
    summary = variants[
        [
            "variant_id",
            "tier",
            "events",
            "events_per_year",
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
    return "\n".join(
        [
            "# Intraday BTC lead-lag phase/tail follow-up",
            "",
            "- status: research backtest only; no orders; no live changes",
            "- construction: phase-0 UTC schedule, tail 10%, one full-gross event at a time",
            "- thresholds: abs(z) >= 3.0 / 3.5 on k=2/4, h=8",
            "- costs: 6/12/20bps per one-way gross turnover; funding excluded",
            "",
            "## Variant summary",
            "",
            dataframe_to_markdown(summary.reset_index(drop=True)),
            "",
            "## 6bps sample metrics",
            "",
            dataframe_to_markdown(table.reset_index(drop=True)),
            "",
            "## Selection-bias warning",
            "",
            "Phase 0, the 10% tails and the 3.0/3.5 thresholds were observed in the preceding "
            "LS63–LS65 research. This is therefore a phase-selected follow-up, not a fresh OOS. "
            "The validation window is reported only to test whether the selected mechanism survived "
            "the later sample; it cannot validate a live strategy by itself.",
            "",
            "## Execution guardrail",
            "",
            "Binance 30m OHLC is a fill proxy. Funding, Bitget book depth, partial fills, minimum "
            "notional, hidden liquidity and a fresh post-2026-09-30 OOS are absent. This result can "
            "only justify a shadow execution study, never an automatic live change.",
            "",
        ]
    )


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
        parser.error("the registered LS66 backtest expects 2022-01-01 → 2026-09-30")

    _, close_frame, membership, beta, bar_returns = _prepare_market(
        config=args.config,
        start_date=args.start_date,
        end_date=args.end_date,
        bar_dir=args.bar_dir,
    )
    assets = list(bar_returns.columns)
    bitcoin_daily = (
        close_frame["bitcoin"].resample("1D").last().pct_change(fill_method=None).fillna(0.0)
    )
    btc_index = pd.DatetimeIndex(bitcoin_daily.index)
    bitcoin_daily.index = (
        btc_index.tz_localize("UTC") if btc_index.tz is None else btc_index.tz_convert("UTC")
    )

    results: dict[str, dict[float, dict[str, Any]]] = {}
    events_by_variant: dict[str, list[TradeEvent]] = {}
    for variant in VARIANTS:
        events = build_phase_events(
            variant=variant,
            close_frame=close_frame,
            beta=beta,
            membership=membership,
            assets=assets,
        )
        events_by_variant[variant.variant_id] = events
        results[variant.variant_id] = {
            cost: simulate_events(
                events=events,
                bar_returns=bar_returns,
                n_bars=len(bar_returns),
                future_bars=variant.future_bars,
                cost_bps_per_side=cost,
                tranche_gross=1.0,
            )
            for cost in COSTS_PER_SIDE
        }

    for cost in COSTS_PER_SIDE:
        component_returns = [
            results[variant.variant_id][cost]["bar_returns"] for variant in VARIANTS
        ]
        results["LL_PHASE_ENSEMBLE"] = results.get("LL_PHASE_ENSEMBLE", {})
        results["LL_PHASE_ENSEMBLE"][cost] = {
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

    def metric(series_id: str, sample: str, cost: float) -> Mapping[str, float]:
        return metrics.loc[
            (metrics["variant_id"] == series_id)
            & (metrics["sample"] == sample)
            & (metrics["cost_bps_per_side"] == cost)
        ].iloc[0]

    variant_rows: list[dict[str, Any]] = []
    all_ids = [variant.variant_id for variant in VARIANTS] + ["LL_PHASE_ENSEMBLE"]
    for variant_id in all_ids:
        event_count = (
            sum(len(events) for events in events_by_variant.values())
            if variant_id == "LL_PHASE_ENSEMBLE"
            else len(events_by_variant[variant_id])
        )
        result = results[variant_id][6.0]
        full_6 = metric(variant_id, "full", 6.0)
        discovery_6 = metric(variant_id, "discovery", 6.0)
        validation_6 = metric(variant_id, "validation", 6.0)
        full_12 = metric(variant_id, "full", 12.0)
        variant_spec = next(
            (item for item in VARIANTS if item.variant_id == variant_id), None
        )
        variant_rows.append(
            {
                "variant_id": variant_id,
                "signal_bars": None if variant_spec is None else variant_spec.signal_bars,
                "future_bars": None if variant_spec is None else variant_spec.future_bars,
                "shock_threshold": None if variant_spec is None else variant_spec.shock_threshold,
                "tier": _tier(
                    full_6=full_6,
                    discovery_6=discovery_6,
                    validation_6=validation_6,
                    full_12=full_12,
                ),
                "events": event_count,
                "events_per_year": event_count / 4.75,
                "average_active_gross": float(result["active_gross"].mean()),
                "max_active_gross": float(result["active_gross"].max()),
                "turnover": float(result["turnover"]),
                "missing_return_observations": int(result["missing_return_observations"]),
                "full_multiple_6": float(full_6["multiple"]),
                "full_sharpe_6": float(full_6["sharpe"]),
                "full_mdd_6": float(full_6["max_drawdown"]),
                "validation_sharpe_6": float(validation_6["sharpe"]),
                "full_multiple_12": float(full_12["multiple"]),
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

    event_rows = [
        {
            **asdict(event),
            "long_assets": "|".join(event.long_assets),
            "short_assets": "|".join(event.short_assets),
        }
        for events in events_by_variant.values()
        for event in events
    ]
    metrics.to_csv(files["metrics"], index=False)
    variants_frame.to_csv(files["variants"], index=False)
    daily_frame.to_csv(files["daily"], index=True)
    pd.DataFrame(event_rows).to_csv(files["events"], index=False)
    files["report"].write_text(_report(metrics, variants_frame), encoding="utf-8")
    manifest = {
        "candidate_family_id": "PR2026-11-LS66-INTRADAY-LEADLAG-PHASE-TAIL",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "phase": PHASE,
        "tail": TAIL,
        "variants": [asdict(variant) for variant in VARIANTS],
        "ensemble": True,
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
