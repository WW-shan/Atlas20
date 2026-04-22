"""Performance analytics for Atlas20 backtests."""

from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd

from atlas20.backtest.engine import BacktestResult



def _safe_series(series: pd.Series) -> pd.Series:
    return series.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)



def compute_summary_metrics(result: BacktestResult, annualization_days: int = 365) -> dict[str, float]:
    """Compute core performance metrics for one backtest."""
    returns = _safe_series(result.daily_returns)
    equity = result.equity_curve.astype(float)
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0 if len(equity) > 1 and equity.iloc[0] != 0 else 0.0
    periods = max(len(returns), 1)
    cagr = (1.0 + returns).prod() ** (annualization_days / periods) - 1.0
    vol = returns.std(ddof=0) * sqrt(annualization_days)
    downside_std = returns.where(returns < 0, 0.0).std(ddof=0) * sqrt(annualization_days)
    sharpe = (returns.mean() * annualization_days / vol) if vol > 0 else 0.0
    sortino = (returns.mean() * annualization_days / downside_std) if downside_std > 0 else 0.0
    max_drawdown = float(result.drawdown.min()) if not result.drawdown.empty else 0.0
    calmar = (cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0
    monthly_returns = (1.0 + returns).resample("ME").prod() - 1.0
    monthly_win_rate = float((monthly_returns > 0).mean()) if not monthly_returns.empty else 0.0
    annualized_turnover = float(result.turnover.sum() * annualization_days / periods)
    avg_turnover = float(result.turnover[result.turnover > 0].mean()) if (result.turnover > 0).any() else 0.0
    avg_holdings = float(result.holdings_count.mean()) if not result.holdings_count.empty else 0.0

    return {
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "monthly_win_rate": monthly_win_rate,
        "annualized_turnover": annualized_turnover,
        "avg_turnover_per_rebalance": avg_turnover,
        "average_holdings": avg_holdings,
    }



def summarize_backtests(results: dict[str, BacktestResult], annualization_days: int = 365) -> pd.DataFrame:
    """Create a summary table for many backtest results."""
    rows = []
    for name, result in results.items():
        metrics = compute_summary_metrics(result, annualization_days)
        metrics["strategy"] = name
        rows.append(metrics)
    summary = pd.DataFrame(rows).set_index("strategy").sort_values(["sharpe", "cagr"], ascending=False)
    return summary



def yearly_return_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    """Build a calendar-year return table for all strategies."""
    data = {
        name: ((1.0 + _safe_series(result.daily_returns)).resample("YE").prod() - 1.0)
        for name, result in results.items()
    }
    frame = pd.DataFrame(data)
    frame.index = frame.index.year
    return frame.sort_index()



def rolling_return_series(result: BacktestResult, window_days: int) -> pd.Series:
    """Return a rolling compounded return series."""
    returns = _safe_series(result.daily_returns)
    return (1.0 + returns).rolling(window_days).apply(np.prod, raw=True) - 1.0



def performance_by_regime(results: dict[str, BacktestResult], regime_frame: pd.DataFrame, annualization_days: int = 365) -> pd.DataFrame:
    """Summarize strategy performance inside bull and non-bull states."""
    rows = []
    bull_state = regime_frame["bull"].reindex(next(iter(results.values())).daily_returns.index).fillna(False)
    for name, result in results.items():
        returns = _safe_series(result.daily_returns)
        for label, mask in {"bull": bull_state, "non_bull": ~bull_state}.items():
            subset = returns[mask]
            if subset.empty:
                row = {"strategy": name, "regime": label, "annualized_return": 0.0, "annualized_volatility": 0.0, "sharpe": 0.0, "days": 0}
            else:
                ann_return = (1.0 + subset).prod() ** (annualization_days / len(subset)) - 1.0
                ann_vol = subset.std(ddof=0) * sqrt(annualization_days)
                sharpe = (subset.mean() * annualization_days / ann_vol) if ann_vol > 0 else 0.0
                row = {
                    "strategy": name,
                    "regime": label,
                    "annualized_return": ann_return,
                    "annualized_volatility": ann_vol,
                    "sharpe": sharpe,
                    "days": int(len(subset)),
                }
            rows.append(row)
    return pd.DataFrame(rows)
