"""CSV export and markdown report generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from atlas20.backtest.engine import BacktestResult
from atlas20.config import ResearchConfig



def dataframe_to_markdown(
    df: pd.DataFrame,
    percent_columns: set[str] | None = None,
    number_columns: set[str] | None = None,
) -> str:
    """Render a compact markdown table without external dependencies."""
    formatted = df.copy()
    percent_columns = percent_columns or set()
    number_columns = number_columns or set()

    for column in formatted.columns:
        if not pd.api.types.is_numeric_dtype(formatted[column]):
            continue
        if column in percent_columns:
            formatted[column] = formatted[column].map(lambda x: f"{x:.2%}" if pd.notna(x) else "")
        elif column in number_columns:
            formatted[column] = formatted[column].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
        else:
            formatted[column] = formatted[column].map(lambda x: f"{x:,.4f}" if pd.notna(x) else "")
    header = "| " + " | ".join([str(df.index.name or "index"), *map(str, formatted.columns)]) + " |"
    sep = "| " + " | ".join(["---"] * (len(formatted.columns) + 1)) + " |"
    rows = []
    for idx, row in formatted.iterrows():
        rows.append("| " + " | ".join([str(idx), *map(str, row.tolist())]) + " |")
    return "\n".join([header, sep, *rows])



def export_result_tables(
    results: dict[str, BacktestResult],
    summary: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    regime_performance: pd.DataFrame,
    report_dir: Path,
) -> None:
    """Export the major result tables and time series as CSV."""
    report_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(report_dir / "strategy_summary.csv")
    yearly_returns.to_csv(report_dir / "yearly_returns.csv")
    regime_performance.to_csv(report_dir / "regime_performance.csv", index=False)

    pd.DataFrame({name: result.daily_returns for name, result in results.items()}).to_csv(report_dir / "daily_returns.csv")
    pd.DataFrame({name: result.equity_curve for name, result in results.items()}).to_csv(report_dir / "equity_curves.csv")
    pd.DataFrame({name: result.drawdown for name, result in results.items()}).to_csv(report_dir / "drawdowns.csv")
    turnover = pd.DataFrame(
        {
            "annualized_turnover": summary["annualized_turnover"],
            "avg_turnover_per_rebalance": summary["avg_turnover_per_rebalance"],
            "average_holdings": summary["average_holdings"],
        }
    )
    turnover.to_csv(report_dir / "turnover_summary.csv")



def _pick_best(summary: pd.DataFrame, prefix: str) -> tuple[str, pd.Series]:
    subset = summary[summary.index.to_series().str.startswith(prefix)]
    if subset.empty:
        return "N/A", pd.Series(dtype=float)
    best_name = subset.sort_values(["sharpe", "cagr"], ascending=False).index[0]
    return best_name, subset.loc[best_name]



def build_markdown_report(
    config: ResearchConfig,
    summary: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    regime_performance: pd.DataFrame,
    output_path: Path,
) -> str:
    """Create the final markdown research report."""
    btc = summary.loc["BTC_BH__always_on"]
    eq = summary.loc["TOP20_EQ__always_on"]
    best_mom_name, best_mom = _pick_best(summary, "TOP20_MOM_")
    best_sector_name, best_sector = _pick_best(summary, "TOP20_SECTOR_")
    bull_subset = summary[summary.index.to_series().str.endswith("__bull_only")]
    always_subset = summary[summary.index.to_series().str.endswith("__always_on")]
    avg_bull_sharpe = bull_subset["sharpe"].mean() if not bull_subset.empty else 0.0
    avg_always_sharpe = always_subset["sharpe"].mean() if not always_subset.empty else 0.0

    def verdict(condition: bool) -> str:
        return "Yes" if condition else "No"

    top_summary = summary.head(12).copy()
    yearly_head = yearly_returns.tail(5).copy()
    regime_head = regime_performance.pivot(index="strategy", columns="regime", values="annualized_return").sort_index().head(12)

    summary_percent_cols = {"cagr", "annualized_volatility", "max_drawdown"}
    summary_number_cols = {"sharpe", "sortino", "calmar", "annualized_turnover", "average_holdings"}
    yearly_percent_cols = set(yearly_head.columns)
    regime_percent_cols = set(regime_head.columns)

    text = f"""# {config.project_name} Research Report

