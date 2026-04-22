# Stop-Loss Study - TOP20_MOM_top8_biweekly__bull_only

Window: 2021-04-22 to 2026-04-22

## Overlay Summary

| strategy | overlay | description | cagr | sharpe | max_drawdown | annualized_turnover | risk_on_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TOP20_MOM_top8_biweekly__bull_only__BTC_LT_14D | BTC_LT_14D | Exit to cash when BTC closes below its level 14 days earlier; re-enter at next rebalance once the condition clears. | 16.93% | 0.70 | -42.06% | 9.36 | 51.97% |
| TOP20_MOM_top8_biweekly__bull_only__NO_STOP | NO_STOP | No additional stop-loss overlay. | 22.53% | 0.68 | -49.31% | 8.06 | 100.00% |
| TOP20_MOM_top8_biweekly__bull_only__BTC_LT_14D_CONFIRM2 | BTC_LT_14D_CONFIRM2 | Same as BTC_LT_14D but require the new state to persist for 2 consecutive days before switching. | 13.96% | 0.56 | -54.82% | 8.63 | 51.86% |
| TOP20_MOM_top8_biweekly__bull_only__BTC_LT_20DMA | BTC_LT_20DMA | Exit to cash when BTC closes below its 20-day moving average; re-enter at next rebalance once back above. | 7.26% | 0.39 | -49.37% | 9.42 | 49.95% |

## Notes

- Market-based stop overlays trigger on daily BTC data and exit the portfolio on the next trading day.
- Re-entry occurs on the next scheduled rebalance date once the overlay condition is risk-on again.
- This study isolates stop overlays on one strategy, rather than applying them to the full strategy grid.