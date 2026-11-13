"""Backtest LS79: LS57 plus an executable multi-phase churn ensemble."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import dataclass
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

from scripts.diagnose_top20_membership_events import membership_matrix  # noqa: E402
from scripts.run_daily_btc_shock_continuation import backtest_continuation  # noqa: E402
from scripts.run_ls57_churn_overlay import (  # noqa: E402
    ALLOCATIONS,
    GROSS_CAP,
    LS57_DIR,
    _sample_metrics,
    load_return_series,
    load_target_gross,
    scale_sleeve_to_residual_gross,
)
from scripts.run_ls57_churn_spot_btc_short_alt import (  # noqa: E402
    FUNDING_MULTIPLIERS,
    MIN_FUNDING_COVERAGE,
    _short_funding_return,
    build_cross_venue_funding_panels,
    executable_short_availability,
    restrict_targets_to_executable_shorts,
    short_funding_coverage,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402
from scripts.run_top20_churn_gated import build_gate_series  # noqa: E402
from scripts.run_top20_churn_short import build_churn_targets  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-09-20"
CONFIRMATION_DAYS = (3, 7, 14)
HOLD_DAYS = (7, 14, 28, 56)
COSTS_BPS = (20.0, 50.0, 100.0)
VARIANTS = tuple(
    (confirmation_days, hold_days)
    for confirmation_days in CONFIRMATION_DAYS
    for hold_days in HOLD_DAYS
)


@dataclass(frozen=True)
class EnsembleBacktest:
    daily_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    gross_exposure: pd.Series
    active_variant_count: pd.Series
    missing_return_observations: int


def average_active_variant_weights(
    variant_weights: dict[tuple[int, int], pd.DataFrame],
) -> tuple[pd.DataFrame, pd.Series]:
    """Average active variant books so ensemble gross never exceeds one."""
    if not variant_weights:
        raise ValueError("at least one variant is required")
    labels = list(variant_weights)
    first = variant_weights[labels[0]]
    index = first.index
    columns = pd.Index(
        sorted({str(column) for weights in variant_weights.values() for column in weights.columns})
    )
    aligned = {
        label: weights.reindex(index=index, columns=columns).fillna(0.0)
        for label, weights in variant_weights.items()
    }
    gross_by_variant = pd.DataFrame(
        {label: weights.abs().sum(axis=1) for label, weights in aligned.items()},
        index=index,
    )
    active_count = gross_by_variant.gt(0.0).sum(axis=1).astype(int)
    combined = sum(
        aligned.values(),
        pd.DataFrame(0.0, index=index, columns=columns),
    )
    ensemble = combined.div(active_count.replace(0, np.nan), axis=0).fillna(0.0)
    gross = ensemble.abs().sum(axis=1)
    if float(gross.max()) > 1.0 + 1e-10:
        raise ValueError(f"ensemble gross exceeds one: {float(gross.max()):.12f}")
    return ensemble, active_count


def backtest_ensemble_weights(
    *,
    index: pd.DatetimeIndex,
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    active_variant_count: pd.Series,
    cost_bps: float,
) -> EnsembleBacktest:
    """Compute ensemble PnL and one-way turnover from the combined book."""
    if cost_bps < 0.0 or not np.isfinite(cost_bps):
        raise ValueError("cost_bps must be finite and non-negative")
    dates = pd.DatetimeIndex(pd.to_datetime(index, utc=True)).sort_values()
    aligned_weights = weights.reindex(index=dates).fillna(0.0).astype(float)
    aligned_returns = returns.reindex(index=dates, columns=aligned_weights.columns)
    held = aligned_weights.abs() > 1e-12
    missing = int(aligned_returns.isna().where(held).sum().sum())
    gross_return = (aligned_weights * aligned_returns.fillna(0.0)).sum(axis=1)
    turnover = aligned_weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = float(aligned_weights.iloc[0].abs().sum())
        turnover.iloc[-1] += float(aligned_weights.iloc[-1].abs().sum())
    daily_returns = (gross_return - turnover * float(cost_bps) / 10_000.0).astype(float)
    if not daily_returns.empty:
        daily_returns.iloc[0] = 0.0
    return EnsembleBacktest(
        daily_returns=daily_returns,
        weights=aligned_weights,
        turnover=turnover,
        gross_exposure=aligned_weights.abs().sum(axis=1),
        active_variant_count=active_variant_count.reindex(dates).fillna(0).astype(int),
        missing_return_observations=missing,
    )


def short_asset_shares(weights: pd.DataFrame) -> pd.DataFrame:
    """Share of total short weight contributed by each asset."""
    short = weights.clip(upper=0.0).abs()
    total = float(short.to_numpy().sum())
    if total <= 0.0:
        return pd.DataFrame(columns=["asset", "short_weight", "share"])
    shares = short.sum(axis=0).rename("short_weight").rename_axis("asset").reset_index()
    shares = shares.loc[shares["short_weight"] > 0.0].copy()
    shares["share"] = shares["short_weight"] / total
    return shares.sort_values(["share", "asset"], ascending=[False, True], kind="stable").reset_index(drop=True)


def _calendar_metrics(series: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, segment in series.groupby(series.index.year, sort=True):
        metrics = _metrics_from_returns(segment)
        rows.append({"year": int(year), **{key: float(value) for key, value in metrics.items()}})
    return pd.DataFrame(rows)


def _rolling_365(series: pd.Series) -> pd.DataFrame:
    log_returns = np.log1p(series.clip(lower=-0.999999, upper=None))
    cumulative = log_returns.cumsum()
    rolling_multiple = np.exp(cumulative - cumulative.shift(365)) - 1.0
    rolling_sharpe = (
        np.sqrt(365.0)
        * series.rolling(365, min_periods=365).mean()
        / series.rolling(365, min_periods=365).std(ddof=1)
    )
    return pd.DataFrame({"rolling_multiple_365d": rolling_multiple, "rolling_sharpe_365d": rolling_sharpe})


def _newey_west_t(series: pd.Series, *, lags: int = 63) -> float:
    values = pd.to_numeric(series, errors="raise").dropna().to_numpy(dtype=float)
    if len(values) <= lags + 1:
        return float("nan")
    mean = float(values.mean())
    centered = values - mean
    variance = float(np.dot(centered, centered) / len(values))
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / float(lags + 1)
        covariance = float(np.dot(centered[lag:], centered[:-lag]) / len(values))
        variance += 2.0 * weight * covariance
    standard_error = float(np.sqrt(max(variance, 0.0) / len(values)))
    return mean / standard_error if standard_error > 0.0 else float("nan")


def _circular_block_bootstrap(
    log_excess: pd.Series,
    *,
    block_length: int = 63,
    draws: int = 5_000,
    seed: int = 79,
) -> dict[str, float]:
    """Bootstrap total log outperformance with circular blocks."""
    values = pd.to_numeric(log_excess, errors="raise").dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return {
            "bootstrap_probability_positive": float("nan"),
            "bootstrap_total_log_excess_ci_2_5": float("nan"),
            "bootstrap_total_log_excess_median": float("nan"),
            "bootstrap_total_log_excess_ci_97_5": float("nan"),
        }
    n_blocks = int(np.ceil(len(values) / block_length))
    offsets = np.arange(block_length)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(values), size=(draws, n_blocks))
    indices = (starts[:, :, None] + offsets[None, None, :]) % len(values)
    totals = values[indices.reshape(draws, -1)[:, : len(values)]].sum(axis=1)
    return {
        "bootstrap_probability_positive": float((totals > 0.0).mean()),
        "bootstrap_total_log_excess_ci_2_5": float(np.quantile(totals, 0.025)),
        "bootstrap_total_log_excess_median": float(np.median(totals)),
        "bootstrap_total_log_excess_ci_97_5": float(np.quantile(totals, 0.975)),
    }


def robustness_diagnostics(
    overlay: pd.Series,
    baseline: pd.Series,
    *,
    scenario: str,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Yearly, leave-one-year, rolling and HAC diagnostics for an overlay."""
    aligned = pd.concat({"overlay": overlay, "baseline": baseline}, axis=1).dropna()
    overlay = aligned["overlay"].astype(float)
    baseline = aligned["baseline"].astype(float)
    excess = overlay - baseline
    yearly = _calendar_metrics(overlay).rename(columns=lambda column: f"overlay_{column}" if column != "year" else column)
    baseline_yearly = _calendar_metrics(baseline).rename(columns=lambda column: f"baseline_{column}" if column != "year" else column)
    yearly = yearly.merge(baseline_yearly, on="year", how="outer").sort_values("year")
    yearly["scenario"] = scenario
    yearly["excess_multiple"] = yearly["overlay_multiple"] - yearly["baseline_multiple"]
    yearly["excess_sharpe"] = yearly["overlay_sharpe"] - yearly["baseline_sharpe"]

    leave_rows: list[dict[str, Any]] = []
    for year in sorted(overlay.index.year.unique()):
        kept = overlay.index.year != year
        overlay_metrics = _metrics_from_returns(overlay.loc[kept])
        baseline_metrics = _metrics_from_returns(baseline.loc[kept])
        leave_rows.append(
            {
                "scenario": scenario,
                "excluded_year": int(year),
                "overlay_multiple": float(overlay_metrics["multiple"]),
                "baseline_multiple": float(baseline_metrics["multiple"]),
                "excess_multiple": float(overlay_metrics["multiple"] - baseline_metrics["multiple"]),
                "overlay_sharpe": float(overlay_metrics["sharpe"]),
                "baseline_sharpe": float(baseline_metrics["sharpe"]),
                "excess_sharpe": float(overlay_metrics["sharpe"] - baseline_metrics["sharpe"]),
                "overlay_max_drawdown": float(overlay_metrics["max_drawdown"]),
                "baseline_max_drawdown": float(baseline_metrics["max_drawdown"]),
            }
        )
    leave_one_out = pd.DataFrame(leave_rows)

    overlay_rolling = _rolling_365(overlay)
    baseline_rolling = _rolling_365(baseline)
    rolling = pd.concat({"overlay": overlay_rolling, "baseline": baseline_rolling}, axis=1).dropna()
    rolling["excess_multiple_365d"] = (
        rolling[("overlay", "rolling_multiple_365d")]
        - rolling[("baseline", "rolling_multiple_365d")]
    )
    rolling["excess_sharpe_365d"] = (
        rolling[("overlay", "rolling_sharpe_365d")]
        - rolling[("baseline", "rolling_sharpe_365d")]
    )
    rolling = rolling.reset_index().rename(columns={rolling.index.name or "index": "date"})
    rolling.insert(0, "scenario", scenario)
    rolling.columns = [
        "_|_".join(str(part) for part in column if part)
        if isinstance(column, tuple)
        else str(column)
        for column in rolling.columns
    ]

    log_excess = np.log1p(overlay.clip(lower=-0.999999)) - np.log1p(
        baseline.clip(lower=-0.999999)
    )
    bootstrap = _circular_block_bootstrap(log_excess)
    summary = {
        "scenario": scenario,
        "years_outperforming": int((yearly["excess_multiple"] > 0.0).sum()),
        "years_total": int(len(yearly)),
        "best_year_excess_multiple": float(yearly["excess_multiple"].max()),
        "worst_year_excess_multiple": float(yearly["excess_multiple"].min()),
        "worst_leave_one_year_excess_multiple": float(leave_one_out["excess_multiple"].min()),
        "worst_leave_one_year_excess_sharpe": float(leave_one_out["excess_sharpe"].min()),
        "rolling_365_windows": int(len(rolling)),
        "rolling_365_outperform_share": float((rolling["excess_multiple_365d"] > 0.0).mean()),
        "worst_rolling_365_excess_multiple": float(rolling["excess_multiple_365d"].min()),
        "median_rolling_365_excess_multiple": float(rolling["excess_multiple_365d"].median()),
        "mean_daily_excess": float(excess.mean()),
        "annualized_excess_sharpe": float(np.sqrt(365.0) * excess.mean() / excess.std(ddof=1)),
        "newey_west_t_63": _newey_west_t(excess, lags=63),
        **bootstrap,
    }
    return summary, yearly, leave_one_out, rolling


