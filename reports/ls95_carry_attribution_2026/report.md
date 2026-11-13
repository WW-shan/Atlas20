# PR2026-11-LS95-LS82-CARRY-ATTRIBUTION

LS95 reruns only the LS82 carry sleeve, without the LS57 base, and attributes its price,
funding and fee PnL by asset, year and side. It is a diagnostic, not a live signal.

## Standalone sleeve

- Terminal multiple: **1.1662x**
- Sharpe: **0.6596**
- Max drawdown: **-8.7032%**
- Attribution/engine daily-return correlation: **0.9948**
- A correlation below 0.95 would make the attribution inconclusive.

## Asset attribution

| index | asset | price_pnl | funding_pnl | fees | net_pnl |
| --- | --- | --- | --- | --- | --- |
| 0 | cardano | 0.2381 | 0.0014 | 0.0194 | 0.2200 |
| 1 | avalanche-2 | 0.0721 | 0.0043 | 0.0179 | 0.0585 |
| 2 | binancecoin | 0.0607 | 0.0120 | 0.0159 | 0.0568 |
| 3 | solana | 0.0416 | 0.0091 | 0.0177 | 0.0330 |
| 4 | ethereum | 0.0257 | 0.0031 | 0.0144 | 0.0143 |
| 5 | bitcoin | 0.0213 | -0.0009 | 0.0177 | 0.0027 |
| 6 | ripple | -0.0120 | 0.0059 | 0.0175 | -0.0237 |
| 7 | dogecoin | -0.1747 | 0.0072 | 0.0172 | -0.1847 |

## Side attribution

| index | side | net_pnl |
| --- | --- | --- |
| 0 | long | 0.1908 |
| 1 | short | -0.0134 |

## Year attribution

| index | year | net_pnl | engine_return |
| --- | --- | --- | --- |
| 0 | 2,022.0000 | -0.0668 | -0.0691 |
| 1 | 2,023.0000 | 0.1574 | 0.1812 |
| 2 | 2,024.0000 | 0.1306 | 0.1163 |
| 3 | 2,025.0000 | -0.0759 | -0.0675 |
| 4 | 2,026.0000 | 0.0317 | 0.0190 |

## Asset-year net PnL

| index | asset | 2022 | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | avalanche-2 | 0.0121 | 0.0252 | 0.0586 | -0.0537 | 0.0163 |
| 1 | binancecoin | -0.0160 | 0.0044 | 0.0720 | -0.0134 | 0.0099 |
| 2 | bitcoin | 0.0175 | 0.0183 | -0.0339 | 0.0052 | -0.0044 |
| 3 | cardano | -0.0011 | 0.0774 | 0.1022 | 0.0276 | 0.0139 |
| 4 | dogecoin | -0.0636 | -0.0385 | -0.0040 | -0.0722 | -0.0063 |
| 5 | ethereum | 0.0180 | -0.0230 | -0.0478 | 0.0325 | 0.0346 |
| 6 | ripple | -0.0078 | 0.0036 | -0.0120 | -0.0038 | -0.0036 |
| 7 | solana | -0.0260 | 0.0900 | -0.0044 | 0.0020 | -0.0286 |

## Side-year net PnL

| index | year | long | short |
| --- | --- | --- | --- |
| 0 | 2,022.0000 | -0.1053 | 0.0386 |
| 1 | 2,023.0000 | 0.2046 | -0.0471 |
| 2 | 2,024.0000 | 0.1481 | -0.0174 |
| 3 | 2,025.0000 | -0.0401 | -0.0357 |
| 4 | 2,026.0000 | -0.0164 | 0.0482 |

## Evidence classification

**asset-concentrated**

The classification only describes the historical source of the carry sleeve's PnL. It does
not promote LS82, change the live track, or justify dropping an asset/year after the fact.

Research output only; no orders sent.
