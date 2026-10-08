"""Multiple-testing diagnostics for the phase-momentum champion.

Inputs are the 20 bps candidate return matrix written by
``scripts/run_phase_momentum_candidates.py`` and the research-history trial
summary ``reports/research_trial_inventory/summary.json`` written by
``scripts/build_trial_inventory.py``.

* Every statistic uses one common sample: a candidate or benchmark return that
  is missing or non-finite on any date stops the run.
* Candidates with identical daily returns (for example a 40% stop that never
  fires) are one trial, not several, and are dropped before any statistic.
* Deflated Sharpe Ratio (Bailey and Lopez de Prado, 2014) for the fixed
  primary strategy and for the best candidate, once with the family's own
  trial count and Sharpe dispersion and once per project-wide scope from the
  trial inventory.  The family count alone ignores every earlier strategy
  family the project tried before settling on this one.
* Stationary-bootstrap White Reality Check for the best candidate mean, both
  against zero and against BTC buy-and-hold, which is the project's hurdle.
* CSCV probability of backtest overfitting (Bailey, Borwein, Lopez de Prado
  and Zhu, 2015) with the paper's logit rule over blocks that use every row.

None of these statistics is used to choose a parameter.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
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

from atlas20.config import load_config  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.universe.builder import prepare_market_data  # noqa: E402

EULER_GAMMA = 0.5772156649015329


def _daily_sharpe(returns: pd.Series) -> float:
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 2 or float(clean.std(ddof=1)) <= 0.0:
        return 0.0
    return float(clean.mean() / clean.std(ddof=1))


def _expected_max_sharpe(trial_count: int, trial_sharpe_std: float) -> float:
    """Expected maximum Sharpe of ``trial_count`` null trials, in per-period units."""
    if trial_count <= 1 or trial_sharpe_std <= 0.0:
        return 0.0
    normal = NormalDist()
    z1 = normal.inv_cdf(1.0 - 1.0 / trial_count)
    z2 = normal.inv_cdf(1.0 - 1.0 / (trial_count * np.e))
    return float(trial_sharpe_std * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def _deflated_sharpe(returns: pd.Series, *, expected_max_sharpe: float) -> dict[str, float]:
    """Probability that the true Sharpe exceeds a per-period hurdle (DSR)."""
    clean = pd.to_numeric(returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 3:
        return {
            "observed_sharpe": 0.0,
            "expected_max_sharpe": 0.0,
            "deflated_sharpe_probability": 0.0,
        }
    sr = _daily_sharpe(clean)
    skew = float(clean.skew()) if clean.std(ddof=1) > 0.0 else 0.0
    # pandas reports excess kurtosis; the DSR variance term needs raw kurtosis.
    kurtosis = float(clean.kurtosis() + 3.0) if clean.std(ddof=1) > 0.0 else 3.0
    variance_term = 1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr * sr
    if variance_term <= 0.0:
        probability = 0.0
    else:
        statistic = (sr - expected_max_sharpe) * np.sqrt(max(len(clean) - 1, 1)) / np.sqrt(variance_term)
        probability = float(NormalDist().cdf(statistic))
    return {
        "observed_sharpe": float(sr * np.sqrt(365.0)),
        "expected_max_sharpe": float(expected_max_sharpe * np.sqrt(365.0)),
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
    """One-sided stationary-bootstrap Reality Check: is the best mean above zero?

    Pass excess returns over a benchmark to test against that benchmark.
    """
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


def _cscv_blocks(returns: pd.DataFrame, n_blocks: int) -> list[pd.DataFrame]:
    """Split every row into ``n_blocks`` contiguous blocks of near-equal size."""
    if n_blocks < 4 or n_blocks % 2 != 0:
        raise ValueError("n_blocks must be an even integer >= 4")
    if len(returns) < n_blocks * 2:
        raise ValueError("Not enough observations for the requested CSCV block count")
    return [returns.iloc[chunk] for chunk in np.array_split(np.arange(len(returns)), n_blocks)]


def _oos_logit(performance: pd.Series, selected: str) -> float:
    """Logit of the relative out-of-sample rank w = r / (N + 1).

    Rank 1 is the worst of N candidates.  A logit <= 0 means the in-sample
    winner landed at or below the out-of-sample median.
    """
    rank = float(performance.rank(ascending=True, method="average").loc[selected])
    relative = rank / (len(performance) + 1.0)
    return float(np.log(relative / (1.0 - relative)))


def _pbo_cscv(returns: pd.DataFrame, *, n_blocks: int = 12) -> tuple[dict[str, object], pd.DataFrame]:
    """Probability of backtest overfitting via CSCV."""
    blocks = _cscv_blocks(returns, n_blocks)
    half = n_blocks // 2
    rows: list[dict[str, object]] = []
    selected_counts: dict[str, int] = {str(column): 0 for column in returns.columns}
    for train_indices in combinations(range(n_blocks), half):
        train_set = set(train_indices)
        test_indices = [index for index in range(n_blocks) if index not in train_set]
        train = pd.concat([blocks[index] for index in train_indices], axis=0)
        test = pd.concat([blocks[index] for index in test_indices], axis=0)
        selected = str(_block_sharpes(train).idxmax())
        selected_counts[selected] += 1
        rows.append(
            {
                "train_blocks": "-".join(str(index) for index in train_indices),
                "selected_candidate": selected,
                "oos_logit": _oos_logit(_block_sharpes(test), selected),
            }
        )
    splits = pd.DataFrame(rows)
    logits = splits["oos_logit"].to_numpy(dtype=float)
    summary: dict[str, object] = {
        "pbo": float(np.mean(logits <= 0.0)),
        "median_oos_logit": float(np.median(logits)),
        "cscv_combinations": int(len(logits)),
        "rows_used": int(sum(len(block) for block in blocks)),
        "most_selected_candidate": max(selected_counts, key=lambda name: selected_counts[name]),
        "most_selected_count": int(max(selected_counts.values())),
    }
    return summary, splits


def _dedupe_identical_columns(returns: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Keep the first of any candidates whose daily returns are identical."""
    kept: list[str] = []
    duplicates: dict[str, str] = {}
    for column in returns.columns:
        series = returns[column].to_numpy()
        match = next(
            (existing for existing in kept if np.array_equal(series, returns[existing].to_numpy())),
            None,
        )
        if match is None:
            kept.append(str(column))
        else:
            duplicates[str(column)] = match
    return returns[kept], duplicates


