# Atlas20 Rotation Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: biweekly and monthly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top6_biweekly__always_on**
- Best sector variant: **TOP20_SECTOR_top4_monthly__bull_only**
- BTC benchmark CAGR: **19.44%**
- Equal-weight benchmark CAGR: **10.16%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **21.55% / 0.65**
   - BTC CAGR / Sharpe: **19.44% / 0.60**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **14.81% / 0.53**
   - Equal-weight CAGR / Sharpe: **10.16% / 0.50**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **No** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.46**
   - Average always-on Sharpe: **0.49**

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
| ETH_BH__bull_only | 28.29% | 51.78% | 0.74 | 1.20 | -50.99% | 0.55 | 3.32 | 0.49 |
| ETH_BH__always_on | 25.11% | 77.09% | 0.68 | 1.15 | -79.38% | 0.32 | 0.17 | 1.00 |
| TOP20_MOM_top6_biweekly__always_on | 21.55% | 78.50% | 0.65 | 1.05 | -86.73% | 0.25 | 18.95 | 6.00 |
| TOP20_EQ__bull_only | 20.28% | 52.82% | 0.62 | 0.92 | -71.37% | 0.28 | 4.51 | 9.76 |
| TOP20_MOM_top8_biweekly__always_on | 19.27% | 75.62% | 0.62 | 0.99 | -84.16% | 0.23 | 17.18 | 8.00 |
| TOP20_MOM_top6_monthly__bull_only | 19.79% | 60.72% | 0.60 | 0.95 | -69.76% | 0.28 | 7.60 | 2.93 |
| BTC_BH__always_on | 19.44% | 57.13% | 0.60 | 1.01 | -76.71% | 0.25 | 0.17 | 1.00 |
| TOP20_MOM_top8_monthly__bull_only | 18.96% | 57.49% | 0.59 | 0.91 | -71.42% | 0.27 | 7.19 | 3.90 |
| TOP20_MOM_top6_monthly__always_on | 14.76% | 77.62% | 0.57 | 0.92 | -86.24% | 0.17 | 12.13 | 5.91 |
| TOP20_MOM_top6_biweekly__bull_only | 15.74% | 59.21% | 0.55 | 0.84 | -65.69% | 0.24 | 11.81 | 2.98 |
| TOP20_SECTOR_top4_monthly__bull_only | 14.81% | 56.07% | 0.53 | 0.82 | -78.75% | 0.19 | 7.75 | 3.03 |
| TOP20_MOM_top4_biweekly__always_on | 8.57% | 83.71% | 0.52 | 0.85 | -91.81% | 0.09 | 20.36 | 4.00 |

## Recent yearly return table

| year | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.35% | -67.53% | -75.37% | -82.27% | -84.46% | -77.21% | -82.41% | -76.85% | -79.94% | -75.78% | -90.07% | -79.24% | -84.05% | -79.27% | -82.53% | -17.71% | -17.35% | -26.02% | -28.18% | -30.04% | -27.24% | -25.16% | -26.81% | -25.90% | -24.09% | -29.85% | -29.51% | -27.65% | -25.94% | -24.76% |
| 2023 | 156.02% | 90.75% | 103.41% | 40.71% | 75.85% | 60.60% | 142.47% | 73.82% | 129.97% | 34.40% | 48.08% | 29.47% | 69.99% | 37.35% | 74.81% | 35.82% | 29.52% | 19.54% | -18.95% | 25.14% | -7.78% | 27.80% | 3.87% | 25.62% | -16.56% | -23.92% | -21.14% | -12.93% | -19.55% | -4.91% |
| 2024 | 121.24% | 46.10% | 81.16% | 13.29% | 34.02% | 24.07% | 28.40% | 23.57% | 46.62% | -16.16% | -24.70% | 55.67% | 13.27% | 48.80% | 17.10% | 96.65% | 98.65% | 93.51% | 24.28% | 36.52% | 53.68% | 30.88% | 53.41% | 44.47% | 14.54% | -15.77% | 85.54% | 18.86% | 82.37% | 22.89% |
| 2025 | -6.34% | -10.97% | -34.96% | -15.35% | -9.46% | -15.30% | -15.63% | -23.51% | -23.69% | 12.12% | -1.03% | 16.55% | -13.21% | -1.66% | -18.92% | -11.18% | 7.05% | -21.64% | -17.33% | -21.47% | -16.47% | -21.15% | -18.90% | -24.60% | -22.71% | -37.61% | -5.84% | -29.26% | -10.65% | -25.04% |
| 2026 | -7.18% | -11.30% | 1.43% | 79.27% | 8.26% | 33.02% | 4.03% | 13.67% | -6.98% | 7.52% | -10.04% | 3.93% | -11.16% | 11.01% | -3.44% | -18.22% | -16.98% | -10.48% | 18.26% | 11.57% | 6.53% | 10.29% | 0.78% | 5.06% | 17.32% | 9.40% | 9.19% | 0.85% | 4.26% | 9.21% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 231.44% | -55.78% |
| BTC_BH__bull_only | 117.52% | -43.00% |
| ETH_BH__always_on | 377.12% | -66.01% |
| ETH_BH__bull_only | 219.12% | -47.17% |
| TOP20_EQ__always_on | 408.36% | -75.14% |
| TOP20_EQ__bull_only | 209.32% | -52.05% |
| TOP20_MOM_top4_biweekly__always_on | 412.69% | -76.05% |
| TOP20_MOM_top4_biweekly__bull_only | 189.41% | -54.45% |
| TOP20_MOM_top4_monthly__always_on | 318.32% | -75.43% |
| TOP20_MOM_top4_monthly__bull_only | 117.41% | -51.77% |
| TOP20_MOM_top6_biweekly__always_on | 467.77% | -72.89% |
| TOP20_MOM_top6_biweekly__bull_only | 184.11% | -51.72% |

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
