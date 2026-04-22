# Atlas20 Rotation - Exact Five Year Window (2021-04-22 to 2026-04-22) Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: monthly and biweekly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top8_biweekly__bull_only**
- Best sector variant: **TOP20_SECTOR_top4_biweekly__bull_only**
- BTC benchmark CAGR: **5.53%**
- Equal-weight benchmark CAGR: **-0.65%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **22.53% / 0.68**
   - BTC CAGR / Sharpe: **5.53% / 0.38**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **11.47% / 0.47**
   - Equal-weight CAGR / Sharpe: **-0.65% / 0.35**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.41**
   - Average always-on Sharpe: **0.26**

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
| TOP20_MOM_top8_biweekly__bull_only | 22.53% | 44.35% | 0.68 | 1.07 | -49.31% | 0.46 | 8.06 | 2.75 |
| ETH_BH__bull_only | 18.67% | 37.34% | 0.64 | 1.04 | -50.95% | 0.37 | 2.80 | 0.32 |
| TOP20_MOM_top4_biweekly__bull_only | 19.14% | 50.25% | 0.60 | 0.97 | -57.57% | 0.33 | 9.41 | 1.38 |
| TOP20_MOM_top6_biweekly__bull_only | 18.13% | 46.30% | 0.59 | 0.93 | -56.95% | 0.32 | 8.71 | 2.07 |
| BTC_BH__bull_only | 10.53% | 27.02% | 0.50 | 0.79 | -33.75% | 0.31 | 2.80 | 0.32 |
| TOP20_SECTOR_top4_biweekly__bull_only | 11.47% | 42.58% | 0.47 | 0.72 | -62.57% | 0.18 | 9.71 | 2.11 |
| TOP20_MOM_top4_monthly__bull_only | 9.52% | 43.56% | 0.42 | 0.68 | -49.54% | 0.19 | 5.47 | 1.26 |
| TOP20_SECTOR_top3_biweekly__bull_only | 8.84% | 42.52% | 0.41 | 0.64 | -61.52% | 0.14 | 10.87 | 1.59 |
| TOP20_MOM_top8_monthly__bull_only | 8.79% | 39.64% | 0.41 | 0.62 | -46.36% | 0.19 | 4.93 | 2.51 |
| TOP20_MOM_top4_biweekly__always_on | 0.94% | 77.86% | 0.40 | 0.67 | -90.17% | 0.01 | 21.77 | 3.77 |
| TOP20_MOM_top6_biweekly__always_on | 2.60% | 72.49% | 0.40 | 0.66 | -87.73% | 0.03 | 20.30 | 5.60 |
| TOP20_MOM_top4_monthly__always_on | 1.91% | 73.55% | 0.39 | 0.66 | -90.71% | 0.02 | 12.92 | 3.78 |

## Recent yearly return table

| index | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.22% | -67.49% | -76.66% | -84.23% | -83.98% | -79.73% | -82.75% | -80.39% | -82.32% | -84.46% | -88.19% | -84.07% | -83.24% | -74.53% | -77.98% | -17.62% | -17.26% | -30.43% | -33.56% | -14.23% | -29.99% | -9.24% | -30.03% | -10.70% | -47.54% | -23.99% | -38.20% | -12.03% | -35.49% | -7.66% |
| 2023 | 155.76% | 90.91% | 203.11% | 141.75% | 118.97% | 189.21% | 161.10% | 191.33% | 156.12% | 139.82% | 91.15% | 143.16% | 110.99% | 151.08% | 100.22% | 24.51% | 28.36% | 65.60% | 72.69% | 163.62% | 59.60% | 149.33% | 66.33% | 147.64% | 46.17% | 106.48% | 54.54% | 116.85% | 42.86% | 94.43% |
| 2024 | 120.89% | 46.02% | 113.39% | 135.48% | 129.82% | 70.71% | 107.71% | 120.36% | 120.17% | -5.76% | 56.51% | 136.11% | 62.03% | 97.63% | 131.20% | 96.44% | 98.50% | 88.01% | 85.69% | 85.12% | 62.12% | 80.55% | 95.95% | 95.46% | 21.78% | 37.97% | 88.29% | 58.88% | 67.83% | 102.25% |
| 2025 | -5.33% | -10.84% | -35.35% | -15.80% | -30.07% | -18.82% | -26.34% | -24.07% | -23.56% | -13.37% | -27.31% | -18.29% | -38.26% | -26.62% | -41.33% | -11.47% | 3.86% | -26.71% | -17.81% | -36.72% | -29.74% | -38.20% | -26.12% | -28.64% | -31.38% | -46.91% | -24.12% | -44.45% | -29.82% | -46.70% |
| 2026 | -14.32% | -22.33% | -19.16% | -23.27% | -27.77% | -20.19% | -23.91% | -18.62% | -27.09% | -32.41% | -32.99% | -33.16% | -28.14% | -31.29% | -29.05% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 312.00% | -48.41% |
| BTC_BH__bull_only | 98.74% | -18.80% |
| ETH_BH__always_on | 380.79% | -58.61% |
| ETH_BH__bull_only | 152.80% | -20.25% |
| TOP20_EQ__always_on | 343.29% | -54.73% |
| TOP20_EQ__bull_only | 130.33% | -27.69% |
| TOP20_MOM_top4_biweekly__always_on | 382.39% | -55.63% |
| TOP20_MOM_top4_biweekly__bull_only | 210.57% | -27.98% |
| TOP20_MOM_top4_monthly__always_on | 313.03% | -51.15% |
| TOP20_MOM_top4_monthly__bull_only | 142.34% | -27.85% |
| TOP20_MOM_top6_biweekly__always_on | 340.35% | -52.28% |
| TOP20_MOM_top6_biweekly__bull_only | 180.73% | -25.04% |

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
