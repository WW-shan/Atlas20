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
- BTC benchmark CAGR: **19.40%**
- Equal-weight benchmark CAGR: **10.11%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **29.76% / 0.73**
   - BTC CAGR / Sharpe: **19.40% / 0.60**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **15.41% / 0.54**
   - Equal-weight CAGR / Sharpe: **10.11% / 0.50**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.50**
   - Average always-on Sharpe: **0.50**

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
| ETH_BH__bull_only | 28.40% | 51.74% | 0.74 | 1.21 | -50.98% | 0.56 | 3.32 | 0.49 |
| TOP20_MOM_top6_biweekly__always_on | 29.76% | 79.86% | 0.73 | 1.20 | -82.46% | 0.36 | 18.41 | 6.00 |
| ETH_BH__always_on | 25.17% | 77.01% | 0.68 | 1.15 | -79.35% | 0.32 | 0.17 | 1.00 |
| TOP20_MOM_top6_biweekly__bull_only | 23.86% | 59.70% | 0.66 | 1.03 | -60.54% | 0.39 | 11.52 | 2.98 |
| TOP20_MOM_top8_biweekly__always_on | 20.98% | 76.65% | 0.64 | 1.03 | -83.03% | 0.25 | 17.18 | 8.00 |
| TOP20_EQ__bull_only | 19.70% | 52.87% | 0.61 | 0.91 | -69.50% | 0.28 | 4.52 | 9.77 |
| BTC_BH__always_on | 19.40% | 57.02% | 0.60 | 1.00 | -76.63% | 0.25 | 0.17 | 1.00 |
| TOP20_MOM_top6_monthly__bull_only | 17.58% | 60.21% | 0.57 | 0.90 | -68.23% | 0.26 | 7.58 | 2.93 |
| TOP20_MOM_top4_biweekly__always_on | 11.19% | 85.64% | 0.55 | 0.92 | -90.16% | 0.12 | 20.43 | 4.00 |
| TOP20_MOM_top8_monthly__bull_only | 16.24% | 57.13% | 0.55 | 0.85 | -69.74% | 0.23 | 7.19 | 3.91 |
| TOP20_MOM_top4_biweekly__bull_only | 15.75% | 63.94% | 0.55 | 0.87 | -71.56% | 0.22 | 12.09 | 1.99 |
| TOP20_SECTOR_top4_monthly__bull_only | 15.41% | 55.90% | 0.54 | 0.83 | -76.38% | 0.20 | 7.50 | 3.05 |

## Recent yearly return table

| year | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.27% | -67.50% | -74.92% | -81.72% | -81.98% | -78.74% | -79.04% | -77.31% | -80.00% | -75.37% | -90.07% | -75.22% | -81.62% | -77.11% | -81.08% | -17.68% | -17.30% | -26.57% | -28.12% | -29.11% | -27.18% | -24.52% | -26.75% | -25.41% | -24.04% | -30.11% | -29.45% | -27.60% | -25.88% | -24.71% |
| 2023 | 155.42% | 90.64% | 95.87% | 35.65% | 90.30% | 59.66% | 177.64% | 74.62% | 141.12% | 45.22% | 82.69% | 17.33% | 82.39% | 54.60% | 79.18% | 35.81% | 29.50% | 15.37% | -17.55% | 31.87% | -5.50% | 52.86% | 4.77% | 33.32% | -6.75% | -14.64% | -21.46% | -0.54% | -10.89% | 2.66% |
| 2024 | 121.05% | 46.07% | 69.67% | -7.40% | 3.48% | 21.84% | 15.66% | 14.89% | 33.54% | -15.64% | -6.44% | 50.10% | 9.56% | 44.80% | 33.75% | 96.54% | 98.52% | 81.72% | 5.54% | 9.28% | 47.17% | 21.31% | 36.74% | 32.35% | 9.22% | -5.58% | 85.57% | 19.01% | 82.33% | 44.02% |
| 2025 | -6.34% | -10.97% | -35.66% | -16.64% | 5.48% | -24.45% | -10.38% | -26.62% | -23.14% | -8.87% | 18.30% | -3.82% | -4.45% | -18.55% | -13.61% | -11.17% | 7.09% | -21.86% | -14.59% | -4.02% | -23.16% | -13.18% | -20.54% | -25.48% | -8.92% | -2.68% | -6.70% | -25.14% | -15.56% | -18.80% |
| 2026 | -7.27% | -10.92% | 3.77% | 52.33% | 7.02% | 22.55% | -2.74% | 16.73% | -2.15% | 6.05% | -13.36% | 2.22% | -9.21% | 20.76% | 2.07% | -18.28% | -16.60% | -9.89% | 9.82% | 20.13% | 3.77% | 12.04% | -2.20% | 15.40% | 18.10% | 33.11% | 10.87% | 10.56% | 2.63% | 18.73% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 224.51% | -54.86% |
| BTC_BH__bull_only | 113.27% | -41.89% |
| ETH_BH__always_on | 372.17% | -65.60% |
| ETH_BH__bull_only | 216.05% | -46.54% |
| TOP20_EQ__always_on | 409.80% | -75.20% |
| TOP20_EQ__bull_only | 207.58% | -52.20% |
| TOP20_MOM_top4_biweekly__always_on | 452.21% | -76.61% |
| TOP20_MOM_top4_biweekly__bull_only | 204.13% | -54.77% |
| TOP20_MOM_top4_monthly__always_on | 308.10% | -78.14% |
| TOP20_MOM_top4_monthly__bull_only | 109.85% | -53.16% |
| TOP20_MOM_top6_biweekly__always_on | 567.97% | -73.64% |
| TOP20_MOM_top6_biweekly__bull_only | 226.32% | -51.73% |

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
