"""Price how much genuine out-of-sample data closes the Deflated-Sharpe gap.

The Deflated Sharpe Ratio is the one AGENTS.md gate the frozen phase-momentum
specification still fails, and it fails because of the project's selection
history (6,138 Top20/2022 trials), not because the sample is short.  Adding
trials cannot repair it - it only raises the hurdle.  Adding *new* data can:
the DSR statistic grows with the sample length whenever the realized Sharpe
stays above the expected-maximum hurdle.

This tool prices that trade-off.  It takes a saved daily-return series, keeps
its shape (volatility, skew and kurtosis) fixed, and appends ``H`` synthetic
out-of-sample days earning a chosen annualized Sharpe.  It then reports the
combined DSR under the project scope.  The OOS block is a counterfactual used
to size the waiting period; it is not a forecast and it selects nothing.

Usage::

    .venv/bin/python scripts/analyze_dsr_horizon.py \
        --returns reports/phase_momentum_hypotheses_2026_10/returns_20bps.csv \
        --column 'PR2026-10-H5|h3_day_close|20'
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from statistics import NormalDist

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.run_phase_momentum_multiple_testing import (  # noqa: E402
    _expected_max_sharpe,
    _project_scopes,
)

DEFAULT_RETURNS = Path("reports/phase_momentum_hypotheses_2026_10/returns_20bps.csv")
DEFAULT_COLUMN = "PR2026-10-H5|h3_day_close|20"
DEFAULT_TRIAL_SUMMARY = Path("reports/research_trial_inventory/summary.json")
DEFAULT_OUTPUT = Path("reports/phase_momentum_dsr_horizon")
DEFAULT_SCOPE = "top20_2022_trials"
TARGET_DSR = 0.95
PERIODS_PER_YEAR = 365.0
HORIZONS = (30, 90, 180, 365, 730, 1095)
ASSUMED_SHARPES = (0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)
# One-sided critical values for an out-of-sample-only t-test on the Sharpe.
OOS_TEST_LEVELS = {"95%": 1.6449, "99%": 2.3263}
_MAX_HORIZON_DAYS = 10_000
_BISECTION_STEPS = 120


@dataclass(frozen=True)
class ReturnShape:
    """Mean, standard deviation, skew and raw (not excess) kurtosis."""

    mean: float
    std: float
    skew: float
    kurtosis: float


def _raw_moments(values: np.ndarray) -> tuple[float, float, float, float]:
    return (
        float(values.mean()),
        float((values**2).mean()),
        float((values**3).mean()),
        float((values**4).mean()),
    )


def _shape_from_raw(m1: float, m2: float, m3: float, m4: float) -> ReturnShape:
    """Central shape from raw moments (population moments)."""
    mean = m1
    variance = m2 - mean * mean
    if variance <= 0.0:
        return ReturnShape(mean, 0.0, 0.0, 3.0)
    std = float(np.sqrt(variance))
    skew = (m3 - 3.0 * mean * m2 + 2.0 * mean**3) / std**3
    kurtosis = (m4 - 4.0 * mean * m3 + 6.0 * mean**2 * m2 - 3.0 * mean**4) / variance**2
    return ReturnShape(mean, std, float(skew), float(kurtosis))


def _raw_from_shape(shape: ReturnShape) -> tuple[float, float, float, float]:
    """Raw moments from a central shape, using the standard moment identities."""
    mean, std = shape.mean, shape.std
    m1 = mean
    m2 = std**2 + mean**2
    m3 = shape.skew * std**3 + 3.0 * mean * std**2 + mean**3
    m4 = (
        shape.kurtosis * std**4
        + 4.0 * mean * shape.skew * std**3
        + 6.0 * mean**2 * std**2
        + mean**4
    )
    return m1, m2, m3, m4


def _combine_raw(
    n_a: int, raw_a: tuple[float, float, float, float],
    n_b: int, raw_b: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    total = n_a + n_b
    return tuple((n_a * a + n_b * b) / total for a, b in zip(raw_a, raw_b))  # type: ignore[return-value]


def deflated_sharpe_probability(
    shape: ReturnShape,
    n_observations: int,
    *,
    expected_max_sharpe_per_period: float,
) -> float:
    """DSR from an explicit return shape, matching the project's formula."""
    if n_observations < 3 or shape.std <= 0.0:
        return 0.0
    sr = shape.mean / shape.std
    variance_term = 1.0 - shape.skew * sr + ((shape.kurtosis - 1.0) / 4.0) * sr * sr
    if variance_term <= 0.0:
        return 0.0
    statistic = (
        (sr - expected_max_sharpe_per_period)
        * np.sqrt(max(n_observations - 1, 1))
        / np.sqrt(variance_term)
    )
    return float(NormalDist().cdf(statistic))


