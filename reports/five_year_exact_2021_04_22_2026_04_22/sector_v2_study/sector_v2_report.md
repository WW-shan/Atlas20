# Sector V2 Study

Window: 2021-04-22 to 2026-04-22

## Summary

| strategy | variant | cagr | sharpe | max_drawdown | annualized_turnover | average_holdings | cagr_delta_vs_best_baseline | sharpe_delta_vs_best_baseline | drawdown_improvement_vs_best_baseline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SECTOR_V2B_top3_biweekly__bull_only__BTC_LT_21D | BTC_LT_21D | 18.16% | 0.65 | -59.86% | 8.96 | 0.82 | 6.69% | 0.18 | 2.71% |
| TOP20_SECTOR_top4_biweekly__bull_only__BTC_LT_21D | BTC_LT_21D | 16.55% | 0.64 | -60.51% | 8.80 | 1.09 | 5.08% | 0.17 | 2.06% |
| TOP20_SECTOR_top4_biweekly__bull_only | BASELINE | 11.47% | 0.47 | -62.57% | 9.71 | 2.11 | 0.00% | 0.00 | 0.00% |
| SECTOR_V2B_top3_biweekly__bull_only | V2B | 11.13% | 0.46 | -68.07% | 10.55 | 1.57 | -0.34% | -0.01 | -5.50% |
| SECTOR_V2A_top3_biweekly__bull_only | V2A | 9.46% | 0.43 | -64.26% | 9.39 | 1.57 | -2.01% | -0.04 | -1.69% |
| TOP20_SECTOR_top3_biweekly__bull_only | BASELINE | 8.84% | 0.41 | -61.52% | 10.87 | 1.59 | -2.63% | -0.06 | 1.05% |
| SECTOR_V2C_top3_biweekly__bull_only | V2C | 7.22% | 0.39 | -72.51% | 10.80 | 1.04 | -4.25% | -0.08 | -9.94% |

## Variant definitions

- `BASELINE`: existing sector rotation from the main research pipeline.
- `V2A`: stronger sector score with breadth and leader strength, equal weight across sectors, top 2 coins per sector.
- `V2B`: same stronger score, but sector weights follow rank emphasis (roughly 50/30/20).
- `V2C`: V2B plus single-leader selection inside each sector.
- `BTC_LT_21D`: adds a daily BTC trailing-price stop overlay that exits to cash when BTC falls below its 21-day-ago close and re-enters on the next eligible rebalance.

## Notes

- Positive `drawdown_improvement_vs_best_baseline` means a shallower drawdown than the best baseline sector strategy.
- The comparison baseline is `TOP20_SECTOR_top4_biweekly__bull_only` because it was the strongest baseline sector variant in this exact five-year window.