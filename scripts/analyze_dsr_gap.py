"""Price the remaining Deflated Sharpe gap for a saved return series.

The Deflated Sharpe Ratio (DSR) is the AGENTS.md gate the frozen phase-momentum
specification still fails.  This tool asks the inverse question: holding a saved
daily-return series' shape fixed (volatility, skew and kurtosis unchanged) and
raising only its mean, what annualized Sharpe would make the DSR reach the
target?  The answer is a *counterfactual* - it is not a claim that such returns
are attainable, and it selects nothing.  It prices how far the current
specification is from the gate, at each scope the project reports DSR over.

Scope conventions follow ``scripts/run_phase_momentum_multiple_testing.py``:
the ``family`` scope uses the candidate family's own Sharpe dispersion, and
every project scope uses the Top20/2022 pool's dispersion (Sharpe ratios on
other windows are not comparable) while varying only the trial count.

Usage::

    .venv/bin/python scripts/analyze_dsr_gap.py \
        --returns reports/phase_momentum_hypotheses_2026_10/returns_20bps.csv \
        --column 'PR2026-10-H5|h3_day_close|20'
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

from scripts.run_phase_momentum_multiple_testing import (  # noqa: E402
    _deflated_sharpe,
    _expected_max_sharpe,
    _project_scopes,
)

DEFAULT_RETURNS = Path("reports/phase_momentum_hypotheses_2026_10/returns_20bps.csv")
DEFAULT_COLUMN = "PR2026-10-H5|h3_day_close|20"
DEFAULT_TRIAL_SUMMARY = Path("reports/research_trial_inventory/summary.json")
DEFAULT_CANDIDATE_SHARPES = Path("reports/phase_momentum_multiple_testing_overlays/candidate_sharpes.csv")
TARGET_DSR = 0.95
_UPPER_ANNUALIZED_SHARPE = 20.0
_BISECTION_STEPS = 200


def _daily_sharpe(returns: pd.Series) -> float:
    std = float(returns.std(ddof=1))
    return float(returns.mean()) / std if std > 0.0 else 0.0


def required_annualized_sharpe(
    returns: pd.Series,
    *,
    expected_max_sharpe: float,
    target: float = TARGET_DSR,
) -> float:
    """The annualized Sharpe the same distribution has to earn to reach ``target``.

    The counterfactual shifts only the mean: ``returns - mean + m`` keeps the
    standard deviation, skew and kurtosis of the saved series, so the comparison
    is against the same return shape, not a rescaled one.  Returns ``inf`` when
    even a 20x annualized Sharpe does not reach the target.
    """
    if not 0.0 < target < 1.0:
        raise ValueError("target must be in (0, 1)")
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 3:
        raise ValueError("need at least three return observations")
    centred = clean - clean.mean()
    std = float(clean.std(ddof=1))
    if std <= 0.0:
        raise ValueError("return series has no dispersion")

    def probability(mean: float) -> float:
        return _deflated_sharpe(centred + mean, expected_max_sharpe=expected_max_sharpe)[
            "deflated_sharpe_probability"
        ]

    if probability(float(clean.mean())) >= target:
        return float(_daily_sharpe(clean) * np.sqrt(365.0))
    high = _UPPER_ANNUALIZED_SHARPE / np.sqrt(365.0) * std
    if probability(high) < target:
        return float("inf")
    low = 0.0
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2.0
        if probability(middle) < target:
            low = middle
        else:
            high = middle
    mean = (low + high) / 2.0
    return float(mean / std * np.sqrt(365.0))


def _family_scope(path: Path) -> tuple[int, float]:
    """The candidate family's own trial count and per-period Sharpe dispersion."""
    frame = pd.read_csv(path)
    annualized = pd.to_numeric(frame["annualized_sharpe"], errors="coerce").dropna()
    if len(annualized) < 2:
        raise ValueError(f"{path}: need at least two candidate Sharpes")
    return int(len(annualized)), float(annualized.std(ddof=1) / np.sqrt(365.0))


def analyse(
    returns: pd.Series,
    *,
    trial_summary: Path,
    candidate_sharpes: Path,
    target: float = TARGET_DSR,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    family_count, family_std = _family_scope(candidate_sharpes)
    scopes = [("family", family_count, family_std)]
    scopes += [(name, count, std) for name, count, std in _project_scopes(trial_summary)]
    observed = _daily_sharpe(returns) * np.sqrt(365.0)
    for scope, count, std in scopes:
        expected = _expected_max_sharpe(int(count), float(std))
        current = _deflated_sharpe(returns, expected_max_sharpe=expected)
        required = required_annualized_sharpe(
            returns, expected_max_sharpe=expected, target=target
        )
        rows.append(
            {
                "scope": scope,
                "trial_count": int(count),
                "trial_sharpe_std_annualized": float(std) * np.sqrt(365.0),
                "expected_max_sharpe": float(expected) * np.sqrt(365.0),
                "observed_sharpe": observed,
                "deflated_sharpe_probability": current["deflated_sharpe_probability"],
                "dsr_target": target,
                "required_annualized_sharpe": required,
                "shortfall_ratio": required / observed if np.isfinite(required) else float("inf"),
                "clears_target": bool(current["deflated_sharpe_probability"] >= target),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--returns", type=Path, default=DEFAULT_RETURNS)
    parser.add_argument("--column", default=DEFAULT_COLUMN)
    parser.add_argument("--trial-summary", type=Path, default=DEFAULT_TRIAL_SUMMARY)
    parser.add_argument("--candidate-sharpes", type=Path, default=DEFAULT_CANDIDATE_SHARPES)
    parser.add_argument("--target", type=float, default=TARGET_DSR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    frame = pd.read_csv(args.returns, parse_dates=["date"]).set_index("date")
    if args.column not in frame.columns:
        raise ValueError(f"column {args.column!r} is not in {args.returns}")
    table = analyse(
        pd.to_numeric(frame[args.column], errors="coerce"),
        trial_summary=args.trial_summary,
        candidate_sharpes=args.candidate_sharpes,
        target=args.target,
    )
    print(f"column: {args.column} ({len(frame)} rows)")
    print(table.to_string(index=False))
    if args.output_dir is not None:
        from atlas20.logging_utils import ensure_dir

        output_dir = ensure_dir(args.output_dir)
        table.to_csv(output_dir / "dsr_gap.csv", index=False)
        (output_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "script": "scripts/analyze_dsr_gap.py",
                    "returns": str(args.returns),
                    "column": args.column,
                    "trial_summary": str(args.trial_summary),
                    "candidate_sharpes": str(args.candidate_sharpes),
                    "target": args.target,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {output_dir / 'dsr_gap.csv'}")


if __name__ == "__main__":
    main()
