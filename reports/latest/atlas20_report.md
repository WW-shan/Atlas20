# Atlas20 Rotation Research Report

## Scope

- Universe: top-20 non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: biweekly and monthly.
- Regime overlays tested: always-on and bull-only.
- Frictions: 10.0 bps fee + 10.0 bps slippage.

## Executive summary

- Best momentum variant: **TOP20_MOM_top8_biweekly__bull_only**
- Best sector variant: **TOP20_SECTOR_top4_biweekly__bull_only**
- BTC benchmark CAGR: **17.01%**
- Equal-weight benchmark CAGR: **10.73%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **25.79% / 0.70**
   - BTC CAGR / Sharpe: **17.01% / 0.56**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **20.93% / 0.63**
   - Equal-weight CAGR / Sharpe: **10.73% / 0.52**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.51**
   - Average always-on Sharpe: **0.51**

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
| ETH_BH__bull_only | 28.47% | 47.28% | 0.77 | 1.24 | -51.03% | 0.56 | 3.32 | 0.36 |
| TOP20_MOM_top8_biweekly__bull_only | 25.79% | 52.94% | 0.70 | 1.07 | -67.41% | 0.38 | 9.86 | 2.87 |
| TOP20_MOM_top8_biweekly__always_on | 26.58% | 79.62% | 0.70 | 1.15 | -88.28% | 0.30 | 20.04 | 7.59 |
| TOP20_SECTOR_top4_biweekly__bull_only | 20.93% | 51.44% | 0.63 | 0.97 | -66.40% | 0.32 | 11.01 | 2.16 |
| TOP20_SECTOR_top3_biweekly__bull_only | 19.76% | 54.33% | 0.60 | 0.96 | -71.54% | 0.28 | 12.09 | 1.67 |
| TOP20_MOM_top6_biweekly__bull_only | 18.27% | 54.22% | 0.59 | 0.90 | -67.67% | 0.27 | 9.88 | 2.17 |
| TOP20_MOM_top6_biweekly__always_on | 14.20% | 81.46% | 0.57 | 0.95 | -90.04% | 0.16 | 21.35 | 5.82 |
| TOP20_MOM_top4_monthly__always_on | 13.57% | 81.56% | 0.57 | 0.96 | -88.79% | 0.15 | 13.85 | 3.94 |
| TOP20_SECTOR_top2_biweekly__bull_only | 17.06% | 56.75% | 0.56 | 0.90 | -70.62% | 0.24 | 13.01 | 1.13 |
| BTC_BH__always_on | 17.01% | 55.96% | 0.56 | 0.94 | -76.74% | 0.22 | 0.17 | 0.99 |
| TOP20_EQ__bull_only | 15.82% | 49.46% | 0.55 | 0.82 | -62.52% | 0.25 | 4.95 | 5.59 |
| TOP20_MOM_top4_biweekly__bull_only | 15.49% | 58.31% | 0.54 | 0.84 | -72.54% | 0.21 | 11.04 | 1.45 |

## Recent yearly return table

| year | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.31% | -67.54% | -75.79% | -81.56% | -90.39% | -78.32% | -86.58% | -79.82% | -83.45% | -85.23% | -88.85% | -83.58% | -88.77% | -74.00% | -84.74% | -17.66% | -17.31% | -30.49% | -33.63% | -39.10% | -30.06% | -33.01% | -30.10% | -32.39% | -47.64% | -37.21% | -38.28% | -34.00% | -35.57% | -30.36% |
| 2023 | 156.39% | 91.12% | 231.52% | 221.38% | 161.56% | 230.31% | 166.30% | 229.46% | 150.12% | 189.02% | 71.82% | 169.86% | 80.56% | 174.24% | 101.79% | 24.53% | 28.39% | 65.66% | 72.84% | 258.41% | 59.70% | 208.24% | 66.42% | 183.42% | 46.26% | 164.77% | 54.65% | 148.52% | 42.93% | 137.42% |
| 2024 | 121.08% | 46.07% | 111.07% | 124.92% | 103.70% | 57.62% | 93.49% | 108.75% | 162.48% | -12.12% | 57.71% | 128.57% | 123.48% | 101.21% | 135.87% | 96.55% | 98.63% | 86.00% | 77.08% | 43.09% | 49.64% | 53.58% | 85.54% | 108.59% | 13.45% | 26.52% | 82.18% | 95.77% | 70.58% | 99.35% |
| 2025 | -5.39% | -10.91% | -41.97% | -41.66% | -27.42% | -32.74% | -28.70% | -31.99% | -27.44% | -27.02% | -15.42% | -25.78% | -34.80% | -23.09% | -37.09% | -12.31% | 4.10% | -31.45% | -36.38% | -25.76% | -34.78% | -30.99% | -30.02% | -30.73% | -33.21% | -26.48% | -27.57% | -40.09% | -24.12% | -36.20% |
| 2026 | -7.80% | -10.97% | -2.13% | 56.97% | -0.01% | 36.26% | -0.02% | 22.91% | 12.45% | -12.45% | -19.64% | -0.12% | -3.79% | 5.13% | -8.33% | -15.05% | -13.47% | -6.80% | 28.16% | 14.28% | 15.74% | 13.27% | 10.14% | 23.36% | 25.09% | 16.66% | 12.48% | 12.20% | 11.04% | 6.54% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 371.79% | -50.61% |
| BTC_BH__bull_only | 126.35% | -31.62% |
| ETH_BH__always_on | 600.33% | -63.46% |
| ETH_BH__bull_only | 270.47% | -33.28% |
| TOP20_EQ__always_on | 565.36% | -63.48% |
| TOP20_EQ__bull_only | 236.74% | -40.15% |
| TOP20_MOM_top4_biweekly__always_on | 611.15% | -67.80% |
| TOP20_MOM_top4_biweekly__bull_only | 216.77% | -38.13% |
| TOP20_MOM_top4_monthly__always_on | 491.37% | -59.07% |
| TOP20_MOM_top4_monthly__bull_only | 206.72% | -39.32% |
| TOP20_MOM_top6_biweekly__always_on | 613.77% | -63.24% |
| TOP20_MOM_top6_biweekly__bull_only | 222.42% | -36.40% |

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
