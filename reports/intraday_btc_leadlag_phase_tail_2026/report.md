# Intraday BTC lead-lag phase/tail follow-up

- status: research backtest only; no orders; no live changes
- construction: phase-0 UTC schedule, tail 10%, one full-gross event at a time
- thresholds: abs(z) >= 3.0 / 3.5 on k=2/4, h=8
- costs: 6/12/20bps per one-way gross turnover; funding excluded

## Variant summary

| index | variant_id | tier | events | events_per_year | average_active_gross | max_active_gross | turnover | missing_return_observations | full_multiple_6 | full_sharpe_6 | full_mdd_6 | validation_sharpe_6 | full_multiple_12 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LL_P2_8_T30 | rejected-now | 184.0000 | 38.7368 | 0.0177 | 1.0000 | 368.0000 | 0.0000 | 1.0674 | 0.1733 | -0.1645 | 0.1971 | 0.8560 |
| 1 | LL_P2_8_T35 | rejected-now | 122.0000 | 25.6842 | 0.0117 | 1.0000 | 244.0000 | 0.0000 | 0.9994 | 0.0479 | -0.1659 | 0.0204 | 0.8633 |
| 2 | LL_P4_8_T30 | watch | 194.0000 | 40.8421 | 0.0186 | 1.0000 | 388.0000 | 0.0000 | 1.3269 | 0.6047 | -0.0603 | 0.7030 | 1.0514 |
| 3 | LL_P4_8_T35 | watch | 134.0000 | 28.2105 | 0.0129 | 1.0000 | 268.0000 | 0.0000 | 1.5548 | 0.9612 | -0.0428 | 0.9744 | 1.3240 |
| 4 | LL_PHASE_ENSEMBLE | watch | 634.0000 | 133.4737 | 0.0152 | 1.0000 | 317.0000 | 0.0000 | 1.2225 | 0.4679 | -0.0775 | 0.4885 | 1.0109 |

## 6bps sample metrics

| index | variant_id | sample | days | multiple | cagr | sharpe | max_drawdown | bitcoin_multiple | bitcoin_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LL_P2_8_T30 | discovery | 730.0000 | 1.0147 | 0.0073 | 0.1381 | -0.0819 | 0.8860 | 0.1655 |
| 1 | LL_P2_8_T30 | full | 1,734.0000 | 1.0674 | 0.0138 | 0.1733 | -0.1645 | 1.7523 | 0.4864 |
| 2 | LL_P2_8_T30 | validation | 1,004.0000 | 1.0520 | 0.0186 | 0.1971 | -0.1645 | 1.9777 | 0.7600 |
| 3 | LL_P2_8_T35 | discovery | 730.0000 | 1.0139 | 0.0070 | 0.1561 | -0.0440 | 0.8860 | 0.1655 |
| 4 | LL_P2_8_T35 | full | 1,734.0000 | 0.9994 | -0.0001 | 0.0479 | -0.1659 | 1.7523 | 0.4864 |
| 5 | LL_P2_8_T35 | validation | 1,004.0000 | 0.9857 | -0.0052 | 0.0204 | -0.1659 | 1.9777 | 0.7600 |
| 6 | LL_P4_8_T30 | discovery | 730.0000 | 1.0560 | 0.0277 | 0.4404 | -0.0603 | 0.8860 | 0.1655 |
| 7 | LL_P4_8_T30 | full | 1,734.0000 | 1.3269 | 0.0614 | 0.6047 | -0.0603 | 1.7523 | 0.4864 |
| 8 | LL_P4_8_T30 | validation | 1,004.0000 | 1.2565 | 0.0866 | 0.7030 | -0.0448 | 1.9777 | 0.7600 |
| 9 | LL_P4_8_T35 | discovery | 730.0000 | 1.1348 | 0.0654 | 1.1636 | -0.0381 | 0.8860 | 0.1655 |
| 10 | LL_P4_8_T35 | full | 1,734.0000 | 1.5548 | 0.0974 | 0.9612 | -0.0428 | 1.7523 | 0.4864 |
| 11 | LL_P4_8_T35 | validation | 1,004.0000 | 1.3701 | 0.1214 | 0.9744 | -0.0428 | 1.9777 | 0.7600 |
| 12 | LL_PHASE_ENSEMBLE | discovery | 730.0000 | 1.0553 | 0.0273 | 0.5345 | -0.0456 | 0.8860 | 0.1655 |
| 13 | LL_PHASE_ENSEMBLE | full | 1,734.0000 | 1.2225 | 0.0432 | 0.4679 | -0.0775 | 1.7523 | 0.4864 |
| 14 | LL_PHASE_ENSEMBLE | validation | 1,004.0000 | 1.1585 | 0.0550 | 0.4885 | -0.0775 | 1.9777 | 0.7600 |

## Selection-bias warning

Phase 0, the 10% tails and the 3.0/3.5 thresholds were observed in the preceding LS63–LS65 research. This is therefore a phase-selected follow-up, not a fresh OOS. The validation window is reported only to test whether the selected mechanism survived the later sample; it cannot validate a live strategy by itself.

## Execution guardrail

Binance 30m OHLC is a fill proxy. Funding, Bitget book depth, partial fills, minimum notional, hidden liquidity and a fresh post-2026-09-30 OOS are absent. This result can only justify a shadow execution study, never an automatic live change.