def combined_shape(
    in_sample: pd.Series,
    *,
    oos_days: int,
    oos_annualized_sharpe: float,
) -> tuple[ReturnShape, int]:
    """Shape of ``in_sample`` plus ``oos_days`` days at the chosen Sharpe.

    The OOS block reuses the in-sample volatility, skew and kurtosis, so only
    the mean is hypothetical: the counterfactual is "the same strategy, a
    different average return", not a rescaled or reshaped one.
    """
    clean = pd.to_numeric(in_sample, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 3:
        raise ValueError("need at least three in-sample observations")
    values = clean.to_numpy(dtype=float)
    base = _shape_from_raw(*_raw_moments(values))
    if oos_days <= 0:
        return base, len(values)
    daily_mean = (oos_annualized_sharpe / np.sqrt(PERIODS_PER_YEAR)) * base.std
    oos_shape = ReturnShape(daily_mean, base.std, base.skew, base.kurtosis)
    combined = _combine_raw(
        len(values), _raw_from_shape(base),
        int(oos_days), _raw_from_shape(oos_shape),
    )
    return _shape_from_raw(*combined), len(values) + int(oos_days)


def _solve(
    in_sample: pd.Series,
    *,
    expected_max_sharpe_per_period: float,
    target: float,
    fixed_days: int | None = None,
    fixed_sharpe: float | None = None,
    lower: float = 0.0,
    upper: float,
) -> float:
    """Bisect for the days (given a Sharpe) or the Sharpe (given days)."""
    def value(x: float) -> float:
        if fixed_days is None:
            shape, n = combined_shape(
                in_sample, oos_days=int(round(x)), oos_annualized_sharpe=float(fixed_sharpe)
            )
        else:
            shape, n = combined_shape(
                in_sample, oos_days=int(fixed_days), oos_annualized_sharpe=float(x)
            )
        return deflated_sharpe_probability(
            shape, n, expected_max_sharpe_per_period=expected_max_sharpe_per_period
        ) - target

    if value(lower) >= 0.0:
        return float(lower)
    if value(upper) < 0.0:
        return float("nan")
    for _ in range(_BISECTION_STEPS):
        middle = 0.5 * (lower + upper)
        if value(middle) >= 0.0:
            upper = middle
        else:
            lower = middle
    return 0.5 * (lower + upper)


def oos_days_for_significant_sharpe(
    annualized_sharpe: float,
    *,
    critical_value: float,
) -> float:
    """Days of OOS needed for a one-sided t-test on the OOS Sharpe alone.

    Unlike the DSR, this test does not pay the selection penalty again: the OOS
    window was never used to choose the specification, so its Sharpe is an
    unbiased estimate.  ``t = SR_annualized * sqrt(years)`` under an iid
    approximation, so ``days = 365 * (critical / SR)^2``.
    """
    if annualized_sharpe <= 0.0:
        return float("inf")
    return PERIODS_PER_YEAR * (critical_value / annualized_sharpe) ** 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt(value: float, digits: int = 4) -> str:
    return "-" if not np.isfinite(value) else f"{value:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--returns", type=Path, default=DEFAULT_RETURNS)
    parser.add_argument("--column", default=DEFAULT_COLUMN)
    parser.add_argument("--trial-summary", type=Path, default=DEFAULT_TRIAL_SUMMARY)
    parser.add_argument("--scope", default=DEFAULT_SCOPE)
    parser.add_argument("--target", type=float, default=TARGET_DSR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    configure_logging("ERROR")
    frame = pd.read_csv(args.returns, parse_dates=[0], index_col=0)
    if args.column not in frame.columns:
        raise ValueError(f"{args.column!r} not in {args.returns}: {list(frame.columns)[:5]}...")
    series = frame[args.column]
    scopes = {name: (count, std) for name, count, std in _project_scopes(args.trial_summary)}
    if args.scope not in scopes:
        raise ValueError(f"unknown scope {args.scope!r}; have {sorted(scopes)}")
    count, sharpe_std = scopes[args.scope]
    hurdle = _expected_max_sharpe(count, sharpe_std)
    base_shape = _shape_from_raw(*_raw_moments(series.to_numpy(dtype=float)))
    base_dsr = deflated_sharpe_probability(
        base_shape, len(series), expected_max_sharpe_per_period=hurdle
    )

    horizon_rows: list[dict[str, object]] = []
    for days in (0, *HORIZONS):
        if days == 0:
            shape, n = base_shape, len(series)
        else:
            shape, n = combined_shape(
                series, oos_days=days, oos_annualized_sharpe=base_shape.mean / base_shape.std * np.sqrt(PERIODS_PER_YEAR)
            )
        horizon_rows.append(
            {
                "oos_days": days,
                "total_days": n,
                "oos_annualized_sharpe": base_shape.mean / base_shape.std * np.sqrt(PERIODS_PER_YEAR),
                "combined_annualized_sharpe": shape.mean / shape.std * np.sqrt(PERIODS_PER_YEAR),
                "dsr": deflated_sharpe_probability(
                    shape, n, expected_max_sharpe_per_period=hurdle
                ),
            }
        )
    horizon = pd.DataFrame(horizon_rows)

    required_rows: list[dict[str, object]] = []
    for days in HORIZONS:
        required = _solve(
            series,
            expected_max_sharpe_per_period=hurdle,
            target=args.target,
            fixed_days=days,
            upper=20.0,
        )
        required_rows.append(
            {
                "oos_days": days,
                "oos_years": days / PERIODS_PER_YEAR,
                "required_oos_annualized_sharpe": required,
                "multiplier_vs_in_sample": required / (base_shape.mean / base_shape.std * np.sqrt(PERIODS_PER_YEAR))
                if np.isfinite(required)
                else float("nan"),
            }
        )
    required = pd.DataFrame(required_rows)

    wait_rows: list[dict[str, object]] = []
    for sharpe in ASSUMED_SHARPES:
        days = _solve(
            series,
            expected_max_sharpe_per_period=hurdle,
            target=args.target,
            fixed_sharpe=sharpe,
            upper=float(_MAX_HORIZON_DAYS),
        )
        wait_rows.append(
            {
                "assumed_oos_annualized_sharpe": sharpe,
                "required_oos_days": days,
                "required_oos_years": days / PERIODS_PER_YEAR if np.isfinite(days) else float("nan"),
            }
        )
    wait = pd.DataFrame(wait_rows)

    oos_rows: list[dict[str, object]] = []
    in_sample_sharpe = base_shape.mean / base_shape.std * np.sqrt(PERIODS_PER_YEAR)
    for sharpe in ASSUMED_SHARPES:
        row: dict[str, object] = {"assumed_oos_annualized_sharpe": sharpe}
        for label, critical in OOS_TEST_LEVELS.items():
            days = oos_days_for_significant_sharpe(sharpe, critical_value=critical)
            row[f"days_to_{label}_t_test"] = days
            row[f"years_to_{label}_t_test"] = days / PERIODS_PER_YEAR if np.isfinite(days) else float("nan")
        oos_rows.append(row)
    oos_only = pd.DataFrame(oos_rows)

    output_dir = ensure_dir(args.output_dir)
    horizon.to_csv(output_dir / "dsr_by_horizon.csv", index=False, float_format="%.6f")
    oos_only.to_csv(output_dir / "oos_only_significance.csv", index=False, float_format="%.6f")
    required.to_csv(output_dir / "required_oos_sharpe.csv", index=False, float_format="%.6f")
    wait.to_csv(output_dir / "required_oos_days.csv", index=False, float_format="%.6f")
    manifest = {
        "script": "scripts/analyze_dsr_horizon.py",
        "generated_at_utc": _utc_now(),
        "returns": str(args.returns),
        "column": args.column,
        "trial_summary": str(args.trial_summary),
        "scope": args.scope,
        "trial_count": count,
        "sharpe_std_per_period": sharpe_std,
        "expected_max_sharpe_annualized": hurdle * np.sqrt(PERIODS_PER_YEAR),
        "in_sample_days": int(len(series)),
        "in_sample_annualized_sharpe": base_shape.mean / base_shape.std * np.sqrt(PERIODS_PER_YEAR),
        "in_sample_dsr": base_dsr,
        "target_dsr": args.target,
        "horizons_days": list(HORIZONS),
        "assumed_oos_sharpes": list(ASSUMED_SHARPES),
        "oos_only_test_levels": OOS_TEST_LEVELS,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = [
        "# How much out-of-sample data closes the Deflated-Sharpe gap?",
        "",
        f"Series: `{args.column}` in `{args.returns}` ({len(series)} days).",
        f"Scope: `{args.scope}` with N = {count:,} trials; expected-maximum Sharpe "
        f"{hurdle * np.sqrt(PERIODS_PER_YEAR):.3f} annualized.",
        f"In-sample annualized Sharpe {manifest['in_sample_annualized_sharpe']:.3f}, DSR "
        f"{base_dsr:.3f} (target {args.target:.2f}).",
        "",
        "The OOS block is a counterfactual: the same return shape, a different mean.",
        "It is not a forecast, and it selects nothing.",
        "",
        "## DSR if new data earns exactly the in-sample Sharpe",
        "",
        dataframe_to_markdown(horizon),
        "",
        "## Out-of-sample Sharpe needed at a fixed horizon",
        "",
        dataframe_to_markdown(required),
        "",
        "## Days needed at an assumed out-of-sample Sharpe",
        "",
        dataframe_to_markdown(wait),
        "",
        "## Contrast: an out-of-sample-only test is far cheaper than the DSR",
        "",
        "The DSR re-pays the selection penalty on the whole sample. A test that uses",
        "only data collected after the freeze does not: that window never selected",
        "the specification, so its Sharpe is an unbiased estimate. The table below",
        "is the one-sided t-test on the OOS Sharpe alone (`t = SR * sqrt(years)`).",
        "",
        dataframe_to_markdown(oos_only),
        "",
        f"For reference the in-sample annualized Sharpe is {in_sample_sharpe:.3f}.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(dataframe_to_markdown(required))
    print()
    print(dataframe_to_markdown(wait))
    print(f"\nWrote DSR-horizon analysis to {output_dir}")


if __name__ == "__main__":
    main()
