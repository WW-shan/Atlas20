# Atlas20 Rotation - Bear Bottom to Current (2022-11-21 to 2026-04-22) Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: monthly and biweekly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top8_biweekly__bull_only**
- Best sector variant: **TOP20_SECTOR_top3_monthly__bull_only**
- BTC benchmark CAGR: **54.29%**
- Equal-weight benchmark CAGR: **24.73%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **No** on CAGR.
   - Best momentum CAGR / Sharpe: **39.76% / 0.92**
   - BTC CAGR / Sharpe: **54.29% / 1.16**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **26.07% / 0.73**
   - Equal-weight CAGR / Sharpe: **24.73% / 0.67**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.74**
   - Average always-on Sharpe: **0.64**

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
| BTC_BH__always_on | 54.29% | 47.09% | 1.16 | 2.07 | -49.63% | 1.09 | 0.29 | 0.99 |
| TOP20_MOM_top8_biweekly__bull_only | 39.76% | 49.92% | 0.92 | 1.48 | -47.78% | 0.83 | 9.81 | 3.57 |
| BTC_BH__bull_only | 25.35% | 30.31% | 0.90 | 1.49 | -23.29% | 1.09 | 2.92 | 0.41 |
| ETH_BH__bull_only | 32.93% | 42.44% | 0.88 | 1.49 | -50.95% | 0.65 | 2.92 | 0.41 |
| TOP20_MOM_top4_monthly__bull_only | 32.77% | 49.66% | 0.82 | 1.38 | -42.51% | 0.77 | 6.84 | 1.65 |
| TOP20_MOM_top4_biweekly__bull_only | 35.43% | 56.94% | 0.81 | 1.37 | -50.44% | 0.70 | 11.17 | 1.79 |
| TOP20_MOM_top6_biweekly__bull_only | 32.92% | 52.03% | 0.81 | 1.32 | -52.29% | 0.63 | 10.22 | 2.69 |
| TOP20_MOM_top8_monthly__bull_only | 29.31% | 45.42% | 0.79 | 1.25 | -46.36% | 0.63 | 6.04 | 3.28 |
| TOP20_EQ__bull_only | 27.29% | 43.84% | 0.77 | 1.19 | -53.79% | 0.51 | 4.78 | 6.33 |
| TOP20_MOM_top4_biweekly__always_on | 32.22% | 69.31% | 0.75 | 1.30 | -59.39% | 0.54 | 19.81 | 3.68 |
| TOP20_MOM_top8_monthly__always_on | 30.71% | 62.13% | 0.74 | 1.26 | -56.91% | 0.54 | 9.76 | 7.01 |
| TOP20_SECTOR_top3_monthly__bull_only | 26.07% | 46.56% | 0.73 | 1.19 | -49.62% | 0.53 | 7.71 | 1.90 |

## Recent yearly return table

| index | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -3.87% | -7.90% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| 2023 | 155.76% | 90.91% | 90.88% | 47.45% | 59.10% | 76.52% | 70.18% | 83.50% | 65.26% | 52.61% | 12.75% | 55.87% | 28.35% | 67.75% | 28.13% | 24.51% | 28.36% | 65.60% | 72.69% | 141.68% | 59.60% | 121.28% | 66.33% | 107.67% | 46.17% | 27.99% | 54.54% | 56.51% | 42.86% | 55.06% |
| 2024 | 120.89% | 46.02% | 113.39% | 135.48% | 141.53% | 70.71% | 126.20% | 120.36% | 154.41% | -5.76% | 162.49% | 136.11% | 128.57% | 97.63% | 108.49% | 96.44% | 98.50% | 88.01% | 85.69% | 62.17% | 62.12% | 69.69% | 95.95% | 112.03% | 21.78% | 162.50% | 88.29% | 110.70% | 67.83% | 87.55% |
| 2025 | -5.33% | -10.84% | -35.35% | -15.80% | -16.06% | -18.82% | -30.65% | -24.07% | -30.83% | -13.37% | -13.30% | -18.29% | -30.59% | -26.62% | -25.42% | -11.47% | 3.86% | -26.71% | -17.81% | -28.04% | -29.74% | -29.53% | -26.12% | -28.66% | -31.38% | -38.46% | -24.12% | -33.44% | -29.82% | -27.16% |
| 2026 | -14.32% | -22.33% | -19.16% | -23.27% | -19.44% | -20.19% | -21.61% | -18.62% | -21.31% | -32.41% | -30.52% | -33.16% | -31.12% | -31.29% | -24.15% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 233.63% | -16.14% |
| BTC_BH__bull_only | 128.89% | -22.13% |
| ETH_BH__always_on | 350.70% | -58.89% |
| ETH_BH__bull_only | 192.21% | -28.68% |
| TOP20_EQ__always_on | 291.40% | -49.49% |
| TOP20_EQ__bull_only | 177.40% | -31.24% |
| TOP20_MOM_top4_biweekly__always_on | 308.99% | -45.85% |
| TOP20_MOM_top4_biweekly__bull_only | 235.65% | -33.92% |
| TOP20_MOM_top4_monthly__always_on | 260.51% | -44.60% |
| TOP20_MOM_top4_monthly__bull_only | 203.88% | -31.01% |
| TOP20_MOM_top6_biweekly__always_on | 302.34% | -51.02% |
| TOP20_MOM_top6_biweekly__bull_only | 221.37% | -33.85% |

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
