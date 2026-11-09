# Atlas20 Rotation Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: biweekly and monthly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top6_biweekly__bull_only**
- Best sector variant: **TOP20_SECTOR_top4_biweekly__bull_only**
- BTC benchmark CAGR: **17.21%**
- Equal-weight benchmark CAGR: **14.35%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **31.74% / 0.77**
   - BTC CAGR / Sharpe: **17.21% / 0.56**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **21.45% / 0.63**
   - Equal-weight CAGR / Sharpe: **14.35% / 0.56**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.54**
   - Average always-on Sharpe: **0.44**

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
| ETH_BH__bull_only | 35.95% | 55.08% | 0.83 | 1.29 | -50.98% | 0.71 | 3.25 | 0.51 |
| TOP20_MOM_top6_biweekly__bull_only | 31.74% | 58.18% | 0.77 | 1.13 | -56.00% | 0.57 | 11.58 | 3.17 |
| TOP20_MOM_top8_biweekly__bull_only | 27.83% | 56.65% | 0.72 | 1.04 | -58.99% | 0.47 | 11.35 | 4.22 |
| TOP20_EQ__bull_only | 23.71% | 54.55% | 0.67 | 0.94 | -69.50% | 0.34 | 4.60 | 10.28 |
| TOP20_MOM_top4_biweekly__bull_only | 21.59% | 60.39% | 0.63 | 0.92 | -60.83% | 0.35 | 11.99 | 2.11 |
| TOP20_SECTOR_top4_biweekly__bull_only | 21.45% | 57.93% | 0.63 | 0.91 | -71.68% | 0.30 | 12.94 | 3.35 |
| TOP20_MOM_top6_biweekly__always_on | 20.27% | 74.29% | 0.62 | 0.90 | -74.61% | 0.27 | 17.82 | 6.00 |
| ETH_BH__always_on | 19.93% | 76.45% | 0.62 | 0.92 | -79.35% | 0.25 | 0.17 | 1.00 |
| TOP20_MOM_top8_biweekly__always_on | 17.15% | 71.95% | 0.59 | 0.83 | -77.57% | 0.22 | 16.72 | 8.00 |
| BTC_BH__always_on | 17.21% | 56.63% | 0.56 | 0.83 | -76.63% | 0.22 | 0.17 | 1.00 |
| TOP20_EQ__always_on | 14.35% | 73.29% | 0.56 | 0.77 | -82.52% | 0.17 | 3.10 | 19.99 |
| TOP20_SECTOR_top3_biweekly__bull_only | 12.26% | 61.75% | 0.50 | 0.73 | -76.29% | 0.16 | 14.78 | 2.47 |

## Recent yearly return table

| year | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.27% | -67.50% | -74.48% | -73.24% | -75.82% | -74.31% | -71.45% | -73.79% | -74.68% | -72.11% | -87.69% | -75.22% | -81.62% | -77.11% | -81.08% | -17.68% | -17.30% | -26.57% | -14.17% | -29.11% | -22.53% | -24.52% | -23.40% | -25.41% | -24.04% | -25.55% | -29.45% | -27.60% | -25.88% | -24.71% |
| 2023 | 155.42% | 90.64% | 95.87% | 58.92% | 114.36% | 66.10% | 151.26% | 79.80% | 133.81% | 43.74% | 67.81% | 17.33% | 82.39% | 54.60% | 79.18% | 35.81% | 29.50% | 15.37% | -3.34% | 48.64% | -1.68% | 38.33% | 7.89% | 29.29% | -2.59% | -12.65% | -21.46% | -0.54% | -10.89% | 2.66% |
| 2024 | 121.05% | 46.07% | 68.12% | -4.33% | 0.81% | 30.74% | 17.57% | 20.81% | 37.05% | -15.77% | -4.61% | 50.10% | 9.56% | 44.80% | 33.75% | 96.54% | 98.52% | 80.06% | 9.04% | 10.45% | 55.10% | 27.10% | 42.53% | 37.90% | 10.77% | -4.91% | 85.57% | 19.01% | 82.33% | 44.02% |
| 2025 | -6.34% | -10.97% | -35.66% | -2.58% | 16.85% | -23.21% | -7.56% | -24.21% | -23.83% | -8.19% | 19.32% | -3.82% | -4.45% | -18.55% | -13.61% | -11.17% | 7.09% | -21.86% | -3.22% | 4.30% | -23.16% | -9.85% | -17.90% | -25.25% | -10.01% | -3.50% | -6.70% | -25.14% | -15.56% | -18.80% |
| 2026 | -14.77% | -28.52% | -15.94% | 8.44% | -22.19% | -11.01% | -30.71% | -14.85% | -26.37% | -9.15% | -39.28% | -20.65% | -29.32% | -5.04% | -17.14% | -24.88% | -33.07% | -27.00% | -21.82% | -12.65% | -24.65% | -20.19% | -28.66% | -13.17% | -4.06% | -9.08% | -13.94% | -13.92% | -19.30% | -3.61% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 72.15% | -22.38% |
| BTC_BH__bull_only | 54.22% | -22.33% |
| ETH_BH__always_on | 148.77% | -45.14% |
| ETH_BH__bull_only | 144.88% | -27.67% |
| TOP20_EQ__always_on | 141.52% | -48.69% |
| TOP20_EQ__bull_only | 106.84% | -28.70% |
| TOP20_MOM_top4_biweekly__always_on | 120.85% | -51.25% |
| TOP20_MOM_top4_biweekly__bull_only | 106.16% | -30.96% |
| TOP20_MOM_top4_monthly__always_on | 65.68% | -51.34% |
| TOP20_MOM_top4_monthly__bull_only | 24.42% | -26.85% |
| TOP20_MOM_top6_biweekly__always_on | 170.57% | -49.57% |
| TOP20_MOM_top6_biweekly__bull_only | 131.00% | -27.85% |

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
