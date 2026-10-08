"""Does the volume/turnover side of the panel mark the frozen spec's bad months?

Section 00.14 closed one direction: every market-state variable H5 can already
see (BTC gate, breadth, dispersion, volatility, its own trailing return, gross)
separates its worst months from the rest by less than 0.4 standard deviations,
so another overlay built from that same information set would buy little.
The proposed way forward was a *new information source*, and the only one the
project's data can supply without a fresh, slow provider pull is the volume /
market-cap side of the panel.

This tool screens that side.  It is hypothesis generation and nothing else: it
adds no rule, changes no specification, and registers no trial.  A candidate
state variable is only worth a pre-registered H6 if it clears the bar written
down below *before* the screen was run.

Candidate states (all trailing, all known at the close of the day before the
month they are matched with, all computed on the point-in-time Top20 only):

``turnover``
    Top20 total dollar volume / Top20 total market cap.
``turnover_ratio`` / ``volume_ratio``
    Those series over their own trailing 252-day median; the
    liquidity-as-sentiment channel (Baker and Stein, 2004: higher turnover
    predicts lower subsequent returns).
``turnover_disp_ratio``
    Cross-sectional dispersion of per-coin turnover, over its own median.
``amihud_ratio``
    Cross-sectional median of |return| / dollar volume, over its own median
    (Amihud, 2002, adapted to crypto per Brauneis, Mestel, Riordan and
    Theissen, 2021, who show low-frequency crypto illiquidity measures are
    informative).
``mcap_hhi`` / ``btc_share`` / ``volume_top3_share``
    Concentration of the Top20 itself; herding and crowding channels.
``holdings_turnover_ratio``
    Turnover of the coins the frozen spec actually holds, over its own median;
    the volume-conditioned momentum channel (Lee and Swaminathan, 2000;
    Begušić and Kostanjcar, 2019, find crypto momentum is concentrated in the
    most liquid coins).

Reading conventions
-------------------
A state's monthly value is the last reading *before* the month starts
(``shift(1).resample("ME").first()``), because an overlay could only act on it
then.  The monthly return is the frozen trial's saved net 20 bps series, and
the comparison number is the month's BTC return, because the failure mode
Section 00.14 found is "market up, strategy down": a state only helps if it
times the strategy's *excess* return, not the market.

Pre-declared bar for promoting a state to a pre-registered H6
-------------------------------------------------------------
All three, on the 2022-01-01..2026-09-21 sample:

1. ``|Spearman(state, H5 - BTC) | >= 0.25``  (about the unadjusted 5% level at
   n=53; with nine candidates the Bonferroni level is about 0.39, which is
   reported but not required, since H6 would still have to survive its own
   pre-registered out-of-sample test);
2. tercile means of ``H5 - BTC`` ordered monotonically in the state;
3. ``|crash_minus_rest / rest_std| >= 0.50``.

Anything that fails is recorded as a rejected hypothesis, not as a reason to
weaken a gate.

Usage::

    .venv/bin/python scripts/analyze_momentum_flow_states.py \
        --output-dir reports/phase_momentum_flow_states
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import math

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
from atlas20.strategies.phase_momentum import (  # noqa: E402
    top20_breadth,
    top20_dispersion,
)

from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402

DEFAULT_TRIAL = "PR2026-10-H5"
DEFAULT_RETURNS = Path("reports/phase_momentum_hypotheses_2026_10/returns_20bps.csv")
DEFAULT_COLUMN = "PR2026-10-H5|h3_day_close|20"
DEFAULT_CRASH_THRESHOLD = -0.08
IC_BAR = 0.25
SEPARATION_BAR = 0.50
MIN_MEMBERS = 5
RATIO_LOOKBACK = 252
RATIO_MIN_PERIODS = 126

FLOW_STATE_COLUMNS = (
    "turnover",
    "turnover_ratio",
    "volume_ratio",
    "turnover_disp_ratio",
    "amihud_ratio",
    "mcap_hhi",
    "btc_share",
    "volume_top3_share",
    "holdings_turnover_ratio",
)
# Two readings of the states Section 00.14 already studied.  ``_mean`` keeps
# that section's convention (the average of the daily state over the month) so
# the corrected table is directly comparable with it; ``_before`` is the
# actionable convention used for the new flow states (the last reading before
# the month starts, which is all an overlay could act on).
LEGACY_MEAN_COLUMNS = (
    "gate_open_mean",
    "breadth_mean",
    "disp_ratio_mean",
    "mkt_vol_mean",
    "gross_mean",
)
LEGACY_BEFORE_COLUMNS = (
    "gate_open_before",
    "breadth_before",
    "disp_ratio_before",
    "mkt_vol_before",
    "own63_before",
    "gross_before",
)
EXISTING_STATE_COLUMNS = LEGACY_BEFORE_COLUMNS


def _spearman(left: pd.Series, right: pd.Series) -> float:
    """Spearman correlation without a scipy dependency (rank then Pearson)."""
    return float(left.rank().corr(right.rank()))


def _member_snapshots(universe: pd.DataFrame, index: pd.DatetimeIndex) -> dict[pd.Timestamp, list[str]]:
    """Point-in-time Top20 membership for every date in the evaluated window."""
    by_date = {pd.Timestamp(date): group for date, group in universe.groupby("rebalance_date")}
    snapshots: dict[pd.Timestamp, list[str]] = {}
    for date in index:
        snapshot = by_date.get(pd.Timestamp(date))
        snapshots[pd.Timestamp(date)] = (
            [] if snapshot is None or snapshot.empty else snapshot["coin_id"].astype(str).tolist()
        )
    return snapshots


def _ratio_to_median(series: pd.Series) -> pd.Series:
    median = series.rolling(RATIO_LOOKBACK, min_periods=RATIO_MIN_PERIODS).median()
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = series / median.where(median > 0.0)
    return ratio.replace([np.inf, -np.inf], np.nan)


def flow_state_frame(
    market,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    weights: pd.DataFrame,
) -> pd.DataFrame:
    """Daily volume/turnover state variables, each known at its own close."""
    snapshots = _member_snapshots(universe, index)
    per_coin_turnover = market.volume / market.market_cap.where(market.market_cap > 0.0)
    per_coin_amihud = market.returns.abs() / market.volume.where(market.volume > 0.0)

    turnover: dict[pd.Timestamp, float] = {}
    turnover_disp: dict[pd.Timestamp, float] = {}
    amihud: dict[pd.Timestamp, float] = {}
    volume_total: dict[pd.Timestamp, float] = {}
    mcap_hhi: dict[pd.Timestamp, float] = {}
    btc_share: dict[pd.Timestamp, float] = {}
    volume_top3_share: dict[pd.Timestamp, float] = {}
    holdings_turnover: dict[pd.Timestamp, float] = {}

    gross = weights.sum(axis=1)
    held_coins = weights.gt(0.0)

    for date in index:
        members = snapshots[pd.Timestamp(date)]
        if not members:
            for target in (
                turnover,
                turnover_disp,
                amihud,
                volume_total,
                mcap_hhi,
                btc_share,
                volume_top3_share,
                holdings_turnover,
            ):
                target[pd.Timestamp(date)] = float("nan")
            continue

        volume_row = pd.to_numeric(market.volume.loc[date, members], errors="coerce")
        mcap_row = pd.to_numeric(market.market_cap.loc[date, members], errors="coerce")
        turnover_row = pd.to_numeric(per_coin_turnover.loc[date, members], errors="coerce")
        amihud_row = pd.to_numeric(per_coin_amihud.loc[date, members], errors="coerce")

        volume_sum = float(volume_row.sum(min_count=1))
        mcap_sum = float(mcap_row.sum(min_count=1))
        turnover[date] = volume_sum / mcap_sum if mcap_sum and mcap_sum > 0.0 else float("nan")
        volume_total[date] = volume_sum

        usable_turnover = turnover_row.replace([np.inf, -np.inf], np.nan).dropna()
        turnover_disp[date] = (
            float(usable_turnover.std(ddof=1)) if len(usable_turnover) >= MIN_MEMBERS else float("nan")
        )

        usable_amihud = amihud_row.replace([np.inf, -np.inf], np.nan).dropna()
        amihud[date] = float(usable_amihud.median()) if len(usable_amihud) >= MIN_MEMBERS else float("nan")

        usable_mcap = mcap_row.replace([np.inf, -np.inf], np.nan).dropna()
        if len(usable_mcap) >= MIN_MEMBERS and usable_mcap.sum() > 0.0:
            shares = usable_mcap / usable_mcap.sum()
            mcap_hhi[date] = float((shares**2).sum())
            btc_share[date] = float(shares.get("bitcoin", float("nan")))
        else:
            mcap_hhi[date] = float("nan")
            btc_share[date] = float("nan")

        usable_volume = volume_row.replace([np.inf, -np.inf], np.nan).dropna()
        if len(usable_volume) >= MIN_MEMBERS and usable_volume.sum() > 0.0:
            volume_top3_share[date] = float(usable_volume.nlargest(3).sum() / usable_volume.sum())
        else:
            volume_top3_share[date] = float("nan")

        held = held_coins.loc[date] if date in held_coins.index else None
        if held is not None and bool(held.any()):
            held_ids = [coin for coin in held.index[held.to_numpy()] if coin in turnover_row.index]
            held_turnover = (
                pd.to_numeric(per_coin_turnover.loc[date, held_ids], errors="coerce")
                .replace([np.inf, -np.inf], np.nan)
                .dropna()
            )
            holdings_turnover[date] = (
                float(held_turnover.mean()) if not held_turnover.empty else float("nan")
            )
        else:
            holdings_turnover[date] = float("nan")

    frame = pd.DataFrame(
        {
            "turnover": pd.Series(turnover),
            "turnover_ratio": _ratio_to_median(pd.Series(turnover)),
            "volume_ratio": _ratio_to_median(pd.Series(volume_total)),
            "turnover_disp_ratio": _ratio_to_median(pd.Series(turnover_disp)),
            "amihud_ratio": _ratio_to_median(pd.Series(amihud)),
            "mcap_hhi": pd.Series(mcap_hhi),
            "btc_share": pd.Series(btc_share),
            "volume_top3_share": pd.Series(volume_top3_share),
            "holdings_turnover_ratio": _ratio_to_median(pd.Series(holdings_turnover)),
            "gross": gross,
        }
    ).sort_index()
    return frame


def monthly_frame(
    port: pd.Series,
    btc: pd.Series,
    flow: pd.DataFrame,
    legacy: pd.DataFrame,
) -> pd.DataFrame:
    """Calendar-month returns next to the state readings known before the month."""
    month_end = port.resample("ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    btc_month = btc.resample("ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    before = lambda series: series.shift(1).resample("ME").first()  # noqa: E731
    frame = pd.DataFrame({"ret": month_end, "btc": btc_month})
    frame["excess"] = frame["ret"] - frame["btc"]
    for column in FLOW_STATE_COLUMNS:
        frame[column] = before(flow[column])
    for column in ("gate_open", "breadth", "disp_ratio", "mkt_vol", "gross"):
        frame[f"{column}_before"] = before(legacy[column])
        frame[f"{column}_mean"] = legacy[column].resample("ME").mean()
    frame["own63_before"] = before(legacy["own63_before"])
    return frame


def separation_table(monthly: pd.DataFrame, threshold: float, columns) -> pd.DataFrame:
    crash = monthly[monthly["ret"] <= threshold]
    rest = monthly[monthly["ret"] > threshold]
    if crash.empty or rest.empty:
        raise ValueError(f"threshold {threshold} leaves an empty group")
    rows = {}
    for column in columns:
        crash_values = crash[column].dropna()
        rest_values = rest[column].dropna()
        if len(crash_values) < 2 or len(rest_values) < 3:
            rows[column] = {
                "crash_mean": float("nan"),
                "rest_mean": float("nan"),
                "difference": float("nan"),
                "rest_std": float("nan"),
                "diff_over_rest_std": float("nan"),
                "welch_t": float("nan"),
                "crash_months": len(crash_values),
            }
            continue
        difference = float(crash_values.mean() - rest_values.mean())
        rest_std = float(rest_values.std(ddof=1))
        standard_error = float(
            np.sqrt(crash_values.var(ddof=1) / len(crash_values) + rest_values.var(ddof=1) / len(rest_values))
        )
        rows[column] = {
            "crash_mean": float(crash_values.mean()),
            "rest_mean": float(rest_values.mean()),
            "difference": difference,
            "rest_std": rest_std,
            "diff_over_rest_std": difference / rest_std if rest_std else float("nan"),
            "welch_t": difference / standard_error if standard_error else float("nan"),
            "crash_months": len(crash_values),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def information_table(monthly: pd.DataFrame, columns) -> pd.DataFrame:
    """Spearman information coefficient against next-month excess return."""
    rows = {}
    for column in columns:
        pair = monthly[[column, "excess"]].dropna()
        if len(pair) < 10 or pair[column].nunique() < 3:
            rows[column] = {"observations": len(pair), "spearman": float("nan"), "p_value": float("nan")}
            continue
        rho = _spearman(pair[column], pair["excess"])
        # Normal approximation of the two-sided p-value for rho; n is around 50,
        # so this is scale, not an exact test, and the screen is in-sample anyway.
        t_stat = rho * math.sqrt((len(pair) - 2) / max(1e-12, 1.0 - rho**2))
        p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
        rows[column] = {"observations": int(len(pair)), "spearman": rho, "p_value": p_value}
    return pd.DataFrame.from_dict(rows, orient="index")


def tercile_table(monthly: pd.DataFrame, columns, buckets: int = 3) -> pd.DataFrame:
    """Mean strategy, BTC and excess return per state bucket (low to high)."""
    rows = []
    for column in columns:
        pair = monthly[[column, "ret", "btc", "excess"]].dropna()
        if len(pair) < buckets * 3 or pair[column].nunique() < buckets:
            continue
        try:
            labels = pd.qcut(pair[column], buckets, labels=False, duplicates="drop")
        except ValueError:
            continue
        for bucket, group in pair.groupby(labels):
            rows.append(
                {
                    "state": column,
                    "bucket": int(bucket) + 1,
                    "months": int(len(group)),
                    "mean_ret": float(group["ret"].mean()),
                    "mean_btc": float(group["btc"].mean()),
                    "mean_excess": float(group["excess"].mean()),
                    "hit_rate": float((group["ret"] > 0.0).mean()),
                }
            )
    return pd.DataFrame(rows)


def redundancy_table(monthly: pd.DataFrame, columns, reference_columns) -> pd.DataFrame:
    rows = {}
    for column in columns:
        row = {}
        for reference in reference_columns:
            pair = monthly[[column, reference]].dropna()
            row[reference] = _spearman(pair[column], pair[reference]) if len(pair) >= 10 else float("nan")
        rows[column] = row
    return pd.DataFrame.from_dict(rows, orient="index")


def _verdicts(
    separation: pd.DataFrame,
    information: pd.DataFrame,
    terciles: pd.DataFrame,
    columns,
    *,
    ic_bar: float = IC_BAR,
    separation_bar: float = SEPARATION_BAR,
) -> pd.DataFrame:
    rows = {}
    for column in columns:
        separation_ratio = float(separation.loc[column, "diff_over_rest_std"])
        rho = float(information.loc[column, "spearman"])
        bucket_means = (
            terciles[terciles["state"] == column].sort_values("bucket")["mean_excess"].tolist()
            if not terciles.empty and (terciles["state"] == column).any()
            else []
        )
        monotone = (
            len(bucket_means) == 3
            and (
                (bucket_means[0] < bucket_means[1] < bucket_means[2])
                or (bucket_means[0] > bucket_means[1] > bucket_means[2])
            )
        )
        passes_ic = abs(rho) >= ic_bar
        passes_separation = abs(separation_ratio) >= separation_bar
        rows[column] = {
            "spearman": rho,
            "abs_spearman": abs(rho),
            "ic_bar": ic_bar,
            "separation_bar": separation_bar,
            "passes_ic_bar": bool(passes_ic),
            "tercile_monotone": bool(monotone),
            "diff_over_rest_std": separation_ratio,
            "passes_separation_bar": bool(passes_separation),
            "promote_to_h6": bool(passes_ic and monotone and passes_separation),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def _report(
    monthly: pd.DataFrame,
    separation: pd.DataFrame,
    legacy_separation_corrected: pd.DataFrame,
    legacy_separation_actionable: pd.DataFrame,
    information: pd.DataFrame,
    terciles: pd.DataFrame,
    redundancy: pd.DataFrame,
    verdicts: pd.DataFrame,
    *,
    trial_id: str,
    threshold: float,
) -> str:
    promoted = verdicts.index[verdicts["promote_to_h6"]].tolist()
    worst = monthly.sort_values("ret").head(12)
    lines = [
        f"# Do volume / turnover states mark {trial_id}'s bad months?",
        "",
        "Hypothesis generation only: no rule was changed, no trial was registered.",
        f"Months: {len(monthly)}; crash months (return <= {threshold:.0%}): "
        f"{int((monthly['ret'] <= threshold).sum())}.",
        "",
        "The states are read at the last close before each month and compared with that",
        "month's net 20 bps return and with that month's BTC return. Section 00.14 found the",
        "failure mode is *market up, strategy down*, so the decisive column is `excess`",
        "(strategy minus BTC).",
        "",
        "## Pre-declared bar",
        "",
        f"`|Spearman(state, excess)| >= {IC_BAR:.2f}`, monotone terciles, and "
        f"`|diff_over_rest_std| >= {SEPARATION_BAR:.2f}`.",
        "",
        "## Crash versus rest",
        "",
        "`welch_t` is the difference in means over the standard error of that difference;",
        "it is reported for scale, and with nine candidates it is not a significance test.",
        "",
        dataframe_to_markdown(separation),
        "",
        "## The states H5 already carries, Section 00.14's convention, full sample",
        "",
        "Section 00.14 reported this table on 53 of the 57 months: it dropped every row with a",
        "missing state, and two warm-ups bind early on - `disp_ratio` needs 126 usable",
        "dispersion readings and `own63` needs 63 days of the return series. That discarded",
        "2022-01..04, including 2022-04, a 10th crash month. The numbers below keep the same within-month",
        "averaging convention but drop missing values state by state across all 57 months, so",
        "they supersede the earlier table.",
        "",
        dataframe_to_markdown(legacy_separation_corrected),
        "",
        "## The same states read before the month instead (what an overlay could act on)",
        "",
        "This is the convention the flow states above use, and it is the one an H6 overlay",
        "would have to use. `own63_before` is identical in both tables.",
        "",
        dataframe_to_markdown(legacy_separation_actionable),
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
        "A value near zero means the state carries information the frozen spec cannot see.",
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
        "could change a rule; a state that fails is recorded as a rejected hypothesis.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--trial-id", default=DEFAULT_TRIAL)
    parser.add_argument("--returns-file", type=Path, default=DEFAULT_RETURNS)
    parser.add_argument("--column", default=DEFAULT_COLUMN)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--crash-threshold", type=float, default=DEFAULT_CRASH_THRESHOLD)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_flow_states"))
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

    flow = flow_state_frame(market, universe, index, weights)
    monthly = monthly_frame(port, btc, flow, legacy).dropna(subset=["ret", "btc"])

    separation = separation_table(monthly, args.crash_threshold, FLOW_STATE_COLUMNS)
    legacy_separation_corrected = separation_table(monthly, args.crash_threshold, LEGACY_MEAN_COLUMNS)
    legacy_separation_actionable = separation_table(
        monthly, args.crash_threshold, LEGACY_BEFORE_COLUMNS
    )
    information = information_table(monthly, FLOW_STATE_COLUMNS)
    terciles = tercile_table(monthly, FLOW_STATE_COLUMNS)
    redundancy = redundancy_table(monthly, FLOW_STATE_COLUMNS, EXISTING_STATE_COLUMNS)
    verdicts = _verdicts(separation, information, terciles, FLOW_STATE_COLUMNS)

    output_dir = ensure_dir(args.output_dir)
    monthly.to_csv(output_dir / "monthly_state.csv", index_label="month")
    flow.to_csv(output_dir / "daily_flow_state.csv", index_label="date")
    separation.to_csv(output_dir / "state_separation.csv", index_label="state_variable")
    legacy_separation_corrected.to_csv(
        output_dir / "state_separation_legacy_corrected.csv", index_label="state_variable"
    )
    legacy_separation_actionable.to_csv(
        output_dir / "state_separation_legacy_actionable.csv", index_label="state_variable"
    )
    information.to_csv(output_dir / "state_information.csv", index_label="state_variable")
    terciles.to_csv(output_dir / "state_terciles.csv", index=False)
    redundancy.to_csv(output_dir / "state_redundancy.csv", index_label="state_variable")
    verdicts.to_csv(output_dir / "state_verdicts.csv", index_label="state_variable")
    (output_dir / "report.md").write_text(
        _report(
            monthly,
            separation,
            legacy_separation_corrected,
            legacy_separation_actionable,
            information,
            terciles,
            redundancy,
            verdicts,
            trial_id=args.trial_id,
            threshold=args.crash_threshold,
        ),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "script": "scripts/analyze_momentum_flow_states.py",
                "trial_id": args.trial_id,
                "returns_file": str(args.returns_file),
                "column": args.column,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "cost_bps": args.cost_bps,
                "crash_threshold": args.crash_threshold,
                "ic_bar": IC_BAR,
                "separation_bar": SEPARATION_BAR,
                "state_columns": list(FLOW_STATE_COLUMNS),
                "legacy_state_columns": {
                    "mean_convention": list(LEGACY_MEAN_COLUMNS),
                    "before_convention": list(LEGACY_BEFORE_COLUMNS),
                },
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
