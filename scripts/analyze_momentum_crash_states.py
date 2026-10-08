"""Do any candidate state variables mark the frozen spec's worst months?

The frozen specification (H5) still fails the Deflated Sharpe gate, and the
question this tool answers is whether that gap is reachable by adding *another*
market-state overlay on top of the ones it already carries (BTC trend gate,
Top20 breadth co-gate, 60-day volatility target, dispersion overlay).

It takes the frozen trial's realised *net* monthly returns (the saved
20 bps series, costs charged) and, for each month, records the state variables
the strategy can already see at the start of that month: whether the BTC gate is open, Top20 breadth, the dispersion ratio
(current dispersion / its own 252-day 75th percentile), market realised
volatility, the strategy's own trailing 63-day return (a crowding proxy) and
its average gross exposure.  It then compares the months that lost more than a
threshold with the rest.

A state variable is only a candidate for a new overlay if it separates the two
groups.  This tool is hypothesis *generation*: any separation it finds is
in-sample and would still have to be pre-registered and confirmed out of
sample before it may change a rule.  ``diff_over_rest_std`` is a standardised
difference, not a significance test.

Usage::

    .venv/bin/python scripts/analyze_momentum_crash_states.py \
        --output-dir reports/phase_momentum_crash_states
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
STATE_COLUMNS = (
    "gate_open",
    "breadth",
    "disp_ratio",
    "mkt_vol",
    "own63_before",
    "gross",
)


def monthly_state_frame(port: pd.Series, state: pd.DataFrame) -> pd.DataFrame:
    """Calendar-month returns next to the state variables observed that month."""
    month_return = port.resample("ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    frame = pd.DataFrame(
        {
            "ret": month_return,
            "gate_open": state["gate"].resample("ME").mean(),
            "breadth": state["breadth"].resample("ME").mean(),
            "disp_ratio": state["disp_ratio"].resample("ME").mean(),
            "mkt_vol": state["mkt_vol"].resample("ME").mean(),
            # The crowding proxy is a trailing statistic, so it is known at the
            # start of the month and read there rather than averaged in.
            "own63_before": state["own63"].shift(1).resample("ME").first(),
            "gross": state["gross"].resample("ME").mean(),
        }
    )
    return frame.dropna()


def separate_crashes(monthly: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Crash-versus-rest comparison of every state column."""
    crash = monthly[monthly["ret"] <= threshold]
    rest = monthly[monthly["ret"] > threshold]
    if crash.empty or rest.empty:
        raise ValueError(f"threshold {threshold} leaves an empty group")
    table = pd.DataFrame(
        {
            "crash_mean": crash[list(STATE_COLUMNS)].mean(),
            "rest_mean": rest[list(STATE_COLUMNS)].mean(),
        }
    )
    table["difference"] = table["crash_mean"] - table["rest_mean"]
    table["rest_std"] = rest[list(STATE_COLUMNS)].std()
    table["diff_over_rest_std"] = table["difference"] / table["rest_std"]
    table["months_of_data"] = [len(crash)] * len(table)
    return table


def _report(monthly: pd.DataFrame, table: pd.DataFrame, *, trial_id: str, threshold: float) -> str:
    worst = monthly.sort_values("ret").head(12)
    lines = [
        f"# Do any state variables mark {trial_id}'s worst months?",
        "",
        f"Crash months are the calendar months with a return at or below {threshold:.0%}.",
        f"Months in the sample: {len(monthly)}; crash months: {int((monthly['ret'] <= threshold).sum())}.",
        "",
        "## Crash versus rest",
        "",
        "`diff_over_rest_std` is the difference in means divided by the rest-months' standard",
        "deviation. It is a standardised difference for comparison, not a significance test.",
        "",
        dataframe_to_markdown(table),
        "",
        "## Worst months and the state they started in",
        "",
        dataframe_to_markdown(worst),
        "",
        "## Reading",
        "",
        "A state variable only supports a new overlay if the crash months look different from",
        "the rest. Any separation here is in-sample hypothesis generation: it would still have",
        "to be pre-registered and confirmed out of sample before it could change a rule.",
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
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_crash_states"))
    args = parser.parse_args()
    configure_logging("ERROR")

    _config, market, universe, index = _load_market(
        args.config, start_date=args.start_date, end_date=args.end_date
    )
    trial = trial_by_id(args.trial_id)
    built = build_trial(trial, market, universe, index)
    result = _production_result(_config, market, built, index, cost_bps=args.cost_bps)
    weights = result.weights
    # The P&L is the saved net series (costs charged); the build only supplies
    # the state variables and the gross exposure those returns were earned on.
    saved = pd.read_csv(args.returns_file, parse_dates=["date"]).set_index("date")
    if args.column not in saved.columns:
        raise ValueError(f"column {args.column!r} is not in {args.returns_file}")
    port = pd.to_numeric(saved[args.column], errors="coerce").reindex(index).fillna(0.0)

    dispersion = top20_dispersion(market, universe, index, window=21)
    state = pd.DataFrame(
        {
            "gate": btc_above_moving_average(market.price, 100, 2).reindex(index).fillna(False).astype(float),
            "breadth": top20_breadth(market, universe, index, ma_window=50),
            "disp_ratio": dispersion
            / dispersion.rolling(252, min_periods=126).quantile(0.75),
            "mkt_vol": market.returns.mean(axis=1).rolling(60).std() * np.sqrt(365.0),
            "own63": port.rolling(63).apply(lambda x: float(np.prod(1.0 + x) - 1.0), raw=True),
            "gross": weights.sum(axis=1),
        }
    ).loc[index]

    monthly = monthly_state_frame(port, state)
    table = separate_crashes(monthly, args.crash_threshold)
    output_dir = ensure_dir(args.output_dir)
    monthly.to_csv(output_dir / "monthly_state.csv", index_label="month")
    table.to_csv(output_dir / "state_separation.csv", index_label="state_variable")
    (output_dir / "report.md").write_text(
        _report(monthly, table, trial_id=args.trial_id, threshold=args.crash_threshold),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "script": "scripts/analyze_momentum_crash_states.py",
                "trial_id": args.trial_id,
                "returns_file": str(args.returns_file),
                "column": args.column,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "cost_bps": args.cost_bps,
                "crash_threshold": args.crash_threshold,
                "monthly_observations": int(len(monthly)),
                "crash_months": int((monthly["ret"] <= args.crash_threshold).sum()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(table.round(3).to_string())
    print(f"crash months: {int((monthly['ret'] <= args.crash_threshold).sum())} of {len(monthly)}")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