def _require_common_sample(returns: pd.DataFrame) -> pd.DataFrame:
    """Every candidate must be measured on the same days.

    The Sharpe and bootstrap helpers drop missing and infinite values per
    candidate, so a gap in one column would quietly compare candidates over
    different windows.  Refuse such a matrix instead of shrinking one sample.
    """
    values = returns.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    bad = ~np.isfinite(values)
    if bad.any():
        raise ValueError(
            f"candidate returns have {int(bad.sum())} missing or non-finite value(s) on "
            f"{int(bad.any(axis=1).sum())} date(s); every candidate must cover the same days"
        )
    return returns


def _load_candidate_returns(path: Path) -> pd.DataFrame:
    """Candidate daily returns indexed by date, on one common sample of days."""
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame.pop("date"), errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{path}: {int(dates.isna().sum())} row(s) have no parseable date")
    returns = frame.set_axis(pd.DatetimeIndex(dates, name="date"), axis=0).sort_index()
    duplicated = returns.index.duplicated()
    if duplicated.any():
        days = sorted({str(day.date()) for day in returns.index[duplicated]})
        raise ValueError(f"{path}: duplicate date(s) {days[:5]}")
    return _require_common_sample(returns.apply(pd.to_numeric, errors="coerce"))


def _excess_over(returns: pd.DataFrame, benchmark: pd.Series) -> pd.DataFrame:
    aligned = pd.to_numeric(benchmark, errors="coerce").reindex(returns.index)
    bad = ~np.isfinite(aligned.to_numpy(dtype=float))
    if bad.any():
        raise ValueError(
            f"benchmark returns are missing or non-finite on {int(bad.sum())} candidate date(s)"
        )
    return returns.sub(aligned, axis=0)


def _load_btc_returns(config_path: str, index: pd.DatetimeIndex) -> pd.Series:
    config = load_config(config_path).model_copy(deep=True)
    processed_dir = config.resolve_path(config.paths.processed_dir)
    panel = pd.read_csv(processed_dir / "panel_daily.csv")
    metadata = pd.read_csv(processed_dir / "metadata.csv").set_index("coin_id")
    market = prepare_market_data(panel, metadata, config)
    return market.returns["bitcoin"].reindex(index)


PROJECT_SCOPES = ("top20_2022_trials", "all_trials")
COMPARABLE_SCOPE = "top20_2022_trials"


