# PR2026-11-LS99-LS57-BASIS-RESIDUAL

LS99 integrates the LS98 BTC/ETH long-spot / short-perp research proxy into
the residual gross of frozen LS57. It is not a live signal and does not prove
same-venue Bitget spot execution, funding, margin or settlement.

- Sample: 2022-01-01 00:00:00+00:00 → 2026-09-20 00:00:00+00:00 (1724 daily observations)
- LS57 baseline: 68.8077x / Sharpe 1.9819 / MDD -39.8350%
- Combined gross cap: 1.45x; basis sleeve full gross: 1.00x
- Primary basis cost: 10bps per leg per side; 20bps is the stress row
- Allocations are fixed at 25% / 50% / 100% of the residual-gross sleeve

## Results

| index | allocation | basis_cost_bps | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | mean_combined_gross | max_combined_gross | mean_scale | residual_scaled_days | scale_change_days | total_scale_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.2500 | 10.0000 | 71.2333 | 1.9960 | -0.3973 | 15.6041 | 2.1241 | 0.6611 | 1.4500 | 0.2491 | 41.0000 | 44.0000 | 0.0017 |
| 1 | 0.5000 | 10.0000 | 72.7587 | 2.0047 | -0.3984 | 15.8525 | 2.1352 | 0.8940 | 1.4500 | 0.4819 | 171.0000 | 131.0000 | 0.0141 |
| 2 | 1.0000 | 10.0000 | 73.4237 | 2.0086 | -0.3997 | 15.9684 | 2.1412 | 1.2977 | 1.4500 | 0.8856 | 572.0000 | 386.0000 | 0.0595 |
| 3 | 0.2500 | 20.0000 | 71.1138 | 1.9953 | -0.3977 | 15.5946 | 2.1237 | 0.6611 | 1.4500 | 0.2491 | 41.0000 | 44.0000 | 0.0034 |
| 4 | 0.5000 | 20.0000 | 71.7471 | 1.9991 | -0.4009 | 15.7332 | 2.1302 | 0.8940 | 1.4500 | 0.4819 | 171.0000 | 131.0000 | 0.0282 |
| 5 | 1.0000 | 20.0000 | 69.2308 | 1.9853 | -0.4055 | 15.3911 | 2.1171 | 1.2977 | 1.4500 | 0.8856 | 572.0000 | 386.0000 | 0.1189 |

## Decision

**PASS (research integration only; not live approval)**

A pass only earns same-venue spot/perp data, funding, margin and small-order
execution research. It does not change `PR2026-10-D-L125-V2` or place orders.
