# Atlas20 Rotation - Five Year Window (2020-2024) Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: monthly and biweekly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top8_biweekly__bull_only**
- Best sector variant: **TOP20_SECTOR_top4_biweekly__bull_only**
- BTC benchmark CAGR: **58.34%**
- Equal-weight benchmark CAGR: **63.80%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **67.82% / 1.23**
   - BTC CAGR / Sharpe: **58.34% / 1.04**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **79.65% / 1.36**
   - Equal-weight CAGR / Sharpe: **63.80% / 1.02**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.98**
   - Average always-on Sharpe: **0.90**

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
| TOP20_SECTOR_top4_biweekly__bull_only | 79.65% | 54.04% | 1.36 | 2.17 | -52.77% | 1.51 | 10.86 | 2.16 |
| TOP20_SECTOR_top3_biweekly__bull_only | 76.18% | 55.18% | 1.31 | 2.09 | -51.95% | 1.47 | 11.20 | 1.64 |
| TOP20_SECTOR_top2_biweekly__bull_only | 78.59% | 60.37% | 1.26 | 2.07 | -53.14% | 1.48 | 13.15 | 1.08 |
| TOP20_MOM_top8_biweekly__bull_only | 67.82% | 54.48% | 1.23 | 1.91 | -52.65% | 1.29 | 9.45 | 2.84 |
| ETH_BH__always_on | 79.14% | 83.65% | 1.12 | 1.86 | -79.33% | 1.00 | 0.20 | 0.98 |
| ETH_BH__bull_only | 53.58% | 51.85% | 1.09 | 1.78 | -49.77% | 1.08 | 2.60 | 0.33 |
| TOP20_MOM_top6_biweekly__bull_only | 55.39% | 54.82% | 1.08 | 1.68 | -53.64% | 1.03 | 9.85 | 2.17 |
| TOP20_MOM_top4_biweekly__bull_only | 58.70% | 60.05% | 1.07 | 1.72 | -55.60% | 1.06 | 11.24 | 1.45 |
| BTC_BH__always_on | 58.34% | 64.48% | 1.04 | 1.70 | -76.67% | 0.76 | 0.20 | 0.98 |
| TOP20_EQ__always_on | 63.80% | 79.71% | 1.02 | 1.65 | -86.49% | 0.74 | 7.31 | 11.37 |
| TOP20_SECTOR_top4_monthly__always_on | 57.59% | 78.34% | 0.98 | 1.59 | -88.62% | 0.65 | 12.31 | 5.16 |
| TOP20_MOM_top8_biweekly__always_on | 56.82% | 82.24% | 0.96 | 1.59 | -85.08% | 0.67 | 17.18 | 7.22 |

## Recent yearly return table

| index | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2020 | 209.50% | 309.50% | 143.48% | 128.63% | 14.10% | 142.63% | 72.83% | 143.96% | 59.61% | 206.82% | 77.23% | 168.33% | 39.52% | 193.98% | 67.31% | -5.43% | 3.30% | -8.17% | 3.05% | 2.19% | -2.16% | 4.16% | -8.17% | -3.38% | 18.15% | 69.69% | 8.32% | 19.53% | 4.75% | 23.49% |
| 2021 | 59.45% | 398.65% | 221.66% | 233.35% | 248.81% | 129.14% | 259.71% | 107.86% | 464.76% | 179.00% | 348.94% | 207.57% | 320.96% | 162.30% | 420.33% | 18.58% | 293.31% | 202.54% | 149.36% | 177.66% | 88.32% | 178.79% | 89.85% | 311.51% | 162.31% | 476.54% | 174.95% | 381.04% | 174.92% | 431.41% |
| 2022 | -64.22% | -67.49% | -76.66% | -84.23% | -75.74% | -79.73% | -75.79% | -80.39% | -78.94% | -84.46% | -82.10% | -84.07% | -78.76% | -74.53% | -75.53% | -17.62% | -17.26% | -30.43% | -33.56% | 5.21% | -29.99% | 1.03% | -30.03% | -0.08% | -47.54% | 15.72% | -38.20% | 6.42% | -35.49% | 4.61% |
| 2023 | 155.76% | 90.91% | 203.11% | 141.75% | 137.26% | 189.21% | 150.11% | 191.33% | 146.76% | 139.82% | 71.35% | 143.16% | 114.26% | 151.08% | 85.80% | 24.51% | 28.36% | 65.60% | 72.69% | 125.83% | 59.60% | 99.84% | 66.33% | 93.51% | 46.17% | 55.88% | 54.54% | 74.48% | 42.86% | 55.30% |
| 2024 | 120.89% | 46.02% | 113.39% | 135.48% | 101.89% | 70.71% | 104.42% | 120.36% | 103.03% | -5.76% | 26.57% | 136.11% | 106.76% | 97.63% | 99.56% | 96.44% | 98.50% | 88.01% | 85.69% | 49.71% | 62.12% | 54.92% | 95.95% | 73.65% | 21.78% | 3.27% | 88.29% | 59.49% | 67.83% | 76.10% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 541.69% | -30.40% |
| BTC_BH__bull_only | 137.77% | -22.14% |
| ETH_BH__always_on | 1027.75% | -39.20% |
| ETH_BH__bull_only | 396.81% | -22.93% |
| TOP20_EQ__always_on | 1046.54% | -47.76% |
| TOP20_EQ__bull_only | 402.95% | -31.59% |
| TOP20_MOM_top4_biweekly__always_on | 999.03% | -60.23% |
| TOP20_MOM_top4_biweekly__bull_only | 426.85% | -21.56% |
| TOP20_MOM_top4_monthly__always_on | 892.21% | -52.19% |
| TOP20_MOM_top4_monthly__bull_only | 369.58% | -30.87% |
| TOP20_MOM_top6_biweekly__always_on | 938.13% | -51.67% |
| TOP20_MOM_top6_biweekly__bull_only | 398.46% | -21.63% |

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
