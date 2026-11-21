"""Monte Carlo path audit for a frozen derivatives return series.

This is a conditional path diagnostic, not new out-of-sample evidence and not
a parameter search.  It resamples *daily returns in stationary blocks* from one
already-produced live-parity series, preserving short-range serial dependence
while destroying the original calendar order.  Because the series is fixed,
the resulting distribution describes path risk conditional on the strategy's
realized return distribution; it cannot validate alpha selection.

The primary report uses block lengths 5, 20, 40 and 80 and 10,000 fixed-seed
draws per block length.  For every path it recomputes terminal multiple, CAGR,
Sharpe and maximum drawdown from the path itself.  It also reports the
probability of terminal wealth below 1, a drawdown worse than 50%, negative
Sharpe, and a 2x terminal target miss.  An optional paired BTC path uses the
same resampled indices on both series and reports terminal-multiple ratios.

Inputs are CSV files with ``daily_return`` and ideally a date-like first column.
The output directory must be absent.  No network, open orders or execution state
are touched.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas20.logging_utils import ensure_dir  # noqa: E402


def _stationary_indices(
    length: int,
    *,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """One circular stationary-bootstrap index path with geometric blocks."""

    if length <= 0:
        raise ValueError("return length must be positive")
    if block_length < 1:
        raise ValueError("block_length must be positive")
    probability = 1.0 / float(block_length)
    indices = np.empty(length, dtype=np.int64)
    position = 0
    while position < length:
        start = int(rng.integers(0, length))
        block = min(int(rng.geometric(probability)), length - position)
        offsets = np.arange(block, dtype=np.int64)
        indices[position : position + block] = (start + offsets) % length
        position += block
    return indices


def _load_returns(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    if "daily_return" not in frame.columns:
        raise ValueError(f"{path}: missing daily_return column")
    values = pd.to_numeric(frame["daily_return"], errors="coerce")
    if values.isna().any():
        raise ValueError(f"{path}: daily_return contains missing/non-numeric values")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError(f"{path}: daily_return contains non-finite values")
    dates = pd.to_datetime(frame.iloc[:, 0], utc=True, errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{path}: first column is not a complete date index")
    series = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates))
    return series.sort_index()


def _path_metrics(returns: np.ndarray) -> tuple[float, float, float, float]:
    """Terminal multiple, CAGR, Sharpe and MDD for one daily-return path."""

    clean = np.asarray(returns, dtype=float)
    if clean.ndim != 1 or clean.size == 0:
        raise ValueError("path returns must be a non-empty 1D array")
    if not np.isfinite(clean).all():
        raise ValueError("path returns must be finite")
    if np.any(clean <= -1.0):
        raise ValueError("path contains a return at or below -100%")
    wealth = np.cumprod(1.0 + clean)
    terminal = float(wealth[-1])
    cagr = float(terminal ** (365.0 / clean.size) - 1.0) if terminal > 0.0 else -1.0
    volatility = float(np.std(clean, ddof=0) * math.sqrt(365.0))
    sharpe = float(np.mean(clean) * 365.0 / volatility) if volatility > 0.0 else 0.0
    peaks = np.maximum.accumulate(np.concatenate(([1.0], wealth)))
    drawdown = wealth / peaks[1:] - 1.0
    return terminal, cagr, sharpe, float(np.min(drawdown))


def _simulate(
    returns: pd.Series,
    *,
    block_length: int,
    draws: int,
    seed: int,
) -> pd.DataFrame:
    values = returns.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    rows = np.empty((draws, 4), dtype=float)
    for draw in range(draws):
        indices = _stationary_indices(
            len(values), block_length=block_length, rng=rng
        )
        rows[draw] = _path_metrics(values[indices])
    return pd.DataFrame(
        rows,
        columns=("terminal_multiple", "cagr", "sharpe", "max_drawdown"),
    )


def _quantiles(frame: pd.DataFrame) -> dict[str, float]:
    result: dict[str, float] = {}
    for column in frame.columns:
        values = frame[column].to_numpy(dtype=float)
        for q in (0.01, 0.05, 0.50, 0.95, 0.99):
            result[f"{column}_p{int(q * 100):02d}"] = float(np.quantile(values, q))
    return result


def _summary(
    simulation: pd.DataFrame,
    *,
    block_length: int,
    draws: int,
    seed: int,
) -> dict[str, object]:
    terminal = simulation["terminal_multiple"]
    drawdown = simulation["max_drawdown"]
    sharpe = simulation["sharpe"]
    return {
        "block_length_days": int(block_length),
        "draws": int(draws),
        "seed": int(seed),
        "terminal_multiple": {
            **_quantiles(simulation[["terminal_multiple"]]),
            "probability_below_1": float((terminal < 1.0).mean()),
            "probability_below_2x": float((terminal < 2.0).mean()),
        },
        "cagr": _quantiles(simulation[["cagr"]]),
        "sharpe": {
            **_quantiles(simulation[["sharpe"]]),
            "probability_negative": float((sharpe < 0.0).mean()),
        },
        "max_drawdown": {
            **_quantiles(simulation[["max_drawdown"]]),
            "probability_worse_than_50pct": float((drawdown < -0.50).mean()),
            "probability_worse_than_60pct": float((drawdown < -0.60).mean()),
        },
    }


def _paired_vs_benchmark(
    candidate: pd.Series,
    benchmark: pd.Series,
    *,
    block_length: int,
    draws: int,
    seed: int,
) -> dict[str, object]:
    aligned = pd.concat([candidate.rename("candidate"), benchmark.rename("benchmark")], axis=1)
    if aligned.isna().any().any():
        raise ValueError("paired benchmark comparison requires identical complete dates")
    values = aligned.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    ratios = np.empty(draws, dtype=float)
    for draw in range(draws):
        indices = _stationary_indices(len(values), block_length=block_length, rng=rng)
        sample = values[indices]
        candidate_terminal = float(np.prod(1.0 + sample[:, 0]))
        benchmark_terminal = float(np.prod(1.0 + sample[:, 1]))
        ratios[draw] = candidate_terminal / benchmark_terminal
    return {
        "block_length_days": int(block_length),
        "draws": int(draws),
        "seed": int(seed),
        "observed_terminal_ratio": float(
            np.prod(1.0 + values[:, 0]) / np.prod(1.0 + values[:, 1])
        ),
        "terminal_ratio_p01": float(np.quantile(ratios, 0.01)),
        "terminal_ratio_p05": float(np.quantile(ratios, 0.05)),
        "terminal_ratio_p50": float(np.quantile(ratios, 0.50)),
        "terminal_ratio_p95": float(np.quantile(ratios, 0.95)),
        "terminal_ratio_p99": float(np.quantile(ratios, 0.99)),
        "probability_ratio_below_1": float((ratios < 1.0).mean()),
    }


def _markdown(summary: dict[str, object]) -> str:
    lines = [
        "# Atlas20 derivatives conditional Monte Carlo path audit",
        "",
        "> Conditional stationary-block bootstrap of already-produced daily returns.",
        "> This is not a new OOS run, not a parameter choice, and not a guarantee of future returns.",
        "",
        f"- source: `{Path(str(summary['source'])).name}`",
        f"- sample: {summary['sample_start']} → {summary['sample_end']} ({summary['observations']} daily returns)",
        f"- primary draws: {summary['draws']} per block length",
        f"- block lengths (days): {', '.join(str(v) for v in summary['block_lengths'])}",
        f"- seed: {summary['seed']}",
        f"- observed terminal multiple: {summary['observed']['multiple']:.6g}x",
        f"- observed Sharpe: {summary['observed']['sharpe']:.4f}",
        f"- observed maximum drawdown: {summary['observed']['max_drawdown']:.4%}",
        "",
        "## Path distribution",
        "",
        "| block | terminal p01 | p05 | p50 | p95 | p99 | P(<1x) | P(<2x) | Sharpe p05 | Sharpe p50 | P(Sharpe<0) | MDD p05 | MDD p50 | P(MDD<-50%) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["by_block"]:
        t = row["terminal_multiple"]
        s = row["sharpe"]
        d = row["max_drawdown"]
        lines.append(
            "| {b} | {t1:.4g}x | {t5:.4g}x | {t50:.4g}x | {t95:.4g}x | {t99:.4g}x | "
            "{p1:.2%} | {p2:.2%} | {s5:.3f} | {s50:.3f} | {ps:.2%} | "
            "{d5:.2%} | {d50:.2%} | {pd:.2%} |".format(
                b=row["block_length_days"],
                t1=t["terminal_multiple_p01"],
                t5=t["terminal_multiple_p05"],
                t50=t["terminal_multiple_p50"],
                t95=t["terminal_multiple_p95"],
                t99=t["terminal_multiple_p99"],
                p1=t["probability_below_1"],
                p2=t["probability_below_2x"],
                s5=s["sharpe_p05"],
                s50=s["sharpe_p50"],
                ps=s["probability_negative"],
                d5=d["max_drawdown_p05"],
                d50=d["max_drawdown_p50"],
                pd=d["probability_worse_than_50pct"],
            )
        )
    paired = summary.get("paired_benchmark")
    lines.extend(["", "## Paired benchmark", ""])
    if paired is None:
        lines.append("_No complete paired benchmark series was supplied._")
    else:
        lines.append(
            "- benchmark: `"
            + Path(str(paired["benchmark_source"])).name
            + "`; same resampled daily indices as the candidate"
        )
        lines.append("")
        lines.append("| block | observed ratio | p05 | p50 | p95 | P(ratio<1) |")
        lines.append("|---:|---:|---:|---:|---:|---:|")
        for row in paired["by_block"]:
            lines.append(
                f"| {row['block_length_days']} | {row['observed_terminal_ratio']:.4g}x | "
                f"{row['terminal_ratio_p05']:.4g}x | {row['terminal_ratio_p50']:.4g}x | "
                f"{row['terminal_ratio_p95']:.4g}x | {row['probability_ratio_below_1']:.2%} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Blocks preserve short-range autocorrelation but destroy longer calendar regimes and event clustering.",
            "- The input is a single realized path; bootstrap uncertainty is not selection-bias correction.",
            "- Four block lengths (5/20/40/80) probe short-range dependence; they are not a complete model of regime shifts.",
            "- A terminal below 1x in the tail is a path-risk warning, not a claim that the live account will hit it.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--returns", type=Path, required=True)
    parser.add_argument("--benchmark-returns", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=10_000)
    parser.add_argument("--block-lengths", default="5,20,40,80")
    parser.add_argument("--seed", type=int, default=20261121)
    args = parser.parse_args(argv)

    if args.draws < 100:
        parser.error("--draws must be at least 100")
    if args.output_dir.exists():
        parser.error(f"output directory already exists: {args.output_dir}")
    block_lengths = tuple(int(item.strip()) for item in args.block_lengths.split(",") if item.strip())
    if not block_lengths or any(value < 1 for value in block_lengths):
        parser.error("--block-lengths must be positive integers")

    returns = _load_returns(args.returns)
    observed = _path_metrics(returns.to_numpy(dtype=float))
    by_block: list[dict[str, object]] = []
    details: dict[int, pd.DataFrame] = {}
    for block in block_lengths:
        simulation = _simulate(
            returns,
            block_length=block,
            draws=args.draws,
            seed=args.seed + block,
        )
        details[block] = simulation
        by_block.append(
            _summary(simulation, block_length=block, draws=args.draws, seed=args.seed + block)
        )

    paired: dict[str, object] | None = None
    if args.benchmark_returns is not None:
        benchmark = _load_returns(args.benchmark_returns)
        aligned_candidate, aligned_benchmark = returns.align(benchmark, join="inner")
        if aligned_candidate.isna().any() or aligned_benchmark.isna().any():
            raise ValueError("benchmark and candidate dates do not fully overlap")
        paired_rows = [
            _paired_vs_benchmark(
                aligned_candidate,
                aligned_benchmark,
                block_length=block,
                draws=args.draws,
                seed=args.seed + 10_000 + block,
            )
            for block in block_lengths
        ]
        paired = {
            "benchmark_source": str(args.benchmark_returns),
            "dates": int(len(aligned_candidate)),
            "by_block": paired_rows,
        }

    summary: dict[str, object] = {
        "source": str(args.returns),
        "sample_start": str(returns.index.min()),
        "sample_end": str(returns.index.max()),
        "observations": int(len(returns)),
        "draws": int(args.draws),
        "block_lengths": list(block_lengths),
        "seed": int(args.seed),
        "observed": {
            "multiple": observed[0],
            "cagr": observed[1],
            "sharpe": observed[2],
            "max_drawdown": observed[3],
        },
        "by_block": by_block,
        "paired_benchmark": paired,
    }
    output = ensure_dir(args.output_dir)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(_markdown(summary) + "\n", encoding="utf-8")
    for block, simulation in details.items():
        simulation.to_csv(output / f"paths_block_{block}.csv", index=False)
    print(
        json.dumps(
            {
                "output": str(output),
                "observations": len(returns),
                "draws_per_block": args.draws,
                "blocks": list(block_lengths),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
