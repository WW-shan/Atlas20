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
| 0 | 0.2500 | 10.0000 | 73.8635 | 2.0107 | -0.3959 | 15.9876 | 2.1407 | 0.6611 | 1.4500 | 0.2491 | 41.0000 | 44.0000 | 0.0017 |
| 1 | 0.5000 | 10.0000 | 78.0014 | 2.0326 | -0.3960 | 16.6143 | 2.1671 | 0.8940 | 1.4500 | 0.4819 | 171.0000 | 131.0000 | 0.0141 |
| 2 | 1.0000 | 10.0000 | 83.0200 | 2.0571 | -0.3953 | 17.3554 | 2.1978 | 1.2977 | 1.4500 | 0.8856 | 572.0000 | 386.0000 | 0.0595 |
| 3 | 0.2500 | 20.0000 | 73.7396 | 2.0100 | -0.3963 | 15.9779 | 2.1403 | 0.6611 | 1.4500 | 0.2491 | 41.0000 | 44.0000 | 0.0034 |
| 4 | 0.5000 | 20.0000 | 76.9169 | 2.0270 | -0.3985 | 16.4893 | 2.1622 | 0.8940 | 1.4500 | 0.4819 | 171.0000 | 131.0000 | 0.0282 |
| 5 | 1.0000 | 20.0000 | 78.2794 | 2.0339 | -0.4011 | 16.7281 | 2.1737 | 1.2977 | 1.4500 | 0.8856 | 572.0000 | 386.0000 | 0.1189 |

## Decision

**PASS (research integration only; not live approval)**

A pass only earns same-venue spot/perp data, funding, margin and small-order
execution research. It does not change `PR2026-10-D-L125-V2` or place orders.
