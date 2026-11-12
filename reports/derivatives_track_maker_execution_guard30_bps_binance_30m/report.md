# Maker-first execution diagnostic

- trades: **2524**; notional: **1707.1142**
- bar source: **binance-30m**
- primary offset / timeout / through: **5bps / 2 bars / 1bps**
- assumptions: maker **2bps**, taker **20bps**, baseline **20bps**
- adverse guard: **30.0**

## Sensitivity

| index | offset_bps | timeout_bars | trade_count | covered_notional | coverage | notional_fill_rate | effective_cost_bps | price_edge_bps | improvement_bps | positive_improvement_share | unfilled_notional_share | unfilled_improvement_median_bps | unfilled_improvement_p05_bps | guard_triggered_share | timeout_notional_share | adverse_guard_bps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2.0000 | 1.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.9188 | 6.9236 | -3.4613 | 13.0764 | 0.9188 | 0.0812 | -35.9066 | -134.0355 | 0.0585 | 0.0227 | 30.0000 |
| 1 | 2.0000 | 2.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.9283 | 6.6858 | -3.3954 | 13.3142 | 0.9283 | 0.0717 | -48.7805 | -135.0576 | 0.0610 | 0.0106 | 30.0000 |
| 2 | 2.0000 | 4.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.9349 | 6.5139 | -3.3420 | 13.4861 | 0.9349 | 0.0651 | -54.8986 | -144.7714 | 0.0649 | 0.0002 | 30.0000 |
| 3 | 5.0000 | 1.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8645 | 8.7833 | -4.3451 | 11.2167 | 0.8661 | 0.1355 | -28.0184 | -134.1023 | 0.0914 | 0.0440 | 30.0000 |
| 4 | 5.0000 | 2.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8784 | 8.5353 | -4.3457 | 11.4647 | 0.8799 | 0.1216 | -44.9168 | -136.8257 | 0.0980 | 0.0237 | 30.0000 |
| 5 | 5.0000 | 4.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8861 | 8.5507 | -4.5003 | 11.4493 | 0.8861 | 0.1139 | -53.7816 | -153.6359 | 0.1081 | 0.0059 | 30.0000 |
| 6 | 10.0000 | 1.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.7868 | 8.9455 | -3.1081 | 11.0545 | 0.7968 | 0.2132 | -24.1463 | -126.7197 | 0.1248 | 0.0883 | 30.0000 |
| 7 | 10.0000 | 2.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8226 | 8.3833 | -3.1906 | 11.6167 | 0.8257 | 0.1774 | -41.3949 | -135.3323 | 0.1361 | 0.0413 | 30.0000 |
| 8 | 10.0000 | 4.0000 | 2,247.0000 | 1,393.1329 | 0.8161 | 0.8398 | 8.0456 | -3.1617 | 11.9544 | 0.8398 | 0.1602 | -50.6532 | -149.1902 | 0.1491 | 0.0112 | 30.0000 |

## Primary yearly breakdown

| index | year | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 2,022.0000 | 368.0000 | 20.6527 | 0.8776 | 7.2449 | 12.7551 |
| 1 | 2,023.0000 | 539.0000 | 69.2490 | 0.9253 | 3.8701 | 16.1299 |
| 2 | 2,024.0000 | 563.0000 | 195.1649 | 0.9012 | 7.2895 | 12.7105 |
| 3 | 2,025.0000 | 394.0000 | 469.2577 | 0.9053 | 6.2191 | 13.7809 |
| 4 | 2,026.0000 | 383.0000 | 638.8086 | 0.8465 | 11.1648 | 8.8352 |

## Primary by side

| index | side | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | buy | 1,016.0000 | 682.9857 | 0.8597 | 10.3263 | 9.6737 |
| 1 | sell | 1,231.0000 | 710.1472 | 0.8963 | 6.8128 | 13.1872 |

## Primary asset breakdown (top 10 by improvement)

| index | asset | trade_count | notional | notional_fill_rate | effective_cost_bps | improvement_bps |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | celestia | 2.0000 | 2.1045 | 1.0000 | -3.0000 | 23.0000 |
| 1 | bittensor | 6.0000 | 8.3946 | 1.0000 | -3.0000 | 23.0000 |
| 2 | filecoin | 14.0000 | 2.5055 | 0.9953 | -2.6968 | 22.6968 |
| 3 | ethereum | 104.0000 | 37.8518 | 0.9824 | -1.8721 | 21.8721 |
| 4 | ethereum-classic | 39.0000 | 5.8481 | 0.9618 | -1.0354 | 21.0354 |
| 5 | uniswap | 53.0000 | 15.6936 | 0.9764 | -0.6824 | 20.6824 |
| 6 | litecoin | 87.0000 | 43.1910 | 0.9653 | -0.4289 | 20.4289 |
| 7 | avalanche-2 | 109.0000 | 99.8006 | 0.9528 | 0.6644 | 19.3356 |
| 8 | dogecoin | 150.0000 | 54.8723 | 0.9443 | 1.4820 | 18.5180 |
| 9 | stellar | 116.0000 | 98.8254 | 0.9340 | 1.9330 | 18.0670 |

## Interpretation guardrails

- Mark high/low is not a tradeable order book; touch-through is a proxy, not proven fill.
- The result does not include queue position, partial fills, cancel latency, venue rejects, ADL or funding.
- This is execution research only. It does not change LS57, LS23 or the live L125-V2 track.
