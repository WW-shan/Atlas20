# BTC Trailing Stop Scan - TOP20_SECTOR_top4_biweekly__bull_only

Window: 2021-04-22 to 2026-04-22

## Summary

| strategy | overlay | cagr | sharpe | max_drawdown | annualized_turnover | risk_on_fraction | cagr_delta_vs_no_stop | drawdown_improvement_vs_no_stop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TOP20_SECTOR_top4_biweekly__bull_only__BTC_LT_21D | BTC_LT_21D | 16.55% | 0.64 | -60.51% | 8.80 | 50.22% | 5.08% | 2.06% |
| TOP20_SECTOR_top4_biweekly__bull_only__BTC_LT_14D | BTC_LT_14D | 13.13% | 0.59 | -50.49% | 9.54 | 51.97% | 1.66% | 12.08% |
| TOP20_SECTOR_top4_biweekly__bull_only__BTC_LT_10D | BTC_LT_10D | 10.15% | 0.51 | -43.41% | 8.84 | 52.03% | -1.32% | 19.16% |
| TOP20_SECTOR_top4_biweekly__bull_only__NO_STOP | NO_STOP | 11.47% | 0.47 | -62.57% | 9.71 | 100.00% | 0.00% | 0.00% |
| TOP20_SECTOR_top4_biweekly__bull_only__BTC_LT_28D | BTC_LT_28D | 6.41% | 0.35 | -62.31% | 10.30 | 52.08% | -5.06% | 0.26% |
| TOP20_SECTOR_top4_biweekly__bull_only__BTC_LT_20DMA | BTC_LT_20DMA | 5.26% | 0.32 | -57.70% | 9.55 | 49.95% | -6.21% | 4.87% |

## Notes

- Daily BTC stop signals trigger exits on the next trading day.
- Re-entry happens at the next scheduled rebalance once BTC is back in risk-on mode.
- Positive `drawdown_improvement_vs_no_stop` means a shallower drawdown than the no-stop baseline.