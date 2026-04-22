# Sector-Lead V3 Study

Window: 2021-04-22 to 2026-04-22

## Summary

| strategy | variant | cagr | sharpe | max_drawdown | annualized_turnover | average_holdings | cagr_delta_vs_best_momentum | sharpe_delta_vs_best_momentum | drawdown_improvement_vs_best_momentum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SECTOR_LEAD_V3D_top1_biweekly__bull_only__BTC_LT_21D | V3+STOP | 34.20% | 0.82 | -53.10% | 9.99 | 0.18 | 11.67% | 0.14 | -3.79% |
| SECTOR_LEAD_V3C_top2_biweekly__bull_only__BTC_LT_21D | V3+STOP | 22.91% | 0.70 | -60.95% | 9.89 | 0.36 | 0.38% | 0.02 | -11.64% |
| TOP20_MOM_top8_biweekly__bull_only | BASELINE | 22.53% | 0.68 | -49.31% | 8.06 | 2.75 | 0.00% | 0.00 | 0.00% |
| SECTOR_LEAD_V3A_top2_biweekly__bull_only | V3A | 22.40% | 0.65 | -61.08% | 13.38 | 0.69 | -0.13% | -0.03 | -11.76% |
| SECTOR_LEAD_V3B_top1_biweekly__bull_only | V3B | 18.53% | 0.57 | -80.75% | 14.39 | 0.35 | -4.00% | -0.11 | -31.43% |
| TOP20_SECTOR_top4_biweekly__bull_only | BASELINE | 11.47% | 0.47 | -62.57% | 9.71 | 2.11 | -11.06% | -0.21 | -13.26% |

## Variant definitions

- `BASELINE`: best existing momentum and sector references from the main pipeline.
- `V3A`: top 2 sectors, concentrated 60/40 weights, one leader per sector, no daily stop overlay.
- `V3B`: top 1 sector, 100% in the sector leader, no daily stop overlay.
- `V3+STOP`: same concentrated sector-lead constructions but with BTC 21-day trailing-price risk-off overlay.

## Notes

- Sector-Lead V3 reduces sector diversification on purpose to chase theme leaders.
- Positive `drawdown_improvement_vs_best_momentum` means a shallower drawdown than `TOP20_MOM_top8_biweekly__bull_only`.