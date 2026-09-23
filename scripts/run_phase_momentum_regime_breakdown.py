"""Market-regime breakdown for the phase-momentum champion.

The project's regime frame is defined in ``config/base.yaml``.  This script
does not change the strategy or select parameters; it only slices the already
saved production returns into bull and non-bull states for the required
regime-robustness audit.
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
from atlas20.signals.regime import build_regime_frame  # noqa: E402

from scripts.run_phase_momentum import _load_market  # noqa: E402


def _regime_metrics(returns: pd.Series, mask: pd.Series) -> dict[str, float | int]:
    clean = (
        pd.to_numeric(returns, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .reindex(mask.index)
    )
    subset = clean[mask.fillna(False).astype(bool)].dropna()
    if subset.empty:
        return {
            "days": 0,
            "total_multiple": 1.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }
    equity = (1.0 + subset).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    total_multiple = float(equity.iloc[-1])
    annualized_volatility = float(subset.std(ddof=0) * np.sqrt(365.0))
    sharpe = (
        float(subset.mean() * 365.0 / annualized_volatility)
        if annualized_volatility > 0.0
        else 0.0
    )
    return {
        "days": int(len(subset)),
        "total_multiple": total_multiple,
        "annualized_return": float(total_multiple ** (365.0 / len(subset)) - 1.0),
        "annualized_volatility": annualized_volatility,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
    }


def _regime_table(
    returns_by_strategy: dict[str, pd.Series],
    bull: pd.Series,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    bull_mask = bull.fillna(False).astype(bool)
    for strategy, returns in returns_by_strategy.items():
        aligned = pd.to_numeric(returns, errors="coerce").reindex(bull_mask.index)
        for regime, mask in {
            "bull": bull_mask,
            "non_bull": ~bull_mask,
        }.items():
            rows.append(
                {
                    "strategy": strategy,
                    "regime": regime,
                    **_regime_metrics(aligned, mask),
                }
            )
    return pd.DataFrame(rows)


def _validate_returns(returns: pd.Series, label: str) -> None:
    numeric = pd.to_numeric(returns, errors="coerce")
    bad = int((~np.isfinite(numeric)).sum())
    if bad:
        raise ValueError(f"{label} contains {bad} non-finite or missing return(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--returns-file",
        type=Path,
        default=Path("reports/phase_momentum_multiple_testing_2022/candidate_returns.csv"),
    )
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--candidates", default="primary,parameter_ensemble_20bps")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_regime_2022"),
    )
    args = parser.parse_args()

    configure_logging("ERROR")
    returns_frame = pd.read_csv(args.returns_file, parse_dates=["date"]).set_index("date").sort_index()
    candidates = [item.strip() for item in args.candidates.split(",") if item.strip()]
    missing = [candidate for candidate in candidates if candidate not in returns_frame.columns]
    if missing:
        raise ValueError(f"Missing candidates in returns file: {missing}")

    config, market, _universe, _index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    regime_frame = build_regime_frame(market.price, market.market_cap, config)
    returns_frame = returns_frame.loc[
        (returns_frame.index >= pd.Timestamp(args.start_date))
        & (returns_frame.index <= pd.Timestamp(args.end_date))
    ]
    regime_bull = regime_frame["bull"].reindex(returns_frame.index)
    missing_regime = regime_bull.isna()
    if missing_regime.any():
        raise ValueError(
            f"regime frame is missing {int(missing_regime.sum())} date(s) in the return window"
        )
    bull = regime_bull.astype(bool)
    returns_by_strategy: dict[str, pd.Series] = {}
    for candidate in candidates:
        series = returns_frame[candidate]
        _validate_returns(series, candidate)
        returns_by_strategy[candidate] = series
    btc = market.returns["bitcoin"].reindex(returns_frame.index)
    _validate_returns(btc, "BTC benchmark")
    returns_by_strategy["BTC"] = btc

    summary = _regime_table(returns_by_strategy, bull)
    output_dir = ensure_dir(args.output_dir)
    summary.to_csv(output_dir / "summary.csv", index=False)
    manifest = {
        "config": args.config,
        "returns_file": str(args.returns_file),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "candidates": candidates,
        "benchmark": "BTC buy-and-hold",
        "regime_definition": config.regime.model_dump(mode="json"),
        "bull_days": int(bull.sum()),
        "non_bull_days": int((~bull).sum()),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = "\n".join(
        [
            "# Phase-Momentum Market Regime Breakdown",
            "",
            "The bull/non-bull split uses the project regime frame from `config/base.yaml`:",
            f"- BTC {config.regime.btc_ma_window}D moving-average state",
            f"- tracked total market-cap {config.regime.tracked_total_mcap_ma_window}D moving-average state",
            f"- combine method: `{config.regime.combine_method}`",
            "",
            f"Bull days: {int(bull.sum())}; non-bull days: {int((~bull).sum())}.",
            "",
            "## Summary",
            "",
            dataframe_to_markdown(summary),
            "",
            "This is a diagnostic slice of the same saved production returns. It does",
            "not select a new parameter and it does not repair capacity, execution, or",
            "data-quality risks.",
            "",
        ]
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Wrote regime breakdown to {output_dir}")


if __name__ == "__main__":
    main()
