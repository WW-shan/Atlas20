"""Backtest the frozen Top20 churn short with three pre-registered gates."""

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
    detect_membership_events,
    membership_matrix,
)
from scripts.run_daily_btc_shock_continuation import backtest_continuation  # noqa: E402
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402
from scripts.run_top20_churn_short import load_ls57_returns  # noqa: E402

DEFAULT_START = "2021-01-01"
DEFAULT_END = "2026-11-12"
CONFIRMATION_DAYS = 7
HOLD_DAYS = 28
COSTS_BPS = (2.0, 20.0, 50.0, 100.0)
GATES = ("alt_rel_60", "btc_ma200", "both")
SAMPLE_WINDOWS: dict[str, tuple[str, str]] = {
    "full": (DEFAULT_START, DEFAULT_END),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", DEFAULT_END),
    "pre2022": ("2021-01-01", "2021-12-31"),
}


def build_gate_series(
    *,
    price: pd.DataFrame,
    returns: pd.DataFrame,
    present: pd.DataFrame,
    assets: list[str],
) -> dict[str, pd.Series]:
    """Build the three frozen signal-date regime gates."""
    btc_returns = pd.to_numeric(returns["bitcoin"], errors="coerce").fillna(0.0)
    present_aligned = present.reindex(columns=assets, fill_value=False).astype(bool)
    member_returns = returns[assets].where(present_aligned).mean(axis=1)
    member_returns = pd.to_numeric(member_returns, errors="coerce").fillna(0.0)
    btc_log = np.log1p(btc_returns.clip(lower=-0.999999))
    member_log = np.log1p(member_returns.clip(lower=-0.999999))
    alt_rel_60 = (
        member_log.rolling(60, min_periods=60).sum()
        - btc_log.rolling(60, min_periods=60).sum()
    )
    alt_weak = alt_rel_60 <= 0.0
    btc_close = pd.to_numeric(price["bitcoin"], errors="coerce")
    btc_ma200 = btc_close < btc_close.rolling(200, min_periods=200).mean()
    return {
        "alt_rel_60": alt_weak.fillna(False),
        "btc_ma200": btc_ma200.fillna(False),
        "both": (alt_weak & btc_ma200).fillna(False),
    }


def build_gated_targets(
    *,
    present: pd.DataFrame,
    gate: pd.Series,
    assets: list[str],
) -> pd.DataFrame:
    """Build LS72 event targets only when the signal-date gate is true."""
    events = detect_membership_events(
        present,
        confirmation_days=CONFIRMATION_DAYS,
        cooldown_days=COOLDOWN_DAYS,
    )
    columns = ["bitcoin", *assets]
    targets = pd.DataFrame(0.0, index=present.index, columns=columns, dtype=float)
    if events.empty:
        return targets
    gate = gate.reindex(present.index, fill_value=False).astype(bool)
    for date, group in events.groupby("event_date", sort=True):
        if not bool(gate.loc[date]):
            continue
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
        return {"multiple": float("nan"), "cagr": float("nan"), "sharpe": float("nan"), "max_drawdown": float("nan")}
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


def _acceptance_checks(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "validation_sharpe_20_positive": float(row["validation_sharpe_20"]) > 0.0,
        "validation_sharpe_50_positive": float(row["validation_sharpe_50"]) > 0.0,
        "pre2022_multiple_at_least_0_92": float(row["pre2022_multiple_20"]) >= 0.92,
        "full_multiple_20_above_one": float(row["full_multiple_20"]) > 1.0,
        "full_multiple_50_above_one": float(row["full_multiple_50"]) > 1.0,
        "full_sharpe_20_above_0_5": float(row["full_sharpe_20"]) > 0.5,
        "full_mdd_20_no_worse_than_minus_30pct": float(row["full_max_drawdown_20"]) >= -0.30,
    }


