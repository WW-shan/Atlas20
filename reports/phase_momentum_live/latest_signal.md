# Latest Phase-Momentum Signal

- As of: 2026-10-07
- Evaluated range: 2022-01-01 .. 2026-10-07 (phase offsets count from 2022-01-01)
- Panel last date: 2026-10-07
- Trial: PR2026-10-H3
- Latest target date: 2026-10-03
- Trade required: False
- Last day complete: True
- BTC gate open: True
- Gross exposure: 0.683682
- Current gross exposure: 0.706208
- Next check date: 2026-10-08
- Rule: Strict point-in-time Top20; 24 sleeves = 2 books at [0.50, 0.50] x 4 trailing-return signals (weighted_multi_horizon, ret21, equal_7_14_28_60, equal_14_21_28) x 3 calendar phases of a 3D rebalance cycle; book A: hold while in Top2, BTC 100D MA + confirm2, 60D volatility target at 80%; book B: hold while in Top2, BTC 100D MA + confirm2, Top20 breadth >= 0.50 above own 50D SMA, 60D volatility target at 80%; long-only spot, no leverage; T+1

## Aggregate Targets

The target to trade toward. It is new only when trade required is True.

| Asset | Weight |
| --- | ---: |
| near | 0.683682 |

## Current Book

Production-engine weights at the as-of close, after drift and before
trading a target dated that day (20 bps cost).

| Asset | Weight |
| --- | ---: |
| near | 0.706208 |

## Current Sleeve Snapshot

| Book | Signal | Phase | Asset | Weight | Target date |
| ---: | --- | ---: | --- | ---: | --- |
| 0 | weighted_multi_horizon | 0 | near | 0.665611 | 2026-10-01 |
| 0 | weighted_multi_horizon | 1 | near | 0.663180 | 2026-10-02 |
| 0 | weighted_multi_horizon | 2 | near | 0.663833 | 2026-10-03 |
| 0 | ret21 | 0 | near | 0.686952 | 2026-09-30 |
| 0 | ret21 | 1 | near | 0.694782 | 2026-09-29 |
| 0 | ret21 | 2 | near | 0.693504 | 2026-09-28 |
| 0 | equal_7_14_28_60 | 0 | near | 0.665611 | 2026-10-01 |
| 0 | equal_7_14_28_60 | 1 | near | 0.709490 | 2026-09-23 |
| 0 | equal_7_14_28_60 | 2 | near | 0.663833 | 2026-10-03 |
| 0 | equal_14_21_28 | 0 | near | 0.686952 | 2026-09-30 |
| 0 | equal_14_21_28 | 1 | near | 0.705276 | 2026-09-20 |
| 0 | equal_14_21_28 | 2 | near | 0.705158 | 2026-09-21 |
| 1 | weighted_multi_horizon | 0 | near | 0.665611 | 2026-10-01 |
| 1 | weighted_multi_horizon | 1 | near | 0.663180 | 2026-10-02 |
| 1 | weighted_multi_horizon | 2 | near | 0.663833 | 2026-10-03 |
| 1 | ret21 | 0 | near | 0.686952 | 2026-09-30 |
| 1 | ret21 | 1 | near | 0.694782 | 2026-09-29 |
| 1 | ret21 | 2 | near | 0.693504 | 2026-09-28 |
| 1 | equal_7_14_28_60 | 0 | near | 0.665611 | 2026-10-01 |
| 1 | equal_7_14_28_60 | 1 | near | 0.709490 | 2026-09-23 |
| 1 | equal_7_14_28_60 | 2 | near | 0.663833 | 2026-10-03 |
| 1 | equal_14_21_28 | 0 | near | 0.686952 | 2026-09-30 |
| 1 | equal_14_21_28 | 1 | near | 0.705276 | 2026-09-20 |
| 1 | equal_14_21_28 | 2 | near | 0.705158 | 2026-09-21 |

This file is a signal snapshot only. It does not place orders.
