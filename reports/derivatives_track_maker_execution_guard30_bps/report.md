# Maker-first execution diagnostic

- trades: **2524**; notional: **1707.1142**
- bar source: **bitget-mark**
- primary offset / timeout / through: **5bps / 2 bars / 1bps**
- assumptions: maker **2bps**, taker **20bps**, baseline **20bps**
- adverse guard: **30.0**

## Sensitivity

| index | offset_bps | timeout_bars | trade_count | covered_notional | coverage | notional_fill_rate | effective_cost_bps | price_edge_bps | improvement_bps | positive_improvement_share | unfilled_notional_share | unfilled_improvement_median_bps | unfilled_improvement_p05_bps | guard_triggered_share | timeout_notional_share | adverse_guard_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2.0000 | 1.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9193 | 7.9479 | -4.4954 | 12.0521 | 0.9193 | 0.0807 | -55.9076 | -214.0118 | 0.0664 | 0.0143 | 30.0000 |
| 1 | 2.0000 | 2.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9259 | 7.7886 | -4.4551 | 12.2114 | 0.9260 | 0.0741 | -67.1078 | -242.0684 | 0.0680 | 0.0061 | 30.0000 |
| 2 | 2.0000 | 4.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9292 | 7.7265 | -4.4513 | 12.2735 | 0.9292 | 0.0708 | -72.5061 | -244.1254 | 0.0694 | 0.0015 | 30.0000 |
| 3 | 5.0000 | 1.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.8812 | 7.9610 | -3.8225 | 12.0390 | 0.8812 | 0.1188 | -50.3860 | -195.7512 | 0.0793 | 0.0395 | 30.0000 |
| 4 | 5.0000 | 2.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9048 | 7.0604 | -3.3468 | 12.9396 | 0.9049 | 0.0952 | -64.1730 | -214.0846 | 0.0849 | 0.0103 | 30.0000 |
| 5 | 5.0000 | 4.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.9117 | 6.8772 | -3.2880 | 13.1228 | 0.9117 | 0.0883 | -66.8157 | -218.1344 | 0.0867 | 0.0016 | 30.0000 |
| 6 | 10.0000 | 1.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.8286 | 7.7736 | -2.6885 | 12.2264 | 0.8339 | 0.1714 | -41.0873 | -192.0698 | 0.1099 | 0.0615 | 30.0000 |
| 7 | 10.0000 | 2.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.8671 | 6.4553 | -2.0629 | 13.5447 | 0.8674 | 0.1329 | -59.4904 | -214.1865 | 0.1196 | 0.0133 | 30.0000 |
| 8 | 10.0000 | 4.0000 | 2,524.0000 | 1,707.1142 | 1.0000 | 0.8753 | 6.2271 | -1.9824 | 13.7729 | 0.8754 | 0.1247 | -65.9679 | -240.0759 | 0.1229 | 0.0018 | 30.0000 |

## Primary yearly breakdown

| index | year | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 2,022.0000 | 413.0000 | 22.5675 | 0.9207 | 5.0012 | 14.9988 |
| 1 | 2,023.0000 | 552.0000 | 70.0108 | 0.9323 | 5.0302 | 14.9698 |
| 2 | 2,024.0000 | 621.0000 | 211.0893 | 0.9089 | 8.0900 | 11.9100 |
| 3 | 2,025.0000 | 495.0000 | 608.2045 | 0.9240 | 5.8527 | 14.1473 |
| 4 | 2,026.0000 | 443.0000 | 795.2422 | 0.8861 | 7.9479 | 12.0521 |

## Primary by side

| index | side | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | buy | 1,154.0000 | 833.9525 | 0.8997 | 6.5886 | 13.4114 |
| 1 | sell | 1,370.0000 | 873.1617 | 0.9097 | 7.5110 | 12.4890 |

## Primary asset breakdown (top 10 by improvement)

| index | asset | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | bittensor | 6.0000 | 8.3946 | 1.0000 | -3.0000 | 23.0000 |
| 1 | algorand | 8.0000 | 0.5688 | 1.0000 | -3.0000 | 23.0000 |
| 2 | filecoin | 14.0000 | 2.5055 | 1.0000 | -3.0000 | 23.0000 |
| 3 | world-liberty-financial | 2.0000 | 3.2745 | 1.0000 | -3.0000 | 23.0000 |
| 4 | celestia | 2.0000 | 2.1045 | 1.0000 | -3.0000 | 23.0000 |
| 5 | ethereum-classic | 39.0000 | 5.8481 | 0.9890 | -2.3814 | 22.3814 |
| 6 | cosmos | 31.0000 | 1.0441 | 0.9909 | -2.3403 | 22.3403 |
| 7 | ethereum | 104.0000 | 37.8518 | 0.9844 | -1.9618 | 21.9618 |
| 8 | chainlink | 97.0000 | 103.9430 | 0.9867 | -1.8310 | 21.8310 |
| 9 | avalanche-2 | 109.0000 | 99.8006 | 0.9768 | -1.2769 | 21.2769 |

## Interpretation guardrails

- Mark high/low is not a tradeable order book; touch-through is a proxy, not proven fill.
- The result does not include queue position, partial fills, cancel latency, venue rejects, ADL or funding.
- This is execution research only. It does not change LS57, LS23 or the live L125-V2 track.
