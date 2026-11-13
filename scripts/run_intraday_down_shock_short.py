"""Backtest the frozen intraday down-shock weak-tail short family.

This is a research-only event study.  It shorts the weakest relative-gap alts
after a negative BTC shock, never sends orders, and never changes the live
target book.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_intraday_btc_leadlag_backtest import (  # noqa: E402
    BETA_CLIP,
    BETA_WINDOW_BARS,
    MIN_BETA_OBSERVATIONS,
    LeadLagVariant,
    _daily_returns,
    _prepare_market,
    _select_cross_section,
    build_signal_gap,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-09-30"
DEFAULT_OOS_START = "2026-09-01"
DEFAULT_OOS_END = "2026-11-13"
OOS_EVALUATION_START = "2026-10-01"
COSTS_PER_SIDE = (6.0, 12.0, 20.0)
SIGNAL_BARS = (1, 2, 4)
SHOCK_THRESHOLDS = (2.5, 3.0)
HOLD_BARS = (4, 8, 16)
TAIL = 0.10
MIN_CROSS_SECTION = 8
LS57_RETURNS = Path(
    "reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/"
    "PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/daily_returns.csv"
)
SAMPLE_WINDOWS: dict[str, tuple[str, str]] = {
    "full": (DEFAULT_START, DEFAULT_END),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", DEFAULT_END),
    "oos": (OOS_EVALUATION_START, DEFAULT_OOS_END),
}


@dataclass(frozen=True)
class DownShockVariant:
    variant_id: str
    signal_bars: int
    shock_threshold: float
    hold_bars: int


@dataclass(frozen=True)
class ShortEvent:
    variant_id: str
    signal_position: int
    entry_position: int
    exit_position: int
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    z: float
    short_assets: tuple[str, ...]


VARIANTS = tuple(
    DownShockVariant(
        variant_id=f"SHORT_DOWN_k{signal_bars}_t{str(threshold).replace('.', '')}_h{hold_bars}",
        signal_bars=signal_bars,
        shock_threshold=threshold,
        hold_bars=hold_bars,
    )
    for signal_bars in SIGNAL_BARS
    for threshold in SHOCK_THRESHOLDS
    for hold_bars in HOLD_BARS
)


def build_short_events(
    *,
    variant: DownShockVariant,
    close_frame: pd.DataFrame,
    beta: pd.DataFrame,
    membership: pd.DataFrame,
    assets: list[str],
) -> list[ShortEvent]:
    """Build negative-shock-only, one-active-event-at-a-time short events."""
    gap, shock_z = build_signal_gap(
        variant=LeadLagVariant(
            variant_id=variant.variant_id,
            signal_bars=variant.signal_bars,
            future_bars=variant.hold_bars,
        ),
        close_frame=close_frame,
        beta=beta,
        assets=assets,
    )
    events: list[ShortEvent] = []
    next_allowed_position = 0
    for position in range(len(close_frame)):
        if position < next_allowed_position:
            continue
        entry_position = position + 1
        exit_position = position + variant.hold_bars
        if exit_position >= len(close_frame):
            continue
        z = shock_z.iloc[position]
        if not pd.notna(z) or float(z) > -float(variant.shock_threshold):
            continue
        selected = _select_cross_section(
            gap.iloc[position],
            membership.iloc[position],
            quantile=TAIL,
        )
        if selected is None:
            continue
        _, short_assets = selected
        events.append(
            ShortEvent(
                variant_id=variant.variant_id,
                signal_position=position,
                entry_position=entry_position,
                exit_position=exit_position,
                signal_time=pd.Timestamp(close_frame.index[position]),
                entry_time=pd.Timestamp(close_frame.index[entry_position]),
                exit_time=pd.Timestamp(close_frame.index[exit_position]),
                z=float(z),
                short_assets=tuple(short_assets),
            )
        )
        next_allowed_position = exit_position
    return events


def simulate_short_events(
    *,
    events: list[ShortEvent],
    bar_returns: pd.DataFrame,
    n_bars: int,
    cost_bps_per_side: float,
    gross: float = 1.0,
) -> dict[str, Any]:
    """Simulate one short leg per event with entry and exit costs."""
    if not np.isfinite(gross) or not 0.0 < gross <= 1.0:
        raise ValueError("gross must be in (0, 1]")
    cost = float(cost_bps_per_side) / 10_000.0
    bar_pnl: dict[int, float] = {position: 0.0 for position in range(n_bars)}
    active_gross = pd.Series(0.0, index=bar_returns.index)
    asset_pnl: defaultdict[str, float] = defaultdict(float)
    missing = 0
    turnover = 0.0
    for event in events:
        short_weight = gross / len(event.short_assets)
        for position in range(event.entry_position, event.exit_position + 1):
            active_gross.iloc[position] += gross
            row = bar_returns.iloc[position]
            for asset in event.short_assets:
                value = row.get(asset, np.nan)
                if not np.isfinite(value):
                    missing += 1
                    continue
                pnl = -short_weight * float(value)
                bar_pnl[position] += pnl
                asset_pnl[asset] += pnl
        bar_pnl[event.entry_position] -= gross * cost
        bar_pnl[event.exit_position] -= gross * cost
        turnover += 2.0 * gross
    series = pd.Series(0.0, index=bar_returns.index, dtype=float)
    for position, value in bar_pnl.items():
        series.iloc[position] = value
    return {
        "bar_returns": series,
        "active_gross": active_gross,
        "asset_pnl": dict(asset_pnl),
        "missing_return_observations": missing,
        "turnover": float(turnover),
        "events": events,
    }


def _sample_metrics(series: pd.Series, sample: str) -> dict[str, float]:
    start, end = SAMPLE_WINDOWS[sample]
    segment = series.loc[
        (series.index >= pd.Timestamp(start, tz="UTC"))
        & (series.index <= pd.Timestamp(end, tz="UTC"))
    ]
    if segment.empty:
        return {
            "multiple": float("nan"),
            "cagr": float("nan"),
            "sharpe": float("nan"),
            "max_drawdown": float("nan"),
        }
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def select_candidate(summary: pd.DataFrame) -> str | None:
    eligible = summary.loc[
        (summary["discovery_sharpe_6"] > 0.0)
        & (summary["discovery_sharpe_12"] > 0.0)
    ].copy()
    if eligible.empty:
        return None
    eligible = eligible.sort_values(
        ["discovery_sharpe_6", "turnover_6", "variant_id"],
        ascending=[False, True, True],
        kind="stable",
    )
    return str(eligible.iloc[0]["variant_id"])


def load_ls57_returns(path: Path = LS57_RETURNS) -> pd.Series:
    frame = pd.read_csv(path)
    date_column = "Unnamed: 0" if "Unnamed: 0" in frame.columns else frame.columns[0]
    index = pd.DatetimeIndex(pd.to_datetime(frame[date_column], utc=True)).sort_values()
    values = pd.to_numeric(frame["equity"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index, name="ls57_20bps")
    if series.isna().any() or not np.isfinite(series.to_numpy(dtype=float)).all():
        raise ValueError("LS57 returns contain missing or non-finite values")
    return series[~series.index.duplicated(keep="last")].sort_index()


def _acceptance_checks(row: Mapping[str, Any], oos: Mapping[str, float]) -> dict[str, bool]:
    return {
        "validation_sharpe_6_positive": float(row["validation_sharpe_6"]) > 0.0,
        "validation_sharpe_12_positive": float(row["validation_sharpe_12"]) > 0.0,
        "oos_6_multiple_above_one": float(oos["multiple"]) > 1.0,
        "full_sharpe_6_above_0_5": float(row["full_sharpe_6"]) > 0.5,
        "full_mdd_no_worse_than_minus_30pct": float(row["full_max_drawdown_6"]) >= -0.30,
        "full_multiple_6_above_one": float(row["full_multiple_6"]) > 1.0,
    }


def _report(
    summary: pd.DataFrame,
    selected: Mapping[str, Any] | None,
    sample_metrics: pd.DataFrame | None,
    acceptance: Mapping[str, bool],
    overlay: pd.DataFrame | None,
    contributions: pd.DataFrame | None,
) -> str:
    ranked = summary.sort_values(
        ["discovery_sharpe_6", "turnover_6"],
        ascending=[False, True],
        kind="stable",
    ).head(18)
    columns = [
        "variant_id",
        "discovery_multiple_6",
        "discovery_sharpe_6",
        "discovery_sharpe_12",
        "validation_multiple_6",
        "validation_sharpe_6",
        "full_multiple_6",
        "full_sharpe_6",
        "full_max_drawdown_6",
        "turnover_6",
        "average_active_gross_6",
        "events",
        "missing_6",
    ]
    lines = [
        "# Intraday down-shock weak-tail short backtest",
        "",
        "- status: research only; no orders; no live changes",
        "- signal: negative BTC shock and lowest relative-gap tail",
        "- execution: 30m signal close → next 30m open; one active event; hold 4/8/16 bars",
        "- costs: 6/12/20bps per side; funding excluded in this screen",
        "",
        "## Discovery-ranked cells",
        "",
        dataframe_to_markdown(ranked[columns].reset_index(drop=True)),
        "",
    ]
    if selected is None:
        lines.extend(
            [
                "## Decision",
                "",
                "No cell passed the discovery-only selection rule; the family is rejected without changing the grid.",
                "",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            "## Selected by discovery only",
            "",
            f"`{selected['variant_id']}`",
            "",
            "## Acceptance checks",
            "",
            *[f"- [{'x' if passed else ' '}] `{name}`" for name, passed in acceptance.items()],
            "",
            "## Sample metrics",
            "",
            dataframe_to_markdown(sample_metrics if sample_metrics is not None else pd.DataFrame()),
            "",
            "## Asset contribution before costs",
            "",
            dataframe_to_markdown(contributions if contributions is not None else pd.DataFrame()),
            "",
            "## Return-space LS57 overlay",
            "",
            "Overlay rows add the short sleeve return to LS57 without modelling margin, gross, funding or execution; diagnostic only.",
            "",
            dataframe_to_markdown(overlay if overlay is not None else pd.DataFrame()),
            "",
            "## Guardrail",
            "",
            "Binance 30m OHLC is a fill proxy. Missing bars are counted and zero-filled only in this screen. A pass requires Bitget mark/order-book, funding and partial-fill verification before any shadow or live decision.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--bar-dir", type=Path, default=Path("data/raw/binance_30m"))
    parser.add_argument("--oos-bar-dir", type=Path, default=Path("data/raw/binance_30m_oos_20261113"))
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--oos-start-date", default=DEFAULT_OOS_START)
    parser.add_argument("--oos-end-date", default=DEFAULT_OOS_END)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date >= args.end_date:
        parser.error("--start-date must be before --end-date")
    if args.start_date != DEFAULT_START or args.end_date != DEFAULT_END:
        parser.error("LS70 is frozen to the registered main window; register another family for another window")

    _, close_frame, membership, beta, bar_returns = _prepare_market(
        config=args.config,
        start_date=args.start_date,
        end_date=args.end_date,
        bar_dir=args.bar_dir,
    )
    assets = list(bar_returns.columns)

    summary_rows: list[dict[str, Any]] = []
    events_by_variant: dict[str, list[ShortEvent]] = {}
    results_6: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        events = build_short_events(
            variant=variant,
            close_frame=close_frame,
            beta=beta,
            membership=membership,
            assets=assets,
        )
        events_by_variant[variant.variant_id] = events
        by_cost = {
            cost: simulate_short_events(
                events=events,
                bar_returns=bar_returns,
                n_bars=len(bar_returns),
                cost_bps_per_side=cost,
            )
            for cost in COSTS_PER_SIDE
        }
        results_6[variant.variant_id] = by_cost[6.0]
        daily_6 = _daily_returns(by_cost[6.0]["bar_returns"])
        daily_12 = _daily_returns(by_cost[12.0]["bar_returns"])
        row: dict[str, Any] = {
            "variant_id": variant.variant_id,
            "signal_bars": variant.signal_bars,
            "shock_threshold": variant.shock_threshold,
            "hold_bars": variant.hold_bars,
            "events": len(events),
            "events_per_year": len(events) / 4.75,
            "average_active_gross_6": float(by_cost[6.0]["active_gross"].mean()),
            "turnover_6": float(by_cost[6.0]["turnover"]),
            "missing_6": int(by_cost[6.0]["missing_return_observations"]),
        }
        for sample in SAMPLE_WINDOWS:
            metrics_6 = _sample_metrics(daily_6, sample)
            for key, value in metrics_6.items():
                row[f"{sample}_{key}_6"] = value
            row[f"{sample}_sharpe_12"] = _sample_metrics(daily_12, sample)["sharpe"]
            row[f"{sample}_multiple_12"] = _sample_metrics(daily_12, sample)["multiple"]
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    selected_id = select_candidate(summary)
    selected_row = None if selected_id is None else summary.loc[summary["variant_id"] == selected_id].iloc[0].to_dict()
    sample_metrics: pd.DataFrame | None = None
    acceptance: dict[str, bool] = {}
    overlay: pd.DataFrame | None = None
    contributions: pd.DataFrame | None = None

    if selected_row is not None:
        variant = next(item for item in VARIANTS if item.variant_id == selected_id)
        # OOS uses a separate cache and its own beta warm-up.  Only signals from
        # October onward are reported; September is warm-up.
        _, oos_close, oos_membership, oos_beta, oos_returns = _prepare_market(
            config=args.config,
            start_date=args.oos_start_date,
            end_date=args.oos_end_date,
            bar_dir=args.oos_bar_dir,
        )
        oos_events = build_short_events(
            variant=variant,
            close_frame=oos_close,
            beta=oos_beta,
            membership=oos_membership,
            assets=list(oos_returns.columns),
        )
        oos_result = simulate_short_events(
            events=oos_events,
            bar_returns=oos_returns,
            n_bars=len(oos_returns),
            cost_bps_per_side=6.0,
        )
        oos_daily = _daily_returns(oos_result["bar_returns"]).loc[OOS_EVALUATION_START:]
        oos_metrics = _sample_metrics(oos_daily, "oos")
        acceptance = _acceptance_checks(selected_row, oos_metrics)

        metric_rows: list[dict[str, Any]] = []
        for sample in SAMPLE_WINDOWS:
            if sample == "oos":
                metric_rows.append({"series": "short_selected_6bps", "sample": sample, **oos_metrics})
            else:
                daily = _daily_returns(results_6[selected_id]["bar_returns"])
                metric_rows.append(
                    {"series": "short_selected_6bps", "sample": sample, **_sample_metrics(daily, sample)}
                )
        sample_metrics = pd.DataFrame(metric_rows)
        asset_pnl = pd.Series(results_6[selected_id]["asset_pnl"], name="short_pnl_before_costs")
        contributions = (
            asset_pnl.sort_values(ascending=False)
            .rename_axis("asset")
            .reset_index()
            .head(20)
        )

        ls57 = load_ls57_returns()
        daily = _daily_returns(results_6[selected_id]["bar_returns"])
        common_start = max(daily.index.min(), ls57.index.min())
        common_end = min(daily.index.max(), ls57.index.max())
        aligned = ls57.loc[(ls57.index >= common_start) & (ls57.index <= common_end)]
        sleeve = daily.reindex(aligned.index).fillna(0.0)
        overlay_rows: list[dict[str, Any]] = []
        overlay_series = {"ls57_20bps": aligned}
        for allocation in (0.10, 0.20):
            label = f"ls57_plus_{int(round(allocation * 100)):02d}pct_short"
            overlay_series[label] = aligned + allocation * sleeve
        for label, series in overlay_series.items():
            for sample in ("full", "discovery", "validation"):
                # Overlay starts in 2022; use the same sample labels where data exists.
                overlay_rows.append({"series": label, "sample": sample, **_sample_metrics(series, sample)})
        overlay = pd.DataFrame(overlay_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "trial_summary.csv",
        "daily": output_dir / "selected_daily_returns_6bps.csv",
        "metrics": output_dir / "selected_metrics.csv",
        "contributions": output_dir / "asset_contributions.csv",
        "overlay": output_dir / "ls57_overlay.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")

    summary.to_csv(files["summary"], index=False)
    if selected_row is not None:
        _daily_returns(results_6[selected_id]["bar_returns"]).to_csv(files["daily"])
    if sample_metrics is not None:
        sample_metrics.to_csv(files["metrics"], index=False)
    if contributions is not None:
        contributions.to_csv(files["contributions"], index=False)
    if overlay is not None:
        overlay.to_csv(files["overlay"], index=False)
    files["report"].write_text(
        _report(summary, selected_row, sample_metrics, acceptance, overlay, contributions),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS70-DOWN-SHOCK-WEAK-SHORT",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "oos_start_date": args.oos_start_date,
        "oos_end_date": args.oos_end_date,
        "oos_evaluation_start": OOS_EVALUATION_START,
        "signal_bars": list(SIGNAL_BARS),
        "shock_thresholds": list(SHOCK_THRESHOLDS),
        "hold_bars": list(HOLD_BARS),
        "tail_fraction": TAIL,
        "min_cross_section": MIN_CROSS_SECTION,
        "beta_window_bars": BETA_WINDOW_BARS,
        "min_beta_observations": MIN_BETA_OBSERVATIONS,
        "beta_clip": list(BETA_CLIP),
        "costs_bps_per_side": list(COSTS_PER_SIDE),
        "trial_count": len(VARIANTS),
        "selected_variant": selected_id,
        "acceptance_checks": acceptance,
        "acceptance_verdict": "pass" if acceptance and all(acceptance.values()) else "fail",
        "funding_included": False,
        "orders_sent": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir}; selected={selected_id}; verdict={manifest['acceptance_verdict']}")


if __name__ == "__main__":
    main()
