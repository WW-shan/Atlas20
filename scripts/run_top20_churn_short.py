"""Backtest a market-neutral Top20 membership churn short.

Research only.  The script shorts confirmed Top20 entry/exit coins and hedges
the short notional with BTC; it never sends orders or changes the live book.
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

from scripts.diagnose_top20_membership_events import (  # noqa: E402
    COOLDOWN_DAYS,
    membership_matrix,
    detect_membership_events,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_daily_btc_shock_continuation import (  # noqa: E402
    backtest_continuation,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

DEFAULT_START = "2021-01-01"
DEFAULT_END = "2026-11-12"
CONFIRMATION_DAYS = (3, 7, 14)
HOLD_DAYS = (7, 14, 28, 56)
COSTS_BPS = (2.0, 20.0, 50.0, 100.0)
SAMPLE_WINDOWS: dict[str, tuple[str, str]] = {
    "full": (DEFAULT_START, DEFAULT_END),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", DEFAULT_END),
    "pre2022": ("2021-01-01", "2021-12-31"),
}
LS57_RETURNS = Path(
    "reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/"
    "PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/"
    "daily_returns.csv"
)


def build_churn_targets(
    *,
    present: pd.DataFrame,
    confirmation_days: int,
    assets: list[str],
) -> pd.DataFrame:
    """Build sparse event-date target books with short churn and long BTC hedge."""
    events = detect_membership_events(
        present,
        confirmation_days=confirmation_days,
        cooldown_days=COOLDOWN_DAYS,
    )
    columns = ["bitcoin", *assets]
    targets = pd.DataFrame(0.0, index=present.index, columns=columns, dtype=float)
    if events.empty:
        return targets
    for date, group in events.groupby("event_date", sort=True):
        coins = [str(coin) for coin in group["coin_id"].unique() if str(coin) in assets]
        if not coins:
            continue
        weight = 0.5 / len(coins)
        targets.loc[date, coins] = -weight
        targets.loc[date, "bitcoin"] = 0.5
    return targets


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
        (summary["discovery_sharpe_20"] > 0.0)
        & (summary["discovery_sharpe_50"] > 0.0)
    ].copy()
    if eligible.empty:
        return None
    eligible = eligible.sort_values(
        ["discovery_sharpe_20", "turnover_20", "variant_id"],
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


def _acceptance_checks(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "validation_sharpe_20_positive": float(row["validation_sharpe_20"]) > 0.0,
        "validation_sharpe_50_positive": float(row["validation_sharpe_50"]) > 0.0,
        "pre2022_sharpe_20_positive": float(row["pre2022_sharpe_20"]) > 0.0,
        "full_multiple_20_above_one": float(row["full_multiple_20"]) > 1.0,
        "full_multiple_50_above_one": float(row["full_multiple_50"]) > 1.0,
        "full_sharpe_20_above_0_5": float(row["full_sharpe_20"]) > 0.5,
        "full_mdd_20_no_worse_than_minus_30pct": float(row["full_max_drawdown_20"])
        >= -0.30,
    }


def _report(
    summary: pd.DataFrame,
    selected: dict[str, Any] | None,
    metrics: pd.DataFrame | None,
    acceptance: dict[str, bool],
    contributions: pd.DataFrame | None,
    overlay: pd.DataFrame | None,
) -> str:
    ranked = summary.sort_values(
        ["discovery_sharpe_20", "turnover_20"],
        ascending=[False, True],
        kind="stable",
    ).head(12)
    lines = [
        "# Top20 membership churn short backtest",
        "",
        "- status: research only; no orders; no live changes",
        "- event: confirmed Top20 entry or exit; short changed coins, long BTC hedge",
        "- execution: event close → next close; all event-day tranches equal-weight; gross <=1",
        "- costs: 2/20/50/100bps per side; funding excluded in this screen",
        "",
        "## Discovery-ranked cells",
        "",
        dataframe_to_markdown(
            ranked[
                [
                    "variant_id",
                    "discovery_multiple_20",
                    "discovery_sharpe_20",
                    "discovery_sharpe_50",
                    "validation_multiple_20",
                    "validation_sharpe_20",
                    "pre2022_sharpe_20",
                    "full_multiple_20",
                    "full_sharpe_20",
                    "full_max_drawdown_20",
                    "turnover_20",
                    "events",
                ]
            ].reset_index(drop=True)
        ),
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
            dataframe_to_markdown(metrics if metrics is not None else pd.DataFrame()),
            "",
            "## Asset contribution before costs",
            "",
            dataframe_to_markdown(contributions if contributions is not None else pd.DataFrame()),
            "",
            "## Return-space LS57 overlay",
            "",
            "Overlay rows add the churn sleeve to LS57 without modelling margin, gross, funding or execution.",
            "",
            dataframe_to_markdown(overlay if overlay is not None else pd.DataFrame()),
            "",
            "## Guardrail",
            "",
            "The event detector is point-in-time, but the Top20 boundary can be noisy. Missing returns are counted and zero-filled in this screen. A pass needs Bitget mark/fill, funding and partial-fill verification before shadow promotion.",
            "",
        ]
    )
    return "\n".join(lines)


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
    if args.start_date != DEFAULT_START or args.end_date != DEFAULT_END:
        parser.error("LS72 is frozen to 2021-01-01 -> 2026-11-12; register another family for another window")

    _, market, universe, raw_index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    index = pd.DatetimeIndex(pd.to_datetime(raw_index, utc=True)).sort_values()
    price = market.price.copy()
    price.index = pd.DatetimeIndex(pd.to_datetime(price.index, utc=True)).sort_values()
    price = price.reindex(index).sort_index()
    returns = market.returns.copy()
    returns.index = pd.DatetimeIndex(pd.to_datetime(returns.index, utc=True)).sort_values()
    returns = returns.reindex(index).sort_index()
    assets = [str(asset) for asset in price.columns if str(asset) != "bitcoin"]
    assets = [asset for asset in assets if asset in returns.columns]
    present = membership_matrix(universe, index=index)

    summary_rows: list[dict[str, Any]] = []
    daily_columns: dict[str, pd.Series] = {}
    target_by_variant: dict[str, pd.DataFrame] = {}
    result_20_by_variant: dict[str, Any] = {}
    for confirmation_days in CONFIRMATION_DAYS:
        targets = build_churn_targets(
            present=present,
            confirmation_days=confirmation_days,
            assets=assets,
        )
        for hold_days in HOLD_DAYS:
            variant_id = f"CHURN_m{confirmation_days}_h{hold_days}"
            target_by_variant[variant_id] = targets
            results: dict[float, Any] = {}
            for cost in COSTS_BPS:
                results[cost] = backtest_continuation(
                    index=index,
                    returns=returns[["bitcoin", *assets]],
                    targets=targets,
                    horizon=hold_days,
                    cost_bps=cost,
                )
            result_20 = results[20.0]
            result_20_by_variant[variant_id] = result_20
            daily_columns[variant_id] = result_20.daily_returns
            row: dict[str, Any] = {
                "variant_id": variant_id,
                "confirmation_days": confirmation_days,
                "hold_days": hold_days,
                "events": int(len(detect_membership_events(present, confirmation_days=confirmation_days))),
                "turnover_20": float(result_20.turnover.sum()),
                "average_active_gross_20": float(result_20.gross_exposure.mean()),
                "max_gross_20": float(result_20.gross_exposure.max()),
                "missing_20": int(result_20.missing_return_observations),
            }
            for sample in SAMPLE_WINDOWS:
                metrics_20 = _sample_metrics(result_20.daily_returns, sample)
                metrics_50 = _sample_metrics(results[50.0].daily_returns, sample)
                for key, value in metrics_20.items():
                    row[f"{sample}_{key}_20"] = value
                row[f"{sample}_multiple_50"] = metrics_50["multiple"]
                row[f"{sample}_sharpe_50"] = metrics_50["sharpe"]
            summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    selected_id = select_candidate(summary)
    selected = None if selected_id is None else summary.loc[summary["variant_id"] == selected_id].iloc[0].to_dict()
    acceptance: dict[str, bool] = {}
    metrics: pd.DataFrame | None = None
    contributions: pd.DataFrame | None = None
    overlay: pd.DataFrame | None = None
    selected_weights = pd.DataFrame()
    if selected_id is not None:
        acceptance = _acceptance_checks(selected)
        result = result_20_by_variant[selected_id]
        metric_rows: list[dict[str, Any]] = []
        for sample in SAMPLE_WINDOWS:
            metric_rows.append(
                {
                    "series": "top20_churn_short_20bps",
                    "sample": sample,
                    **_sample_metrics(result.daily_returns, sample),
                }
            )
        metrics = pd.DataFrame(metric_rows)
        aligned_returns = returns[["bitcoin", *assets]].reindex(
            index=result.weights.index,
            columns=result.weights.columns,
        )
        pnl = (result.weights * aligned_returns.fillna(0.0)).sum(axis=0)
        contributions = (
            pnl.rename("pnl_before_costs").sort_values(ascending=False).rename_axis("asset").reset_index().head(20)
        )
        ls57 = load_ls57_returns()
        common_start = max(result.daily_returns.index.min(), ls57.index.min())
        common_end = min(result.daily_returns.index.max(), ls57.index.max())
        aligned = ls57.loc[(ls57.index >= common_start) & (ls57.index <= common_end)]
        sleeve = result.daily_returns.reindex(aligned.index).fillna(0.0)
        overlay_series = {"ls57_20bps": aligned}
        for allocation in (0.10, 0.20):
            overlay_series[f"ls57_plus_{int(round(allocation * 100)):02d}pct_churn"] = (
                aligned + allocation * sleeve
            )
        overlay_rows: list[dict[str, Any]] = []
        for label, series in overlay_series.items():
            for sample in ("full", "discovery", "validation"):
                overlay_rows.append({"series": label, "sample": sample, **_sample_metrics(series, sample)})
        overlay = pd.DataFrame(overlay_rows)
        selected_weights = target_by_variant[selected_id]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "trial_summary.csv",
        "daily": output_dir / "daily_returns_20bps.csv",
        "targets": output_dir / "selected_targets.csv",
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
    pd.DataFrame(daily_columns).sort_index().to_csv(files["daily"])
    selected_weights.to_csv(files["targets"])
    if metrics is not None:
        metrics.to_csv(files["metrics"], index=False)
    if contributions is not None:
        contributions.to_csv(files["contributions"], index=False)
    if overlay is not None:
        overlay.to_csv(files["overlay"], index=False)
    files["report"].write_text(
        _report(summary, selected, metrics, acceptance, contributions, overlay),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS72-TOP20-CHURN-SHORT",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "confirmation_days": list(CONFIRMATION_DAYS),
        "hold_days": list(HOLD_DAYS),
        "costs_bps": list(COSTS_BPS),
        "cooldown_days": COOLDOWN_DAYS,
        "event_type": "entry_plus_exit",
        "hedge": "equal-notional BTC long",
        "trial_count": len(CONFIRMATION_DAYS) * len(HOLD_DAYS),
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
