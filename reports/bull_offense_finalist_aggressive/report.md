# Bull Offense Finalist (unlevered)

- Window: 2021-01-01 .. 2026-09-21 (2090 days)
- Structure: point-in-time Top-N, weekly rebalance, BTC 50D trend gate, top 1 by 30D absolute+relative momentum, asset stop on its own 50D MA, 80% target vol (30D window)
- Leverage: none. Gross exposure hard-capped at 1.0x.
- Peak gross exposure observed: 1.0000
- Average gross exposure: 38.0%; flat on 47.9% of days

## Champion at each cost level

| cost_bps | total_return | cagr | sharpe | max_drawdown | calmar | annualized_turnover | avg_gross_exposure | pct_days_flat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5.0 | 14762.7% | 139.6% | 1.5101 | -65.3% | 2.1376 | 25.8745 | 38.0% | 47.9% |
| 8.0 | 14116.3% | 137.8% | 1.5000 | -65.7% | 2.0976 | 25.8745 | 38.0% | 47.9% |
| 10.0 | 13700.9% | 136.5% | 1.4933 | -65.9% | 2.0714 | 25.8745 | 38.0% | 47.9% |
| 15.0 | 12714.4% | 133.5% | 1.4764 | -66.5% | 2.0073 | 25.8745 | 38.0% | 47.9% |

## BTC buy-and-hold on the same window

| cost_bps | total_return | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- |
| 5.0 | 194.7% | 20.8% | 0.6159 | -76.6% |
| 8.0 | 194.6% | 20.8% | 0.6158 | -76.6% |
| 10.0 | 194.5% | 20.8% | 0.6158 | -76.6% |
| 15.0 | 194.4% | 20.8% | 0.6156 | -76.6% |

## Yearly returns (5 bps)

| year | strategy | btc | excess | beats_btc |
| --- | --- | --- | --- | --- |
| 2021 | 703.2% | 57.6% | 645.6% | 1.0000 |
| 2022 | -0.3% | -64.3% | 63.9% | 1.0000 |
| 2023 | 243.6% | 155.4% | 88.1% | 1.0000 |
| 2024 | 456.0% | 121.1% | 334.9% | 1.0000 |
| 2025 | -7.2% | -6.3% | -0.8% | 0.0000 |
| 2026 | 4.7% | -1.0% | 5.7% | 1.0000 |

## Sub-periods (5 bps)

| period | total_return | btc_total_return | excess_total_return | cagr | sharpe | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| 2021 | 703.2% | 57.6% | 645.6% | 703.2% | 3.0525 | -18.8% |
| 2022 | -0.3% | -64.3% | 63.9% | -0.3% | 0.2508 | -31.6% |
| 2023 | 243.6% | 155.4% | 88.1% | 243.6% | 1.9454 | -37.2% |
| 2024 | 456.0% | 121.1% | 334.9% | 453.4% | 2.1379 | -34.0% |
| 2025 | -7.2% | -6.3% | -0.8% | -7.2% | 0.1795 | -35.7% |
| 2026_ytd | 4.7% | -1.0% | 5.7% | 6.5% | 0.4007 | -48.8% |
| 2021_2022 | 700.6% | -43.7% | 744.3% | 183.0% | 1.8232 | -31.6% |
| 2023_onward | 1756.4% | 423.4% | 1333.0% | 119.0% | 1.3658 | -65.3% |

## Champion vs the risk/return frontier (cost-stressed)

| cell | hold_count | lookback | btc_ma | asset_ma | target_vol | total_return | max_drawdown | sharpe | stress15_total_return | stress15_max_drawdown | pareto |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.0000 | 21.0000 | 50.0000 | 0.0000 | 1.0000 | 14762.7% | -65.3% | 1.5101 | 12714.4% | -66.5% | 1.0000 |

## Rolling monthly starts, windows >= 180 days

| cost_bps | windows | win_rate_vs_btc | worst_ratio | median_ratio | median_cagr | median_maxdd |
| --- | --- | --- | --- | --- | --- | --- |
| 5.0 | 63.0000 | 96.8% | 0.9757 | 3.6802 | 0.9063 | -65.3% |
| 8.0 | 63.0000 | 96.8% | 0.9606 | 3.5526 | 0.8911 | -65.7% |
| 10.0 | 63.0000 | 96.8% | 0.9507 | 3.4699 | 0.8811 | -65.9% |
| 15.0 | 63.0000 | 95.2% | 0.9262 | 3.2766 | 0.8561 | -66.5% |

## Rolling monthly starts, every window (>= 30 days)

| cost_bps | windows | win_rate_vs_btc | worst_ratio | median_ratio | median_cagr | median_maxdd |
| --- | --- | --- | --- | --- | --- | --- |
| 5.0 | 68.0000 | 97.1% | 0.9757 | 3.5445 | 1.0071 | -65.3% |
| 8.0 | 68.0000 | 97.1% | 0.9606 | 3.4373 | 0.9885 | -65.7% |
| 10.0 | 68.0000 | 97.1% | 0.9507 | 3.3571 | 0.9762 | -65.9% |
| 15.0 | 68.0000 | 95.6% | 0.9262 | 3.1643 | 0.9458 | -66.5% |

## Asset contribution (5 bps, additive share of gross return)

| coin | contribution_pct | share_of_gross_pct | holding_days |
| --- | --- | --- | --- |
| dogecoin | 188.0000 | 24.3000 | 84.0000 |
| shiba-inu | 126.6000 | 16.3000 | 56.0000 |
| solana | 102.5000 | 13.2000 | 70.0000 |
| terra-luna | 90.5000 | 11.7000 | 35.0000 |
| zcash | 46.4000 | 6.0000 | 63.0000 |
| crypto-com-chain | 45.9000 | 5.9000 | 14.0000 |
| stellar | 38.4000 | 5.0000 | 42.0000 |
| aave | 32.8000 | 4.2000 | 7.0000 |
| pepe | 29.9000 | 3.9000 | 21.0000 |
| bitcoin-cash | 28.0000 | 3.6000 | 49.0000 |
