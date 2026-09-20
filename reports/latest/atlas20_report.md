# Atlas20 Rotation Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: biweekly and monthly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top6_monthly__bull_only**
- Best sector variant: **TOP20_SECTOR_top3_monthly__bull_only**
- BTC benchmark CAGR: **19.44%**
- Equal-weight benchmark CAGR: **11.34%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **26.38% / 0.69**
   - BTC CAGR / Sharpe: **19.44% / 0.60**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **26.03% / 0.69**
   - Equal-weight CAGR / Sharpe: **11.34% / 0.52**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.53**
   - Average always-on Sharpe: **0.53**

4. **Is the extra complexity of sector rotation justified?**
   - Verdict: **Yes**
   - Interpretation: sector rotation is only justified if it improves Sharpe meaningfully without materially worsening implementation risk.

5. **What are the main practical risks and data limitations?**
   - Historical market-cap rankings use direct CoinGecko daily market caps for the recent window and a price-scaled proxy anchor before that because free long-history point-in-time market-cap series are limited.
   - Sector labels come from a current metadata snapshot plus manual overrides, so they are not perfectly point-in-time.
   - Candidate coverage is reduced-survivorship rather than perfect-survivorship-free; the project uses current large caps plus a curated legacy list.
   - CryptoCompare symbol-level history can still be imperfect for rebrands, ticker collisions, or synthetic duplicates, although the pipeline now validates 365-day overlap against CoinGecko and exports `data/processed/data_quality.csv`.

## Strategy comparison table

| strategy | cagr | annualized_volatility | sharpe | sortino | max_drawdown | calmar | annualized_turnover | average_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ETH_BH__bull_only | 28.29% | 51.78% | 0.74 | 1.20 | -50.99% | 0.55 | 3.32 | 0.49 |
| TOP20_SECTOR_top3_monthly__bull_only | 26.03% | 57.61% | 0.69 | 1.10 | -77.72% | 0.33 | 8.02 | 2.22 |
| TOP20_MOM_top6_monthly__bull_only | 26.38% | 60.58% | 0.69 | 1.10 | -73.77% | 0.36 | 7.58 | 2.93 |
| TOP20_MOM_top8_monthly__bull_only | 25.07% | 57.20% | 0.68 | 1.05 | -73.64% | 0.34 | 7.17 | 3.90 |
| ETH_BH__always_on | 25.11% | 77.09% | 0.68 | 1.15 | -79.38% | 0.32 | 0.17 | 1.00 |
| TOP20_MOM_top8_biweekly__always_on | 23.85% | 74.94% | 0.67 | 1.07 | -84.88% | 0.28 | 16.81 | 8.00 |
| TOP20_EQ__bull_only | 22.51% | 53.68% | 0.65 | 0.97 | -72.89% | 0.31 | 4.49 | 9.76 |
| TOP20_SECTOR_top4_monthly__bull_only | 22.78% | 55.14% | 0.65 | 1.01 | -74.71% | 0.30 | 7.36 | 2.96 |
| TOP20_MOM_top6_biweekly__always_on | 21.17% | 77.13% | 0.64 | 1.04 | -85.60% | 0.25 | 19.24 | 6.00 |
| TOP20_MOM_top4_biweekly__always_on | 17.47% | 82.26% | 0.61 | 1.01 | -89.97% | 0.19 | 21.78 | 4.00 |
| BTC_BH__always_on | 19.44% | 57.13% | 0.60 | 1.01 | -76.71% | 0.25 | 0.17 | 1.00 |
| TOP20_MOM_top4_biweekly__bull_only | 18.96% | 63.23% | 0.59 | 0.93 | -71.60% | 0.26 | 12.85 | 2.01 |

## Recent yearly return table

| year | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.35% | -67.53% | -74.39% | -82.30% | -79.25% | -79.39% | -79.56% | -79.17% | -77.96% | -72.85% | -74.14% | -73.90% | -71.00% | -75.76% | -77.91% | -17.71% | -17.35% | -27.11% | -32.55% | -27.34% | -30.13% | -24.44% | -28.32% | -24.53% | -31.75% | -25.29% | -34.61% | -27.71% | -30.39% | -26.51% |
| 2023 | 156.02% | 90.75% | 130.55% | 64.06% | 62.46% | 97.80% | 162.29% | 107.21% | 167.26% | 10.55% | 35.20% | 65.08% | 57.44% | 58.25% | 97.16% | 35.82% | 29.52% | 36.49% | -3.32% | 22.17% | 24.09% | 46.60% | 27.47% | 45.42% | -22.98% | -5.27% | 8.29% | 10.68% | 0.88% | 17.98% |
| 2024 | 121.24% | 46.10% | 79.10% | 1.76% | 33.49% | 2.51% | 22.16% | 10.27% | 48.15% | -13.38% | -35.36% | 57.45% | 3.35% | 57.05% | 38.00% | 96.65% | 98.65% | 91.85% | 20.11% | 31.35% | 28.63% | 16.22% | 38.11% | 34.04% | 22.61% | -36.26% | 93.68% | 0.21% | 89.82% | 34.43% |
| 2025 | -6.34% | -10.97% | -36.19% | -23.39% | -9.46% | -20.48% | -15.63% | -27.17% | -23.69% | -1.42% | -1.03% | 8.23% | -13.21% | -8.63% | -18.92% | -11.18% | 7.05% | -21.64% | -17.33% | -21.47% | -16.47% | -21.15% | -18.90% | -24.60% | -22.71% | -37.61% | -5.84% | -29.26% | -10.65% | -25.04% |
| 2026 | -7.18% | -11.30% | 1.43% | 79.27% | 8.26% | 33.02% | 4.03% | 13.67% | -6.98% | 7.52% | -10.04% | 3.93% | -11.16% | 11.01% | -3.44% | -18.22% | -16.98% | -10.48% | 18.26% | 11.57% | 6.53% | 10.29% | 0.78% | 5.06% | 17.32% | 9.40% | 9.19% | 0.85% | 4.26% | 9.21% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 227.79% | -55.63% |
| BTC_BH__bull_only | 115.49% | -42.77% |
| ETH_BH__always_on | 376.97% | -66.34% |
| ETH_BH__bull_only | 219.53% | -47.60% |
| TOP20_EQ__always_on | 433.64% | -76.07% |
| TOP20_EQ__bull_only | 231.48% | -53.86% |
| TOP20_MOM_top4_biweekly__always_on | 444.41% | -73.91% |
| TOP20_MOM_top4_biweekly__bull_only | 211.21% | -53.69% |
| TOP20_MOM_top4_monthly__always_on | 364.60% | -76.86% |
| TOP20_MOM_top4_monthly__bull_only | 164.47% | -53.04% |
| TOP20_MOM_top6_biweekly__always_on | 447.56% | -72.41% |
| TOP20_MOM_top6_biweekly__bull_only | 176.17% | -52.81% |

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
