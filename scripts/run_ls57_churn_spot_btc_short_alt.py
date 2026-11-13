"""Executable LS57 + churn overlay: short alt perpetuals, long BTC spot."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.data import load_binance_funding  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_daily_btc_shock_continuation import backtest_continuation  # noqa: E402
from scripts.run_ls57_churn_overlay import (  # noqa: E402
    ALLOCATIONS,
    GROSS_CAP,
    LS57_DIR,
    LS74_DIR,
    _sample_metrics,
    load_return_series,
    load_target_gross,
    scale_sleeve_to_residual_gross,
)
from scripts.run_phase_momentum import _load_market  # noqa: E402

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-09-20"
COST_FILES = {
    20.0: "daily_returns_20bps.csv",
    50.0: "daily_returns_50bps.csv",
    100.0: "daily_returns_100bps.csv",
}
FUNDING_MULTIPLIERS = {
    "normal": 0,
    "adverse_1x": 1,
    "adverse_2x": 2,
    "adverse_3x": 3,
}
FUNDING_LOOKBACK_DAYS = 7
MIN_FUNDING_COVERAGE = 0.95
BINANCE_FUNDING_DIR = Path("data/raw/binance_funding")
BYBIT_FUNDING_DIR = Path("data/raw/alternative_funding/bybit")
BITGET_FUNDING_DIR = Path("data/raw/bitget_derivatives/funding")


def _load_generic_funding_dir(path: Path) -> dict[str, pd.Series]:
    """Load one generic funding directory, keeping missing dates missing."""
    series: dict[str, pd.Series] = {}
    if not path.is_dir():
        return series
    for csv_path in sorted(path.glob("*.csv")):
        frame = pd.read_csv(csv_path)
        if not {"funding_time", "funding_rate"}.issubset(frame.columns):
            continue
        stamps = pd.to_datetime(frame["funding_time"], utc=True, errors="coerce")
        values = pd.to_numeric(frame["funding_rate"], errors="coerce")
        loaded = pd.Series(values.to_numpy(dtype=float), index=stamps).dropna()
        loaded = loaded[~loaded.index.duplicated(keep="last")].sort_index()
        if not loaded.empty:
            series[csv_path.stem] = loaded
    return series


def _daily_funding_panel(
    funding: dict[str, pd.Series],
    *,
    absolute: bool = False,
) -> pd.DataFrame:
    """Aggregate settlement rates into UTC calendar-day sums."""
    columns: list[pd.Series] = []
    for coin, rates in funding.items():
        values = rates.abs() if absolute else rates
        daily = values.groupby(values.index.normalize()).sum(min_count=1)
        daily.name = coin
        columns.append(daily)
    if not columns:
        return pd.DataFrame(dtype=float)
    return pd.concat(columns, axis=1).sort_index()


def build_cross_venue_funding_panels(
    *,
    coins: Iterable[str],
    index: pd.DatetimeIndex,
    binance_dir: Path = BINANCE_FUNDING_DIR,
    bybit_dir: Path = BYBIT_FUNDING_DIR,
    bitget_dir: Path = BITGET_FUNDING_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return conservative normal and adverse daily rates for short legs.

    Normal: minimum daily settlement sum across venues (worst for a short).
    Adverse: maximum daily absolute-settlement sum across venues (worst for a
    short before the sign reversal used by the adverse scenario).
    """
    coin_set = {str(coin) for coin in coins}
    panels: list[pd.DataFrame] = []
    absolute_panels: list[pd.DataFrame] = []
    if binance_dir.is_dir() and coin_set:
        binance = load_binance_funding(binance_dir, coins=coin_set)
        if not binance.empty:
            panels.append(binance.groupby(binance.index.normalize()).sum(min_count=1))
            absolute_panels.append(binance.abs().groupby(binance.index.normalize()).sum(min_count=1))
    for path in (bybit_dir, bitget_dir):
        loaded = _load_generic_funding_dir(path)
        if not loaded:
            continue
        normal = _daily_funding_panel(loaded)
        adverse = _daily_funding_panel(loaded, absolute=True)
        panels.append(normal)
        absolute_panels.append(adverse)

    columns = sorted(coin_set, key=str.casefold)
    if not panels:
        empty = pd.DataFrame(index=index, columns=columns, dtype=float)
        return empty, empty.copy()
    normal = pd.concat(panels).groupby(level=0).min(min_count=1)
    adverse = pd.concat(absolute_panels).groupby(level=0).max(min_count=1)
    return (
        normal.reindex(index=index, columns=columns),
        adverse.reindex(index=index, columns=columns),
    )


