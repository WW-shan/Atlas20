"""Multiple-testing diagnostics for a derivatives candidate return matrix.

The input is one CSV with a ``date`` column and one column per candidate.  The
script reports per-candidate Deflated Sharpe, a single-step White Reality
Check, and CSCV/PBO.  It is deliberately independent of the mark/funding
source; the caller must label whether the input is a Bitget result or a
proxy diagnostic.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import ensure_dir  # noqa: E402
from scripts.run_phase_momentum_multiple_testing import (  # noqa: E402
    _daily_sharpe,
    _dedupe_identical_columns,
    _deflated_sharpe,
    _expected_max_sharpe,
    _load_candidate_returns,
    _pbo_cscv,
    _reality_check,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--returns", type=Path, required=True)
    parser.add_argument("--trial-count", type=int, required=True)
    parser.add_argument("--bootstrap-count", type=int, default=1000)
    parser.add_argument("--block-length", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.trial_count < 1:
        raise SystemExit("--trial-count must be positive")

    returns = _load_candidate_returns(args.returns)
    returns, duplicates = _dedupe_identical_columns(returns)
    per_period_sharpes = returns.apply(_daily_sharpe)
    expected_max = _expected_max_sharpe(
        args.trial_count,
        float(per_period_sharpes.std(ddof=1)) if len(per_period_sharpes) > 1 else 0.0,
    )
    dsr_rows = []
    for candidate in returns.columns:
        metrics = _deflated_sharpe(returns[candidate], expected_max_sharpe=expected_max)
        dsr_rows.append({"candidate": candidate, **metrics})
    dsr = pd.DataFrame(dsr_rows)
    reality = _reality_check(
        returns,
        n_bootstrap=args.bootstrap_count,
        block_length=args.block_length,
        seed=args.seed,
    )
    try:
        pbo, pbo_splits = _pbo_cscv(returns, n_blocks=12)
    except ValueError as exc:
        pbo = {"pbo": float("nan"), "error": str(exc)}
        pbo_splits = pd.DataFrame()
    summary = {
        "trial_count": int(args.trial_count),
        "candidate_count_used": int(len(returns.columns)),
        "duplicates": duplicates,
        "expected_max_sharpe": expected_max,
        "reality_check": reality,
        "pbo": pbo,
    }
    output_dir = ensure_dir(args.output_dir)
    dsr.to_csv(output_dir / "dsr.csv", index=False)
    pbo_splits.to_csv(output_dir / "pbo_splits.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote derivatives multiple-testing diagnostics to {output_dir}")


if __name__ == "__main__":
    main()
