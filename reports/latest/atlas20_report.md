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
- BTC benchmark CAGR: **20.75%**
- Equal-weight benchmark CAGR: **11.17%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **28.70% / 0.72**
   - BTC CAGR / Sharpe: **20.75% / 0.62**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **16.02% / 0.55**
   - Equal-weight CAGR / Sharpe: **11.17% / 0.52**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **No** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.50**
   - Average always-on Sharpe: **0.51**

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
| ETH_BH__bull_only | 29.50% | 51.77% | 0.76 | 1.23 | -50.98% | 0.58 | 3.32 | 0.49 |
| TOP20_MOM_top6_biweekly__always_on | 28.70% | 74.30% | 0.72 | 1.17 | -74.61% | 0.38 | 17.80 | 6.00 |
| ETH_BH__always_on | 26.24% | 77.02% | 0.69 | 1.17 | -79.35% | 0.33 | 0.17 | 1.00 |
| TOP20_MOM_top8_biweekly__always_on | 24.24% | 72.13% | 0.67 | 1.07 | -77.57% | 0.31 | 16.73 | 8.00 |
| TOP20_EQ__bull_only | 20.49% | 52.82% | 0.62 | 0.93 | -69.50% | 0.29 | 4.52 | 9.77 |
| BTC_BH__always_on | 20.75% | 57.08% | 0.62 | 1.04 | -76.63% | 0.27 | 0.17 | 1.00 |
| TOP20_MOM_top6_biweekly__bull_only | 19.29% | 55.12% | 0.60 | 0.92 | -56.00% | 0.34 | 11.01 | 2.98 |
| TOP20_MOM_top8_monthly__bull_only | 17.40% | 54.45% | 0.57 | 0.88 | -71.19% | 0.24 | 6.89 | 3.91 |
| TOP20_MOM_top6_monthly__bull_only | 17.50% | 57.11% | 0.57 | 0.90 | -70.66% | 0.25 | 7.27 | 2.93 |
| TOP20_MOM_top4_biweekly__always_on | 13.16% | 77.98% | 0.55 | 0.90 | -82.49% | 0.16 | 19.38 | 4.00 |
| TOP20_SECTOR_top4_monthly__bull_only | 16.02% | 55.90% | 0.55 | 0.85 | -76.38% | 0.21 | 7.50 | 3.05 |
| TOP20_SECTOR_top3_monthly__bull_only | 15.97% | 57.59% | 0.55 | 0.86 | -81.86% | 0.20 | 8.66 | 2.29 |

## Recent yearly return table

| year | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.27% | -67.50% | -74.48% | -73.24% | -75.82% | -74.31% | -71.45% | -73.79% | -74.68% | -72.11% | -87.69% | -75.22% | -81.62% | -77.11% | -81.08% | -17.68% | -17.30% | -26.57% | -14.17% | -29.11% | -22.53% | -24.52% | -23.40% | -25.41% | -24.04% | -25.55% | -29.45% | -27.60% | -25.88% | -24.71% |
| 2023 | 155.42% | 90.64% | 95.87% | 58.92% | 114.36% | 66.10% | 151.26% | 79.80% | 133.81% | 43.74% | 67.81% | 17.33% | 82.39% | 54.60% | 79.18% | 35.81% | 29.50% | 15.37% | -3.34% | 48.64% | -1.68% | 38.33% | 7.89% | 29.29% | -2.59% | -12.65% | -21.46% | -0.54% | -10.89% | 2.66% |
| 2024 | 121.05% | 46.07% | 68.12% | -4.33% | 0.81% | 30.74% | 17.57% | 20.81% | 37.05% | -15.77% | -4.61% | 50.10% | 9.56% | 44.80% | 33.75% | 96.54% | 98.52% | 80.06% | 9.04% | 10.45% | 55.10% | 27.10% | 42.53% | 37.90% | 10.77% | -4.91% | 85.57% | 19.01% | 82.33% | 44.02% |
| 2025 | -6.34% | -10.97% | -35.66% | -2.58% | 16.85% | -23.21% | -7.56% | -24.21% | -23.83% | -8.19% | 19.32% | -3.82% | -4.45% | -18.55% | -13.61% | -11.17% | 7.09% | -21.86% | -3.22% | 4.30% | -23.16% | -9.85% | -17.90% | -25.25% | -10.01% | -3.50% | -6.70% | -25.14% | -15.56% | -18.80% |
| 2026 | -1.04% | -6.42% | 8.76% | 53.85% | 9.10% | 25.45% | -0.33% | 20.60% | 0.89% | 8.98% | -14.24% | 4.91% | -6.29% | 24.52% | 5.73% | -12.78% | -12.39% | -5.56% | 10.92% | 22.48% | 6.22% | 14.81% | 1.04% | 18.99% | 15.09% | 28.40% | 13.79% | 14.12% | 5.83% | 22.99% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 231.70% | -54.86% |
| BTC_BH__bull_only | 118.08% | -41.89% |
| ETH_BH__always_on | 379.75% | -65.60% |
| ETH_BH__bull_only | 221.25% | -46.54% |
| TOP20_EQ__always_on | 415.86% | -75.05% |
| TOP20_EQ__bull_only | 211.39% | -52.20% |
| TOP20_MOM_top4_biweekly__always_on | 380.95% | -72.34% |
| TOP20_MOM_top4_biweekly__bull_only | 178.86% | -51.58% |
| TOP20_MOM_top4_monthly__always_on | 270.53% | -73.53% |
| TOP20_MOM_top4_monthly__bull_only | 101.02% | -47.04% |
| TOP20_MOM_top6_biweekly__always_on | 480.91% | -70.33% |
| TOP20_MOM_top6_biweekly__bull_only | 191.74% | -50.07% |

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