def pre2022_ensemble_diagnostic(config_path: str) -> pd.DataFrame:
    """Price-only 2021 negative control; funding availability is unavailable."""
    _, market, universe, raw_index = _load_market(
        config_path,
        start_date="2021-01-01",
        end_date="2021-12-31",
    )
    index = pd.DatetimeIndex(pd.to_datetime(raw_index, utc=True)).sort_values()
    price = market.price.copy()
    price.index = pd.DatetimeIndex(pd.to_datetime(price.index, utc=True)).sort_values()
    price = price.reindex(index).sort_index()
    returns = market.returns.copy()
    returns.index = pd.DatetimeIndex(pd.to_datetime(returns.index, utc=True)).sort_values()
    returns = returns.reindex(index).sort_index()
    assets = sorted(
        [str(asset) for asset in price.columns if str(asset) != "bitcoin" and str(asset) in returns.columns],
        key=str.casefold,
    )
    present = membership_matrix(universe, index=index)
    gate = build_gate_series(price=price, returns=returns, present=present, assets=assets)["alt_rel_60"]
    variant_weights: dict[tuple[int, int], pd.DataFrame] = {}
    active_counts: dict[tuple[int, int], pd.Series] = {}
    for confirmation_days in CONFIRMATION_DAYS:
        targets = build_churn_targets(
            present=present,
            confirmation_days=confirmation_days,
            assets=assets,
        )
        targets.loc[~gate.reindex(targets.index, fill_value=False).astype(bool), :] = 0.0
        for hold_days in HOLD_DAYS:
            result = backtest_continuation(
                index=index,
                returns=returns[["bitcoin", *assets]],
                targets=targets,
                horizon=hold_days,
                cost_bps=20.0,
                normalize_gross=True,
            )
            variant_weights[(confirmation_days, hold_days)] = result.weights
            active_counts[(confirmation_days, hold_days)] = (
                result.weights.abs().sum(axis=1) > 0.0
            ).astype(int)
    ensemble_weights, ensemble_active = average_active_variant_weights(variant_weights)
    rows: list[dict[str, Any]] = []
    for cost in COSTS_BPS:
        result = backtest_ensemble_weights(
            index=index,
            returns=returns[["bitcoin", *assets]],
            weights=ensemble_weights,
            active_variant_count=ensemble_active,
            cost_bps=cost,
        )
        metrics = _metrics_from_returns(result.daily_returns)
        rows.append(
            {
                "cost_bps": cost,
                **{key: float(value) for key, value in metrics.items()},
                "mean_gross": float(result.gross_exposure.mean()),
                "turnover": float(result.turnover.sum()),
                "missing_return_observations": result.missing_return_observations,
                "funding_included": False,
                "note": "2021 price-only negative control; funding availability absent",
            }
        )
    return pd.DataFrame(rows)


