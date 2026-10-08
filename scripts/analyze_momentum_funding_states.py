"""Do perpetual funding-rate states mark the frozen spec's bad months?

Section 00.15 screened the daily volume side of the panel and Section 00.16 the
hourly candles; both were rejected, and both are *spot* data.  The one
information source the project had never touched is derivatives positioning:
how much leverage longs are paying to stay long.  ``data.binance.vision``
publishes the complete funding history of every Binance USDT perpetual as one
monthly archive per symbol, which ``scripts/download_funding_rates.py`` caches
under ``data/raw/binance_funding``; 52 of the 57 coins in the point-in-time
universe have it (the Gate-only pairs and `bitget-token` do not).

The mechanism is documented externally.  "Crypto Carry" (*Management Science*,
2026) shows the futures-spot carry "can reach exceptionally high levels,
sometimes exceeding 40% per annum" and traces it to "demand from smaller,
trend-chasing investors seeking leveraged exposure" plus limited arbitrage
capital, so carry is a direct read on crowded leverage.  A 2026 panel study of
Binance perpetuals finds that "cumulative funding rates" and open-interest
changes "significantly predict extreme price crashes".  This tool tests whether
that is usable as an overlay on the frozen specification.

It is hypothesis generation: no rule change, no new trial.

States (all over point-in-time Top20 members with funding data, minimum five a
day, all read at the close before the month they are matched with):

``funding_level``
    Seven-day mean of the cross-sectional mean daily funding paid by longs, in
    basis points per day (a day usually carries three 8-hour payments).
``funding_pct``
    That series ranked inside its own trailing 252-day window: the crowdedness
    of leverage relative to its recent history.
``funding_positive_share``
    Seven-day mean share of members whose daily funding is positive.
``funding_disp_ratio``
    Cross-sectional dispersion of member funding over its own trailing median:
    disagreement about which coins deserve leverage.

Pre-declared bar
----------------
This is the third screen over the same 2022-01-01..2026-09-21 sample, so the
information bar is the family-wise one for the twenty candidate states of
Sections 00.15, 00.16 and this one: ``0.05 / 20`` two-sided at n = 57 is a
t-statistic of about 3.0, i.e. ``|Spearman(state, H5 - BTC)| >= 0.38``.  The
other two conditions are unchanged: tercile means of ``H5 - BTC`` monotone, and
``|crash_minus_rest / rest_std| >= 0.50``.

A state that clears the bar would still have to be pre-registered as H6 with
its own kill criterion and confirmed out of sample before it could change a
rule.  Note also a deployment limitation recorded in the report: Binance
publishes funding archives monthly, not daily, and ``fapi.binance.com`` is not
reachable from this network, so a funding overlay could be backtested here but
not yet driven live.

Usage::

    .venv/bin/python scripts/analyze_momentum_funding_states.py \
        --output-dir reports/phase_momentum_funding_states
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import btc_above_moving_average  # noqa: E402
from atlas20.strategies.phase_momentum import top20_breadth, top20_dispersion  # noqa: E402

from scripts.analyze_momentum_flow_states import (  # noqa: E402
    EXISTING_STATE_COLUMNS,
    _member_snapshots,
    _ratio_to_median,
    _verdicts,
    information_table,
    redundancy_table,
    separation_table,
    tercile_table,
)
from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402

DEFAULT_TRIAL = "PR2026-10-H5"
DEFAULT_RETURNS = Path("reports/phase_momentum_hypotheses_2026_10/returns_20bps.csv")
DEFAULT_COLUMN = "PR2026-10-H5|h3_day_close|20"
DEFAULT_CRASH_THRESHOLD = -0.08
IC_BAR = 0.38
SEPARATION_BAR = 0.50
MIN_MEMBERS = 5
RATIO_LOOKBACK = 252
RATIO_MIN_PERIODS = 126
BPS = 1e4

FUNDING_STATE_COLUMNS = (
    "funding_level",
    "funding_pct",
    "funding_positive_share",
    "funding_disp_ratio",
)


def load_funding(directory: Path) -> dict[str, pd.Series]:
    """Daily funding paid by longs, per coin, summed over the day's payments."""
    funding: dict[str, pd.Series] = {}
    for path in sorted(directory.glob("*.csv")):
        frame = pd.read_csv(path)
        if not {"calc_time", "last_funding_rate"} <= set(frame.columns):
            continue
        stamps = pd.to_datetime(pd.to_numeric(frame["calc_time"], errors="coerce"), unit="ms", utc=True)
        rates = pd.to_numeric(frame["last_funding_rate"], errors="coerce")
        daily = (
            pd.Series(rates.to_numpy(), index=stamps)
            .dropna()
            .resample("D")
            .sum(min_count=1)
        )
        daily.index = pd.DatetimeIndex(daily.index).tz_localize(None)
        funding[path.stem] = daily
    return funding


