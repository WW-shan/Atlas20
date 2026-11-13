# Intraday BTC lead-lag fresh OOS

- status: fresh shadow validation only; no orders; no live changes
- data window: 2026-09-01 → 2026-11-13; OOS entries: 2026-10-01 → 2026-11-13
- frozen rules: phase-0 UTC, tail 10%, thresholds 3.0/3.5, single full-gross event
- costs: 6/12/20bps per one-way gross turnover; funding excluded

## Coverage warning

- unavailable assets in the new cache: **matic-network, monero**
- no historical 30m bars were spliced into this OOS; missing assets are excluded for the whole run

## Frozen variants

| index | variant_id | cost_bps_per_side | tier | events | multiple | cagr | sharpe | max_drawdown | bitcoin_multiple | bitcoin_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | LL_P2_8_T30 | 6.0000 | fresh-oos-failed | 2.0000 | 0.9870 | -0.1048 | -4.0361 | -0.0130 | 0.8409 | -4.1561 |
| 1 | LL_P2_8_T30 | 12.0000 | fresh-oos-failed | 2.0000 | 0.9847 | -0.1229 | -4.0728 | -0.0153 | 0.8409 | -4.1561 |
| 2 | LL_P2_8_T30 | 20.0000 | fresh-oos-failed | 2.0000 | 0.9815 | -0.1464 | -4.1023 | -0.0185 | 0.8409 | -4.1561 |
| 3 | LL_P2_8_T35 | 6.0000 | fresh-oos-failed | 2.0000 | 0.9870 | -0.1048 | -4.0361 | -0.0130 | 0.8409 | -4.1561 |
| 4 | LL_P2_8_T35 | 12.0000 | fresh-oos-failed | 2.0000 | 0.9847 | -0.1229 | -4.0728 | -0.0153 | 0.8409 | -4.1561 |
| 5 | LL_P2_8_T35 | 20.0000 | fresh-oos-failed | 2.0000 | 0.9815 | -0.1464 | -4.1023 | -0.0185 | 0.8409 | -4.1561 |
| 6 | LL_P4_8_T30 | 6.0000 | fresh-oos-mixed | 5.0000 | 1.0003 | 0.0027 | 0.0725 | -0.0154 | 0.8409 | -4.1561 |
| 7 | LL_P4_8_T30 | 12.0000 | fresh-oos-mixed | 5.0000 | 0.9943 | -0.0471 | -0.6311 | -0.0178 | 0.8409 | -4.1561 |
| 8 | LL_P4_8_T30 | 20.0000 | fresh-oos-mixed | 5.0000 | 0.9864 | -0.1097 | -1.5371 | -0.0210 | 0.8409 | -4.1561 |
| 9 | LL_P4_8_T35 | 6.0000 | fresh-oos-positive | 4.0000 | 1.0107 | 0.0946 | 1.4159 | -0.0094 | 0.8409 | -4.1561 |
| 10 | LL_P4_8_T35 | 12.0000 | fresh-oos-positive | 4.0000 | 1.0059 | 0.0509 | 0.8075 | -0.0105 | 0.8409 | -4.1561 |
| 11 | LL_P4_8_T35 | 20.0000 | fresh-oos-positive | 4.0000 | 0.9995 | -0.0046 | -0.0426 | -0.0121 | 0.8409 | -4.1561 |
| 12 | LL_PHASE_ENSEMBLE | 6.0000 | fresh-oos-failed | 13.0000 | 0.9963 | -0.0311 | -1.1095 | -0.0076 | 0.8409 | -4.1561 |
| 13 | LL_PHASE_ENSEMBLE | 12.0000 | fresh-oos-failed | 13.0000 | 0.9924 | -0.0626 | -2.2185 | -0.0107 | 0.8409 | -4.1561 |
| 14 | LL_PHASE_ENSEMBLE | 20.0000 | fresh-oos-failed | 13.0000 | 0.9873 | -0.1031 | -3.4360 | -0.0151 | 0.8409 | -4.1561 |

The tier is assigned from the 6bps/12bps pair; the 20bps row is shown separately and does not inherit a positive label by itself.

## Interpretation

This window is short and has low event power. A positive result only keeps LS66 as a shadow candidate; a failed result rejects the frozen LS66 cells without re-tuning phase, tail or threshold on the same data.
