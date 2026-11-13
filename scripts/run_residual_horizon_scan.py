"""Scan residual-momentum horizons and signs without touching live trading.

The runner is the reproducible implementation of
``docs/superpowers/specs/2026-11-13-residual-horizon-scan-design.md``.  It
registers one frozen 12-configuration grid, evaluates every configuration on
the same point-in-time Top20 panel, and separates discovery, validation and
post-cutoff observations.  It sends no orders and does not change the live
track.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
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
from scripts.run_residual_momentum_screen import (  # noqa: E402
    ResidualBacktest,
    asset_contribution_table,
    backtest_schedule,
    yearly_returns,
)
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-11-12"
COSTS = (2.0, 20.0, 50.0, 100.0)
BETA_LOOKBACK_DAYS = 120
MIN_BETA_OBSERVATIONS = 90
REBALANCE_DAYS = 28
COUNT = 4
PER_ASSET_WEIGHT = 0.125
MIN_ASSETS = 8
LOOKBACKS = (63, 126, 252)
SKIPS = (0, 21)
DIRECTIONS = (1, -1)
SAMPLES: dict[str, tuple[str, str]] = {
    "full": ("2022-01-01", "2026-11-12"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-09-21"),
    "latest": ("2026-09-22", "2026-11-12"),
}


@dataclass(frozen=True)
class Variant:
    variant_id: str
    lookback_days: int
    skip_days: int
    direction: int


def variant_specs() -> tuple[Variant, ...]:
    """Return the pre-registered 3 x 2 x 2 residual factor grid."""
    return tuple(
        Variant(
            variant_id=(
                f"residual_L{lookback}_S{skip}_"
                f"{'momentum' if direction > 0 else 'reversal'}"
            ),
            lookback_days=lookback,
            skip_days=skip,
            direction=direction,
        )
        for lookback in LOOKBACKS
        for skip in SKIPS
        for direction in DIRECTIONS
    )


def slice_returns(returns: pd.Series, start: str, end: str) -> pd.Series:
    """Slice a UTC daily return series to an inclusive local-date window."""
    lower = pd.Timestamp(start, tz="UTC")
    upper = pd.Timestamp(end, tz="UTC")
    return returns.loc[(returns.index >= lower) & (returns.index <= upper)]


def realized_market_beta(returns: pd.Series, bitcoin: pd.Series) -> float:
    """Estimate the full-sample realized beta of a daily return stream."""
    aligned = pd.concat(
        [returns.rename("strategy"), bitcoin.rename("bitcoin")], axis=1
    ).dropna()
    if len(aligned) < 2:
        return float("nan")
    market_var = float(aligned["bitcoin"].var(ddof=1))
    if not np.isfinite(market_var) or market_var <= 0.0:
        return float("nan")
    return float(aligned["strategy"].cov(aligned["bitcoin"]) / market_var)


def tier_for_variant(
    *,
    full_20: Mapping[str, float],
    discovery_20: Mapping[str, float],
    validation_20: Mapping[str, float],
    full_50: Mapping[str, float],
) -> str:
    """Label evidence strength without turning the label into a research ban."""
    if (
        float(full_20["multiple"]) > 1.0
        and float(full_20["sharpe"]) > 0.8
        and float(discovery_20["multiple"]) > 1.0
        and float(discovery_20["sharpe"]) > 0.5
        and float(validation_20["multiple"]) > 1.0
        and float(validation_20["sharpe"]) > 0.5
        and float(full_50["multiple"]) > 1.0
    ):
        return "candidate-for-integration"
    if float(discovery_20["multiple"]) > 1.0 and float(validation_20["multiple"]) > 1.0:
        return "watch"
    return "rejected-now"


def _run_variant(
    variant: Variant,
    *,
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    returns: pd.DataFrame,
    index: pd.DatetimeIndex,
    start: str,
) -> tuple[dict[float, ResidualBacktest], dict[pd.Timestamp, pd.Series]]:
    schedule = build_cross_sectional_residual_momentum_schedule(
        prices,
        universe,
        {},
        calendar=index,
        eligible=set(returns.columns),
        beta_lookback_days=BETA_LOOKBACK_DAYS,
        min_beta_observations=MIN_BETA_OBSERVATIONS,
        momentum_lookback_days=variant.lookback_days,
        skip_days=variant.skip_days,
        rebalance_days=REBALANCE_DAYS,
        count=COUNT,
        per_asset_weight=PER_ASSET_WEIGHT,
        min_assets=MIN_ASSETS,
        anchor=start,
        direction=variant.direction,
    )
    results = {
        cost: backtest_schedule(index, returns, schedule, cost_bps=cost)
        for cost in COSTS
    }
    return results, schedule


def _segment_metrics(
    variant: Variant,
    results: Mapping[float, ResidualBacktest],
    bitcoin: pd.Series,
) -> tuple[list[dict[str, Any]], dict[str, dict[float, dict[str, float]]]]:
    rows: list[dict[str, Any]] = []
    by_sample: dict[str, dict[float, dict[str, float]]] = {}
    for sample_name, (start, end) in SAMPLES.items():
        by_sample[sample_name] = {}
        btc_segment = slice_returns(bitcoin, start, end)
        btc_metrics = _metrics_from_returns(btc_segment)
        for cost, result in results.items():
            segment = slice_returns(result.daily_returns, start, end)
            metrics = _metrics_from_returns(segment)
            by_sample[sample_name][cost] = metrics
            rows.append(
                {
                    "variant_id": variant.variant_id,
                    "direction": variant.direction,
                    "lookback_days": variant.lookback_days,
                    "skip_days": variant.skip_days,
                    "sample": sample_name,
                    "start": start,
                    "end": end,
                    "days": len(segment),
                    "cost_bps": cost,
                    **metrics,
                    "bitcoin_multiple": btc_metrics["multiple"],
                    "bitcoin_sharpe": btc_metrics["sharpe"],
                    "bitcoin_max_drawdown": btc_metrics["max_drawdown"],
                }
            )
    return rows, by_sample


def _ranking_rows(
    variants: tuple[Variant, ...],
    by_variant: Mapping[str, dict[str, dict[float, dict[str, float]]]],
    contributions: Mapping[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in variants:
        samples = by_variant[variant.variant_id]
        tier = tier_for_variant(
            full_20=samples["full"][20.0],
            discovery_20=samples["discovery"][20.0],
            validation_20=samples["validation"][20.0],
            full_50=samples["full"][50.0],
        )
        table = contributions[variant.variant_id]
        positives = [str(asset) for asset in table.head(3).index]
        negatives = [
            str(asset)
            for asset in table.tail(3)
            .sort_values("cumulative_contribution")
            .index
        ]
        rows.append(
            {
                "variant_id": variant.variant_id,
                "direction": variant.direction,
                "lookback_days": variant.lookback_days,
                "skip_days": variant.skip_days,
                "full_multiple_20": samples["full"][20.0]["multiple"],
                "full_sharpe_20": samples["full"][20.0]["sharpe"],
                "full_mdd_20": samples["full"][20.0]["max_drawdown"],
                "discovery_multiple_20": samples["discovery"][20.0]["multiple"],
                "discovery_sharpe_20": samples["discovery"][20.0]["sharpe"],
                "validation_multiple_20": samples["validation"][20.0]["multiple"],
                "validation_sharpe_20": samples["validation"][20.0]["sharpe"],
                "latest_multiple_20": samples["latest"][20.0]["multiple"],
                "latest_sharpe_20": samples["latest"][20.0]["sharpe"],
                "tier": tier,
                "top_positive_assets": ", ".join(positives),
                "top_negative_assets": ", ".join(negatives),
            }
        )
    return rows


def _report(
    ranking: pd.DataFrame,
    sample_rows: pd.DataFrame,
    *,
    start: str,
    end: str,
    best_variant: str,
) -> str:
    display_columns = [
        "variant_id",
        "full_multiple_20",
        "full_sharpe_20",
        "full_mdd_20",
        "discovery_multiple_20",
        "discovery_sharpe_20",
        "validation_multiple_20",
        "validation_sharpe_20",
        "latest_multiple_20",
        "tier",
    ]
    best_rows = sample_rows.loc[
        (sample_rows["variant_id"] == best_variant)
        & (sample_rows["cost_bps"] == 20.0)
    ].copy()
    best_rows = best_rows[
        ["sample", "days", "multiple", "cagr", "sharpe", "max_drawdown"]
    ]
    lines = [
        "# PIT Top20 residual momentum horizon / sign scan",
        "",
        "- status: factor screen only; no funding; no leverage; no orders",
        f"- sample: {start} → {end}",
        "- discovery: 2022-01-01 → 2023-12-31; validation: 2024-01-01 → 2026-09-21",
        "- latest: 2026-09-22 → 2026-11-12 (descriptive only)",
        "- beta: 120D rolling BTC beta, minimum 90 observations",
        "- grid: lookback 63/126/252 x skip 0/21 x direction momentum/reversal = 12",
        "",
        "## Discovery-ranked configurations",
        "",
        "The table is displayed in discovery-sharpe order only. Validation and latest columns were "
        "not used to choose the order or the parameters.",
        "",
        dataframe_to_markdown(ranking[display_columns].reset_index(drop=True)),
        "",
        "## Best discovery variant by sample",
        "",
        f"Selected by discovery Sharpe only: `{best_variant}`. The 20bps metrics below are shown for "
        "transparency; the latest window is far too short to validate the strategy.",
        "",
        dataframe_to_markdown(best_rows.reset_index(drop=True)),
        "",
        "## Asset concentration",
        "",
        "Every asset contribution is in `asset_contributions.csv`. The ranking table lists the three "
        "largest positive and negative full-sample contributions for each variant.",
        "",
        "## Interpretation guardrail",
        "",
        "This is a monthly dollar-neutral residual-factor screen using daily panel returns and turnover "
        "costs. It does not include funding, Bitget fills, queue position, stop-losses or live routing. "
        "A label is descriptive evidence, not an order or a permanent ban on later hypotheses. A "
        "candidate-for-integration label still requires independent execution, funding and robustness "
        "checks before it can affect a live track.",
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
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.start_date >= args.end_date:
        parser.error("--start-date must be before --end-date")
    if args.start_date != SAMPLES["full"][0] or args.end_date != SAMPLES["full"][1]:
        parser.error(
            "the frozen grid expects --start-date 2022-01-01 and "
            "--end-date 2026-11-12; register a new study for another window"
        )

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
    bitcoin = returns["bitcoin"].fillna(0.0)
    bitcoin.iloc[0] = 0.0

    variants = variant_specs()
    all_sample_rows: list[dict[str, Any]] = []
    by_variant: dict[str, dict[str, dict[float, dict[str, float]]]] = {}
    daily_columns: dict[str, pd.Series] = {}
    contributions_by_variant: dict[str, pd.DataFrame] = {}
    trial_rows: list[dict[str, Any]] = []
    turnover: dict[str, float] = {}
    max_gross: dict[str, float] = {}
    missing: dict[str, int] = {}
    realized_beta: dict[str, float] = {}
    best_weights: pd.DataFrame | None = None
    best_discovery_sharpe = -float("inf")
    best_variant = ""

    for variant in variants:
        results, schedule = _run_variant(
            variant,
            prices=market.price,
            universe=universe,
            returns=returns,
            index=index,
            start=args.start_date,
        )
        reference = results[20.0]
        daily_columns[variant.variant_id] = reference.daily_returns
        sample_rows, samples = _segment_metrics(variant, results, bitcoin)
        all_sample_rows.extend(sample_rows)
        by_variant[variant.variant_id] = samples
        contributions = asset_contribution_table(reference, returns)
        contributions_by_variant[variant.variant_id] = contributions
        turnover[variant.variant_id] = float(reference.turnover.sum())
        max_gross[variant.variant_id] = (
            float(reference.gross_exposure.max())
            if not reference.gross_exposure.empty
            else 0.0
        )
        missing[variant.variant_id] = reference.missing_return_observations
        realized_beta[variant.variant_id] = realized_market_beta(
            reference.daily_returns, bitcoin
        )
        discovery_sharpe = float(samples["discovery"][20.0]["sharpe"])
        if discovery_sharpe > best_discovery_sharpe:
            best_discovery_sharpe = discovery_sharpe
            best_variant = variant.variant_id
            best_weights = reference.weights
        trial_rows.append(
            {
                **asdict(variant),
                "factor_events": len(
                    [target for target in schedule.values() if not target.empty]
                ),
                "turnover_20": turnover[variant.variant_id],
                "max_gross_20": max_gross[variant.variant_id],
                "missing_return_observations_20": missing[variant.variant_id],
                "realized_beta_full": realized_beta[variant.variant_id],
            }
        )

    ranking_rows = _ranking_rows(variants, by_variant, contributions_by_variant)
    ranking = pd.DataFrame(ranking_rows).sort_values(
        ["discovery_sharpe_20", "validation_sharpe_20"],
        ascending=False,
        kind="stable",
    )
    sample_rows_frame = pd.DataFrame(all_sample_rows)
    daily = pd.DataFrame(daily_columns, index=index)
    daily["bitcoin"] = bitcoin
    yearly_rows: list[dict[str, Any]] = []
    for column in daily.columns:
        yearly = yearly_returns(daily[column])
        for year, value in yearly.items():
            yearly_rows.append({"series": column, "year": int(year), "return": float(value)})
    contributions_long = pd.concat(
        [
            table.reset_index().assign(variant_id=variant_id)
            for variant_id, table in contributions_by_variant.items()
        ],
        ignore_index=True,
    )
    trial_log = pd.DataFrame(trial_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "daily": output_dir / "daily_returns.csv",
        "summary": output_dir / "sample_metrics.csv",
        "ranking": output_dir / "variant_ranking.csv",
        "yearly": output_dir / "yearly_returns.csv",
        "contributions": output_dir / "asset_contributions.csv",
        "trial_log": output_dir / "trial_log.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
        "weights": output_dir / "best_discovery_weights.csv",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")

    daily.to_csv(files["daily"], index=True)
    sample_rows_frame.to_csv(files["summary"], index=False)
    ranking.to_csv(files["ranking"], index=False)
    pd.DataFrame(yearly_rows).to_csv(files["yearly"], index=False)
    contributions_long.to_csv(files["contributions"], index=False)
    trial_log.to_csv(files["trial_log"], index=False)
    if best_weights is not None:
        best_weights.to_csv(files["weights"], index=True)
    files["report"].write_text(
        _report(
            ranking,
            sample_rows_frame,
            start=args.start_date,
            end=args.end_date,
            best_variant=best_variant,
        ),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS62-RESIDUAL-HORIZON-SCAN",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "samples": {name: list(window) for name, window in SAMPLES.items()},
        "beta_lookback_days": BETA_LOOKBACK_DAYS,
        "min_beta_observations": MIN_BETA_OBSERVATIONS,
        "rebalance_days": REBALANCE_DAYS,
        "count": COUNT,
        "per_asset_weight": PER_ASSET_WEIGHT,
        "min_assets": MIN_ASSETS,
        "costs_bps": list(COSTS),
        "lookbacks": list(LOOKBACKS),
        "skips": list(SKIPS),
        "directions": list(DIRECTIONS),
        "variant_count": len(variants),
        "best_discovery_variant": best_variant,
        "trial_log": trial_rows,
        "funding_included": False,
        "orders_sent": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {output_dir} with {len(variants)} variants and {len(index)} days; "
        f"best discovery={best_variant}"
    )


if __name__ == "__main__":
    main()
