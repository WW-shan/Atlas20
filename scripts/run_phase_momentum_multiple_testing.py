"""Multiple-testing diagnostics for the phase-momentum candidate family.

This runner implements three complementary checks on the already-produced
20 bps candidate return matrix:

* Deflated Sharpe Ratio (DSR) using the number of trials and the cross-trial
  dispersion of Sharpe ratios.
* A stationary-bootstrap White Reality Check for the maximum candidate mean
  return.
* Combinatorial Symmetric Cross-Validation (CSCV) probability of backtest
  overfitting (PBO) using 12 contiguous blocks.

The diagnostics are deliberately conservative: they are not used to choose a
new parameter, only to judge whether the best full-sample candidate remains
credible after accounting for the number of tried variants.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from itertools import combinations
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


def _daily_sharpe(returns: pd.Series) -> float:
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 2 or float(clean.std(ddof=1)) <= 0.0:
        return 0.0
    return float(clean.mean() / clean.std(ddof=1))


def _deflated_sharpe(
    returns: pd.Series,
    *,
    trial_count: int,
    trial_sharpes: pd.Series,
) -> dict[str, float]:
    """Bailey and Lopez de Prado's DSR using the observed trial dispersion."""
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 3:
        return {
            "observed_sharpe": 0.0,
            "expected_max_sharpe": 0.0,
            "deflated_sharpe_probability": 0.0,
        }
    sr = _daily_sharpe(clean)
    skew = float(clean.skew()) if clean.std(ddof=1) > 0.0 else 0.0
    kurtosis = float(clean.kurtosis() + 3.0) if clean.std(ddof=1) > 0.0 else 3.0
    trial_std = float(trial_sharpes.std(ddof=1)) if len(trial_sharpes) > 1 else 0.0
    if trial_count <= 1 or trial_std <= 0.0:
        sr0 = 0.0
    else:
        normal = NormalDist()
        gamma = 0.5772156649015329
        z1 = normal.inv_cdf(1.0 - 1.0 / trial_count)
        z2 = normal.inv_cdf(1.0 - 1.0 / (trial_count * np.e))
        sr0 = trial_std * ((1.0 - gamma) * z1 + gamma * z2)
    variance_term = 1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr * sr
    if variance_term <= 0.0:
        probability = 0.0
    else:
        statistic = (sr - sr0) * np.sqrt(max(len(clean) - 1, 1)) / np.sqrt(variance_term)
        probability = float(NormalDist().cdf(statistic))
    return {
        "observed_sharpe": float(sr * np.sqrt(365.0)),
        "expected_max_sharpe": float(sr0 * np.sqrt(365.0)),
        "deflated_sharpe_probability": probability,
    }