## Scope

- Universe: top-{config.universe.universe_size} non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: monthly and biweekly.
- Regime overlays tested: always-on and bull-only.
- Frictions: {config.frictions.fee_bps:.1f} bps fee + {config.frictions.slippage_bps:.1f} bps slippage.

## Executive summary

- Best momentum variant: **{best_mom_name}**
- Best sector variant: **{best_sector_name}**
- BTC benchmark CAGR: **{btc['cagr']:.2%}**
- Equal-weight benchmark CAGR: **{eq['cagr']:.2%}**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **{verdict(not best_mom.empty and best_mom['cagr'] > btc['cagr'])}** on CAGR.
   - Best momentum CAGR / Sharpe: **{best_mom.get('cagr', 0.0):.2%} / {best_mom.get('sharpe', 0.0):.2f}**
   - BTC CAGR / Sharpe: **{btc['cagr']:.2%} / {btc['sharpe']:.2f}**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **{verdict(not best_sector.empty and best_sector['sharpe'] > eq['sharpe'])}** on Sharpe.
   - Best sector CAGR / Sharpe: **{best_sector.get('cagr', 0.0):.2%} / {best_sector.get('sharpe', 0.0):.2f}**
   - Equal-weight CAGR / Sharpe: **{eq['cagr']:.2%} / {eq['sharpe']:.2f}**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **{verdict(avg_bull_sharpe > avg_always_sharpe)}** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **{avg_bull_sharpe:.2f}**
   - Average always-on Sharpe: **{avg_always_sharpe:.2f}**

4. **Is the extra complexity of sector rotation justified?**
   - Verdict: **{verdict(not best_sector.empty and best_sector['sharpe'] > eq['sharpe'] and best_sector['max_drawdown'] >= eq['max_drawdown'])}**
   - Interpretation: sector rotation is only justified if it improves Sharpe meaningfully without materially worsening implementation risk.

5. **What are the main practical risks and data limitations?**
   - Historical market-cap rankings use direct CoinGecko daily market caps for the recent window and a price-scaled proxy anchor before that because free long-history point-in-time market-cap series are limited.
   - Sector labels come from a current metadata snapshot plus manual overrides, so they are not perfectly point-in-time.
   - Candidate coverage is reduced-survivorship rather than perfect-survivorship-free; the project uses current large caps plus a curated legacy list.
   - CryptoCompare symbol-level history can still be imperfect for rebrands, ticker collisions, or synthetic duplicates, although the pipeline now validates 365-day overlap against CoinGecko and exports `data/processed/data_quality.csv`.

## Strategy comparison table

{dataframe_to_markdown(top_summary[["cagr", "annualized_volatility", "sharpe", "sortino", "max_drawdown", "calmar", "annualized_turnover", "average_holdings"]], percent_columns=summary_percent_cols, number_columns=summary_number_cols)}

## Recent yearly return table

{dataframe_to_markdown(yearly_head, percent_columns=yearly_percent_cols)}

## Performance by regime snapshot

{dataframe_to_markdown(regime_head.fillna(0.0), percent_columns=regime_percent_cols)}

## Interpretation notes

- Market cap is used strictly for **universe selection**, not weighting.
- Rotation strategies use **equal-weight allocations** after signal selection.
- A strong result for momentum generally indicates relative-strength persistence inside large and liquid crypto assets.
- A weak result for sector rotation usually indicates that its extra selection layer does not compensate for turnover and classification noise.

## Next recommended improvements

1. Replace proxy market caps with a paid or archived point-in-time market-cap dataset.
2. Add exchange-level liquidity filters and price-source cross checks.
3. Add daily regime-trigger exits as an overlay rather than rebalance-date-only gating.
4. Add transaction-cost sensitivity sweeps and bootstrap significance tests.
5. Expand sector mapping with time-aware overrides for major token rebrands and protocol migrations.
"""
    output_path.write_text(text, encoding="utf-8")
    return text