def _rolling_percentile(series: pd.Series) -> pd.Series:
    """Rank of the latest reading inside its own trailing window, in [0, 1]."""

    def rank(window: np.ndarray) -> float:
        last = window[-1]
        if not np.isfinite(last):
            return np.nan
        earlier = window[:-1]
        earlier = earlier[np.isfinite(earlier)]
        return float((earlier < last).mean()) if earlier.size else np.nan

    return series.rolling(RATIO_LOOKBACK, min_periods=RATIO_MIN_PERIODS).apply(rank, raw=True)


def funding_state_frame(
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    funding: dict[str, pd.Series],
) -> tuple[pd.DataFrame, pd.Series]:
    """Daily funding states over point-in-time members, plus usable-member count."""
    wide = pd.DataFrame(funding).sort_index()
    wide = wide.reindex(wide.index.union(index))
    snapshots = _member_snapshots(universe, index)

    level: dict[pd.Timestamp, float] = {}
    positive: dict[pd.Timestamp, float] = {}
    dispersion: dict[pd.Timestamp, float] = {}
    members_used: dict[pd.Timestamp, float] = {}
    for date in index:
        members = [coin for coin in snapshots[pd.Timestamp(date)] if coin in wide.columns]
        if not members or date not in wide.index:
            level[date] = positive[date] = dispersion[date] = float("nan")
            members_used[date] = 0.0
            continue
        row = pd.to_numeric(wide.loc[date, members], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        members_used[date] = float(len(row))
        if len(row) < MIN_MEMBERS:
            level[date] = positive[date] = dispersion[date] = float("nan")
            continue
        level[date] = float(row.mean()) * BPS
        positive[date] = float((row > 0.0).mean())
        dispersion[date] = float(row.std(ddof=1)) * BPS

    level_series = pd.Series(level, dtype=float).sort_index()
    smooth_level = level_series.rolling(7, min_periods=5).mean()
    frame = pd.DataFrame(
        {
            "funding_level": smooth_level,
            "funding_pct": _rolling_percentile(smooth_level),
            "funding_positive_share": pd.Series(positive, dtype=float)
            .sort_index()
            .rolling(7, min_periods=5)
            .mean(),
            "funding_disp_ratio": _ratio_to_median(
                pd.Series(dispersion, dtype=float).sort_index().rolling(7, min_periods=5).mean()
            ),
        }
    ).sort_index()
    return frame, pd.Series(members_used, dtype=float).sort_index()


def monthly_frame(
    port: pd.Series, btc: pd.Series, funding: pd.DataFrame, legacy: pd.DataFrame
) -> pd.DataFrame:
    """Calendar-month returns next to the state readings known before the month."""
    month_end = port.resample("ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    btc_month = btc.resample("ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    frame = pd.DataFrame({"ret": month_end, "btc": btc_month})
    frame["excess"] = frame["ret"] - frame["btc"]
    for column in FUNDING_STATE_COLUMNS:
        frame[column] = funding[column].shift(1).resample("ME").first()
    for column in ("gate_open", "breadth", "disp_ratio", "mkt_vol", "gross"):
        frame[f"{column}_before"] = legacy[column].shift(1).resample("ME").first()
    frame["own63_before"] = legacy["own63_before"].shift(1).resample("ME").first()
    return frame


def coverage_table(
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    funding: dict[str, pd.Series],
    members_used: pd.Series,
) -> pd.DataFrame:
    snapshots = _member_snapshots(universe, index)
    members = sorted({coin for coins in snapshots.values() for coin in coins})
    total = sum(len(snapshots[pd.Timestamp(date)]) for date in index)
    observed = int(members_used.reindex(index).fillna(0.0).sum())
    without = [coin for coin in members if coin not in funding]
    return pd.DataFrame(
        {
            "metric": [
                "coins with funding history",
                "distinct point-in-time members",
                "members without funding history",
                "member-days with funding",
                "member-days total",
                "member-day coverage",
                "days below the five-member floor",
            ],
            "value": [
                float(len(funding)),
                float(len(members)),
                float(len(without)),
                float(observed),
                float(total),
                float(observed / total) if total else float("nan"),
                float((members_used.reindex(index) < MIN_MEMBERS).sum()),
            ],
        }
    )


def _report(
    monthly: pd.DataFrame,
    separation: pd.DataFrame,
    information: pd.DataFrame,
    terciles: pd.DataFrame,
    redundancy: pd.DataFrame,
    verdicts: pd.DataFrame,
    coverage: pd.DataFrame,
    *,
    trial_id: str,
    threshold: float,
) -> str:
    promoted = verdicts.index[verdicts["promote_to_h6"]].tolist()
    worst = monthly.sort_values("ret").head(12)
    lines = [
        f"# Do perpetual funding-rate states mark {trial_id}'s bad months?",
        "",
        "Hypothesis generation only: no rule was changed, no trial was registered.",
        f"Months: {len(monthly)}; crash months (return <= {threshold:.0%}): "
        f"{int((monthly['ret'] <= threshold).sum())}.",
        "",
        "Funding is the only derivatives-positioning information the project holds; it cannot",
        "be built from the spot price, volume and market-cap panel. States are read at the last",
        "close before each month and compared with that month's net 20 bps return and its BTC",
        "return, because the failure mode is market up and strategy down.",
        "",
        "## Pre-declared bar (family-wise over all three screens)",
        "",
        f"`|Spearman(state, excess)| >= {IC_BAR:.2f}` - the 5% two-sided level divided by the",
        "twenty candidate states of Sections 00.15, 00.16 and this one - plus monotone terciles",
        f"and `|diff_over_rest_std| >= {SEPARATION_BAR:.2f}`.",
        "",
        "## Point-in-time Top20 coverage of the funding feed",
        "",
        dataframe_to_markdown(coverage),
        "",
        "## Crash versus rest",
        "",
        dataframe_to_markdown(separation),
        "",
        "## Rank information against next-month excess return",
        "",
        dataframe_to_markdown(information),
        "",
        "## Excess return by state tercile (1 = lowest state, 3 = highest)",
        "",
        dataframe_to_markdown(terciles) if not terciles.empty else "_no state had enough usable months_",
        "",
        "## Correlation with the states H5 already carries",
        "",
        dataframe_to_markdown(redundancy),
        "",
        "## Verdicts",
        "",
        dataframe_to_markdown(verdicts),
        "",
        (
            "States clearing the pre-declared bar: " + ", ".join(promoted) + "."
            if promoted
            else "No state cleared the pre-declared bar."
        ),
        "",
        "## Worst months and the state they started in",
        "",
        dataframe_to_markdown(worst),
        "",
        "## Reading",
        "",
        "Any separation here is in-sample. A state that clears the bar would still have to be",
        "pre-registered as H6 with its own kill criterion and confirmed out of sample before it",
        "could change a rule. Deployment note: Binance publishes funding archives monthly rather",
        "than daily and fapi.binance.com is unreachable from this network, so even a promoted",
        "state could be backtested here but not driven live without another data route.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", default=DEFAULT_TRIAL)
    parser.add_argument("--returns-file", type=Path, default=DEFAULT_RETURNS)
    parser.add_argument("--column", default=DEFAULT_COLUMN)
    parser.add_argument("--funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--crash-threshold", type=float, default=DEFAULT_CRASH_THRESHOLD)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_funding_states"))
    args = parser.parse_args()
    configure_logging("ERROR")

    _config, market, universe, index = _load_market(
        args.config, start_date=args.start_date, end_date=args.end_date
    )
    trial = trial_by_id(args.trial_id)
    built = build_trial(trial, market, universe, index)
    result = _production_result(_config, market, built, index, cost_bps=args.cost_bps)
    weights = result.weights

    saved = pd.read_csv(args.returns_file, parse_dates=["date"]).set_index("date")
    if args.column not in saved.columns:
        raise ValueError(f"column {args.column!r} is not in {args.returns_file}")
    port = pd.to_numeric(saved[args.column], errors="coerce").reindex(index).fillna(0.0)
    btc = market.returns["bitcoin"].reindex(index).fillna(0.0)

    funding = load_funding(args.funding_dir)
    funding_states, members_used = funding_state_frame(universe, index, funding)
    coverage = coverage_table(universe, index, funding, members_used)

    dispersion = top20_dispersion(market, universe, index, window=21)
    legacy = pd.DataFrame(
        {
            "gate_open": btc_above_moving_average(market.price, 100, 2)
            .reindex(index)
            .fillna(False)
            .astype(float),
            "breadth": top20_breadth(market, universe, index, ma_window=50),
            "disp_ratio": dispersion / dispersion.rolling(252, min_periods=126).quantile(0.75),
            "mkt_vol": market.returns.mean(axis=1).rolling(60).std() * np.sqrt(365.0),
            "own63_before": port.rolling(63).apply(lambda x: float(np.prod(1.0 + x) - 1.0), raw=True),
            "gross": weights.sum(axis=1),
        }
    ).loc[index]

    monthly = monthly_frame(port, btc, funding_states, legacy).dropna(subset=["ret", "btc"])
    separation = separation_table(monthly, args.crash_threshold, FUNDING_STATE_COLUMNS)
    information = information_table(monthly, FUNDING_STATE_COLUMNS)
    terciles = tercile_table(monthly, FUNDING_STATE_COLUMNS)
    redundancy = redundancy_table(monthly, FUNDING_STATE_COLUMNS, EXISTING_STATE_COLUMNS)
    verdicts = _verdicts(
        separation,
        information,
        terciles,
        FUNDING_STATE_COLUMNS,
        ic_bar=IC_BAR,
        separation_bar=SEPARATION_BAR,
    )

    output_dir = ensure_dir(args.output_dir)
    monthly.to_csv(output_dir / "monthly_state.csv", index_label="month")
    funding_states.to_csv(output_dir / "daily_funding_state.csv", index_label="date")
    coverage.to_csv(output_dir / "funding_coverage.csv", index=False)
    separation.to_csv(output_dir / "state_separation.csv", index_label="state_variable")
    information.to_csv(output_dir / "state_information.csv", index_label="state_variable")
    terciles.to_csv(output_dir / "state_terciles.csv", index=False)
    redundancy.to_csv(output_dir / "state_redundancy.csv", index_label="state_variable")
    verdicts.to_csv(output_dir / "state_verdicts.csv", index_label="state_variable")
    (output_dir / "report.md").write_text(
        _report(
            monthly,
            separation,
            information,
            terciles,
            redundancy,
            verdicts,
            coverage,
            trial_id=args.trial_id,
            threshold=args.crash_threshold,
        ),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "script": "scripts/analyze_momentum_funding_states.py",
                "trial_id": args.trial_id,
                "returns_file": str(args.returns_file),
                "column": args.column,
                "funding_dir": str(args.funding_dir),
                "start_date": args.start_date,
                "end_date": args.end_date,
                "cost_bps": args.cost_bps,
                "crash_threshold": args.crash_threshold,
                "ic_bar": IC_BAR,
                "separation_bar": SEPARATION_BAR,
                "state_columns": list(FUNDING_STATE_COLUMNS),
                "monthly_observations": int(len(monthly)),
                "crash_months": int((monthly["ret"] <= args.crash_threshold).sum()),
                "promoted": verdicts.index[verdicts["promote_to_h6"]].tolist(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(verdicts.round(3).to_string())
    print(
        f"crash months: {int((monthly['ret'] <= args.crash_threshold).sum())} of {len(monthly)}; "
        f"promoted: {verdicts.index[verdicts['promote_to_h6']].tolist()}"
    )
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