def _stationary_bootstrap_indices(
    length: int,
    *,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return one stationary-bootstrap index path with geometric blocks."""
    if length <= 0:
        return np.empty(0, dtype=int)
    if block_length < 1:
        raise ValueError("block_length must be positive")
    p = 1.0 / float(block_length)
    indices = np.empty(length, dtype=int)
    position = 0
    while position < length:
        start = int(rng.integers(0, length))
        block = int(rng.geometric(p))
        block = min(block, length - position)
        for offset in range(block):
            indices[position + offset] = (start + offset) % length
        position += block
    return indices


def _reality_check(
    returns: pd.DataFrame,
    *,
    n_bootstrap: int,
    block_length: int,
    seed: int,
) -> dict[str, float]:
    """One-sided stationary-bootstrap Reality Check against a zero benchmark."""
    values = returns.to_numpy(dtype=float, copy=True)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 1:
        return {
            "observed_max_mean_daily": 0.0,
            "reality_check_p_value": 1.0,
            "bootstrap_count": float(n_bootstrap),
        }
    # Center each candidate under the null of zero mean.
    centered = values - np.nanmean(values, axis=0, keepdims=True)
    observed = float(np.nanmax(np.nanmean(values, axis=0)))
    rng = np.random.default_rng(seed)
    bootstrap_maxima = np.empty(n_bootstrap, dtype=float)
    for iteration in range(n_bootstrap):
        indices = _stationary_bootstrap_indices(
            values.shape[0],
            block_length=block_length,
            rng=rng,
        )
        bootstrap_means = np.nanmean(centered[indices, :], axis=0)
        bootstrap_maxima[iteration] = float(np.nanmax(bootstrap_means))
    p_value = float((np.sum(bootstrap_maxima >= observed) + 1.0) / (n_bootstrap + 1.0))
    return {
        "observed_max_mean_daily": observed,
        "reality_check_p_value": p_value,
        "bootstrap_count": float(n_bootstrap),
    }


def _block_sharpes(block: pd.DataFrame) -> pd.Series:
    mean = block.mean(axis=0)
    std = block.std(axis=0, ddof=1).replace(0.0, np.nan)
    return (mean / std).fillna(0.0)


def _pbo_cscv(returns: pd.DataFrame, *, n_blocks: int = 12) -> dict[str, float]:
    """Probability of backtest overfitting via CSCV."""
    if n_blocks < 4 or n_blocks % 2 != 0:
        raise ValueError("n_blocks must be an even integer >= 4")
    if len(returns) < n_blocks * 2:
        raise ValueError("Not enough observations for the requested CSCV block count")
    blocks = [frame for _, frame in returns.groupby(np.arange(len(returns)) // (len(returns) // n_blocks))]
    blocks = blocks[:n_blocks]
    if len(blocks) != n_blocks:
        raise ValueError("Could not construct the requested CSCV blocks")
    half = n_blocks // 2
    ranks: list[float] = []
    selected_counts: dict[str, int] = {column: 0 for column in returns.columns}
    for train_indices in combinations(range(n_blocks), half):
        train_set = set(train_indices)
        test_indices = [index for index in range(n_blocks) if index not in train_set]
        train = pd.concat([blocks[index] for index in train_indices], axis=0)
        test = pd.concat([blocks[index] for index in test_indices], axis=0)
        train_perf = _block_sharpes(train)
        test_perf = _block_sharpes(test)
        selected = str(train_perf.idxmax())
        selected_counts[selected] += 1
        # Percentile rank: 1.0 is best.  PBO counts selections that land in
        # the bottom half out of sample.
        percentile = float(test_perf.rank(pct=True).loc[selected])
        ranks.append(percentile)
    rank_array = np.asarray(ranks, dtype=float)
    return {
        "pbo": float(np.mean(rank_array <= 0.5)),
        "median_oos_percentile": float(np.median(rank_array)),
        "mean_oos_percentile": float(np.mean(rank_array)),
        "cscv_combinations": float(len(rank_array)),
        "most_selected_candidate": max(selected_counts, key=selected_counts.get),
        "most_selected_count": float(max(selected_counts.values())),
    }


def _write_report(
    output_dir: Path,
    *,
    best_candidate: str,
    candidate_table: pd.DataFrame,
    dsr: dict[str, float],
    reality: dict[str, float],
    pbo: dict[str, float],
) -> None:
    lines = [
        "# Phase-Momentum Multiple-Testing Diagnostics",
        "",
        "## Inputs",
        "",
        f"Best full-sample candidate by daily Sharpe: `{best_candidate}`.",
        f"Number of candidate trials: {len(candidate_table)}.",
        "All candidate returns are net of 20 bps total trading cost.",
        "",
        "## Candidate Sharpe dispersion",
        "",
        dataframe_to_markdown(candidate_table.sort_values("annualized_sharpe", ascending=False)),
        "",
        "## Deflated Sharpe Ratio",
        "",
        f"- Observed annualized Sharpe: {dsr['observed_sharpe']:.4f}",
        f"- Expected maximum Sharpe under the null: {dsr['expected_max_sharpe']:.4f}",
        f"- Deflated Sharpe probability: {dsr['deflated_sharpe_probability']:.4f}",
        "",
        "## White Reality Check",
        "",
        f"- Observed maximum mean daily return: {reality['observed_max_mean_daily']:.6f}",
        f"- Stationary-bootstrap p-value: {reality['reality_check_p_value']:.4f}",
        f"- Bootstrap count: {int(reality['bootstrap_count'])}",
        "",
        "## CSCV / PBO",
        "",
        f"- PBO: {pbo['pbo']:.4f}",
        f"- Median out-of-sample percentile of the in-sample winner: {pbo['median_oos_percentile']:.4f}",
        f"- Mean out-of-sample percentile of the in-sample winner: {pbo['mean_oos_percentile']:.4f}",
        f"- CSCV combinations: {int(pbo['cscv_combinations'])}",
        f"- Most frequently selected candidate: `{pbo['most_selected_candidate']}`",
        "",
        "## Interpretation",
        "",
        "- DSR probability is the probability that the observed Sharpe exceeds the",
        "  expected maximum Sharpe under the null after accounting for trial count.",
        "- The Reality Check p-value is one-sided for positive mean return; it does",
        "  not test whether the strategy beats BTC.",
        "- PBO is the fraction of CSCV splits where the in-sample winner lands in",
        "  the bottom half out of sample. Lower is better.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-returns",
        type=Path,
        default=Path("reports/phase_momentum_2022/parameter_returns.csv"),
    )
    parser.add_argument("--bootstrap-count", type=int, default=1000)
    parser.add_argument("--bootstrap-block-length", type=int, default=20)
    parser.add_argument("--cscv-blocks", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_multiple_testing_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    returns = pd.read_csv(args.candidate_returns, parse_dates=["date"]).set_index("date").sort_index()
    returns = returns.apply(pd.to_numeric, errors="coerce").dropna(how="all")
    if returns.empty:
        raise ValueError("Candidate returns are empty")
    trial_sharpes = returns.apply(_daily_sharpe)
    annualized_sharpes = trial_sharpes * np.sqrt(365.0)
    candidate_table = pd.DataFrame(
        {
            "candidate": returns.columns,
            "annualized_sharpe": annualized_sharpes.values,
            "mean_daily_return": returns.mean().values,
            "annualized_volatility": returns.std(ddof=1).values * np.sqrt(365.0),
        }
    )
    best_candidate = str(trial_sharpes.idxmax())
    best_returns = returns[best_candidate]
    dsr = _deflated_sharpe(
        best_returns,
        trial_count=len(returns.columns),
        trial_sharpes=trial_sharpes,
    )
    reality = _reality_check(
        returns,
        n_bootstrap=args.bootstrap_count,
        block_length=args.bootstrap_block_length,
        seed=args.seed,
    )
    pbo = _pbo_cscv(returns, n_blocks=args.cscv_blocks)

    output_dir = ensure_dir(args.output_dir)
    candidate_table.to_csv(output_dir / "candidate_sharpes.csv", index=False)
    pd.DataFrame([dsr]).to_csv(output_dir / "deflated_sharpe.csv", index=False)
    pd.DataFrame([reality]).to_csv(output_dir / "reality_check.csv", index=False)
    pd.DataFrame([pbo]).to_csv(output_dir / "pbo.csv", index=False)
    manifest = {
        "candidate_returns": str(args.candidate_returns),
        "candidate_count": len(returns.columns),
        "best_candidate": best_candidate,
        "bootstrap_count": args.bootstrap_count,
        "bootstrap_block_length": args.bootstrap_block_length,
        "cscv_blocks": args.cscv_blocks,
        "seed": args.seed,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_report(
        output_dir,
        best_candidate=best_candidate,
        candidate_table=candidate_table,
        dsr=dsr,
        reality=reality,
        pbo=pbo,
    )
    print(pd.DataFrame([{**{"best_candidate": best_candidate}, **dsr, **reality, **pbo}]).to_string(index=False))
    print(f"Wrote multiple-testing diagnostics to {output_dir}")


if __name__ == "__main__":
    main()
