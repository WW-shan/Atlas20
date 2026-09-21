# Atlas20 Rotation Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: biweekly and monthly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top6_biweekly__always_on**
- Best sector variant: **TOP20_SECTOR_top3_monthly__bull_only**
- BTC benchmark CAGR: **19.43%**
- Equal-weight benchmark CAGR: **8.83%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **No** on CAGR.
   - Best momentum CAGR / Sharpe: **19.02% / 0.62**
   - BTC CAGR / Sharpe: **19.43% / 0.60**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **15.76% / 0.54**
   - Equal-weight CAGR / Sharpe: **8.83% / 0.49**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **No** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.46**
   - Average always-on Sharpe: **0.46**

4. **Is the extra complexity of sector rotation justified?**
   - Verdict: **Yes**
   - Interpretation: sector rotation is only justified if it improves Sharpe meaningfully without materially worsening implementation risk.

5. **What are the main practical risks and data limitations?**
   - Historical market-cap rankings use CoinMarketCap's own daily market cap and circulating supply. There is no synthetic fallback: an asset without real supply data is not rankable, so it never appears in the universe on invented numbers.
   - Sector labels come from a current metadata snapshot plus manual overrides, so they are not perfectly point-in-time.
   - Candidate coverage is reduced-survivorship rather than perfect-survivorship-free; the project uses current large caps plus a curated legacy list.
   - CoinMarketCap symbol/ID resolution is not infallible for rebrands or ticker reuse. `data/processed/data_quality.csv` records per-asset coverage, and the panel drops any row that predates the asset's first real market-cap observation.

## Strategy comparison table

| strategy | cagr | annualized_volatility | sharpe | sortino | max_drawdown | calmar | annualized_turnover | average_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ETH_BH__bull_only | 28.32% | 51.76% | 0.74 | 1.20 | -50.98% | 0.56 | 3.32 | 0.49 |
| ETH_BH__always_on | 25.09% | 77.03% | 0.67 | 1.15 | -79.35% | 0.32 | 0.17 | 1.00 |
| TOP20_MOM_top6_biweekly__always_on | 19.02% | 79.00% | 0.62 | 1.01 | -87.49% | 0.22 | 19.27 | 6.00 |
| TOP20_MOM_top8_biweekly__always_on | 18.27% | 76.11% | 0.61 | 0.97 | -85.07% | 0.21 | 17.35 | 8.00 |
| BTC_BH__always_on | 19.43% | 57.04% | 0.60 | 1.00 | -76.63% | 0.25 | 0.17 | 1.00 |
| TOP20_EQ__bull_only | 17.74% | 52.93% | 0.58 | 0.86 | -71.71% | 0.25 | 4.58 | 9.76 |
| TOP20_MOM_top6_biweekly__bull_only | 17.05% | 59.74% | 0.57 | 0.87 | -65.64% | 0.26 | 11.92 | 2.98 |
| TOP20_MOM_top6_monthly__bull_only | 16.57% | 60.58% | 0.56 | 0.88 | -71.23% | 0.23 | 7.60 | 2.93 |
| TOP20_SECTOR_top3_monthly__bull_only | 15.76% | 57.85% | 0.54 | 0.86 | -81.73% | 0.19 | 8.64 | 2.29 |
| TOP20_MOM_top8_monthly__bull_only | 14.87% | 57.61% | 0.53 | 0.82 | -72.17% | 0.21 | 7.23 | 3.90 |
| TOP20_MOM_top8_biweekly__bull_only | 13.99% | 56.67% | 0.52 | 0.78 | -62.46% | 0.22 | 11.09 | 3.97 |
| TOP20_MOM_top6_monthly__always_on | 9.80% | 77.57% | 0.51 | 0.83 | -87.35% | 0.11 | 12.23 | 5.91 |

## Recent yearly return table

| year | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.27% | -67.50% | -74.87% | -83.08% | -86.90% | -78.89% | -83.10% | -78.41% | -81.10% | -78.11% | -89.46% | -78.24% | -84.51% | -79.69% | -81.79% | -17.68% | -17.30% | -27.03% | -31.73% | -29.98% | -30.98% | -25.11% | -28.89% | -25.85% | -25.78% | -30.11% | -26.56% | -27.60% | -29.98% | -24.71% |
| 2023 | 155.42% | 90.64% | 96.51% | 32.47% | 56.25% | 54.12% | 152.34% | 74.17% | 130.92% | 4.43% | 70.19% | 20.07% | 67.78% | 35.92% | 78.79% | 35.81% | 29.50% | 15.59% | -18.86% | 13.43% | -7.72% | 41.25% | 3.90% | 28.36% | -31.25% | -17.46% | -17.13% | -10.71% | -19.79% | -0.94% |
| 2024 | 121.05% | 46.07% | 70.42% | -7.40% | 17.75% | 19.53% | 21.19% | 13.31% | 39.45% | -15.14% | -14.88% | 52.37% | 12.14% | 44.82% | 23.53% | 96.54% | 98.52% | 81.29% | 5.54% | 20.31% | 44.39% | 23.55% | 34.86% | 37.50% | 11.19% | -16.22% | 88.37% | 17.81% | 82.37% | 29.57% |
| 2025 | -6.34% | -10.97% | -34.95% | -15.31% | 3.08% | -15.22% | -11.70% | -23.46% | -20.66% | 10.02% | 3.62% | 16.54% | -9.08% | -1.68% | -16.14% | -11.17% | 7.09% | -21.59% | -17.28% | -10.60% | -16.41% | -17.50% | -18.86% | -21.61% | -0.96% | -12.07% | -5.82% | -25.86% | -10.66% | -22.48% |
| 2026 | -7.17% | -11.29% | 2.06% | 49.33% | 1.30% | 20.67% | -6.49% | 15.27% | -5.11% | 4.60% | -14.34% | 0.51% | -10.75% | 18.98% | -1.17% | -18.19% | -16.95% | -11.37% | 7.66% | 13.71% | 2.18% | 7.72% | -3.42% | 11.91% | 16.48% | 31.60% | 9.01% | 8.69% | 1.12% | 14.96% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 230.85% | -55.72% |
| BTC_BH__bull_only | 117.44% | -42.98% |
| ETH_BH__always_on | 376.65% | -66.00% |
| ETH_BH__bull_only | 219.05% | -47.14% |
| TOP20_EQ__always_on | 399.83% | -75.33% |
| TOP20_EQ__bull_only | 203.00% | -53.09% |
| TOP20_MOM_top4_biweekly__always_on | 411.77% | -78.79% |
| TOP20_MOM_top4_biweekly__bull_only | 187.71% | -55.37% |
| TOP20_MOM_top4_monthly__always_on | 301.36% | -78.41% |
| TOP20_MOM_top4_monthly__bull_only | 106.39% | -54.35% |
| TOP20_MOM_top6_biweekly__always_on | 490.92% | -74.99% |
| TOP20_MOM_top6_biweekly__bull_only | 195.40% | -52.47% |

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
