"""Fresh post-2026-09-30 OOS check for the frozen LS66 lead-lag cells."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import asdict
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
    TradeEvent,
    _daily_returns,
    _prepare_market,
    _select_cross_section,
    build_signal_gap,
    simulate_events,
)
from scripts.run_intraday_btc_leadlag_phase_backtest import (  # noqa: E402
    PHASE,
    TAIL,
    VARIANTS,
    PhaseVariant,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

DEFAULT_START = "2026-09-01"
DEFAULT_END = "2026-11-13"
DEFAULT_OOS_START = "2026-10-01"
COSTS = (6.0, 12.0, 20.0)


def _utc_timestamp(value: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize("UTC") if timestamp.tz is None else timestamp.tz_convert("UTC")


def build_oos_events(
    *,
    variant: PhaseVariant,
    close_frame: pd.DataFrame,
    beta: pd.DataFrame,
    membership: pd.DataFrame,
    assets: list[str],
    oos_start: pd.Timestamp,
    oos_end: pd.Timestamp,
) -> list[TradeEvent]:
    """Build phase-0 events whose complete holding period lies inside the OOS."""
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
        entry_time = pd.Timestamp(close_frame.index[entry_position])
        exit_time = pd.Timestamp(close_frame.index[exit_position])
        if entry_time < oos_start or exit_time > oos_end:
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
                entry_time=entry_time,
                exit_time=exit_time,
                z=float(z),
                long_assets=long_assets,
                short_assets=short_assets,
            )
        )
    return events


def _tier(full_6: Mapping[str, float], full_12: Mapping[str, float]) -> str:
    if float(full_6["multiple"]) > 1.0 and float(full_12["multiple"]) > 1.0 and float(full_6["max_drawdown"]) > -0.15:
        return "fresh-oos-positive"
    if float(full_6["multiple"]) > 1.0:
        return "fresh-oos-mixed"
    return "fresh-oos-failed"


def _coverage_rows(bar_dir: Path) -> list[dict[str, Any]]:
    coverage = json.loads((bar_dir / "coverage.json").read_text(encoding="utf-8"))
    return [
        {
            "coin_id": coin,
            "available": bool(info.get("available")),
            "pair": info.get("pair"),
            "rows": int(info.get("rows", 0)),
            "first": info.get("first"),
            "last": info.get("last"),
        }
        for coin, info in sorted(coverage.items())
    ]


def _report(
    metrics: pd.DataFrame,
    coverage: pd.DataFrame,
    *,
    start: str,
    end: str,
    oos_start: str,
) -> str:
    table = metrics[
        [
            "variant_id",
            "cost_bps_per_side",
            "tier",
            "events",
            "multiple",
            "cagr",
            "sharpe",
            "max_drawdown",
            "bitcoin_multiple",
            "bitcoin_sharpe",
        ]
    ].sort_values(["variant_id", "cost_bps_per_side"], kind="stable")
    missing = coverage.loc[~coverage["available"], "coin_id"].tolist()
    return "\n".join(
        [
            "# Intraday BTC lead-lag fresh OOS",
            "",
            "- status: fresh shadow validation only; no orders; no live changes",
            f"- data window: {start} → {end}; OOS entries: {oos_start} → {end}",
            "- frozen rules: phase-0 UTC, tail 10%, thresholds 3.0/3.5, single full-gross event",
            "- costs: 6/12/20bps per one-way gross turnover; funding excluded",
            "",
            "## Coverage warning",
            "",
            f"- unavailable assets in the new cache: **{', '.join(missing) if missing else 'none'}**",
            "- no historical 30m bars were spliced into this OOS; missing assets are excluded for the whole run",
            "",
            "## Frozen variants",
            "",
            dataframe_to_markdown(table.reset_index(drop=True)),
            "",
            "The tier is assigned from the 6bps/12bps pair; the 20bps row is shown separately and "
            "does not inherit a positive label by itself.",
            "",
            "## Interpretation",
            "",
            "This window is short and has low event power. A positive result only keeps LS66 as a "
            "shadow candidate; a failed result rejects the frozen LS66 cells without re-tuning phase, "
            "tail or threshold on the same data.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--bar-dir", type=Path, required=True)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--oos-start", default=DEFAULT_OOS_START)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date >= args.end_date:
        parser.error("--start-date must be before --end-date")
    if not (args.start_date < args.oos_start <= args.end_date):
        parser.error("--oos-start must lie inside the requested data window")

    _, close_frame, membership, beta, bar_returns = _prepare_market(
        config=args.config,
        start_date=args.start_date,
        end_date=args.end_date,
        bar_dir=args.bar_dir,
    )
    assets = list(bar_returns.columns)
    oos_start = _utc_timestamp(args.oos_start)
    oos_end = _utc_timestamp(args.end_date) + pd.Timedelta(hours=23, minutes=59)
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
        events = build_oos_events(
            variant=variant,
            close_frame=close_frame,
            beta=beta,
            membership=membership,
            assets=assets,
            oos_start=oos_start,
            oos_end=oos_end,
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
            for cost in COSTS
        }

    for cost in COSTS:
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
            "turnover": sum(
                results[variant.variant_id][cost]["turnover"]
                for variant in VARIANTS
            )
            / len(VARIANTS),
            "missing_return_observations": sum(
                results[variant.variant_id][cost]["missing_return_observations"]
                for variant in VARIANTS
            ),
        }

    metric_rows: list[dict[str, Any]] = []
    daily_columns: dict[str, pd.Series] = {}
    btc_segment = bitcoin_daily.loc[
        (bitcoin_daily.index >= oos_start) & (bitcoin_daily.index <= oos_end)
    ]
    btc_metrics = _metrics_from_returns(btc_segment)
    for variant_id, cost_map in results.items():
        for cost, result in cost_map.items():
            daily = _daily_returns(result["bar_returns"])
            daily_columns[f"{variant_id}__cost{cost:g}"] = daily
            segment = daily.loc[(daily.index >= oos_start) & (daily.index <= oos_end)]
            metrics = _metrics_from_returns(segment)
            metric_rows.append(
                {
                    "variant_id": variant_id,
                    "cost_bps_per_side": cost,
                    "tier": None,
                    "events": (
                        sum(len(events) for events in events_by_variant.values())
                        if variant_id == "LL_PHASE_ENSEMBLE"
                        else len(events_by_variant[variant_id])
                    ),
                    "days": len(segment),
                    **metrics,
                    "bitcoin_multiple": btc_metrics["multiple"],
                    "bitcoin_sharpe": btc_metrics["sharpe"],
                    "turnover": float(result["turnover"]),
                    "max_active_gross": float(result["active_gross"].max()),
                    "missing_return_observations": int(
                        result["missing_return_observations"]
                    ),
                }
            )
    metrics_frame = pd.DataFrame(metric_rows)
    for variant_id in [*[variant.variant_id for variant in VARIANTS], "LL_PHASE_ENSEMBLE"]:
        six = metrics_frame.loc[
            (metrics_frame["variant_id"] == variant_id)
            & (metrics_frame["cost_bps_per_side"] == 6.0)
        ].iloc[0]
        twelve = metrics_frame.loc[
            (metrics_frame["variant_id"] == variant_id)
            & (metrics_frame["cost_bps_per_side"] == 12.0)
        ].iloc[0]
        metrics_frame.loc[
            metrics_frame["variant_id"] == variant_id, "tier"
        ] = _tier(six, twelve)
    day_frame = pd.DataFrame(daily_columns).sort_index().fillna(0.0)
    coverage = pd.DataFrame(_coverage_rows(args.bar_dir))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "metrics": output_dir / "oos_metrics.csv",
        "daily": output_dir / "daily_returns.csv",
        "events": output_dir / "events.csv",
        "coverage": output_dir / "coverage.csv",
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
    metrics_frame.to_csv(files["metrics"], index=False)
    day_frame.to_csv(files["daily"], index=True)
    pd.DataFrame(event_rows).to_csv(files["events"], index=False)
    coverage.to_csv(files["coverage"], index=False)
    files["report"].write_text(
        _report(
            metrics_frame,
            coverage,
            start=args.start_date,
            end=args.end_date,
            oos_start=args.oos_start,
        ),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS67-INTRADAY-LEADLAG-FRESH-OOS",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "oos_start": args.oos_start,
        "bar_dir": str(args.bar_dir),
        "variants": [asdict(variant) for variant in VARIANTS],
        "phase": PHASE,
        "tail": TAIL,
        "costs_per_side": list(COSTS),
        "available_assets": int(coverage["available"].sum()),
        "missing_assets": coverage.loc[~coverage["available"], "coin_id"].tolist(),
        "orders_sent": False,
        "funding_included": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir} with {len(metrics_frame)} OOS rows")


if __name__ == "__main__":
    main()
