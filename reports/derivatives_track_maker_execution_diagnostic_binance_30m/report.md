# Maker-first execution diagnostic

- trades: **2524**; notional: **1707.1142**
- bar source: **binance-30m**
- primary offset / timeout / through: **5bps / 2 bars / 1bps**
- assumptions: maker **2bps**, taker **20bps**, baseline **20bps**

## Sensitivity

| index | offset_bps | timeout_bars | trade_count | covered_notional | coverage | notional_fill_rate | effective_cost_bps | price_edge_bps | improvement_bps | positive_improvement_share | unfilled_notional_share | unfilled_improvement_median_bps | unfilled_improvement_p05_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2.0000 | 1.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.9188 | 6.9236 | -3.4613 | 13.0764 | 0.9188 | 0.0812 | -35.9066 | -134.0355 |
| 1 | 2.0000 | 2.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.9313 | 6.8959 | -3.6595 | 13.1041 | 0.9313 | 0.0687 | -52.0497 | -214.3813 |
| 2 | 2.0000 | 4.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.9444 | 7.2071 | -4.2055 | 12.7929 | 0.9444 | 0.0556 | -84.8828 | -262.4378 |
| 3 | 5.0000 | 1.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8645 | 8.7833 | -4.3451 | 11.2167 | 0.8661 | 0.1355 | -28.0184 | -134.1023 |
| 4 | 5.0000 | 2.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8870 | 6.5360 | -2.5015 | 13.4640 | 0.8885 | 0.1130 | -45.7896 | -208.2369 |
| 5 | 5.0000 | 4.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.9199 | 7.0446 | -3.6023 | 12.9554 | 0.9199 | 0.0801 | -71.5711 | -310.3193 |
| 6 | 10.0000 | 1.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.7868 | 8.9455 | -3.1081 | 11.0545 | 0.7968 | 0.2132 | -24.1463 | -126.7197 |
| 7 | 10.0000 | 2.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8358 | 6.4551 | -1.5000 | 13.5449 | 0.8392 | 0.1642 | -37.2340 | -165.5664 |
| 8 | 10.0000 | 4.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8895 | 6.2786 | -2.2887 | 13.7214 | 0.8895 | 0.1105 | -61.9342 | -303.2974 |

## Primary yearly breakdown

| index | year | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 2,022.0000 | 368.0000 | 20.6527 | 0.9069 | 4.4066 | 15.5934 |
| 1 | 2,023.0000 | 539.0000 | 69.2490 | 0.9490 | 0.9998 | 19.0002 |
| 2 | 2,024.0000 | 563.0000 | 195.1649 | 0.9178 | 6.9274 | 13.0726 |
| 3 | 2,025.0000 | 394.0000 | 469.2577 | 0.9122 | 5.6401 | 14.3599 |
| 4 | 2,026.0000 | 383.0000 | 638.8086 | 0.8516 | 7.7436 | 12.2564 |

## Primary by side

| index | side | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | buy | 1,016.0000 | 682.9857 | 0.8707 | 6.1659 | 13.8341 |
| 1 | sell | 1,231.0000 | 710.1472 | 0.9026 | 6.8920 | 13.1080 |

## Primary asset breakdown (top 10 by improvement)

| index | asset | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | filecoin | 14.0000 | 2.5055 | 1.0000 | -3.0000 | 23.0000 |
| 1 | celestia | 2.0000 | 2.1045 | 1.0000 | -3.0000 | 23.0000 |
| 2 | bittensor | 6.0000 | 8.3946 | 1.0000 | -3.0000 | 23.0000 |
| 3 | ethereum | 104.0000 | 37.8518 | 0.9824 | -1.9757 | 21.9757 |
| 4 | ethereum-classic | 39.0000 | 5.8481 | 0.9765 | -1.9460 | 21.9460 |
| 5 | litecoin | 87.0000 | 43.1910 | 0.9747 | -1.1647 | 21.1647 |
| 6 | uniswap | 53.0000 | 15.6936 | 0.9764 | -0.4914 | 20.4914 |
| 7 | sui | 129.0000 | 87.1645 | 0.9665 | -0.4686 | 20.4686 |
| 8 | avalanche-2 | 109.0000 | 99.8006 | 0.9542 | 0.4259 | 19.5741 |
| 9 | dogecoin | 150.0000 | 54.8723 | 0.9515 | 0.7322 | 19.2678 |

## Interpretation guardrails

- Mark high/low is not a tradeable order book; touch-through is a proxy, not proven fill.
- The result does not include queue position, partial fills, cancel latency, venue rejects, ADL or funding.
- This is execution research only. It does not change LS57, LS23 or the live L125-V2 track.
