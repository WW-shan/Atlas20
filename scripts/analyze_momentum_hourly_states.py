"""Do intraday (hourly) states mark the frozen spec's bad months?

Section 00.15 screened the daily volume / turnover side of the panel and
rejected every state: the daily panel carries no state that both separates the
frozen spec's crash months and ranks its next-month excess return.  This tool
screens the last untapped information source already inside the repository: the
Binance hourly candles (``data/raw/binance_1h``, 56 pairs, 2021-12-25 onwards,
42 of the 43 point-in-time Top20 members that traded over the evaluated window).

None of these states can be built from the daily close, dollar volume and
market cap the strategy already sees, so the screen is not a re-cut of the same
information.  It is still hypothesis generation: no rule changes, no new trial.

Candidate states (all read at the close of the day before the month they are
matched with, all over point-in-time Top20 members only, minimum five usable
members on a day):

``rv_ratio``
    Seven-day mean of the Top20 mean 24-hour realized variance (sum of squared
    hourly log returns), over its own trailing 252-day median.  Andersen,
    Bollerslev, Diebold and Labys (2003) show intraday realized variance is a
    far less noisy volatility estimate than daily squared returns.
``range_ratio``
    Seven-day mean of the Top20 mean daily (high - low) / close, over its own
    trailing median: a range-based volatility estimate that needs no return
    series (Parkinson, 1980).
``rvs_down_share``
    Top20 mean share of 24-hour realized variance contributed by negative
    hours: "bad" volatility, which is priced separately from total volatility
    (Barndorff-Nielsen, Kinnebrock and Shephard, 2010).
``hour_share_ratio``
    Top20 mean of the largest single hour's share of the day's dollar volume,
    over its own trailing median.  Concentrated hourly volume is a
    manipulation / wash-trading signature (Cong, Li, Tang and Yang, 2023,
    who find fabricated volume averaged over 70% of reported volume on
    unregulated exchanges).
``venue_share_ratio``
    Binance dollar volume over the members' total CMC dollar volume (seven-day
    mean), over its own trailing median: how much of the reported market is
    verifiable on one regulated-by-reputation venue.
``hourly_autocorr``
    Cross-sectional median of each member's 30-day lag-one autocorrelation of
    hourly returns: whether the current regime is intraday-trending or
    intraday-reverting.
``night_minus_day``
    Trailing seven-day sum of the equal-weight Top20 portfolio's 00:00-08:00
    UTC return minus its 08:00-24:00 UTC return.  Hansen, Kim and Kimbrough
    (2024) document systematic hour-of-day patterns in crypto volatility and
    volume.

Pre-declared bar
----------------
This is the *second* screen over the same 2022-01-01..2026-09-21 sample, so the
bar is the family-wise one for eighteen candidate states, not the unadjusted
0.25 Section 00.15 used for the first nine:

1. ``|Spearman(state, H5 - BTC) | >= 0.38``  (the two-sided 5% level divided by
   eighteen comparisons at n = 57);
2. tercile means of ``H5 - BTC`` monotone;
3. ``|crash_minus_rest / rest_std| >= 0.50``.

Anything that fails is a rejected hypothesis.  A state that clears it would
still have to be pre-registered as H6 with its own kill criterion and confirmed
out of sample before it could change a rule.

Usage::

    .venv/bin/python scripts/analyze_momentum_hourly_states.py \
        --output-dir reports/phase_momentum_hourly_states
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

from atlas20.backtest.intraday import load_hourly_bars  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import btc_above_moving_average  # noqa: E402
from atlas20.strategies.phase_momentum import top20_breadth, top20_dispersion  # noqa: E402

from scripts.analyze_momentum_flow_states import (  # noqa: E402
    EXISTING_STATE_COLUMNS,
    _member_snapshots,
    _ratio_to_median,
    _spearman,
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
NIGHT_HOURS = 8
LOOKBACK_DAYS = 400

HOURLY_STATE_COLUMNS = (
    "rv_ratio",
    "range_ratio",
    "rvs_down_share",
    "hour_share_ratio",
    "venue_share_ratio",
    "hourly_autocorr",
    "night_minus_day",
)
DAILY_AGGREGATES = (
    "realized_variance",
    "down_share",
    "range",
    "hour_share",
    "quote_volume",
    "night_minus_day",
)


def _hourly_daily_frame(bars: pd.DataFrame) -> pd.DataFrame:
    """Per-UTC-day aggregates of one coin's hourly candles."""
    frame = bars.copy()
    frame["hour_return"] = np.log(frame["close"]).diff()
    frame["day"] = frame["open_time"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
    frame["hour"] = frame["open_time"].dt.tz_convert("UTC").dt.hour
    frame["squared"] = frame["hour_return"] ** 2
    frame["negative_squared"] = frame["squared"].where(frame["hour_return"] < 0.0, 0.0)
    frame["is_night"] = frame["hour"] < NIGHT_HOURS

    grouped = frame.groupby("day")
    daily = pd.DataFrame(
        {
            "realized_variance": grouped["squared"].sum(min_count=1),
            "negative_squared": grouped["negative_squared"].sum(min_count=1),
            "range": (grouped["high"].max() - grouped["low"].min()) / grouped["close"].last(),
            "quote_volume": grouped["quote_volume"].sum(min_count=1),
            "max_hour_volume": grouped["quote_volume"].max(),
            "hours": grouped["hour_return"].count(),
        }
    )
    daily["hour_share"] = daily["max_hour_volume"] / daily["quote_volume"].where(
        daily["quote_volume"] > 0.0
    )
    daily["down_share"] = daily["negative_squared"] / daily["realized_variance"].where(
        daily["realized_variance"] > 0.0
    )
    night = frame[frame["is_night"]].groupby("day")["hour_return"].sum(min_count=1)
    day = frame[~frame["is_night"]].groupby("day")["hour_return"].sum(min_count=1)
    daily["night_minus_day"] = night - day
    # A day built from fewer than 20 hourly bars is incomplete (Binance has had
    # outages and a handful of pairs start or stop mid-day); drop it so the
    # state is never read from a partial day.
    daily = daily[daily["hours"] >= 20]
    autocorr = frame["hour_return"].rolling(24 * 30, min_periods=24 * 20).corr(
        frame["hour_return"].shift(1)
    )
    daily["hourly_autocorr"] = autocorr.groupby(frame["day"]).last().reindex(daily.index)
    return daily


def _wide(frames: dict[str, pd.DataFrame], column: str) -> pd.DataFrame:
    return pd.DataFrame({coin: frame[column] for coin, frame in frames.items()}).sort_index()


def _cross_section(
    wide: pd.DataFrame,
    snapshots: dict[pd.Timestamp, list[str]],
    index: pd.DatetimeIndex,
    *,
    how: str = "mean",
) -> pd.Series:
    values: dict[pd.Timestamp, float] = {}
    for date in index:
        members = snapshots[pd.Timestamp(date)]
        if not members:
            values[pd.Timestamp(date)] = float("nan")
            continue
        available = [coin for coin in members if coin in wide.columns]
        row = pd.to_numeric(wide.loc[date, available], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        ).dropna() if available and date in wide.index else pd.Series(dtype=float)
        if len(row) < MIN_MEMBERS:
            values[pd.Timestamp(date)] = float("nan")
        elif how == "median":
            values[pd.Timestamp(date)] = float(row.median())
        else:
            values[pd.Timestamp(date)] = float(row.mean())
    return pd.Series(values, dtype=float).sort_index()


def hourly_state_frame(
    market,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    hourly: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Daily intraday state variables over point-in-time Top20 members."""
    frames = {coin: _hourly_daily_frame(bars) for coin, bars in hourly.items()}
    realized_variance = _wide(frames, "realized_variance")
    down_share = _wide(frames, "down_share")
    range_ = _wide(frames, "range")
    hour_share = _wide(frames, "hour_share")
    quote_volume = _wide(frames, "quote_volume")
    night = _wide(frames, "night_minus_day")
    autocorr = _wide(frames, "hourly_autocorr")

    snapshots = _member_snapshots(universe, index)
    xs_rv = _cross_section(realized_variance, snapshots, index)
    xs_down = _cross_section(down_share, snapshots, index)
    xs_range = _cross_section(range_, snapshots, index)
    xs_hour = _cross_section(hour_share, snapshots, index)
    xs_autocorr = _cross_section(autocorr, snapshots, index, how="median")
    xs_night = _cross_section(night, snapshots, index)
    venue_share = pd.Series(np.nan, index=index, dtype=float)
    for date in index:
        members = [coin for coin in snapshots[pd.Timestamp(date)] if coin in quote_volume.columns]
        if not members or date not in quote_volume.index:
            continue
        binance = pd.to_numeric(quote_volume.loc[date, members], errors="coerce").sum(min_count=1)
        reported = pd.to_numeric(
            market.volume.loc[date, members], errors="coerce"
        ).sum(min_count=1) if date in market.volume.index else float("nan")
        if pd.notna(binance) and pd.notna(reported) and reported > 0.0:
            venue_share[date] = float(binance / reported)

    frame = pd.DataFrame(
        {
            "rv_ratio": _ratio_to_median(xs_rv.rolling(7, min_periods=5).mean()),
            "range_ratio": _ratio_to_median(xs_range.rolling(7, min_periods=5).mean()),
            "rvs_down_share": xs_down.rolling(7, min_periods=5).mean(),
            "hour_share_ratio": _ratio_to_median(xs_hour.rolling(7, min_periods=5).mean()),
            "venue_share_ratio": _ratio_to_median(venue_share.rolling(7, min_periods=5).mean()),
            "hourly_autocorr": xs_autocorr,
            "night_minus_day": xs_night.rolling(7, min_periods=5).sum(),
        }
    ).sort_index()
    return frame


def monthly_frame(port: pd.Series, btc: pd.Series, hourly: pd.DataFrame, legacy: pd.DataFrame) -> pd.DataFrame:
    """Calendar-month returns next to the state readings known before the month."""
    month_end = port.resample("ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    btc_month = btc.resample("ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    frame = pd.DataFrame({"ret": month_end, "btc": btc_month})
    frame["excess"] = frame["ret"] - frame["btc"]
    for column in HOURLY_STATE_COLUMNS:
        frame[column] = hourly[column].shift(1).resample("ME").first()
    for column in ("gate_open", "breadth", "disp_ratio", "mkt_vol", "gross"):
        frame[f"{column}_before"] = legacy[column].shift(1).resample("ME").first()
    frame["own63_before"] = legacy["own63_before"].shift(1).resample("ME").first()
    return frame


def _report(
    monthly: pd.DataFrame,
    separation: pd.DataFrame,
    information: pd.DataFrame,
    terciles: pd.DataFrame,
    redundancy: pd.DataFrame,
    verdicts: pd.DataFrame,
    *,
    trial_id: str,
    threshold: float,
    coverage: pd.DataFrame,
) -> str:
    promoted = verdicts.index[verdicts["promote_to_h6"]].tolist()
    worst = monthly.sort_values("ret").head(12)
    lines = [
        f"# Do intraday (hourly) states mark {trial_id}'s bad months?",
        "",
        "Hypothesis generation only: no rule was changed, no trial was registered.",
        f"Months: {len(monthly)}; crash months (return <= {threshold:.0%}): "
        f"{int((monthly['ret'] <= threshold).sum())}.",
        "",
        "These states come from Binance hourly candles and cannot be built from the daily",
        "panel the strategy already sees. They are read at the last close before each month",
        "and compared with that month's net 20 bps return and its BTC return; the decisive",
        "column is `excess`, because the failure mode is market up and strategy down.",
        "",
        "## Pre-declared bar (family-wise over both screens)",
        "",
        f"`|Spearman(state, excess)| >= {IC_BAR:.2f}` - the 5% two-sided level divided by the",
        "eighteen candidate states of Section 00.15 and this section - plus monotone terciles",
        f"and `|diff_over_rest_std| >= {SEPARATION_BAR:.2f}`.",
        "",
        "## Point-in-time Top20 coverage of the hourly feed",
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
        "could change a rule; a state that fails is a rejected hypothesis.",
        "",
    ]
    return "\n".join(lines)


def _coverage_table(
    hourly: dict[str, pd.DataFrame], universe: pd.DataFrame, index: pd.DatetimeIndex
) -> pd.DataFrame:
    snapshots = _member_snapshots(universe, index)
    members = sorted({coin for coins in snapshots.values() for coin in coins})
    available = set(hourly)
    observed = total = 0
    for date in index:
        present = snapshots[pd.Timestamp(date)]
        total += len(present)
        observed += sum(1 for coin in present if coin in available)
    return pd.DataFrame(
        {
            "metric": [
                "hourly pairs loaded",
                "distinct point-in-time members",
                "members without hourly data",
                "member-days observed",
                "member-days total",
                "member-day coverage",
            ],
            "value": [
                float(len(available)),
                float(len(members)),
                float(len([coin for coin in members if coin not in available])),
                float(observed),
                float(total),
                float(observed / total) if total else float("nan"),
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", default=DEFAULT_TRIAL)
    parser.add_argument("--returns-file", type=Path, default=DEFAULT_RETURNS)
    parser.add_argument("--column", default=DEFAULT_COLUMN)
    parser.add_argument("--hourly-dir", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--crash-threshold", type=float, default=DEFAULT_CRASH_THRESHOLD)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_hourly_states"))
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

    hourly = load_hourly_bars(args.hourly_dir)
    coverage = _coverage_table(hourly, universe, index)

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

    hourly_state = hourly_state_frame(market, universe, index, hourly)
    monthly = monthly_frame(port, btc, hourly_state, legacy).dropna(subset=["ret", "btc"])

    separation = separation_table(monthly, args.crash_threshold, HOURLY_STATE_COLUMNS)
    information = information_table(monthly, HOURLY_STATE_COLUMNS)
    terciles = tercile_table(monthly, HOURLY_STATE_COLUMNS)
    redundancy = redundancy_table(monthly, HOURLY_STATE_COLUMNS, EXISTING_STATE_COLUMNS)
    verdicts = _verdicts(
        separation,
        information,
        terciles,
        HOURLY_STATE_COLUMNS,
        ic_bar=IC_BAR,
        separation_bar=SEPARATION_BAR,
    )

    output_dir = ensure_dir(args.output_dir)
    monthly.to_csv(output_dir / "monthly_state.csv", index_label="month")
    hourly_state.to_csv(output_dir / "daily_hourly_state.csv", index_label="date")
    coverage.to_csv(output_dir / "hourly_coverage.csv", index=False)
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
            trial_id=args.trial_id,
            threshold=args.crash_threshold,
            coverage=coverage,
        ),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "script": "scripts/analyze_momentum_hourly_states.py",
                "trial_id": args.trial_id,
                "returns_file": str(args.returns_file),
                "column": args.column,
                "hourly_dir": str(args.hourly_dir),
                "start_date": args.start_date,
                "end_date": args.end_date,
                "cost_bps": args.cost_bps,
                "crash_threshold": args.crash_threshold,
                "ic_bar": IC_BAR,
                "separation_bar": SEPARATION_BAR,
                "state_columns": list(HOURLY_STATE_COLUMNS),
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
