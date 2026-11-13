# LS57 + residual-gross Top20 churn overlay

- baseline LS57 full: 68.8077x / Sharpe 1.9819 / MDD -39.8350%
- all allocations are pre-registered: 10% / 20% / 25% NAV
- hard combined gross cap: 1.50x
- return-space diagnostic only; funding is not included

## Allocation results

| index | allocation | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | mean_combined_gross | max_combined_gross | mean_sleeve_scale | residual_scaled_days | passes_all |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.1000 | 73.6173 | 2.0128 | -0.3856 | 15.8284 | 2.1403 | 0.4725 | 1.4000 | 0.0604 | 0.0000 | 1.0000 |
| 1 | 0.2000 | 78.6296 | 2.0410 | -0.3727 | 16.4219 | 2.1698 | 0.5329 | 1.5000 | 0.1209 | 0.0000 | 1.0000 |
| 2 | 0.2500 | 81.2613 | 2.0543 | -0.3659 | 16.7250 | 2.1836 | 0.5631 | 1.5000 | 0.1510 | 5.0000 | 1.0000 |

## Decision

Selected largest passing allocation: **25% NAV**.
This only earns a real funding/mark/fill merge study; it is not a live approval.
