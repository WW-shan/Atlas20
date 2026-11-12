# Maker-first execution diagnostic

- trades: **2524**; notional: **1707.1142**
- bar source: **bitget-mark**
- primary offset / timeout / through: **5bps / 2 bars / 1bps**
- assumptions: maker **2bps**, taker **20bps**, baseline **20bps**
- adverse guard: **off**

## Sensitivity

| index | offset_bps | timeout_bars | trade_count | covered_notional | coverage | notional_fill_rate | effective_cost_bps | price_edge_bps | improvement_bps | positive_improvement_share | unfilled_notional_share | unfilled_improvement_median_bps | unfilled_improvement_p05_bps | guard_triggered_share | timeout_notional_share | adverse_guard_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2.0000 | 1.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9193 | 7.9479 | -4.4954 | 12.0521 | 0.9193 | 0.0807 | -55.9076 | -214.0118 | 0.0000 | 0.0807 | nan |
| 1 | 2.0000 | 2.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9348 | 9.0977 | -5.9240 | 10.9023 | 0.9349 | 0.0652 | -86.5935 | -255.5907 | 0.0000 | 0.0652 | nan |
| 2 | 2.0000 | 4.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9630 | 6.8666 | -4.2005 | 13.1334 | 0.9630 | 0.0370 | -97.2540 | -287.3397 | 0.0000 | 0.0370 | nan |
| 3 | 5.0000 | 1.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.8812 | 7.9610 | -3.8225 | 12.0390 | 0.8812 | 0.1188 | -50.3860 | -195.7512 | 0.0000 | 0.1188 | nan |
| 4 | 5.0000 | 2.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9140 | 8.4464 | -4.8980 | 11.5536 | 0.9141 | 0.0860 | -76.2576 | -278.5524 | 0.0000 | 0.0860 | nan |
| 5 | 5.0000 | 4.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9511 | 6.0032 | -3.1231 | 13.9968 | 0.9511 | 0.0489 | -97.1179 | -331.7520 | 0.0000 | 0.0489 | nan |
| 6 | 10.0000 | 1.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.8286 | 7.7736 | -2.6885 | 12.2264 | 0.8339 | 0.1714 | -41.0873 | -192.0698 | 0.0000 | 0.1714 | nan |
| 7 | 10.0000 | 2.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.8844 | 7.6212 | -3.5401 | 12.3788 | 0.8848 | 0.1156 | -66.5237 | -298.3869 | 0.0000 | 0.1156 | nan |
| 8 | 10.0000 | 4.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9301 | 4.7703 | -1.5118 | 15.2297 | 0.9304 | 0.0699 | -97.1179 | -386.0164 | 0.0000 | 0.0699 | nan |

## Primary yearly breakdown

| index | year | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 2,022.0000 | 413.0000 | 22.5675 | 0.9346 | 3.8528 | 16.1472 |
| 1 | 2,023.0000 | 552.0000 | 70.0108 | 0.9357 | 9.3263 | 10.6737 |
| 2 | 2,024.0000 | 621.0000 | 211.0893 | 0.9247 | 7.7481 | 12.2519 |
| 3 | 2,025.0000 | 495.0000 | 608.2045 | 0.9296 | 3.6769 | 16.3231 |
| 4 | 2,026.0000 | 443.0000 | 795.2422 | 0.8967 | 12.3324 | 7.6676 |

## Primary by side

| index | side | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | buy | 1,154.0000 | 833.9525 | 0.9125 | 9.9192 | 10.0808 |
| 1 | sell | 1,370.0000 | 873.1617 | 0.9154 | 7.0398 | 12.9602 |

## Primary asset breakdown (top 10 by improvement)

| index | asset | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | bittensor | 6.0000 | 8.3946 | 1.0000 | -3.0000 | 23.0000 |
| 1 | algorand | 8.0000 | 0.5688 | 1.0000 | -3.0000 | 23.0000 |
| 2 | filecoin | 14.0000 | 2.5055 | 1.0000 | -3.0000 | 23.0000 |
| 3 | world-liberty-financial | 2.0000 | 3.2745 | 1.0000 | -3.0000 | 23.0000 |
| 4 | celestia | 2.0000 | 2.1045 | 1.0000 | -3.0000 | 23.0000 |
| 5 | chainlink | 97.0000 | 103.9430 | 0.9941 | -2.1687 | 22.1687 |
| 6 | ethereum-classic | 39.0000 | 5.8481 | 0.9890 | -2.1149 | 22.1149 |
| 7 | cosmos | 31.0000 | 1.0441 | 0.9909 | -1.9311 | 21.9311 |
| 8 | ethereum | 104.0000 | 37.8518 | 0.9844 | -1.4725 | 21.4725 |
| 9 | avalanche-2 | 109.0000 | 99.8006 | 0.9794 | -0.0738 | 20.0738 |

## Interpretation guardrails

- Mark high/low is not a tradeable order book; touch-through is a proxy, not proven fill.
- The result does not include queue position, partial fills, cancel latency, venue rejects, ADL or funding.
- This is execution research only. It does not change LS57, LS23 or the live L125-V2 track.
