# Atlas20 Rotation Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: monthly and biweekly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top8_biweekly__bull_only**
- Best sector variant: **TOP20_SECTOR_top3_biweekly__bull_only**
- BTC benchmark CAGR: **16.81%**
- Equal-weight benchmark CAGR: **-4.99%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **No** on CAGR.
   - Best momentum CAGR / Sharpe: **8.11% / 0.41**
   - BTC CAGR / Sharpe: **16.81% / 0.56**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **No** on Sharpe.
   - Best sector CAGR / Sharpe: **-0.40% / 0.24**
   - Equal-weight CAGR / Sharpe: **-4.99% / 0.32**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.24**
   - Average always-on Sharpe: **0.22**

4. **Is the extra complexity of sector rotation justified?**
   - Verdict: **No**
   - Interpretation: sector rotation is only justified if it improves Sharpe meaningfully without materially worsening implementation risk.

5. **What are the main practical risks and data limitations?**
   - Historical market-cap rankings use direct CoinGecko daily market caps for the recent window and a price-scaled proxy anchor before that because free long-history point-in-time market-cap series are limited.
   - Sector labels come from a current metadata snapshot plus manual overrides, so they are not perfectly point-in-time.
   - Candidate coverage is reduced-survivorship rather than perfect-survivorship-free; the project uses current large caps plus a curated legacy list.
   - CryptoCompare symbol-level history can still be imperfect for rebrands, ticker collisions, or synthetic duplicates, although the pipeline now validates 365-day overlap against CoinGecko and exports `data/processed/data_quality.csv`.

## Strategy comparison table

| strategy | cagr | annualized_volatility | sharpe | sortino | max_drawdown | calmar | annualized_turnover | average_holdings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ETH_BH__bull_only | 16.87% | 44.04% | 0.57 | 0.91 | -50.95% | 0.33 | 3.01 | 0.31 |
| BTC_BH__always_on | 16.81% | 57.08% | 0.56 | 0.93 | -76.67% | 0.22 | 0.19 | 0.98 |
| ETH_BH__always_on | 11.14% | 76.29% | 0.52 | 0.87 | -79.33% | 0.14 | 0.19 | 0.98 |
| TOP20_MOM_top8_biweekly__bull_only | 8.11% | 49.06% | 0.41 | 0.61 | -67.33% | 0.12 | 8.44 | 2.52 |
| TOP20_EQ__always_on | -4.99% | 76.49% | 0.32 | 0.51 | -86.49% | -0.06 | 6.21 | 13.88 |
| TOP20_MOM_top6_biweekly__bull_only | 2.83% | 50.14% | 0.31 | 0.46 | -67.68% | 0.04 | 8.41 | 1.90 |
| TOP20_MOM_top4_monthly__always_on | -7.40% | 80.44% | 0.31 | 0.51 | -90.71% | -0.08 | 13.07 | 3.81 |
| TOP20_MOM_top4_monthly__bull_only | 2.61% | 50.85% | 0.31 | 0.47 | -68.16% | 0.04 | 5.54 | 1.25 |
| TOP20_MOM_top4_biweekly__bull_only | 1.01% | 54.84% | 0.30 | 0.45 | -73.22% | 0.01 | 9.47 | 1.27 |
| TOP20_MOM_top6_monthly__always_on | -7.60% | 76.34% | 0.28 | 0.45 | -87.63% | -0.09 | 11.81 | 5.63 |
| TOP20_MOM_top8_biweekly__always_on | -8.72% | 77.17% | 0.27 | 0.44 | -89.87% | -0.10 | 18.79 | 7.21 |
| TOP20_MOM_top8_monthly__always_on | -8.07% | 75.37% | 0.27 | 0.43 | -89.30% | -0.09 | 10.55 | 7.34 |

## Recent yearly return table

| index | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.22% | -67.49% | -76.66% | -84.23% | -90.91% | -79.73% | -87.11% | -80.39% | -83.98% | -84.46% | -88.79% | -84.07% | -87.80% | -74.53% | -84.11% | -17.62% | -17.26% | -30.43% | -33.56% | -40.70% | -29.99% | -33.11% | -30.03% | -32.35% | -47.54% | -37.15% | -38.20% | -28.21% | -35.49% | -30.31% |
| 2023 | 155.76% | 90.91% | 203.11% | 141.75% | 119.49% | 189.21% | 146.57% | 191.33% | 132.46% | 139.82% | 31.04% | 143.16% | 62.62% | 151.08% | 85.72% | 24.51% | 28.36% | 65.60% | 72.69% | 257.76% | 59.60% | 207.76% | 66.33% | 183.01% | 46.17% | 164.41% | 54.54% | 148.17% | 42.86% | 137.13% |
| 2024 | 120.89% | 46.02% | 113.39% | 135.48% | 107.95% | 70.71% | 100.23% | 120.36% | 172.54% | -5.76% | 66.63% | 136.11% | 139.42% | 97.63% | 126.82% | 96.44% | 98.50% | 88.01% | 85.69% | 48.99% | 62.12% | 60.50% | 95.95% | 117.53% | 21.78% | 41.61% | 88.29% | 108.28% | 67.83% | 96.76% |
| 2025 | -5.33% | -10.84% | -35.35% | -15.80% | -27.83% | -18.82% | -26.73% | -24.07% | -18.04% | -13.37% | -27.53% | -18.29% | -36.42% | -26.62% | -37.38% | -11.47% | 3.86% | -26.71% | -17.81% | -35.42% | -29.74% | -36.77% | -26.12% | -33.11% | -31.38% | -46.43% | -24.12% | -45.00% | -29.82% | -41.55% |
| 2026 | -14.32% | -22.33% | -19.16% | -23.27% | -27.83% | -20.19% | -21.15% | -18.62% | -26.39% | -32.41% | -32.14% | -33.16% | -29.69% | -31.29% | -26.80% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 336.08% | -39.57% |
| BTC_BH__bull_only | 93.03% | -26.83% |
| ETH_BH__always_on | 518.86% | -52.93% |
| ETH_BH__bull_only | 210.46% | -28.32% |
| TOP20_EQ__always_on | 418.52% | -59.36% |
| TOP20_EQ__bull_only | 144.46% | -35.60% |
| TOP20_MOM_top4_biweekly__always_on | 452.65% | -71.14% |
| TOP20_MOM_top4_biweekly__bull_only | 131.23% | -33.26% |
| TOP20_MOM_top4_monthly__always_on | 406.05% | -60.42% |
| TOP20_MOM_top4_monthly__bull_only | 157.19% | -35.21% |
| TOP20_MOM_top6_biweekly__always_on | 399.61% | -65.49% |
| TOP20_MOM_top6_biweekly__bull_only | 123.66% | -30.30% |

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
