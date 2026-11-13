"""Screen a PIT Top20 residual-momentum factor without touching live trading.

This is a first-stage factor screen. It builds a monthly dollar-neutral book
using a 60D BTC beta and 28D residual momentum, then charges turnover costs.
It does not include funding, leverage, order routing, or live signals.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
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

from atlas20.derivatives.signals import (  # noqa: E402
    build_cross_sectional_residual_momentum_schedule,
)
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-09-21"
DEFAULT_COSTS = (2.0, 20.0, 50.0, 100.0)
BETA_LOOKBACK_DAYS = 60
MIN_BETA_OBSERVATIONS = 45
MOMENTUM_LOOKBACK_DAYS = 28
REBALANCE_DAYS = 28
COUNT = 4
PER_ASSET_WEIGHT = 0.125
MIN_ASSETS = 8


@dataclass(frozen=True)
class ResidualBacktest:
    daily_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    gross_exposure: pd.Series
    missing_return_observations: int


def schedule_to_daily_weights(
    index: pd.DatetimeIndex,
    schedule: Mapping[pd.Timestamp, pd.Series],
) -> pd.DataFrame:
    """Convert signal-date target weights into next-day effective weights."""
    dates = pd.DatetimeIndex([pd.Timestamp(value) for value in index])
    if dates.empty:
        return pd.DataFrame(index=dates)
    assets = sorted(
        {
            str(asset)
            for target in schedule.values()
            for asset, weight in target.items()
            if abs(float(weight)) > 1e-15
        },
        key=str.casefold,
    )
    raw = pd.DataFrame(np.nan, index=dates, columns=assets, dtype=float)
    for raw_date, target in schedule.items():
        date = pd.Timestamp(raw_date)
        if date not in raw.index:
            continue
        raw.loc[date, :] = 0.0
        for asset, weight in target.items():
            asset_name = str(asset)
            if asset_name not in raw.columns:
                continue
            raw.loc[date, asset_name] = float(weight)
    raw = raw.ffill().fillna(0.0)
    weights = raw.shift(1).fillna(0.0)
    return weights.sort_index()


def backtest_schedule(
    index: pd.DatetimeIndex,
    returns: pd.DataFrame,
    schedule: Mapping[pd.Timestamp, pd.Series],
    *,
    cost_bps: float,
) -> ResidualBacktest:
    """Backtest a signed target schedule with next-day execution and costs."""
    if cost_bps < 0.0 or not np.isfinite(cost_bps):
        raise ValueError("cost_bps must be finite and non-negative")
    dates = pd.DatetimeIndex([pd.Timestamp(value) for value in index])
    if dates.empty:
        empty = pd.Series(dtype=float)
        return ResidualBacktest(empty, pd.DataFrame(index=dates), empty, empty, 0)
    weights = schedule_to_daily_weights(dates, schedule)
    return_frame = returns.copy()
    return_frame.index = pd.DatetimeIndex([pd.Timestamp(value) for value in return_frame.index])
    return_frame = return_frame.reindex(index=dates, columns=weights.columns)
    held = weights.abs() > 1e-15
    missing = int(return_frame.isna().where(held).sum().sum())
    clean_returns = return_frame.fillna(0.0)
    gross_return = (weights * clean_returns).sum(axis=1)
    raw_weights = weights.copy()
    # weights are already shifted; reconstruct the target-change timing from
    # the unshifted raw target before charging the execution-day cost.
    assets = list(weights.columns)
    raw_targets = pd.DataFrame(np.nan, index=dates, columns=assets, dtype=float)
    for raw_date, target in schedule.items():
        date = pd.Timestamp(raw_date)
        if date not in raw_targets.index:
            continue
        raw_targets.loc[date, :] = 0.0
        for asset, weight in target.items():
            if str(asset) in raw_targets.columns:
                raw_targets.loc[date, str(asset)] = float(weight)
    raw_targets = raw_targets.ffill().fillna(0.0)
    target_change = raw_targets.diff().abs().sum(axis=1)
    target_change.iloc[0] = float(raw_targets.iloc[0].abs().sum())
    execution_turnover = target_change.shift(1).fillna(0.0)
    trading_cost = execution_turnover * float(cost_bps) / 10_000.0
    daily_returns = (gross_return - trading_cost).astype(float)
    daily_returns.iloc[0] = 0.0
    return ResidualBacktest(
        daily_returns=daily_returns.sort_index(),
        weights=raw_weights.sort_index(),
        turnover=execution_turnover.sort_index(),
        gross_exposure=raw_weights.abs().sum(axis=1).sort_index(),
        missing_return_observations=missing,
    )


def _compound(returns: pd.Series) -> float:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return float((1.0 + clean).prod() - 1.0)


def yearly_returns(returns: pd.Series) -> pd.Series:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return clean.groupby(clean.index.year).apply(_compound)


def asset_contribution_table(
    result: ResidualBacktest,
    returns: pd.DataFrame,
) -> pd.DataFrame:
    """Return additive daily PnL contributions for every traded asset."""
    aligned = returns.copy()
    aligned.index = pd.DatetimeIndex([pd.Timestamp(value) for value in aligned.index])
    aligned = aligned.reindex(
        index=result.weights.index,
        columns=result.weights.columns,
    ).fillna(0.0)
    contributions = (result.weights * aligned).sum(axis=0).astype(float)
    absolute_sum = float(contributions.abs().sum())
    table = contributions.rename("cumulative_contribution").to_frame()
    table.index.name = "asset"
    table["absolute_share"] = (
        table["cumulative_contribution"].abs() / absolute_sum
        if absolute_sum > 0.0
        else 0.0
    )
    return table.sort_values("cumulative_contribution", ascending=False)


def residual_momentum_acceptance(
    *,
    metrics_20: Mapping[str, float],
    metrics_50: Mapping[str, float],
    positive_years: int,
    total_years: int,
    first_half_return: float,
    second_half_return: float,
) -> dict[str, bool]:
    checks = {
        "sharpe_20_ge_0_8": float(metrics_20["sharpe"]) >= 0.8,
        "multiple_20_gt_1": float(metrics_20["multiple"]) > 1.0,
        "mdd_20_ge_minus_40": float(metrics_20["max_drawdown"]) >= -0.40,
        "multiple_50_gt_1": float(metrics_50["multiple"]) > 1.0,
        "sharpe_50_ge_0_5": float(metrics_50["sharpe"]) >= 0.5,
        "positive_years_ge_80pct": total_years > 0
        and positive_years / total_years >= 0.80,
        "both_halves_positive": first_half_return > 0.0
        and second_half_return > 0.0,
    }
    return {name: bool(value) for name, value in checks.items()}


def _screen_report(
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    contributions: pd.DataFrame,
    checks: dict[str, bool],
    *,
    strategy_label: str,
    turnovers: Mapping[float, float],
    gross: Mapping[float, float],
    missing: Mapping[float, int],
    factor_events: int,
    start: str,
    end: str,
) -> str:
    verdict = "PASS (screen only)" if all(checks.values()) else "FAIL"
    top_contributors = contributions.head(8).reset_index()
    bottom_contributors = contributions.tail(8).sort_values(
        "cumulative_contribution"
    ).reset_index()
    lines = [
        f"# PIT Top20 {strategy_label} screen",
        "",
        "- status: factor screen only; no funding; no leverage; no orders",
        f"- sample: {start} → {end}",
        f"- rebalance events: **{factor_events}**",
        f"- screen verdict: **{verdict}**",
        "",
        "## Acceptance checks",
        "",
        *[f"- [{'x' if passed else ' '}] {name}" for name, passed in checks.items()],
        "",
        "## Summary",
        "",
        dataframe_to_markdown(summary),
        "",
        "## Yearly returns",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## Largest positive asset contributions at 20bps",
        "",
        dataframe_to_markdown(top_contributors),
        "",
        "## Largest negative asset contributions at 20bps",
        "",
        dataframe_to_markdown(bottom_contributors),
        "",
        "## Diagnostics",
        "",
        f"- turnover at 20bps: **{turnovers.get(20.0, float('nan')):.4f}x**",
        f"- max gross at 20bps: **{gross.get(20.0, float('nan')):.4f}x**",
        f"- missing return observations at 20bps: **{missing.get(20.0, 0)}**",
        "",
        "## Interpretation guardrail",
        "",
        "This screen uses daily panel returns and turnover costs, not Bitget fills, funding, stop-losses or live routing. A pass only earns a follow-up integration study; it is not a live candidate. A fail rejects this frozen configuration, not the broader residual-factor research direction; each new hypothesis must be registered separately.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--direction", type=int, choices=(-1, 1), default=1)
    parser.add_argument(
        "--candidate-id",
        default="PR2026-11-LS60-RESIDUAL-MOMENTUM-SCREEN",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date >= args.end_date:
        parser.error("--start-date must be before --end-date")

    _, market, universe, raw_index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    index = pd.DatetimeIndex([pd.Timestamp(value) for value in raw_index])
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    returns = market.returns.copy()
    returns.index = pd.DatetimeIndex([pd.Timestamp(value) for value in returns.index])
    if returns.index.tz is None:
        returns.index = returns.index.tz_localize("UTC")
    else:
        returns.index = returns.index.tz_convert("UTC")
    returns = returns.reindex(index).sort_index()
    schedule = build_cross_sectional_residual_momentum_schedule(
        market.price,
        universe,
        {},
        calendar=index,
        eligible=set(returns.columns),
        beta_lookback_days=BETA_LOOKBACK_DAYS,
        min_beta_observations=MIN_BETA_OBSERVATIONS,
        momentum_lookback_days=MOMENTUM_LOOKBACK_DAYS,
        rebalance_days=REBALANCE_DAYS,
        count=COUNT,
        per_asset_weight=PER_ASSET_WEIGHT,
        min_assets=MIN_ASSETS,
        anchor=args.start_date,
        direction=int(args.direction),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "daily": output_dir / "daily_returns.csv",
        "weights": output_dir / "weights.csv",
        "contributions": output_dir / "asset_contributions.csv",
        "summary": output_dir / "summary.csv",
        "yearly": output_dir / "yearly_returns.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")

    summary_rows: list[dict[str, Any]] = []
    daily_columns: dict[str, pd.Series] = {}
    turnovers: dict[float, float] = {}
    gross: dict[float, float] = {}
    missing: dict[float, int] = {}
    reference_20: ResidualBacktest | None = None
    for cost in DEFAULT_COSTS:
        result = backtest_schedule(index, returns, schedule, cost_bps=cost)
        metrics = _metrics_from_returns(result.daily_returns)
        label = f"cost_{cost:g}bps"
        daily_columns[label] = result.daily_returns
        summary_rows.append({"strategy": label, "cost_bps": cost, **metrics})
        turnovers[cost] = float(result.turnover.sum())
        gross[cost] = float(result.gross_exposure.max()) if not result.gross_exposure.empty else 0.0
        missing[cost] = result.missing_return_observations
        if cost == 20.0:
            reference_20 = result
    assert reference_20 is not None
    daily = pd.DataFrame(daily_columns, index=index)
    btc = returns["bitcoin"].reindex(index).fillna(0.0)
    btc.iloc[0] = 0.0
    btc_metrics = _metrics_from_returns(btc)
    summary_rows.append({"strategy": "bitcoin_buy_hold", "cost_bps": 0.0, **btc_metrics})
    summary = pd.DataFrame(summary_rows)
    contributions = asset_contribution_table(reference_20, returns)
    yearly_strategy = yearly_returns(daily["cost_20bps"])
    yearly_btc = yearly_returns(btc)
    yearly = pd.DataFrame(
        {"strategy_20bps": yearly_strategy, "bitcoin": yearly_btc}
    ).reset_index().rename(columns={"index": "year"})
    midpoint = len(index) // 2
    first_half_return = _compound(daily["cost_20bps"].iloc[:midpoint])
    second_half_return = _compound(daily["cost_20bps"].iloc[midpoint:])
    metrics_by_cost = summary.set_index("strategy")
    checks = residual_momentum_acceptance(
        metrics_20=metrics_by_cost.loc["cost_20bps"].to_dict(),
        metrics_50=metrics_by_cost.loc["cost_50bps"].to_dict(),
        positive_years=int((yearly_strategy > 0.0).sum()),
        total_years=int(len(yearly_strategy)),
        first_half_return=first_half_return,
        second_half_return=second_half_return,
    )
    daily.to_csv(files["daily"], index=True)
    reference_20.weights.to_csv(files["weights"], index=True)
    contributions.to_csv(files["contributions"], index_label="asset")
    summary.to_csv(files["summary"], index=False)
    yearly.to_csv(files["yearly"], index=False)
    files["report"].write_text(
        _screen_report(
            summary,
            yearly,
            contributions,
            checks,
            strategy_label=(
                "residual-reversal" if int(args.direction) < 0 else "residual-momentum"
            ),
            turnovers=turnovers,
            gross=gross,
            missing=missing,
            factor_events=len([target for target in schedule.values() if not target.empty]),
            start=args.start_date,
            end=args.end_date,
        ),
        encoding="utf-8",
    )
    manifest = {
        "candidate_id": str(args.candidate_id),
        "direction": int(args.direction),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "beta_lookback_days": BETA_LOOKBACK_DAYS,
        "min_beta_observations": MIN_BETA_OBSERVATIONS,
        "momentum_lookback_days": MOMENTUM_LOOKBACK_DAYS,
        "rebalance_days": REBALANCE_DAYS,
        "count": COUNT,
        "per_asset_weight": PER_ASSET_WEIGHT,
        "min_assets": MIN_ASSETS,
        "costs_bps": list(DEFAULT_COSTS),
        "factor_events": len([target for target in schedule.values() if not target.empty]),
        "first_half_return": first_half_return,
        "second_half_return": second_half_return,
        "metrics": summary.to_dict("records"),
        "yearly": yearly.to_dict("records"),
        "asset_contributions": contributions.reset_index().to_dict("records"),
        "turnover": {str(key): value for key, value in turnovers.items()},
        "max_gross": {str(key): value for key, value in gross.items()},
        "missing_return_observations": {str(key): value for key, value in missing.items()},
        "acceptance_checks": checks,
        "acceptance_verdict": "pass" if all(checks.values()) else "fail",
        "funding_included": False,
        "orders_sent": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir} with {len(index)} days; verdict={manifest['acceptance_verdict']}")


if __name__ == "__main__":
    main()