def _variant_metrics(
    variant_weights: dict[tuple[int, int], pd.DataFrame],
    returns: pd.DataFrame,
    active_counts: dict[tuple[int, int], pd.Series],
    *,
    cost_bps: float,
    index: pd.DatetimeIndex,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label in VARIANTS:
        weights = variant_weights[label]
        result = backtest_ensemble_weights(
            index=index,
            returns=returns,
            weights=weights,
            active_variant_count=active_counts[label],
            cost_bps=cost_bps,
        )
        full = _sample_metrics(result.daily_returns, "full")
        validation = _sample_metrics(result.daily_returns, "validation")
        rows.append(
            {
                "variant_id": f"m{label[0]}_h{label[1]}",
                "confirmation_days": label[0],
                "hold_days": label[1],
                "full_multiple_20bps": full["multiple"],
                "full_sharpe_20bps": full["sharpe"],
                "full_max_drawdown_20bps": full["max_drawdown"],
                "validation_multiple_20bps": validation["multiple"],
                "validation_sharpe_20bps": validation["sharpe"],
                "active_days": int((result.gross_exposure > 0.0).sum()),
                "max_gross": float(result.gross_exposure.max()),
            }
        )
    return pd.DataFrame(rows)


def _report(
    summary: pd.DataFrame,
    variants: pd.DataFrame,
    shares: pd.DataFrame,
    baseline: dict[str, float],
    baseline_validation: dict[str, float],
    selected: float | None,
    *,
    coverage: float,
    standalone: dict[str, float],
    robustness_summary: list[dict[str, Any]],
    pre2022: pd.DataFrame,
) -> str:
    max_share = float(shares["share"].max()) if not shares.empty else 0.0
    top_asset = str(shares.iloc[0]["asset"]) if not shares.empty else "none"
    lines = [
        "# LS57 + executable multi-phase churn ensemble",
        "",
        f"- LS57 baseline: {baseline['multiple']:.4f}x / Sharpe {baseline['sharpe']:.4f} / MDD {baseline['max_drawdown']:.4%}",
        f"- LS57 validation: {baseline_validation['multiple']:.4f}x / Sharpe {baseline_validation['sharpe']:.4f}",
        f"- ensemble standalone 20bps: {standalone['multiple']:.4f}x / Sharpe {standalone['sharpe']:.4f} / MDD {standalone['max_drawdown']:.4%}",
        f"- short funding coverage: {coverage:.4%}",
        f"- largest short-asset share: {max_share:.2%} ({top_asset})",
        "- all 12 pre-registered m/h cells are included; no validation-based cell selection",
        "- BTC long is spot; alt shorts are perpetuals; costs and funding are charged on the combined book",
        "",
        "## Variant metrics at 20bps",
        "",
        dataframe_to_markdown(variants.reset_index(drop=True)),
        "",
        "## Ensemble overlay results",
        "",
        dataframe_to_markdown(
            summary[
                [
                    "allocation",
                    "sleeve_cost_bps",
                    "funding_scenario",
                    "full_multiple",
                    "full_sharpe",
                    "full_max_drawdown",
                    "validation_multiple",
                    "validation_sharpe",
                    "max_combined_gross",
                    "funding_sum",
                    "passes_primary",
                ]
            ].reset_index(drop=True)
        ),
        "",
        "## Robustness diagnostics",
        "",
        dataframe_to_markdown(pd.DataFrame(robustness_summary).reset_index(drop=True)),
        "",
        "## 2021 price-only negative control",
        "",
        dataframe_to_markdown(pre2022.reset_index(drop=True)),
        "",
        "## Short concentration",
        "",
        dataframe_to_markdown(shares.head(15).reset_index(drop=True)),
        "",
        "## Decision",
        "",
    ]
    if selected is None:
        lines.append("No allocation passed the 20bps normal + 1x-adverse primary gate.")
    else:
        lines.append(
            f"Largest allocation passing 20bps normal + 1x adverse: **{selected:.0%} NAV**. "
            "Conditional overlay candidate only; live promotion still requires Bitget mark/fill/funding validation."
        )
    tail_allocation = selected if selected is not None else max(ALLOCATIONS)
    tail = summary.loc[
        (summary["allocation"] == tail_allocation)
        & (summary["sleeve_cost_bps"] == 20.0)
    ]
    lines.extend(["", f"### Tail scenarios at {tail_allocation:.0%} allocation", ""])
    lines.append(
        dataframe_to_markdown(
            tail[
                [
                    "funding_scenario",
                    "full_multiple",
                    "full_sharpe",
                    "full_max_drawdown",
                    "validation_multiple",
                    "validation_sharpe",
                    "passes_primary",
                ]
            ].reset_index(drop=True)
        )
    )
    lines.extend(
        [
            "",
            "2x/3x adverse and 100bps are reported as tail evidence. They block promotion but do not "
            "trigger allocation or threshold tuning inside this family.",
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
    if args.start_date != DEFAULT_START or args.end_date != DEFAULT_END:
        parser.error("LS79 is frozen to 2022-01-01 -> 2026-09-20")

    lower = pd.Timestamp(args.start_date, tz="UTC")
    upper = pd.Timestamp(args.end_date, tz="UTC")
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
        [str(asset) for asset in price.columns if str(asset) != "bitcoin" and str(asset) in returns.columns],
        key=str.casefold,
    )
    present = membership_matrix(universe, index=index)
    gates = build_gate_series(price=price, returns=returns, present=present, assets=assets)
    normal_rates, adverse_rates = build_cross_venue_funding_panels(coins=assets, index=index)
    available = executable_short_availability(normal_rates)

    restricted_targets: dict[tuple[int, int], pd.DataFrame] = {}
    for confirmation_days in CONFIRMATION_DAYS:
        targets = build_churn_targets(
            present=present,
            confirmation_days=confirmation_days,
            assets=assets,
        )
        targets.loc[~gates["alt_rel_60"].reindex(targets.index, fill_value=False).astype(bool), :] = 0.0
        restricted_targets[(confirmation_days,)] = restrict_targets_to_executable_shorts(targets, available)

    variant_weights: dict[tuple[int, int], pd.DataFrame] = {}
    variant_active_counts: dict[tuple[int, int], pd.Series] = {}
    for label in VARIANTS:
        confirmation_days, hold_days = label
        variant_targets = restricted_targets[(confirmation_days,)]
        result = backtest_continuation(
            index=index,
            returns=returns[["bitcoin", *assets]],
            targets=variant_targets,
            horizon=hold_days,
            cost_bps=20.0,
            normalize_gross=True,
        )
        variant_weights[label] = result.weights
        variant_active_counts[label] = (result.weights.abs().sum(axis=1) > 0.0).astype(int)

    ensemble_weights, ensemble_active = average_active_variant_weights(variant_weights)
    ensemble_by_cost = {
        cost: backtest_ensemble_weights(
            index=index,
            returns=returns[["bitcoin", *assets]],
            weights=ensemble_weights,
            active_variant_count=ensemble_active,
            cost_bps=cost,
        )
        for cost in COSTS_BPS
    }
    ensemble_20 = ensemble_by_cost[20.0]
    standalone = _sample_metrics(ensemble_20.daily_returns, "full")
    variant_table = _variant_metrics(
        variant_weights,
        returns[["bitcoin", *assets]],
        variant_active_counts,
        cost_bps=20.0,
        index=index,
    )
    coverage = short_funding_coverage(ensemble_weights, normal_rates)
    funding_by_scenario = {
        scenario: _short_funding_return(
            ensemble_weights,
            normal_rates,
            adverse_rates,
            multiplier=multiplier,
        )
        for scenario, multiplier in FUNDING_MULTIPLIERS.items()
    }
    shares = short_asset_shares(ensemble_weights)

    ls57_returns = load_return_series(LS57_DIR / "daily_returns.csv")
    ls57_returns = ls57_returns.loc[(ls57_returns.index >= lower) & (ls57_returns.index <= upper)]
    ls57_gross = load_target_gross(LS57_DIR / "target_gross.csv")
    ls57_gross = ls57_gross.loc[(ls57_gross.index >= lower) & (ls57_gross.index <= upper)]
    base_gross = ls57_gross.reindex(ls57_returns.index).ffill().fillna(0.0)
    baseline = _sample_metrics(ls57_returns, "full")
    baseline_validation = _sample_metrics(ls57_returns, "validation")

    rows: list[dict[str, Any]] = []
    combined_by_key: dict[tuple[float, float, str], pd.Series] = {}
    for allocation in ALLOCATIONS:
        scale_frame = scale_sleeve_to_residual_gross(
            ls57_gross=base_gross,
            sleeve_gross=ensemble_20.gross_exposure,
            allocation=allocation,
        ).reindex(ls57_returns.index)
        scale_delta = scale_frame["sleeve_scale"].diff().abs().fillna(
            scale_frame["sleeve_scale"].abs()
        )
        for cost, result in ensemble_by_cost.items():
            scale_cost = (
                scale_delta
                * result.gross_exposure.reindex(ls57_returns.index).shift(1).fillna(
                    result.gross_exposure.reindex(ls57_returns.index)
                )
                * float(cost)
                / 10_000.0
            )
            for scenario, funding in funding_by_scenario.items():
                funding_aligned = funding.reindex(ls57_returns.index).fillna(0.0)
                combined = (
                    ls57_returns
                    + scale_frame["sleeve_scale"]
                    * (result.daily_returns.reindex(ls57_returns.index).fillna(0.0) + funding_aligned)
                    - scale_cost
                )
                combined_by_key[(allocation, cost, scenario)] = combined.rename(
                    f"ls57_plus_{int(round(allocation * 100)):02d}pct_{int(cost)}bps_{scenario}"
                )
                full = _sample_metrics(combined, "full")
                validation = _sample_metrics(combined, "validation")
                passes = (
                    full["multiple"] > baseline["multiple"]
                    and full["sharpe"] > baseline["sharpe"]
                    and full["max_drawdown"] >= baseline["max_drawdown"] - 0.01
                    and validation["multiple"] > baseline_validation["multiple"]
                    and validation["sharpe"] > baseline_validation["sharpe"]
                    and float(scale_frame["combined_gross"].max()) <= GROSS_CAP + 1e-10
                    and coverage >= MIN_FUNDING_COVERAGE
                )
                rows.append(
                    {
                        "allocation": allocation,
                        "sleeve_cost_bps": cost,
                        "funding_scenario": scenario,
                        "full_multiple": full["multiple"],
                        "full_sharpe": full["sharpe"],
                        "full_max_drawdown": full["max_drawdown"],
                        "validation_multiple": validation["multiple"],
                        "validation_sharpe": validation["sharpe"],
                        "max_combined_gross": float(scale_frame["combined_gross"].max()),
                        "funding_sum": float((scale_frame["sleeve_scale"] * funding_aligned).sum()),
                        "scale_change_cost_sum": float(scale_cost.sum()),
                        "passes_primary": bool(passes),
                    }
                )

    summary = pd.DataFrame(rows)
    primary = summary.loc[
        (summary["sleeve_cost_bps"] == 20.0)
        & summary["funding_scenario"].isin(["normal", "adverse_1x"])
        & summary["passes_primary"]
    ]
    selected = None
    if not primary.empty:
        counts = primary.groupby("allocation")["funding_scenario"].nunique()
        allocations = counts.loc[counts == 2]
        if not allocations.empty:
            selected = float(allocations.index.max())

    diagnostic_allocation = selected if selected is not None else max(ALLOCATIONS)
    selected_daily = pd.DataFrame(
        {
            "normal": combined_by_key[(diagnostic_allocation, 20.0, "normal")],
            "adverse_1x": combined_by_key[(diagnostic_allocation, 20.0, "adverse_1x")],
        }
    )
    robustness_rows: list[dict[str, Any]] = []
    yearly_frames: list[pd.DataFrame] = []
    leave_frames: list[pd.DataFrame] = []
    rolling_frames: list[pd.DataFrame] = []
    for scenario in ("normal", "adverse_1x"):
        summary_row, yearly, leave_one_out, rolling = robustness_diagnostics(
            selected_daily[scenario],
            ls57_returns,
            scenario=scenario,
        )
        robustness_rows.append(summary_row)
        yearly_frames.append(yearly)
        leave_frames.append(leave_one_out)
        rolling_frames.append(rolling)
    yearly_diagnostics = pd.concat(yearly_frames, ignore_index=True)
    leave_one_year_out = pd.concat(leave_frames, ignore_index=True)
    rolling_diagnostics = pd.concat(rolling_frames, ignore_index=True)

    pre2022 = pre2022_ensemble_diagnostic(args.config)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "selected_daily": output_dir / "selected_daily_returns.csv",
        "yearly_diagnostics": output_dir / "yearly_diagnostics.csv",
        "leave_one_year_out": output_dir / "leave_one_year_out.csv",
        "rolling_diagnostics": output_dir / "rolling_365d_diagnostics.csv",
        "robustness": output_dir / "robustness_summary.json",
        "pre2022": output_dir / "pre2022_ensemble_metrics.csv",
        "summary": output_dir / "overlay_summary.csv",
        "variants": output_dir / "variant_metrics.csv",
        "shares": output_dir / "short_asset_shares.csv",
        "weights": output_dir / "ensemble_weights.csv",
        "funding": output_dir / "sleeve_funding.csv",
        "daily_20": output_dir / "ensemble_daily_20bps.csv",
        "daily_50": output_dir / "ensemble_daily_50bps.csv",
        "daily_100": output_dir / "ensemble_daily_100bps.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    selected_daily.to_csv(files["selected_daily"])
    yearly_diagnostics.to_csv(files["yearly_diagnostics"], index=False)
    leave_one_year_out.to_csv(files["leave_one_year_out"], index=False)
    rolling_diagnostics.to_csv(files["rolling_diagnostics"], index=False)
    files["robustness"].write_text(
        json.dumps(robustness_rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pre2022.to_csv(files["pre2022"], index=False)
    variant_table.to_csv(files["variants"], index=False)
    shares.to_csv(files["shares"], index=False)
    ensemble_weights.to_csv(files["weights"])
    pd.DataFrame(funding_by_scenario).to_csv(files["funding"])
    ensemble_by_cost[20.0].daily_returns.to_csv(files["daily_20"])
    ensemble_by_cost[50.0].daily_returns.to_csv(files["daily_50"])
    ensemble_by_cost[100.0].daily_returns.to_csv(files["daily_100"])
    files["report"].write_text(
        _report(
            summary,
            variant_table,
            shares,
            baseline,
            baseline_validation,
            selected,
            coverage=coverage,
            standalone=standalone,
            robustness_summary=robustness_rows,
            pre2022=pre2022,
        ),
        encoding="utf-8",
    )
    manifest = {
        "candidate_id": "PR2026-11-LS79-LS57-CHURN-MULTIPHASE-ENSEMBLE",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "variants": [f"m{confirmation_days}_h{hold_days}" for confirmation_days, hold_days in VARIANTS],
        "allocations": list(ALLOCATIONS),
        "costs_bps": list(COSTS_BPS),
        "funding_scenarios": list(FUNDING_MULTIPLIERS),
        "funding_coverage": coverage,
        "standalone": standalone,
        "selected_allocation": selected,
        "diagnostic_allocation": diagnostic_allocation,
        "robustness": robustness_rows,
        "pre2022_price_only": pre2022.to_dict(orient="records"),
        "baseline": baseline,
        "baseline_validation": baseline_validation,
        "gross_cap": GROSS_CAP,
        "max_ensemble_gross": float(ensemble_20.gross_exposure.max()),
        "missing_return_observations": ensemble_20.missing_return_observations,
        "btc_leg": "spot",
        "alt_short_leg": "perpetual",
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_dir}; selected={selected}; coverage={coverage:.4f}")


if __name__ == "__main__":
    main()
