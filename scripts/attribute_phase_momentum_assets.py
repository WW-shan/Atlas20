"""Per-coin attribution for the frozen phase-momentum champion.

AGENTS.md will not call a strategy robust when its result depends on one asset
or a small number of trades. The project already reports leave-one-signal-out,
leave-one-phase-out, best-year-removed and the entrant/incumbent split; this adds
the missing per-coin view: how much of the champion's return came from each coin,
using the same accounting as the entrant attribution (the engine's actual book,
fill-split on target days, classed at the signal date).

It is an attribution tool, not a search: the specification, universe, costs and
fill rules are the frozen champion's, and nothing is selected here.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.backtest.intraday import load_hourly_bars, pre_fill_returns  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from scripts.run_phase_momentum import _production_result  # noqa: E402
from scripts.run_phase_momentum_hypotheses import (  # noqa: E402
    BASELINE_ID,
    FILL_HOURS,
    HOUR_FILLS,
    MAIN_WINDOW,
    _load_market,
    build_trial,
    trial_by_id,
)


def coin_contribution_matrix(
    result: object,
    asset_returns: pd.DataFrame,
    *,
    fill_split: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Sum of daily per-coin contributions from the engine's book.

    Mirrors ``run_phase_momentum_hypotheses.entrant_attribution`` exactly, but
    keeps the coin axis instead of collapsing it into entrant classes: on a day
    that follows a target the overnight book earns the move to the fill and the
    new target the rest of the day; otherwise the drifted book earns the day's
    return.
    """
    dates = pd.DatetimeIndex(asset_returns.index)
    columns = asset_returns.columns
    returns = np.nan_to_num(asset_returns.reindex(columns=columns).to_numpy(dtype=float), nan=0.0)
    split = None
    if fill_split is not None:
        split = fill_split.reindex(index=dates, columns=columns).to_numpy(dtype=float)
        split = np.where(np.isfinite(split), split, returns)
    end_weights = result.weights.reindex(index=dates, columns=columns).fillna(0.0).to_numpy(dtype=float)
    targets = result.rebalance_targets.reindex(columns=columns).fillna(0.0)
    totals = np.zeros(len(columns), dtype=float)
    per_day = np.zeros((len(dates), len(columns)), dtype=float)
    previous = np.zeros(len(columns), dtype=float)
    for position, date in enumerate(dates):
        if position == 0:
            previous = end_weights[position]
            continue
        signal_date = dates[position - 1]
        day = returns[position]
        if signal_date in targets.index:
            new = targets.loc[signal_date].to_numpy(dtype=float)
            if split is not None:
                part = split[position]
                denominator = 1.0 + part
                safe = np.where(denominator > 0.0, denominator, 1.0)
                remaining = np.where(denominator > 0.0, (1.0 + day) / safe - 1.0, day)
                contribution = previous * part + new * remaining
            else:
                contribution = new * day
        else:
            contribution = previous * day
        totals += contribution
        per_day[position] = contribution
        previous = end_weights[position]
    frame = pd.DataFrame(per_day, index=dates, columns=columns)
    frame.attrs["totals"] = pd.Series(totals, index=columns, name="contribution")
    return frame


def coin_contributions(
    result: object,
    asset_returns: pd.DataFrame,
    *,
    fill_split: pd.DataFrame | None = None,
) -> pd.Series:
    """Per-coin totals, the column sum of :func:`coin_contribution_matrix`."""
    return coin_contribution_matrix(result, asset_returns, fill_split=fill_split).attrs["totals"]


def counterfactual_multiple(
    portfolio_returns: pd.Series,
    contribution_matrix: pd.DataFrame,
    coins: tuple[str, ...],
) -> float:
    """Terminal multiple after removing the named coins' daily contributions.

    The engine's daily contribution of every coin sums to the portfolio's daily
    return, so subtracting one coin's contribution is the counterfactual "that
    coin earned nothing, everything else unchanged". It is an attribution
    counterfactual, not a re-run: the positions are the champion's.
    """
    removed = contribution_matrix.reindex(columns=list(coins)).fillna(0.0).sum(axis=1)
    adjusted = portfolio_returns.reindex(contribution_matrix.index).fillna(0.0) - removed.reindex(
        contribution_matrix.index
    ).fillna(0.0)
    return float((1.0 + adjusted).prod())


def summarise(contributions: pd.Series) -> pd.DataFrame:
    """Contribution, share of the total and cumulative share, largest first."""
    gross = float(contributions.sum())
    frame = contributions.rename("contribution").to_frame()
    frame["share"] = frame["contribution"] / gross if gross else np.nan
    frame = frame.sort_values("contribution", ascending=False)
    frame["cumulative_share"] = frame["share"].cumsum()
    return frame