def _report(
    summary: pd.DataFrame,
    selected: dict[str, Any] | None,
    metrics: pd.DataFrame | None,
    acceptance: dict[str, bool],
    overlay: pd.DataFrame | None,
) -> str:
    lines = [
        "# Gated Top20 membership churn short",
        "",
        "- frozen event rule: m=7, h=28, entry+exit, BTC-hedged churn",
        "- gates: alt_rel_60, btc_ma200, both; all three reported",
        "- execution: event close → next close; total gross <=1",
        "- costs: 2/20/50/100bps per side; funding excluded",
        "",
        "## Gate results",
        "",
        dataframe_to_markdown(
            summary[
                [
                    "variant_id",
                    "events",
                    "discovery_multiple_20",
                    "discovery_sharpe_20",
                    "discovery_sharpe_50",
                    "validation_multiple_20",
                    "validation_sharpe_20",
                    "pre2022_multiple_20",
                    "pre2022_sharpe_20",
                    "full_multiple_20",
                    "full_sharpe_20",
                    "full_max_drawdown_20",
                    "turnover_20",
                ]
            ].reset_index(drop=True)
        ),
        "",
    ]
    if selected is None:
        lines.extend(["## Decision", "", "No gate passed the discovery-only selection rule.", ""])
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
            "## Return-space LS57 overlay",
            "",
            dataframe_to_markdown(overlay if overlay is not None else pd.DataFrame()),
            "",
            "## Guardrail",
            "",
            "The gate is evaluated only on the event date. A pass needs funding, Bitget mark/fill and forward OOS verification before shadow promotion.",
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
        parser.error("LS73 is frozen to 2021-01-01 -> 2026-11-12; register another family for another window")

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
    assets = sorted(
        [
            str(asset)
            for asset in price.columns
            if str(asset) != "bitcoin" and str(asset) in returns.columns
        ],
        key=str.casefold,
    )
    present = membership_matrix(universe, index=index)
    gates = build_gate_series(price=price, returns=returns, present=present, assets=assets)

    summary_rows: list[dict[str, Any]] = []
    daily_columns: dict[str, pd.Series] = {}
    results_20: dict[str, Any] = {}
    targets_by_gate: dict[str, pd.DataFrame] = {}
    for gate_name in GATES:
        targets = build_gated_targets(present=present, gate=gates[gate_name], assets=assets)
        targets_by_gate[gate_name] = targets
        results: dict[float, Any] = {}
        for cost in COSTS_BPS:
            results[cost] = backtest_continuation(
                index=index,
                returns=returns[["bitcoin", *assets]],
                targets=targets,
                horizon=HOLD_DAYS,
                cost_bps=cost,
            )
        result_20 = results[20.0]
        results_20[gate_name] = result_20
        daily_columns[gate_name] = result_20.daily_returns
        row: dict[str, Any] = {
            "variant_id": gate_name,
            "events": int(len(detect_membership_events(present, confirmation_days=CONFIRMATION_DAYS))),
            "turnover_20": float(result_20.turnover.sum()),
            "average_active_gross_20": float(result_20.gross_exposure.mean()),
            "max_gross_20": float(result_20.gross_exposure.max()),
            "missing_20": int(result_20.missing_return_observations),
        }
        for sample in SAMPLE_WINDOWS:
            m20 = _sample_metrics(result_20.daily_returns, sample)
            m50 = _sample_metrics(results[50.0].daily_returns, sample)
            for key, value in m20.items():
                row[f"{sample}_{key}_20"] = value
            row[f"{sample}_multiple_50"] = m50["multiple"]
            row[f"{sample}_sharpe_50"] = m50["sharpe"]
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    selected_id = select_candidate(summary)
    selected = None if selected_id is None else summary.loc[summary["variant_id"] == selected_id].iloc[0].to_dict()
    acceptance: dict[str, bool] = {}
    metrics: pd.DataFrame | None = None
    overlay: pd.DataFrame | None = None
    if selected_id is not None:
        acceptance = _acceptance_checks(selected)
        result = results_20[selected_id]
        metrics = pd.DataFrame(
            [
                {"series": f"churn_gate_{selected_id}_20bps", "sample": sample, **_sample_metrics(result.daily_returns, sample)}
                for sample in SAMPLE_WINDOWS
            ]
        )
        ls57 = load_ls57_returns()
        start = max(ls57.index.min(), result.daily_returns.index.min())
        end = min(ls57.index.max(), result.daily_returns.index.max())
        base = ls57.loc[(ls57.index >= start) & (ls57.index <= end)]
        sleeve = result.daily_returns.reindex(base.index).fillna(0.0)
        overlay_rows: list[dict[str, Any]] = []
        for allocation in (0.10, 0.20):
            combined = base + allocation * sleeve
            for sample in ("full", "discovery", "validation"):
                overlay_rows.append(
                    {"series": f"ls57_plus_{int(round(allocation * 100)):02d}pct_churn_gate", "sample": sample, **_sample_metrics(combined, sample)}
                )
        overlay = pd.DataFrame(overlay_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "trial_summary.csv",
        "daily": output_dir / "daily_returns_20bps.csv",
        "targets": output_dir / "selected_targets.csv",
        "metrics": output_dir / "selected_metrics.csv",
        "overlay": output_dir / "ls57_overlay.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    pd.DataFrame(daily_columns).sort_index().to_csv(files["daily"])
    (targets_by_gate.get(selected_id, pd.DataFrame()) if selected_id else pd.DataFrame()).to_csv(files["targets"])
    if metrics is not None:
        metrics.to_csv(files["metrics"], index=False)
    if overlay is not None:
        overlay.to_csv(files["overlay"], index=False)
    files["report"].write_text(_report(summary, selected, metrics, acceptance, overlay), encoding="utf-8")
    manifest = {
        "candidate_family_id": "PR2026-11-LS73-TOP20-CHURN-ALT-WEAK",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "confirmation_days": CONFIRMATION_DAYS,
        "hold_days": HOLD_DAYS,
        "gates": list(GATES),
        "costs_bps": list(COSTS_BPS),
        "trial_count": len(GATES),
        "selected_variant": selected_id,
        "acceptance_checks": acceptance,
        "acceptance_verdict": "pass" if acceptance and all(acceptance.values()) else "fail",
        "funding_included": False,
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_dir}; selected={selected_id}; verdict={manifest['acceptance_verdict']}")


if __name__ == "__main__":
    main()
