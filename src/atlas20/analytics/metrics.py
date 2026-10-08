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
    # Compound the returns rather than divide the equity ends: equity[0] is
    # already after day 0's return. That is harmless for an engine run (day 0
    # is a structural zero) but dropped the first day of every sliced result -
    # the ctrend champion's yearly table showed BTC 2024 at 111.5%, not 121.1%.
    total_return = float((1.0 + returns).prod() - 1.0)
    # The equity curve has one point per day, so the investment spans len - 1
    # days: day 0 closes at the starting capital because the first target only
    # takes effect on day 1. Annualizing over len days understated CAGR, badly
    # so for short windows (1.35pp on a 100-day run).
    periods = max(len(returns) - 1, 1)
    cagr = (1.0 + returns).prod() ** (annualization_days / periods) - 1.0
    vol = returns.std(ddof=0) * sqrt(annualization_days)
    # Downside deviation below a 0 target, sqrt(mean(min(r, 0)^2)). The std of
    # min(r, 0) subtracted the mean loss first, shrinking the denominator and
    # overstating Sortino (BTC since 2021: 1.036 instead of 0.908).
    downside_std = sqrt(float((returns.clip(upper=0.0) ** 2).mean())) * sqrt(annualization_days) if len(returns) else 0.0
    sharpe = (returns.mean() * annualization_days / vol) if vol > 0 else 0.0
    sortino = (returns.mean() * annualization_days / downside_std) if downside_std > 0 else 0.0
    # Drawdown runs from the starting capital. A result sliced out of a longer
    # run has an equity curve that starts after its first return, so a
    # first-day loss never registered ([-10%, +5%] showed no drawdown).
    wealth = pd.concat([pd.Series([1.0]), (1.0 + returns).cumprod()], ignore_index=True)
    max_drawdown = float((wealth / wealth.cummax() - 1.0).min())
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
    frame.index.name = "year"
    return frame.sort_index()



def rolling_return_series(result: BacktestResult, window_days: int) -> pd.Series:
    """Return a rolling compounded return series."""
    returns = _safe_series(result.daily_returns)
    return (1.0 + returns).rolling(window_days).apply(np.prod, raw=True) - 1.0



def performance_by_regime(results: dict[str, BacktestResult], regime_frame: pd.DataFrame, annualization_days: int = 365) -> pd.DataFrame:
    """Summarize strategy performance inside bull and non-bull states.

    Day t's return is labelled with the regime at the previous close (t-1).
    """
    rows = []
    # The regime at close t is computed from prices that already contain day
    # t's return, so same-day labels sort crash days into non-bull by
    # construction (a random walk scored bull Sharpe 2.81 vs non-bull -1.96).
    # Same one-day lag as _lagged_regime_labels in
    # scripts/run_phase_momentum_regime_breakdown.py.
    return_index = next(iter(results.values())).daily_returns.index
    bull_state = regime_frame["bull"].shift(1, freq="D").reindex(return_index).fillna(False).astype(bool)
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