def executable_short_availability(
    funding_rates: pd.DataFrame,
    *,
    lookback_days: int = FUNDING_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Mark an alt executable when funding was observed in the recent lookback."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    available = funding_rates.notna().astype(float).rolling(
        lookback_days,
        min_periods=1,
    ).max()
    return available.fillna(0.0).astype(bool)


def restrict_targets_to_executable_shorts(
    targets: pd.DataFrame,
    available: pd.DataFrame,
) -> pd.DataFrame:
    """Drop non-executable alt shorts and rebuild each event's dollar-neutral book."""
    if "bitcoin" not in targets.columns:
        raise ValueError("targets must contain bitcoin")
    restricted = pd.DataFrame(0.0, index=targets.index, columns=targets.columns, dtype=float)
    alt_columns = [column for column in targets.columns if column != "bitcoin"]
    availability = available.reindex(index=targets.index, columns=alt_columns).fillna(False).astype(bool)
    for date, row in targets.iterrows():
        bitcoin_weight = float(row.get("bitcoin", 0.0))
        shorts = row.loc[alt_columns].astype(float)
        short_assets = list(shorts.index[shorts < 0.0])
        if bitcoin_weight <= 0.0 or not short_assets:
            continue
        short_gross = float(-shorts.loc[short_assets].sum())
        eligible = [asset for asset in short_assets if bool(availability.loc[date, asset])]
        if not eligible or short_gross <= 0.0:
            continue
        restricted.loc[date, eligible] = -short_gross / float(len(eligible))
        restricted.loc[date, "bitcoin"] = bitcoin_weight
    return restricted


def _short_funding_return(
    weights: pd.DataFrame,
    normal_rates: pd.DataFrame,
    adverse_rates: pd.DataFrame,
    *,
    multiplier: int,
) -> pd.Series:
    """Return funding PnL for alt perp shorts; the BTC spot leg pays none."""
    shorts = weights.clip(upper=0.0)
    aligned_normal = normal_rates.reindex(index=weights.index, columns=weights.columns)
    if multiplier == 0:
        return -(shorts * aligned_normal.fillna(0.0)).sum(axis=1).astype(float)
    aligned_adverse = adverse_rates.reindex(index=weights.index, columns=weights.columns)
    return (-float(multiplier) * shorts.abs() * aligned_adverse.fillna(0.0)).sum(axis=1).astype(float)


def short_funding_coverage(weights: pd.DataFrame, funding_rates: pd.DataFrame) -> float:
    """Weighted short exposure with an observed funding rate."""
    shorts = weights.clip(upper=0.0).abs()
    aligned = funding_rates.reindex(index=weights.index, columns=weights.columns)
    denominator = float(shorts.to_numpy().sum())
    if denominator <= 0.0:
        return 1.0
    covered = float(shorts.where(aligned.notna(), 0.0).to_numpy().sum())
    return covered / denominator