def _terminal_multiple(series: pd.Series) -> float:
    return float((1.0 + series.fillna(0.0)).prod())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--hourly-dir", default="data/raw/binance_1h")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument(
        "--trial-id",
        default=BASELINE_ID,
        help="registered trial to attribute (default: the frozen champion)",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/phase_momentum_asset_attribution",
        help="directory for the per-coin CSVs and the summary",
    )
    args = parser.parse_args()

    config, market, universe, index = _load_market(
        args.config, start_date=MAIN_WINDOW[0], end_date=MAIN_WINDOW[1]
    )
    configure_logging(config.logging.level)

    hourly = load_hourly_bars(Path(args.hourly_dir))
    daily = market.returns.loc[index]
    closes = market.raw_price.reindex(index=index, columns=daily.columns)
    trial = trial_by_id(args.trial_id)
    built = build_trial(trial, market, universe, index)

    output_dir = ensure_dir(Path(args.output_dir))
    summaries: dict[str, pd.DataFrame] = {}
    multiples: dict[str, float] = {}
    counterfactuals: dict[str, dict[str, float]] = {}
    for fill, policy in HOUR_FILLS.items():
        pre_fill = pre_fill_returns(
            daily, hourly, fill_hours=FILL_HOURS, missing_fill=policy, reference_close=closes
        )
        fill_split = pre_fill.where(pre_fill.notna(), daily)
        result = _production_result(
            config, market, built, index, cost_bps=args.cost_bps, execution_lag_days=0, pre_fill=pre_fill
        )
        matrix = coin_contribution_matrix(result, daily, fill_split=fill_split)
        contributions = matrix.attrs["totals"]
        frame = summarise(contributions)
        frame.to_csv(output_dir / f"per_coin_{fill}.csv")
        summaries[fill] = frame
        multiples[fill] = _terminal_multiple(result.daily_returns)
        counterfactuals[fill] = {
            "drop_top1": counterfactual_multiple(result.daily_returns, matrix, (frame.index[0],)),
            "drop_top3": counterfactual_multiple(result.daily_returns, matrix, tuple(frame.index[:3])),
            "drop_top5": counterfactual_multiple(result.daily_returns, matrix, tuple(frame.index[:5])),
        }
        print(f"{fill}: terminal {multiples[fill]:.4f}x, gross contribution {contributions.sum():.4f}")

    worse = min(multiples, key=lambda key: multiples[key])
    frame = summaries[worse]
    cf = counterfactuals[worse]
    lines = [
        "# Phase-momentum champion: per-coin attribution",
        "",
        f"- Spec: `{args.trial_id}`, costs {args.cost_bps:g} bps, "
        f"fills +{FILL_HOURS}h under both missing-candle policies.",
        f"- Worse policy: `{worse}` ({multiples[worse]:.4f}x). Contribution is the sum of daily "
        "weight x return over the engine's book; shares sum to 100%.",
        "",
        "| rank | coin | contribution | share | cumulative share |",
        "| ---: | --- | ---: | ---: | ---: |",
    ]
    for rank, (coin, row) in enumerate(frame.iterrows(), start=1):
        lines.append(
            f"| {rank} | {coin} | {row['contribution']:.4f} | {row['share']:.2%} | "
            f"{row['cumulative_share']:.2%} |"
        )
    top = frame["contribution"]
    hhi = float((frame["share"] ** 2).sum())
    lines += [
        "",
        f"- Coins held at all: {int((top != 0).sum())}.",
        f"- Top-1 coin share: {frame['share'].iloc[0]:.2%}; "
        f"top-3: {frame['share'].iloc[:3].sum():.2%}; top-5: {frame['share'].iloc[:5].sum():.2%}.",
        f"- Contribution HHI (sum of squared shares): {hhi:.4f}.",
        "",
        "Attribution counterfactuals (remove that coin's daily contribution, keep every position):",
        "",
        f"- Full champion: **{multiples[worse]:.4f}x**.",
        f"- Without the top-1 contributor ({frame.index[0]}): **{cf['drop_top1']:.4f}x**.",
        f"- Without the top-3 contributors: **{cf['drop_top3']:.4f}x**.",
        f"- Without the top-5 contributors: **{cf['drop_top5']:.4f}x**.",
    ]
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {output_dir}")
    print("\n".join(lines[4:15]))


if __name__ == "__main__":
    main()