def _project_scopes(summary_path: Path) -> list[tuple[str, int, float]]:
    """(scope, trial count, per-period Sharpe std) for each project-wide scope.

    ``summary.json`` comes from ``scripts/build_trial_inventory.py``.  Each
    scope contributes its own trial count, but the Sharpe dispersion always
    comes from the comparable pool (Top20, 2022-01-01 start, cost nearest
    20 bps): trials on other windows and universes are not on the same
    footing and would inflate the dispersion.
    """
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    comparable = summary[COMPARABLE_SCOPE]
    periods = comparable.get("periods_per_year")
    if periods != 365:
        raise ValueError(
            f"trial summary Sharpe ratios must be daily and annualized with 365 periods, got {periods!r}"
        )
    sharpe_std = float(comparable["sharpe_std_per_period"])
    scopes: list[tuple[str, int, float]] = []
    for scope in PROJECT_SCOPES:
        count = int(summary[scope]["n_trials"])
        if count < 2 or not np.isfinite(sharpe_std) or sharpe_std <= 0.0:
            raise ValueError(f"trial inventory scope {scope!r} has too few trials or no Sharpe dispersion")
        scopes.append((scope, count, sharpe_std))
    return scopes


def _write_report(
    output_dir: Path,
    *,
    candidate_table: pd.DataFrame,
    duplicates: dict[str, str],
    dsr: pd.DataFrame,
    reality: pd.DataFrame,
    pbo: dict[str, object],
    sample: dict[str, object],
    trial_summary: Path,
) -> None:
    duplicate_lines = (
        [f"- `{name}` is identical to `{kept}`" for name, kept in duplicates.items()]
        if duplicates
        else ["- none"]
    )
    lines = [
        "# Phase-Momentum Multiple-Testing Diagnostics",
        "",
        "All candidate returns are net of 20 bps total trading cost. Every statistic uses the",
        f"same {sample['rows']} days ({sample['start']} to {sample['end']}); a candidate or benchmark",
        "with a missing or non-finite day stops the run instead of being measured on fewer days.",
        "",
        "## Identical candidates counted once",
        "",
        *duplicate_lines,
        "",
        "## Candidate Sharpe dispersion",
        "",
        dataframe_to_markdown(candidate_table.sort_values("annualized_sharpe", ascending=False)),
        "",
        "## Deflated Sharpe Ratio",
        "",
        "`family` uses only the unique phase-momentum candidates and their own Sharpe",
        f"dispersion. The project scopes come from `{trial_summary}`:",
        "`top20_2022_trials` counts every configuration the project backtested on Top20 from",
        "2022-01-01, the comparable pool the champion was selected from; `all_trials` counts every",
        "configuration on any window or universe. Both use the Sharpe dispersion of the",
        "Top20/2022 pool, because Sharpe ratios on other windows are not comparable. A",
        "probability above 0.95 passes.",
        "",
        dataframe_to_markdown(dsr),
        "",
        "## White Reality Check",
        "",
        "One-sided stationary bootstrap for the best candidate mean. Against BTC the test",
        "uses daily excess returns over BTC buy-and-hold. It covers only this family's",
        "return series; earlier families kept no daily returns, so their selection is",
        "priced by the project-scope Deflated Sharpe instead.",
        "",
        dataframe_to_markdown(reality),
        "",
        "## CSCV / PBO",
        "",
        f"- PBO: {pbo['pbo']:.4f} (logit rule, lower is better)",
        f"- Median out-of-sample logit of the in-sample winner: {pbo['median_oos_logit']:.4f}",
        f"- CSCV combinations: {pbo['cscv_combinations']}; rows used: {pbo['rows_used']}",
        f"- Most frequently selected candidate: `{pbo['most_selected_candidate']}`",
        "",
        "PBO judges the procedure \"pick the best full-sample candidate\". The fixed primary",
        "was itself chosen with the full sample in view, so a PBO above 0.5 is evidence",
        "against trusting the family's in-sample ranking, including the primary's place in it.",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--candidate-returns",
        type=Path,
        default=Path("reports/phase_momentum_multiple_testing_2022/candidate_returns.csv"),
    )
    parser.add_argument("--primary", default="primary")
    parser.add_argument(
        "--trial-summary",
        type=Path,
        default=Path("reports/research_trial_inventory/summary.json"),
        help="summary.json written by scripts/build_trial_inventory.py",
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
    returns = _load_candidate_returns(args.candidate_returns)
    if args.primary not in returns.columns:
        raise ValueError(f"primary candidate {args.primary!r} is not in the candidate returns")
    unique, duplicates = _dedupe_identical_columns(returns)
    sample: dict[str, object] = {
        "rows": int(len(unique)),
        "start": str(pd.Timestamp(unique.index.min()).date()),
        "end": str(pd.Timestamp(unique.index.max()).date()),
        "rule": "every candidate and the BTC benchmark have a finite return on every date; otherwise the run stops",
    }

    trial_sharpes = unique.apply(_daily_sharpe)
    candidate_table = pd.DataFrame(
        {
            "candidate": unique.columns,
            "annualized_sharpe": (trial_sharpes * np.sqrt(365.0)).values,
            "mean_daily_return": unique.mean().values,
            "annualized_volatility": unique.std(ddof=1).values * np.sqrt(365.0),
        }
    )
    best_candidate = str(trial_sharpes.idxmax())
    scopes = [("family", len(unique.columns), float(trial_sharpes.std(ddof=1)))]
    scopes += _project_scopes(args.trial_summary)
    dsr_rows: list[dict[str, object]] = []
    for candidate in dict.fromkeys([args.primary, best_candidate]):
        for scope, count, sharpe_std in scopes:
            dsr_rows.append(
                {
                    "candidate": candidate,
                    "scope": scope,
                    "trial_count": count,
                    "trial_sharpe_std_annualized": sharpe_std * np.sqrt(365.0),
                    **_deflated_sharpe(
                        unique[candidate],
                        expected_max_sharpe=_expected_max_sharpe(count, sharpe_std),
                    ),
                }
            )
    dsr = pd.DataFrame(dsr_rows)

    btc = _load_btc_returns(args.config, pd.DatetimeIndex(unique.index))
    reality = pd.DataFrame(
        [
            {
                "benchmark": benchmark,
                **_reality_check(
                    frame,
                    n_bootstrap=args.bootstrap_count,
                    block_length=args.bootstrap_block_length,
                    seed=args.seed,
                ),
            }
            for benchmark, frame in (
                ("zero", unique),
                ("BTC buy-and-hold", _excess_over(unique, btc)),
            )
        ]
    )
    pbo, splits = _pbo_cscv(unique, n_blocks=args.cscv_blocks)

    output_dir = ensure_dir(args.output_dir)
    candidate_table.to_csv(output_dir / "candidate_sharpes.csv", index=False)
    dsr.to_csv(output_dir / "deflated_sharpe.csv", index=False)
    reality.to_csv(output_dir / "reality_check.csv", index=False)
    pd.DataFrame([pbo]).to_csv(output_dir / "pbo.csv", index=False)
    splits.to_csv(output_dir / "cscv_splits.csv", index=False)
    manifest = {
        "candidate_returns": str(args.candidate_returns),
        "candidate_count": int(len(returns.columns)),
        "unique_candidate_count": int(len(unique.columns)),
        "identical_candidates": duplicates,
        "common_sample": sample,
        "primary": args.primary,
        "best_candidate": best_candidate,
        "trial_summary": str(args.trial_summary),
        "trial_summary_sha256": hashlib.sha256(args.trial_summary.read_bytes()).hexdigest(),
        "trial_scopes": [
            {
                "scope": scope,
                "trial_count": count,
                "trial_sharpe_std_per_period": sharpe_std,
                "trial_sharpe_std_annualized": sharpe_std * np.sqrt(365.0),
                "sharpe_std_source": "family candidates" if scope == "family" else COMPARABLE_SCOPE,
            }
            for scope, count, sharpe_std in scopes
        ],
        "bootstrap_count": args.bootstrap_count,
        "bootstrap_block_length": args.bootstrap_block_length,
        "cscv_blocks": args.cscv_blocks,
        "seed": args.seed,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_report(
        output_dir,
        candidate_table=candidate_table,
        duplicates=duplicates,
        dsr=dsr,
        reality=reality,
        pbo=pbo,
        sample=sample,
        trial_summary=args.trial_summary,
    )
    print(dsr.to_string(index=False))
    print(reality.to_string(index=False))
    print(pd.DataFrame([pbo]).to_string(index=False))
    print(f"Wrote multiple-testing diagnostics to {output_dir}")


if __name__ == "__main__":
    main()