def _event_audit(
    original: pd.DataFrame,
    restricted: pd.DataFrame,
    available: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    alt_columns = [column for column in original.columns if column != "bitcoin"]
    for date, row in original.iterrows():
        shorts = row.loc[alt_columns].astype(float)
        assets = list(shorts.index[shorts < 0.0])
        if not assets:
            continue
        eligible = [asset for asset in assets if bool(available.loc[date, asset])]
        rows.append(
            {
                "event_date": date,
                "original_short_legs": len(assets),
                "executable_short_legs": len(eligible),
                "dropped_short_legs": len(assets) - len(eligible),
                "dropped_assets": "|".join(sorted(set(assets) - set(eligible))),
                "rebuilt": bool(restricted.loc[date, alt_columns].abs().sum() > 0.0),
            }
        )
    return pd.DataFrame(rows)


def _report(
    summary: pd.DataFrame,
    baseline: dict[str, float],
    baseline_validation: dict[str, float],
    event_audit: pd.DataFrame,
    selected: float | None,
    *,
    coverage: float,
) -> str:
    dropped = event_audit.loc[event_audit["dropped_short_legs"] > 0, "dropped_assets"]
    dropped_assets = sorted({asset for value in dropped for asset in str(value).split("|") if asset})
    lines = [
        "# LS57 + churn overlay: alt perp shorts, BTC spot",
        "",
        f"- LS57 baseline: {baseline['multiple']:.4f}x / Sharpe {baseline['sharpe']:.4f} / MDD {baseline['max_drawdown']:.4%}",
        f"- LS57 validation: {baseline_validation['multiple']:.4f}x / Sharpe {baseline_validation['sharpe']:.4f}",
        f"- short funding coverage: {coverage:.4%}",
        "- normal funding: cross-venue minimum daily settlement sum; short alt legs only",
        "- adverse: cross-venue maximum daily absolute settlement sum, then multiplied",
        "- BTC long is spot and pays no perpetual funding",
        "- executable universe: funding observed within the prior 7 calendar days",
        "",
        "## Executable event audit",
        "",
        f"- events with a short leg: {len(event_audit)}",
        f"- events rebuilt with at least one executable leg: {int(event_audit['rebuilt'].sum())}",
        f"- original / executable short legs: {int(event_audit['original_short_legs'].sum())} / {int(event_audit['executable_short_legs'].sum())}",
        f"- dropped names: {', '.join(dropped_assets) if dropped_assets else 'none'}",
        "",
        "## Results",
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
                    "passes_return_risk",
                ]
            ].reset_index(drop=True)
        ),
        "",
        "## Decision",
        "",
    ]
    if selected is None:
        lines.append("No allocation passed the 20bps normal + 1x-adverse return/risk gate.")
    else:
        lines.append(
            f"Largest allocation passing 20bps normal + 1x adverse: **{selected:.0%} NAV**. "
            "This remains research-only and still requires Bitget mark/fill/funding validation."
        )
    tail = summary.loc[
        (summary["sleeve_cost_bps"] == 20.0)
        & (summary["allocation"] == (selected if selected is not None else max(ALLOCATIONS)))
    ]
    if not tail.empty:
        lines.extend(["", "### Tail scenarios for the selected allocation", ""])
        lines.append(dataframe_to_markdown(tail[
            ["funding_scenario", "full_multiple", "full_sharpe", "full_max_drawdown", "validation_multiple", "validation_sharpe"]
        ].reset_index(drop=True)))
    lines.extend(
        [
            "",
            "The 3x-adverse result is a tail stress, not a promotion threshold in this study; "
            "it remains a failure if it does not beat LS57 and blocks any live promotion.",
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
        parser.error("LS78 is frozen to 2022-01-01 -> 2026-09-20")

    lower = pd.Timestamp(args.start_date, tz="UTC")
    upper = pd.Timestamp(args.end_date, tz="UTC")

    _, market, _, raw_index = _load_market(
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

    raw_targets = pd.read_csv(LS74_DIR / "targets.csv", index_col=0)
    raw_targets.index = pd.DatetimeIndex(pd.to_datetime(raw_targets.index, utc=True)).sort_values()
    raw_targets.columns = raw_targets.columns.astype(str)
    raw_targets = raw_targets.reindex(index).fillna(0.0)
    target_columns = ["bitcoin", *[asset for asset in assets if asset in raw_targets.columns]]
    raw_targets = raw_targets.reindex(columns=target_columns, fill_value=0.0).sort_index()

    short_coins = [asset for asset in assets if asset != "bitcoin"]
    normal_rates, adverse_rates = build_cross_venue_funding_panels(
        coins=short_coins,
        index=index,
    )
    available = executable_short_availability(normal_rates)
    restricted_targets = restrict_targets_to_executable_shorts(raw_targets, available)
    event_audit = _event_audit(raw_targets, restricted_targets, available)

    results = {
        cost: backtest_continuation(
            index=index,
            returns=returns[["bitcoin", *assets]],
            targets=restricted_targets,
            horizon=28,
            cost_bps=cost,
            normalize_gross=True,
        )
        for cost in COST_FILES
    }
    result_20 = results[20.0]
    held = result_20.weights.reindex(index).fillna(0.0)
    short_coverage = short_funding_coverage(held, normal_rates)
    sleeve_gross = result_20.gross_exposure.reindex(index).fillna(0.0)
    funding_by_scenario = {
        scenario: _short_funding_return(
            held,
            normal_rates,
            adverse_rates,
            multiplier=multiplier,
        )
        for scenario, multiplier in FUNDING_MULTIPLIERS.items()
    }

    ls57_returns = load_return_series(LS57_DIR / "daily_returns.csv")
    ls57_returns = ls57_returns.loc[(ls57_returns.index >= lower) & (ls57_returns.index <= upper)]
    ls57_gross = load_target_gross(LS57_DIR / "target_gross.csv")
    ls57_gross = ls57_gross.loc[(ls57_gross.index >= lower) & (ls57_gross.index <= upper)]
    base_gross = ls57_gross.reindex(ls57_returns.index).ffill().fillna(0.0)
    baseline = _sample_metrics(ls57_returns, "full")
    baseline_validation = _sample_metrics(ls57_returns, "validation")

    rows: list[dict[str, Any]] = []
    for allocation in ALLOCATIONS:
        scale_frame = scale_sleeve_to_residual_gross(
            ls57_gross=base_gross,
            sleeve_gross=sleeve_gross,
            allocation=allocation,
        ).reindex(ls57_returns.index)
        scale_delta = scale_frame["sleeve_scale"].diff().abs().fillna(
            scale_frame["sleeve_scale"].abs()
        )
        for cost, filename in COST_FILES.items():
            # Recompute the executable variant at every cost rather than reusing
            # LS74 returns that still contain non-executable short names.
            standalone = results[cost]
            sleeve_path = standalone.daily_returns.reindex(ls57_returns.index).fillna(0.0)
            scale_cost = (
                scale_delta
                * sleeve_gross.shift(1).fillna(sleeve_gross)
                * float(cost)
                / 10_000.0
            )
            for scenario, funding in funding_by_scenario.items():
                funding_aligned = funding.reindex(ls57_returns.index).fillna(0.0)
                combined = (
                    ls57_returns
                    + scale_frame["sleeve_scale"] * (sleeve_path + funding_aligned)
                    - scale_cost
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
                    and short_coverage >= MIN_FUNDING_COVERAGE
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
                        "passes_return_risk": bool(passes),
                    }
                )

    summary = pd.DataFrame(rows)
    eligible = summary.loc[
        (summary["sleeve_cost_bps"] == 20.0)
        & summary["funding_scenario"].isin(["normal", "adverse_1x"])
        & summary["passes_return_risk"]
    ]
    selected = None
    if not eligible.empty:
        by_allocation = eligible.groupby("allocation")["funding_scenario"].nunique()
        passing_allocations = by_allocation.loc[by_allocation == 2]
        if not passing_allocations.empty:
            selected = float(passing_allocations.index.max())

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "stress_summary.csv",
        "events": output_dir / "executable_events.csv",
        "targets": output_dir / "restricted_targets.csv",
        "funding": output_dir / "sleeve_funding.csv",
        "daily_20": output_dir / "daily_returns_20bps.csv",
        "daily_50": output_dir / "daily_returns_50bps.csv",
        "daily_100": output_dir / "daily_returns_100bps.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    event_audit.to_csv(files["events"], index=False)
    restricted_targets.to_csv(files["targets"])
    pd.DataFrame(funding_by_scenario).to_csv(files["funding"])
    results[20.0].daily_returns.to_csv(files["daily_20"])
    results[50.0].daily_returns.to_csv(files["daily_50"])
    results[100.0].daily_returns.to_csv(files["daily_100"])
    files["report"].write_text(
        _report(
            summary,
            baseline,
            baseline_validation,
            event_audit,
            selected,
            coverage=short_coverage,
        ),
        encoding="utf-8",
    )
    manifest = {
        "candidate_id": "PR2026-11-LS78-LS57-CHURN-SPOT-BTC-SHORT-ALT",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "allocations": list(ALLOCATIONS),
        "costs_bps": list(COST_FILES),
        "funding_scenarios": list(FUNDING_MULTIPLIERS),
        "funding_lookback_days": FUNDING_LOOKBACK_DAYS,
        "funding_coverage": short_coverage,
        "selected_allocation": selected,
        "baseline": baseline,
        "baseline_validation": baseline_validation,
        "gross_cap": GROSS_CAP,
        "btc_leg": "spot",
        "alt_short_leg": "perpetual",
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_dir}; selected={selected}; coverage={short_coverage:.4f}")


if __name__ == "__main__":
    main()
