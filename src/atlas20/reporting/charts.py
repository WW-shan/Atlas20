"""Matplotlib chart helpers for Atlas20 reports."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from atlas20.analytics.metrics import rolling_return_series
from atlas20.backtest.engine import BacktestResult


plt.style.use("seaborn-v0_8-darkgrid")



def _select_results(results: dict[str, BacktestResult], selected: list[str]) -> dict[str, BacktestResult]:
    if not selected:
        return results
    return {name: result for name, result in results.items() if name in selected}



def plot_equity_curves(results: dict[str, BacktestResult], output_path: Path, selected: list[str] | None = None) -> None:
    """Plot normalized equity curves for selected strategies."""
    chosen = _select_results(results, selected or [])
    fig, ax = plt.subplots(figsize=(13, 7))
    for name, result in chosen.items():
        normalized = result.equity_curve / result.equity_curve.iloc[0]
        ax.plot(normalized.index, normalized.values, label=name, linewidth=1.8)
    ax.set_title("Atlas20 Strategy Equity Curves")
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)



def plot_drawdowns(results: dict[str, BacktestResult], output_path: Path, selected: list[str] | None = None) -> None:
    """Plot drawdown curves for selected strategies."""
    chosen = _select_results(results, selected or [])
    fig, ax = plt.subplots(figsize=(13, 7))
    for name, result in chosen.items():
        ax.plot(result.drawdown.index, result.drawdown.values, label=name, linewidth=1.6)
    ax.set_title("Atlas20 Strategy Drawdowns")
    ax.set_ylabel("Drawdown")
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)



def plot_rolling_returns(
    results: dict[str, BacktestResult],
    output_path: Path,
    window_days: int,
    selected: list[str] | None = None,
) -> None:
    """Plot rolling 12-month compounded returns for selected strategies."""
    chosen = _select_results(results, selected or [])
    fig, ax = plt.subplots(figsize=(13, 7))
    for name, result in chosen.items():
        rolling = rolling_return_series(result, window_days)
        ax.plot(rolling.index, rolling.values, label=name, linewidth=1.6)
    ax.set_title(f"Rolling {window_days}-Day Returns")
    ax.set_ylabel("Rolling Return")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)



def plot_sector_exposure(sector_exposure: pd.DataFrame, output_path: Path, title: str) -> None:
    """Plot stacked area sector exposure over time."""
    fig, ax = plt.subplots(figsize=(13, 7))
    sector_exposure = sector_exposure.fillna(0.0)
    ax.stackplot(sector_exposure.index, sector_exposure.T.values, labels=sector_exposure.columns)
    ax.set_title(title)
    ax.set_ylabel("Weight")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
