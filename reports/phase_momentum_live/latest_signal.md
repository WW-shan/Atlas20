# Latest Phase-Momentum Signal

- As of: 2026-10-08
- Evaluated range: 2022-01-01 .. 2026-10-08 (phase offsets count from 2022-01-01)
- Panel last date: 2026-10-08
- Trial: PR2026-10-H5
- Latest target date: 2026-10-08
- Trade required: True
- Last day complete: True
- BTC gate open: True
- Gross exposure: 0.621428
- Current gross exposure: 0.460486
- Next check date: 2026-10-09
- Rule: Strict point-in-time Top20; 24 sleeves = 2 books at [0.50, 0.50] x 4 trailing-return signals (weighted_multi_horizon, ret21, equal_7_14_28_60, equal_14_21_28) x 3 calendar phases of a 3D rebalance cycle; book A: hold while in Top2, BTC 100D MA + confirm2, 60D volatility target at 80%, dispersion overlay P75 (21D dispersion, 252D lookback); book B: hold while in Top2, BTC 100D MA + confirm2, Top20 breadth >= 0.50 above own 50D SMA, 60D volatility target at 80%, dispersion overlay P75 (21D dispersion, 252D lookback); long-only spot, no leverage; T+1

## Aggregate Targets

The target to trade toward. It is new only when trade required is True.

| Asset | Weight |
| --- | ---: |
| near | 0.621428 |

## Current Book

Production-engine weights at the as-of close, after drift and before
trading a target dated that day (20 bps cost).

| Asset | Weight |
| --- | ---: |
| near | 0.460486 |

## Current Sleeve Snapshot

| Book | Signal | Phase | Asset | Weight | Target date |
| ---: | --- | ---: | --- | ---: | --- |
| 0 | weighted_multi_horizon | 0 | near | 0.621428 | 2026-10-08 |
| 0 | weighted_multi_horizon | 1 | near | 0.621428 | 2026-10-08 |
| 0 | weighted_multi_horizon | 2 | near | 0.621428 | 2026-10-08 |
| 0 | ret21 | 0 | near | 0.621428 | 2026-10-08 |
| 0 | ret21 | 1 | near | 0.621428 | 2026-10-08 |
| 0 | ret21 | 2 | near | 0.621428 | 2026-10-08 |
| 0 | equal_7_14_28_60 | 0 | near | 0.621428 | 2026-10-08 |
| 0 | equal_7_14_28_60 | 1 | near | 0.621428 | 2026-10-08 |
| 0 | equal_7_14_28_60 | 2 | near | 0.621428 | 2026-10-08 |
| 0 | equal_14_21_28 | 0 | near | 0.621428 | 2026-10-08 |
| 0 | equal_14_21_28 | 1 | near | 0.621428 | 2026-10-08 |
| 0 | equal_14_21_28 | 2 | near | 0.621428 | 2026-10-08 |
| 1 | weighted_multi_horizon | 0 | near | 0.621428 | 2026-10-08 |
| 1 | weighted_multi_horizon | 1 | near | 0.621428 | 2026-10-08 |
| 1 | weighted_multi_horizon | 2 | near | 0.621428 | 2026-10-08 |
| 1 | ret21 | 0 | near | 0.621428 | 2026-10-08 |
| 1 | ret21 | 1 | near | 0.621428 | 2026-10-08 |
| 1 | ret21 | 2 | near | 0.621428 | 2026-10-08 |
| 1 | equal_7_14_28_60 | 0 | near | 0.621428 | 2026-10-08 |
| 1 | equal_7_14_28_60 | 1 | near | 0.621428 | 2026-10-08 |
| 1 | equal_7_14_28_60 | 2 | near | 0.621428 | 2026-10-08 |
| 1 | equal_14_21_28 | 0 | near | 0.621428 | 2026-10-08 |
| 1 | equal_14_21_28 | 1 | near | 0.621428 | 2026-10-08 |
| 1 | equal_14_21_28 | 2 | near | 0.621428 | 2026-10-08 |

This file is a signal snapshot only. It does not place orders.
