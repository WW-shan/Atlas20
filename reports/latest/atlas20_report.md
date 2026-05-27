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
- BTC benchmark CAGR: **16.84%**
- Equal-weight benchmark CAGR: **6.84%**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **Yes** on CAGR.
   - Best momentum CAGR / Sharpe: **20.31% / 0.62**
   - BTC CAGR / Sharpe: **16.84% / 0.56**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **Yes** on Sharpe.
   - Best sector CAGR / Sharpe: **18.13% / 0.58**
   - Equal-weight CAGR / Sharpe: **6.84% / 0.48**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **Yes** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **0.51**
   - Average always-on Sharpe: **0.43**

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
| ETH_BH__bull_only | 34.56% | 48.17% | 0.86 | 1.39 | -50.96% | 0.68 | 3.02 | 0.36 |
| TOP20_EQ__bull_only | 20.52% | 50.19% | 0.63 | 0.93 | -63.57% | 0.32 | 4.56 | 5.82 |
| TOP20_MOM_top8_biweekly__bull_only | 20.31% | 52.86% | 0.62 | 0.94 | -67.41% | 0.30 | 9.40 | 2.86 |
| TOP20_MOM_top8_biweekly__always_on | 17.45% | 81.13% | 0.61 | 1.00 | -89.92% | 0.19 | 19.87 | 7.61 |
| TOP20_SECTOR_top4_biweekly__bull_only | 18.13% | 52.22% | 0.58 | 0.90 | -66.40% | 0.27 | 10.34 | 2.13 |
| TOP20_MOM_top4_monthly__bull_only | 17.73% | 56.03% | 0.57 | 0.91 | -68.27% | 0.26 | 6.33 | 1.44 |
| BTC_BH__always_on | 16.84% | 57.17% | 0.56 | 0.94 | -76.74% | 0.22 | 0.19 | 0.98 |
| TOP20_MOM_top6_biweekly__bull_only | 15.84% | 54.02% | 0.55 | 0.84 | -67.75% | 0.23 | 9.34 | 2.16 |
| ETH_BH__always_on | 11.16% | 76.38% | 0.52 | 0.88 | -79.38% | 0.14 | 0.19 | 0.98 |
| TOP20_MOM_top6_biweekly__always_on | 8.06% | 82.94% | 0.51 | 0.84 | -91.73% | 0.09 | 21.43 | 5.85 |
| TOP20_SECTOR_top4_biweekly__always_on | 9.04% | 79.19% | 0.51 | 0.85 | -91.21% | 0.10 | 23.70 | 5.75 |
| BTC_BH__bull_only | 12.29% | 34.65% | 0.51 | 0.80 | -57.40% | 0.21 | 3.02 | 0.36 |

## Recent yearly return table

| year | BTC_BH__always_on | ETH_BH__always_on | TOP20_EQ__always_on | TOP20_MOM_top4_monthly__always_on | TOP20_MOM_top4_biweekly__always_on | TOP20_MOM_top6_monthly__always_on | TOP20_MOM_top6_biweekly__always_on | TOP20_MOM_top8_monthly__always_on | TOP20_MOM_top8_biweekly__always_on | TOP20_SECTOR_top2_monthly__always_on | TOP20_SECTOR_top2_biweekly__always_on | TOP20_SECTOR_top3_monthly__always_on | TOP20_SECTOR_top3_biweekly__always_on | TOP20_SECTOR_top4_monthly__always_on | TOP20_SECTOR_top4_biweekly__always_on | BTC_BH__bull_only | ETH_BH__bull_only | TOP20_EQ__bull_only | TOP20_MOM_top4_monthly__bull_only | TOP20_MOM_top4_biweekly__bull_only | TOP20_MOM_top6_monthly__bull_only | TOP20_MOM_top6_biweekly__bull_only | TOP20_MOM_top8_monthly__bull_only | TOP20_MOM_top8_biweekly__bull_only | TOP20_SECTOR_top2_monthly__bull_only | TOP20_SECTOR_top2_biweekly__bull_only | TOP20_SECTOR_top3_monthly__bull_only | TOP20_SECTOR_top3_biweekly__bull_only | TOP20_SECTOR_top4_monthly__bull_only | TOP20_SECTOR_top4_biweekly__bull_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | -64.31% | -67.54% | -76.70% | -84.31% | -90.96% | -79.81% | -87.17% | -80.47% | -84.04% | -84.57% | -88.86% | -84.16% | -87.88% | -74.64% | -84.19% | -17.66% | -17.31% | -30.49% | -33.63% | -40.77% | -30.06% | -33.17% | -30.10% | -32.40% | -47.64% | -37.21% | -38.28% | -28.26% | -35.57% | -30.36% |
| 2023 | 156.39% | 91.12% | 203.41% | 141.92% | 119.76% | 189.54% | 146.78% | 191.65% | 132.68% | 140.10% | 30.95% | 143.43% | 62.63% | 151.25% | 85.73% | 24.53% | 28.39% | 65.66% | 72.84% | 258.41% | 59.70% | 208.24% | 66.42% | 183.42% | 46.26% | 164.77% | 54.65% | 148.52% | 42.93% | 137.42% |
| 2024 | 121.08% | 46.07% | 113.41% | 135.58% | 107.98% | 70.68% | 100.24% | 120.46% | 172.78% | -5.83% | 66.30% | 136.21% | 139.39% | 97.79% | 126.67% | 96.55% | 98.63% | 88.10% | 85.65% | 49.01% | 62.05% | 60.56% | 96.04% | 117.75% | 21.67% | 41.49% | 88.27% | 108.33% | 67.87% | 96.74% |
| 2025 | -5.33% | -10.85% | -35.36% | -15.84% | -27.89% | -18.87% | -26.75% | -24.12% | -18.04% | -13.43% | -27.59% | -18.37% | -36.44% | -26.64% | -37.42% | -11.48% | 3.84% | -26.75% | -17.82% | -35.48% | -29.80% | -36.81% | -26.17% | -33.13% | -31.45% | -46.49% | -24.18% | -45.04% | -29.84% | -41.60% |
| 2026 | -14.33% | -22.35% | -19.17% | -23.29% | -27.90% | -20.21% | -21.19% | -18.63% | -26.45% | -32.44% | -32.23% | -33.18% | -29.75% | -31.32% | -26.87% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

## Performance by regime snapshot

| strategy | bull | non_bull |
| --- | --- | --- |
| BTC_BH__always_on | 362.88% | -49.75% |
| BTC_BH__bull_only | 134.76% | -28.54% |
| ETH_BH__always_on | 616.21% | -64.51% |
| ETH_BH__bull_only | 291.91% | -30.11% |
| TOP20_EQ__always_on | 565.06% | -65.16% |
| TOP20_EQ__bull_only | 254.09% | -37.74% |
| TOP20_MOM_top4_biweekly__always_on | 555.44% | -71.14% |
| TOP20_MOM_top4_biweekly__bull_only | 142.94% | -35.31% |
| TOP20_MOM_top4_monthly__always_on | 480.96% | -65.50% |
| TOP20_MOM_top4_monthly__bull_only | 229.56% | -37.35% |
| TOP20_MOM_top6_biweekly__always_on | 609.66% | -65.90% |
| TOP20_MOM_top6_biweekly__bull_only | 177.66% | -32.20% |

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
