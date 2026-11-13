# LS57 + residual-gross churn overlay with funding

- baseline LS57 full: 68.8077x / Sharpe 1.9819 / MDD -39.8350%
- sleeve funding: Binance 8h settlement proxy, UTC daily sum; missing rates are skipped
- weighted funding coverage: 92.5972%
- missing held-weight observations: 76.841071
- return-space diagnostic; Bitget mark/fill and liquidation are not included

## Allocation results

| index | allocation | full_multiple | full_sharpe | full_max_drawdown | validation_multiple | validation_sharpe | mean_combined_gross | max_combined_gross | funding_sum | scale_change_cost_sum | funding_coverage | passes_all |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.1000 | 73.2946 | 2.0109 | -0.3863 | 15.8168 | 2.1397 | 0.4725 | 1.4000 | -0.0020 | 0.0024 | 0.9260 | 1.0000 |
| 1 | 0.2000 | 77.9415 | 2.0372 | -0.3742 | 16.3978 | 2.1686 | 0.5329 | 1.5000 | -0.0039 | 0.0048 | 0.9260 | 1.0000 |
| 2 | 0.2500 | 80.3435 | 2.0494 | -0.3680 | 16.6928 | 2.1820 | 0.5631 | 1.5000 | -0.0049 | 0.0064 | 0.9260 | 1.0000 |

## Decision

A pass is only a funding-aware overlay candidate; it still requires Bitget exact funding, mark/fill, margin and forward OOS verification.
