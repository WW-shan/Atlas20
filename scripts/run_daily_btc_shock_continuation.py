"""Backtest the frozen daily BTC-shock relative-continuation family.

This is a research-only portfolio backtest.  It reverses the failed LS68
reversal direction, allocates every holding phase as a fractional tranche, and
never exceeds gross exposure 1.0.  It sends no orders and does not alter the
live target book.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import dataclass
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

from scripts.run_intraday_btc_leadlag_diagnostic import (  # noqa: E402
    build_membership,
    signal_window_return,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

DEFAULT_START = "2021-01-01"
DEFAULT_END = "2026-11-12"
SIGNAL_DAYS = (1, 3, 5, 10)
HORIZON_DAYS = (1, 3, 5, 10)
SHOCK_BUCKETS = ("all", "abs_z_ge_2_0", "abs_z_ge_2_5")
TAIL_FRACTIONS = (0.10, 0.20)
COSTS_BPS = (2.0, 20.0, 50.0, 100.0)
BETA_WINDOW_DAYS = 120
MIN_BETA_OBSERVATIONS = 90
BETA_CLIP = (0.0, 4.0)
MIN_CROSS_SECTION = 8
GROSS_TOLERANCE = 1e-10
OVERLAY_ALLOCATIONS = (0.10, 0.20)
LS57_RETURNS = Path(
    "reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/"
    "PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/"
    "daily_returns.csv"
)
PERIODS: dict[str, tuple[str, str]] = {
    "full": ("2021-01-01", "2026-11-12"),
    "discovery": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2026-11-12"),
    "pre2022": ("2021-01-01", "2021-12-31"),
}


@dataclass(frozen=True)
class ContinuationVariant:
    variant_id: str
    signal_days: int
    horizon_days: int
    shock_bucket: str
    tail_fraction: float


@dataclass(frozen=True)
class ContinuationBacktest:
    daily_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    gross_exposure: pd.Series
    missing_return_observations: int


VARIANTS = tuple(
    ContinuationVariant(
        variant_id=(
            f"BTC_CONT_k{signal_days}_h{horizon_days}_"
            f"{shock_bucket}_tail{int(round(tail_fraction * 100)):02d}"
        ),
        signal_days=signal_days,
        horizon_days=horizon_days,
        shock_bucket=shock_bucket,
        tail_fraction=tail_fraction,
    )
    for signal_days in SIGNAL_DAYS
    for horizon_days in HORIZON_DAYS
    for shock_bucket in SHOCK_BUCKETS
    for tail_fraction in TAIL_FRACTIONS
)


def _utc_index(values: Any) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(values, utc=True))
    return index.sort_values()


def shock_gate_passes(z: pd.Series, bucket: str) -> pd.Series:
    """Return the finite-signal mask for one frozen shock bucket."""
    finite = pd.to_numeric(z, errors="coerce").notna()
    if bucket == "all":
        return finite
    prefix = "abs_z_ge_"
    if not bucket.startswith(prefix):
        raise ValueError(f"unknown shock bucket {bucket!r}")
    threshold = float(bucket[len(prefix) :].replace("_", "."))
    return finite & (pd.to_numeric(z, errors="coerce").abs() >= threshold)


def continuation_book(
    gap_row: pd.Series,
    eligible: pd.Series,
    tail_fraction: float,
) -> pd.Series | None:
    """Return a gross-1 dollar-neutral continuation book for one signal day."""
    if not 0.0 < tail_fraction < 0.5:
        raise ValueError("tail_fraction must be in (0, 0.5)")
    common = (
        eligible.reindex(gap_row.index).fillna(False).astype(bool)
        & gap_row.notna()
        & np.isfinite(gap_row.astype(float))
    )
    assets = gap_row.index[common]
    if len(assets) < MIN_CROSS_SECTION:
        return None
    gap = gap_row.loc[assets].astype(float)
    if gap.nunique() < 2:
        return None
    leg_count = max(1, int(np.ceil(len(gap) * tail_fraction)))
    if 2 * leg_count > len(gap):
        return None
    long_assets = tuple(str(asset) for asset in gap.nlargest(leg_count).index)
    short_assets = tuple(str(asset) for asset in gap.nsmallest(leg_count).index)
    if set(long_assets) & set(short_assets):
        return None
    per_asset = 0.5 / leg_count
    weights = pd.Series(0.0, index=gap.index, dtype=float)
    weights.loc[list(long_assets)] = per_asset
    weights.loc[list(short_assets)] = -per_asset
    return weights.sort_index()


def build_targets(
    *,
    index: pd.DatetimeIndex,
    price: pd.DataFrame,
    beta: pd.DataFrame,
    membership: pd.DataFrame,
    assets: list[str],
    signal_days: int,
    shock_bucket: str,
    tail_fraction: float,
) -> pd.DataFrame:
    """Build signal-date target books; execution timing is applied later."""
    signal_returns = signal_window_return(price[assets], signal_days)
    btc_shock = signal_window_return(price[["bitcoin"]], signal_days)["bitcoin"]
    shock_std = btc_shock.rolling(
        BETA_WINDOW_DAYS,
        min_periods=MIN_BETA_OBSERVATIONS,
    ).std(ddof=1)
    shock_z = (btc_shock / shock_std).replace([np.inf, -np.inf], np.nan)
    gap = signal_returns.sub(beta.mul(btc_shock, axis=0))
    gate = shock_gate_passes(shock_z, shock_bucket).reindex(index, fill_value=False)

    targets = pd.DataFrame(0.0, index=index, columns=assets, dtype=float)
    for position, date in enumerate(index):
        if not bool(gate.iloc[position]):
            continue
        book = continuation_book(
            gap.loc[date, assets],
            membership.loc[date, assets],
            tail_fraction,
        )
        if book is not None:
            targets.loc[date, assets] = book.reindex(assets, fill_value=0.0).to_numpy(
                dtype=float
            )
    return targets


def held_phase_weights(
    index: pd.DatetimeIndex,
    targets: pd.DataFrame,
    *,
    horizon: int,
) -> pd.DataFrame:
    """Convert every daily signal into an equal 1/h tranche held for h returns.

    A signal at close ``t`` is executed at close ``t+1``.  Its weight therefore
    first applies to the return from close ``t+1`` to ``t+2`` and remains for
    exactly ``horizon`` return observations.  Running every day's signal this
    way is the equal-weight ensemble of all h phase offsets.
    """
    if horizon < 1:
        raise ValueError("horizon must be positive")
    dates = _utc_index(index)
    if not dates.is_unique:
        raise ValueError("index must be unique")
    aligned = targets.reindex(index=dates).fillna(0.0).astype(float)
    weights = pd.DataFrame(0.0, index=dates, columns=aligned.columns, dtype=float)
    if len(dates) <= horizon + 1:
        return weights

    for signal_position in range(len(dates) - horizon - 1):
        target = aligned.iloc[signal_position]
        if not np.isfinite(target.to_numpy(dtype=float)).all():
            raise ValueError("target weights must be finite")
        if float(target.abs().sum()) > 1.0 + GROSS_TOLERANCE:
            raise ValueError("each signal book must have gross exposure at most one")
        if float(target.abs().sum()) <= GROSS_TOLERANCE:
            continue
        start = signal_position + 2
        stop = signal_position + horizon + 2
        weights.iloc[start:stop] += target.to_numpy(dtype=float) / float(horizon)

    gross = weights.abs().sum(axis=1)
    if float(gross.max()) > 1.0 + GROSS_TOLERANCE:
        raise ValueError(f"combined phase gross exceeds one: {float(gross.max()):.12f}")
    return weights


def backtest_continuation(
    *,
    index: pd.DatetimeIndex,
    returns: pd.DataFrame,
    targets: pd.DataFrame,
    horizon: int,
    cost_bps: float,
    normalize_gross: bool = False,
) -> ContinuationBacktest:
    """Run one signed continuation book with next-close execution and costs."""
    if cost_bps < 0.0 or not np.isfinite(cost_bps):
        raise ValueError("cost_bps must be finite and non-negative")
    dates = _utc_index(index)
    weights = held_phase_weights(dates, targets, horizon=horizon)
    if normalize_gross:
        gross = weights.abs().sum(axis=1)
        weights = weights.div(gross.replace(0.0, np.nan), axis=0).fillna(0.0)
    aligned_returns = returns.reindex(index=dates, columns=weights.columns)
    held = weights.abs() > GROSS_TOLERANCE
    missing = int(aligned_returns.isna().where(held).sum().sum())
    gross_return = (weights * aligned_returns.fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = float(weights.iloc[0].abs().sum())
        # The research window ends at a mark; charge an explicit liquidation of
        # every remaining tranche so terminal open positions are not free.
        turnover.iloc[-1] += float(weights.iloc[-1].abs().sum())
    trading_cost = turnover * float(cost_bps) / 10_000.0
    daily_returns = (gross_return - trading_cost).astype(float)
    if not daily_returns.empty:
        daily_returns.iloc[0] = 0.0
    return ContinuationBacktest(
        daily_returns=daily_returns.sort_index(),
        weights=weights.sort_index(),
        turnover=turnover.sort_index(),
        gross_exposure=weights.abs().sum(axis=1).sort_index(),
        missing_return_observations=missing,
    )


def _sample_series(series: pd.Series, sample: str) -> pd.Series:
    start, end = PERIODS[sample]
    window = series.loc[
        (series.index >= pd.Timestamp(start, tz="UTC"))
        & (series.index <= pd.Timestamp(end, tz="UTC"))
    ].copy()
    if not window.empty:
        window.iloc[0] = 0.0
    return window


def _sample_metrics(series: pd.Series, sample: str) -> dict[str, float]:
    window = _sample_series(series, sample)
    if window.empty:
        return {
            "days": 0.0,
            "multiple": float("nan"),
            "cagr": float("nan"),
            "sharpe": float("nan"),
            "max_drawdown": float("nan"),
        }
    return {key: float(value) for key, value in _metrics_from_returns(window).items()}


def select_candidate(summary: pd.DataFrame) -> str | None:
    """Apply the pre-registered discovery-only selection rule."""
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


def _acceptance_checks(
    selected: Mapping[str, Any],
    btc_full_multiple: float,
) -> dict[str, bool]:
    return {
        "validation_sharpe_20_positive": float(selected["validation_sharpe_20"]) > 0.0,
        "validation_sharpe_50_positive": float(selected["validation_sharpe_50"]) > 0.0,
        "pre2022_sharpe_20_positive": float(selected["pre2022_sharpe_20"]) > 0.0,
        "pre2022_sharpe_50_positive": float(selected["pre2022_sharpe_50"]) > 0.0,
        "full_multiple_beats_btc": float(selected["full_multiple_20"]) > btc_full_multiple,
        "full_mdd_no_worse_than_minus_50pct": float(selected["full_max_drawdown_20"])
        >= -0.50,
        "full_sharpe_above_0_5": float(selected["full_sharpe_20"]) > 0.50,
    }


def _compound(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    if not np.isfinite(array).all():
        raise ValueError("returns must be finite")
    return float(np.prod(1.0 + array) - 1.0)


def yearly_returns(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if clean.isna().any():
        raise ValueError("yearly returns require finite data")
    return clean.groupby(clean.index.year).apply(_compound)


def load_ls57_returns(path: Path = LS57_RETURNS) -> pd.Series:
    frame = pd.read_csv(path)
    date_column = "Unnamed: 0" if "Unnamed: 0" in frame.columns else frame.columns[0]
    index = _utc_index(frame[date_column])
    values = pd.to_numeric(frame["equity"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=index, name="ls57_20bps")
    if series.isna().any() or not np.isfinite(series.to_numpy(dtype=float)).all():
        raise ValueError("LS57 returns contain missing or non-finite values")
    return series[~series.index.duplicated(keep="last")].sort_index()


def _write_report(
    *,
    summary: pd.DataFrame,
    selected_row: Mapping[str, Any] | None,
    selected_metrics: pd.DataFrame | None,
    acceptance: Mapping[str, bool],
    yearly: pd.DataFrame | None,
    contributions: pd.DataFrame | None,
    overlay: pd.DataFrame | None,
    start: str,
    end: str,
) -> str:
    lines = [
        "# Daily BTC shock relative-continuation backtest",
        "",
        f"- sample: {start} → {end}",
        "- discovery: 2022-01-01 → 2023-12-31",
        "- validation: 2024-01-01 → 2026-11-12",
        "- independent pre-2022 OOS: 2021-01-01 → 2021-12-31",
        "- direction: long strongest relative gap / short weakest relative gap",
        "- execution: signal close t, earliest next close t+1, all phases equally weighted",
        "- costs: 2/20/50/100bps per side on turnover; funding not included in this screen",
        "",
        "## Discovery-ranked cells",
        "",
    ]
    display = summary.sort_values(
        ["discovery_sharpe_20", "turnover_20"],
        ascending=[False, True],
        kind="stable",
    ).head(16)
    columns = [
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
        "missing_20",
    ]
    lines.extend([dataframe_to_markdown(display[columns]), ""])

    if selected_row is None:
        lines.extend(
            [
                "## Decision",
                "",
                "No discovery cell met the frozen selection rule (`20bps` and `50bps` discovery Sharpe both positive).",
                "The family is rejected without looking for a validation winner or changing the grid.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "## Selected by discovery only",
            "",
            f"`{selected_row['variant_id']}`",
            "",
            dataframe_to_markdown(
                pd.DataFrame([selected_row]).T.reset_index().rename(
                    columns={"index": "field", 0: "value"}
                )
            ),
            "",
            "## Acceptance checks",
            "",
            *[f"- [{'x' if passed else ' '}] `{name}`" for name, passed in acceptance.items()],
            "",
            "## Sample metrics",
            "",
            dataframe_to_markdown(selected_metrics if selected_metrics is not None else pd.DataFrame()),
            "",
            "## Yearly returns",
            "",
            dataframe_to_markdown(yearly if yearly is not None else pd.DataFrame()),
            "",
            "## Asset contribution before costs",
            "",
            dataframe_to_markdown(contributions if contributions is not None else pd.DataFrame()),
            "",
            "## Return-space overlay with LS57",
            "",
            "These rows add sleeve returns to LS57 without modelling margin, gross, funding or a new order path; they are diagnostic only.",
            "",
            dataframe_to_markdown(overlay if overlay is not None else pd.DataFrame()),
            "",
            "## Interpretation guardrail",
            "",
            "A pass only earns a funding-aware Bitget mark/fill and gross boundary study. This screen fills missing held-asset returns with zero after counting them, so any material missing count invalidates an execution-level interpretation. The discovery/validation/pre-2022 split is reported as frozen, not as a claim that overlapping holding-period returns are independent.",
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
        parser.error(
            "LS69 is frozen to 2021-01-01 → 2026-11-12; pre-register another family for another window"
        )

    _, market, universe, raw_index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    index = _utc_index(raw_index)
    price = market.price.copy()
    price.index = _utc_index(price.index)
    price = price.reindex(index).sort_index()
    returns = market.returns.copy()
    returns.index = _utc_index(returns.index)
    returns = returns.reindex(index).sort_index()
    assets = sorted(
        [str(asset) for asset in price.columns if str(asset) != "bitcoin"],
        key=str.casefold,
    )
    assets = [asset for asset in assets if asset in returns.columns and asset in price.columns]
    membership = build_membership(universe, index=index, assets=assets)

    btc_returns = returns["bitcoin"].astype(float)
    market_var = btc_returns.rolling(
        BETA_WINDOW_DAYS,
        min_periods=MIN_BETA_OBSERVATIONS,
    ).var(ddof=1)
    beta = returns[assets].rolling(
        BETA_WINDOW_DAYS,
        min_periods=MIN_BETA_OBSERVATIONS,
    ).cov(btc_returns)
    beta = beta.div(market_var, axis=0).replace([np.inf, -np.inf], np.nan)
    beta = beta.clip(*BETA_CLIP)

    summary_rows: list[dict[str, Any]] = []
    daily_20bps: dict[str, pd.Series] = {}
    targets_by_variant: dict[str, pd.DataFrame] = {}
    results_20: dict[str, ContinuationBacktest] = {}
    for variant in VARIANTS:
        targets = build_targets(
            index=index,
            price=price,
            beta=beta,
            membership=membership,
            assets=assets,
            signal_days=variant.signal_days,
            shock_bucket=variant.shock_bucket,
            tail_fraction=variant.tail_fraction,
        )
        targets_by_variant[variant.variant_id] = targets
        results_by_cost: dict[float, ContinuationBacktest] = {}
        for cost in COSTS_BPS:
            results_by_cost[cost] = backtest_continuation(
                index=index,
                returns=returns[assets],
                targets=targets,
                horizon=variant.horizon_days,
                cost_bps=cost,
            )
        result_20 = results_by_cost[20.0]
        results_20[variant.variant_id] = result_20
        daily_20bps[variant.variant_id] = result_20.daily_returns
        row: dict[str, Any] = {
            "variant_id": variant.variant_id,
            "signal_days": variant.signal_days,
            "horizon_days": variant.horizon_days,
            "shock_bucket": variant.shock_bucket,
            "tail_fraction": variant.tail_fraction,
            "turnover_20": float(result_20.turnover.sum()),
            "average_active_gross_20": float(result_20.gross_exposure.mean()),
            "max_gross_20": float(result_20.gross_exposure.max()),
            "missing_20": result_20.missing_return_observations,
        }
        for sample in PERIODS:
            metrics_20 = _sample_metrics(result_20.daily_returns, sample)
            metrics_50 = _sample_metrics(results_by_cost[50.0].daily_returns, sample)
            for key, value in metrics_20.items():
                row[f"{sample}_{key}_20"] = value
            row[f"{sample}_sharpe_50"] = metrics_50["sharpe"]
            row[f"{sample}_multiple_50"] = metrics_50["multiple"]
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    selected_id = select_candidate(summary)
    selected_row: dict[str, Any] | None = None
    selected_metrics: pd.DataFrame | None = None
    acceptance: dict[str, bool] = {}
    yearly: pd.DataFrame | None = None
    contributions: pd.DataFrame | None = None
    overlay: pd.DataFrame | None = None
    selected_targets = pd.DataFrame()
    selected_result: ContinuationBacktest | None = None

    btc_full = _sample_metrics(btc_returns, "full")
    if selected_id is not None:
        selected_row = summary.loc[summary["variant_id"] == selected_id].iloc[0].to_dict()
        acceptance = _acceptance_checks(selected_row, btc_full["multiple"])
        selected_targets = targets_by_variant[selected_id]
        selected_result = results_20[selected_id]
        metric_rows: list[dict[str, Any]] = []
        for sample in PERIODS:
            variant_metrics = _sample_metrics(selected_result.daily_returns, sample)
            btc_metrics = _sample_metrics(btc_returns, sample)
            metric_rows.append(
                {"series": "ls69_selected_20bps", "sample": sample, **variant_metrics}
            )
            metric_rows.append({"series": "bitcoin_buy_hold", "sample": sample, **btc_metrics})
        selected_metrics = pd.DataFrame(metric_rows)
        yearly = pd.DataFrame(
            {
                "ls69_selected_20bps": yearly_returns(selected_result.daily_returns),
                "bitcoin_buy_hold": yearly_returns(btc_returns),
            }
        ).reset_index(names="year")

        aligned_returns = returns[assets].reindex(
            index=selected_result.weights.index,
            columns=selected_result.weights.columns,
        )
        asset_pnl = (selected_result.weights * aligned_returns.fillna(0.0)).sum(axis=0)
        contributions = (
            asset_pnl.rename("pnl_before_costs")
            .sort_values(ascending=False)
            .rename_axis("asset")
            .reset_index()
        )
        contributions["share_of_abs_pnl"] = contributions["pnl_before_costs"].abs() / contributions[
            "pnl_before_costs"
        ].abs().sum()

        ls57 = load_ls57_returns()
        common_start = max(selected_result.daily_returns.index.min(), ls57.index.min())
        common_end = min(selected_result.daily_returns.index.max(), ls57.index.max())
        ls57_window = ls57.loc[
            (ls57.index >= common_start) & (ls57.index <= common_end)
        ]
        sleeve_window = selected_result.daily_returns.reindex(ls57_window.index).fillna(0.0)
        overlay_rows: list[dict[str, Any]] = []
        overlay_series = {"ls57_20bps": ls57_window}
        for allocation in OVERLAY_ALLOCATIONS:
            label = f"ls57_plus_{int(round(allocation * 100)):02d}pct_ls69"
            overlay_series[label] = ls57_window + float(allocation) * sleeve_window
        for label, series in overlay_series.items():
            for sample in ("full", "discovery", "validation"):
                overlay_rows.append(
                    {"series": label, "sample": sample, **_sample_metrics(series, sample)}
                )
        overlay = pd.DataFrame(overlay_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "trial_summary.csv",
        "daily": output_dir / "daily_returns_20bps.csv",
        "weights": output_dir / "selected_weights_20bps.csv",
        "targets": output_dir / "selected_targets.csv",
        "metrics": output_dir / "selected_metrics.csv",
        "yearly": output_dir / "yearly_returns.csv",
        "contributions": output_dir / "asset_contributions.csv",
        "overlay": output_dir / "ls57_overlay.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")

    summary.to_csv(files["summary"], index=False)
    pd.DataFrame(daily_20bps).sort_index().to_csv(files["daily"])
    selected_targets.to_csv(files["targets"])
    if selected_result is not None:
        selected_result.weights.to_csv(files["weights"])
    if selected_metrics is not None:
        selected_metrics.to_csv(files["metrics"], index=False)
    if yearly is not None:
        yearly.to_csv(files["yearly"], index=False)
    if contributions is not None:
        contributions.to_csv(files["contributions"], index=False)
    if overlay is not None:
        overlay.to_csv(files["overlay"], index=False)
    files["report"].write_text(
        _write_report(
            summary=summary,
            selected_row=selected_row,
            selected_metrics=selected_metrics,
            acceptance=acceptance,
            yearly=yearly,
            contributions=contributions.head(20) if contributions is not None else None,
            overlay=overlay,
            start=args.start_date,
            end=args.end_date,
        ),
        encoding="utf-8",
    )
    manifest = {
        "candidate_family_id": "PR2026-11-LS69-DAILY-BTC-SHOCK-CONTINUATION",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "signal_days": list(SIGNAL_DAYS),
        "horizon_days": list(HORIZON_DAYS),
        "shock_buckets": list(SHOCK_BUCKETS),
        "tail_fractions": list(TAIL_FRACTIONS),
        "costs_bps": list(COSTS_BPS),
        "beta_window_days": BETA_WINDOW_DAYS,
        "min_beta_observations": MIN_BETA_OBSERVATIONS,
        "beta_clip": list(BETA_CLIP),
        "min_cross_section": MIN_CROSS_SECTION,
        "execution": "signal close t; earliest next close t+1; return begins t+2",
        "phase_treatment": "every signal contributes a 1/h tranche; aggregate gross <= 1",
        "periods": {key: list(value) for key, value in PERIODS.items()},
        "overlay_allocations": list(OVERLAY_ALLOCATIONS),
        "trial_count": len(VARIANTS),
        "selected_variant": selected_id,
        "acceptance_checks": acceptance,
        "acceptance_verdict": (
            "pass" if acceptance and all(acceptance.values()) else "fail"
        ),
        "assets": assets,
        "funding_included": False,
        "missing_return_treatment": "counted; zero contribution in this diagnostic",
        "orders_sent": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {output_dir} with {len(summary)} cells; "
        f"selected={selected_id}; verdict={manifest['acceptance_verdict']}"
    )


if __name__ == "__main__":
    main()
