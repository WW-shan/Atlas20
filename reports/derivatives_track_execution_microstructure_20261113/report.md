# Execution microstructure sample

- equity reference: **500.00 USDT**
- requested snapshots: **12**
- read-only: **yes**; orders sent: **no**

| asset | symbol | obs | median spread bps | p95 spread bps | median impact bps | p95 impact bps | max impact bps | min fill ratio | median depth25/order |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| hyperliquid | HYPEUSDT | 12 | 0.2090 | 0.7591 | 0.0000 | 0.2404 | 0.4344 | 1.0000 | 2094.9299 |
| monero | XMRUSDT | 12 | 4.0330 | 6.1731 | 0.1805 | 0.4192 | 0.4640 | 1.0000 | 927.1393 |
| near | NEARUSDT | 12 | 0.2916 | 0.2916 | 0.0000 | 0.0000 | -0.0000 | 1.0000 | 13494.9586 |

The impact estimate walks the public visible book for an immediate order.
It excludes fees, queue position, hidden liquidity, partial fills, rejections and latency.
An off-window sample does not prove execution quality at the actual rebalance.
